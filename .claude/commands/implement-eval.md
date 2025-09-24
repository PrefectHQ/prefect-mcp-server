these are instructions for implementing an eval for the Prefect MCP server.

- start by reading @evals/README.md for context
- read issue #$ARGUMENTS for detail on the eval
- add a new file in @evals/
    - do server state setup in a fixture
    - add a test case that prompts the agent and asserts on its behavior
- verify that the eval passes by running `just evals`
- update @evals/README.md to include the new eval in the table
