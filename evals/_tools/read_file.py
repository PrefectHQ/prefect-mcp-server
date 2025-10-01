from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import RunContext


class ReadFileArgs(BaseModel):
    file_path: str = Field(description="Path to the file to read")
    encoding: str = Field(default="utf-8", description="File encoding")


class ReadFileResult(BaseModel):
    success: bool = Field(description="Whether the file was successfully read")
    content: str = Field(description="File content if successful")
    error: str = Field(default="", description="Error message if unsuccessful")


async def read_file(_ctx: RunContext[Any], args: ReadFileArgs) -> ReadFileResult:
    """Read a file from the filesystem. Returns file content or error."""
    try:
        file_path = Path(args.file_path).resolve()

        # Security check - ensure we're not reading outside the current working directory
        cwd = Path.cwd().resolve()
        if not str(file_path).startswith(str(cwd)):
            return ReadFileResult(
                success=False,
                content="",
                error=f"Access denied: file path '{file_path}' is outside the working directory",
            )

        # Check if file exists
        if not file_path.exists():
            return ReadFileResult(
                success=False, content="", error=f"File not found: {file_path}"
            )

        # Check if it's actually a file
        if not file_path.is_file():
            return ReadFileResult(
                success=False, content="", error=f"Path is not a file: {file_path}"
            )

        # Read the file
        with open(file_path, encoding=args.encoding) as f:
            content = f.read()

        return ReadFileResult(success=True, content=content, error="")

    except PermissionError:
        return ReadFileResult(
            success=False,
            content="",
            error=f"Permission denied reading file: {args.file_path}",
        )
    except UnicodeDecodeError as e:
        return ReadFileResult(
            success=False,
            content="",
            error=f"Encoding error reading file with {args.encoding}: {e}",
        )
    except Exception as e:
        return ReadFileResult(
            success=False, content="", error=f"Unexpected error reading file: {e}"
        )
