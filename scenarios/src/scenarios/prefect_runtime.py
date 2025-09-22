"""Utilities for orchestrating ephemeral Prefect servers used in scenario tests."""

import contextlib
import dataclasses
import http.client
import time
import urllib.error
import urllib.request
from collections.abc import Iterator

import docker
from docker.errors import DockerException, ImageNotFound

DEFAULT_IMAGE = "prefecthq/prefect:3-latest"
API_PORT = "4200/tcp"
API_ROUTE = "/hello"
HEALTH_TIMEOUT = 120.0
POLL_INTERVAL = 1.0


@dataclasses.dataclass(slots=True)
class PrefectServerHandle:
    """Handle for a running Prefect server container."""

    client: docker.DockerClient
    container: docker.models.containers.Container
    api_url: str

    def stop(self, *, timeout: int = 10) -> None:
        """Stop and remove the underlying container."""
        with contextlib.suppress(DockerException):
            self.container.stop(timeout=timeout)
        with contextlib.suppress(DockerException):
            self.container.remove()

    def __enter__(self) -> "PrefectServerHandle":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.stop()


def start_prefect_server(
    *,
    image: str = DEFAULT_IMAGE,
    command: tuple[str, ...] | None = None,
    env: dict[str, str] | None = None,
    pull: bool = False,
) -> PrefectServerHandle:
    """Launch a Prefect server container and wait until the API responds.

    Parameters
    ----------
    image:
        Prefect image to run. Defaults to the latest Prefect 3 image.
    command:
        Optional override for the container command. If omitted, the Prefect
        server start command is used.
    env:
        Environment variables to pass into the container.
    pull:
        If true, pull the specified image before starting.
    """

    try:
        client = docker.from_env()
        client.ping()
    except DockerException as exc:
        raise RuntimeError("Docker daemon is unavailable") from exc

    if pull:
        client.images.pull(image)

    resolved_command = command or (
        "prefect",
        "server",
        "start",
        "--host",
        "0.0.0.0",
    )

    ports = {API_PORT: ("127.0.0.1", 0)}

    try:
        container = client.containers.run(
            image=image,
            command=resolved_command,
            detach=True,
            environment=env,
            ports=ports,
        )
    except ImageNotFound:
        client.images.pull(image)
        container = client.containers.run(
            image=image,
            command=resolved_command,
            detach=True,
            environment=env,
            ports=ports,
        )

    try:
        host_port = _wait_for_network_binding(container)
        api_url = f"http://127.0.0.1:{host_port}/api"
        _wait_for_hello(api_url)
        return PrefectServerHandle(client=client, container=container, api_url=api_url)
    except Exception:
        with contextlib.suppress(DockerException):
            container.stop(timeout=5)
        with contextlib.suppress(DockerException):
            container.remove()
        raise


def _wait_for_network_binding(
    container: docker.models.containers.Container,
) -> int:
    deadline = time.time() + HEALTH_TIMEOUT
    while time.time() < deadline:
        container.reload()
        ports = container.attrs.get("NetworkSettings", {}).get("Ports", {})
        host_info = ports.get(API_PORT)
        if host_info:
            try:
                return int(host_info[0]["HostPort"])
            except (KeyError, ValueError, IndexError, TypeError):
                pass
        if container.status in {"exited", "dead"}:
            logs = container.logs(tail=50).decode(errors="ignore")
            raise RuntimeError(
                "Prefect server container exited before binding port. Logs:\n" + logs
            )
        time.sleep(POLL_INTERVAL)
    raise TimeoutError("Timed out waiting for Prefect server port binding")


def _wait_for_hello(api_url: str) -> None:
    url = api_url + API_ROUTE
    deadline = time.time() + HEALTH_TIMEOUT
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    response.read(1)
                    return
        except (
            urllib.error.URLError,
            TimeoutError,
            ConnectionError,
            http.client.RemoteDisconnected,
        ):
            time.sleep(POLL_INTERVAL)
            continue
    raise TimeoutError(f"Timed out waiting for Prefect server response at {url}")


@contextlib.contextmanager
def prefect_server(
    *,
    image: str = DEFAULT_IMAGE,
    command: tuple[str, ...] | None = None,
    env: dict[str, str] | None = None,
    pull: bool = False,
) -> Iterator[PrefectServerHandle]:
    """Context manager wrapper around :func:`start_prefect_server`."""

    handle = start_prefect_server(image=image, command=command, env=env, pull=pull)
    try:
        yield handle
    finally:
        handle.stop()
