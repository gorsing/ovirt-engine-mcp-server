#!/usr/bin/env python3
"""Tests for config module."""
import pytest
import os
import tempfile
from unittest.mock import patch


class TestConfigDataclass:
    """Tests for the Config dataclass."""

    def test_config_defaults(self):
        """Test default configuration values."""
        from ovirt_engine_mcp_server.config import Config

        config = Config()

        assert config.ovirt_engine_url == ""
        assert config.ovirt_engine_user == ""
        assert config.ovirt_engine_password == ""
        assert config.ovirt_engine_ca_file == ""
        assert config.ovirt_engine_timeout == 30
        assert config.ovirt_engine_insecure is False
        assert config.mcp_log_level == "INFO"

    def test_config_with_values(self):
        """Test configuration with values."""
        from ovirt_engine_mcp_server.config import Config

        config = Config(
            ovirt_engine_url="https://ovirt.example.com",
            ovirt_engine_user="admin@internal",
            ovirt_engine_password="secret",
            ovirt_engine_timeout=60,
            ovirt_engine_insecure=True,
            mcp_log_level="DEBUG",
        )

        assert config.ovirt_engine_url == "https://ovirt.example.com"
        assert config.ovirt_engine_user == "admin@internal"
        assert config.ovirt_engine_password == "secret"
        assert config.ovirt_engine_timeout == 60
        assert config.ovirt_engine_insecure is True
        assert config.mcp_log_level == "DEBUG"


class TestLoadConfig:
    """Tests for the load_config function."""

    def test_load_config_from_env(self):
        """Test loading configuration from environment variables."""
        from ovirt_engine_mcp_server.config import load_config, Config

        env_vars = {
            "OVIRT_ENGINE_URL": "https://ovirt.env.test",
            "OVIRT_ENGINE_USER": "env_user",
            "OVIRT_ENGINE_PASSWORD": "env_pass",
            "OVIRT_ENGINE_TIMEOUT": "45",
            "OVIRT_ENGINE_INSECURE": "true",
            "MCP_LOG_LEVEL": "WARNING",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            # Nonexistent config path; load environment variables only
            config = load_config("/nonexistent/config.yaml")

        assert config.ovirt_engine_url == "https://ovirt.env.test"
        assert config.ovirt_engine_user == "env_user"
        assert config.ovirt_engine_password == "env_pass"
        assert config.ovirt_engine_timeout == 45
        assert config.ovirt_engine_insecure is True
        assert config.mcp_log_level == "WARNING"

    def test_load_config_from_yaml(self):
        """Test loading configuration from a YAML file."""
        from ovirt_engine_mcp_server.config import load_config

        yaml_content = """
ovirt_engine_url: https://ovirt.yaml.test
ovirt_engine_user: yaml_user
ovirt_engine_password: yaml_pass
ovirt_engine_timeout: 50
mcp_log_level: ERROR
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config = load_config(f.name)

        assert config.ovirt_engine_url == "https://ovirt.yaml.test"
        assert config.ovirt_engine_user == "yaml_user"
        assert config.ovirt_engine_password == "yaml_pass"
        assert config.ovirt_engine_timeout == 50
        assert config.mcp_log_level == "ERROR"

    def test_load_config_env_overrides_yaml(self):
        """Test environment variables overriding YAML configuration."""
        from ovirt_engine_mcp_server.config import load_config

        yaml_content = """
ovirt_engine_url: https://ovirt.yaml.test
ovirt_engine_user: yaml_user
ovirt_engine_timeout: 50
"""

        env_vars = {
            "OVIRT_ENGINE_USER": "env_override_user",
            "OVIRT_ENGINE_TIMEOUT": "99",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            with patch.dict(os.environ, env_vars, clear=False):
                config = load_config(f.name)

        # Environment overrides
        assert config.ovirt_engine_user == "env_override_user"
        assert config.ovirt_engine_timeout == 99
        # YAML values retained
        assert config.ovirt_engine_url == "https://ovirt.yaml.test"

    def test_load_config_missing_file(self):
        """Test defaults when the config file does not exist."""
        from ovirt_engine_mcp_server.config import load_config

        # Clear environment variables
        env_vars = {k: "" for k in [
            "OVIRT_ENGINE_URL", "OVIRT_ENGINE_USER", "OVIRT_ENGINE_PASSWORD",
            "OVIRT_ENGINE_CA_FILE", "OVIRT_ENGINE_TIMEOUT", "OVIRT_ENGINE_INSECURE",
            "MCP_LOG_LEVEL"
        ]}

        with patch.dict(os.environ, env_vars, clear=True):
            config = load_config("/nonexistent/config.yaml")

        # Use default values
        assert config.ovirt_engine_url == ""
        assert config.ovirt_engine_timeout == 30

    def test_load_config_invalid_yaml(self):
        """Test an invalid YAML file."""
        from ovirt_engine_mcp_server.config import load_config

        invalid_yaml = """
this is not: valid yaml: : :
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(invalid_yaml)
            f.flush()
            # Should not raise an exception; defaults are used
            config = load_config(f.name)

        assert config is not None


class TestConvertValue:
    """Tests for the _convert_value function."""

    def test_convert_bool_from_string_true(self):
        """Test converting a string to boolean True."""
        from ovirt_engine_mcp_server.config import _convert_value

        assert _convert_value("true", bool) is True
        assert _convert_value("True", bool) is True
        assert _convert_value("TRUE", bool) is True
        assert _convert_value("1", bool) is True
        assert _convert_value("yes", bool) is True
        assert _convert_value("on", bool) is True

    def test_convert_bool_from_string_false(self):
        """Test converting a string to boolean False."""
        from ovirt_engine_mcp_server.config import _convert_value

        assert _convert_value("false", bool) is False
        assert _convert_value("False", bool) is False
        assert _convert_value("0", bool) is False
        assert _convert_value("no", bool) is False

    def test_convert_bool_from_bool(self):
        """Test that booleans stay unchanged."""
        from ovirt_engine_mcp_server.config import _convert_value

        assert _convert_value(True, bool) is True
        assert _convert_value(False, bool) is False

    def test_convert_int_from_string(self):
        """Test converting a string to an integer."""
        from ovirt_engine_mcp_server.config import _convert_value

        assert _convert_value("42", int) == 42
        assert _convert_value("0", int) == 0
        assert _convert_value("-10", int) == -10

    def test_convert_string(self):
        """Test that strings stay unchanged."""
        from ovirt_engine_mcp_server.config import _convert_value

        assert _convert_value("hello", str) == "hello"
        assert _convert_value(123, str) == "123"

    def test_convert_none(self):
        """Test None values."""
        from ovirt_engine_mcp_server.config import _convert_value

        assert _convert_value(None, str) is None
        assert _convert_value(None, int) is None
        assert _convert_value(None, bool) is None


class TestSanitizeLogMessage:
    """Tests for the sanitize_log_message function."""

    def test_sanitize_password(self):
        """Test masking a password."""
        from ovirt_engine_mcp_server.config import sanitize_log_message

        msg = "Connection with password=secret123 failed"
        result = sanitize_log_message(msg)

        assert "secret123" not in result
        assert "***" in result

    def test_sanitize_password_colon(self):
        """Test masking a password (colon format)."""
        from ovirt_engine_mcp_server.config import sanitize_log_message

        msg = "Error: password: mypassword"
        result = sanitize_log_message(msg)

        assert "mypassword" not in result

    def test_sanitize_api_key(self):
        """Test masking an API key."""
        from ovirt_engine_mcp_server.config import sanitize_log_message

        msg = "Using api_key=abc123xyz"
        result = sanitize_log_message(msg)

        assert "abc123xyz" not in result
        assert "***" in result

    def test_sanitize_token(self):
        """Test masking a token."""
        from ovirt_engine_mcp_server.config import sanitize_log_message

        msg = "Auth token=bearer_token_here"
        result = sanitize_log_message(msg)

        assert "bearer_token_here" not in result

    def test_sanitize_secret(self):
        """Test masking a secret."""
        from ovirt_engine_mcp_server.config import sanitize_log_message

        msg = "secret=my_secret_value"
        result = sanitize_log_message(msg)

        assert "my_secret_value" not in result

    def test_no_sensitive_data(self):
        """Test a message without sensitive data."""
        from ovirt_engine_mcp_server.config import sanitize_log_message

        msg = "Connected to server successfully"
        result = sanitize_log_message(msg)

        assert result == msg

    def test_case_insensitive(self):
        """Test case-insensitive masking."""
        from ovirt_engine_mcp_server.config import sanitize_log_message

        msg = "PASSWORD=Secret123 and Api_Key=xyz"
        result = sanitize_log_message(msg)

        assert "Secret123" not in result
        assert "xyz" not in result


class TestSensitiveFields:
    """Tests for sensitive field definitions."""

    def test_sensitive_fields_defined(self):
        """Test that the sensitive fields list is defined."""
        from ovirt_engine_mcp_server.config import SENSITIVE_FIELDS

        assert "ovirt_engine_password" in SENSITIVE_FIELDS
