---
name: release-notes
description: Find what changed in the latest or a specific Prefect OSS release. Use for Prefect release notes, changelogs, version changes, upgrade summaries, and "what's new" questions.
---

# Prefect Release Notes

Use the Prefect MCP server's `docs_get_release_notes` tool for Prefect OSS
release-note questions.

- Pass `version="latest"` when the user asks what is new or what changed in the
  latest release.
- Pass an exact patch version when the user names one.
- Include the exact version, release date, concise highlights, and source URL in
  the answer.
- Do not infer the latest release from model knowledge, the locally installed
  Prefect version, or generic documentation search.
