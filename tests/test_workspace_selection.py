"""Tests for multi-workspace selection functionality."""

import os

import pytest

from prefect_mcp_server.settings import WorkspaceSettings


def test_workspace_auto_discovery(monkeypatch):
    """Test workspace discovery from environment patterns."""
    monkeypatch.setenv("PREFECT_WORKSPACE_PROD_API_URL", "https://api.test/prod")
    monkeypatch.setenv("PREFECT_WORKSPACE_PROD_API_KEY", "key_prod")
    monkeypatch.setenv("PREFECT_WORKSPACE_DEV_API_URL", "https://api.test/dev")
    monkeypatch.setenv("PREFECT_WORKSPACE_DEV_API_KEY", "key_dev")

    settings = WorkspaceSettings()
    workspaces = settings.discover_workspaces()

    assert "prod" in workspaces
    assert "dev" in workspaces
    assert len(workspaces) == 2


def test_workspace_discovery_case_insensitive(monkeypatch):
    """Test workspace names are normalized to lowercase."""
    monkeypatch.setenv("PREFECT_WORKSPACE_STAGING_API_URL", "https://api.test")
    monkeypatch.setenv("PREFECT_WORKSPACE_STAGING_API_KEY", "key123")

    settings = WorkspaceSettings()
    workspaces = settings.discover_workspaces()

    assert "staging" in workspaces
    assert "STAGING" not in workspaces


def test_get_workspace_credentials(monkeypatch):
    """Test credential retrieval for named workspace."""
    monkeypatch.setenv("PREFECT_WORKSPACE_STAGING_API_URL", "https://api.test")
    monkeypatch.setenv("PREFECT_WORKSPACE_STAGING_API_KEY", "key123")

    settings = WorkspaceSettings()
    creds = settings.get_workspace_credentials("staging")

    assert creds["api_url"] == "https://api.test"
    assert creds["api_key"] == "key123"


def test_get_workspace_credentials_case_insensitive(monkeypatch):
    """Test credential retrieval works with different case."""
    monkeypatch.setenv("PREFECT_WORKSPACE_PROD_API_URL", "https://api.test")
    monkeypatch.setenv("PREFECT_WORKSPACE_PROD_API_KEY", "key123")

    settings = WorkspaceSettings()

    # Should work with lowercase
    creds = settings.get_workspace_credentials("prod")
    assert creds["api_url"] == "https://api.test"

    # Should work with uppercase
    creds = settings.get_workspace_credentials("PROD")
    assert creds["api_url"] == "https://api.test"


def test_get_workspace_credentials_missing(monkeypatch):
    """Test error when workspace credentials not configured."""
    settings = WorkspaceSettings()

    with pytest.raises(ValueError, match="Workspace 'nonexistent' not configured"):
        settings.get_workspace_credentials("nonexistent")


def test_get_workspace_credentials_incomplete(monkeypatch):
    """Test error when only API URL is configured."""
    monkeypatch.setenv("PREFECT_WORKSPACE_INCOMPLETE_API_URL", "https://api.test")

    settings = WorkspaceSettings()

    with pytest.raises(ValueError, match="Workspace 'incomplete' not configured"):
        settings.get_workspace_credentials("incomplete")


def test_list_configured_workspaces(monkeypatch):
    """Test listing only workspaces with complete credentials."""
    monkeypatch.setenv("PREFECT_WORKSPACE_COMPLETE_API_URL", "https://api.test/1")
    monkeypatch.setenv("PREFECT_WORKSPACE_COMPLETE_API_KEY", "key1")
    monkeypatch.setenv("PREFECT_WORKSPACE_INCOMPLETE_API_URL", "https://api.test/2")
    # Missing API_KEY for INCOMPLETE

    settings = WorkspaceSettings()
    configured = settings.list_configured_workspaces()

    assert "complete" in configured
    assert "incomplete" not in configured
    assert len(configured) == 1


def test_default_workspace(monkeypatch):
    """Test default workspace configuration."""
    monkeypatch.setenv("PREFECT_DEFAULT_WORKSPACE", "prod")

    settings = WorkspaceSettings()

    assert settings.default_workspace == "prod"


def test_no_workspaces_configured():
    """Test behavior when no workspaces are configured."""
    settings = WorkspaceSettings()

    workspaces = settings.discover_workspaces()
    assert workspaces == []

    configured = settings.list_configured_workspaces()
    assert configured == []
