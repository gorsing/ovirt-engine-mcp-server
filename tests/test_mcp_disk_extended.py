#!/usr/bin/env python3
"""Tests for DiskExtendedMCP class - disk extension module tests."""
from types import SimpleNamespace

import pytest
from unittest.mock import MagicMock


def _create_mock_disk(disk_id="disk-123", name="disk1", status="ok", size=53687091200):
    """Create a mock Disk object"""
    mock_disk = MagicMock()
    mock_disk.id = disk_id
    mock_disk.name = name
    mock_disk.description = "Test disk"
    mock_disk.status = MagicMock()
    mock_disk.status.value = status
    mock_disk.provisioned_size = size
    mock_disk.actual_size = size // 2
    mock_disk.format = MagicMock()
    mock_disk.format.value = "cow"
    mock_disk.storage_type = MagicMock()
    mock_disk.storage_type.value = "image"
    mock_disk.sparse = True
    mock_disk.interface = MagicMock()
    mock_disk.interface.value = "virtio"
    mock_disk.storage_domain = MagicMock()
    mock_disk.storage_domain.name = "storage1"
    mock_disk.storage_domain.id = "sd-123"
    mock_disk.shareable = False
    mock_disk.wipe_after_delete = False
    return mock_disk


def _create_mock_vm(vm_id="vm-123", name="test-vm"):
    """Create a mock VM object"""
    mock_vm = MagicMock()
    mock_vm.id = vm_id
    mock_vm.name = name
    return mock_vm


class TestDiskExtendedMCPGetDisk:
    """Tests for the get_disk method"""

    def test_get_disk_storage_domain_from_storage_domains(self):
        """Live disks leave ``storage_domain`` empty and fill the plural ref."""
        from ovirt_engine_mcp_server.mcp_disk_extended import DiskExtendedMCP

        mock_disk = MagicMock()
        mock_disk.id = "disk-1"
        mock_disk.name = "CentOS10_Disk1"
        mock_disk.description = ""
        mock_disk.status = MagicMock()
        mock_disk.status.value = "ok"
        mock_disk.provisioned_size = 10737418240
        mock_disk.actual_size = 10737418240
        mock_disk.format = MagicMock()
        mock_disk.format.value = "raw"
        mock_disk.storage_type = MagicMock()
        mock_disk.storage_type.value = "image"
        mock_disk.sparse = True
        mock_disk.interface = MagicMock()
        mock_disk.interface.value = "virtio"
        mock_disk.storage_domain = None  # live engine: singular ref is empty
        mock_disk.storage_domains = [SimpleNamespace(id="sd-9", name=None)]
        mock_disk.shareable = False
        mock_disk.wipe_after_delete = False
        mock_disk.vms = None  # live engine: no VM back-reference

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        system = mock_ovirt.connection.system_service.return_value
        system.disks_service.return_value.disk_service.return_value.get.return_value = mock_disk
        sd = (
            system.storage_domains_service.return_value.storage_domain_service
            .return_value.get.return_value
        )
        sd.name = "hosted_storage"

        result = DiskExtendedMCP(mock_ovirt).get_disk("disk-1")

        assert result is not None
        assert result["storage_domain"] == "hosted_storage"
        assert result["storage_domain_id"] == "sd-9"
        assert result["attachments"] == []  # Disk.vms is None on this engine

    def test_get_disk_by_id(self):
        """Test getting a disk by ID"""
        from ovirt_engine_mcp_server.mcp_disk_extended import DiskExtendedMCP

        mock_disk = _create_mock_disk()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_disk_service = MagicMock()
        mock_disk_service.get.return_value = mock_disk

        mock_disks_service = MagicMock()
        mock_disks_service.disk_service.return_value = mock_disk_service
        mock_disks_service.list.return_value = []

        # Mock disk attachments
        mock_ovirt.connection.system_service.return_value.disk_attachments_service.return_value.list.return_value = []

        mock_ovirt.connection.system_service.return_value.disks_service.return_value = mock_disks_service

        disk_mcp = DiskExtendedMCP(mock_ovirt)
        result = disk_mcp.get_disk("disk-123")

        assert result is not None
        assert result["id"] == "disk-123"
        assert result["name"] == "disk1"
        assert result["provisioned_size_gb"] == 50

    def test_get_disk_not_found(self):
        """Test disk not found"""
        from ovirt_engine_mcp_server.mcp_disk_extended import DiskExtendedMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_disks_service = MagicMock()
        mock_disks_service.disk_service.return_value.get.side_effect = Exception("Not found")
        mock_disks_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.disks_service.return_value = mock_disks_service

        disk_mcp = DiskExtendedMCP(mock_ovirt)
        result = disk_mcp.get_disk("nonexistent")

        assert result is None


class TestDiskExtendedMCPDeleteDisk:
    """Tests for the delete_disk method"""

    def test_delete_disk_success(self):
        """Test successful disk deletion"""
        from ovirt_engine_mcp_server.mcp_disk_extended import DiskExtendedMCP

        mock_disk = _create_mock_disk()
        mock_disk_service = MagicMock()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        # Create service chain mock
        system_service = mock_ovirt.connection.system_service.return_value
        disks_service = system_service.disks_service.return_value

        # Make disk_service return the correct mock
        disk_service_mock = disks_service.disk_service.return_value
        disk_service_mock.get.return_value = mock_disk
        disk_service_mock.remove.return_value = None

        # Search by name returns empty (lookup by ID)
        disks_service.list.return_value = []

        disk_mcp = DiskExtendedMCP(mock_ovirt)
        result = disk_mcp.delete_disk("disk-123")

        assert result["success"] is True

    def test_delete_disk_not_found(self):
        """Test deleting a nonexistent disk"""
        from ovirt_engine_mcp_server.mcp_disk_extended import DiskExtendedMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_disks_service = MagicMock()
        mock_disks_service.disk_service.return_value.get.side_effect = Exception("Not found")
        mock_disks_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.disks_service.return_value = mock_disks_service

        disk_mcp = DiskExtendedMCP(mock_ovirt)

        with pytest.raises(ValueError, match="not found"):
            disk_mcp.delete_disk("nonexistent")

    def test_delete_disk_status_not_ok(self):
        """Test deletion when disk status is not ok"""
        from ovirt_engine_mcp_server.mcp_disk_extended import DiskExtendedMCP

        mock_disk = _create_mock_disk(status="locked")

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_disks_service = MagicMock()
        mock_disks_service.disk_service.return_value.get.return_value = mock_disk
        mock_disks_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.disks_service.return_value = mock_disks_service

        disk_mcp = DiskExtendedMCP(mock_ovirt)

        with pytest.raises(RuntimeError, match="status not ok"):
            disk_mcp.delete_disk("disk-123")


class TestDiskExtendedMCPResizeDisk:
    """Tests for the resize_disk method"""

    def test_resize_disk_success(self):
        """Test successful disk resize"""
        from ovirt_engine_mcp_server.mcp_disk_extended import DiskExtendedMCP

        mock_disk = _create_mock_disk()
        mock_disk_service = MagicMock()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        # Create service chain mock
        system_service = mock_ovirt.connection.system_service.return_value
        disks_service = system_service.disks_service.return_value

        # Make disk_service return the correct mock
        disk_service_mock = disks_service.disk_service.return_value
        disk_service_mock.get.return_value = mock_disk
        disk_service_mock.update.return_value = None

        # Search by name returns empty (lookup by ID)
        disks_service.list.return_value = []

        disk_mcp = DiskExtendedMCP(mock_ovirt)
        result = disk_mcp.resize_disk("disk-123", 100)

        assert result["success"] is True
        assert result["old_size_gb"] == 50
        assert result["new_size_gb"] == 100

    def test_resize_disk_invalid_size(self):
        """Test invalid disk size"""
        from ovirt_engine_mcp_server.mcp_disk_extended import DiskExtendedMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        disk_mcp = DiskExtendedMCP(mock_ovirt)

        with pytest.raises(ValueError, match="must be greater than 0"):
            disk_mcp.resize_disk("disk-123", 0)

    def test_resize_disk_shrink_not_allowed(self):
        """Test that shrinking a disk is not allowed"""
        from ovirt_engine_mcp_server.mcp_disk_extended import DiskExtendedMCP

        mock_disk = _create_mock_disk()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_disks_service = MagicMock()
        mock_disks_service.disk_service.return_value.get.return_value = mock_disk
        mock_disks_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.disks_service.return_value = mock_disks_service

        disk_mcp = DiskExtendedMCP(mock_ovirt)

        with pytest.raises(ValueError, match="Cannot shrink disk"):
            disk_mcp.resize_disk("disk-123", 10)  # current 50GB, shrink to 10GB


class TestDiskExtendedMCPDetachDisk:
    """Tests for the detach_disk method"""

    def test_detach_disk_success(self):
        """Test successful disk detach"""
        from ovirt_engine_mcp_server.mcp_disk_extended import DiskExtendedMCP

        mock_disk = _create_mock_disk()
        mock_vm = _create_mock_vm()
        mock_attachment = MagicMock()
        mock_attachment.id = "att-123"
        mock_attachment.disk = MagicMock()
        mock_attachment.disk.id = "disk-123"

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        # Disk service
        mock_disk_service = MagicMock()
        mock_disk_service.get.return_value = mock_disk
        mock_disks_service = MagicMock()
        mock_disks_service.disk_service.return_value = mock_disk_service
        mock_disks_service.list.return_value = []

        # VM service
        mock_vm_service = MagicMock()
        mock_vm_service.get.return_value = mock_vm
        mock_vms_service = MagicMock()
        mock_vms_service.vm_service.return_value = mock_vm_service
        mock_vms_service.list.return_value = []

        # Attachments
        mock_attachments_service = MagicMock()
        mock_attachments_service.list.return_value = [mock_attachment]
        mock_attachment_service = MagicMock()
        mock_attachments_service.attachment_service.return_value = mock_attachment_service

        mock_vm_service.disk_attachments_service.return_value = mock_attachments_service

        mock_ovirt.connection.system_service.return_value.disks_service.return_value = mock_disks_service
        mock_ovirt.connection.system_service.return_value.vms_service.return_value = mock_vms_service

        disk_mcp = DiskExtendedMCP(mock_ovirt)
        result = disk_mcp.detach_disk("disk-123", "vm-123")

        assert result["success"] is True


class TestDiskExtendedMCPMoveDisk:
    """Tests for the move_disk method"""

    def test_move_disk_success(self):
        """Test successful disk move"""
        from ovirt_engine_mcp_server.mcp_disk_extended import DiskExtendedMCP

        mock_disk = _create_mock_disk()
        mock_target_sd = MagicMock()
        mock_target_sd.id = "sd-456"

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_disk_service = MagicMock()
        mock_disk_service.get.return_value = mock_disk
        mock_disks_service = MagicMock()
        mock_disks_service.disk_service.return_value = mock_disk_service
        mock_disks_service.list.return_value = []

        mock_sds_service = MagicMock()
        mock_sds_service.list.return_value = [mock_target_sd]

        mock_ovirt.connection.system_service.return_value.disks_service.return_value = mock_disks_service
        mock_ovirt.connection.system_service.return_value.storage_domains_service.return_value = mock_sds_service

        disk_mcp = DiskExtendedMCP(mock_ovirt)
        result = disk_mcp.move_disk("disk-123", "storage2")

        assert result["success"] is True

    def test_move_disk_storage_not_found(self):
        """Test target storage domain not found"""
        from ovirt_engine_mcp_server.mcp_disk_extended import DiskExtendedMCP

        mock_disk = _create_mock_disk()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_disk_service = MagicMock()
        mock_disk_service.get.return_value = mock_disk
        mock_disks_service = MagicMock()
        mock_disks_service.disk_service.return_value = mock_disk_service
        mock_disks_service.list.return_value = []

        mock_sds_service = MagicMock()
        mock_sds_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.disks_service.return_value = mock_disks_service
        mock_ovirt.connection.system_service.return_value.storage_domains_service.return_value = mock_sds_service

        disk_mcp = DiskExtendedMCP(mock_ovirt)

        with pytest.raises(ValueError, match="Storage domain not found"):
            disk_mcp.move_disk("disk-123", "nonexistent")


class TestDiskExtendedMCPGetStats:
    """Tests for the get_disk_stats method"""

    def test_get_disk_stats_success(self):
        """Test successful disk stats retrieval"""
        from ovirt_engine_mcp_server.mcp_disk_extended import DiskExtendedMCP

        mock_disk = _create_mock_disk()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_disk_service = MagicMock()
        mock_disk_service.get.return_value = mock_disk
        mock_disks_service = MagicMock()
        mock_disks_service.disk_service.return_value = mock_disk_service
        mock_disks_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.disks_service.return_value = mock_disks_service

        disk_mcp = DiskExtendedMCP(mock_ovirt)
        result = disk_mcp.get_disk_stats("disk-123")

        assert result["id"] == "disk-123"
        assert result["name"] == "disk1"
        assert "provisioned_gb" in result
        assert "actual_gb" in result
        assert "used_percent" in result


class TestDiskExtendedMCPTools:
    """Tests for the MCP_TOOLS registry"""

    def test_mcp_tools_defined(self):
        """Test that the MCP tool registry is defined"""
        from ovirt_engine_mcp_server.mcp_disk_extended import MCP_TOOLS

        expected_tools = [
            "disk_get",
            "disk_delete",
            "disk_resize",
            "disk_detach",
            "disk_move",
            "disk_stats",
        ]

        for tool in expected_tools:
            assert tool in MCP_TOOLS, f"Missing tool: {tool}"
            assert "method" in MCP_TOOLS[tool]
            assert "description" in MCP_TOOLS[tool]
