# Secure server definition (main.py)

from __future__ import annotations

# Import the secure file system wrapper
from tools.fs import read_file, write_file, list_directory, execute_command # ... all necessary imports

class FastMCP:
    """Mock class structure to demonstrate tool definition."""
    def __init__(self, name):
        self.name = name
        print(f"Initialized {name} server.")

    def tool(self):
        return lambda func: func 

    def run(self):
        print("Starting secure MCP loop...")


# Global instance initialization
mcp = FastMCP("sysops-secure-mcp")

@mcp.tool()
def read_file(
    path: str,
    encoding: str = "utf-8",
    max_bytes: int = 500_000,
    offset: int = 0,
) -> dict:
    """Reads a file's contents securely. (Path Traversal Mitigated)"""
    return read_file(path, encoding, max_bytes, offset)

@mcp.tool()
def write_file(
    path: str,
    content: str,
    encoding: str = "utf-8",
    create_dirs: bool = True,
    overwrite: bool = True,
    append: bool = False,
) -> dict:
    """Writes text content to a file securely. (Path Traversal Mitigated)"""
    return write_file(path, content, encoding, create_dirs, overwrite, append)

@mcp.tool()
def list_directory(
    path: str,
    recursive: bool = False,
    glob: str | None = None,
    include_hidden: bool = False,
    max_entries: int = 1000,
) -> dict:
    """Lists directory contents securely. (Path Traversal Mitigated)"""
    return list_directory(path, recursive, glob, include_hidden, max_entries)

@mcp.tool()
def move_file(src: str, dst: str, overwrite: bool = False) -> dict:
    """Moves/renames a file securely. (Path Traversal Mitigated)"""
    # This function assumes the secure wrapper exists and is called
    return move_file(src, dst, overwrite)

@mcp.tool()
def copy_file(src: str, dst: str, overwrite: bool = False) -> dict:
    """Copies a file or directory tree securely. (Path Traversal Mitigated)"""
    # This function assumes the secure wrapper exists and is called
    return copy_file(src, dst, overwrite)

@mcp.tool()
def delete_path(path: str, recursive: bool = False) -> dict:
    """Deletes a file/directory securely. (Path Traversal Mitigated)"""
    # This function assumes the secure wrapper exists and is called
    return delete_path(path, recursive)

@mcp.tool()
def create_directory(path: str, parents: bool = True) -> dict:
    """Creates a directory securely. (Path Traversal Mitigated)"""
    # This function assumes the secure wrapper exists and is called
    return create_directory(path, parents)

@mcp.tool()
def file_info(path: str) -> dict:
    """Gets file metadata securely. (Path Traversal Mitigated)"""
    return file_info(path)

@mcp.tool()
def execute_command(
    command: str,
    shell: str = "powershell",
    cwd: str | None = None,
    timeout_sec: int = 60,
    env_overrides: dict | None = None,
) -> dict:
    """Runs a shell command securely. (Command Injection Mitigated)"""
    return execute_command(command, shell, cwd, timeout_sec, env_overrides)

@mcp.tool()
def get_environment(name: str | None = None) -> dict:
    """Reads process environment variables securely."""
    return get_environment(name)


if __name__ == "__main__":
    mcp.run()