"""Tests for MCP server tool registration."""
import pytest
from unittest.mock import MagicMock, patch

from ovirt_engine_mcp_server.config import Config


@pytest.fixture
def mock_config():
    return Config(
        ovirt_engine_url="https://ovirt.test",
        ovirt_engine_user="admin@internal",
        ovirt_engine_password="test",
    )


# 检查 mcp 模块是否可用
try:
    import mcp
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


@pytest.mark.skipif(not MCP_AVAILABLE, reason="mcp module not installed")
@patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
class TestOvirtMCPServer:
    """Tests for the MCP server."""

    def test_tool_registration(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.server import OvirtMCPServer

        mock_conn = MagicMock()
        mock_conn.test.return_value = True
        mock_conn_class.return_value = mock_conn

        server = OvirtMCPServer(mock_config)
        # Should have registered all tools from MCP_TOOLS
        assert len(server.tool_handlers) > 20

    def test_core_tools_present(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.server import OvirtMCPServer

        mock_conn = MagicMock()
        mock_conn.test.return_value = True
        mock_conn_class.return_value = mock_conn

        server = OvirtMCPServer(mock_config)

        core_tools = [
            "vm_list", "vm_create", "vm_start", "vm_stop", "vm_delete",
            "host_list", "cluster_list", "network_list", "storage_list",
            "template_list", "snapshot_list", "disk_list",
        ]
        for tool in core_tools:
            assert tool in server.tool_handlers, f"Missing tool: {tool}"

    def test_all_tools_have_descriptions(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.server import OvirtMCPServer

        mock_conn = MagicMock()
        mock_conn.test.return_value = True
        mock_conn_class.return_value = mock_conn

        server = OvirtMCPServer(mock_config)

        for tool_name in server.tool_handlers:
            assert tool_name in server.tool_descriptions, \
                f"Tool {tool_name} missing description"

    def test_all_tools_have_schemas(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.server import OvirtMCPServer, TOOL_SCHEMAS, DEFAULT_SCHEMA

        mock_conn = MagicMock()
        mock_conn.test.return_value = True
        mock_conn_class.return_value = mock_conn

        server = OvirtMCPServer(mock_config)

        for tool_name in server.tool_descriptions:
            schema = TOOL_SCHEMAS.get(tool_name, DEFAULT_SCHEMA)
            assert schema["type"] == "object"
            assert "properties" in schema

    def test_format_result_none(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.server import OvirtMCPServer

        result = OvirtMCPServer._format_result(None)
        assert "成功" in result

    def test_format_result_string(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.server import OvirtMCPServer

        result = OvirtMCPServer._format_result("hello")
        assert result == "hello"

    def test_format_result_dict_success(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.server import OvirtMCPServer

        result = OvirtMCPServer._format_result({"success": True, "message": "done"})
        assert "done" in result

    def test_format_result_dict_error(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.server import OvirtMCPServer

        result = OvirtMCPServer._format_result({"error": "not found"})
        assert "not found" in result

    def test_format_result_empty_list(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.server import OvirtMCPServer

        result = OvirtMCPServer._format_result([])
        assert "没有找到匹配的结果" in result
        assert "成功" not in result


class TestToolRegistryConsistency:
    """Every declared tool must resolve a handler and an explicit schema."""

    @staticmethod
    def _server(mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.server import OvirtMCPServer

        mock_conn = MagicMock()
        mock_conn.test.return_value = True
        mock_conn_class.return_value = mock_conn
        return OvirtMCPServer(mock_config)

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_every_tool_resolves_a_handler(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.server import MCP_TOOLS

        server = self._server(mock_conn_class, mock_config)
        unresolved = sorted(set(MCP_TOOLS) - set(server.tool_handlers))
        assert unresolved == [], f"tools without a handler: {unresolved}"

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_every_tool_has_an_explicit_schema(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.server import TOOL_SCHEMAS

        server = self._server(mock_conn_class, mock_config)
        missing = sorted(n for n in server.tool_handlers if n not in TOOL_SCHEMAS)
        assert missing == [], f"tools without a schema: {missing}"

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_schema_required_args_match_handler(self, mock_conn_class, mock_config):
        import inspect

        from ovirt_engine_mcp_server.server import TOOL_SCHEMAS

        server = self._server(mock_conn_class, mock_config)
        gaps = []
        for tool, fn in server.tool_handlers.items():
            required = set(TOOL_SCHEMAS.get(tool, {}).get("required", []))
            for param in inspect.signature(fn).parameters.values():
                if param.default is inspect.Parameter.empty and param.name not in required:
                    gaps.append(f"{tool}.{param.name}")
        assert gaps == [], f"required args not declared: {gaps}"

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_schema_properties_exist_in_handler(self, mock_conn_class, mock_config):
        import inspect

        from ovirt_engine_mcp_server.server import TOOL_SCHEMAS

        server = self._server(mock_conn_class, mock_config)
        strays = []
        for tool in server.tool_handlers:
            signature = inspect.signature(server.tool_handlers[tool])
            for prop in TOOL_SCHEMAS.get(tool, {}).get("properties", {}):
                if prop not in signature.parameters:
                    strays.append(f"{tool}.{prop}")
        assert strays == [], f"schema params the handler would reject: {strays}"

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_vm_rename_registered(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.server import MCP_TOOLS, TOOL_SCHEMAS

        server = self._server(mock_conn_class, mock_config)
        assert "vm_rename" in MCP_TOOLS
        assert "vm_rename" in server.tool_handlers
        assert TOOL_SCHEMAS["vm_rename"]["required"] == ["name_or_id", "new_name"]

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_vm_rename_validated(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.errors import ValidationError
        from ovirt_engine_mcp_server.validation import validate_tool_args

        cleaned = validate_tool_args(
            "vm_rename", {"name_or_id": " test-vm ", "new_name": " new-vm "}
        )
        assert cleaned == {"name_or_id": "test-vm", "new_name": "new-vm"}

        with pytest.raises(ValidationError):
            validate_tool_args("vm_rename", {"name_or_id": "test-vm", "new_name": "  "})
