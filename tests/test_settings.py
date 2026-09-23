import pytest
from pydantic import ValidationError

from prefect_mcp_server.settings import LogfireSettings


def test_logfire_sampling_matches_prefect_testbed_defaults() -> None:
    settings = LogfireSettings()

    assert settings.service_name == "prefect-mcp-server"
    assert settings.sampling_head_rate == 0.1
    assert settings.sampling_level_threshold == "warn"
    assert settings.sampling_duration_threshold == 5.0
    assert settings.sampling_background_rate == 0.01


def test_logfire_sampling_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGFIRE_SERVICE_NAME", "prefect-mcp-server-evals")
    monkeypatch.setenv("LOGFIRE_SAMPLING_HEAD_RATE", "0.25")
    monkeypatch.setenv("LOGFIRE_SAMPLING_LEVEL_THRESHOLD", "error")
    monkeypatch.setenv("LOGFIRE_SAMPLING_DURATION_THRESHOLD", "2.5")
    monkeypatch.setenv("LOGFIRE_SAMPLING_BACKGROUND_RATE", "0.05")

    settings = LogfireSettings()

    assert settings.service_name == "prefect-mcp-server-evals"
    assert settings.sampling_head_rate == 0.25
    assert settings.sampling_level_threshold == "error"
    assert settings.sampling_duration_threshold == 2.5
    assert settings.sampling_background_rate == 0.05


@pytest.mark.parametrize("field", ["sampling_head_rate", "sampling_background_rate"])
@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_logfire_sampling_rejects_invalid_rates(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        LogfireSettings.model_validate({field: value})
