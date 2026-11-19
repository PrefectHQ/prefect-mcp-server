# Choosing a retention mechanism

Source: [Prefect database maintenance](https://docs.prefect.io/v3/advanced/database-maintenance), reviewed 2026-11-04.
The guide evolves with Prefect. Check the installed server's settings before
using newer options. The basic settings below are also present in Prefect 3.7.1.

## Prefer the built-in service for an age-based policy

For a user-approved 30-day flow-run policy, propose these settings on the server's
background-service process:

```bash
PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED="events,flow_runs"
PREFECT_SERVER_SERVICES_DB_VACUUM_RETENTION_PERIOD=2592000
PREFECT_SERVER_SERVICES_DB_VACUUM_BATCH_SIZE=200
```

Substitute the requested retention duration in seconds. Keep existing event
cleanup enabled; event history has its own setting,
`PREFECT_SERVER_EVENTS_RETENTION_PERIOD`. Changing flow-run retention does not
change event retention. Do not shorten event history without considering the
user's automation requirements.

Flow-run cleanup selects old terminal runs by **end time**. Recently finished
runs and runs still active must remain. Its batching removes associated logs
and artifacts; explain that loss of history. Changing a CLI profile on the
operator's laptop does not configure a remote service.

When the API starts with `--no-services`, with multiple workers, or in a scaled
deployment, a separate `prefect server services start` process must be running
with the same database and retention settings. Verify actual cleanup in service
logs and by querying the remaining run history; an environment variable alone
does not prove the service ran.

The latest guide also describes an independently configurable `orphans` mode.
Do not assume older servers accept it; verify version support first. The normal
flow-run cleanup path is preferable to inventing a direct SQL deletion cascade.

## Custom policies and direct SQL

Use a custom retention flow only when age-based cleanup is insufficient. The
guide's custom example filters on `start_time`, whereas the built-in service
uses `end_time`; these select different runs. In particular, a long-running
flow may have started long ago but finished recently.

Preview candidates before deletion, preserve nonterminal runs, use small
batches, and stop on persistent deletion failures instead of retrying the same
batch forever. Direct SQL bypasses application cleanup and may leave orphaned
logs and artifacts; plan version-appropriate reconciliation if SQL is necessary.
Do not use `prefect server database reset` as a retention procedure.

## Reclaiming PostgreSQL storage is a separate decision

Prefect's database vacuum service deletes records. PostgreSQL autovacuum or
`VACUUM ANALYZE` makes dead-tuple space reusable and refreshes statistics; it does
not generally shrink the database files on disk. Inspect table sizes and
`pg_stat_user_tables` before choosing physical maintenance.

`VACUUM FULL` rewrites a table and takes an exclusive lock, blocking reads and
writes. It is unsuitable for a no-downtime cleanup. If returning space to the OS
is necessary, assess a maintenance window or `pg_repack` with the database
operator rather than promising an immediate online shrink.
