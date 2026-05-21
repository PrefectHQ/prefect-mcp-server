"""Eval for diagnosing flow runs that crash due to concurrency lease renewal failure.

Based on real user issues:
- https://github.com/PrefectHQ/prefect/issues/19068
- https://github.com/PrefectHQ/prefect/issues/18839

The scenario mirrors Prefect's own integration tests in
prefect/integration-tests/test_concurrency_leases.py: a flow holds a concurrency
slot, the underlying `renew_concurrency_lease` API call starts failing, and
Prefect's real renewal loop -> retry logic -> crash handler runs end-to-end,
terminating the flow run.

We only mock the HTTP boundary (the client method that talks to the API). The
retry policy, error logging through the run logger, and cancel-scope-driven
crash all execute for real, so an agent diagnosing the crash sees the same
state and log message it would in production.
"""

from collections.abc import Awaitable, Callable
from unittest import mock
from uuid import uuid4

import httpx
import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient, SyncPrefectClient
from prefect.client.schemas.actions import GlobalConcurrencyLimitCreate
from prefect.client.schemas.objects import FlowRun
from prefect.concurrency.sync import concurrency
from pydantic_ai import Agent


@pytest.fixture
async def crashed_flow_run(prefect_client: PrefectClient) -> FlowRun:
    """Actually crash a flow run by forcing lease renewal to fail at the HTTP boundary.

    Patches:
    - `_RENEWAL_FRACTION` / `_RENEWAL_MAX_ATTEMPTS` / `_RENEWAL_RETRY_BASE_DELAY`
      so the failure surfaces within seconds instead of the production cadence.
    - `SyncPrefectClient.renew_concurrency_lease` raises `httpx.ConnectError`,
      simulating the network blip Prefect's renewal retries are meant to absorb.

    Everything downstream of the patched call - retry/backoff, `get_run_logger()`
    emitting the "Concurrency lease renewal failed" message, the watcher
    cancel scope, and the resulting CRASHED state - runs for real.
    """
    limit_name = f"db-connection-pool-{uuid4().hex[:8]}"
    await prefect_client.create_global_concurrency_limit(
        concurrency_limit=GlobalConcurrencyLimitCreate(name=limit_name, limit=1)
    )

    def failing_renew(
        self: SyncPrefectClient, lease_id: object, lease_duration: float
    ) -> None:
        raise httpx.ConnectError("Simulated network failure during lease renewal")

    @flow(name=f"db-sync-job-{uuid4().hex[:8]}")
    def db_sync_job() -> str:
        # strict=True -> raise_on_lease_renewal_failure=True, so a real renewal
        # failure cancels the cancel scope and crashes the run.
        # lease_duration=60 is the minimum the API accepts; _RENEWAL_FRACTION=0.01
        # below makes the first renewal attempt fire ~0.6s into the sleep.
        with concurrency(limit_name, occupy=1, strict=True, lease_duration=60):
            import time

            time.sleep(3)
        return "done"

    with (
        mock.patch("prefect.concurrency._leases._RENEWAL_FRACTION", 0.01),
        mock.patch("prefect.concurrency._leases._RENEWAL_MAX_ATTEMPTS", 1),
        mock.patch("prefect.concurrency._leases._RENEWAL_RETRY_BASE_DELAY", 0.1),
        mock.patch.object(SyncPrefectClient, "renew_concurrency_lease", failing_renew),
    ):
        try:
            db_sync_job(return_state=True)
        except BaseException:
            # CancelledError from the cancel scope is a BaseException
            pass

    runs = await prefect_client.read_flow_runs()
    assert runs, "expected a flow run to have been recorded"
    return runs[0]


async def test_diagnoses_lease_renewal_failure(
    simple_agent: Agent,
    crashed_flow_run: FlowRun,
    evaluate_response: Callable[[str, str], Awaitable[None]],
) -> None:
    """Agent should diagnose the CRASHED run as a concurrency lease renewal failure."""
    assert crashed_flow_run.state is not None
    assert crashed_flow_run.state.type.value == "CRASHED", (
        f"expected CRASHED but got {crashed_flow_run.state.type.value}; "
        f"message={crashed_flow_run.state.message!r}"
    )

    prompt = f"My flow run '{crashed_flow_run.name}' crashed. What happened?"

    async with simple_agent:
        result = await simple_agent.run(prompt)

    await evaluate_response(
        "Does the agent identify that the crash was due to concurrency lease "
        "renewal failure? The response should mention 'lease' or that "
        "concurrency slot reservation could not be maintained.",
        result.output,
    )
