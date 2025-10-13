"""Tests for Prefect docs MCP server settings."""

import pytest
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def mock_turbopuffer_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock Turbopuffer environment variables for testing."""
    monkeypatch.setenv("TURBOPUFFER_API_KEY", "test-api-key")


def test_docs_mcp_settings_defaults() -> None:
    """Test that DocsMCPSettings has sensible defaults."""
    from docs_mcp_server._settings import DocsMCPSettings

    settings = DocsMCPSettings()

    assert settings.top_k == 5
    assert settings.max_tokens == 900
    assert settings.include_attributes == []
    assert settings.turbopuffer.namespace == "docs-v1"
    assert settings.logfire.environment == "local"
    assert settings.logfire.send_to_logfire == "if-token-present"
    assert settings.logfire.console is False


def test_docs_mcp_settings_top_k_validation() -> None:
    """Test that top_k is validated correctly."""
    from docs_mcp_server._settings import DocsMCPSettings

    # Valid values
    settings = DocsMCPSettings(top_k=1)
    assert settings.top_k == 1

    settings = DocsMCPSettings(top_k=20)
    assert settings.top_k == 20

    # Invalid values should raise ValidationError
    with pytest.raises(ValidationError):
        DocsMCPSettings(top_k=0)

    with pytest.raises(ValidationError):
        DocsMCPSettings(top_k=21)

    with pytest.raises(ValidationError):
        DocsMCPSettings(top_k=-1)


def test_docs_mcp_settings_max_tokens_validation() -> None:
    """Test that max_tokens is validated correctly."""
    from docs_mcp_server._settings import DocsMCPSettings

    # Valid values
    settings = DocsMCPSettings(max_tokens=100)
    assert settings.max_tokens == 100

    settings = DocsMCPSettings(max_tokens=2000)
    assert settings.max_tokens == 2000

    # Invalid values should raise ValidationError
    with pytest.raises(ValidationError):
        DocsMCPSettings(max_tokens=99)

    with pytest.raises(ValidationError):
        DocsMCPSettings(max_tokens=2001)


def test_docs_mcp_settings_include_attributes() -> None:
    """Test that include_attributes can be configured."""
    from docs_mcp_server._settings import DocsMCPSettings

    settings = DocsMCPSettings(include_attributes=["title", "link", "metadata"])
    assert settings.include_attributes == ["title", "link", "metadata"]

    # Empty list is valid
    settings = DocsMCPSettings(include_attributes=[])
    assert settings.include_attributes == []


def test_turbopuffer_settings_defaults() -> None:
    """Test TurboPufferSettings defaults."""
    from docs_mcp_server._settings import TurboPufferSettings

    settings = TurboPufferSettings()
    assert settings.namespace == "docs-v1"


def test_turbopuffer_settings_custom_namespace() -> None:
    """Test TurboPufferSettings with custom namespace."""
    from docs_mcp_server._settings import TurboPufferSettings

    settings = TurboPufferSettings(namespace="custom-namespace")
    assert settings.namespace == "custom-namespace"


def test_logfire_settings_defaults() -> None:
    """Test LogfireSettings defaults."""
    from docs_mcp_server._settings import LogfireSettings

    settings = LogfireSettings()
    assert settings.token is None
    assert settings.environment == "local"
    assert settings.send_to_logfire == "if-token-present"
    assert settings.console is False


def test_logfire_settings_with_token() -> None:
    """Test LogfireSettings with token."""
    from docs_mcp_server._settings import LogfireSettings
    from pydantic import SecretStr

    settings = LogfireSettings(token=SecretStr("test-token"))
    assert isinstance(settings.token, SecretStr)
    assert settings.token.get_secret_value() == "test-token"


def test_logfire_settings_environment() -> None:
    """Test LogfireSettings environment configuration."""
    from docs_mcp_server._settings import LogfireSettings

    settings = LogfireSettings(environment="production")
    assert settings.environment == "production"

    settings = LogfireSettings(environment="staging")
    assert settings.environment == "staging"


def test_logfire_settings_send_to_logfire() -> None:
    """Test LogfireSettings send_to_logfire configuration."""
    from docs_mcp_server._settings import LogfireSettings

    settings = LogfireSettings(send_to_logfire=True)
    assert settings.send_to_logfire is True

    settings = LogfireSettings(send_to_logfire=False)
    assert settings.send_to_logfire is False

    settings = LogfireSettings(send_to_logfire="if-token-present")
    assert settings.send_to_logfire == "if-token-present"


def test_logfire_settings_console() -> None:
    """Test LogfireSettings console configuration."""
    from docs_mcp_server._settings import LogfireSettings

    settings = LogfireSettings(console=False)
    assert settings.console is False

    settings = LogfireSettings(console=None)
    assert settings.console is None


def test_settings_env_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that environment variables with PREFECT_DOCS_MCP_ prefix are read."""
    from docs_mcp_server._settings import DocsMCPSettings

    monkeypatch.setenv("PREFECT_DOCS_MCP_TOP_K", "10")
    monkeypatch.setenv("PREFECT_DOCS_MCP_MAX_TOKENS", "1500")

    settings = DocsMCPSettings()
    assert settings.top_k == 10
    assert settings.max_tokens == 1500


def test_logfire_settings_env_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that environment variables with LOGFIRE_ prefix are read."""
    from docs_mcp_server._settings import LogfireSettings

    monkeypatch.setenv("LOGFIRE_TOKEN", "secret-token")
    monkeypatch.setenv("LOGFIRE_ENVIRONMENT", "production")

    settings = LogfireSettings()
    assert settings.token is not None
    assert settings.token.get_secret_value() == "secret-token"
    assert settings.environment == "production"


def test_nested_settings_configuration() -> None:
    """Test that nested settings can be configured."""
    from docs_mcp_server._settings import (
        DocsMCPSettings,
        LogfireSettings,
        TurboPufferSettings,
    )

    settings = DocsMCPSettings(
        top_k=10,
        logfire=LogfireSettings(environment="production", send_to_logfire=True),
        turbopuffer=TurboPufferSettings(namespace="custom-namespace"),
    )

    assert settings.top_k == 10
    assert settings.logfire.environment == "production"
    assert settings.logfire.send_to_logfire is True
    assert settings.turbopuffer.namespace == "custom-namespace"


def test_global_settings_instance() -> None:
    """Test that the global settings instance exists."""
    from docs_mcp_server._settings import settings

    assert settings is not None
    assert settings.top_k >= 1
    assert settings.top_k <= 20
    assert settings.turbopuffer is not None
    assert settings.logfire is not None
