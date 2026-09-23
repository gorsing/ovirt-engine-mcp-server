#!/usr/bin/env python3
"""
oVirt MCP Server - disk extension module
Provides disk details, deletion, resize, and detach operations
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


class DiskExtendedMCP(BaseMCP):
    """Disk extension management MCP"""

    def __init__(self, ovirt_mcp):
        super().__init__(ovirt_mcp)

    @require_connection
    def get_disk(self, name_or_id: str) -> Optional[Dict]:
        """Get disk details"""
        disk = self._find_disk(name_or_id)
        if not disk:
            return None

        # Get disk attachment info
        # oVirt has no system-level disk_attachments_service, and
        # ``Disk.vms`` is what tells us where the disk is attached (it comes
        # back empty on some engines — then we simply report no attachments).
        attachments = []
        for vm_ref in getattr(disk, "vms", None) or []:
            try:
                vm_attachments = (
                    self.connection.system_service()
                    .vms_service()
                    .vm_service(vm_ref.id)
                    .disk_attachments_service()
                    .list()
                )
            except Exception as e:
                logger.debug(f"Failed to get disk attachments for VM {vm_ref.id}: {e}")
                continue
            for att in vm_attachments:
                if not att.disk or att.disk.id != disk.id:
                    continue
                attachments.append({
                    "vm_id": vm_ref.id,
                    "vm_name": self._vm_name(vm_ref),
                    "active": bool(getattr(att, "active", False)),
                    "bootable": bool(getattr(att, "bootable", False)),
                    "interface": str(att.interface.value) if att.interface else "virtio",
                })

        # ``Disk.storage_domain`` is None on live engines; the populated
        # reference is ``storage_domains`` (and it carries an id, not a name).
        storage_domains = getattr(disk, "storage_domains", None) or []
        storage_domain = storage_domains[0] if storage_domains else None

        return {
            "id": disk.id,
            "name": disk.name,
            "description": disk.description or "",
            "status": str(disk.status.value) if disk.status else "unknown",
            "provisioned_size_gb": int((disk.provisioned_size or 0) / (1024**3)),
            "actual_size_gb": int((disk.actual_size or 0) / (1024**3)),
            "format": str(disk.format.value) if disk.format else "cow",
            "storage_type": str(disk.storage_type.value) if disk.storage_type else "image",
            "sparse": disk.sparse if hasattr(disk, 'sparse') else True,
            "interface": str(disk.interface.value) if disk.interface else "virtio",
            "storage_domain": self._storage_domain_name(storage_domain),
            "storage_domain_id": storage_domain.id if storage_domain else "",
            "shareable": disk.shareable if hasattr(disk, 'shareable') else False,
            "wipe_after_delete": disk.wipe_after_delete if hasattr(disk, 'wipe_after_delete') else False,
            "propagate_errors": disk.propagate_errors if hasattr(disk, 'propagate_errors') else False,
            "qcow_version": str(disk.qcow_version.value) if hasattr(disk, 'qcow_version') and disk.qcow_version else "",
            "attachments": attachments[:10],  # Limit the count
        }

    @require_connection
    def delete_disk(self, name_or_id: str, force: bool = False) -> Dict[str, Any]:
        """Delete a disk"""
        disk = self._find_disk(name_or_id)
        if not disk:
            raise ValueError(f"Disk not found: {name_or_id}")

        # Check the disk status
        if disk.status and disk.status.value != "ok" and not force:
            raise RuntimeError(f"Disk status not ok: {disk.status.value}, use force=True to force deletion")

        disk_service = self.connection.system_service().disks_service().disk_service(disk.id)

        try:
            disk_service.remove()
            return {"success": True, "message": f"Disk {disk.name} deleted"}
        except Exception as e:
            raise RuntimeError(f"Failed to delete disk: {e}")

    @require_connection
    def resize_disk(self, name_or_id: str, new_size_gb: int) -> Dict[str, Any]:
        """Resize a disk"""
        if new_size_gb <= 0:
            raise ValueError("Disk size must be greater than 0")

        disk = self._find_disk(name_or_id)
        if not disk:
            raise ValueError(f"Disk not found: {name_or_id}")

        current_size_gb = int((disk.provisioned_size or 0) / (1024**3))

        # Expand only; shrinking is not allowed
        if new_size_gb < current_size_gb:
            raise ValueError(f"Cannot shrink disk: current {current_size_gb}GB, requested {new_size_gb}GB")

        disk_service = self.connection.system_service().disks_service().disk_service(disk.id)

        try:
            # Update the disk size
            updated_disk = sdk.types.Disk(
                id=disk.id,
                provisioned_size=new_size_gb * 1024**3,
            )
            disk_service.update(updated_disk)

            return {
                "success": True,
                "message": f"Disk {disk.name} size changed from {current_size_gb}GB to {new_size_gb}GB",
                "old_size_gb": current_size_gb,
                "new_size_gb": new_size_gb,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to resize disk: {e}")

    @require_connection
    def detach_disk(self, name_or_id: str, vm_name_or_id: str) -> Dict[str, Any]:
        """Detach a disk from a VM"""
        disk = self._find_disk(name_or_id)
        if not disk:
            raise ValueError(f"Disk not found: {name_or_id}")

        vm = self._find_vm(vm_name_or_id)
        if not vm:
            raise ValueError(f"VM not found: {vm_name_or_id}")

        try:
            # Get the VM's disk attachments
            vm_service = self.connection.system_service().vms_service().vm_service(vm.id)
            attachments_service = vm_service.disk_attachments_service()
            attachments = attachments_service.list()

            # Find the matching attachment
            attachment_id = None
            for att in attachments:
                if att.disk and att.disk.id == disk.id:
                    attachment_id = att.id
                    break

            if not attachment_id:
                raise ValueError(f"Disk {disk.name} is not attached to VM {vm.name}")

            # Detach the disk
            attachment_service = attachments_service.attachment_service(attachment_id)
            attachment_service.remove()

            return {
                "success": True,
                "message": f"Disk {disk.name} detached from VM {vm.name}",
            }
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to detach disk: {e}")

    @require_connection
    def move_disk(self, name_or_id: str, target_storage_domain: str) -> Dict[str, Any]:
        """Move a disk to another storage domain"""
        disk = self._find_disk(name_or_id)
        if not disk:
            raise ValueError(f"Disk not found: {name_or_id}")

        # Find the target storage domain
        sds = self.connection.system_service().storage_domains_service().list(
            search=f"name={_sanitize_search_value(target_storage_domain)}"
        )
        if not sds:
            raise ValueError(f"Storage domain not found: {target_storage_domain}")

        disk_service = self.connection.system_service().disks_service().disk_service(disk.id)

        try:
            # Perform the move
            disk_service.move(
                storage_domain=sdk.types.StorageDomain(id=sds[0].id)
            )

            return {
                "success": True,
                "message": f"Disk {disk.name} is moving to storage domain {target_storage_domain}",
            }
        except Exception as e:
            raise RuntimeError(f"Failed to move disk: {e}")

    @require_connection
    def get_disk_stats(self, name_or_id: str) -> Dict[str, Any]:
        """Get disk statistics"""
        disk = self._find_disk(name_or_id)
        if not disk:
            raise ValueError(f"Disk not found: {name_or_id}")

        provisioned = disk.provisioned_size or 0
        actual = disk.actual_size or 0

        return {
            "id": disk.id,
            "name": disk.name,
            "status": str(disk.status.value) if disk.status else "unknown",
            "provisioned_gb": int(provisioned / (1024**3)),
            "actual_gb": int(actual / (1024**3)),
            "used_percent": round(actual / provisioned * 100, 2) if provisioned > 0 else 0,
            "format": str(disk.format.value) if disk.format else "cow",
            "sparse": disk.sparse if hasattr(disk, 'sparse') else True,
        }

    @require_connection
    def update_disk(self, name_or_id: str, new_name: str = None,
                   description: str = None, shareable: bool = None,
                   wipe_after_delete: bool = None) -> Dict[str, Any]:
        """Update disk configuration

        Args:
            name_or_id: Disk name or ID
            new_name: New name
            description: New description
            shareable: Whether the disk can be shared
            wipe_after_delete: Wipe after delete

        Returns:
            Update result
        """
        disk = self._find_disk(name_or_id)
        if not disk:
            raise ValueError(f"Disk not found: {name_or_id}")

        disk_service = self.connection.system_service().disks_service().disk_service(disk.id)

        if new_name:
            disk.name = new_name
        if description is not None:
            disk.description = description
        if shareable is not None:
            disk.shareable = shareable
        if wipe_after_delete is not None:
            disk.wipe_after_delete = wipe_after_delete

        try:
            disk_service.update(disk)
            return {"success": True, "message": f"Disk configuration updated"}
        except Exception as e:
            raise RuntimeError(f"Failed to update disk: {e}")

    @require_connection
    def sparsify_disk(self, name_or_id: str) -> Dict[str, Any]:
        """Sparsify a disk (reclaim blank blocks)

        Args:
            name_or_id: Disk name or ID

        Returns:
            Operation result
        """
        disk = self._find_disk(name_or_id)
        if not disk:
            raise ValueError(f"Disk not found: {name_or_id}")

        # Check the disk format
        if disk.format and disk.format.value != "cow":
            raise ValueError("Only COW format disks support sparsify")

        disk_service = self.connection.system_service().disks_service().disk_service(disk.id)

        try:
            disk_service.sparsify()
            return {
                "success": True,
                "message": f"Sparsify task for disk {disk.name} started",
                "disk_id": disk.id,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to sparsify disk: {e}")

    @require_connection
    def export_disk(self, name_or_id: str, export_domain: str) -> Dict[str, Any]:
        """Export a disk to an export domain

        Args:
            name_or_id: Disk name or ID
            export_domain: Export domain name

        Returns:
            Export result
        """
        disk = self._find_disk(name_or_id)
        if not disk:
            raise ValueError(f"Disk not found: {name_or_id}")

        # Find the export domain
        sds = self.connection.system_service().storage_domains_service().list(
            search=f"name={_sanitize_search_value(export_domain)}"
        )
        if not sds:
            raise ValueError(f"Storage domain not found: {export_domain}")

        # Check that it is an export domain
        if sds[0].type and sds[0].type.value != "export":
            raise ValueError(f"Storage domain {export_domain} is not an export domain")

        disk_service = self.connection.system_service().disks_service().disk_service(disk.id)

        try:
            disk_service.export(
                storage_domain=sdk.types.StorageDomain(id=sds[0].id)
            )
            return {
                "success": True,
                "message": f"Export task for disk {disk.name} started",
                "disk_id": disk.id,
                "export_domain": export_domain,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to export disk: {e}")


# MCP tool registry
MCP_TOOLS = {
    "disk_get": {"method": "get_disk", "description": "Get disk details"},
    "disk_delete": {"method": "delete_disk", "description": "Delete a disk"},
    "disk_resize": {"method": "resize_disk", "description": "Resize a disk"},
    "disk_detach": {"method": "detach_disk", "description": "Detach a disk from a VM"},
    "disk_move": {"method": "move_disk", "description": "Move a disk to another storage domain"},
    "disk_stats": {"method": "get_disk_stats", "description": "Get disk statistics"},

    # New tools
    "disk_update": {"method": "update_disk", "description": "Update disk configuration"},
    "disk_sparsify": {"method": "sparsify_disk", "description": "Sparsify a disk (reclaim blank blocks)"},
    "disk_export": {"method": "export_disk", "description": "Export a disk to an export domain"},
}
