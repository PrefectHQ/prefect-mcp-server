---
name: sdk
description: Write idiomatic Prefect 3.x Python - flows, tasks, concurrency, caching, serving, and deployments. Use when writing or reviewing code that imports prefect, or deciding how to structure and run a workflow.
---

# Prefect SDK (3.x)

Assume Prefect 3.x. For version-sensitive details, use the Prefect MCP docs
tools or https://docs.prefect.io/v3 instead of memory. If code was written for
Prefect 2.x, follow the
[upgrade guide](https://docs.prefect.io/v3/how-to-guides/migrate/upgrade-to-prefect-3).

## Flows and tasks

```python
from prefect import flow, task


@task(retries=3, retry_delay_seconds=10)
def fetch(url: str) -> dict: ...


@flow(log_prints=True)
def pipeline(urls: list[str]):
    futures = fetch.map(urls)
    return futures.result()
```

- `@flow` on the entrypoint. `@task` for the discrete steps worth retrying,
  caching, or running concurrently - prefer small tasks, but plain function
  calls inside a flow are fine.
- Type-annotate flow parameters: they validate with pydantic and become the
  deployment's parameter schema in the UI.
- A flow's final state follows its return value. Return the futures or states
  you care about so task failures fail the flow; return
  `Completed(name="Skipped")`-style manual states for custom outcomes.
  See [states](https://docs.prefect.io/v3/concepts/states).

## Running tasks: call, submit, or delay

| Method | Returns | Use for |
|---|---|---|
| `fetch(url)` | result | sequential steps |
| `fetch.submit(url)` / `fetch.map(urls)` | future(s) | concurrency within a flow |
| `fetch.delay(url)` | future | background work outside a flow, served by task workers |

Resolve submitted futures (`.result()` or `wait()`) in the flow that created
them. `.map` + submit run on the flow's task runner - `ThreadPoolTaskRunner`
by default; pass `task_runner=ProcessPoolTaskRunner()` (or Dask/Ray from
`prefect[dask]`/`prefect[ray]`) on the flow for parallelism.
Match sync/async along a call chain: await async flows and tasks.

## Retries, caching, concurrency

- Retries: `@task(retries=3, retry_delay_seconds=[1, 10, 100])` or
  `prefect.tasks.exponential_backoff`.
- Caching: on by default per cache key (inputs + task code + run id) once
  result persistence is on (`PREFECT_RESULTS_PERSIST_BY_DEFAULT=true`). Tune
  with `cache_policy` and `cache_expiration`.
  See [caching](https://docs.prefect.io/v3/concepts/caching).
- Shared-resource limits: `from prefect.concurrency.sync import concurrency`
  (context manager, slot held for the duration) or `rate_limit` (controls
  start frequency). Tag-based task limits and work-pool/deployment limits
  cover the orchestration layer.
  See [concurrency limits](https://docs.prefect.io/v3/concepts/global-concurrency-limits).

## Running on a schedule

Pick the lowest rung that works:

1. Call the flow - local runs get full orchestration and UI visibility.
2. `flow.serve(name=..., cron=...)` - one long-lived process, no
   infrastructure config.
3. `flow.from_source(source="https://github.com/org/repo", entrypoint="flows/etl.py:pipeline").deploy(name=..., work_pool_name=...)`
   - dynamic infrastructure via work pools and workers.
4. `prefect.yaml` + `prefect deploy` - declarative form of (3) for repos with
   many deployments.

Schedules (`cron=`, `interval=`, `rrule=`, `schedules=[...]`) live on the
deployment. See
[deployments](https://docs.prefect.io/v3/how-to-guides/deployments/deploy-via-python).

## Config, secrets, runtime

- Small config: `prefect.variables.Variable`. Secrets and connections:
  blocks (`Secret.load("name")`, `AwsCredentials.load("name")`).
- Run metadata: `from prefect import runtime` -
  `runtime.flow_run.name`, `runtime.deployment.parameters`, etc.

## Testing

`prefect_test_harness` from `prefect.testing.utilities` gives tests an
ephemeral API; call `my_task.fn(...)` to unit-test task logic directly.

## With the Prefect MCP tools

When adapting code to an existing workspace, read real state first:
`get_work_pools` for valid `work_pool_name` values, `get_deployments` for
existing schedules and parameters. Use the docs tools for anything
version-sensitive.
