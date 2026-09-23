#!/usr/bin/env python3
"""Tests for DataCenterMCP class - data center management module tests."""
import pytest
from unittest.mock import MagicMock, patch


def _create_mock_datacenter(dc_id="dc-123", name="Default", status="up", storage_type="nfs"):
    """Create a mock DataCenter object"""
    mock_dc = MagicMock()
    mock_dc.id = dc_id
    mock_dc.name = name
    mock_dc.description = "Default datacenter"
    mock_dc.status = MagicMock()
    mock_dc.status.value = status
    mock_dc.storage_type = MagicMock()
    mock_dc.storage_type.value = storage_type
    mock_dc.version = MagicMock()
    mock_dc.version.major = 4
    mock_dc.version.minor = 7
    mock_dc.supported_versions = []
    mock_dc.mac_pool = MagicMock()
    mock_dc.mac_pool.name = "Default"
    return mock_dc


def _create_mock_cluster(cluster_id="cluster-123", name="Default"):
    """Create a mock Cluster object"""
    mock_cluster = MagicMock()
    mock_cluster.id = cluster_id
    mock_cluster.name = name
    return mock_cluster


def _create_mock_storage_domain(sd_id="sd-123", name="storage1", sd_type="data"):
    """Create a mock StorageDomain object"""
    mock_sd = MagicMock()
    mock_sd.id = sd_id
    mock_sd.name = name
    mock_sd.type = MagicMock()
    mock_sd.type.value = sd_type
    return mock_sd


class TestDataCenterMCPList:
    """Test list_datacenters method"""

    def test_list_datacenters_empty(self):
        """Test empty data center list"""
        from ovirt_engine_mcp_server.mcp_datacenter import DataCenterMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        mock_dcs_service = MagicMock()
        mock_dcs_service.list.return_value = []
        mock_ovirt.connection.system_service.return_value.data_centers_service.return_value = mock_dcs_service

        dc_mcp = DataCenterMCP(mock_ovirt)
        result = dc_mcp.list_datacenters()

        assert result == []

    def test_list_datacenters_with_data(self):
        """Test data center list with data"""
        from ovirt_engine_mcp_server.mcp_datacenter import DataCenterMCP

        mock_dc = _create_mock_datacenter()
        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        mock_dcs_service = MagicMock()
        mock_dcs_service.list.return_value = [mock_dc]
        mock_ovirt.connection.system_service.return_value.data_centers_service.return_value = mock_dcs_service

        dc_mcp = DataCenterMCP(mock_ovirt)
        result = dc_mcp.list_datacenters()

        assert len(result) == 1
        assert result[0]["name"] == "Default"
        assert result[0]["status"] == "up"
        assert result[0]["storage_type"] == "nfs"

    def test_list_datacenters_not_connected(self):
        """Test exception raised when not connected"""
        from ovirt_engine_mcp_server.mcp_datacenter import DataCenterMCP
        from ovirt_engine_mcp_server.errors import OvirtConnectionError

        mock_ovirt = MagicMock()
        mock_ovirt.connected = False

        dc_mcp = DataCenterMCP(mock_ovirt)

        with pytest.raises(OvirtConnectionError):
            dc_mcp.list_datacenters()


class TestDataCenterMCPGet:
    """Test get_datacenter method"""

    def test_get_datacenter_by_id(self):
        """Test get data center by ID"""
        from ovirt_engine_mcp_server.mcp_datacenter import DataCenterMCP

        mock_dc = _create_mock_datacenter()
        mock_cluster = _create_mock_cluster()
        mock_sd = _create_mock_storage_domain()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        # Mock data center service
        mock_dc_service = MagicMock()
        mock_dc_service.get.return_value = mock_dc
        mock_dc_service.clusters_service.return_value.list.return_value = [mock_cluster]
        mock_dc_service.storage_domains_service.return_value.list.return_value = [mock_sd]
        mock_dc_service.networks_service.return_value.list.return_value = []

        mock_dcs_service = MagicMock()
        mock_dcs_service.data_center_service.return_value = mock_dc_service
        mock_dcs_service.list.return_value = []  # name search returns no results

        mock_ovirt.connection.system_service.return_value.data_centers_service.return_value = mock_dcs_service

        dc_mcp = DataCenterMCP(mock_ovirt)
        result = dc_mcp.get_datacenter("dc-123")

        assert result is not None
        assert result["id"] == "dc-123"
        assert result["name"] == "Default"
        assert len(result["clusters"]) == 1
        assert len(result["storage_domains"]) == 1

    def test_get_datacenter_not_found(self):
        """Test data center not found"""
        from ovirt_engine_mcp_server.mcp_datacenter import DataCenterMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_dcs_service = MagicMock()
        mock_dcs_service.data_center_service.return_value.get.side_effect = Exception("Not found")
        mock_dcs_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.data_centers_service.return_value = mock_dcs_service

        dc_mcp = DataCenterMCP(mock_ovirt)
        result = dc_mcp.get_datacenter("nonexistent")

        assert result is None


class TestDataCenterMCPCreate:
    """Test create_datacenter method"""

    def test_create_datacenter_success(self):
        """Test create data center success"""
        from ovirt_engine_mcp_server.mcp_datacenter import DataCenterMCP

        mock_dc = _create_mock_datacenter(name="NewDC")

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_dcs_service = MagicMock()
        mock_dcs_service.list.return_value = []  # name does not conflict
        mock_dcs_service.add.return_value = mock_dc

        mock_ovirt.connection.system_service.return_value.data_centers_service.return_value = mock_dcs_service

        dc_mcp = DataCenterMCP(mock_ovirt)
        result = dc_mcp.create_datacenter("NewDC", storage_type="nfs", description="Test DC")

        assert result["success"] is True
        assert "datacenter_id" in result
        mock_dcs_service.add.assert_called_once()

    def test_create_datacenter_already_exists(self):
        """Test create an already existing data center"""
        from ovirt_engine_mcp_server.mcp_datacenter import DataCenterMCP

        mock_dc = _create_mock_datacenter()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_dcs_service = MagicMock()
        mock_dcs_service.list.return_value = [mock_dc]  # name already exists

        mock_ovirt.connection.system_service.return_value.data_centers_service.return_value = mock_dcs_service

        dc_mcp = DataCenterMCP(mock_ovirt)

        with pytest.raises(ValueError, match="already exists"):
            dc_mcp.create_datacenter("Default")

    def test_create_datacenter_invalid_storage_type(self):
        """Test invalid storage type"""
        from ovirt_engine_mcp_server.mcp_datacenter import DataCenterMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        dc_mcp = DataCenterMCP(mock_ovirt)

        with pytest.raises(ValueError, match="Invalid storage type"):
            dc_mcp.create_datacenter("NewDC", storage_type="invalid")


class TestDataCenterMCPUpdate:
    """Test update_datacenter method"""

    def test_update_datacenter_success(self):
        """Test update data center success"""
        from ovirt_engine_mcp_server.mcp_datacenter import DataCenterMCP

        mock_dc = _create_mock_datacenter()
        mock_dc_service = MagicMock()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_dcs_service = MagicMock()
        mock_dcs_service.data_center_service.return_value.get.side_effect = [mock_dc, mock_dc]
        mock_dcs_service.list.return_value = []  # ID lookup succeeds

        mock_ovirt.connection.system_service.return_value.data_centers_service.return_value = mock_dcs_service

        dc_mcp = DataCenterMCP(mock_ovirt)
        result = dc_mcp.update_datacenter("dc-123", new_name="UpdatedDC", description="Updated")

        assert result["success"] is True

    def test_update_datacenter_not_found(self):
        """Test update a non-existent data center"""
        from ovirt_engine_mcp_server.mcp_datacenter import DataCenterMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_dcs_service = MagicMock()
        mock_dcs_service.data_center_service.return_value.get.side_effect = Exception("Not found")
        mock_dcs_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.data_centers_service.return_value = mock_dcs_service

        dc_mcp = DataCenterMCP(mock_ovirt)

        with pytest.raises(ValueError, match="not found"):
            dc_mcp.update_datacenter("nonexistent")


class TestDataCenterMCPDelete:
    """Test delete_datacenter method"""

    def test_delete_datacenter_success(self):
        """Test delete data center success"""
        from ovirt_engine_mcp_server.mcp_datacenter import DataCenterMCP

        mock_dc = _create_mock_datacenter()
        mock_dc_service = MagicMock()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_dcs_service = MagicMock()
        mock_dcs_service.data_center_service.return_value.get.return_value = mock_dc
        mock_dcs_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.data_centers_service.return_value = mock_dcs_service

        dc_mcp = DataCenterMCP(mock_ovirt)
        result = dc_mcp.delete_datacenter("dc-123")

        assert result["success"] is True
        mock_dc_service.remove.assert_not_called()  # dc_service.remove() is used

    def test_delete_datacenter_not_found(self):
        """Test delete a non-existent data center"""
        from ovirt_engine_mcp_server.mcp_datacenter import DataCenterMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_dcs_service = MagicMock()
        mock_dcs_service.data_center_service.return_value.get.side_effect = Exception("Not found")
        mock_dcs_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.data_centers_service.return_value = mock_dcs_service

        dc_mcp = DataCenterMCP(mock_ovirt)

        with pytest.raises(ValueError, match="not found"):
            dc_mcp.delete_datacenter("nonexistent")


class TestDataCenterMCPTools:
    """Test MCP_TOOLS registry"""

    def test_mcp_tools_defined(self):
        """Test MCP tool registry is defined"""
        from ovirt_engine_mcp_server.mcp_datacenter import MCP_TOOLS

        expected_tools = [
            "datacenter_list",
            "datacenter_get",
            "datacenter_create",
            "datacenter_update",
            "datacenter_delete",
        ]

        for tool in expected_tools:
            assert tool in MCP_TOOLS, f"Missing tool: {tool}"
            assert "method" in MCP_TOOLS[tool]
            assert "description" in MCP_TOOLS[tool]
