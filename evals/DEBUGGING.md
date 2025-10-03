# Debugging Eval Failures

## Useful Logfire Queries

### Find which tools were called in recent eval runs

```sql
SELECT
  span_name,
  message,
  start_timestamp
FROM records
WHERE service_name = 'nate'  -- or 'ci' for CI runs
  AND start_timestamp > now() - interval '30 minutes'
  AND span_name = 'running tool'
ORDER BY start_timestamp ASC
```

### Get tool inputs and outputs

```sql
SELECT
  span_name,
  message,
  attributes
FROM records
WHERE service_name = 'nate'
  AND start_timestamp > now() - interval '30 minutes'
  AND span_name = 'running tool'
ORDER BY start_timestamp ASC
```

The `attributes` field contains:
- `tool_arguments`: What the agent passed to the tool
- `tool_response`: What the tool returned

### See the sequence of agent actions

```sql
SELECT
  span_name,
  message,
  start_timestamp
FROM records
WHERE service_name = 'nate'
  AND start_timestamp > now() - interval '30 minutes'
  AND (span_name LIKE '%tool%' OR span_name LIKE '%chat%')
ORDER BY start_timestamp ASC
```

This shows the pattern of: chat → run tool → chat → run tool, which helps identify if the agent is stuck in a loop.

### Find available service names

```sql
SELECT DISTINCT service_name
FROM records
WHERE start_timestamp > now() - interval '15 minutes'
```

Use this to find the right service_name for your query (local runs vs CI).

## Common Patterns

### Agent stuck in docs search loop

**Symptom**: Multiple `docs_search_prefect` calls, no `write_file` or `run_shell_command`

**Diagnosis**: Agent has information but won't take action. Usually means:
- Task is too complex for the model
- Output type constraint is too strict (agent unsure it can meet requirements)
- Prompt needs to be more directive about expected workflow

**Fix**: Simplify the task, relax output requirements, or make prompt more explicit about steps.

### Agent not calling expected tools

**Symptom**: Tool call spy assertions fail

**Diagnosis**: Use the queries above to see what the agent actually called

**Fix**: Check if the tool exists, if the agent has access to it, if the prompt guides toward using it.
