#!/usr/bin/env python3
"""Tests for StorageExtendedMCP class - storage extension module tests.."""
from types import SimpleNamespace

import pytest
from unittest.mock import MagicMock


def _create_mock_storage_domain(sd_id="sd-123", name="storage1", sd_type="data", status="active"):
    """Create a mock StorageDomain object."""
    mock_sd = MagicMock()
    mock_sd.id = sd_id
    mock_sd.name = name
    mock_sd.description = "Test storage"
    mock_sd.type = MagicMock()
    mock_sd.type.value = sd_type
    mock_sd.status = MagicMock()
    mock_sd.status.value = status
    mock_sd.available = 107374182400  # 100GB
    mock_sd.used = 107374182400  # 100GB
    mock_sd.storage = MagicMock()
    mock_sd.storage.type = MagicMock()
    mock_sd.storage.type.value = "nfs"
    mock_sd.storage.data_center = MagicMock()
    mock_sd.storage.data_center.name = "Default"
    mock_sd.storage.data_center.id = "dc-123"
    mock_sd.master = False
    mock_sd.wipe_after_delete = False
    mock_sd.supports_discard = True
    return mock_sd


def _create_mock_datacenter(dc_id="dc-123", name="Default"):
    """Create a mock DataCenter object."""
    mock_dc = MagicMock()
    mock_dc.id = dc_id
    mock_dc.name = name
    return mock_dc


class TestStorageExtendedMCPGetStorageDomain:
    """Tests for get_storage_domain method."""

    def test_get_storage_domain_by_id(self):
        """Get storage domain by ID."""
        from ovirt_engine_mcp_server.mcp_storage_extended import StorageExtendedMCP

        mock_sd = _create_mock_storage_domain()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_sd_service = MagicMock()
        mock_sd_service.get.return_value = mock_sd
        mock_sd_service.files_service.return_value.list.return_value = []

        mock_sds_service = MagicMock()
        mock_sds_service.storage_domain_service.return_value = mock_sd_service
        mock_sds_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.storage_domains_service.return_value = mock_sds_service

        storage_mcp = StorageExtendedMCP(mock_ovirt)
        result = storage_mcp.get_storage_domain("sd-123")

        assert result is not None
        assert result["id"] == "sd-123"
        assert result["name"] == "storage1"
        assert result["type"] == "data"

    def test_get_storage_domain_not_found(self):
        """Storage domain not found."""
        from ovirt_engine_mcp_server.mcp_storage_extended import StorageExtendedMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_sds_service = MagicMock()
        mock_sds_service.storage_domain_service.return_value.get.side_effect = Exception("Not found")
        mock_sds_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.storage_domains_service.return_value = mock_sds_service

        storage_mcp = StorageExtendedMCP(mock_ovirt)
        result = storage_mcp.get_storage_domain("nonexistent")

        assert result is None

    def test_get_storage_domain_with_files(self):
        """Get storage domain with file list."""
        from ovirt_engine_mcp_server.mcp_storage_extended import StorageExtendedMCP

        mock_sd = _create_mock_storage_domain()
        mock_file = MagicMock()
        mock_file.name = "disk1.img"
        mock_file.size = 10737418240

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_sd_service = MagicMock()
        mock_sd_service.get.return_value = mock_sd
        mock_sd_service.files_service.return_value.list.return_value = [mock_file]

        mock_sds_service = MagicMock()
        mock_sds_service.storage_domain_service.return_value = mock_sd_service
        mock_sds_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.storage_domains_service.return_value = mock_sds_service

        storage_mcp = StorageExtendedMCP(mock_ovirt)
        result = storage_mcp.get_storage_domain("sd-123")

        assert result is not None
        assert len(result["files"]) == 1
        assert result["files"][0]["name"] == "disk1.img"


class TestStorageExtendedMCPCreateStorageDomain:
    """Tests for create_storage_domain method."""

    def test_create_storage_domain_success(self):
        """Create storage domain successfully."""
        from ovirt_engine_mcp_server.mcp_storage_extended import StorageExtendedMCP

        mock_sd = _create_mock_storage_domain()
        mock_host = MagicMock()
        mock_host.id = "host-123"

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_hosts_service = MagicMock()
        mock_hosts_service.list.return_value = [mock_host]

        mock_sds_service = MagicMock()
        mock_sds_service.list.return_value = []  # no name conflict
        mock_sds_service.add.return_value = mock_sd

        mock_ovirt.connection.system_service.return_value.hosts_service.return_value = mock_hosts_service
        mock_ovirt.connection.system_service.return_value.storage_domains_service.return_value = mock_sds_service

        storage_mcp = StorageExtendedMCP(mock_ovirt)
        result = storage_mcp.create_storage_domain(
            name="new-storage",
            storage_type="nfs",
            host="host1",
            path="192.168.1.100:/export/data"
        )

        assert result["success"] is True
        assert "storage_domain_id" in result

    def test_create_storage_domain_invalid_type(self):
        """Invalid storage type."""
        from ovirt_engine_mcp_server.mcp_storage_extended import StorageExtendedMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        storage_mcp = StorageExtendedMCP(mock_ovirt)

        with pytest.raises(ValueError, match="Invalid storage type"):
            storage_mcp.create_storage_domain("new-storage", "invalid", "host1", "/path")

    def test_create_storage_domain_host_not_found(self):
        """Host not found."""
        from ovirt_engine_mcp_server.mcp_storage_extended import StorageExtendedMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_hosts_service = MagicMock()
        mock_hosts_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.hosts_service.return_value = mock_hosts_service

        storage_mcp = StorageExtendedMCP(mock_ovirt)

        with pytest.raises(ValueError, match="Host not found"):
            storage_mcp.create_storage_domain("new-storage", "nfs", "nonexistent", "/path")

    def test_create_storage_domain_already_exists(self):
        """Storage domain already exists."""
        from ovirt_engine_mcp_server.mcp_storage_extended import StorageExtendedMCP

        mock_sd = _create_mock_storage_domain()
        mock_host = MagicMock()
        mock_host.id = "host-123"

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_hosts_service = MagicMock()
        mock_hosts_service.list.return_value = [mock_host]

        mock_sds_service = MagicMock()
        mock_sds_service.list.return_value = [mock_sd]  # name already exists

        mock_ovirt.connection.system_service.return_value.hosts_service.return_value = mock_hosts_service
        mock_ovirt.connection.system_service.return_value.storage_domains_service.return_value = mock_sds_service

        storage_mcp = StorageExtendedMCP(mock_ovirt)

        with pytest.raises(ValueError, match="already exists"):
            storage_mcp.create_storage_domain("storage1", "nfs", "host1", "/path")


class TestStorageExtendedMCPDeleteStorageDomain:
    """Tests for delete_storage_domain method."""

    def test_delete_storage_domain_success(self):
        """Delete storage domain successfully."""
        from ovirt_engine_mcp_server.mcp_storage_extended import StorageExtendedMCP

        mock_sd = _create_mock_storage_domain()
        mock_sd_service = MagicMock()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_sds_service = MagicMock()
        mock_sds_service.storage_domain_service.return_value.get.return_value = mock_sd
        mock_sds_service.storage_domain_service.return_value = mock_sd_service
        mock_sds_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.storage_domains_service.return_value = mock_sds_service
        mock_ovirt.connection.system_service.return_value.storage_domains_service.return_value.storage_domain_service.return_value = mock_sd_service
        mock_ovirt.connection.system_service.return_value.storage_domains_service.return_value.list.return_value = []

        storage_mcp = StorageExtendedMCP(mock_ovirt)
        result = storage_mcp.delete_storage_domain("sd-123")

        assert result["success"] is True

    def test_delete_storage_domain_not_found(self):
        """Delete a nonexistent storage domain."""
        from ovirt_engine_mcp_server.mcp_storage_extended import StorageExtendedMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_sds_service = MagicMock()
        mock_sds_service.storage_domain_service.return_value.get.side_effect = Exception("Not found")
        mock_sds_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.storage_domains_service.return_value = mock_sds_service

        storage_mcp = StorageExtendedMCP(mock_ovirt)

        with pytest.raises(ValueError, match="Storage domain not found"):
            storage_mcp.delete_storage_domain("nonexistent")


class TestStorageExtendedMCPDetachStorageDomain:
    """Tests for detach_storage_domain method."""

    def test_detach_storage_domain_success(self):
        """Detach storage domain successfully."""
        from ovirt_engine_mcp_server.mcp_storage_extended import StorageExtendedMCP

        mock_sd = _create_mock_storage_domain()
        mock_dc = _create_mock_datacenter()
        mock_sd_service = MagicMock()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        # Storage domain service
        mock_sds_service = MagicMock()
        mock_sds_service.storage_domain_service.return_value.get.return_value = mock_sd
        mock_sds_service.list.return_value = []

        # Datacenter service
        mock_dcs_service = MagicMock()
        mock_dcs_service.data_center_service.return_value.get.return_value = mock_dc
        mock_dcs_service.list.return_value = []
        mock_dcs_service.data_center_service.return_value.storage_domains_service.return_value.storage_domain_service.return_value = mock_sd_service

        mock_ovirt.connection.system_service.return_value.storage_domains_service.return_value = mock_sds_service
        mock_ovirt.connection.system_service.return_value.data_centers_service.return_value = mock_dcs_service

        storage_mcp = StorageExtendedMCP(mock_ovirt)
        result = storage_mcp.detach_storage_domain("sd-123", datacenter="Default")

        assert result["success"] is True


class TestStorageExtendedMCPAttachStorageDomain:
    """Tests for attach_storage_domain method."""

    def test_attach_storage_domain_success(self):
        """Attach storage domain successfully."""
        from ovirt_engine_mcp_server.mcp_storage_extended import StorageExtendedMCP

        mock_sd = _create_mock_storage_domain()
        mock_dc = _create_mock_datacenter()
        mock_sd_service = MagicMock()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_sds_service = MagicMock()
        mock_sds_service.storage_domain_service.return_value.get.return_value = mock_sd
        mock_sds_service.list.return_value = []

        mock_dcs_service = MagicMock()
        mock_dcs_service.data_center_service.return_value.get.return_value = mock_dc
        mock_dcs_service.list.return_value = []
        mock_dcs_service.data_center_service.return_value.storage_domains_service.return_value = mock_sd_service

        mock_ovirt.connection.system_service.return_value.storage_domains_service.return_value = mock_sds_service
        mock_ovirt.connection.system_service.return_value.data_centers_service.return_value = mock_dcs_service

        storage_mcp = StorageExtendedMCP(mock_ovirt)
        result = storage_mcp.attach_storage_domain("sd-123", "Default")

        assert result["success"] is True


class TestStorageExtendedMCPGetStats:
    """Tests for get_storage_domain_stats method."""

    def test_get_storage_domain_stats_success(self):
        """Get storage domain statistics successfully."""
        from ovirt_engine_mcp_server.mcp_storage_extended import StorageExtendedMCP

        mock_sd = _create_mock_storage_domain()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_sds_service = MagicMock()
        mock_sds_service.storage_domain_service.return_value.get.return_value = mock_sd
        mock_sds_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.storage_domains_service.return_value = mock_sds_service

        storage_mcp = StorageExtendedMCP(mock_ovirt)
        result = storage_mcp.get_storage_domain_stats("sd-123")

        assert result["id"] == "sd-123"
        assert result["name"] == "storage1"
        assert "available_gb" in result
        assert "used_gb" in result
        assert "usage_percent" in result


class TestStorageExtendedMCPTools:
    """Tests for MCP_TOOLS registry."""

    def test_mcp_tools_defined(self):
        """MCP tool registry is defined."""
        from ovirt_engine_mcp_server.mcp_storage_extended import MCP_TOOLS

        expected_tools = [
            "storage_get",
            "storage_create",
            "storage_delete",
            "storage_detach",
            "storage_attach_to_dc",
            "storage_stats",
        ]

        for tool in expected_tools:
            assert tool in MCP_TOOLS, f"Missing tool: {tool}"
            assert "method" in MCP_TOOLS[tool]
            assert "description" in MCP_TOOLS[tool]


class TestIscsiBondsDataCenterScoped:
    """iSCSI bonds live under the data center, not on SystemService."""

    @staticmethod
    def _mcp():
        from ovirt_engine_mcp_server.mcp_storage_extended import StorageExtendedMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        dcs_service = (
            mock_ovirt.connection.system_service.return_value
            .data_centers_service.return_value
        )
        dcs_service.list.return_value = [SimpleNamespace(id="dc-77", name="Default")]
        # the same accessor resolves the bond's data-center reference
        dcs_service.data_center_service.return_value.get.return_value = SimpleNamespace(
            id="dc-77", name="Default"
        )
        dcs_service.data_center_service.return_value.iscsi_bonds_service.return_value.list.return_value = [
            SimpleNamespace(
                id="bond-1",
                name="bond-a",
                description="bond desc",
                data_center=SimpleNamespace(id="dc-77", name=None),
            )
        ]
        return mock_ovirt, StorageExtendedMCP(mock_ovirt)

    def test_list_iscsi_bonds_reads_data_center_service(self):
        mock_ovirt, mcp = self._mcp()

        result = mcp.list_iscsi_bonds()

        assert result == [{
            "id": "bond-1",
            "name": "bond-a",
            "description": "bond desc",
            "data_center": "Default",
        }]
        # the system-level call that used to crash must not be attempted
        mock_ovirt.connection.system_service.return_value.iscsi_bonds_service.assert_not_called()


class TestStorageConnectionsScoping:
    """``storage_connections_list`` optionally scopes to one storage domain."""

    @staticmethod
    def _connection():
        return SimpleNamespace(
            id="conn-1",
            address="10.10.10.10",
            type=SimpleNamespace(value="nfs"),
            path="/export/data",
            port=2049,
            mount_options="soft",
            nfs_version=SimpleNamespace(value="4.1"),
        )

    @staticmethod
    def _connection_without_port():
        return SimpleNamespace(
            id="conn-2",
            address="ovih03.dcz",
            type=SimpleNamespace(value="glusterfs"),
            path="/hosted-engine",
            port=None,
            mount_options=None,
            nfs_version=None,
        )

    def test_none_values_are_not_leaked(self):
        from ovirt_engine_mcp_server.mcp_storage_extended import StorageExtendedMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        conns = (
            mock_ovirt.connection.system_service.return_value
            .storage_connections_service.return_value
        )
        conns.list.return_value = [self._connection_without_port()]

        result = StorageExtendedMCP(mock_ovirt).list_storage_connections()

        assert result[0]["port"] == ""
        assert result[0]["mount_options"] == ""
        assert result[0]["path"] == "/hosted-engine"
        assert "None" not in str(result)

    def test_list_all_connections_uses_system_collection(self):
        from ovirt_engine_mcp_server.mcp_storage_extended import StorageExtendedMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        conns = (
            mock_ovirt.connection.system_service.return_value
            .storage_connections_service.return_value
        )
        conns.list.return_value = [self._connection()]

        result = StorageExtendedMCP(mock_ovirt).list_storage_connections()

        assert result[0]["type"] == "nfs"
        assert result[0]["nfs_version"] == "4.1"
        assert result[0]["mount_options"] == "soft"

    def test_storage_domain_scope_uses_domain_service(self):
        from ovirt_engine_mcp_server.mcp_storage_extended import StorageExtendedMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        sds = (
            mock_ovirt.connection.system_service.return_value
            .storage_domains_service.return_value
        )
        # `_find_resource` probes the item service first and gets the domain
        sds.storage_domain_service.return_value.get.return_value = SimpleNamespace(
            id="sd-9", name="hosted_storage"
        )
        sd_service = sds.storage_domain_service.return_value
        sd_service.storage_connections_service.return_value.list.return_value = [
            self._connection()
        ]

        result = StorageExtendedMCP(mock_ovirt).list_storage_connections("hosted_storage")

        called_with = [c.args for c in sds.storage_domain_service.call_args_list]
        assert ("sd-9",) in called_with  # resolved domain id, not the raw string
        sd_service.storage_connections_service.assert_called_once_with()
        # the unscoped system collection must not be used in scoped mode
        (
            mock_ovirt.connection.system_service.return_value
            .storage_connections_service.return_value.list
        ).assert_not_called()
        assert result[0]["id"] == "conn-1"

    def test_unknown_storage_domain_raises(self):
        from ovirt_engine_mcp_server.mcp_storage_extended import StorageExtendedMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        sds = (
            mock_ovirt.connection.system_service.return_value
            .storage_domains_service.return_value
        )
        sds.storage_domain_service.return_value.get.side_effect = Exception("404")
        sds.list.return_value = []

        with pytest.raises(ValueError, match="Storage domain not found"):
            StorageExtendedMCP(mock_ovirt).list_storage_connections("no-such-sd")
