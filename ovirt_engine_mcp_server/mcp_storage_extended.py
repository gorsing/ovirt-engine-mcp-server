#!/usr/bin/env python3
"""
oVirt MCP Server - Storage extension module
Provides storage domain details, creation, deletion, and detach operations
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


class StorageExtendedMCP(BaseMCP):
    """Storage extended management MCP."""

    def __init__(self, ovirt_mcp):
        super().__init__(ovirt_mcp)

    @require_connection
    def get_storage_domain(self, name_or_id: str) -> Optional[Dict]:
        """Get storage domain details."""
        sd = self._find_storage_domain(name_or_id)
        if not sd:
            return None

        # Get storage domain files (if supported)
        files = []
        try:
            sd_service = self.connection.system_service().storage_domains_service().storage_domain_service(sd.id)
            files_service = sd_service.files_service()
            file_list = files_service.list()
            files = [
                {"name": f.name, "size": f.size if hasattr(f, "size") else 0}
                for f in file_list[:20]  # limit count
            ]
        except Exception as e:
            logger.debug(f"Failed to get storage domain files: {e}")

        # Get associated data centers
        data_centers = []
        try:
            dc_service = sd_service.storage_domains_service() if hasattr(sd_service, 'storage_domains_service') else None
            # Resolve via the storage domain's data center link
            if sd.storage_connections:
                data_centers = [
                    {"id": dc.id, "name": dc.name}
                    for dc in [sd.storage_connections]
                ]
        except Exception as e:
            logger.debug(f"Failed to get storage domain data center: {e}")

        return {
            "id": sd.id,
            "name": sd.name,
            "description": sd.description or "",
            "type": str(sd.type.value) if sd.type else "data",
            "status": str(sd.status.value) if sd.status else "unknown",
            "storage_type": str(sd.storage.type.value) if sd.storage else "nfs",
            "available_space_gb": int((sd.available or 0) / (1024**3)),
            "used_space_gb": int((sd.used or 0) / (1024**3)),
            "total_space_gb": int(((sd.available or 0) + (sd.used or 0)) / (1024**3)),
            "master": sd.master if hasattr(sd, 'master') else False,
            "wipe_after_delete": sd.wipe_after_delete if hasattr(sd, 'wipe_after_delete') else False,
            "supports_discard": sd.supports_discard if hasattr(sd, 'supports_discard') else False,
            "warning_low_space": sd.warning_low_space_indicator if hasattr(sd, 'warning_low_space_indicator') else 0,
            "critical_low_space": sd.critical_space_action_blocker if hasattr(sd, 'critical_space_action_blocker') else 0,
            "data_center": sd.storage.data_center.name if sd.storage and sd.storage.data_center else "",
            "data_center_id": sd.storage.data_center.id if sd.storage and sd.storage.data_center else "",
            "files": files,
        }

    @require_connection
    def create_storage_domain(self, name: str, storage_type: str, host: str,
                             path: str, datacenter: str = None,
                             description: str = "",
                             domain_type: str = "data") -> Dict[str, Any]:
        """Create a storage domain."""
        # Validate storage type
        valid_storage_types = ["nfs", "fc", "iscsi", "localfs", "posixfs", "glusterfs"]
        if storage_type.lower() not in valid_storage_types:
            raise ValueError(f"Invalid storage type: {storage_type}, valid values: {valid_storage_types}")

        # Validate domain type
        valid_domain_types = ["data", "iso", "export"]
        if domain_type.lower() not in valid_domain_types:
            raise ValueError(f"Invalid domain type: {domain_type}, valid values: {valid_domain_types}")

        # Find the host
        hosts = self.connection.system_service().hosts_service().list(
            search=f"name={_sanitize_search_value(host)}"
        )
        if not hosts:
            raise ValueError(f"Host not found: {host}")

        sds_service = self.connection.system_service().storage_domains_service()

        # Check whether the storage domain already exists
        existing = sds_service.list(search=f"name={_sanitize_search_value(name)}")
        if existing:
            raise ValueError(f"Storage domain already exists: {name}")

        try:
            # Build different storage configuration based on storage type
            if storage_type.lower() == "nfs":
                storage = sdk.types.HostStorage(
                    type=sdk.types.StorageType.NFS,
                    address=path.split(":")[0] if ":" in path else path,
                    path=path.split(":")[1] if ":" in path else "",
                )
            elif storage_type.lower() == "localfs":
                storage = sdk.types.HostStorage(
                    type=sdk.types.StorageType.LOCALFS,
                    path=path,
                )
            else:
                storage = sdk.types.HostStorage(
                    type=sdk.types.StorageType(storage_type.upper()),
                    address=path,
                )

            sd = sds_service.add(
                sdk.types.StorageDomain(
                    name=name,
                    description=description,
                    type=sdk.types.StorageDomainType(domain_type.upper()),
                    storage=storage,
                    host=sdk.types.Host(id=hosts[0].id),
                    data_center=sdk.types.DataCenter(
                        name=datacenter
                    ) if datacenter else None,
                )
            )
            return {
                "success": True,
                "message": f"Storage domain {name} created",
                "storage_domain_id": sd.id,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to create storage domain: {e}")

    @require_connection
    def delete_storage_domain(self, name_or_id: str, force: bool = False) -> Dict[str, Any]:
        """Delete a storage domain."""
        sd = self._find_storage_domain(name_or_id)
        if not sd:
            raise ValueError(f"Storage domain not found: {name_or_id}")

        sd_service = self.connection.system_service().storage_domains_service().storage_domain_service(sd.id)

        try:
            sd_service.remove(force=force)
            return {"success": True, "message": f"Storage domain {sd.name} deleted"}
        except Exception as e:
            raise RuntimeError(f"Failed to delete storage domain: {e}")

    @require_connection
    def detach_storage_domain(self, name_or_id: str, datacenter: str = None) -> Dict[str, Any]:
        """Detach a storage domain from a data center."""
        sd = self._find_storage_domain(name_or_id)
        if not sd:
            raise ValueError(f"Storage domain not found: {name_or_id}")

        # Get the data center
        if not datacenter and sd.storage and sd.storage.data_center:
            datacenter = sd.storage.data_center.name

        if not datacenter:
            raise ValueError("Data center name is required")

        dc = self._find_datacenter(datacenter)
        if not dc:
            raise ValueError(f"Data center not found: {datacenter}")

        try:
            # Detach via the data center's storage domain service
            dc_service = self.connection.system_service().data_centers_service().data_center_service(dc.id)
            sd_service = dc_service.storage_domains_service().storage_domain_service(sd.id)
            sd_service.remove()

            return {"success": True, "message": f"Storage domain {sd.name} detached from data center {datacenter}"}
        except Exception as e:
            raise RuntimeError(f"Failed to detach storage domain: {e}")

    @require_connection
    def attach_storage_domain(self, name_or_id: str, datacenter: str) -> Dict[str, Any]:
        """Attach a storage domain to a data center."""
        sd = self._find_storage_domain(name_or_id)
        if not sd:
            raise ValueError(f"Storage domain not found: {name_or_id}")

        dc = self._find_datacenter(datacenter)
        if not dc:
            raise ValueError(f"Data center not found: {datacenter}")

        try:
            dc_service = self.connection.system_service().data_centers_service().data_center_service(dc.id)
            sd_service = dc_service.storage_domains_service()

            sd_service.add(
                sdk.types.StorageDomain(id=sd.id)
            )

            return {"success": True, "message": f"Storage domain {sd.name} attached to data center {datacenter}"}
        except Exception as e:
            raise RuntimeError(f"Failed to attach storage domain: {e}")

    @require_connection
    def get_storage_domain_stats(self, name_or_id: str) -> Dict[str, Any]:
        """Get storage domain statistics."""
        sd = self._find_storage_domain(name_or_id)
        if not sd:
            raise ValueError(f"Storage domain not found: {name_or_id}")

        available = sd.available or 0
        used = sd.used or 0
        total = available + used

        return {
            "id": sd.id,
            "name": sd.name,
            "type": str(sd.type.value) if sd.type else "data",
            "status": str(sd.status.value) if sd.status else "unknown",
            "available_gb": int(available / (1024**3)),
            "used_gb": int(used / (1024**3)),
            "total_gb": int(total / (1024**3)),
            "usage_percent": round(used / total * 100, 2) if total > 0 else 0,
            "master": sd.master if hasattr(sd, 'master') else False,
        }

    @require_connection
    def refresh_storage_domain(self, name_or_id: str) -> Dict[str, Any]:
        """Refresh a storage domain.

        Args:
            name_or_id: Storage domain name or ID

        Returns:
            Refresh result
        """
        sd = self._find_storage_domain(name_or_id)
        if not sd:
            raise ValueError(f"Storage domain not found: {name_or_id}")

        sd_service = self.connection.system_service().storage_domains_service().storage_domain_service(sd.id)

        try:
            sd_service.refresh()
            return {"success": True, "message": f"Refresh task started for storage domain {sd.name}"}
        except Exception as e:
            raise RuntimeError(f"Failed to refresh storage domain: {e}")

    @require_connection
    def update_storage_domain(self, name_or_id: str, new_name: str = None,
                             description: str = None,
                             warning_low_space: int = None,
                             critical_low_space: int = None) -> Dict[str, Any]:
        """Update a storage domain.

        Args:
            name_or_id: Storage domain name or ID
            new_name: New name
            description: New description
            warning_low_space: Low space warning threshold (GB)
            critical_low_space: Critical space threshold (GB)

        Returns:
            Update result
        """
        sd = self._find_storage_domain(name_or_id)
        if not sd:
            raise ValueError(f"Storage domain not found: {name_or_id}")

        sd_service = self.connection.system_service().storage_domains_service().storage_domain_service(sd.id)

        if new_name:
            sd.name = new_name
        if description is not None:
            sd.description = description
        if warning_low_space is not None:
            sd.warning_low_space_indicator = warning_low_space * 1024**3
        if critical_low_space is not None:
            sd.critical_space_action_blocker = critical_low_space * 1024**3

        try:
            sd_service.update(sd)
            return {"success": True, "message": f"Storage domain updated"}
        except Exception as e:
            raise RuntimeError(f"Failed to update storage domain: {e}")

    @require_connection
    def list_storage_files(self, name_or_id: str) -> List[Dict]:
        """List storage domain files.

        Args:
            name_or_id: Storage domain name or ID

        Returns:
            List of files
        """
        sd = self._find_storage_domain(name_or_id)
        if not sd:
            raise ValueError(f"Storage domain not found: {name_or_id}")

        sd_service = self.connection.system_service().storage_domains_service().storage_domain_service(sd.id)
        files_service = sd_service.files_service()

        try:
            files = files_service.list()
        except Exception as e:
            logger.error(f"Failed to get storage domain files: {e}")
            return []

        return [
            {
                "id": f.id,
                "name": f.name,
                "size": f.size if hasattr(f, 'size') else 0,
            }
            for f in files
        ]

    @require_connection
    def list_storage_connections(self, name_or_id: str = None) -> List[Dict]:
        """List storage connections.

        Args:
            name_or_id: Storage domain name or ID(optional; list all if omitted)

        Returns:
            List of storage connections
        """
        if name_or_id:
            # scope to one storage domain — its connections are served by the
            # domain service, not by the system-level collection
            sd = self._find_storage_domain(name_or_id)
            if not sd:
                raise ValueError(f"Storage domain not found: {name_or_id}")
            sd_service = (
                self.connection.system_service()
                .storage_domains_service()
                .storage_domain_service(sd.id)
            )
            connections_service = sd_service.storage_connections_service()
        else:
            connections_service = self.connection.system_service().storage_connections_service()

        try:
            connections = connections_service.list()
        except Exception as e:
            logger.error(f"Failed to get storage connections: {e}")
            return []

        return [
            {
                "id": c.id,
                "address": c.address if hasattr(c, 'address') else "",
                "type": str(c.type.value) if hasattr(c, 'type') and c.type else "",
                "path": c.path if getattr(c, "path", None) else "",
                # live payloads leave `port` as None — don't leak it into output
                "port": c.port if getattr(c, "port", None) is not None else "",
                "mount_options": c.mount_options if getattr(c, "mount_options", None) else "",
                "nfs_version": str(c.nfs_version.value) if hasattr(c, 'nfs_version') and c.nfs_version else "",
            }
            for c in connections
        ]

    @require_connection
    def list_available_disks(self, name_or_id: str) -> List[Dict]:
        """List available disks on a storage domain.

        Args:
            name_or_id: Storage domain name or ID

        Returns:
            List of available disks
        """
        sd = self._find_storage_domain(name_or_id)
        if not sd:
            raise ValueError(f"Storage domain not found: {name_or_id}")

        sd_service = self.connection.system_service().storage_domains_service().storage_domain_service(sd.id)
        disks_service = sd_service.disks_service()

        try:
            disks = disks_service.list()
        except Exception as e:
            logger.error(f"Failed to get available disks: {e}")
            return []

        return [
            {
                "id": d.id,
                "name": d.name,
                "size_gb": int((d.provisioned_size or 0) / (1024**3)),
                "actual_size_gb": int((d.actual_size or 0) / (1024**3)),
                "format": str(d.format.value) if d.format else "cow",
                "status": str(d.status.value) if d.status else "ok",
                "sparse": d.sparse if hasattr(d, 'sparse') else True,
            }
            for d in disks
        ]

    @require_connection
    def list_export_vms(self, name_or_id: str) -> List[Dict]:
        """List VMs on an export domain.

        Args:
            name_or_id: Export domain name or ID

        Returns:
            List of VMs
        """
        sd = self._find_storage_domain(name_or_id)
        if not sd:
            raise ValueError(f"Storage domain not found: {name_or_id}")

        # Check that this is an export domain
        if sd.type and sd.type.value != "export":
            raise ValueError("This storage domain is not an export domain")

        sd_service = self.connection.system_service().storage_domains_service().storage_domain_service(sd.id)
        vms_service = sd_service.vms_service()

        try:
            vms = vms_service.list()
        except Exception as e:
            logger.error(f"Failed to list exported VMs: {e}")
            return []

        return [
            {
                "id": vm.id,
                "name": vm.name,
                "description": vm.description or "",
                "memory_mb": int(vm.memory / (1024**2)) if vm.memory else 0,
                "cpu_cores": vm.cpu.topology.cores if vm.cpu and vm.cpu.topology else 0,
                "os_type": vm.os.type if vm.os else "",
            }
            for vm in vms
        ]

    @require_connection
    def import_vm_from_export(self, name_or_id: str, vm_name: str,
                             cluster: str, storage_domain: str = None,
                             clone: bool = False) -> Dict[str, Any]:
        """Import a VM from an export domain.

        Args:
            name_or_id: Export domain name or ID
            vm_name: VM name to import
            cluster: Target cluster
            storage_domain: Target storage domain (optional)
            clone: Whether to clone

        Returns:
            Import result
        """
        sd = self._find_storage_domain(name_or_id)
        if not sd:
            raise ValueError(f"Storage domain not found: {name_or_id}")

        # Find the cluster
        clusters = self.connection.system_service().clusters_service().list(
            search=f"name={_sanitize_search_value(cluster)}"
        )
        if not clusters:
            raise ValueError(f"Cluster not found: {cluster}")

        sd_service = self.connection.system_service().storage_domains_service().storage_domain_service(sd.id)
        vms_service = sd_service.vms_service()

        # Find the VM to import
        vms = vms_service.list(search=f"name={_sanitize_search_value(vm_name)}")
        if not vms:
            raise ValueError(f"VM not found in export domain: {vm_name}")

        vm = vms[0]
        vm_service = vms_service.vm_service(vm.id)

        try:
            # Import the VM
            import_params = sdk.types.Vm(
                cluster=sdk.types.Cluster(id=clusters[0].id),
            )
            if storage_domain:
                sd_target = self._find_storage_domain(storage_domain)
                if sd_target:
                    import_params.placement_policy = sdk.types.VmPlacementPolicy(
                        host=sdk.types.Host(id=sd_target.id)
                    )

            result = vm_service.import_(
                storage_domain=sdk.types.StorageDomain(id=sd.id) if storage_domain else None,
                cluster=sdk.types.Cluster(id=clusters[0].id),
                clone=clone,
            )

            return {
                "success": True,
                "message": f"Import task started for VM {vm_name}",
                "vm_id": vm.id,
                "cluster": cluster,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to import VM: {e}")

    @require_connection
    def list_disk_snapshots(self, disk_name_or_id: str) -> List[Dict]:
        """List disk snapshots.

        Args:
            disk_name_or_id: Disk name or ID

        Returns:
            List of disk snapshots
        """
        # Find the disk
        disks_service = self.connection.system_service().disks_service()

        disk_id = None
        try:
            disk = disks_service.disk_service(disk_name_or_id).get()
            disk_id = disk_name_or_id
        except Exception:
            disks = disks_service.list(search=f"name={_sanitize_search_value(disk_name_or_id)}")
            if not disks:
                raise ValueError(f"Disk not found: {disk_name_or_id}")
            disk_id = disks[0].id

        disk_service = disks_service.disk_service(disk_id)
        snapshots_service = disk_service.disk_snapshots_service()

        try:
            snapshots = snapshots_service.list()
        except Exception as e:
            logger.error(f"Failed to get disk snapshots: {e}")
            return []

        return [
            {
                "id": s.id,
                "description": s.description if hasattr(s, 'description') else "",
                "size_gb": int((s.provisioned_size or 0) / (1024**3)),
                "creation_time": str(s.creation_time) if hasattr(s, 'creation_time') else "",
                "status": str(s.status.value) if s.status else "ok",
            }
            for s in snapshots
        ]

    @require_connection
    def list_iscsi_bonds(self) -> List[Dict]:
        """List iSCSI bonds.

        Returns:
            List of iSCSI bonds
        """
        # iSCSI bonds are data-center-scoped; SystemService has no
        # ``iscsi_bonds_service`` (the old lookup crashed with AttributeError).
        dcs_service = self.connection.system_service().data_centers_service()

        result = []
        for dc in dcs_service.list():
            try:
                bonds = dcs_service.data_center_service(dc.id).iscsi_bonds_service().list()
            except Exception as e:
                logger.error(f"Failed to list iSCSI bonds: {e}")
                continue

            for b in bonds:
                result.append({
                    "id": b.id,
                    "name": b.name,
                    "description": b.description if hasattr(b, 'description') else "",
                    "data_center": self._data_center_name(b.data_center) or dc.name,
                })

        return result


# MCP tool registry
MCP_TOOLS = {
    "storage_get": {"method": "get_storage_domain", "description": "Get storage domain details"},
    "storage_create": {"method": "create_storage_domain", "description": "Create storage domain"},
    "storage_delete": {"method": "delete_storage_domain", "description": "Delete storage domain"},
    "storage_detach": {"method": "detach_storage_domain", "description": "Detach storage domain"},
    "storage_attach_to_dc": {"method": "attach_storage_domain", "description": "Attach storage domain to data center"},
    "storage_stats": {"method": "get_storage_domain_stats", "description": "Get storage domain statistics"},

    # New tools
    "storage_refresh": {"method": "refresh_storage_domain", "description": "Refresh storage domain"},
    "storage_update": {"method": "update_storage_domain", "description": "Update storage domain configuration"},
    "storage_files": {"method": "list_storage_files", "description": "List storage domain files"},
    "storage_connections_list": {"method": "list_storage_connections", "description": "List storage connections"},
    "storage_available_disks": {"method": "list_available_disks", "description": "List available disks on storage domain"},
    "storage_export_vms": {"method": "list_export_vms", "description": "List VMs on export domain"},
    "storage_import_vm": {"method": "import_vm_from_export", "description": "Import VM from export domain"},
    "disk_snapshot_list": {"method": "list_disk_snapshots", "description": "List disk snapshots"},
    "iscsi_bond_list": {"method": "list_iscsi_bonds", "description": "List iSCSI bonds"},
}
