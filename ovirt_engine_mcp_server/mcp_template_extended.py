#!/usr/bin/env python3
"""
oVirt MCP Server - Template extensions module
Provides template details, create, delete, update and disk, NIC, instance type management features
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


class TemplateExtendedMCP(BaseMCP):
    """Template extended management MCP"""

    def __init__(self, ovirt_mcp):
        super().__init__(ovirt_mcp)

    def _template_disks(self, template_id: str) -> List[Dict]:
        """Disk attachments of a template.

        ``Template`` / ``DiskAttachment`` expose no ``*_service()`` methods in
        ovirtsdk4 4.6 — the sub-collections must be reached through services.
        The old object-based calls raised ``AttributeError`` inside the
        caller's broad ``except``, so templates always reported zero disks.
        """
        disks: List[Dict] = []
        try:
            attachments = (
                self.connection.system_service()
                .templates_service()
                .template_service(template_id)
                .disk_attachments_service()
                .list()
            )
        except Exception as e:
            logger.debug(f"Failed to get template disk attachments: {e}")
            return disks

        disks_service = self.connection.system_service().disks_service()
        for da in attachments:
            try:
                disk = disks_service.disk_service(da.disk.id).get()
            except Exception as e:
                logger.debug(f"Failed to get template disk details: {e}")
                continue
            storage_domains = getattr(disk, "storage_domains", None) or []
            sd = storage_domains[0] if storage_domains else None
            fmt = getattr(disk, "storage_format", None) or getattr(
                disk, "format", None
            )
            disks.append({
                "id": disk.id,
                "name": getattr(disk, "alias", None) or disk.id,
                "size_gb": int((disk.provisioned_size or 0) / (1024**3)),
                "actual_size_gb": int((disk.actual_size or 0) / (1024**3)),
                "format": str(fmt.value) if fmt else "cow",
                "storage_domain": self._storage_domain_name(sd),
                "interface": str(da.interface.value) if da.interface else "virtio",
                "bootable": bool(da.bootable),
            })
        return disks

    def _template_nics(self, template_id: str) -> List[Dict]:
        """NICs of a template (see ``_template_disks`` for the caveat)."""
        nics: List[Dict] = []
        try:
            nic_list = (
                self.connection.system_service()
                .templates_service()
                .template_service(template_id)
                .nics_service()
                .list()
            )
        except Exception as e:
            logger.debug(f"Failed to get template NICs: {e}")
            return nics

        for n in nic_list:
            vnic_profile = getattr(n, "vnic_profile", None)
            profile_obj = self._link_obj("vnic_profile", vnic_profile)
            network_ref = getattr(n, "network", None)
            if not network_ref and profile_obj is not None:
                network_ref = getattr(profile_obj, "network", None)
            if profile_obj is not None and profile_obj.name:
                profile_name = profile_obj.name
            else:
                profile_name = getattr(vnic_profile, "name", None) or ""
            nics.append({
                "id": n.id,
                "name": n.name,
                "mac": n.mac.address if n.mac else "",
                "network": self._network_name(network_ref),
                "interface": str(n.interface.value) if n.interface else "virtio",
                "linked": bool(n.linked),
                "vnic_profile": profile_name,
            })
        return nics

    @require_connection
    def get_template(self, name_or_id: str) -> Optional[Dict]:
        """Get template details

        Args:
            name_or_id: Template name or ID

        Returns:
            Template details
        """
        template = self._find_template(name_or_id)
        if not template:
            return None

        disks = self._template_disks(template.id)
        nics = self._template_nics(template.id)

        return {
            "id": template.id,
            "name": template.name,
            "description": template.description or "",
            "memory_mb": int(template.memory / (1024**2)) if template.memory else 0,
            "cpu_cores": template.cpu.topology.cores if template.cpu and template.cpu.topology else 0,
            "cpu_sockets": template.cpu.topology.sockets if template.cpu and template.cpu.topology else 1,
            "cpu_threads": template.cpu.topology.threads if template.cpu and template.cpu.topology else 1,
            "os_type": template.os.type if template.os else "",
            "cluster": self._cluster_name(template.cluster),
            "cluster_id": template.cluster.id if template.cluster else "",
            "status": str(template.status.value) if template.status else "ok",
            "disks": disks,
            "nics": nics,
            "creation_time": str(template.creation_time) if template.creation_time else "",
            "bios_type": str(template.bios.type.value) if template.bios else "",
        }

    @require_connection
    def create_template(self, name: str, vm: str, description: str = "",
                       cluster: str = None) -> Dict[str, Any]:
        """Create a template from a VM

        Args:
            name: Template name
            vm: Source VM name or ID
            description: Description
            cluster: Target cluster (optional)

        Returns:
            Creation result
        """
        # Find VM
        vm_obj = self._find_vm(vm)
        if not vm_obj:
            raise ValueError(f"VM not found: {vm}")

        vms_service = self.connection.system_service().vms_service()
        vm_service = vms_service.vm_service(vm_obj.id)

        # Build template
        template_params = sdk.types.Template(
            name=name,
            description=description,
        )

        if cluster:
            cluster_obj = self._find_cluster(cluster)
            if cluster_obj:
                template_params.cluster = sdk.types.Cluster(id=cluster_obj.id)

        try:
            template = vm_service.export(template_params)

            return {
                "success": True,
                "message": f"Template {name} is being created",
                "template_id": template.id,
                "source_vm": vm_obj.name,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to create template: {e}")

    @require_connection
    def delete_template(self, name_or_id: str, force: bool = False) -> Dict[str, Any]:
        """Delete a template

        Args:
            name_or_id: Template name or ID
            force: Force delete

        Returns:
            Deletion result
        """
        template = self._find_template(name_or_id)
        if not template:
            raise ValueError(f"Template not found: {name_or_id}")

        # Cannot delete the Blank template
        if template.name.lower() == "blank":
            raise ValueError("Cannot delete the Blank template")

        templates_service = self.connection.system_service().templates_service()
        template_service = templates_service.template_service(template.id)

        try:
            template_service.remove(force=force)
            return {"success": True, "message": f"Template {template.name} deleted"}
        except Exception as e:
            raise RuntimeError(f"Failed to delete template: {e}")

    @require_connection
    def update_template(self, name_or_id: str, new_name: str = None,
                       description: str = None, memory_mb: int = None,
                       cpu_cores: int = None) -> Dict[str, Any]:
        """Update a template

        Args:
            name_or_id: Template name or ID
            new_name: New name
            description: New description
            memory_mb: Memory (MB)
            cpu_cores: CPU cores

        Returns:
            Update result
        """
        template = self._find_template(name_or_id)
        if not template:
            raise ValueError(f"Template not found: {name_or_id}")

        templates_service = self.connection.system_service().templates_service()
        template_service = templates_service.template_service(template.id)

        # Update properties
        if new_name:
            template.name = new_name
        if description is not None:
            template.description = description
        if memory_mb is not None:
            template.memory = memory_mb * 1024 * 1024
        if cpu_cores is not None and template.cpu:
            template.cpu.topology.cores = cpu_cores

        try:
            template_service.update(template)
            return {"success": True, "message": f"Template updated"}
        except Exception as e:
            raise RuntimeError(f"Failed to update template: {e}")

    @require_connection
    def list_template_disks(self, name_or_id: str) -> List[Dict]:
        """List template disks

        Args:
            name_or_id: Template name or ID

        Returns:
            Disk list
        """
        template = self._find_template(name_or_id)
        if not template:
            raise ValueError(f"Template not found: {name_or_id}")

        return self._template_disks(template.id)

    @require_connection
    def list_template_nics(self, name_or_id: str) -> List[Dict]:
        """List template NICs

        Args:
            name_or_id: Template name or ID

        Returns:
            NIC list
        """
        template = self._find_template(name_or_id)
        if not template:
            raise ValueError(f"Template not found: {name_or_id}")

        return self._template_nics(template.id)

    # -- Instance Type management --------------------------------------------------

    @require_connection
    def list_instance_types(self) -> List[Dict]:
        """List instance types

        Returns:
            List of instance types
        """
        instance_types_service = self.connection.system_service().instance_types_service()

        try:
            types = instance_types_service.list()
        except Exception as e:
            logger.error(f"Failed to get instance type list: {e}")
            return []

        return [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description or "",
                "memory_mb": int(t.memory / (1024**2)) if t.memory else 0,
                "cpu_cores": t.cpu.topology.cores if t.cpu and t.cpu.topology else 0,
                "cpu_sockets": t.cpu.topology.sockets if t.cpu and t.cpu.topology else 1,
            }
            for t in types
        ]

    @require_connection
    def get_instance_type(self, name_or_id: str) -> Optional[Dict]:
        """Get instance type details

        Args:
            name_or_id: Instance type name or ID

        Returns:
            Instance type details
        """
        instance_types_service = self.connection.system_service().instance_types_service()

        # Try to get by ID
        try:
            it = instance_types_service.instance_type_service(name_or_id).get()
            if it:
                return self._format_instance_type(it)
        except Exception:
            pass

        # Search by name
        types = instance_types_service.list(search=f"name={_sanitize_search_value(name_or_id)}")
        if not types:
            return None

        return self._format_instance_type(types[0])

    def _format_instance_type(self, it) -> Dict:
        """Format instance type"""
        return {
            "id": it.id,
            "name": it.name,
            "description": it.description or "",
            "memory_mb": int(it.memory / (1024**2)) if it.memory else 0,
            "cpu_cores": it.cpu.topology.cores if it.cpu and it.cpu.topology else 0,
            "cpu_sockets": it.cpu.topology.sockets if it.cpu and it.cpu.topology else 1,
            "cpu_threads": it.cpu.topology.threads if it.cpu and it.cpu.topology else 1,
            "os_type": it.os.type if it.os else "",
            "bios_type": str(it.bios.type.value) if it.bios else "",
        }


# MCP tool registry
MCP_TOOLS = {
    # Template management
    "template_get": {"method": "get_template", "description": "Get template details"},
    "template_create": {"method": "create_template", "description": "Create a template from a VM"},
    "template_delete": {"method": "delete_template", "description": "Delete a template"},
    "template_update": {"method": "update_template", "description": "Update a template"},

    # Template disks and NICs
    "template_disk_list": {"method": "list_template_disks", "description": "List template disks"},
    "template_nic_list": {"method": "list_template_nics", "description": "List template NICs"},

    # Instance types
    "instance_type_list": {"method": "list_instance_types", "description": "List instance types"},
    "instance_type_get": {"method": "get_instance_type", "description": "Get instance type details"},
}
