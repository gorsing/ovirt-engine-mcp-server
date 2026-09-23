#!/usr/bin/env python3
"""Tests for MCP extensions - network and cluster extension module tests."""
from types import SimpleNamespace

import pytest
from unittest.mock import MagicMock


def _create_mock_network(net_id="net-123", name="ovirtmgmt"):
    """Create a mock Network object"""
    mock_net = MagicMock()
    mock_net.id = net_id
    mock_net.name = name
    mock_net.description = "Management network"
    mock_net.vlan = None
    mock_net.mtu = 1500
    mock_net.status = MagicMock()
    mock_net.status.value = "operational"
    mock_net.data_center = MagicMock()
    mock_net.data_center.id = "dc-123"
    mock_net.cluster = MagicMock()
    mock_net.cluster.name = "Default"
    mock_net.usages = []
    return mock_net


def _create_mock_cluster(cluster_id="cluster-123", name="Default"):
    """Create a mock Cluster object"""
    mock_cluster = MagicMock()
    mock_cluster.id = cluster_id
    mock_cluster.name = name
    mock_cluster.description = "Default cluster"
    mock_cluster.cpu = MagicMock()
    mock_cluster.cpu.architecture = MagicMock()
    mock_cluster.cpu.architecture.value = "x86_64"
    mock_cluster.cpu.id = "Intel"
    mock_cluster.memory = 137438953472  # 128GB
    mock_cluster.version = MagicMock()
    mock_cluster.version.major = 4
    mock_cluster.version.minor = 7
    mock_cluster.status = MagicMock()
    mock_cluster.status.value = "up"
    return mock_cluster


def _create_mock_template(template_id="tpl-123", name="CentOS8"):
    """Create a mock Template object"""
    mock_tpl = MagicMock()
    mock_tpl.id = template_id
    mock_tpl.name = name
    mock_tpl.description = "CentOS 8 template"
    mock_tpl.memory = 4294967296  # 4GB
    mock_tpl.cpu = MagicMock()
    mock_tpl.cpu.topology = MagicMock()
    mock_tpl.cpu.topology.cores = 2
    mock_tpl.os = MagicMock()
    mock_tpl.os.type = "linux"
    mock_tpl.creation_time = "2024-01-01"
    mock_tpl.disk_attachments_service = MagicMock()
    mock_tpl.disk_attachments_service.return_value.list.return_value = []
    return mock_tpl


class TestNetworkMCP:
    """Test NetworkMCP class"""

    def test_list_networks(self):
        """Test list networks"""
        from ovirt_engine_mcp_server.mcp_extensions import NetworkMCP

        mock_networks = [_create_mock_network()]

        mock_ovirt = MagicMock()
        mock_ovirt.list_networks.return_value = [
            {"id": "net-123", "name": "ovirtmgmt"}
        ]

        net_mcp = NetworkMCP(mock_ovirt)
        result = net_mcp.list_networks()

        assert len(result) == 1
        assert result[0]["name"] == "ovirtmgmt"

    def test_list_vnics(self):
        """Test list VM NICs"""
        from ovirt_engine_mcp_server.mcp_extensions import NetworkMCP

        mock_nic = MagicMock()
        mock_nic.id = "nic-123"
        mock_nic.name = "nic1"
        mock_nic.mac = MagicMock()
        mock_nic.mac.address = "00:11:22:33:44:55"
        mock_nic.network = MagicMock()
        mock_nic.network.name = "ovirtmgmt"
        mock_nic.interface = MagicMock()
        mock_nic.interface.value = "virtio"
        mock_nic.linked = True

        mock_vm = {"id": "vm-123", "name": "test-vm"}

        mock_ovirt = MagicMock()
        mock_ovirt._find_vm.return_value = mock_vm
        mock_ovirt.connection.system_service.return_value.vms_service.return_value.vm_service.return_value.nics_service.return_value.list.return_value = [mock_nic]

        net_mcp = NetworkMCP(mock_ovirt)
        result = net_mcp.list_vnics("test-vm")

        assert len(result) == 1
        assert result[0]["name"] == "nic1"
        assert result[0]["mac"] == "00:11:22:33:44:55"

    def test_list_vnics_vm_not_found(self):
        """Test list NICs when VM does not exist"""
        from ovirt_engine_mcp_server.mcp_extensions import NetworkMCP

        mock_ovirt = MagicMock()
        mock_ovirt._find_vm.return_value = None

        net_mcp = NetworkMCP(mock_ovirt)

        with pytest.raises(ValueError, match="VM not found"):
            net_mcp.list_vnics("nonexistent")

    def test_create_network(self):
        """Test create network"""
        from ovirt_engine_mcp_server.mcp_extensions import NetworkMCP

        mock_dc = MagicMock()
        mock_dc.id = "dc-123"
        mock_network = _create_mock_network()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        mock_ovirt.connection.system_service.return_value.data_centers_service.return_value.list.return_value = [mock_dc]
        mock_ovirt.connection.system_service.return_value.networks_service.return_value.add.return_value = mock_network

        net_mcp = NetworkMCP(mock_ovirt)
        result = net_mcp.create_network("new-net", "Default", vlan="100")

        assert result["success"] is True
        assert "network_id" in result

    def test_create_network_datacenter_not_found(self):
        """Test create network when data center does not exist"""
        from ovirt_engine_mcp_server.mcp_extensions import NetworkMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        mock_ovirt.connection.system_service.return_value.data_centers_service.return_value.list.return_value = []

        net_mcp = NetworkMCP(mock_ovirt)

        with pytest.raises(ValueError, match="Data center not found"):
            net_mcp.create_network("new-net", "Nonexistent")

    def test_update_network(self):
        """Test update network"""
        from ovirt_engine_mcp_server.mcp_extensions import NetworkMCP

        mock_network = _create_mock_network()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        mock_ovirt.connection.system_service.return_value.networks_service.return_value.list.return_value = [mock_network]
        mock_ovirt.connection.system_service.return_value.networks_service.return_value.network_service.return_value.get.return_value = mock_network

        net_mcp = NetworkMCP(mock_ovirt)
        result = net_mcp.update_network("ovirtmgmt", new_name="mgmt-net")

        assert result["success"] is True

    def test_delete_network(self):
        """Test delete network"""
        from ovirt_engine_mcp_server.mcp_extensions import NetworkMCP

        mock_network = _create_mock_network()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        mock_ovirt.connection.system_service.return_value.networks_service.return_value.list.return_value = [mock_network]

        net_mcp = NetworkMCP(mock_ovirt)
        result = net_mcp.delete_network("ovirtmgmt")

        assert result["success"] is True


class TestClusterMCP:
    """Test ClusterMCP class"""

    def test_list_clusters(self):
        """Test list clusters"""
        from ovirt_engine_mcp_server.mcp_extensions import ClusterMCP

        mock_ovirt = MagicMock()
        mock_ovirt.list_clusters.return_value = [
            {"id": "cluster-123", "name": "Default"}
        ]

        cluster_mcp = ClusterMCP(mock_ovirt)
        result = cluster_mcp.list_clusters()

        assert len(result) == 1
        assert result[0]["name"] == "Default"

    def test_get_cluster(self):
        """Test get cluster details"""
        from ovirt_engine_mcp_server.mcp_extensions import ClusterMCP

        mock_cluster = _create_mock_cluster()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        mock_ovirt.connection.system_service.return_value.clusters_service.return_value.list.return_value = [mock_cluster]

        cluster_mcp = ClusterMCP(mock_ovirt)
        result = cluster_mcp.get_cluster("Default")

        assert result is not None
        assert result["name"] == "Default"
        assert "cpu" in result

    def test_get_cluster_not_found(self):
        """Test cluster does not exist"""
        from ovirt_engine_mcp_server.mcp_extensions import ClusterMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        mock_ovirt.connection.system_service.return_value.clusters_service.return_value.list.return_value = []

        cluster_mcp = ClusterMCP(mock_ovirt)
        result = cluster_mcp.get_cluster("Nonexistent")

        assert result is None

    def test_list_cluster_hosts(self):
        """Test list cluster hosts"""
        from ovirt_engine_mcp_server.mcp_extensions import ClusterMCP

        mock_hosts = [{"id": "host-123", "name": "host1"}]

        mock_ovirt = MagicMock()
        mock_ovirt.list_hosts.return_value = mock_hosts

        cluster_mcp = ClusterMCP(mock_ovirt)
        result = cluster_mcp.list_cluster_hosts("Default")

        assert len(result) == 1
        mock_ovirt.list_hosts.assert_called_with(cluster="Default")

    def test_list_cluster_vms(self):
        """Test list cluster VMs"""
        from ovirt_engine_mcp_server.mcp_extensions import ClusterMCP

        mock_vms = [{"id": "vm-123", "name": "vm1"}]

        mock_ovirt = MagicMock()
        mock_ovirt.list_vms.return_value = mock_vms

        cluster_mcp = ClusterMCP(mock_ovirt)
        result = cluster_mcp.list_cluster_vms("Default")

        assert len(result) == 1

    def test_get_cluster_cpu_load(self):
        """Test get cluster CPU load"""
        from ovirt_engine_mcp_server.mcp_extensions import ClusterMCP

        mock_hosts = [
            {"id": "host-1", "name": "host1", "cpu_usage": 30},
            {"id": "host-2", "name": "host2", "cpu_usage": 50},
        ]

        mock_ovirt = MagicMock()
        mock_ovirt.list_hosts.return_value = mock_hosts

        cluster_mcp = ClusterMCP(mock_ovirt)
        result = cluster_mcp.get_cluster_cpu_load("Default")

        assert result["cluster"] == "Default"
        assert result["host_count"] == 2
        assert result["cpu_load_avg"] == 40.0

    def test_get_cluster_cpu_load_empty(self):
        """Test CPU load of an empty cluster"""
        from ovirt_engine_mcp_server.mcp_extensions import ClusterMCP

        mock_ovirt = MagicMock()
        mock_ovirt.list_hosts.return_value = []

        cluster_mcp = ClusterMCP(mock_ovirt)
        result = cluster_mcp.get_cluster_cpu_load("Default")

        assert result["cpu_load"] == 0
        assert result["host_count"] == 0

    def test_get_cluster_memory_usage(self):
        """Test get cluster memory usage"""
        from ovirt_engine_mcp_server.mcp_extensions import ClusterMCP

        mock_hosts = [
            {"id": "host-1", "name": "host1", "memory_gb": 64, "memory_usage": 50},
            {"id": "host-2", "name": "host2", "memory_gb": 64, "memory_usage": 75},
        ]

        mock_ovirt = MagicMock()
        mock_ovirt.list_hosts.return_value = mock_hosts

        cluster_mcp = ClusterMCP(mock_ovirt)
        result = cluster_mcp.get_cluster_memory_usage("Default")

        assert result["cluster"] == "Default"
        assert result["memory_total_gb"] == 128
        assert result["host_count"] == 2


class TestTemplateMCP:
    """Test TemplateMCP class"""

    def test_list_templates(self):
        """Test list templates"""
        from ovirt_engine_mcp_server.mcp_extensions import TemplateMCP

        mock_ovirt = MagicMock()
        mock_ovirt.list_templates.return_value = [
            {"id": "tpl-123", "name": "CentOS8"}
        ]

        tpl_mcp = TemplateMCP(mock_ovirt)
        result = tpl_mcp.list_templates()

        assert len(result) == 1
        assert result[0]["name"] == "CentOS8"

    def test_get_template(self):
        """Test get template details"""
        from ovirt_engine_mcp_server.mcp_extensions import TemplateMCP

        mock_tpl = _create_mock_template()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        mock_ovirt.connection.system_service.return_value.templates_service.return_value.list.return_value = [mock_tpl]

        tpl_mcp = TemplateMCP(mock_ovirt)
        result = tpl_mcp.get_template("CentOS8")

        assert result is not None
        assert result["name"] == "CentOS8"
        assert result["cpu_cores"] == 2

    def test_get_template_not_found(self):
        """Test template does not exist"""
        from ovirt_engine_mcp_server.mcp_extensions import TemplateMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        mock_ovirt.connection.system_service.return_value.templates_service.return_value.list.return_value = []

        tpl_mcp = TemplateMCP(mock_ovirt)
        result = tpl_mcp.get_template("Nonexistent")

        assert result is None

    def test_create_vm_from_template(self):
        """Test create VM from template"""
        from ovirt_engine_mcp_server.mcp_extensions import TemplateMCP

        mock_ovirt = MagicMock()
        mock_ovirt.create_vm.return_value = {
            "success": True,
            "vm_id": "vm-123"
        }

        tpl_mcp = TemplateMCP(mock_ovirt)
        result = tpl_mcp.create_vm_from_template(
            name="new-vm",
            template="CentOS8",
            cluster="Default",
            memory_mb=8192,
            cpu_cores=4
        )

        assert result["success"] is True
        mock_ovirt.create_vm.assert_called_with(
            name="new-vm",
            cluster="Default",
            memory_mb=8192,
            cpu_cores=4,
            template="CentOS8"
        )


class TestMCPExtensionsTools:
    """Test MCP_TOOLS registry"""

    def test_mcp_tools_defined(self):
        """Test MCP tool registry is defined"""
        from ovirt_engine_mcp_server.mcp_extensions import MCP_TOOLS

        expected_tools = [
            "vm_list",
            "vm_get",
            "vm_create",
            "vm_delete",
            "vm_start",
            "vm_stop",
            "vm_restart",
            "snapshot_list",
            "snapshot_create",
            "snapshot_restore",
            "snapshot_delete",
            "disk_list",
            "disk_create",
            "disk_attach",
            "network_list",
            "nic_list",
            "nic_add",
            "nic_remove",
            "host_list",
            "cluster_list",
            "template_list",
        ]

        for tool in expected_tools:
            assert tool in MCP_TOOLS, f"Missing tool: {tool}"
            assert "method" in MCP_TOOLS[tool]
            assert "description" in MCP_TOOLS[tool]


class TestVnicProfileLiveAttributes:
    """``VnicPassThrough`` exposes ``.mode``, not a bare ``.value``."""

    @staticmethod
    def _profile(pass_through):
        return SimpleNamespace(
            id="vnic-1",
            name="ovirtmgmt",
            description=None,
            network=SimpleNamespace(name="ovirtmgmt", id="net-1"),
            pass_through=pass_through,
            port_mirroring=[],
            custom_properties=[],
        )

    @staticmethod
    def _mock_ovirt(profile):
        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        profiles_service = mock_ovirt.connection.system_service.return_value.vnic_profiles_service.return_value
        profiles_service.list.return_value = [profile]
        return mock_ovirt

    def test_list_vnic_profiles_uses_pass_through_mode(self):
        from ovirt_engine_mcp_server.mcp_extensions import NetworkMCP

        profile = self._profile(SimpleNamespace(mode=SimpleNamespace(value="disabled")))
        mock_ovirt = self._mock_ovirt(profile)

        result = NetworkMCP(mock_ovirt).list_vnic_profiles()

        assert result[0]["pass_through"] == "disabled"

    def test_list_vnic_profiles_handles_absent_pass_through(self):
        from ovirt_engine_mcp_server.mcp_extensions import NetworkMCP

        mock_ovirt = self._mock_ovirt(self._profile(None))

        result = NetworkMCP(mock_ovirt).list_vnic_profiles()

        assert result[0]["pass_through"] == "disabled"

    def test_get_vnic_profile_uses_pass_through_mode(self):
        from ovirt_engine_mcp_server.mcp_extensions import NetworkMCP

        profile = self._profile(SimpleNamespace(mode=SimpleNamespace(value="enabled")))
        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        profiles_service = mock_ovirt.connection.system_service.return_value.vnic_profiles_service.return_value
        profiles_service.profile_service.return_value.get.side_effect = Exception("404")
        profiles_service.list.return_value = [profile]

        result = NetworkMCP(mock_ovirt).get_vnic_profile("ovirtmgmt")

        assert result is not None
        assert result["pass_through"] == "enabled"


class TestClusterCpuFormatting:
    """Cluster CPU output must use ASCII keys and tolerate a missing arch."""

    @staticmethod
    def _cluster(architecture=..., cpu_name=None):
        cluster = _create_mock_cluster()
        if architecture is not ...:
            cluster.cpu.architecture = architecture
        cluster.cpu.name = cpu_name
        return cluster

    @staticmethod
    def _mcp_for(cluster):
        from ovirt_engine_mcp_server.mcp_extensions import ClusterMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        clusters = mock_ovirt.connection.system_service.return_value.clusters_service.return_value
        clusters.list.return_value = [cluster]
        return ClusterMCP(mock_ovirt)

    def test_get_cluster_uses_ascii_model_key(self):
        cluster = self._cluster(cpu_name=None)

        result = self._mcp_for(cluster).get_cluster("Default")

        assert all(str(key).isascii() for key in result["cpu"])
        assert result["cpu"]["model"] == ""
        assert result["cpu"]["architecture"] == "x86_64"

    def test_get_cluster_handles_missing_architecture(self):
        cluster = self._cluster(architecture=None)

        result = self._mcp_for(cluster).get_cluster("Default")

        assert result["cpu_architecture"] == "x86_64"
        assert result["cpu"]["architecture"] == "x86_64"


class TestDataCenterScopedQos:
    """QoS is served by the data center; SystemService has no `qoss_service`."""

    @staticmethod
    def _qos():
        return SimpleNamespace(
            id="qos-1",
            name="qos-high-throughput",
            description="hb",
            data_center=SimpleNamespace(id="dc-77", name="Default"),
            type_=SimpleNamespace(value="host"),
            max_inbound=12345,
            max_outbound=54321,
        )

    @staticmethod
    def _mcp(qos_list, dcs=...):
        from ovirt_engine_mcp_server.mcp_extensions import NetworkMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        dcs_service = (
            mock_ovirt.connection.system_service.return_value
            .data_centers_service.return_value
        )
        dcs_service.list.return_value = (
            [SimpleNamespace(id="dc-77", name="Default")] if dcs is ... else dcs
        )
        dcs_service.data_center_service.return_value.qoss_service.return_value.list.return_value = qos_list
        return mock_ovirt, NetworkMCP(mock_ovirt)

    def test_qos_list_reads_data_center_service(self):
        mock_ovirt, mcp = self._mcp([self._qos()])

        result = mcp.list_qos()

        assert len(result) == 1
        assert result[0]["name"] == "qos-high-throughput"
        assert result[0]["datacenter"] == "Default"
        assert result[0]["type"] == "host"
        assert result[0]["max_inbound"] == 12345
        assert result[0]["max_outbound"] == 54321
        # the system-level lookup that used to crash must not be attempted
        mock_ovirt.connection.system_service.return_value.qoss_service.assert_not_called()

    def test_qos_list_unknown_datacenter_raises(self):
        with pytest.raises(ValueError, match="Data center not found"):
            self._mcp([], dcs=[])[1].list_qos("no-such-dc")


class TestNetworkFilterVersionFormatting:
    """`Version` is a struct — raw objects leaked into tool output."""

    @staticmethod
    def _mcp(filters):
        from ovirt_engine_mcp_server.mcp_extensions import NetworkMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        filters_service = (
            mock_ovirt.connection.system_service.return_value
            .network_filters_service.return_value
        )
        filters_service.list.return_value = filters
        return NetworkMCP(mock_ovirt)

    def test_version_is_plain_text(self):
        result = self._mcp([
            SimpleNamespace(
                id="f-1",
                name="allow-arp",
                version=SimpleNamespace(full_version="3.2", major=3, minor=2),
            ),
            SimpleNamespace(id="f-2", name="legacy", version=None),
        ]).list_network_filters()

        assert [row["version"] for row in result] == ["3.2", ""]
        assert "object at 0x" not in str(result)

    def test_missing_version_attribute(self):
        result = self._mcp([SimpleNamespace(id="f-3", name="no-version")]).list_network_filters()

        assert result[0]["version"] == ""


class TestVnicProfileItemAccessor:
    """`VnicProfilesService.profile_service` is the item accessor."""

    @staticmethod
    def _mcp(profile):
        from ovirt_engine_mcp_server.mcp_extensions import NetworkMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        profiles = (
            mock_ovirt.connection.system_service.return_value
            .vnic_profiles_service.return_value
        )
        profiles.profile_service.return_value.get.return_value = profile
        return NetworkMCP(mock_ovirt), profiles

    def test_update_uses_profile_service(self):
        profile = SimpleNamespace(
            id="vnic-1", name="ovirtmgmt", description=None, port_mirroring=False
        )
        mcp, profiles = self._mcp(profile)

        mcp.update_vnic_profile("vnic-1", new_name="renamed-profile")

        profiles.profile_service.assert_called_once_with("vnic-1")
        profiles.profile_service.return_value.update.assert_called_once()
        profiles.vnic_profile_service.assert_not_called()
        assert profile.name == "renamed-profile"
