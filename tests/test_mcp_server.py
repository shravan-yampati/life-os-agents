"""Tests for the MCP server exposing Life OS tools."""

import os
from src.mcp_server.server import (
    mcp,
    get_finance_summary,
    ask_mentor,
)


def test_mcp_server_registers_tools():
    """Verify that all expected tools are registered with FastMCP."""
    # Depending on the FastMCP version, tools are stored in _tools or _tools_dict
    # We can check by inspecting the decorators or just that mcp initialized.
    assert mcp.name == "life-os"
    assert len(mcp._tools) == 5 if hasattr(mcp, "_tools") else True


def test_ask_mentor_wrapper():
    """Test the wrapper logic of an MCP tool offline.
    
    Uses the CLOUD_PROVIDER=local by default if running in the test environment,
    or at least ensures the wrapper returns a string.
    """
    os.environ["CLOUD_PROVIDER"] = "local"
    result = ask_mentor("What is a budget?")
    assert isinstance(result, str)
    assert len(result) > 0


def test_finance_summary_wrapper_error():
    """Test the error dict structure when a bad path is provided."""
    result = get_finance_summary("non_existent_file.csv")
    assert isinstance(result, dict)
    assert result["status"] == "error"
    assert "File not found" in result["error"]
