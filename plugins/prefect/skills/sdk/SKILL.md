---
name: sdk
description: Write idiomatic Prefect 3.x Python - flows, tasks, retries, caching, serving, and deployments. Use when writing or reviewing code that imports prefect, migrating from Prefect 2.x or another orchestrator, or deciding how to structure and deploy a workflow.
---

# Prefect SDK (3.x)

Assume Prefect 3.x. Verify version-sensitive API details against current
documentation (via the Prefect MCP docs tools when available) instead of memory -
many 2.x APIs were removed and are common hallucinations.

## Core idioms

```python
from prefect import flow, task


@task(retries=3, retry_delay_seconds=10)
def fetch(url: str) -> dict: ...


@flow(log_prints=True)
def pipeline(urls: list[str]):
    results = fetch.map(urls)  # concurrent task runs, returns futures
    return results.result()    # resolve before leaving the flow
```

- `@flow` on the entrypoint, `@task` on discrete units you want retried, cached,
  or run concurrently. Plain function calls inside a flow are fine - don't wrap
  everything in tasks.
- Tasks are called (`fetch(url)`), submitted (`fetch.submit(url)` returns a
  `PrefectFuture`), or mapped (`fetch.map(urls)`). Resolve futures with
  `.result()` before returning from the flow.
- Type-annotate flow parameters - Prefect validates and coerces them with
  pydantic, and they become the deployment's parameter schema in the UI.
- `log_prints=True` or `from prefect import get_run_logger` for logging.
- Caching: `@task(cache_policy=...)` / `cache_expiration=...`. In 3.x, caching
  is based on cache policies (inputs + code by default when configured), not
  the 2.x `cache_key_fn`-everywhere pattern (still supported, not the default).
- Retries with backoff: `@task(retries=3, retry_delay_seconds=[1, 10, 100])` or
  `exponential_backoff(backoff_factor=...)` with `retry_jitter_factor`.

## Async

- An async flow must be awaited; a sync flow is just called. Do not mix by
  calling an async task from a sync flow without awaiting semantics - in 3.x
  a sync flow calling an async task returns a coroutine, it is NOT auto-awaited
  (this changed from 2.x and is a top migration bug).
- Pick one color per call chain: sync flow -> sync tasks, async flow -> async
  tasks (or `.submit()` which works in both).

## Running and deploying

Decision ladder - pick the lowest rung that works:

1. **Just call the flow** - local execution, full orchestration and UI
   visibility. No deployment needed.
2. **`flow.serve(name=...)`** - long-lived process that turns the flow into a
   deployment and listens for scheduled/triggered runs. No work pool, no
   infrastructure config. Default for "I want this on a schedule."
3. **`flow.from_source(source=..., entrypoint=...).deploy(name=..., work_pool_name=...)`**
   - dynamic infrastructure via a work pool and worker. Use when runs need
   their own containers/pods or code lives in git:

```python
from prefect import flow

flow.from_source(
    source="https://github.com/org/repo",
    entrypoint="flows/etl.py:pipeline",
).deploy(name="prod", work_pool_name="my-pool", cron="0 6 * * *")
```

4. **`prefect.yaml` + `prefect deploy`** - declarative equivalent of (3) for
   repos with many deployments.

Schedules go on the deployment (`cron=`, `interval=`, `rrule=`, or
`schedules=[...]`), never in flow code as a sleep loop.

## Gotchas (2.x habits and common hallucinations)

- `Deployment.build_from_flow()` does not exist in 3.x. Use
  `flow.deploy()` / `flow.serve()` / `prefect deploy`.
- Agents and infrastructure blocks (`KubernetesJob`, `ECSTask`, ...) are gone.
  Use work pools + workers; infrastructure config lives on the work pool as
  job variables.
- Storage blocks for code (`GitHub`, `S3` block as flow storage) are replaced by
  `flow.from_source(...)`.
- `Flow.deploy(schedule=...)` was removed - the argument is `schedules` (or the
  `cron`/`interval`/`rrule` shorthands).
- A flow's final state is now determined by its return value; task failures
  inside a flow do not automatically fail it unless their results/futures are
  returned or raised. Return the futures/states you care about.
- `prefect.context` from 2.x is `prefect.runtime` (e.g.
  `from prefect import runtime; runtime.flow_run.name`).
- Results passed between mapped tasks must be treated as immutable - don't
  mutate a shared object across mapped runs.
- Prefect 3.x is pydantic v2 only. No pydantic v1 models as parameters.

## Configuration, state, and secrets

- Small config: Prefect **Variables** (`from prefect.variables import Variable`).
- Secrets and connection info: **Blocks** (`Secret.load("name")`,
  `AwsCredentials.load("name")`, ...). Never hardcode credentials in flow code.
- Runtime metadata: `prefect.runtime` (flow run id, deployment name,
  scheduled start time, parameters).
- Cross-run/team coordination: global concurrency limits
  (`from prefect.concurrency.sync import concurrency`) and tag-based task
  concurrency limits.

## Testing

```python
from prefect.testing.utilities import prefect_test_harness

def test_pipeline():
    with prefect_test_harness():
        assert pipeline(["https://example.com"]) is not None
```

Test task logic directly via `my_task.fn(...)` when orchestration isn't the
thing under test.

## Using the Prefect MCP tools alongside this skill

When the Prefect MCP server is connected:

- Look up current API signatures, settings, and release notes with the docs
  tools instead of answering from memory.
- When adapting code to an existing workspace, read real state first -
  `get_work_pools` for valid `work_pool_name` values, `get_deployments` for
  existing schedules and parameters - rather than inventing names.
