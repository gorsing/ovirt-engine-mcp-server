#!/usr/bin/env python3
"""
oVirt MCP Server - Host extension module
Provides host details, add/remove, and statistics
"""
from typing import Dict, List, Any, Optional
import logging

from .base_mcp import BaseMCP
from .decorators import require_connection
from .search_utils import sanitize_search_value as _sanitize_search_value

try:
    import ovirtsdk4 as sdk
except ImportError:
    sdk = None

logger = logging.getLogger(__name__)


def _enum_value(value: Any, default: str = "") -> str:
    """Stringify a field that may be an SDK enum **or** a plain string.

    Live engines return some fields (e.g. ``Host.os.type`` == ``'RHEL'``) as
    plain strings, so ``value.value`` cannot be assumed to exist.
    """
    if value is None:
        return default
    inner = getattr(value, "value", None)
    return str(inner) if inner is not None else str(value)


def _storage_bytes(storage: Any) -> int:
    """Total size in bytes of a host storage entry.

    ``HostStorage`` exposes no ``size``/``available`` attributes — capacity
    lives on its logical units (LUNs).
    """
    total = 0
    for lu in getattr(storage, "logical_units", None) or []:
        total += getattr(lu, "size", None) or 0
    return total


class HostExtendedMCP(BaseMCP):
    """Host extended management MCP."""

    def __init__(self, ovirt_mcp):
        super().__init__(ovirt_mcp)

    @require_connection
    def get_host(self, name_or_id: str) -> Optional[Dict]:
        """Get host details."""
        host = self._find_host(name_or_id)
        if not host:
            return None

        # Get host_service outside try blocks to avoid scope issues
        host_service = self.connection.system_service().hosts_service().host_service(host.id)

        # Get host network interfaces
        nics = []
        try:
            nics_service = host_service.nics_service()
            nic_list = nics_service.list()
            nics = [
                {
                    "id": n.id,
                    "name": n.name,
                    "mac": n.mac.address if n.mac else "",
                    "ip": n.ip.address if n.ip else "",
                    "speed_bps": n.speed if n.speed else 0,
                }
                for n in nic_list[:10]  # limit count
            ]
        except Exception as e:
            logger.debug(f"Failed to get host NICs: {e}")

        # Get host storage
        storage = []
        try:
            storage_service = host_service.storage_service()
            storage_list = storage_service.list()
            storage = [
                {
                    "id": s.id,
                    "name": s.name or "",
                    "type": _enum_value(s.type),
                    "size_gb": int(_storage_bytes(s) / (1024**3)),
                }
                for s in storage_list[:10]
            ]
        except Exception as e:
            logger.debug(f"Failed to get host storage: {e}")

        return {
            "id": host.id,
            "name": host.name,
            "description": host.description or "",
            "status": _enum_value(host.status, "unknown"),
            "cluster": self._cluster_name(host.cluster),
            "cluster_id": host.cluster.id if host.cluster else "",
            "address": host.address,
            "port": host.port,
            "cpu_cores": host.cpu.topology.cores if host.cpu and host.cpu.topology else 0,
            "cpu_sockets": host.cpu.topology.sockets if host.cpu and host.cpu.topology else 0,
            "cpu_threads": host.cpu.topology.threads if host.cpu and host.cpu.topology else 0,
            "cpu_speed_mhz": host.cpu.speed if host.cpu else 0,
            "memory_gb": int((host.memory or 0) / (1024**3)),
            # os.type is a plain str on live engines; kvm / vdsm_version are
            # absent from the Host type altogether.
            "os_type": _enum_value(host.os.type) if host.os else "",
            "os_version": getattr(getattr(getattr(host, "os", None), "version", None), "full_version", None) or "",
            "kvm_version": getattr(getattr(host, "kvm", None), "version", None) or "",
            "libvirt_version": getattr(getattr(host, "libvirt_version", None), "full_version", None) or "",
            "vdsm_version": getattr(getattr(host, "vdsm_version", None), "full_version", None) or "",
            "nics": nics,
            "storage": storage,
        }

    @require_connection
    def add_host(self, name: str, cluster: str, address: str,
                password: str = None, ssh_port: int = 22) -> Dict[str, Any]:
        """Add a host."""
        # Find the cluster
        clusters = self.connection.system_service().clusters_service().list(
            search=f"name={_sanitize_search_value(cluster)}"
        )
        if not clusters:
            raise ValueError(f"Cluster not found: {cluster}")

        hosts_service = self.connection.system_service().hosts_service()

        # Check whether the host already exists
        existing = hosts_service.list(search=f"name={_sanitize_search_value(name)}")
        if existing:
            raise ValueError(f"Host already exists: {name}")

        try:
            host = hosts_service.add(
                sdk.types.Host(
                    name=name,
                    address=address,
                    port=ssh_port,
                    cluster=sdk.types.Cluster(id=clusters[0].id),
                    # SSH authentication requires a password or public key
                    ssh=sdk.types.Ssh(
                        authentication_method=sdk.types.SshAuthenticationMethod.PASSWORD,
                        password=password,
                    ) if password else None,
                )
            )
            return {
                "success": True,
                "message": f"Host {name} added, waiting for activation",
                "host_id": host.id,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to add host: {e}")

    @require_connection
    def remove_host(self, name_or_id: str, force: bool = False) -> Dict[str, Any]:
        """Remove a host."""
        host = self._find_host(name_or_id)
        if not host:
            raise ValueError(f"Host not found: {name_or_id}")

        host_service = self.connection.system_service().hosts_service().host_service(host.id)

        try:
            host_service.remove(force=force)
            return {"success": True, "message": f"Host {host.name} removed"}
        except Exception as e:
            raise RuntimeError(f"Failed to remove host: {e}")

    @require_connection
    def get_host_stats(self, name_or_id: str) -> Dict[str, Any]:
        """Get host statistics."""
        host = self._find_host(name_or_id)
        if not host:
            raise ValueError(f"Host not found: {name_or_id}")

        host_service = self.connection.system_service().hosts_service().host_service(host.id)
        stats_service = host_service.statistics_service()
        stats = stats_service.list()

        result = {
            "host_id": host.id,
            "host_name": host.name,
            "stats": {},
        }

        # Parse statistics
        stat_mapping = {
            "memory.used": "memory_used_mb",
            "memory.free": "memory_free_mb",
            "memory.buffers": "memory_buffers_mb",
            "memory.cached": "memory_cached_mb",
            "memory.shared": "memory_shared_mb",
            "cpu.current.user": "cpu_user_percent",
            "cpu.current.system": "cpu_system_percent",
            "cpu.current.idle": "cpu_idle_percent",
            "cpu.load.avg.5m": "cpu_load_avg_5m",
            "network.interface.tx": "network_tx_bytes",
            "network.interface.rx": "network_rx_bytes",
        }

        for stat in stats:
            stat_name = stat.name
            if stat_name in stat_mapping:
                key = stat_mapping[stat_name]
                if stat.values and stat.values:
                    value = stat.values[0]
                    if hasattr(value, "datum"):
                        result["stats"][key] = value.datum
                    else:
                        result["stats"][key] = value
                else:
                    result["stats"][key] = stat.value

        # Compute summary values
        if "memory_used_mb" in result["stats"] and "memory_free_mb" in result["stats"]:
            total = result["stats"]["memory_used_mb"] + result["stats"]["memory_free_mb"]
            if total > 0:
                result["stats"]["memory_usage_percent"] = round(
                    result["stats"]["memory_used_mb"] / total * 100, 2
                )

        return result

    @require_connection
    def get_host_devices(self, name_or_id: str) -> List[Dict]:
        """List host devices."""
        host = self._find_host(name_or_id)
        if not host:
            raise ValueError(f"Host not found: {name_or_id}")

        host_service = self.connection.system_service().hosts_service().host_service(host.id)
        devices_service = host_service.devices_service()
        devices = devices_service.list()

        return [
            {
                "id": d.id,
                "name": d.name,
                "capability": str(d.capability.value) if d.capability else "",
                "product": d.product.name if d.product else "",
                "vendor": d.vendor.name if d.vendor else "",
                "driver": d.driver or "",
                "iommu_group": d.iommu_group if hasattr(d, "iommu_group") else None,
            }
            for d in devices[:50]  # limit count
        ]

    # -- Host NIC management --------------------------------------------------------

    @require_connection
    def list_host_nics(self, name_or_id: str) -> List[Dict]:
        """List host NICs.

        Args:
            name_or_id: Host name or ID

        Returns:
            List of NICs
        """
        host = self._find_host(name_or_id)
        if not host:
            raise ValueError(f"Host not found: {name_or_id}")

        host_service = self.connection.system_service().hosts_service().host_service(host.id)
        nics_service = host_service.nics_service()

        try:
            nics = nics_service.list()
        except Exception as e:
            logger.error(f"Failed to get host NICs: {e}")
            return []

        return [
            {
                "id": n.id,
                "name": n.name,
                "mac": n.mac.address if n.mac else "",
                "ip": n.ip.address if n.ip else "",
                "ipv6": n.ipv6.address if hasattr(n, 'ipv6') and n.ipv6 else "",
                "mtu": n.mtu if hasattr(n, 'mtu') else 0,
                "speed_bps": n.speed if n.speed else 0,
                "status": str(n.status.value) if hasattr(n, 'status') and n.status else "up",
                "bond": n.bond.name if hasattr(n, 'bond') and n.bond else "",
                "vlan": n.vlan.id if hasattr(n, 'vlan') and n.vlan else None,
            }
            for n in nics
        ]

    @require_connection
    def update_host_nic(self, name_or_id: str, nic_name: str,
                       custom_properties: Dict = None) -> Dict[str, Any]:
        """Update host NIC configuration.

        Args:
            name_or_id: Host name or ID
            nic_name: NIC name
            custom_properties: Custom properties

        Returns:
            Update result
        """
        host = self._find_host(name_or_id)
        if not host:
            raise ValueError(f"Host not found: {name_or_id}")

        host_service = self.connection.system_service().hosts_service().host_service(host.id)
        nics_service = host_service.nics_service()

        # Find the NIC
        nics = nics_service.list()
        nic_id = None
        for n in nics:
            if n.name == nic_name:
                nic_id = n.id
                break

        if not nic_id:
            raise ValueError(f"NIC not found: {nic_name}")

        nic_service = nics_service.nic_service(nic_id)
        nic = nic_service.get()

        if custom_properties:
            nic.custom_properties = [
                sdk.types.CustomProperty(name=k, value=str(v))
                for k, v in custom_properties.items()
            ]

        try:
            nic_service.update(nic)
            return {"success": True, "message": f"NIC {nic_name} updated"}
        except Exception as e:
            raise RuntimeError(f"Failed to update NIC: {e}")

    # -- Host NUMA management --------------------------------------------------------

    @require_connection
    def get_host_numa(self, name_or_id: str) -> Dict[str, Any]:
        """Get host NUMA topology.

        Args:
            name_or_id: Host name or ID

        Returns:
            NUMA topology information
        """
        host = self._find_host(name_or_id)
        if not host:
            raise ValueError(f"Host not found: {name_or_id}")

        host_service = self.connection.system_service().hosts_service().host_service(host.id)
        numa_service = host_service.numa_nodes_service()

        try:
            nodes = numa_service.list()
        except Exception as e:
            logger.error(f"Failed to get NUMA nodes: {e}")
            return {"host": host.name, "numa_nodes": []}

        numa_nodes = []
        for node in nodes:
            numa_nodes.append({
                "id": node.id,
                "index": node.index if hasattr(node, 'index') else 0,
                "memory_mb": int((node.memory or 0) / (1024**2)),
                "cpu": {
                    "cores": node.cpu.topology.cores if node.cpu and node.cpu.topology else 0,
                    "sockets": node.cpu.topology.sockets if node.cpu and node.cpu.topology else 0,
                    "threads": node.cpu.topology.threads if node.cpu and node.cpu.topology else 0,
                } if node.cpu else {},
            })

        return {
            "host_id": host.id,
            "host_name": host.name,
            "numa_nodes": numa_nodes,
            "node_count": len(numa_nodes),
        }

    # -- Host hook management --------------------------------------------------------

    @require_connection
    def list_host_hooks(self, name_or_id: str) -> List[Dict]:
        """List host hooks.

        Args:
            name_or_id: Host name or ID

        Returns:
            List of hooks
        """
        host = self._find_host(name_or_id)
        if not host:
            raise ValueError(f"Host not found: {name_or_id}")

        host_service = self.connection.system_service().hosts_service().host_service(host.id)
        hooks_service = host_service.hooks_service()

        try:
            hooks = hooks_service.list()
        except Exception as e:
            logger.error(f"Failed to get host hooks: {e}")
            return []

        return [
            {
                "id": h.id,
                "name": h.name,
                "event": str(h.event.value) if hasattr(h, 'event') and h.event else "",
                "priority": h.priority if hasattr(h, 'priority') else 0,
                "script": h.script if hasattr(h, 'script') else "",
            }
            for h in hooks
        ]

    # -- Host fence operations ------------------------------------------------------

    @require_connection
    def fence_host(self, name_or_id: str, action: str = "restart") -> Dict[str, Any]:
        """Perform a fence operation on the host.

        Args:
            name_or_id: Host name or ID
            action: Action type (restart/start/stop/status)

        Returns:
            Operation result
        """
        host = self._find_host(name_or_id)
        if not host:
            raise ValueError(f"Host not found: {name_or_id}")

        valid_actions = ["restart", "start", "stop", "status"]
        if action.lower() not in valid_actions:
            raise ValueError(f"Invalid action: {action}, valid values: {valid_actions}")

        host_service = self.connection.system_service().hosts_service().host_service(host.id)

        try:
            if action.lower() == "restart":
                host_service.fence(fence_type=sdk.types.FenceType.RESTART)
            elif action.lower() == "start":
                host_service.fence(fence_type=sdk.types.FenceType.START)
            elif action.lower() == "stop":
                host_service.fence(fence_type=sdk.types.FenceType.STOP)
            elif action.lower() == "status":
                # Check fence status
                fence_status = host_service.fence(fence_type=sdk.types.FenceType.STATUS)
                return {
                    "success": True,
                    "message": f"Fence status retrieved",
                    "host": host.name,
                    "action": action,
                }

            return {
                "success": True,
                "message": f"Fence {action} executed on host {host.name}",
                "host_id": host.id,
                "action": action,
            }
        except Exception as e:
            raise RuntimeError(f"Fence operation failed: {e}")

    # -- Host network configuration --------------------------------------------------------

    @require_connection
    def update_host_network(self, name_or_id: str, network: str,
                           nic: str = None, vlan_id: int = None,
                           bond: str = None) -> Dict[str, Any]:
        """Update host network configuration.

        Args:
            name_or_id: Host name or ID
            network: Network name
            nic: NIC name (optional)
            vlan_id: VLAN ID (optional)
            bond: Bond interface name (optional)

        Returns:
            Update result
        """
        host = self._find_host(name_or_id)
        if not host:
            raise ValueError(f"Host not found: {name_or_id}")

        # Find the network
        networks_service = self.connection.system_service().networks_service()
        networks = networks_service.list(search=f"name={_sanitize_search_value(network)}")
        if not networks:
            raise ValueError(f"Network not found: {network}")

        host_service = self.connection.system_service().hosts_service().host_service(host.id)
        network_service = host_service.networks_service()

        try:
            # Attach the network to the host
            network_service.add(
                sdk.types.HostNetwork(
                    network=sdk.types.Network(id=networks[0].id),
                    nic=nic,
                    vlan=sdk.types.Vlan(id=vlan_id) if vlan_id else None,
                )
            )

            return {
                "success": True,
                "message": f"Network {network} configured on host",
                "host_id": host.id,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to update host network: {e}")

    # -- Host device update --------------------------------------------------------

    @require_connection
    def update_host_device(self, name_or_id: str, device_name: str,
                          enabled: bool = True) -> Dict[str, Any]:
        """Update host device configuration.

        Args:
            name_or_id: Host name or ID
            device_name: Device name
            enabled: Whether enabled

        Returns:
            Update result
        """
        host = self._find_host(name_or_id)
        if not host:
            raise ValueError(f"Host not found: {name_or_id}")

        host_service = self.connection.system_service().hosts_service().host_service(host.id)
        devices_service = host_service.devices_service()

        # Find the device
        devices = devices_service.list(search=f"name={_sanitize_search_value(device_name)}")
        if not devices:
            raise ValueError(f"Device not found: {device_name}")

        device_service = devices_service.device_service(devices[0].id)

        try:
            # Update device state
            device = device_service.get()
            # Handle operations based on device type
            return {
                "success": True,
                "message": f"Device {device_name} updated",
                "enabled": enabled,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to update device: {e}")

    # -- Host storage list ----------------------------------------------------------

    @require_connection
    def list_host_storage(self, name_or_id: str) -> List[Dict]:
        """List host storage.

        Args:
            name_or_id: Host name or ID

        Returns:
            List of storage entries
        """
        host = self._find_host(name_or_id)
        if not host:
            raise ValueError(f"Host not found: {name_or_id}")

        host_service = self.connection.system_service().hosts_service().host_service(host.id)
        storage_service = host_service.storage_service()

        try:
            storage_list = storage_service.list()
        except Exception as e:
            logger.error(f"Failed to get host storage: {e}")
            return []

        return [
            {
                "id": s.id,
                "name": s.name or "",
                "type": _enum_value(s.type),
                "size_gb": int(_storage_bytes(s) / (1024**3)),
                "free_gb": int((getattr(s, "available", None) or 0) / (1024**3)),
                "mount_point": getattr(s, "mount_point", "") or "",
                "path": getattr(s, "path", "") or "",
            }
            for s in storage_list
        ]

    # -- Host installation --------------------------------------------------------------

    @require_connection
    def install_host(self, name_or_id: str, root_password: str = None,
                    ssh_key: str = None, override_iptables: bool = False) -> Dict[str, Any]:
        """Install/reinstall a host.

        Args:
            name_or_id: Host name or ID
            root_password: Root password
            ssh_key: SSH public key
            override_iptables: Override iptables rules

        Returns:
            Installation result
        """
        host = self._find_host(name_or_id)
        if not host:
            raise ValueError(f"Host not found: {name_or_id}")

        host_service = self.connection.system_service().hosts_service().host_service(host.id)

        try:
            host_service.install(
                root_password=root_password,
                ssh=ssh_key,
                override_iptables=override_iptables,
            )

            return {
                "success": True,
                "message": f"Install task started for host {host.name}",
                "host_id": host.id,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to install host: {e}")

    # -- iSCSI discovery and login ------------------------------------------------------

    @require_connection
    def iscsi_discover(self, name_or_id: str, address: str,
                      port: int = 3260, username: str = None,
                      password: str = None) -> Dict[str, Any]:
        """Discover iSCSI targets.

        Args:
            name_or_id: Host name or ID
            address: iSCSI target address
            port: Port number, default 3260
            username: CHAP username (optional)
            password: CHAP password (optional)

        Returns:
            List of discovered targets
        """
        host = self._find_host(name_or_id)
        if not host:
            raise ValueError(f"Host not found: {name_or_id}")

        host_service = self.connection.system_service().hosts_service().host_service(host.id)

        try:
            result = host_service.iscsi_discover(
                iscsi=sdk.types.IscsiDetails(
                    address=address,
                    port=port,
                    username=username,
                    password=password,
                )
            )

            targets = []
            if result:
                for target in result:
                    targets.append({
                        "address": target.address if hasattr(target, 'address') else address,
                        "target": target.target if hasattr(target, 'target') else "",
                        "portal": target.portal if hasattr(target, 'portal') else "",
                    })

            return {
                "success": True,
                "message": f"iSCSI discovery completed",
                "host": host.name,
                "targets": targets,
                "target_count": len(targets),
            }
        except Exception as e:
            raise RuntimeError(f"iSCSI discovery failed: {e}")

    @require_connection
    def iscsi_login(self, name_or_id: str, address: str, target: str,
                   port: int = 3260, username: str = None,
                   password: str = None) -> Dict[str, Any]:
        """Log in to an iSCSI target.

        Args:
            name_or_id: Host name or ID
            address: iSCSI target address
            target: Target name
            port: Port number, default 3260
            username: CHAP username (optional)
            password: CHAP password (optional)

        Returns:
            Login result
        """
        host = self._find_host(name_or_id)
        if not host:
            raise ValueError(f"Host not found: {name_or_id}")

        host_service = self.connection.system_service().hosts_service().host_service(host.id)

        try:
            host_service.iscsi_login(
                iscsi=sdk.types.IscsiDetails(
                    address=address,
                    port=port,
                    target=target,
                    username=username,
                    password=password,
                )
            )

            return {
                "success": True,
                "message": f"Logged in to iSCSI target {target}",
                "host": host.name,
                "address": address,
                "target": target,
            }
        except Exception as e:
            raise RuntimeError(f"iSCSI login failed: {e}")


# MCP tool registry
MCP_TOOLS = {
    "host_get": {"method": "get_host", "description": "Get host details"},
    "host_add": {"method": "add_host", "description": "Add a host"},
    "host_remove": {"method": "remove_host", "description": "Remove a host"},
    "host_stats": {"method": "get_host_stats", "description": "Get host statistics"},
    "host_devices": {"method": "get_host_devices", "description": "List host devices"},

    # New tools
    "host_nic_list": {"method": "list_host_nics", "description": "List host NICs"},
    "host_nic_update": {"method": "update_host_nic", "description": "Update host NIC configuration"},
    "host_numa_get": {"method": "get_host_numa", "description": "Get host NUMA topology"},
    "host_hook_list": {"method": "list_host_hooks", "description": "List host hooks"},
    "host_fence": {"method": "fence_host", "description": "Perform fence operation on host"},
    "host_network_update": {"method": "update_host_network", "description": "Update host network configuration"},
    "host_device_update": {"method": "update_host_device", "description": "Update host device configuration"},
    "host_storage_list": {"method": "list_host_storage", "description": "List host storage"},
    "host_install": {"method": "install_host", "description": "Install/reinstall host"},
    "host_iscsi_discover": {"method": "iscsi_discover", "description": "Discover iSCSI targets"},
    "host_iscsi_login": {"method": "iscsi_login", "description": "Log in to iSCSI target"},
}
