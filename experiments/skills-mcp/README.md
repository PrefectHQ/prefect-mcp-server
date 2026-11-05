# Skills over MCP experiment

This opt-in stdio server exposes Prefect MCP's existing tools alongside a bundled
`diagnose-flow-run` skill using FastMCP's experimental Skills extension
(SEP-2640). It proves out `skills/list`, `skills/get`, verified resource reads,
and an agent applying the retrieved instructions to a real failed Prefect run.

## Run

From the repository root:

```bash
uv sync --frozen
uv sync --project experiments/skills-mcp --frozen
uv run --project experiments/skills-mcp --frozen prefect-mcp-skills --repo "$PWD"
```

Configure that command as a stdio MCP server in a skills-aware client. Prefect
credentials and API URL are inherited by the backend. The experiment does not
add authentication or provide a hosted endpoint.

The gateway has its own project, environment, and lockfile. It runs FastMCP
4.2.0a3 and Pydantic AI 2; a stdio proxy launches the checked-out Prefect MCP
server in the root project's FastMCP 3 environment. This avoids reopening the
production MCP SDK/instrumentation migration in #189 and #220. The production
entrypoints and dependency resolution are unchanged. Alpha APIs may change.

## Client experiment

`agent.py` is a minimal Pydantic AI adapter, not a general-purpose skill installer.
It advertises only names/descriptions discovered from this one server. The model
chooses `load_skill`; FastMCP's `read_skill` verifies the manifest, frontmatter,
sizes, and hashes before the adapter exposes instructions. Supporting files are
exposed separately through `read_skill_file`. The whole skill is fetched during
loading, but only the requested contents enter the model context.

This adapter trusts the bundled documentation skill for this experiment. It has
no shell tool, never installs files, and does not implement general third-party
skill approval, caching, or cross-server composition. It does not enable native
skills support in Codex or Pi; those clients would need a separate adapter.

## Verification

```bash
uv run --project experiments/skills-mcp --frozen pytest experiments/skills-mcp/tests -q
ANTHROPIC_API_KEY=... uv run --project experiments/skills-mcp --frozen pytest experiments/skills-mcp/evals -q
```

The protocol tests exercise real MCP discovery, verified reads, tool proxying,
and rejection of corrupted resource bytes. The live eval starts an ephemeral
Prefect API, runs a flow that fails CSV validation, and asks for an incident
handoff without naming the skill or providing its body. It requires a skill
load, supporting-file read, run and log queries, the actual UUID and failing
column, the reference's report headings, and an unchanged run state. It uses
Claude Haiku 4.5 by default (`SKILLS_EVAL_MODEL` overrides it), with a 15-request
limit and no LLM judge.

The `Skills over MCP experiment` workflow runs protocol tests on PRs, and the
paid eval on same-repository PRs, main, and manual dispatch. Fork PRs run only
the protocol tests because they do not receive API credentials. Eval failures
fail the job; JUnit output is retained as an artifact.
