import os
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from docker.errors import DockerException

from scenarios import PrefectServerHandle, prefect_server


@contextmanager
def _temporary_env(**values: str) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for key, old in previous.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old


@pytest.fixture(scope="session")
def prefect_server_handle() -> Iterator[PrefectServerHandle]:
    try:
        with prefect_server() as handle:
            yield handle
    except (RuntimeError, DockerException) as exc:
        pytest.skip(f"Prefect server unavailable: {exc}")


@pytest.fixture(scope="session", autouse=True)
def prefect_api_environment(
    prefect_server_handle: PrefectServerHandle,
) -> Iterator[None]:
    with _temporary_env(
        PREFECT_API_URL=prefect_server_handle.api_url,
        PREFECT_API_KEY="",
    ):
        yield


@pytest.fixture(scope="session")
def prefect_api_url(prefect_server_handle: PrefectServerHandle) -> str:
    return prefect_server_handle.api_url
