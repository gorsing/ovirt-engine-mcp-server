#!/usr/bin/env python3
"""
oVirt MCP Server - VM extensions module
Provides VM migration, console, CD-ROM, host device, NUMA, watchdog, session, VM pool, checkpoint and other advanced management features
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


class VmExtendedMCP(BaseMCP):
    """VM extended management MCP"""

    def __init__(self, ovirt_mcp):
        super().__init__(ovirt_mcp)

    # -- VM migration --------------------------------------------------------------

    @require_connection
    def migrate_vm(self, name_or_id: str, target_host: str = None) -> Dict[str, Any]:
        """Migrate a VM to another host

        Args:
            name_or_id: VM name or ID
            target_host: Target host name or ID (optional, auto-selected if omitted)

        Returns:
            Migration result
        """
        vm = self._find_vm(name_or_id)
        if not vm:
            raise ValueError(f"VM not found: {name_or_id}")

        vm_service = self.connection.system_service().vms_service().vm_service(vm.id)

        # Build migration parameters
        host_ref = None
        if target_host:
            host = self._find_host(target_host)
            if not host:
                raise ValueError(f"Target host not found: {target_host}")
            host_ref = sdk.types.Host(id=host.id)

        try:
            vm_service.migrate(host=host_ref)
            return {
                "success": True,
                "message": f"VM {vm.name} is migrating" + (f" to host {target_host}" if target_host else ""),
                "vm_id": vm.id,
                "target_host": target_host,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to migrate VM: {e}")

    # -- VM console ------------------------------------------------------------

    @require_connection
    def get_vm_console(self, name_or_id: str, console_type: str = "spice") -> Dict[str, Any]:
        """Get VM console access information

        Args:
            name_or_id: VM name or ID
            console_type: Console type (spice/vnc), defaults to spice

        Returns:
            Console connection information
        """
        vm = self._find_vm(name_or_id)
        if not vm:
            raise ValueError(f"VM not found: {name_or_id}")

        vm_service = self.connection.system_service().vms_service().vm_service(vm.id)

        # Get graphical consoles
        consoles = []
        try:
            graphics_consoles_service = vm_service.graphics_consoles_service()
            console_list = graphics_consoles_service.list()

            for console in console_list:
                # Get console ticket
                ticket = None
                try:
                    console_service = graphics_consoles_service.console_service(console.id)
                    ticket_response = console_service.ticket()
                    ticket = ticket_response.value if ticket_response else None
                except Exception as e:
                    logger.debug(f"Failed to get console ticket: {e}")

                consoles.append({
                    "id": console.id,
                    "protocol": str(console.protocol.value) if console.protocol else "",
                    "address": console.address if hasattr(console, 'address') else "",
                    "port": console.port if hasattr(console, 'port') else 0,
                    "tls_port": console.tls_port if hasattr(console, 'tls_port') else 0,
                    "ticket": ticket,
                })
        except Exception as e:
            logger.error(f"Failed to get consoles: {e}")

        # Filter by type
        if console_type:
            consoles = [c for c in consoles if c["protocol"].lower() == console_type.lower()]

        return {
            "vm_id": vm.id,
            "vm_name": vm.name,
            "consoles": consoles,
            "console_count": len(consoles),
        }

    # -- CD-ROM management ------------------------------------------------------------

    @require_connection
    def list_vm_cdroms(self, name_or_id: str) -> List[Dict]:
        """List VM CD-ROM devices

        Args:
            name_or_id: VM name or ID

        Returns:
            CD-ROM list
        """
        vm = self._find_vm(name_or_id)
        if not vm:
            raise ValueError(f"VM not found: {name_or_id}")

        vm_service = self.connection.system_service().vms_service().vm_service(vm.id)
        cdroms_service = vm_service.cdroms_service()

        try:
            cdroms = cdroms_service.list()
        except Exception as e:
            logger.error(f"Failed to get CD-ROM list: {e}")
            return []

        result = []
        for cdrom in cdroms:
            result.append({
                "id": cdrom.id,
                "file": cdrom.file.id if cdrom.file else "",
                "storage_domain": self._storage_domain_name(cdrom.storage_domain),
            })

        return result

    @require_connection
    def update_vm_cdrom(self, name_or_id: str, cdrom_id: str,
                       iso_file: str = None, eject: bool = False) -> Dict[str, Any]:
        """Update VM CD-ROM (mount/eject ISO)

        Args:
            name_or_id: VM name or ID
            cdrom_id: CDROM ID
            iso_file: ISO file path (optional)
            eject: Whether to eject the disc

        Returns:
            Update result
        """
        vm = self._find_vm(name_or_id)
        if not vm:
            raise ValueError(f"VM not found: {name_or_id}")

        vm_service = self.connection.system_service().vms_service().vm_service(vm.id)
        cdroms_service = vm_service.cdroms_service()
        cdrom_service = cdroms_service.cdrom_service(cdrom_id)

        # Get current CD-ROM
        cdrom = cdrom_service.get()

        # Update file
        if eject:
            cdrom.file = None
        elif iso_file:
            cdrom.file = sdk.types.File(id=iso_file)

        try:
            cdrom_service.update(cdrom)
            return {
                "success": True,
                "message": f"CD-ROM updated",
                "vm_id": vm.id,
                "cdrom_id": cdrom_id,
                "iso_file": iso_file if not eject else "ejected",
            }
        except Exception as e:
            raise RuntimeError(f"Failed to update CD-ROM: {e}")

    # -- Host device management ----------------------------------------------------------

    @require_connection
    def list_vm_host_devices(self, name_or_id: str) -> List[Dict]:
        """List VM host devices

        Args:
            name_or_id: VM name or ID

        Returns:
            List of host devices
        """
        vm = self._find_vm(name_or_id)
        if not vm:
            raise ValueError(f"VM not found: {name_or_id}")

        vm_service = self.connection.system_service().vms_service().vm_service(vm.id)
        host_devices_service = vm_service.host_devices_service()

        try:
            devices = host_devices_service.list()
        except Exception as e:
            logger.error(f"Failed to get host device list: {e}")
            return []

        return [
            {
                "id": d.id,
                "name": d.name,
                "device": d.device if hasattr(d, 'device') else "",
                "vendor": d.vendor if hasattr(d, 'vendor') else "",
                "product": d.product if hasattr(d, 'product') else "",
            }
            for d in devices
        ]

    @require_connection
    def attach_vm_host_device(self, name_or_id: str, device_name: str) -> Dict[str, Any]:
        """Attach a host device to the VM

        Args:
            name_or_id: VM name or ID
            device_name: Device name

        Returns:
            Attach result
        """
        vm = self._find_vm(name_or_id)
        if not vm:
            raise ValueError(f"VM not found: {name_or_id}")

        # Get devices from the VM's host
        if not vm.host:
            raise ValueError("VM is not running on a host; cannot attach device")

        host_service = self.connection.system_service().hosts_service().host_service(vm.host.id)
        devices_service = host_service.devices_service()

        # Find device
        devices = devices_service.list(search=f"name={_sanitize_search_value(device_name)}")
        if not devices:
            raise ValueError(f"Device not found: {device_name}")

        device = devices[0]

        vm_service = self.connection.system_service().vms_service().vm_service(vm.id)
        host_devices_service = vm_service.host_devices_service()

        try:
            host_devices_service.add(
                sdk.types.HostDevice(id=device.id, name=device.name)
            )
            return {
                "success": True,
                "message": f"Device {device_name} attached to VM",
                "vm_id": vm.id,
                "device_id": device.id,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to attach device: {e}")

    @require_connection
    def detach_vm_host_device(self, name_or_id: str, device_name: str) -> Dict[str, Any]:
        """Detach a host device from the VM

        Args:
            name_or_id: VM name or ID
            device_name: Device name

        Returns:
            Detach result
        """
        vm = self._find_vm(name_or_id)
        if not vm:
            raise ValueError(f"VM not found: {name_or_id}")

        vm_service = self.connection.system_service().vms_service().vm_service(vm.id)
        host_devices_service = vm_service.host_devices_service()

        # Find device
        devices = host_devices_service.list()
        device = None
        for d in devices:
            if d.name == device_name:
                device = d
                break

        if not device:
            raise ValueError(f"VM has no attached device: {device_name}")

        device_service = host_devices_service.host_device_service(device.id)

        try:
            device_service.remove()
            return {
                "success": True,
                "message": f"Device {device_name} detached from VM",
                "vm_id": vm.id,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to detach device: {e}")

    # -- Mediated device management ----------------------------------------------------------

    @require_connection
    def list_vm_mediated_devices(self, name_or_id: str) -> List[Dict]:
        """List VM mediated devices (vGPU etc.)

        Args:
            name_or_id: VM name or ID

        Returns:
            List of mediated devices
        """
        vm = self._find_vm(name_or_id)
        if not vm:
            raise ValueError(f"VM not found: {name_or_id}")

        vm_service = self.connection.system_service().vms_service().vm_service(vm.id)
        mediated_devices_service = vm_service.mediated_devices_service()

        try:
            devices = mediated_devices_service.list()
        except Exception as e:
            logger.error(f"Failed to get mediated device list: {e}")
            return []

        return [
            {
                "id": d.id,
                "name": d.name,
                "spec": d.spec_params if hasattr(d, 'spec_params') else {},
                "driver": d.driver if hasattr(d, 'driver') else "",
            }
            for d in devices
        ]

    # -- NUMA management ------------------------------------------------------------

    @require_connection
    def list_vm_numa_nodes(self, name_or_id: str) -> List[Dict]:
        """List VM NUMA nodes

        Args:
            name_or_id: VM name or ID

        Returns:
            List of NUMA nodes
        """
        vm = self._find_vm(name_or_id)
        if not vm:
            raise ValueError(f"VM not found: {name_or_id}")

        vm_service = self.connection.system_service().vms_service().vm_service(vm.id)
        numa_service = vm_service.numa_nodes_service()

        try:
            nodes = numa_service.list()
        except Exception as e:
            logger.error(f"Failed to get NUMA nodes: {e}")
            return []

        result = []
        for node in nodes:
            result.append({
                "id": node.id,
                "index": node.index if hasattr(node, 'index') else 0,
                "memory_mb": int((node.memory or 0) / (1024**2)),
                "cpu": {
                    "cores": node.cpu.topology.cores if node.cpu and node.cpu.topology else 0,
                    "sockets": node.cpu.topology.sockets if node.cpu and node.cpu.topology else 0,
                    "threads": node.cpu.topology.threads if node.cpu and node.cpu.topology else 0,
                } if node.cpu else {},
            })

        return result

    # -- Watchdog management ----------------------------------------------------------

    @require_connection
    def list_vm_watchdogs(self, name_or_id: str) -> List[Dict]:
        """List VM watchdog devices

        Args:
            name_or_id: VM name or ID

        Returns:
            List of watchdogs
        """
        vm = self._find_vm(name_or_id)
        if not vm:
            raise ValueError(f"VM not found: {name_or_id}")

        vm_service = self.connection.system_service().vms_service().vm_service(vm.id)
        watchdogs_service = vm_service.watchdogs_service()

        try:
            watchdogs = watchdogs_service.list()
        except Exception as e:
            logger.error(f"Failed to get watchdog list: {e}")
            return []

        return [
            {
                "id": w.id,
                "model": str(w.model.value) if w.model else "",
                "action": str(w.action.value) if w.action else "",
            }
            for w in watchdogs
        ]

    @require_connection
    def update_vm_watchdog(self, name_or_id: str, watchdog_id: str,
                          action: str = None) -> Dict[str, Any]:
        """Update VM watchdog configuration

        Args:
            name_or_id: VM name or ID
            watchdog_id: Watchdog ID
            action: Action to trigger (none/reset/poweroff/shutdown/dump)

        Returns:
            Update result
        """
        vm = self._find_vm(name_or_id)
        if not vm:
            raise ValueError(f"VM not found: {name_or_id}")

        vm_service = self.connection.system_service().vms_service().vm_service(vm.id)
        watchdogs_service = vm_service.watchdogs_service()
        watchdog_service = watchdogs_service.watchdog_service(watchdog_id)

        watchdog = watchdog_service.get()

        if action:
            valid_actions = ["none", "reset", "poweroff", "shutdown", "dump"]
            if action.lower() not in valid_actions:
                raise ValueError(f"Invalid action: {action}, valid values: {valid_actions}")
            watchdog.action = sdk.types.WatchdogAction(action.lower())

        try:
            watchdog_service.update(watchdog)
            return {
                "success": True,
                "message": f"Watchdog updated",
                "vm_id": vm.id,
                "watchdog_id": watchdog_id,
                "action": action,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to update watchdog: {e}")

    # -- VM pin to host ----------------------------------------------------------

    @require_connection
    def pin_vm_to_host(self, name_or_id: str, host: str,
                      pin_policy: str = "user") -> Dict[str, Any]:
        """Pin a VM to a specific host

        Args:
            name_or_id: VM name or ID
            host: Host name or ID
            pin_policy: Pin policy (user/resizable/migratable)

        Returns:
            Pin result
        """
        vm = self._find_vm(name_or_id)
        if not vm:
            raise ValueError(f"VM not found: {name_or_id}")

        host_obj = self._find_host(host)
        if not host_obj:
            raise ValueError(f"Host not found: {host}")

        vm_service = self.connection.system_service().vms_service().vm_service(vm.id)

        # Set pinned host
        vm_update = sdk.types.Vm(
            host=sdk.types.Host(id=host_obj.id),
        )

        # Set pin policy (if available)
        if hasattr(sdk.types, 'VmPlacementPolicy'):
            valid_policies = ["user", "resizable", "migratable"]
            if pin_policy.lower() not in valid_policies:
                raise ValueError(f"Invalid policy: {pin_policy}, valid values: {valid_policies}")

        try:
            vm_service.update(vm_update)
            return {
                "success": True,
                "message": f"VM {vm.name} pinned to host {host}",
                "vm_id": vm.id,
                "host_id": host_obj.id,
                "pin_policy": pin_policy,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to pin VM: {e}")

    # -- VM session management ------------------------------------------------------------

    @require_connection
    def list_vm_sessions(self, name_or_id: str) -> List[Dict]:
        """List active VM sessions

        Args:
            name_or_id: VM name or ID

        Returns:
            List of sessions
        """
        vm = self._find_vm(name_or_id)
        if not vm:
            raise ValueError(f"VM not found: {name_or_id}")

        vm_service = self.connection.system_service().vms_service().vm_service(vm.id)
        sessions_service = vm_service.sessions_service()

        try:
            sessions = sessions_service.list()
        except Exception as e:
            logger.error(f"Failed to get session list: {e}")
            return []

        return [
            {
                "id": s.id,
                "user": self._user_name(s.user),
                "user_id": s.user.id if s.user else "",
                "protocol": str(s.protocol.value) if s.protocol else "",
                "console_user": s.console_user if hasattr(s, 'console_user') else False,
            }
            for s in sessions
        ]

    # -- VM pool management ------------------------------------------------------------

    @require_connection
    def list_vm_pools(self, cluster: str = None) -> List[Dict]:
        """List VM pools

        Args:
            cluster: Cluster name (optional)

        Returns:
            List of VM pools
        """
        pools_service = self.connection.system_service().vm_pools_service()

        search = None
        if cluster:
            search = f"cluster={_sanitize_search_value(cluster)}"

        try:
            pools = pools_service.list(search=search)
        except Exception as e:
            logger.error(f"Failed to get VM pool list: {e}")
            return []

        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description or "",
                "size": p.size if hasattr(p, 'size') else 0,
                "max_user_vms": p.max_user_vms if hasattr(p, 'max_user_vms') else 0,
                "prestarted_vms": p.prestarted_vms if hasattr(p, 'prestarted_vms') else 0,
                "cluster": self._cluster_name(p.cluster),
                "template": self._vm_name(p.vm),
                "stateful": p.stateful if hasattr(p, 'stateful') else False,
            }
            for p in pools
        ]

    @require_connection
    def get_vm_pool(self, name_or_id: str) -> Optional[Dict]:
        """Get VM pool details

        Args:
            name_or_id: VM pool name or ID

        Returns:
            VM pool details
        """
        pools_service = self.connection.system_service().vm_pools_service()

        # Try to get by ID
        try:
            pool = pools_service.pool_service(name_or_id).get()
            if pool:
                return self._format_pool_detail(pool)
        except Exception:
            pass

        # Search by name
        pools = pools_service.list(search=f"name={_sanitize_search_value(name_or_id)}")
        if not pools:
            return None

        return self._format_pool_detail(pools[0])

    def _format_pool_detail(self, pool) -> Dict:
        """Format pool details"""
        return {
            "id": pool.id,
            "name": pool.name,
            "description": pool.description or "",
            "size": pool.size if hasattr(pool, 'size') else 0,
            "max_user_vms": pool.max_user_vms if hasattr(pool, 'max_user_vms') else 0,
            "prestarted_vms": pool.prestarted_vms if hasattr(pool, 'prestarted_vms') else 0,
            "cluster": self._cluster_name(pool.cluster),
            "cluster_id": pool.cluster.id if pool.cluster else "",
            "template": self._vm_name(pool.vm),
            "template_id": pool.vm.id if pool.vm else "",
            "stateful": pool.stateful if hasattr(pool, 'stateful') else False,
            "display": {
                "type": str(pool.display.type.value) if pool.display else "",
            } if pool.display else {},
            "rng_device": str(pool.rng_device.source.value) if hasattr(pool, 'rng_device') and pool.rng_device else "",
        }

    @require_connection
    def create_vm_pool(self, name: str, template: str, cluster: str,
                      size: int = 5, description: str = "",
                      max_user_vms: int = 1, prestarted_vms: int = 0,
                      stateful: bool = False) -> Dict[str, Any]:
        """Create a VM pool

        Args:
            name: Pool name
            template: Template name
            cluster: Cluster name
            size: Pool size, defaults to 5
            description: Description
            max_user_vms: Max VMs per user, defaults to 1
            prestarted_vms: Prestarted VMs, defaults to 0
            stateful: Whether stateful, defaults to False

        Returns:
            Creation result
        """
        # Find template
        templates = self.connection.system_service().templates_service().list(
            search=f"name={_sanitize_search_value(template)}"
        )
        if not templates:
            raise ValueError(f"Template not found: {template}")

        # Find cluster
        clusters = self.connection.system_service().clusters_service().list(
            search=f"name={_sanitize_search_value(cluster)}"
        )
        if not clusters:
            raise ValueError(f"Cluster not found: {cluster}")

        pools_service = self.connection.system_service().vm_pools_service()

        try:
            pool = pools_service.add(
                sdk.types.VmPool(
                    name=name,
                    description=description,
                    size=size,
                    max_user_vms=max_user_vms,
                    prestarted_vms=prestarted_vms,
                    stateful=stateful,
                    cluster=sdk.types.Cluster(id=clusters[0].id),
                    vm=sdk.types.Vm(id=templates[0].id),
                )
            )

            return {
                "success": True,
                "message": f"VM pool {name} created",
                "pool_id": pool.id,
                "size": size,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to create VM pool: {e}")

    @require_connection
    def delete_vm_pool(self, name_or_id: str, force: bool = False) -> Dict[str, Any]:
        """Delete a VM pool

        Args:
            name_or_id: VM pool name or ID
            force: Force delete

        Returns:
            Deletion result
        """
        pools_service = self.connection.system_service().vm_pools_service()

        # Find pool
        pool_id = None
        pool_name = None
        try:
            pool_service = pools_service.pool_service(name_or_id)
            pool = pool_service.get()
            pool_id = name_or_id
            pool_name = pool.name
        except Exception:
            pools = pools_service.list(search=f"name={_sanitize_search_value(name_or_id)}")
            if not pools:
                raise ValueError(f"VM pool not found: {name_or_id}")
            pool_id = pools[0].id
            pool_name = pools[0].name

        pool_service = pools_service.pool_service(pool_id)

        try:
            pool_service.remove(force=force)
            return {"success": True, "message": f"VM pool {pool_name} deleted"}
        except Exception as e:
            raise RuntimeError(f"Failed to delete VM pool: {e}")

    @require_connection
    def update_vm_pool(self, name_or_id: str, new_name: str = None,
                      size: int = None, description: str = None,
                      prestarted_vms: int = None) -> Dict[str, Any]:
        """Update a VM pool

        Args:
            name_or_id: VM pool name or ID
            new_name: New name (optional)
            size: New size (optional)
            description: New description (optional)
            prestarted_vms: Prestarted VMs (optional)

        Returns:
            Update result
        """
        pools_service = self.connection.system_service().vm_pools_service()

        # Find pool
        pool_id = None
        try:
            pool_service = pools_service.pool_service(name_or_id)
            pool = pool_service.get()
            pool_id = name_or_id
        except Exception:
            pools = pools_service.list(search=f"name={_sanitize_search_value(name_or_id)}")
            if not pools:
                raise ValueError(f"VM pool not found: {name_or_id}")
            pool_id = pools[0].id
            pool = pools[0]
            pool_service = pools_service.pool_service(pool_id)

        # Update properties
        if new_name:
            pool.name = new_name
        if size is not None:
            pool.size = size
        if description is not None:
            pool.description = description
        if prestarted_vms is not None:
            pool.prestarted_vms = prestarted_vms

        try:
            pool_service.update(pool)
            return {"success": True, "message": f"VM pool updated"}
        except Exception as e:
            raise RuntimeError(f"Failed to update VM pool: {e}")

    # -- VM checkpoint management ----------------------------------------------------------

    @require_connection
    def list_vm_checkpoints(self, name_or_id: str) -> List[Dict]:
        """List VM checkpoints

        Args:
            name_or_id: VM name or ID

        Returns:
            List of checkpoints
        """
        vm = self._find_vm(name_or_id)
        if not vm:
            raise ValueError(f"VM not found: {name_or_id}")

        vm_service = self.connection.system_service().vms_service().vm_service(vm.id)
        checkpoints_service = vm_service.checkpoints_service()

        try:
            checkpoints = checkpoints_service.list()
        except Exception as e:
            logger.error(f"Failed to get checkpoint list: {e}")
            return []

        return [
            {
                "id": c.id,
                "name": c.name if hasattr(c, 'name') else c.id,
                "creation_time": str(c.creation_time) if hasattr(c, 'creation_time') else "",
                "description": c.description if hasattr(c, 'description') else "",
            }
            for c in checkpoints
        ]

    @require_connection
    def create_vm_checkpoint(self, name_or_id: str, description: str = "") -> Dict[str, Any]:
        """Create a VM checkpoint

        Args:
            name_or_id: VM name or ID
            description: Checkpoint description

        Returns:
            Creation result
        """
        vm = self._find_vm(name_or_id)
        if not vm:
            raise ValueError(f"VM not found: {name_or_id}")

        vm_service = self.connection.system_service().vms_service().vm_service(vm.id)
        checkpoints_service = vm_service.checkpoints_service()

        try:
            checkpoint = checkpoints_service.add(
                sdk.types.Checkpoint(
                    description=description,
                )
            )

            return {
                "success": True,
                "message": f"Checkpoint created",
                "vm_id": vm.id,
                "checkpoint_id": checkpoint.id,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to create checkpoint: {e}")

    @require_connection
    def restore_vm_checkpoint(self, name_or_id: str, checkpoint_id: str) -> Dict[str, Any]:
        """Restore a VM to a checkpoint

        Args:
            name_or_id: VM name or ID
            checkpoint_id: Checkpoint ID

        Returns:
            Restore result
        """
        vm = self._find_vm(name_or_id)
        if not vm:
            raise ValueError(f"VM not found: {name_or_id}")

        vm_service = self.connection.system_service().vms_service().vm_service(vm.id)
        checkpoints_service = vm_service.checkpoints_service()
        checkpoint_service = checkpoints_service.checkpoint_service(checkpoint_id)

        try:
            checkpoint_service.restore()
            return {
                "success": True,
                "message": f"VM restored to checkpoint",
                "vm_id": vm.id,
                "checkpoint_id": checkpoint_id,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to restore checkpoint: {e}")

    @require_connection
    def delete_vm_checkpoint(self, name_or_id: str, checkpoint_id: str) -> Dict[str, Any]:
        """Delete a VM checkpoint

        Args:
            name_or_id: VM name or ID
            checkpoint_id: Checkpoint ID

        Returns:
            Deletion result
        """
        vm = self._find_vm(name_or_id)
        if not vm:
            raise ValueError(f"VM not found: {name_or_id}")

        vm_service = self.connection.system_service().vms_service().vm_service(vm.id)
        checkpoints_service = vm_service.checkpoints_service()
        checkpoint_service = checkpoints_service.checkpoint_service(checkpoint_id)

        try:
            checkpoint_service.remove()
            return {
                "success": True,
                "message": f"Checkpoint deleted",
                "vm_id": vm.id,
                "checkpoint_id": checkpoint_id,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to delete checkpoint: {e}")


# MCP tool registry
MCP_TOOLS = {
    # VM migration and console
    "vm_migrate": {"method": "migrate_vm", "description": "Migrate a VM to another host"},
    "vm_console": {"method": "get_vm_console", "description": "Get VM console access information"},

    # CD-ROM management
    "vm_cdrom_list": {"method": "list_vm_cdroms", "description": "List VM CD-ROM devices"},
    "vm_cdrom_update": {"method": "update_vm_cdrom", "description": "Update VM CD-ROM (mount/eject ISO)"},

    # Host device management
    "vm_hostdevice_list": {"method": "list_vm_host_devices", "description": "List VM host devices"},
    "vm_hostdevice_attach": {"method": "attach_vm_host_device", "description": "Attach a host device to the VM"},
    "vm_hostdevice_detach": {"method": "detach_vm_host_device", "description": "Detach a host device from the VM"},

    # Mediated device management
    "vm_mediated_device_list": {"method": "list_vm_mediated_devices", "description": "List VM mediated devices (vGPU)"},

    # NUMA management
    "vm_numa_list": {"method": "list_vm_numa_nodes", "description": "List VM NUMA nodes"},

    # Watchdog management
    "vm_watchdog_list": {"method": "list_vm_watchdogs", "description": "List VM watchdog devices"},
    "vm_watchdog_update": {"method": "update_vm_watchdog", "description": "Update VM watchdog configuration"},

    # VM pinning
    "vm_pin_to_host": {"method": "pin_vm_to_host", "description": "Pin a VM to a specific host"},

    # Session management
    "vm_session_list": {"method": "list_vm_sessions", "description": "List active VM sessions"},

    # VM pool management
    "vm_pool_list": {"method": "list_vm_pools", "description": "List VM pools"},
    "vm_pool_get": {"method": "get_vm_pool", "description": "Get VM pool details"},
    "vm_pool_create": {"method": "create_vm_pool", "description": "Create a VM pool"},
    "vm_pool_delete": {"method": "delete_vm_pool", "description": "Delete a VM pool"},
    "vm_pool_update": {"method": "update_vm_pool", "description": "Update a VM pool"},

    # Checkpoint management
    "vm_checkpoint_list": {"method": "list_vm_checkpoints", "description": "List VM checkpoints"},
    "vm_checkpoint_create": {"method": "create_vm_checkpoint", "description": "Create a VM checkpoint"},
    "vm_checkpoint_restore": {"method": "restore_vm_checkpoint", "description": "Restore a VM to a checkpoint"},
    "vm_checkpoint_delete": {"method": "delete_vm_checkpoint", "description": "Delete a VM checkpoint"},
}
