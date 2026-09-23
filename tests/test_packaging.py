from pathlib import Path

from tomllib import loads


def test_logfire_is_a_runtime_dependency() -> None:
    pyproject = loads((Path(__file__).parents[1] / "pyproject.toml").read_text())

    assert "logfire>=4.9.0" in pyproject["project"]["dependencies"]
