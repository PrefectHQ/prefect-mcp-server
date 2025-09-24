import asyncio
import os
from typing import Any

from prefect.settings import get_current_settings
from pydantic import BaseModel, Field
from pydantic_ai import RunContext


class ShellArgs(BaseModel):
    cmd: str = Field(description="Base command, e.g. 'git'")
    args: list[str] = Field(default_factory=list, description="Arguments")
    cwd: str | None = Field(default=None, description="Working directory")


class ShellResult(BaseModel):
    exit_code: int = Field(description="Exit code")
    stdout: str = Field(description="Standard output")
    stderr: str = Field(description="Standard error")


async def run_shell_command(ctx: RunContext[Any], args: ShellArgs) -> ShellResult:
    """Execute an allow-listed command. Returns stdout/stderr/exit_code."""
    cmd, argv = args.cmd, args.args
    if cmd != "prefect":
        return ShellResult(
            exit_code=126, stdout="", stderr=f"Command '{cmd}' is not allowed."
        )
    # build and run
    default_cwd = os.getcwd()
    env = {
        **get_current_settings().to_environment_variables(),
        **{k: v for k, v in os.environ.items() if k in {"PATH", "HOME"}},
    }
    proc = await asyncio.create_subprocess_exec(
        cmd,
        *argv,
        cwd=args.cwd or default_cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=20)
    except asyncio.TimeoutError:
        proc.kill()
        return ShellResult(exit_code=124, stdout="", stderr="Timed out after 20s")
    return ShellResult(
        exit_code=proc.returncode or 124, stdout=out.decode(), stderr=err.decode()
    )
