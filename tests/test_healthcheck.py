#!/usr/bin/env python3
"""Tests for healthcheck module - healthcheck tests."""
import pytest
from unittest.mock import MagicMock, patch
import sys


class TestCheckOvirtConnection:
    """Tests for the check_ovirt_connection function"""

    def test_missing_url(self):
        """Test missing URL config"""
        # Patch at module level
        with patch.dict(sys.modules, {'ovirtsdk4': MagicMock()}):
            from ovirt_engine_mcp_server.healthcheck import check_ovirt_connection
            from ovirt_engine_mcp_server.config import Config

            config = Config()  # empty URL

            result = check_ovirt_connection(config)

            assert result is False

    def test_missing_user(self):
        """Test missing user config"""
        with patch.dict(sys.modules, {'ovirtsdk4': MagicMock()}):
            from ovirt_engine_mcp_server.healthcheck import check_ovirt_connection
            from ovirt_engine_mcp_server.config import Config

            config = Config(
                ovirt_engine_url="https://ovirt.test",
                # Missing user
            )

            result = check_ovirt_connection(config)

            assert result is False

    def test_missing_password(self):
        """Test missing password config"""
        with patch.dict(sys.modules, {'ovirtsdk4': MagicMock()}):
            from ovirt_engine_mcp_server.healthcheck import check_ovirt_connection
            from ovirt_engine_mcp_server.config import Config

            config = Config(
                ovirt_engine_url="https://ovirt.test",
                ovirt_engine_user="admin@internal",
                # Missing password
            )

            result = check_ovirt_connection(config)

            assert result is False


class TestHealthcheckMain:
    """Tests for the main function"""

    @patch.dict(sys.modules, {'ovirtsdk4': MagicMock()})
    @patch("ovirt_engine_mcp_server.healthcheck.load_config")
    @patch("ovirt_engine_mcp_server.healthcheck.check_ovirt_connection")
    def test_main_success(self, mock_check, mock_load_config):
        """Test main function success"""
        from ovirt_engine_mcp_server.healthcheck import main
        from ovirt_engine_mcp_server.config import Config

        mock_config = Config(
            ovirt_engine_url="https://ovirt.test",
            ovirt_engine_user="admin@internal",
            ovirt_engine_password="secret",
        )
        mock_load_config.return_value = mock_config
        mock_check.return_value = True

        # main() calls sys.exit(0) on success
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0

    @patch.dict(sys.modules, {'ovirtsdk4': MagicMock()})
    @patch("ovirt_engine_mcp_server.healthcheck.load_config")
    def test_main_config_error(self, mock_load_config):
        """Test main function config error"""
        from ovirt_engine_mcp_server.healthcheck import main

        mock_load_config.side_effect = Exception("Config error")

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    @patch.dict(sys.modules, {'ovirtsdk4': MagicMock()})
    @patch("ovirt_engine_mcp_server.healthcheck.load_config")
    @patch("ovirt_engine_mcp_server.healthcheck.check_ovirt_connection")
    def test_main_connection_failed(self, mock_check, mock_load_config):
        """Test main function connection failure"""
        from ovirt_engine_mcp_server.healthcheck import main
        from ovirt_engine_mcp_server.config import Config

        mock_config = Config(
            ovirt_engine_url="https://ovirt.test",
            ovirt_engine_user="admin@internal",
            ovirt_engine_password="secret",
        )
        mock_load_config.return_value = mock_config
        mock_check.return_value = False

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1


class TestHealthcheckModuleImport:
    """Tests for module import"""

    def test_import_success(self):
        """Test successful module import"""
        with patch.dict(sys.modules, {'ovirtsdk4': MagicMock()}):
            # Should import successfully
            from ovirt_engine_mcp_server import healthcheck

            assert hasattr(healthcheck, "check_ovirt_connection")
            assert hasattr(healthcheck, "main")
