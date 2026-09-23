#!/usr/bin/env python3
"""Tests for AffinityMCP class - affinity group management module tests."""
import pytest
from unittest.mock import MagicMock


def _create_mock_cluster(cluster_id="cluster-123", name="Default"):
    """Create a mock Cluster object"""
    mock_cluster = MagicMock()
    mock_cluster.id = cluster_id
    mock_cluster.name = name
    return mock_cluster


def _create_mock_affinity_group(group_id="ag-123", name="web-servers", positive=True, enforcing=False):
    """Create a mock AffinityGroup object"""
    mock_group = MagicMock()
    mock_group.id = group_id
    mock_group.name = name
    mock_group.positive = positive
    mock_group.enforcing = enforcing
    mock_group.vms = []
    return mock_group


def _create_mock_vm(vm_id="vm-123", name="test-vm"):
    """Create a mock VM object"""
    mock_vm = MagicMock()
    mock_vm.id = vm_id
    mock_vm.name = name
    return mock_vm


class TestAffinityMCPListAffinityGroups:
    """Tests for the list_affinity_groups method"""

    def test_list_affinity_groups_empty(self):
        """Test an empty affinity group list"""
        from ovirt_engine_mcp_server.mcp_affinity import AffinityMCP

        mock_cluster = _create_mock_cluster()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_clusters_service = MagicMock()
        mock_clusters_service.cluster_service.return_value.get.return_value = mock_cluster
        mock_clusters_service.list.return_value = [mock_cluster]

        mock_affinity_groups_service = MagicMock()
        mock_affinity_groups_service.list.return_value = []

        mock_cluster_service = MagicMock()
        mock_cluster_service.affinity_groups_service.return_value = mock_affinity_groups_service

        mock_clusters_service.cluster_service.return_value = mock_cluster_service

        mock_ovirt.connection.system_service.return_value.clusters_service.return_value = mock_clusters_service

        affinity_mcp = AffinityMCP(mock_ovirt)
        result = affinity_mcp.list_affinity_groups("Default")

        assert result == []

    def test_list_affinity_groups_with_data(self):
        """Test affinity group list with data"""
        from ovirt_engine_mcp_server.mcp_affinity import AffinityMCP

        mock_cluster = _create_mock_cluster()
        mock_group = _create_mock_affinity_group()
        mock_vm = _create_mock_vm()
        mock_group.vms = [mock_vm]

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_clusters_service = MagicMock()
        mock_clusters_service.cluster_service.return_value.get.return_value = mock_cluster
        mock_clusters_service.list.return_value = [mock_cluster]

        mock_affinity_groups_service = MagicMock()
        mock_affinity_groups_service.list.return_value = [mock_group]

        mock_cluster_service = MagicMock()
        mock_cluster_service.affinity_groups_service.return_value = mock_affinity_groups_service

        mock_clusters_service.cluster_service.return_value = mock_cluster_service

        mock_ovirt.connection.system_service.return_value.clusters_service.return_value = mock_clusters_service

        affinity_mcp = AffinityMCP(mock_ovirt)
        result = affinity_mcp.list_affinity_groups("Default")

        assert len(result) == 1
        assert result[0]["name"] == "web-servers"
        assert result[0]["positive"] is True
        assert result[0]["vm_count"] == 1

    def test_list_affinity_groups_cluster_not_found(self):
        """Test cluster not found"""
        from ovirt_engine_mcp_server.mcp_affinity import AffinityMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_clusters_service = MagicMock()
        mock_clusters_service.cluster_service.return_value.get.side_effect = Exception("Not found")
        mock_clusters_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.clusters_service.return_value = mock_clusters_service

        affinity_mcp = AffinityMCP(mock_ovirt)

        with pytest.raises(ValueError, match="Cluster not found"):
            affinity_mcp.list_affinity_groups("Nonexistent")


class TestAffinityMCPGetAffinityGroup:
    """Tests for the get_affinity_group method"""

    def test_get_affinity_group_by_id(self):
        """Test getting an affinity group by ID"""
        from ovirt_engine_mcp_server.mcp_affinity import AffinityMCP

        mock_cluster = _create_mock_cluster()
        mock_group = _create_mock_affinity_group()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_clusters_service = MagicMock()
        mock_clusters_service.cluster_service.return_value.get.return_value = mock_cluster
        mock_clusters_service.list.return_value = [mock_cluster]

        mock_group_service = MagicMock()
        mock_group_service.get.return_value = mock_group

        mock_affinity_groups_service = MagicMock()
        mock_affinity_groups_service.affinity_group_service.return_value = mock_group_service

        mock_cluster_service = MagicMock()
        mock_cluster_service.affinity_groups_service.return_value = mock_affinity_groups_service

        mock_clusters_service.cluster_service.return_value = mock_cluster_service

        mock_ovirt.connection.system_service.return_value.clusters_service.return_value = mock_clusters_service

        affinity_mcp = AffinityMCP(mock_ovirt)
        result = affinity_mcp.get_affinity_group("Default", "ag-123")

        assert result is not None
        assert result["id"] == "ag-123"
        assert result["name"] == "web-servers"

    def test_get_affinity_group_not_found(self):
        """Test affinity group not found"""
        from ovirt_engine_mcp_server.mcp_affinity import AffinityMCP

        mock_cluster = _create_mock_cluster()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_clusters_service = MagicMock()
        mock_clusters_service.cluster_service.return_value.get.return_value = mock_cluster
        mock_clusters_service.list.return_value = [mock_cluster]

        mock_group_service = MagicMock()
        mock_group_service.get.side_effect = Exception("Not found")

        mock_affinity_groups_service = MagicMock()
        mock_affinity_groups_service.affinity_group_service.return_value = mock_group_service
        mock_affinity_groups_service.list.return_value = []

        mock_cluster_service = MagicMock()
        mock_cluster_service.affinity_groups_service.return_value = mock_affinity_groups_service

        mock_clusters_service.cluster_service.return_value = mock_cluster_service

        mock_ovirt.connection.system_service.return_value.clusters_service.return_value = mock_clusters_service

        affinity_mcp = AffinityMCP(mock_ovirt)
        result = affinity_mcp.get_affinity_group("Default", "nonexistent")

        assert result is None


class TestAffinityMCPCreateAffinityGroup:
    """Tests for the create_affinity_group method"""

    def test_create_affinity_group_success(self):
        """Test successful affinity group creation"""
        from ovirt_engine_mcp_server.mcp_affinity import AffinityMCP

        mock_cluster = _create_mock_cluster()
        mock_group = _create_mock_affinity_group()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_clusters_service = MagicMock()
        mock_clusters_service.cluster_service.return_value.get.return_value = mock_cluster
        mock_clusters_service.list.return_value = [mock_cluster]

        mock_affinity_groups_service = MagicMock()
        mock_affinity_groups_service.list.return_value = []  # no name conflict
        mock_affinity_groups_service.add.return_value = mock_group

        mock_cluster_service = MagicMock()
        mock_cluster_service.affinity_groups_service.return_value = mock_affinity_groups_service

        mock_clusters_service.cluster_service.return_value = mock_cluster_service

        mock_ovirt.connection.system_service.return_value.clusters_service.return_value = mock_clusters_service

        affinity_mcp = AffinityMCP(mock_ovirt)
        result = affinity_mcp.create_affinity_group(
            name="db-servers",
            cluster="Default",
            positive=True,
            enforcing=True
        )

        assert result["success"] is True
        assert result["enforcing"] is True

    def test_create_affinity_group_already_exists(self):
        """Test affinity group already exists"""
        from ovirt_engine_mcp_server.mcp_affinity import AffinityMCP

        mock_cluster = _create_mock_cluster()
        mock_group = _create_mock_affinity_group()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_clusters_service = MagicMock()
        mock_clusters_service.cluster_service.return_value.get.return_value = mock_cluster
        mock_clusters_service.list.return_value = [mock_cluster]

        mock_affinity_groups_service = MagicMock()
        mock_affinity_groups_service.list.return_value = [mock_group]  # name already exists

        mock_cluster_service = MagicMock()
        mock_cluster_service.affinity_groups_service.return_value = mock_affinity_groups_service

        mock_clusters_service.cluster_service.return_value = mock_cluster_service

        mock_ovirt.connection.system_service.return_value.clusters_service.return_value = mock_clusters_service

        affinity_mcp = AffinityMCP(mock_ovirt)

        with pytest.raises(ValueError, match="already exists"):
            affinity_mcp.create_affinity_group("web-servers", "Default")


class TestAffinityMCPUpdateAffinityGroup:
    """Tests for the update_affinity_group method"""

    def test_update_affinity_group_success(self):
        """Test successful affinity group update"""
        from ovirt_engine_mcp_server.mcp_affinity import AffinityMCP

        mock_cluster = _create_mock_cluster()
        mock_group = _create_mock_affinity_group()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_clusters_service = MagicMock()
        mock_clusters_service.cluster_service.return_value.get.return_value = mock_cluster
        mock_clusters_service.list.return_value = [mock_cluster]

        mock_group_service = MagicMock()
        mock_group_service.get.return_value = mock_group

        mock_affinity_groups_service = MagicMock()
        mock_affinity_groups_service.affinity_group_service.return_value = mock_group_service

        mock_cluster_service = MagicMock()
        mock_cluster_service.affinity_groups_service.return_value = mock_affinity_groups_service

        mock_clusters_service.cluster_service.return_value = mock_cluster_service

        mock_ovirt.connection.system_service.return_value.clusters_service.return_value = mock_clusters_service

        affinity_mcp = AffinityMCP(mock_ovirt)
        result = affinity_mcp.update_affinity_group(
            "Default",
            "ag-123",
            new_name="updated-group",
            enforcing=True
        )

        assert result["success"] is True


class TestAffinityMCPDeleteAffinityGroup:
    """Tests for the delete_affinity_group method"""

    def test_delete_affinity_group_success(self):
        """Test successful affinity group deletion"""
        from ovirt_engine_mcp_server.mcp_affinity import AffinityMCP

        mock_cluster = _create_mock_cluster()
        mock_group = _create_mock_affinity_group()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_clusters_service = MagicMock()
        mock_clusters_service.cluster_service.return_value.get.return_value = mock_cluster
        mock_clusters_service.list.return_value = [mock_cluster]

        mock_group_service = MagicMock()
        mock_group_service.get.return_value = mock_group

        mock_affinity_groups_service = MagicMock()
        mock_affinity_groups_service.affinity_group_service.return_value = mock_group_service

        mock_cluster_service = MagicMock()
        mock_cluster_service.affinity_groups_service.return_value = mock_affinity_groups_service

        mock_clusters_service.cluster_service.return_value = mock_cluster_service

        mock_ovirt.connection.system_service.return_value.clusters_service.return_value = mock_clusters_service

        affinity_mcp = AffinityMCP(mock_ovirt)
        result = affinity_mcp.delete_affinity_group("Default", "ag-123")

        assert result["success"] is True


class TestAffinityMCPAddVMToAffinityGroup:
    """Tests for the add_vm_to_affinity_group method"""

    def test_add_vm_to_affinity_group_success(self):
        """Test successfully adding a VM to an affinity group"""
        from ovirt_engine_mcp_server.mcp_affinity import AffinityMCP

        mock_cluster = _create_mock_cluster()
        mock_group = _create_mock_affinity_group()
        mock_vm = _create_mock_vm()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        # Cluster service
        mock_clusters_service = MagicMock()
        mock_clusters_service.cluster_service.return_value.get.return_value = mock_cluster
        mock_clusters_service.list.return_value = [mock_cluster]

        # VM service
        mock_vms_service = MagicMock()
        mock_vms_service.vm_service.return_value.get.return_value = mock_vm
        mock_vms_service.list.return_value = [mock_vm]

        # Group service
        mock_group_service = MagicMock()
        mock_group_service.get.return_value = mock_group

        mock_vms_in_group_service = MagicMock()

        mock_affinity_groups_service = MagicMock()
        mock_affinity_groups_service.affinity_group_service.return_value = mock_group_service
        mock_affinity_groups_service.affinity_group_service.return_value.vms_service.return_value = mock_vms_in_group_service

        mock_cluster_service = MagicMock()
        mock_cluster_service.affinity_groups_service.return_value = mock_affinity_groups_service

        mock_clusters_service.cluster_service.return_value = mock_cluster_service

        mock_ovirt.connection.system_service.return_value.clusters_service.return_value = mock_clusters_service
        mock_ovirt.connection.system_service.return_value.vms_service.return_value = mock_vms_service

        affinity_mcp = AffinityMCP(mock_ovirt)
        result = affinity_mcp.add_vm_to_affinity_group("Default", "ag-123", "test-vm")

        assert result["success"] is True


class TestAffinityMCPRemoveVMFromAffinityGroup:
    """Tests for the remove_vm_from_affinity_group method"""

    def test_remove_vm_from_affinity_group_success(self):
        """Test successfully removing a VM from an affinity group"""
        from ovirt_engine_mcp_server.mcp_affinity import AffinityMCP

        mock_cluster = _create_mock_cluster()
        mock_group = _create_mock_affinity_group()
        mock_vm = _create_mock_vm()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        # Cluster service
        mock_clusters_service = MagicMock()
        mock_clusters_service.cluster_service.return_value.get.return_value = mock_cluster
        mock_clusters_service.list.return_value = [mock_cluster]

        # VM service
        mock_vms_service = MagicMock()
        mock_vms_service.vm_service.return_value.get.return_value = mock_vm
        mock_vms_service.list.return_value = [mock_vm]

        # Group service
        mock_group_service = MagicMock()
        mock_group_service.get.return_value = mock_group

        mock_vm_in_group_service = MagicMock()

        mock_vms_in_group_service = MagicMock()
        mock_vms_in_group_service.vm_service.return_value = mock_vm_in_group_service

        mock_affinity_groups_service = MagicMock()
        mock_affinity_groups_service.affinity_group_service.return_value = mock_group_service
        mock_affinity_groups_service.affinity_group_service.return_value.vms_service.return_value = mock_vms_in_group_service

        mock_cluster_service = MagicMock()
        mock_cluster_service.affinity_groups_service.return_value = mock_affinity_groups_service

        mock_clusters_service.cluster_service.return_value = mock_cluster_service

        mock_ovirt.connection.system_service.return_value.clusters_service.return_value = mock_clusters_service
        mock_ovirt.connection.system_service.return_value.vms_service.return_value = mock_vms_service

        affinity_mcp = AffinityMCP(mock_ovirt)
        result = affinity_mcp.remove_vm_from_affinity_group("Default", "ag-123", "test-vm")

        assert result["success"] is True


class TestAffinityMCPTools:
    """Tests for the MCP_TOOLS registry"""

    def test_mcp_tools_defined(self):
        """Test that the MCP tool registry is defined"""
        from ovirt_engine_mcp_server.mcp_affinity import MCP_TOOLS

        expected_tools = [
            "affinity_group_list",
            "affinity_group_get",
            "affinity_group_create",
            "affinity_group_update",
            "affinity_group_delete",
            "affinity_group_add_vm",
            "affinity_group_remove_vm",
        ]

        for tool in expected_tools:
            assert tool in MCP_TOOLS, f"Missing tool: {tool}"
            assert "method" in MCP_TOOLS[tool]
            assert "description" in MCP_TOOLS[tool]
