---
name: orientation
description: Overview of what the Prefect MCP server can do and its access boundaries. Load before using Prefect MCP tools to learn which tools to reach for and when to use the Prefect CLI instead.
---

# Prefect MCP Orientation

Default Prefect inspection tools are read-only. For ordinary mutations, use the CLI.

If experimental execution-plan authoring is enabled, `execution_plans_get_schema` can retrieve the Cloud-authored document schema, and `execution_plans_publish` can create and activate execution-plan versions with credentials that have those write permissions.

Use `docs_get_release_notes` for the latest or version-specific Prefect OSS release notes. Use `docs_search_prefect` for other Prefect concepts, usage examples, and best practices.

Use `get_object_schema` to get JSON schemas for complex objects like automations.
