"""Absolute-path entry point for MCP clients whose working directory varies."""
from sg_library.mcp_server import mcp

if __name__ == '__main__':
    mcp.run(transport='stdio')
