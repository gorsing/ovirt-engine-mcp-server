#!/usr/bin/env python3
"""Tests for OvirtMCP class - 综合测试覆盖."""
from types import SimpleNamespace

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime

from ovirt_engine_mcp_server.config import Config


@pytest.fixture
def mock_config():
    """Create a mock Config."""
    return Config(
        ovirt_engine_url="https://ovirt.test",
        ovirt_engine_user="admin@internal",
        ovirt_engine_password="test",
    )


def _create_mock_vm(vm_id="vm-123", name="test-vm", status="up", memory=4294967296):
    """创建 mock VM 对象"""
    mock_vm = MagicMock()
    mock_vm.id = vm_id
    mock_vm.name = name
    mock_vm.status = MagicMock()
    mock_vm.status.value = status
    mock_vm.memory = memory
    mock_vm.description = "Test VM"
    mock_vm.cluster = MagicMock()
    mock_vm.cluster.name = "Default"
    mock_vm.cluster.id = "cluster-123"
    mock_vm.host = MagicMock()
    mock_vm.host.name = "host1"
    mock_vm.cpu = MagicMock()
    mock_vm.cpu.topology = MagicMock()
    mock_vm.cpu.topology.cores = 2
    mock_vm.cpu.topology.threads = 2
    mock_vm.os = MagicMock()
    mock_vm.os.type = "linux"
    mock_vm.creation_time = datetime.now()
    # Mock disk_attachments_service
    mock_vm.disk_attachments_service = MagicMock()
    mock_vm.disk_attachments_service.return_value.list.return_value = []
    # Mock nics_service
    mock_vm.nics_service = MagicMock()
    mock_vm.nics_service.return_value.list.return_value = []
    return mock_vm


def _create_mock_snapshot(snap_id="snap-123", description="Test snapshot"):
    """创建 mock Snapshot 对象"""
    mock_snap = MagicMock()
    mock_snap.id = snap_id
    mock_snap.description = description
    mock_snap.date = datetime.now()
    mock_snap.snapshot_status = MagicMock()
    mock_snap.snapshot_status.value = "ok"
    return mock_snap


def _create_mock_disk(disk_id="disk-123", name="disk1", size=53687091200):
    """创建 mock Disk 对象"""
    mock_disk = MagicMock()
    mock_disk.id = disk_id
    mock_disk.name = name
    mock_disk.provisioned_size = size
    mock_disk.actual_size = size // 2
    mock_disk.status = MagicMock()
    mock_disk.status.value = "ok"
    mock_disk.format = MagicMock()
    mock_disk.format.value = "cow"
    mock_disk.interface = MagicMock()
    mock_disk.interface.value = "virtio"
    mock_disk.storage_domain = MagicMock()
    mock_disk.storage_domain.name = "storage1"
    mock_disk.storage_domain.id = "sd-123"
    return mock_disk


class TestOvirtMCPConnection:
    """Tests for OvirtMCP connection handling."""

    def test_init_with_config(self, mock_config):
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mcp = OvirtMCP(mock_config)
        assert mcp.config == mock_config
        assert mcp.connection is None
        assert mcp.connected is False

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_connect_success(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_conn = MagicMock()
        mock_conn.test.return_value = True
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        result = mcp.connect()

        assert result is True
        assert mcp.connected is True

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_connect_failure(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_conn_class.side_effect = Exception("Connection refused")

        mcp = OvirtMCP(mock_config)
        result = mcp.connect()

        assert result is False
        assert mcp.connected is False

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_is_connected(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_conn = MagicMock()
        mock_conn.test.return_value = True
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        assert mcp.is_connected() is False

        mcp.connect()
        assert mcp.is_connected() is True

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_disconnect(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_conn = MagicMock()
        mock_conn.test.return_value = True
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        result = mcp.disconnect()

        assert result is True
        assert mcp.connected is False


class TestOvirtMCPVMOperations:
    """Tests for VM-related operations."""

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_list_vms_empty(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_conn = MagicMock()
        mock_conn.test.return_value = True
        mock_vms_service = MagicMock()
        mock_vms_service.list.return_value = []
        mock_conn.system_service.return_value.vms_service.return_value = mock_vms_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        assert mcp.list_vms() == []

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_list_vms_with_data(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_vm = _create_mock_vm()
        mock_conn = MagicMock()
        mock_conn.test.return_value = True
        mock_vms_service = MagicMock()
        mock_vms_service.list.return_value = [mock_vm]
        mock_conn.system_service.return_value.vms_service.return_value = mock_vms_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        vms = mcp.list_vms()

        assert len(vms) == 1
        assert vms[0].name == "test-vm"

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_start_vm_success(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_vm = _create_mock_vm()
        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        # Setup service chain
        mock_vms_service = MagicMock()
        mock_vms_service.list.return_value = [mock_vm]
        mock_vm_service = MagicMock()
        mock_vm_service.start.return_value = None

        mock_conn.system_service.return_value.vms_service.return_value = mock_vms_service
        mock_conn.system_service.return_value.vms_service.return_value.vm_service.return_value = mock_vm_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        result = mcp.start_vm("test-vm")

        assert result["success"] is True
        mock_vm_service.start.assert_called_once()

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_start_vm_not_found(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_conn = MagicMock()
        mock_conn.test.return_value = True
        mock_vms_service = MagicMock()
        mock_vms_service.list.return_value = []
        # Make vm_service throw exception (VM not found by ID)
        mock_vms_service.vm_service.return_value.get.side_effect = Exception("Not found")
        mock_conn.system_service.return_value.vms_service.return_value = mock_vms_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()

        with pytest.raises(ValueError, match="VM not found"):
            mcp.start_vm("nonexistent")

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_stop_vm_graceful(self, mock_conn_class, mock_config):
        """测试优雅关闭 VM (shutdown)"""
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_vm = _create_mock_vm()
        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        mock_vms_service = MagicMock()
        mock_vms_service.list.return_value = [mock_vm]
        mock_vm_service = MagicMock()
        mock_vm_service.shutdown.return_value = None

        mock_conn.system_service.return_value.vms_service.return_value = mock_vms_service
        mock_conn.system_service.return_value.vms_service.return_value.vm_service.return_value = mock_vm_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        result = mcp.stop_vm("test-vm", graceful=True)

        assert result["success"] is True
        mock_vm_service.shutdown.assert_called_once()

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_stop_vm_force(self, mock_conn_class, mock_config):
        """测试强制关闭 VM (stop)"""
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_vm = _create_mock_vm()
        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        mock_vms_service = MagicMock()
        mock_vms_service.list.return_value = [mock_vm]
        mock_vm_service = MagicMock()
        mock_vm_service.stop.return_value = None

        mock_conn.system_service.return_value.vms_service.return_value = mock_vms_service
        mock_conn.system_service.return_value.vms_service.return_value.vm_service.return_value = mock_vm_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        result = mcp.stop_vm("test-vm", graceful=False)

        assert result["success"] is True
        mock_vm_service.stop.assert_called_once()

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_restart_vm(self, mock_conn_class, mock_config):
        """测试重启 VM"""
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_vm = _create_mock_vm()
        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        mock_vms_service = MagicMock()
        mock_vms_service.list.return_value = [mock_vm]
        mock_vm_service = MagicMock()

        mock_conn.system_service.return_value.vms_service.return_value = mock_vms_service
        mock_conn.system_service.return_value.vms_service.return_value.vm_service.return_value = mock_vm_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        result = mcp.restart_vm("test-vm")

        assert result["success"] is True
        mock_vm_service.reboot.assert_called_once()

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_delete_vm(self, mock_conn_class, mock_config):
        """测试删除 VM"""
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_vm = _create_mock_vm(status="down")
        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        mock_vms_service = MagicMock()
        mock_vms_service.list.return_value = [mock_vm]
        mock_vm_service = MagicMock()
        mock_vm_service.get.return_value = mock_vm

        mock_conn.system_service.return_value.vms_service.return_value = mock_vms_service
        mock_conn.system_service.return_value.vms_service.return_value.vm_service.return_value = mock_vm_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        result = mcp.delete_vm("test-vm")

        assert result["success"] is True
        mock_vm_service.remove.assert_called_once()

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_update_vm_resources(self, mock_conn_class, mock_config):
        """测试更新 VM 资源"""
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_vm = _create_mock_vm()
        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        mock_vms_service = MagicMock()
        mock_vms_service.list.return_value = [mock_vm]
        mock_vm_service = MagicMock()
        mock_vm_service.get.return_value = mock_vm

        mock_conn.system_service.return_value.vms_service.return_value = mock_vms_service
        mock_conn.system_service.return_value.vms_service.return_value.vm_service.return_value = mock_vm_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        result = mcp.update_vm_resources("test-vm", memory_mb=8192, cpu_cores=4)

        assert result["success"] is True
        mock_vm_service.update.assert_called_once()

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_create_vm_success(self, mock_conn_class, mock_config):
        """测试创建 VM 成功"""
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        # Mock cluster
        mock_cluster = MagicMock()
        mock_cluster.id = "cluster-123"
        mock_clusters_service = MagicMock()
        mock_clusters_service.list.return_value = [mock_cluster]

        # Mock template
        mock_template = MagicMock()
        mock_template.id = "template-123"
        mock_templates_service = MagicMock()
        mock_templates_service.list.return_value = [mock_template]

        # Mock VM creation
        mock_vm = _create_mock_vm()
        mock_vms_service = MagicMock()
        mock_vms_service.add.return_value = mock_vm

        # Mock network
        mock_network = MagicMock()
        mock_network.id = "net-123"
        mock_networks_service = MagicMock()
        mock_networks_service.list.return_value = [mock_network]

        mock_conn.system_service.return_value.clusters_service.return_value = mock_clusters_service
        mock_conn.system_service.return_value.templates_service.return_value = mock_templates_service
        mock_conn.system_service.return_value.vms_service.return_value = mock_vms_service
        mock_conn.system_service.return_value.networks_service.return_value = mock_networks_service

        # Mock nics_service for network attachment
        mock_nics_service = MagicMock()
        mock_vm_nics_service = MagicMock()
        mock_conn.system_service.return_value.vms_service.return_value.vm_service.return_value.nics_service.return_value = mock_vm_nics_service

        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        result = mcp.create_vm(
            name="new-vm",
            cluster="Default",
            memory_mb=4096,
            cpu_cores=2
        )

        assert result["success"] is True
        assert result["vm_id"] == "vm-123"


class TestOvirtMCPSnapshotOperations:
    """Tests for snapshot-related operations."""

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_list_snapshots(self, mock_conn_class, mock_config):
        """测试列出快照"""
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_vm = _create_mock_vm()
        mock_snapshot = _create_mock_snapshot()

        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        mock_vms_service = MagicMock()
        mock_vms_service.list.return_value = [mock_vm]
        mock_snapshots_service = MagicMock()
        mock_snapshots_service.list.return_value = [mock_snapshot]

        mock_conn.system_service.return_value.vms_service.return_value = mock_vms_service
        mock_conn.system_service.return_value.vms_service.return_value.vm_service.return_value.snapshots_service.return_value = mock_snapshots_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        snapshots = mcp.list_snapshots("test-vm")

        assert len(snapshots) == 1
        assert snapshots[0].id == "snap-123"

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_create_snapshot(self, mock_conn_class, mock_config):
        """测试创建快照"""
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_vm = _create_mock_vm()
        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        mock_vms_service = MagicMock()
        mock_vms_service.list.return_value = [mock_vm]
        mock_snapshots_service = MagicMock()

        mock_conn.system_service.return_value.vms_service.return_value = mock_vms_service
        mock_conn.system_service.return_value.vms_service.return_value.vm_service.return_value.snapshots_service.return_value = mock_snapshots_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        result = mcp.create_snapshot("test-vm", description="backup")

        assert result["success"] is True
        mock_snapshots_service.add.assert_called_once()

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_restore_snapshot(self, mock_conn_class, mock_config):
        """测试恢复快照"""
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_vm = _create_mock_vm(status="down")
        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        mock_vms_service = MagicMock()
        mock_vms_service.list.return_value = [mock_vm]
        mock_vm_service = MagicMock()
        mock_vm_service.get.return_value = mock_vm
        mock_snapshot_service = MagicMock()

        mock_conn.system_service.return_value.vms_service.return_value = mock_vms_service
        mock_conn.system_service.return_value.vms_service.return_value.vm_service.return_value = mock_vm_service
        mock_conn.system_service.return_value.vms_service.return_value.vm_service.return_value.snapshots_service.return_value.snapshot_service.return_value = mock_snapshot_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        result = mcp.restore_snapshot("test-vm", "snap-123")

        assert result["success"] is True
        mock_snapshot_service.restore.assert_called_once()

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_delete_snapshot(self, mock_conn_class, mock_config):
        """测试删除快照"""
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_vm = _create_mock_vm()
        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        mock_vms_service = MagicMock()
        mock_vms_service.list.return_value = [mock_vm]
        mock_snapshot_service = MagicMock()

        mock_conn.system_service.return_value.vms_service.return_value = mock_vms_service
        mock_conn.system_service.return_value.vms_service.return_value.vm_service.return_value.snapshots_service.return_value.snapshot_service.return_value = mock_snapshot_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        result = mcp.delete_snapshot("test-vm", "snap-123")

        assert result["success"] is True
        mock_snapshot_service.remove.assert_called_once()


class TestOvirtMCPDiskOperations:
    """Tests for disk-related operations."""

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_attach_disk(self, mock_conn_class, mock_config):
        """测试附加磁盘"""
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_vm = _create_mock_vm()
        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        mock_vms_service = MagicMock()
        mock_vms_service.list.return_value = [mock_vm]
        mock_disk_attachments_service = MagicMock()

        mock_conn.system_service.return_value.vms_service.return_value = mock_vms_service
        mock_conn.system_service.return_value.vms_service.return_value.vm_service.return_value.disk_attachments_service.return_value = mock_disk_attachments_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        result = mcp.attach_disk("test-vm", "disk-123")

        assert result["success"] is True
        mock_disk_attachments_service.add.assert_called_once()


class TestOvirtMCPNetworkOperations:
    """Tests for network-related operations."""

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_list_networks(self, mock_conn_class, mock_config):
        """测试列出网络"""
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_network = MagicMock()
        mock_network.id = "net-123"
        mock_network.name = "ovirtmgmt"
        mock_network.description = "Management network"
        mock_network.vlan = None
        mock_network.cluster = MagicMock()
        mock_network.cluster.name = "Default"
        mock_network.status = MagicMock()
        mock_network.status.value = "operational"

        mock_conn = MagicMock()
        mock_conn.test.return_value = True
        mock_networks_service = MagicMock()
        mock_networks_service.list.return_value = [mock_network]

        mock_conn.system_service.return_value.networks_service.return_value = mock_networks_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        networks = mcp.list_networks()

        assert len(networks) == 1
        assert networks[0]["name"] == "ovirtmgmt"

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_get_network(self, mock_conn_class, mock_config):
        """测试获取网络详情"""
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_network = MagicMock()
        mock_network.id = "net-123"
        mock_network.name = "ovirtmgmt"
        mock_network.description = "Management network"
        mock_network.vlan = None
        mock_network.mtu = 1500
        mock_network.status = MagicMock()
        mock_network.status.value = "operational"
        mock_network.data_center = MagicMock()
        mock_network.data_center.id = "dc-123"
        mock_network.cluster = MagicMock()
        mock_network.cluster.name = "Default"
        mock_network.usages = []

        mock_conn = MagicMock()
        mock_conn.test.return_value = True
        mock_networks_service = MagicMock()
        mock_networks_service.network_service.return_value.get.return_value = mock_network

        mock_conn.system_service.return_value.networks_service.return_value = mock_networks_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        network = mcp.get_network("ovirtmgmt")

        assert network is not None
        assert network["name"] == "ovirtmgmt"

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_create_network(self, mock_conn_class, mock_config):
        """测试创建网络"""
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_network = MagicMock()
        mock_network.id = "net-456"
        mock_network.name = "new-network"

        mock_conn = MagicMock()
        mock_conn.test.return_value = True
        mock_networks_service = MagicMock()
        mock_networks_service.add.return_value = mock_network

        mock_conn.system_service.return_value.networks_service.return_value = mock_networks_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        result = mcp.create_network("new-network", vlan_id=100, mtu=9000)

        assert result["success"] is True
        assert result["network_id"] == "net-456"


class TestOvirtMCPHostOperations:
    """Tests for host-related operations."""

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_list_hosts_empty(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_conn = MagicMock()
        mock_conn.test.return_value = True
        mock_hosts_service = MagicMock()
        mock_hosts_service.list.return_value = []
        mock_conn.system_service.return_value.hosts_service.return_value = mock_hosts_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        assert mcp.list_hosts() == []

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_list_hosts_with_data(self, mock_conn_class, mock_config):
        """测试列出主机"""
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_host = MagicMock()
        mock_host.id = "host-123"
        mock_host.name = "host1"
        mock_host.status = MagicMock()
        mock_host.status.value = "up"
        mock_host.address = "192.168.1.1"
        mock_host.cluster = MagicMock()
        mock_host.cluster.name = "Default"
        mock_host.cpu = MagicMock()
        mock_host.cpu.topology = MagicMock()
        mock_host.cpu.topology.cores = 8
        mock_host.cpu.topology.sockets = 1
        mock_host.cpu.topology.threads = 2
        mock_host.cpu.speed = 3000
        mock_host.memory = 68719476736  # 64GB

        mock_conn = MagicMock()
        mock_conn.test.return_value = True
        mock_hosts_service = MagicMock()
        mock_hosts_service.list.return_value = [mock_host]

        mock_conn.system_service.return_value.hosts_service.return_value = mock_hosts_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        hosts = mcp.list_hosts()

        assert len(hosts) == 1
        assert hosts[0]["name"] == "host1"


class TestOvirtMCPBackupOperations:
    """Tests for backup-related operations."""

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_create_backup_stub(self, mock_conn_class, mock_config):
        """测试创建备份（存根实现）"""
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_vm = _create_mock_vm()
        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        mock_vms_service = MagicMock()
        mock_vms_service.list.return_value = [mock_vm]
        mock_vms_service.vm_service.return_value.get.return_value = mock_vm
        # 不支持备份 API
        mock_vms_service.vm_service.return_value.backups_service.side_effect = AttributeError

        mock_conn.system_service.return_value.vms_service.return_value = mock_vms_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        result = mcp.create_backup("test-vm", backup_type="full")

        assert result["success"] is True
        assert result["stub"] is True  # 使用存根实现

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_restore_backup_stub(self, mock_conn_class, mock_config):
        """测试恢复备份（存根实现）"""
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_vm = _create_mock_vm()
        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        mock_vms_service = MagicMock()
        mock_vms_service.list.return_value = [mock_vm]
        mock_vms_service.vm_service.return_value.get.return_value = mock_vm
        mock_vms_service.vm_service.return_value.backups_service.return_value.backup_service.return_value.get.side_effect = Exception("Not found")

        mock_conn.system_service.return_value.vms_service.return_value = mock_vms_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        result = mcp.restore_backup("test-vm", "backup-123")

        assert result["success"] is True
        assert result.get("stub") is True


class TestValidation:
    """Tests for input validation."""

    def test_validate_name_ok(self):
        from ovirt_engine_mcp_server.validation import validate_name
        assert validate_name("test-vm") == "test-vm"

    def test_validate_name_empty(self):
        from ovirt_engine_mcp_server.validation import validate_name, ValidationError
        with pytest.raises(ValidationError):
            validate_name("")

    def test_validate_name_or_id(self):
        from ovirt_engine_mcp_server.validation import validate_name_or_id
        assert validate_name_or_id("vm-123") == "vm-123"

    def test_validate_positive_int(self):
        from ovirt_engine_mcp_server.validation import validate_positive_int
        assert validate_positive_int(4096, "memory") == 4096

    def test_validate_positive_int_too_small(self):
        from ovirt_engine_mcp_server.validation import validate_positive_int, ValidationError
        with pytest.raises(ValidationError):
            validate_positive_int(0, "memory", min_val=1)

    def test_validate_tool_args_no_rules(self):
        from ovirt_engine_mcp_server.validation import validate_tool_args
        args = {"name_or_id": "test"}
        assert validate_tool_args("vm_start", args) == args


class TestErrors:
    """Tests for error types."""

    def test_ovirt_mcp_error(self):
        from ovirt_engine_mcp_server.errors import OvirtMCPError
        err = OvirtMCPError("test", code="TEST", retryable=True)
        assert err.code == "TEST"
        assert err.retryable is True
        assert err.to_dict()["error"] is True

    def test_connection_error(self):
        from ovirt_engine_mcp_server.errors import OvirtConnectionError
        err = OvirtConnectionError()
        assert err.code == "CONNECTION_ERROR"
        assert err.retryable is True

    def test_not_found_error(self):
        from ovirt_engine_mcp_server.errors import NotFoundError
        err = NotFoundError("not here")
        assert err.retryable is False

    def test_timeout_error(self):
        from ovirt_engine_mcp_server.errors import OvirtTimeoutError
        err = OvirtTimeoutError()
        assert err.retryable is True


class TestDetailPayloads:
    """Sub-collections and reference resolution for detail payloads."""

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_get_vm_includes_disks_and_nics(self, mock_conn_class, mock_config):
        """Sub-collections must be fetched through services, not the entity."""
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_vm = _create_mock_vm()

        attachment = MagicMock()
        attachment.disk.id = "disk-1"
        attachment.bootable = True
        attachment.interface = MagicMock()
        attachment.interface.value = "virtio"

        disk = MagicMock()
        disk.id = "disk-1"
        disk.alias = "root"
        disk.provisioned_size = 10737418240
        disk.status.value = "ok"

        nic = MagicMock()
        nic.id = "nic-1"
        nic.name = "nic1"
        nic.mac.address = "56:6f:b4:e7:00:01"
        nic.linked = True
        nic.network = MagicMock()
        nic.network.name = None  # live payload: id only
        nic.network.id = "net-9"

        network = MagicMock()
        network.name = "ovirtmgmt"

        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        vms_service = mock_conn.system_service.return_value.vms_service.return_value
        vms_service.list.return_value = [mock_vm]
        vms_service.vm_service.return_value.get.return_value = mock_vm
        vms_service.vm_service.return_value.disk_attachments_service.return_value.list.return_value = [attachment]
        vms_service.vm_service.return_value.nics_service.return_value.list.return_value = [nic]

        disks_service = mock_conn.system_service.return_value.disks_service.return_value
        disks_service.disk_service.return_value.get.return_value = disk

        networks_service = mock_conn.system_service.return_value.networks_service.return_value
        networks_service.network_service.return_value.get.return_value = network

        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        vm = mcp.get_vm("test-vm")

        assert len(vm.disks) == 1
        assert vm.disks[0]["name"] == "root"
        assert vm.disks[0]["size_gb"] == 10
        assert vm.disks[0]["bootable"] is True
        assert vm.disks[0]["interface"] == "virtio"

        assert len(vm.nics) == 1
        assert vm.nics[0]["name"] == "nic1"
        assert vm.nics[0]["network"] == "ovirtmgmt"  # resolved by id

        disks_service.disk_service.assert_called_with("disk-1")

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_host_usage_comes_from_statistics(self, mock_conn_class, mock_config):
        """Host has no usage attributes — read the statistics instead."""
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        def stat(name, datum):
            s = MagicMock()
            s.name = name
            value = MagicMock()
            value.datum = datum
            s.values = [value]
            return s

        host = MagicMock()
        host.id = "host-1"
        host.name = "ovih02.dcz"
        host.status = MagicMock()
        host.status.value = "up"
        host.cluster = MagicMock()
        host.cluster.name = "Default"
        host.cpu = MagicMock()
        host.cpu.topology.cores = 8
        host.memory = 17179869184

        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        hosts_service = mock_conn.system_service.return_value.hosts_service.return_value
        hosts_service.list.return_value = [host]
        hosts_service.host_service.return_value.statistics_service.return_value.list.return_value = [
            stat("cpu.current.idle", 97),
            stat("cpu.current.user", 3),
            stat("memory.used", 8 * 1024**3),
            stat("memory.total", 16 * 1024**3),
        ]
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        hosts = mcp.list_hosts()

        assert hosts[0]["cpu_usage"] == 3.0  # 100 - idle
        assert hosts[0]["memory_usage"] == 50.0

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_get_vm_nic_resolves_network_through_profile(
        self, mock_conn_class, mock_config
    ):
        """Live NIC payload: ``network`` is empty, only the profile is set."""
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_vm = _create_mock_vm()
        # SimpleNamespace => accessing a missing attribute raises, like the SDK
        nic = SimpleNamespace(
            id="nic-1",
            name="nic1",
            mac=SimpleNamespace(address="56:6f:b4:e7:00:01"),
            linked=True,
            network=None,
            vnic_profile=SimpleNamespace(id="prof-9", name=None),
        )
        profile = SimpleNamespace(
            id="prof-9",
            name="ovirtmgmt",
            network=SimpleNamespace(id="net-9", name=None),
        )
        network = SimpleNamespace(id="net-9", name="ovirtmgmt")

        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        vms_service = mock_conn.system_service.return_value.vms_service.return_value
        vms_service.list.return_value = [mock_vm]
        vms_service.vm_service.return_value.get.return_value = mock_vm
        vms_service.vm_service.return_value.disk_attachments_service.return_value.list.return_value = []
        vms_service.vm_service.return_value.nics_service.return_value.list.return_value = [nic]

        profiles_service = (
            mock_conn.system_service.return_value.vnic_profiles_service.return_value
        )
        profiles_service.profile_service.return_value.get.return_value = profile

        networks_service = mock_conn.system_service.return_value.networks_service.return_value
        networks_service.network_service.return_value.get.return_value = network

        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        vm = mcp.get_vm("test-vm")

        assert vm.nics[0]["vnic_profile"] == "ovirtmgmt"
        assert vm.nics[0]["network"] == "ovirtmgmt"
        profiles_service.profile_service.assert_called_once_with("prof-9")
        networks_service.network_service.assert_called_once_with("net-9")

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_link_name_resolves_by_kind_and_caches(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        ref = MagicMock()
        ref.name = None
        ref.id = "net-9"

        resolved = MagicMock()
        resolved.name = "ovirtmgmt"

        mock_conn = MagicMock()
        mock_conn.test.return_value = True
        networks_service = mock_conn.system_service.return_value.networks_service.return_value
        networks_service.network_service.return_value.get.return_value = resolved
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()

        assert mcp._network_name(ref) == "ovirtmgmt"
        assert mcp._network_name(ref) == "ovirtmgmt"
        networks_service.network_service.assert_called_once_with("net-9")
        networks_service.network_service.return_value.get.assert_called_once()

        # an empty ref never hits the API
        assert mcp._network_name(None) == ""


class TestRenameVM:
    """Tests for OvirtMCP.rename_vm — backs the vm_rename tool."""

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_rename_vm_success(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_vm = _create_mock_vm()
        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        vms_service = MagicMock()
        vms_service.vm_service.return_value.get.return_value = mock_vm
        vms_service.list.return_value = []
        mock_conn.system_service.return_value.vms_service.return_value = vms_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        result = mcp.rename_vm("test-vm", "renamed-vm")

        assert result["success"] is True
        assert result["vm_id"] == "vm-123"
        assert result["old_name"] == "test-vm"
        assert result["new_name"] == "renamed-vm"

        update = vms_service.vm_service.return_value.update
        assert update.call_count == 1
        assert update.call_args[0][0].name == "renamed-vm"

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_rename_vm_to_existing_name_rejected(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_vm = _create_mock_vm()
        other_vm = _create_mock_vm(vm_id="other-id", name="taken")

        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        vms_service = MagicMock()
        vms_service.vm_service.return_value.get.return_value = mock_vm
        vms_service.list.return_value = [other_vm]
        mock_conn.system_service.return_value.vms_service.return_value = vms_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()

        with pytest.raises(ValueError):
            mcp.rename_vm("test-vm", "taken")

        vms_service.vm_service.return_value.update.assert_not_called()

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_rename_vm_same_name_is_noop(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_vm = _create_mock_vm()
        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        vms_service = MagicMock()
        vms_service.vm_service.return_value.get.return_value = mock_vm
        vms_service.list.return_value = []
        mock_conn.system_service.return_value.vms_service.return_value = vms_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        result = mcp.rename_vm("test-vm", "test-vm")

        assert result["success"] is True
        assert "未变" in result["message"]
        vms_service.vm_service.return_value.update.assert_not_called()

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_rename_vm_rejects_blank_new_name(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_conn = MagicMock()
        mock_conn.test.return_value = True
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()

        with pytest.raises(ValueError):
            mcp.rename_vm("test-vm", "   ")

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_rename_vm_not_found(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP
        from ovirt_engine_mcp_server.errors import NotFoundError

        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        vms_service = MagicMock()
        vms_service.vm_service.return_value.get.side_effect = Exception("404")
        vms_service.list.return_value = []
        mock_conn.system_service.return_value.vms_service.return_value = vms_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()

        with pytest.raises(NotFoundError):
            mcp.rename_vm("no-such-vm", "whatever")


class TestGetVMNotFound:
    """get_vm on a missing VM must raise, not return a bogus success."""

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_get_vm_missing_raises_not_found(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP
        from ovirt_engine_mcp_server.errors import NotFoundError

        mock_conn = MagicMock()
        mock_conn.test.return_value = True

        vms_service = MagicMock()
        vms_service.vm_service.return_value.get.side_effect = Exception("404")
        vms_service.list.return_value = []
        mock_conn.system_service.return_value.vms_service.return_value = vms_service
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()

        with pytest.raises(NotFoundError):
            mcp.get_vm("no-such-vm")


class TestReferenceNameResolution:
    """List payloads carry cluster/host links with only an id populated."""

    @staticmethod
    def _setup(mock_conn, resolved_cluster_name, resolved_host_name):
        """Wire a VM/host whose cluster/host link has name=None."""
        mock_conn.test.return_value = True

        resolved_cluster = MagicMock()
        resolved_cluster.name = resolved_cluster_name
        resolved_host = MagicMock()
        resolved_host.name = resolved_host_name

        system = mock_conn.system_service.return_value
        system.clusters_service.return_value.cluster_service.return_value.get.return_value = (
            resolved_cluster
        )
        system.hosts_service.return_value.host_service.return_value.get.return_value = (
            resolved_host
        )
        return system

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_map_vm_resolves_cluster_and_host_by_id(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_vm = _create_mock_vm()
        mock_vm.cluster = MagicMock()
        mock_vm.cluster.name = None  # live list payload: id only
        mock_vm.cluster.id = "cluster-77"
        mock_vm.host = MagicMock()
        mock_vm.host.name = None
        mock_vm.host.id = "host-77"

        mock_conn = MagicMock()
        system = self._setup(mock_conn, "Default", "ovih02.dcz")
        system.vms_service.return_value.list.return_value = [mock_vm]
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        vms = mcp.list_vms()

        assert vms[0].cluster == "Default"
        assert vms[0].host == "ovih02.dcz"
        system.clusters_service.return_value.cluster_service.assert_called_with(
            "cluster-77"
        )

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_map_vm_keeps_inline_names_without_extra_calls(
        self, mock_conn_class, mock_config
    ):
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        mock_vm = _create_mock_vm()  # cluster.name == "Default", host.name == "host1"

        mock_conn = MagicMock()
        system = self._setup(mock_conn, "SHOULD-NOT-BE-USED", "SHOULD-NOT-BE-USED")
        system.vms_service.return_value.list.return_value = [mock_vm]
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()
        vms = mcp.list_vms()

        assert vms[0].cluster == "Default"
        assert vms[0].host == "host1"
        system.clusters_service.return_value.cluster_service.assert_not_called()

    @patch("ovirt_engine_mcp_server.ovirt_mcp.Connection")
    def test_list_hosts_resolves_cluster_and_filters(self, mock_conn_class, mock_config):
        from ovirt_engine_mcp_server.ovirt_mcp import OvirtMCP

        host = MagicMock()
        host.id = "host-77"
        host.name = "ovih02.dcz"
        host.status = MagicMock()
        host.status.value = "up"
        host.cluster = MagicMock()
        host.cluster.name = None  # live list payload: id only
        host.cluster.id = "cluster-77"
        host.cpu = MagicMock()
        host.cpu.topology.cores = 64
        host.memory = 137438953472

        mock_conn = MagicMock()
        system = self._setup(mock_conn, "Default", "n/a")
        system.hosts_service.return_value.list.return_value = [host]
        mock_conn_class.return_value = mock_conn

        mcp = OvirtMCP(mock_config)
        mcp.connect()

        hosts = mcp.list_hosts(cluster="Default")
        assert len(hosts) == 1
        assert hosts[0]["cluster"] == "Default"

        # resolved once, then cached for the next call
        system.clusters_service.return_value.cluster_service.assert_called_once_with(
            "cluster-77"
        )
        assert mcp.list_hosts(cluster="OtherCluster") == []
        system.clusters_service.return_value.cluster_service.assert_called_once_with(
            "cluster-77"
        )
