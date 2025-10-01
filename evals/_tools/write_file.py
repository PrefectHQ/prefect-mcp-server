from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import RunContext


class WriteFileArgs(BaseModel):
    file_path: str = Field(description="Path to the file to write")
    content: str = Field(description="Content to write to the file")
    encoding: str = Field(default="utf-8", description="File encoding")
    create_dirs: bool = Field(
        default=False, description="Create parent directories if they don't exist"
    )
    overwrite: bool = Field(
        default=True, description="Whether to overwrite existing files"
    )


class WriteFileResult(BaseModel):
    success: bool = Field(description="Whether the file was successfully written")
    message: str = Field(description="Success message or error description")
    file_path: str = Field(description="The resolved file path that was written to")


async def write_file(_ctx: RunContext[Any], args: WriteFileArgs) -> WriteFileResult:
    """Write content to a file on the filesystem. Returns success status and message."""
    try:
        file_path = Path(args.file_path).resolve()

        # Security check - ensure we're not writing outside the current working directory
        cwd = Path.cwd().resolve()
        if not str(file_path).startswith(str(cwd)):
            return WriteFileResult(
                success=False,
                message=f"Access denied: file path '{file_path}' is outside the working directory",
                file_path=str(file_path),
            )

        # Check if file exists and overwrite is False
        if file_path.exists() and not args.overwrite:
            return WriteFileResult(
                success=False,
                message=f"File already exists and overwrite is disabled: {file_path}",
                file_path=str(file_path),
            )

        # Create parent directories if requested
        if args.create_dirs:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        elif not file_path.parent.exists():
            return WriteFileResult(
                success=False,
                message=f"Parent directory does not exist: {file_path.parent}",
                file_path=str(file_path),
            )

        # Write the file
        with open(file_path, "w", encoding=args.encoding) as f:
            f.write(args.content)

        return WriteFileResult(
            success=True,
            message=f"Successfully wrote {len(args.content)} characters to file",
            file_path=str(file_path),
        )

    except PermissionError:
        return WriteFileResult(
            success=False,
            message=f"Permission denied writing to file: {args.file_path}",
            file_path=args.file_path,
        )
    except UnicodeEncodeError as e:
        return WriteFileResult(
            success=False,
            message=f"Encoding error writing file with {args.encoding}: {e}",
            file_path=args.file_path,
        )
    except Exception as e:
        return WriteFileResult(
            success=False,
            message=f"Unexpected error writing file: {e}",
            file_path=args.file_path,
        )
