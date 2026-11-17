from importlib.metadata import requires


def test_logfire_is_a_runtime_dependency() -> None:
    runtime_requirements = requires("prefect-mcp") or []

    assert "logfire>=5.6.0" in runtime_requirements
