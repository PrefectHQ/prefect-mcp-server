---
name: prefect-database-retention
description: Plan cleanup of old flow-run history in a self-hosted Prefect database, including retention settings, candidate previews, and post-deletion storage maintenance. Use for growing Prefect databases or retiring old run history, not deployment creation or individual run failures.
---
# Retire old Prefect run history

Distilled from [How to maintain your Prefect database](https://docs.prefect.io/v3/advanced/database-maintenance).

Call `get_identity` to establish the connected instance and version. This is a
self-hosted maintenance procedure; do not prescribe server database settings or
SQL access for a Prefect Cloud workspace. For Cloud, explain that its retention
is managed separately and link the relevant Cloud guidance.

Establish the retention window, whether the user wants a preview or execution,
and how server background services run. Do not choose a destructive cutoff on
the user's behalf. The MCP inspection tools can preview records but cannot
change server settings, delete runs, or run SQL. Separate proposed actions from
anything actually executed.

Read [references/retention.md](references/retention.md) when preparing the cleanup
plan. It distinguishes Prefect's deletion service from PostgreSQL VACUUM and
covers version-sensitive configuration and alternatives.

For a candidate preview, query `get_flow_runs` with a bounded `limit` (100) and
filters for terminal states (`COMPLETED`, `FAILED`, `CANCELLED`, `CRASHED`), an
`end_time.before_` cutoff in UTC, and `parent_task_run_id.is_null_=true` for
top-level runs. Do not select by creation time alone or include active runs.
Report full UUIDs. A truncated response is a sample, not a complete deletion
inventory; the background service re-evaluates eligibility when it runs.

Recommend the smallest maintenance change consistent with the evidence and the
installed version. Include what history would be lost, which process needs the
settings, how to verify cleanup, and what remains unknown (for example, actual
PostgreSQL table bloat). A preview does not authorize deletion or a recurring
cleanup policy. Before an approved rollout, verify a database backup and test
on a non-production instance; do not treat this skill as execution permission.
