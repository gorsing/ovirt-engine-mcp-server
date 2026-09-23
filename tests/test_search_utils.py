#!/usr/bin/env python3
"""Tests for search_utils module - search utils tests."""
import pytest


class TestSanitizeSearchValue:
    """Tests for the sanitize_search_value function"""

    def test_empty_string(self):
        """Test empty string"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        assert sanitize_search_value("") == ""
        assert sanitize_search_value(None) is None

    def test_simple_string(self):
        """Test simple string (no special characters)"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        result = sanitize_search_value("simple_name")
        assert result == "simple_name"

    def test_string_with_spaces(self):
        """Test string with spaces"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        result = sanitize_search_value("my vm name")
        assert result == '"my vm name"'

    def test_string_with_semicolon(self):
        """Test string with semicolon (injection attempt)"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        # Semicolon is used to terminate search conditions
        result = sanitize_search_value("vm; delete all")
        assert result == '"vm; delete all"'

    def test_string_with_ampersand(self):
        """Test string with & (injection attempt)"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        result = sanitize_search_value("vm & host")
        assert result == '"vm & host"'

    def test_string_with_pipe(self):
        """Test string with | (injection attempt)"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        result = sanitize_search_value("vm | command")
        assert result == '"vm | command"'

    def test_string_with_parentheses(self):
        """Test string with parentheses"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        result = sanitize_search_value("(nested)")
        assert result == '"(nested)"'

    def test_string_with_quotes(self):
        """Test string with quotes"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        # Quotes need escaping
        result = sanitize_search_value('my"vm')
        assert '"' in result
        assert '\\"' in result

    def test_string_with_backslash(self):
        """Test string with backslash"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        result = sanitize_search_value("path\\to\\vm")
        assert "\\\\" in result

    def test_string_with_equals(self):
        """Test string with equals sign"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        result = sanitize_search_value("name=value")
        assert result == '"name=value"'

    def test_string_with_less_than(self):
        """Test string with <"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        result = sanitize_search_value("a < b")
        assert result == '"a < b"'

    def test_string_with_greater_than(self):
        """Test string with >"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        result = sanitize_search_value("a > b")
        assert result == '"a > b"'

    def test_string_with_exclamation(self):
        """Test string with !"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        result = sanitize_search_value("vm!test")
        assert result == '"vm!test"'

    def test_complex_injection_attempt(self):
        """Test a complex injection attempt"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        # Simulate a SQL-injection-style attack
        malicious = "vm'; DROP TABLE vms; --"
        result = sanitize_search_value(malicious)

        # Should be wrapped in quotes
        assert result.startswith('"')
        assert result.endswith('"')

    def test_unicode_characters(self):
        """Test Unicode characters"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        # Non-ASCII characters (written as \u escapes so this file stays ASCII)
        result = sanitize_search_value("caf\u00e9")
        assert result == "caf\u00e9"

    def test_numeric_string(self):
        """Test numeric string"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        result = sanitize_search_value("12345")
        assert result == "12345"

    def test_uuid_format(self):
        """Test UUID format"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        uuid = "12345678-1234-1234-1234-123456789012"
        result = sanitize_search_value(uuid)
        assert result == uuid

    def test_dashes_only(self):
        """Test string with only dashes"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        result = sanitize_search_value("my-vm-name")
        assert result == "my-vm-name"

    def test_underscores_only(self):
        """Test string with only underscores"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        result = sanitize_search_value("my_vm_name")
        assert result == "my_vm_name"

    def test_dots_only(self):
        """Test string with only dots"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        result = sanitize_search_value("vm.name.test")
        assert result == "vm.name.test"

    def test_already_quoted(self):
        """Test already quoted string"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        result = sanitize_search_value('"already quoted"')
        # Inner quotes should be escaped
        assert '\\"' in result

    def test_injection_with_quotes_and_special_chars(self):
        """Test injection with quotes and special characters"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        malicious = 'vm" & "injection'
        result = sanitize_search_value(malicious)
        # Should be escaped and wrapped correctly
        assert '\\"' in result


class TestSanitizeSearchValueEdgeCases:
    """Tests for edge cases"""

    def test_very_long_string(self):
        """Test very long string"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        long_string = "a" * 10000
        result = sanitize_search_value(long_string)
        assert len(result) >= len(long_string)

    def test_only_special_chars(self):
        """Test only special characters"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        result = sanitize_search_value("; & | ( )")
        assert result == '"; & | ( )"'

    def test_whitespace_only(self):
        """Test only whitespace characters"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        result = sanitize_search_value("   ")
        assert result == '"   "'

    def test_newline_in_string(self):
        """Test string with newline"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        result = sanitize_search_value("vm\nname")
        # Newline is not in the special-character list; returned as-is
        assert result == "vm\nname"

    def test_tab_in_string(self):
        """Test string with tab"""
        from ovirt_engine_mcp_server.search_utils import sanitize_search_value

        result = sanitize_search_value("vm\tname")
        # Tab is not in the special-character list; returned as-is
        assert result == "vm\tname"
