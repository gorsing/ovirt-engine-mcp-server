#!/usr/bin/env python3
"""Tests for HostExtendedMCP class - host extension module tests.."""
from types import SimpleNamespace

import pytest
from unittest.mock import MagicMock


def _create_mock_host(host_id="host-123", name="host1", status="up"):
    """Create a mock Host object."""
    mock_host = MagicMock()
    mock_host.id = host_id
    mock_host.name = name
    mock_host.description = "Test host"
    mock_host.status = MagicMock()
    mock_host.status.value = status
    mock_host.address = "192.168.1.1"
    mock_host.port = 54321
    mock_host.cluster = MagicMock()
    mock_host.cluster.name = "Default"
    mock_host.cluster.id = "cluster-123"
    mock_host.cpu = MagicMock()
    mock_host.cpu.topology = MagicMock()
    mock_host.cpu.topology.cores = 8
    mock_host.cpu.topology.sockets = 1
    mock_host.cpu.topology.threads = 2
    mock_host.cpu.speed = 3000
    mock_host.memory = 68719476736  # 64GB
    mock_host.os = MagicMock()
    mock_host.os.type = MagicMock()
    mock_host.os.type.value = "rhel"
    mock_host.os.version = MagicMock()
    mock_host.os.version.full_version = "8.6"
    mock_host.kvm = MagicMock()
    mock_host.kvm.version = "4.0"
    mock_host.libvirt_version = MagicMock()
    mock_host.libvirt_version.full_version = "8.0.0"
    mock_host.vdsm_version = MagicMock()
    mock_host.vdsm_version.full_version = "4.50"
    return mock_host


def _create_mock_stat(stat_name, stat_value):
    """Create a mock Stat object."""
    mock_stat = MagicMock()
    mock_stat.name = stat_name
    mock_stat.values = [MagicMock()]
    mock_stat.values[0].datum = stat_value
    return mock_stat


def _create_mock_device(device_id="dev-123", name="eth0"):
    """Create a mock Device object."""
    mock_device = MagicMock()
    mock_device.id = device_id
    mock_device.name = name
    mock_device.capability = MagicMock()
    mock_device.capability.value = "nic"
    mock_device.product = MagicMock()
    mock_device.product.name = "Intel Ethernet"
    mock_device.vendor = MagicMock()
    mock_device.vendor.name = "Intel"
    mock_device.driver = "igb"
    return mock_device


class TestHostExtendedMCPGetHost:
    """Tests for get_host method."""

    def test_get_host_by_id(self):
        """Get host by ID."""
        from ovirt_engine_mcp_server.mcp_host_extended import HostExtendedMCP

        mock_host = _create_mock_host()
        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_host_service = MagicMock()
        mock_host_service.get.return_value = mock_host
        mock_host_service.nics_service.return_value.list.return_value = []
        mock_host_service.storage_service.return_value.list.return_value = []

        mock_hosts_service = MagicMock()
        mock_hosts_service.host_service.return_value = mock_host_service
        mock_hosts_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.hosts_service.return_value = mock_hosts_service

        host_mcp = HostExtendedMCP(mock_ovirt)
        result = host_mcp.get_host("host-123")

        assert result is not None
        assert result["id"] == "host-123"
        assert result["name"] == "host1"
        assert result["status"] == "up"

    def test_get_host_not_found(self):
        """Host not found."""
        from ovirt_engine_mcp_server.mcp_host_extended import HostExtendedMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_hosts_service = MagicMock()
        mock_hosts_service.host_service.return_value.get.side_effect = Exception("Not found")
        mock_hosts_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.hosts_service.return_value = mock_hosts_service

        host_mcp = HostExtendedMCP(mock_ovirt)
        result = host_mcp.get_host("nonexistent")

        assert result is None

    def test_get_host_with_nics(self):
        """Get host with NIC information."""
        from ovirt_engine_mcp_server.mcp_host_extended import HostExtendedMCP

        mock_host = _create_mock_host()
        mock_nic = MagicMock()
        mock_nic.id = "nic-123"
        mock_nic.name = "eth0"
        mock_nic.mac = MagicMock()
        mock_nic.mac.address = "00:11:22:33:44:55"
        mock_nic.ip = MagicMock()
        mock_nic.ip.address = "192.168.1.100"
        mock_nic.speed = 1000000000

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_host_service = MagicMock()
        mock_host_service.get.return_value = mock_host
        mock_host_service.nics_service.return_value.list.return_value = [mock_nic]
        mock_host_service.storage_service.return_value.list.return_value = []

        mock_hosts_service = MagicMock()
        mock_hosts_service.host_service.return_value = mock_host_service
        mock_hosts_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.hosts_service.return_value = mock_hosts_service

        host_mcp = HostExtendedMCP(mock_ovirt)
        result = host_mcp.get_host("host-123")

        assert result is not None
        assert len(result["nics"]) == 1
        assert result["nics"][0]["name"] == "eth0"


class TestHostExtendedMCPAddHost:
    """Tests for add_host method."""

    def test_add_host_success(self):
        """Add host successfully."""
        from ovirt_engine_mcp_server.mcp_host_extended import HostExtendedMCP

        mock_host = _create_mock_host()
        mock_cluster = MagicMock()
        mock_cluster.id = "cluster-123"

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_clusters_service = MagicMock()
        mock_clusters_service.list.return_value = [mock_cluster]

        mock_hosts_service = MagicMock()
        mock_hosts_service.list.return_value = []  # no name conflict
        mock_hosts_service.add.return_value = mock_host

        mock_ovirt.connection.system_service.return_value.clusters_service.return_value = mock_clusters_service
        mock_ovirt.connection.system_service.return_value.hosts_service.return_value = mock_hosts_service

        host_mcp = HostExtendedMCP(mock_ovirt)
        result = host_mcp.add_host(
            name="new-host",
            cluster="Default",
            address="192.168.1.10",
            password="secret"
        )

        assert result["success"] is True
        assert "host_id" in result

    def test_add_host_cluster_not_found(self):
        """Add host when cluster does not exist."""
        from ovirt_engine_mcp_server.mcp_host_extended import HostExtendedMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_clusters_service = MagicMock()
        mock_clusters_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.clusters_service.return_value = mock_clusters_service

        host_mcp = HostExtendedMCP(mock_ovirt)

        with pytest.raises(ValueError, match="Cluster not found"):
            host_mcp.add_host("new-host", "Nonexistent", "192.168.1.10")

    def test_add_host_already_exists(self):
        """Add an already existing host."""
        from ovirt_engine_mcp_server.mcp_host_extended import HostExtendedMCP

        mock_host = _create_mock_host()
        mock_cluster = MagicMock()
        mock_cluster.id = "cluster-123"

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_clusters_service = MagicMock()
        mock_clusters_service.list.return_value = [mock_cluster]

        mock_hosts_service = MagicMock()
        mock_hosts_service.list.return_value = [mock_host]  # name already exists

        mock_ovirt.connection.system_service.return_value.clusters_service.return_value = mock_clusters_service
        mock_ovirt.connection.system_service.return_value.hosts_service.return_value = mock_hosts_service

        host_mcp = HostExtendedMCP(mock_ovirt)

        with pytest.raises(ValueError, match="already exists"):
            host_mcp.add_host("host1", "Default", "192.168.1.10")


class TestHostExtendedMCPRemoveHost:
    """Tests for remove_host method."""

    def test_remove_host_success(self):
        """Remove host successfully."""
        from ovirt_engine_mcp_server.mcp_host_extended import HostExtendedMCP

        mock_host = _create_mock_host()
        mock_host_service = MagicMock()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_hosts_service = MagicMock()
        mock_hosts_service.host_service.return_value.get.return_value = mock_host
        mock_hosts_service.host_service.return_value = mock_host_service
        mock_hosts_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.hosts_service.return_value = mock_hosts_service

        # re-set mock_host_service
        mock_ovirt.connection.system_service.return_value.hosts_service.return_value.host_service.return_value = mock_host_service
        mock_ovirt.connection.system_service.return_value.hosts_service.return_value.list.return_value = []

        host_mcp = HostExtendedMCP(mock_ovirt)
        result = host_mcp.remove_host("host-123")

        assert result["success"] is True

    def test_remove_host_not_found(self):
        """Remove a nonexistent host."""
        from ovirt_engine_mcp_server.mcp_host_extended import HostExtendedMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_hosts_service = MagicMock()
        mock_hosts_service.host_service.return_value.get.side_effect = Exception("Not found")
        mock_hosts_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.hosts_service.return_value = mock_hosts_service

        host_mcp = HostExtendedMCP(mock_ovirt)

        with pytest.raises(ValueError, match="Host not found"):
            host_mcp.remove_host("nonexistent")


class TestHostExtendedMCPGetHostStats:
    """Tests for get_host_stats method."""

    def test_get_host_stats_success(self):
        """Get host statistics successfully."""
        from ovirt_engine_mcp_server.mcp_host_extended import HostExtendedMCP

        mock_host = _create_mock_host()
        mock_stats = [
            _create_mock_stat("memory.used", 32768),
            _create_mock_stat("memory.free", 32768),
            _create_mock_stat("cpu.current.user", 15.5),
            _create_mock_stat("cpu.current.system", 5.2),
            _create_mock_stat("cpu.load.avg.5m", 2.5),
        ]

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_host_service = MagicMock()
        mock_host_service.get.return_value = mock_host
        mock_host_service.statistics_service.return_value.list.return_value = mock_stats

        mock_hosts_service = MagicMock()
        mock_hosts_service.host_service.return_value = mock_host_service
        mock_hosts_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.hosts_service.return_value = mock_hosts_service

        host_mcp = HostExtendedMCP(mock_ovirt)
        result = host_mcp.get_host_stats("host-123")

        assert result["host_id"] == "host-123"
        assert "stats" in result
        assert "memory_used_mb" in result["stats"]
        assert "memory_usage_percent" in result["stats"]


class TestHostExtendedMCPGetHostDevices:
    """Tests for get_host_devices method."""

    def test_get_host_devices_success(self):
        """Get host devices successfully."""
        from ovirt_engine_mcp_server.mcp_host_extended import HostExtendedMCP

        mock_host = _create_mock_host()
        mock_devices = [_create_mock_device(f"dev-{i}", f"device{i}") for i in range(3)]

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_host_service = MagicMock()
        mock_host_service.get.return_value = mock_host
        mock_host_service.devices_service.return_value.list.return_value = mock_devices

        mock_hosts_service = MagicMock()
        mock_hosts_service.host_service.return_value = mock_host_service
        mock_hosts_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.hosts_service.return_value = mock_hosts_service

        host_mcp = HostExtendedMCP(mock_ovirt)
        result = host_mcp.get_host_devices("host-123")

        assert len(result) == 3
        assert result[0]["name"] == "device0"

    def test_get_host_devices_not_found(self):
        """Get devices when host does not exist."""
        from ovirt_engine_mcp_server.mcp_host_extended import HostExtendedMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_hosts_service = MagicMock()
        mock_hosts_service.host_service.return_value.get.side_effect = Exception("Not found")
        mock_hosts_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.hosts_service.return_value = mock_hosts_service

        host_mcp = HostExtendedMCP(mock_ovirt)

        with pytest.raises(ValueError, match="Host not found"):
            host_mcp.get_host_devices("nonexistent")


class TestHostExtendedMCPTools:
    """Tests for MCP_TOOLS registry."""

    def test_mcp_tools_defined(self):
        """MCP tool registry is defined."""
        from ovirt_engine_mcp_server.mcp_host_extended import MCP_TOOLS

        expected_tools = [
            "host_get",
            "host_add",
            "host_remove",
            "host_stats",
            "host_devices",
        ]

        for tool in expected_tools:
            assert tool in MCP_TOOLS, f"Missing tool: {tool}"
            assert "method" in MCP_TOOLS[tool]
            assert "description" in MCP_TOOLS[tool]


class TestHostLiveEngineAttributes:
    """Live Engine Host objects expose different attributes than assumed.

    Regression cover for: ``os.type`` is a plain ``str`` (not an enum),
    ``kvm`` / ``vdsm_version`` don't exist at all, and ``HostStorage`` has no
    ``size`` / ``available`` / ``mount_point`` — capacity lives on the LUNs.
    """

    @staticmethod
    def _live_host():
        return SimpleNamespace(
            id="host-77",
            name="ovih02.dcz",
            description=None,
            status=SimpleNamespace(value="up"),
            cluster=SimpleNamespace(name="Default", id="cluster-77"),
            address="10.25.248.132",
            port=22,
            cpu=SimpleNamespace(
                topology=SimpleNamespace(cores=64, sockets=2, threads=2),
                speed=2600,
            ),
            memory=137438953472,  # 128 GB
            os=SimpleNamespace(type="RHEL"),  # plain str, no .value, no .version
            libvirt_version=SimpleNamespace(full_version="8.6.0"),
            # NOTE: no `kvm` and no `vdsm_version` attributes exist at all
        )

    @staticmethod
    def _live_storage():
        return SimpleNamespace(
            id="storage-1",
            name="ovih02-dcz-DomData",
            type=SimpleNamespace(value="fcp"),
            path=None,
            # no size / available / mount_point here
            logical_units=[SimpleNamespace(size=107374182400, paths=1)],  # 100 GB
        )

    @staticmethod
    def _mock_ovirt(host, storage_list, devices=None, numa_nodes=None):
        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        host_service = MagicMock()
        host_service.get.return_value = host
        host_service.nics_service.return_value.list.return_value = []
        host_service.storage_service.return_value.list.return_value = storage_list
        host_service.devices_service.return_value.list.return_value = devices or []
        host_service.numa_nodes_service.return_value.list.return_value = numa_nodes or []

        hosts_service = MagicMock()
        hosts_service.host_service.return_value = host_service
        hosts_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.hosts_service.return_value = (
            hosts_service
        )
        return mock_ovirt

    def test_get_host_reads_live_attributes(self):
        from ovirt_engine_mcp_server.mcp_host_extended import HostExtendedMCP

        mock_ovirt = self._mock_ovirt(self._live_host(), [self._live_storage()])

        result = HostExtendedMCP(mock_ovirt).get_host("host-77")

        assert result is not None
        assert result["name"] == "ovih02.dcz"
        assert result["status"] == "up"
        assert result["os_type"] == "RHEL"  # plain str, must not touch .value
        assert result["os_version"] == ""  # os.version is absent
        assert result["kvm_version"] == ""  # attribute does not exist
        assert result["vdsm_version"] == ""  # attribute does not exist
        assert result["libvirt_version"] == "8.6.0"
        assert result["storage"][0]["size_gb"] == 100  # from the LUNs

    def test_list_host_storage_without_size_attributes(self):
        from ovirt_engine_mcp_server.mcp_host_extended import HostExtendedMCP

        mock_ovirt = self._mock_ovirt(self._live_host(), [self._live_storage()])

        result = HostExtendedMCP(mock_ovirt).list_host_storage("host-77")

        assert len(result) == 1
        entry = result[0]
        assert entry["name"] == "ovih02-dcz-DomData"
        assert entry["type"] == "fcp"
        assert entry["size_gb"] == 100  # summed from logical_units
        assert entry["free_gb"] is None  # no `available` attribute: unknown, not zero
        assert entry["mount_point"] == ""  # no `mount_point` attribute
        assert entry["path"] == ""  # None on this engine

    @staticmethod
    def _live_device():
        return SimpleNamespace(
            id="7063695f303030305f30375f30305f30",
            name="pci_0000_07_00_0",
            capability="pci",  # plain str on live engines, no `.value`
            product=SimpleNamespace(name="Virtio 1.0 RNG"),
            vendor=SimpleNamespace(name="Red Hat, Inc."),
            driver="virtio-pci",
            iommu_group=None,
        )

    @staticmethod
    def _live_numa_node():
        return SimpleNamespace(
            id="numa-node-0",
            index=0,
            memory=15933,  # live engines report MB, not bytes
            cpu=SimpleNamespace(
                topology=None,  # live engines leave topology empty
                cores=[SimpleNamespace(index=i) for i in range(16)],
            ),
        )

    def test_get_host_devices_plain_str_capability(self):
        """Live `capability` is a plain str: `.value` must not be touched."""
        from ovirt_engine_mcp_server.mcp_host_extended import HostExtendedMCP

        mock_ovirt = self._mock_ovirt(self._live_host(), [], devices=[self._live_device()])

        result = HostExtendedMCP(mock_ovirt).get_host_devices("host-77")

        assert len(result) == 1
        assert result[0]["capability"] == "pci"
        assert result[0]["product"] == "Virtio 1.0 RNG"
        assert result[0]["vendor"] == "Red Hat, Inc."
        assert result[0]["driver"] == "virtio-pci"
        assert result[0]["iommu_group"] is None

    def test_get_host_numa_live_engine_values(self):
        """Live NUMA: memory already in MB, topology None, cores as a list."""
        from ovirt_engine_mcp_server.mcp_host_extended import HostExtendedMCP

        mock_ovirt = self._mock_ovirt(
            self._live_host(), [], numa_nodes=[self._live_numa_node()]
        )

        result = HostExtendedMCP(mock_ovirt).get_host_numa("host-77")

        assert result["node_count"] == 1
        node = result["numa_nodes"][0]
        assert node["memory_mb"] == 15933
        assert node["cpu"]["cores"] == 16
        assert node["cpu"]["sockets"] == 0
        assert node["cpu"]["threads"] == 0

    def test_get_host_numa_prefers_declared_topology(self):
        """When topology is present it wins over the core list."""
        from ovirt_engine_mcp_server.mcp_host_extended import HostExtendedMCP

        node = SimpleNamespace(
            id="numa-node-1",
            index=1,
            memory=4096,
            cpu=SimpleNamespace(
                topology=SimpleNamespace(cores=4, sockets=1, threads=1),
                cores=[],
            ),
        )
        mock_ovirt = self._mock_ovirt(self._live_host(), [], numa_nodes=[node])

        result = HostExtendedMCP(mock_ovirt).get_host_numa("host-77")

        entry = result["numa_nodes"][0]
        assert entry["memory_mb"] == 4096
        assert entry["cpu"] == {"cores": 4, "sockets": 1, "threads": 1}

    def test_list_host_storage_reports_available_as_gb(self):
        """When the engine reports `available`, convert bytes to GB."""
        from ovirt_engine_mcp_server.mcp_host_extended import HostExtendedMCP

        storage = SimpleNamespace(
            id="storage-2",
            name="iso-domain",
            type=SimpleNamespace(value="nfs"),
            path="/exports/iso",
            available=107374182400,  # 100 GB in bytes
            logical_units=[],
        )
        mock_ovirt = self._mock_ovirt(self._live_host(), [storage])

        result = HostExtendedMCP(mock_ovirt).list_host_storage("host-77")

        assert result[0]["free_gb"] == 100
