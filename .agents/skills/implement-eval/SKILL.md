---
name: implement-eval
description: Implement or update scenario-focused evaluations for the Prefect MCP server. Use when adding eval coverage from a GitHub issue or a described support scenario, preparing Prefect server state, prompting the test agent, asserting user-facing behavior, running evals, and updating the eval catalog.
---

# Implement a Prefect MCP eval

1. Read `AGENTS.md` and `evals/README.md` before making changes.
2. Resolve the requested scenario:
   - If the user provides a GitHub issue number or URL, read it with an available GitHub integration or the `gh` CLI.
   - Otherwise, use the scenario described by the user.
   - Identify the user-facing question, required Prefect state, expected investigation, and success criteria.
3. Inspect related evals and fixtures before choosing a file location. Extend an existing scenario directory when appropriate; otherwise add a focused test under `evals/`.
4. Implement the eval:
   - Create server state in a fixture.
   - Prompt the agent in language a Prefect user or support engineer would use.
   - Assert on the final behavior or answer, not incidental wording or private implementation details.
   - Keep protocol behavior in unit tests rather than evals.
5. Run the narrowest relevant eval first, then run the full suite with `just evals`.
6. Add or update the eval's row in `evals/README.md`.
7. Review the diff for unrelated changes and report the scenario covered and verification performed.

Do not add live credentials, harness-specific argument placeholders, or client-specific tool syntax to the skill.
