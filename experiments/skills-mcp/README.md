# Skills over MCP experiment

This opt-in stdio server exposes Prefect MCP's existing tools alongside a bundled
`prefect-database-retention` skill using FastMCP's experimental Skills extension
(SEP-2640). It proves out `skills/list`, `skills/get`, verified resource reads,
and an agent planning retention against real Prefect run records. The skill is
distilled from the [advanced database maintenance guide](https://docs.prefect.io/v3/advanced/database-maintenance).

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

## Discovery and plugin coexistence

The bundled skill is specific to self-hosted database retention. It is separate
from the plugin's existing `workflows` skill; neither is installed over the other.
It adds no tools, prompts, or server instructions. A legacy client keeps the
existing tool descriptions and can ignore skills entirely. FastMCP also lists
the files as ordinary `skill://` resources, so they are visible in resource
browsers even without Skills-extension support; they are not completely hidden.
Only a skills-aware host adapter advertises the skill catalog to the model.

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
corrupted-resource rejection, and the unchanged legacy tool/prompt surface.
The live eval seeds an ephemeral Prefect API with old terminal runs, a recent
completion that started long ago, and an active run. The agent must preview only
the eligible records and propose a 30-day policy that preserves event retention,
starts the missing background services, requires backup/approval, and avoids
`VACUUM FULL` for a no-downtime scenario. Configuration is validated with the
installed Prefect settings model; assertions do not depend on report wording.

The same scenario runs with and without the existing plugin's `workflows`
instructions loaded. A negative case asks for a flow listing and verifies that
the database skill is not loaded. The eval does not execute deletion, change
settings, or test PostgreSQL maintenance itself; its API fixture uses SQLite.
It uses Claude Haiku 4.5 by default (`SKILLS_EVAL_MODEL` overrides it), with a
15-request limit per cleanup scenario and no LLM judge.

The `Skills over MCP experiment` workflow runs protocol tests on PRs, and the
paid eval on same-repository PRs, main, and manual dispatch. Fork PRs run only
the protocol tests because they do not receive API credentials. Eval failures
fail the job; JUnit output is retained as an artifact.
