#!/usr/bin/env python3
"""
Ovirt MCP Server - network and cluster extension module
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


class NetworkMCP(BaseMCP):
    """Network management MCP"""

    def __init__(self, ovirt_mcp):
        super().__init__(ovirt_mcp)

    def list_networks(self, cluster: str = None, datacenter: str = None) -> List[Dict]:
        """List networks"""
        return self.ovirt.list_networks(cluster)

    @require_connection
    def get_network(self, name_or_id: str) -> Optional[Dict]:
        """Get network details

        Args:
            name_or_id: Network name or ID

        Returns:
            Network details
        """
        network = self._find_network(name_or_id)
        if not network:
            return None

        return {
            "id": network.id,
            "name": network.name,
            "description": network.description or "",
            "data_center": self._data_center_name(network.data_center),
            "data_center_id": network.data_center.id if network.data_center else "",
            "vlan_id": network.vlan.id if network.vlan else None,
            "mtu": network.mtu if hasattr(network, 'mtu') else 0,
            "stp": network.stp if hasattr(network, 'stp') else False,
            "usages": [str(u.value) for u in network.usages] if network.usages else [],
        }

    @require_connection
    def list_vnics(self, name_or_id: str) -> List[Dict]:
        """List VM NICs"""
        vm = self.ovirt._find_vm(name_or_id)
        if not vm: raise ValueError(f"VM not found: {name_or_id}")

        nics_service = self.connection.system_service().vms_service().vm_service(vm["id"]).nics_service()
        nics = nics_service.list()

        return [
            {
                "id": n.id,
                "name": n.name,
                "mac": n.mac.address if n.mac else "",
                "network": self._network_name(n.network),
                "interface": str(n.interface.value) if n.interface else "virtio",
                "linked": n.linked
            }
            for n in nics
        ]

    @require_connection
    def add_nic(self, name_or_id: str, nic_name: str, network: str,
               interface: str = "virtio") -> Dict[str, Any]:
        """Add NIC"""
        vm = self.ovirt._find_vm(name_or_id)
        if not vm:
            raise ValueError(f"VM not found: {name_or_id}")

        # Find the network
        net = self._find_network(network)

        nics_service = self.connection.system_service().vms_service().vm_service(vm["id"]).nics_service()

        try:
            nic = nics_service.add(
                sdk.types.Nic(
                    name=nic_name,
                    interface=sdk.types.NicInterface(interface),
                    network=sdk.types.Network(id=net.id) if net else None,
                )
            )
            return {"success": True, "message": f"NIC {nic_name} added", "nic_id": nic.id}
        except Exception as e:
            raise RuntimeError(f"Failed to add NIC: {e}")

    @require_connection
    def remove_nic(self, name_or_id: str, nic_name: str) -> Dict[str, Any]:
        """Remove NIC"""
        vm = self.ovirt._find_vm(name_or_id)
        if not vm:
            raise ValueError(f"VM not found: {name_or_id}")

        nics_service = self.connection.system_service().vms_service().vm_service(vm["id"]).nics_service()
        nics = nics_service.list()

        nic_id = None
        for n in nics:
            if n.name == nic_name:
                nic_id = n.id
                break

        if not nic_id:
            raise ValueError(f"NIC not found: {nic_name}")

        nics_service.nic_service(nic_id).remove()
        return {"success": True, "message": f"NIC {nic_name} removed"}

    @require_connection
    def create_network(self, name: str, datacenter: str, vlan: str = None,
                      description: str = "", mtu: int = 0) -> Dict[str, Any]:
        """Create network"""
        # Get data center
        dcs = self.connection.system_service().data_centers_service().list(search=f"name={_sanitize_search_value(datacenter)}")
        if not dcs: raise ValueError(f"Data center not found: {datacenter}")

        # Create the network
        network = self.connection.system_service().networks_service().add(
            sdk.types.Network(
                name=name,
                description=description,
                data_center=sdk.types.DataCenter(id=dcs[0].id),
                vlan=sdk.types.Vlan(id=int(vlan)) if vlan else None,
                mtu=mtu if mtu > 0 else None,
            )
        )

        return {"success": True, "message": f"Network {name} created", "network_id": network.id}

    @require_connection
    def update_network(self, name: str, new_name: str = None, description: str = None,
                      mtu: int = None) -> Dict[str, Any]:
        """Update network"""
        networks = self.connection.system_service().networks_service().list(search=f"name={_sanitize_search_value(name)}")
        if not networks: raise ValueError(f"Network not found: {name}")

        network_service = self.connection.system_service().networks_service().network_service(networks[0].id)
        network = network_service.get()

        if new_name:
            network.name = new_name
        if description is not None:
            network.description = description
        if mtu is not None:
            network.mtu = mtu

        network_service.update(network)

        return {"success": True, "message": f"Network updated"}

    @require_connection
    def delete_network(self, name: str) -> Dict[str, Any]:
        """Delete network"""
        networks = self.connection.system_service().networks_service().list(search=f"name={_sanitize_search_value(name)}")
        if not networks: raise ValueError(f"Network not found: {name}")

        self.connection.system_service().networks_service().network_service(networks[0].id).remove()

        return {"success": True, "message": f"Network {name} deleted"}

    # -- VNIC Profile management --------------------------------------------------

    @require_connection
    def list_vnic_profiles(self, network: str = None) -> List[Dict]:
        """List VNIC profiles

        Args:
            network: Network name (optional)

        Returns:
            List of VNIC profiles
        """
        profiles_service = self.connection.system_service().vnic_profiles_service()

        search = None
        if network:
            search = f"network={_sanitize_search_value(network)}"

        try:
            profiles = profiles_service.list(search=search)
        except Exception as e:
            logger.error(f"Failed to list VNIC profiles: {e}")
            return []

        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description or "",
                "network": self._network_name(p.network),
                "network_id": p.network.id if p.network else "",
                # pass_through is a VnicPassThrough object exposing `.mode`,
                # not a bare enum with `.value`.
                "pass_through": (
                    str(p.pass_through.mode.value)
                    if getattr(p, "pass_through", None) is not None
                    and getattr(p.pass_through, "mode", None) is not None
                    else "disabled"
                ),
                "port_mirroring": p.port_mirroring if hasattr(p, 'port_mirroring') else False,
            }
            for p in profiles
        ]

    @require_connection
    def get_vnic_profile(self, name_or_id: str) -> Optional[Dict]:
        """Get VNIC profile details

        Args:
            name_or_id: Profile name or ID

        Returns:
            Profile details
        """
        profiles_service = self.connection.system_service().vnic_profiles_service()

        try:
            profile = profiles_service.profile_service(name_or_id).get()
            if profile:
                return self._format_vnic_profile(profile)
        except Exception:
            pass

        profiles = profiles_service.list(search=f"name={_sanitize_search_value(name_or_id)}")
        if not profiles:
            return None

        return self._format_vnic_profile(profiles[0])

    def _format_vnic_profile(self, profile) -> Dict:
        """Format VNIC profile"""
        return {
            "id": profile.id,
            "name": profile.name,
            "description": profile.description or "",
            "network": self._network_name(profile.network),
            "network_id": profile.network.id if profile.network else "",
            "pass_through": (
                str(profile.pass_through.mode.value)
                if getattr(profile, "pass_through", None) is not None
                and getattr(profile.pass_through, "mode", None) is not None
                else "disabled"
            ),
            "port_mirroring": profile.port_mirroring if hasattr(profile, 'port_mirroring') else False,
            "custom_properties": [
                {"name": cp.name, "value": cp.value}
                for cp in profile.custom_properties
            ] if hasattr(profile, 'custom_properties') and profile.custom_properties else [],
        }

    @require_connection
    def create_vnic_profile(self, name: str, network: str,
                           description: str = "",
                           port_mirroring: bool = False) -> Dict[str, Any]:
        """Create VNIC profile

        Args:
            name: Profile name
            network: Network name
            description: Description
            port_mirroring: Whether to enable port mirroring

        Returns:
            Creation result
        """
        # Find the network
        net = self._find_network(network)
        if not net:
            raise ValueError(f"Network not found: {network}")

        profiles_service = self.connection.system_service().vnic_profiles_service()

        try:
            profile = profiles_service.add(
                sdk.types.VnicProfile(
                    name=name,
                    description=description,
                    network=sdk.types.Network(id=net.id),
                    port_mirroring=port_mirroring,
                )
            )
            return {
                "success": True,
                "message": f"VNIC Profile {name} created",
                "profile_id": profile.id,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to create VNIC profile: {e}")

    @require_connection
    def update_vnic_profile(self, name_or_id: str, new_name: str = None,
                           description: str = None,
                           port_mirroring: bool = None) -> Dict[str, Any]:
        """Update VNIC profile

        Args:
            name_or_id: Profile name or ID
            new_name: New name
            description: New description
            port_mirroring: Port mirroring setting

        Returns:
            Update result
        """
        profiles_service = self.connection.system_service().vnic_profiles_service()

        # Find the profile
        profile_id = None
        try:
            profile_service = profiles_service.profile_service(name_or_id)
            profile = profile_service.get()
            profile_id = name_or_id
        except Exception:
            profiles = profiles_service.list(search=f"name={_sanitize_search_value(name_or_id)}")
            if not profiles:
                raise ValueError(f"VNIC Profile not found: {name_or_id}")
            profile_id = profiles[0].id
            profile = profiles[0]
            profile_service = profiles_service.profile_service(profile_id)

        if new_name:
            profile.name = new_name
        if description is not None:
            profile.description = description
        if port_mirroring is not None:
            profile.port_mirroring = port_mirroring

        profile_service.update(profile)
        return {"success": True, "message": f"VNIC Profile updated"}

    @require_connection
    def delete_vnic_profile(self, name_or_id: str) -> Dict[str, Any]:
        """Delete VNIC profile

        Args:
            name_or_id: Profile name or ID

        Returns:
            Delete result
        """
        profiles_service = self.connection.system_service().vnic_profiles_service()

        # Find the profile
        profile_id = None
        try:
            profile_service = profiles_service.profile_service(name_or_id)
            profile_service.get()
            profile_id = name_or_id
        except Exception:
            profiles = profiles_service.list(search=f"name={_sanitize_search_value(name_or_id)}")
            if not profiles:
                raise ValueError(f"VNIC Profile not found: {name_or_id}")
            profile_id = profiles[0].id

        profiles_service.profile_service(profile_id).remove()
        return {"success": True, "message": f"VNIC Profile deleted"}

    # -- Network Filter management ------------------------------------------------

    @require_connection
    def list_network_filters(self) -> List[Dict]:
        """List network filters

        Returns:
            List of network filters
        """
        filters_service = self.connection.system_service().network_filters_service()

        try:
            filters = filters_service.list()
        except Exception as e:
            logger.error(f"Failed to list network filters: {e}")
            return []

        result = []
        for f in filters:
            # ``f.version`` is a Version struct — putting it straight into the
            # result leaked "<ovirtsdk4.types.Version object at 0x…>" into output
            ver = getattr(f, "version", None)
            if ver is None:
                version = ""
            elif getattr(ver, "full_version", None):
                version = ver.full_version
            else:
                version = f"{ver.major}.{ver.minor}"
            result.append({
                "id": f.id,
                "name": f.name,
                "version": version,
            })
        return result

    # -- MAC Pool management ------------------------------------------------------

    @require_connection
    def list_mac_pools(self) -> List[Dict]:
        """List MAC pools

        Returns:
            List of MAC pools
        """
        pools_service = self.connection.system_service().mac_pools_service()

        try:
            pools = pools_service.list()
        except Exception as e:
            logger.error(f"Failed to list MAC pools: {e}")
            return []

        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description or "",
                "allow_duplicates": p.allow_duplicates if hasattr(p, 'allow_duplicates') else False,
                "ranges": [
                    {"from": r.from_, "to": r.to}
                    for r in p.ranges
                ] if p.ranges else [],
            }
            for p in pools
        ]

    # -- QoS management ------------------------------------------------------------

    @require_connection
    def list_qos(self, datacenter: str = None) -> List[Dict]:
        """List QoS configurations

        Args:
            datacenter: Data center name (optional)

        Returns:
            List of QoS entries
        """
        # QoS is data-center-scoped in oVirt — ``SystemService`` has no
        # ``qoss_service``, so the old system-level lookup crashed with
        # AttributeError.
        dcs_service = self.connection.system_service().data_centers_service()
        if datacenter:
            dcs = dcs_service.list(search=f"name={_sanitize_search_value(datacenter)}")
            if not dcs:
                raise ValueError(f"Data center not found: {datacenter}")
        else:
            dcs = dcs_service.list()

        result = []
        for dc in dcs:
            try:
                qoss = dcs_service.data_center_service(dc.id).qoss_service().list()
            except Exception as e:
                logger.error(f"Failed to list QoS entries: {e}")
                continue

            # when a datacenter was requested we already iterated only that DC
            for qos in qoss:
                result.append({
                    "id": qos.id,
                    "name": qos.name,
                    "description": qos.description or "",
                    "datacenter": self._data_center_name(qos.data_center) or dc.name,
                    "type": str(qos.type_.value) if hasattr(qos, 'type_') and qos.type_ else "",
                    "max_inbound": qos.max_inbound if hasattr(qos, 'max_inbound') else 0,
                    "max_outbound": qos.max_outbound if hasattr(qos, 'max_outbound') else 0,
                })

        return result


class ClusterMCP(BaseMCP):
    """Cluster management MCP"""

    def __init__(self, ovirt_mcp):
        super().__init__(ovirt_mcp)

    def list_clusters(self) -> List[Dict]:
        """List clusters"""
        return self.ovirt.list_clusters()

    @require_connection
    def get_cluster(self, name: str) -> Optional[Dict]:
        """Get cluster details"""
        clusters = self.connection.system_service().clusters_service().list(search=f"name={_sanitize_search_value(name)}")
        if not clusters: return None

        c = clusters[0]

        # Get cluster CPU
        cpu_info = {}
        if c.cpu:
            cpu_info = {
                "architecture": str(c.cpu.architecture.value)
                if getattr(c.cpu, "architecture", None) else "x86_64",
                "model": str(c.cpu.name) if getattr(c.cpu, "name", None) else "",
            }

        return {
            "id": c.id,
            "name": c.name,
            "description": c.description or "",
            "cpu_architecture": str(c.cpu.architecture.value)
            if c.cpu and getattr(c.cpu, "architecture", None) else "x86_64",
            "cpu": cpu_info,
            "memory_gb": int((getattr(c, "memory", None) or 0) / (1024**3)),
            "version": f"{c.version.major}.{c.version.minor}" if c.version else "4.7",
            "status": str(c.status.value) if getattr(c, "status", None) else "up",
            "data_center": self._data_center_name(c.data_center),
            "data_center_id": c.data_center.id if c.data_center else "",
            "gluster_service": c.gluster_service if hasattr(c, 'gluster_service') else False,
            "virt_service": c.virt_service if hasattr(c, 'virt_service') else True,
            "threads_per_core": c.threads_per_core if hasattr(c, 'threads_per_core') else 1,
            "ha_reservation": c.ha_reservation if hasattr(c, 'ha_reservation') else False,
            "trusted_service": c.trusted_service if hasattr(c, 'trusted_service') else False,
        }

    @require_connection
    def create_cluster(self, name: str, datacenter: str, cpu_type: str,
                      description: str = "",
                      gluster_service: bool = False,
                      threads_per_core: int = 1) -> Dict[str, Any]:
        """Create cluster

        Args:
            name: Cluster name
            datacenter: Data center name
            cpu_type: CPU type
            description: Description
            gluster_service: Whether to enable the Gluster service
            threads_per_core: Threads per core

        Returns:
            Creation result
        """
        # Find the data center
        dcs = self.connection.system_service().data_centers_service().list(
            search=f"name={_sanitize_search_value(datacenter)}"
        )
        if not dcs:
            raise ValueError(f"Data center not found: {datacenter}")

        clusters_service = self.connection.system_service().clusters_service()

        # Check whether it already exists
        existing = clusters_service.list(search=f"name={_sanitize_search_value(name)}")
        if existing:
            raise ValueError(f"Cluster already exists: {name}")

        try:
            cluster = clusters_service.add(
                sdk.types.Cluster(
                    name=name,
                    description=description,
                    data_center=sdk.types.DataCenter(id=dcs[0].id),
                    cpu=sdk.types.Cpu(
                        architecture=sdk.types.Architecture.X86_64,
                        type=cpu_type,
                    ),
                    gluster_service=gluster_service,
                    threads_per_core=threads_per_core,
                )
            )

            return {
                "success": True,
                "message": f"Cluster {name} created",
                "cluster_id": cluster.id,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to create cluster: {e}")

    @require_connection
    def update_cluster(self, name_or_id: str, new_name: str = None,
                      description: str = None,
                      threads_per_core: int = None) -> Dict[str, Any]:
        """Update cluster

        Args:
            name_or_id: Cluster name or ID
            new_name: New name
            description: New description
            threads_per_core: Threads per core

        Returns:
            Update result
        """
        cluster = self._find_cluster(name_or_id)
        if not cluster:
            raise ValueError(f"Cluster not found: {name_or_id}")

        clusters_service = self.connection.system_service().clusters_service()
        cluster_service = clusters_service.cluster_service(cluster.id)

        if new_name:
            cluster.name = new_name
        if description is not None:
            cluster.description = description
        if threads_per_core is not None:
            cluster.threads_per_core = threads_per_core

        try:
            cluster_service.update(cluster)
            return {"success": True, "message": f"Cluster updated"}
        except Exception as e:
            raise RuntimeError(f"Failed to update cluster: {e}")

    @require_connection
    def delete_cluster(self, name_or_id: str) -> Dict[str, Any]:
        """Delete cluster

        Args:
            name_or_id: Cluster name or ID

        Returns:
            Delete result
        """
        cluster = self._find_cluster(name_or_id)
        if not cluster:
            raise ValueError(f"Cluster not found: {name_or_id}")

        clusters_service = self.connection.system_service().clusters_service()
        cluster_service = clusters_service.cluster_service(cluster.id)

        try:
            cluster_service.remove()
            return {"success": True, "message": f"Cluster {cluster.name} deleted"}
        except Exception as e:
            raise RuntimeError(f"Failed to delete cluster: {e}")

    def list_cluster_hosts(self, name: str) -> List[Dict]:
        """List cluster hosts"""
        hosts = self.ovirt.list_hosts(cluster=name)
        return hosts

    def list_cluster_vms(self, name: str, status: str = None) -> List[Dict]:
        """List cluster VMs"""
        return self.ovirt.list_vms(cluster=name, status=status)

    def get_cluster_cpu_load(self, name: str) -> Dict[str, Any]:
        """Get cluster CPU load"""
        hosts = self.list_cluster_hosts(name)

        if not hosts:
            return {"cluster": name, "cpu_load": 0, "host_count": 0}

        total_load = sum(h.get("cpu_usage", 0) for h in hosts)

        return {
            "cluster": name,
            "cpu_load_avg": total_load / len(hosts),
            "cpu_load_total": total_load,
            "host_count": len(hosts),
            "hosts": hosts
        }

    def get_cluster_memory_usage(self, name: str) -> Dict[str, Any]:
        """Get cluster memory usage"""
        hosts = self.list_cluster_hosts(name)

        if not hosts:
            return {"cluster": name, "memory_usage": 0}

        total_mem = sum(h.get("memory_gb", 0) for h in hosts)
        # Simplified calculation
        avg_usage = sum(h.get("memory_usage", 0) for h in hosts) / len(hosts)

        return {
            "cluster": name,
            "memory_usage_avg": avg_usage,
            "memory_total_gb": total_mem,
            "host_count": len(hosts)
        }

    # -- CPU Profile management ----------------------------------------------------

    @require_connection
    def list_cpu_profiles(self, cluster: str) -> List[Dict]:
        """List CPU profiles of a cluster

        Args:
            cluster: Cluster name or ID

        Returns:
            List of CPU profiles
        """
        cluster_obj = self._find_cluster(cluster)
        if not cluster_obj:
            raise ValueError(f"Cluster not found: {cluster}")

        cluster_service = self.connection.system_service().clusters_service().cluster_service(cluster_obj.id)
        profiles_service = cluster_service.cpu_profiles_service()

        try:
            profiles = profiles_service.list()
        except Exception as e:
            logger.error(f"Failed to list CPU profiles: {e}")
            return []

        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description or "",
                "cluster": cluster_obj.name,
            }
            for p in profiles
        ]

    @require_connection
    def get_cpu_profile(self, cluster: str, name_or_id: str) -> Optional[Dict]:
        """Get CPU profile details

        Args:
            cluster: Cluster name or ID
            name_or_id: Profile name or ID

        Returns:
            CPU profile details
        """
        cluster_obj = self._find_cluster(cluster)
        if not cluster_obj:
            raise ValueError(f"Cluster not found: {cluster}")

        cluster_service = self.connection.system_service().clusters_service().cluster_service(cluster_obj.id)
        profiles_service = cluster_service.cpu_profiles_service()

        try:
            profile = profiles_service.cpu_profile_service(name_or_id).get()
            return {
                "id": profile.id,
                "name": profile.name,
                "description": profile.description or "",
                "cluster": cluster_obj.name,
                "cluster_id": cluster_obj.id,
            }
        except Exception:
            profiles = profiles_service.list(search=f"name={_sanitize_search_value(name_or_id)}")
            if not profiles:
                return None
            profile = profiles[0]
            return {
                "id": profile.id,
                "name": profile.name,
                "description": profile.description or "",
                "cluster": cluster_obj.name,
                "cluster_id": cluster_obj.id,
            }


class TemplateMCP(BaseMCP):
    """Template management MCP"""

    def __init__(self, ovirt_mcp):
        super().__init__(ovirt_mcp)

    def list_templates(self, cluster: str = None) -> List[Dict]:
        """List templates"""
        return self.ovirt.list_templates(cluster)

    @require_connection
    def get_template(self, name: str) -> Optional[Dict]:
        """Get template details"""
        templates = self.connection.system_service().templates_service().list(search=f"name={_sanitize_search_value(name)}")
        if not templates: return None

        t = templates[0]

        # Get disk information
        # Template objects expose no *_service() methods — go through the
        # service, otherwise the AttributeError was swallowed and disks
        # always came back empty.
        disks = []
        try:
            templates_service = self.connection.system_service().templates_service()
            disk_attachments = (
                templates_service.template_service(t.id)
                .disk_attachments_service()
                .list()
            )
            for da in disk_attachments:
                disk = self.connection.system_service().disks_service().disk_service(
                    da.disk.id
                ).get()
                disks.append({
                    "name": disk.alias or disk.id,
                    "size_gb": int((disk.provisioned_size or 0) / (1024**3))
                })
        except Exception as e:
            logger.debug(f"Failed to get template disk info: {e}")

        return {
            "id": t.id,
            "name": t.name,
            "description": t.description or "",
            "memory_mb": int(t.memory / (1024**2)) if t.memory else 0,
            "cpu_cores": t.cpu.topology.cores if t.cpu and t.cpu.topology else 0,
            "os_type": t.os.type if t.os else "",
            "disks": disks,
            "creation_time": str(t.creation_time) if t.creation_time else ""
        }

    def create_vm_from_template(self, name: str, template: str, cluster: str,
                                memory_mb: int = None, cpu_cores: int = None) -> Dict[str, Any]:
        """Create VM from template"""
        return self.ovirt.create_vm(
            name=name,
            cluster=cluster,
            memory_mb=memory_mb or 4096,
            cpu_cores=cpu_cores or 2,
            template=template
        )

    def clone_template(self, name: str, new_name: str, cluster: str) -> Dict[str, Any]:
        """Clone template"""
        # First create a VM from the template
        result = self.create_vm_from_template(new_name, name, cluster)
        return result


# MCP tool registry
MCP_TOOLS = {
    # Core VM operations
    "vm_list": {"method": "list_vms", "description": "List VMs"},
    "vm_get": {"method": "get_vm", "description": "Get VM details"},
    "vm_create": {"method": "create_vm", "description": "Create VM"},
    "vm_delete": {"method": "delete_vm", "description": "Delete VM"},
    "vm_start": {"method": "start_vm", "description": "Start VM"},
    "vm_stop": {"method": "stop_vm", "description": "Stop VM"},
    "vm_restart": {"method": "restart_vm", "description": "Restart VM"},
    "vm_update_resources": {"method": "update_vm_resources", "description": "Update VM resources"},
    "vm_rename": {"method": "rename_vm", "description": "Rename VM"},
    "vm_stats": {"method": "get_vm_stats", "description": "Get VM statistics"},

    # Snapshot management
    "snapshot_list": {"method": "list_snapshots", "description": "List snapshots"},
    "snapshot_create": {"method": "create_snapshot", "description": "Create snapshot"},
    "snapshot_restore": {"method": "restore_snapshot", "description": "Restore snapshot"},
    "snapshot_delete": {"method": "delete_snapshot", "description": "Delete snapshot"},

    # Disk management
    "disk_list": {"method": "list_disks", "description": "List disks"},
    "disk_create": {"method": "create_disk", "description": "Create disk"},
    "disk_attach": {"method": "attach_disk", "description": "Attach disk"},

    # Network management
    "network_list": {"method": "list_networks", "description": "List networks"},
    "network_get": {"method": "get_network", "description": "Get network details"},
    "network_create": {"method": "create_network", "description": "Create network"},
    "network_update": {"method": "update_network", "description": "Update network"},
    "network_delete": {"method": "delete_network", "description": "Delete network"},
    "nic_list": {"method": "list_vnics", "description": "List NICs"},
    "nic_add": {"method": "add_nic", "description": "Add NIC"},
    "nic_remove": {"method": "remove_nic", "description": "Remove NIC"},

    # VNIC Profile management
    "vnic_profile_list": {"method": "list_vnic_profiles", "description": "List VNIC profiles"},
    "vnic_profile_get": {"method": "get_vnic_profile", "description": "Get VNIC profile details"},
    "vnic_profile_create": {"method": "create_vnic_profile", "description": "Create VNIC profile"},
    "vnic_profile_update": {"method": "update_vnic_profile", "description": "Update VNIC profile"},
    "vnic_profile_delete": {"method": "delete_vnic_profile", "description": "Delete VNIC profile"},

    # Network Filter management
    "network_filter_list": {"method": "list_network_filters", "description": "List network filters"},

    # MAC Pool management
    "mac_pool_list": {"method": "list_mac_pools", "description": "List MAC pools"},

    # QoS management
    "qos_list": {"method": "list_qos", "description": "List QoS configurations"},

    # Host management
    "host_list": {"method": "list_hosts", "description": "List hosts"},
    "host_activate": {"method": "activate_host", "description": "Activate host"},
    "host_deactivate": {"method": "deactivate_host", "description": "Deactivate host"},

    # Cluster management
    "cluster_list": {"method": "list_clusters", "description": "List clusters"},
    "cluster_get": {"method": "get_cluster", "description": "Get cluster details"},
    "cluster_create": {"method": "create_cluster", "description": "Create cluster"},
    "cluster_update": {"method": "update_cluster", "description": "Update cluster"},
    "cluster_delete": {"method": "delete_cluster", "description": "Delete cluster"},
    "cluster_hosts": {"method": "list_cluster_hosts", "description": "Cluster hosts"},
    "cluster_vms": {"method": "list_cluster_vms", "description": "Cluster VMs"},
    "cluster_cpu_load": {"method": "get_cluster_cpu_load", "description": "Cluster CPU load"},
    "cluster_memory_usage": {"method": "get_cluster_memory_usage", "description": "Cluster memory usage"},

    # CPU Profile management
    "cpu_profile_list": {"method": "list_cpu_profiles", "description": "List CPU profiles"},
    "cpu_profile_get": {"method": "get_cpu_profile", "description": "Get CPU profile details"},

    # Storage management
    "storage_list": {"method": "list_storage_domains", "description": "List storage domains"},
    "storage_attach": {"method": "attach_storage", "description": "Attach storage"},

    # Template management
    "template_list": {"method": "list_templates", "description": "List templates"},
    "template_vm_create": {"method": "create_vm_from_template", "description": "Create VM from template"},
}


def get_tool_list() -> List[Dict]:
    """Get all MCP tool definitions"""
    return [
        {"name": name, "description": info["description"]}
        for name, info in MCP_TOOLS.items()
    ]
