"""sysops-mcp — filesystem and shell command operations."""
from __future__ import annotations

from tools._logging import get_logger

log = get_logger()
log.info("=" * 60)
log.info("sysops-mcp server starting")

from mcp.server.fastmcp import FastMCP

from tools import complex_files
from tools import exec as exec_tools
from tools import fs

mcp = FastMCP("sysops-mcp")


@mcp.tool()
def read_file(
    path: str,
    encoding: str = "utf-8",
    max_bytes: int = 500_000,
    offset: int = 0,
) -> dict:
    """Read a file's contents. Returns text for text files; base64 for binaries
    (NUL-byte sniffed). Truncates at max_bytes; pass offset to continue.
    """
    return fs.read_file(path, encoding, max_bytes, offset)


@mcp.tool()
def write_file(
    path: str,
    content: str,
    encoding: str = "utf-8",
    create_dirs: bool = True,
    overwrite: bool = True,
    append: bool = False,
) -> dict:
    """Write text content to a file. Creates parent directories by default.
    Set append=True to append instead of overwrite.
    """
    return fs.write_file(path, content, encoding, create_dirs, overwrite, append)


@mcp.tool()
def write_complex_file(request: complex_files.ComplexFileRequest) -> dict:
    """
    Write content to a specific complex file (docx, xlsx, pptx, pdf, csv, tsv, yaml, xml).
    All files are stored in a centralized artifacts directory separated by session.
    Provide the necessary configuration inside the request based on the file_type.
    """
    return complex_files.handle_complex_file_creation(request)


@mcp.tool()
def get_complex_file_schema(file_type: str | None = None) -> dict:
    """
    Get the generation schema for complex files.
    If file_type is provided (e.g., 'docx', 'xlsx'), returns the schema for that specific type.
    If no file_type is provided, returns the schemas for all supported file types.
    """
    return complex_files.get_schema(file_type)


@mcp.tool()
def list_directory(
    path: str,
    recursive: bool = False,
    glob: str | None = None,
    include_hidden: bool = False,
    max_entries: int = 1000,
) -> dict:
    """List directory contents. Returns name, path, type, size, mtime per entry.
    Pass `glob` (e.g. '*.py') to filter, recursive=True to walk subtrees.
    """
    return fs.list_directory(path, recursive, glob, include_hidden, max_entries)


@mcp.tool()
def move_file(src: str, dst: str, overwrite: bool = False) -> dict:
    """Move or rename a file or directory."""
    return fs.move_file(src, dst, overwrite)


@mcp.tool()
def copy_file(src: str, dst: str, overwrite: bool = False) -> dict:
    """Copy a file or directory tree."""
    return fs.copy_file(src, dst, overwrite)


@mcp.tool()
def delete_path(path: str, recursive: bool = False) -> dict:
    """Delete a file, or a directory when recursive=True. Destructive — logs at WARN."""
    return fs.delete_path(path, recursive)


@mcp.tool()
def create_directory(path: str, parents: bool = True) -> dict:
    """Create a directory. parents=True creates intermediate dirs."""
    return fs.create_directory(path, parents)


@mcp.tool()
def file_info(path: str) -> dict:
    """Return metadata: exists, type, size, mtime, ctime, is_symlink, absolute path."""
    return fs.file_info(path)


@mcp.tool()
def execute_command(
    command: str,
    shell: str = "powershell",
    cwd: str | None = None,
    timeout_sec: int = 60,
    env_overrides: dict | None = None,
) -> dict:
    """Run a shell command. shell is one of 'powershell', 'pwsh', 'cmd', 'bash'.

    Captures stdout/stderr (truncated to 100KB each), exit_code, and duration.
    Hard timeout via timeout_sec (max 600s). Local trust model — every call
    is logged with command, cwd, and exit code.
    """
    return exec_tools.execute_command(command, shell, cwd, timeout_sec, env_overrides)


@mcp.tool()
def get_environment(name: str | None = None) -> dict:
    """Read process environment variables. Pass name for one var, omit for all."""
    return exec_tools.get_environment(name)


if __name__ == "__main__":
    log.info("entering FastMCP stdio loop")
    mcp.run()
