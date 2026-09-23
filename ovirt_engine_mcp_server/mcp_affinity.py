#!/usr/bin/env python3
"""
oVirt MCP Server - Affinity group management module
Provides creation and management of VM affinity groups
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


class AffinityMCP(BaseMCP):
    """Affinity group management MCP"""

    def __init__(self, ovirt_mcp):
        super().__init__(ovirt_mcp)

    def _find_affinity_label(self, name_or_id: str) -> Optional[Any]:
        """Find an affinity label"""
        labels_service = self.connection.system_service().affinity_labels_service()

        try:
            label = labels_service.affinity_label_service(name_or_id).get()
            if label:
                return label
        except Exception:
            pass

        labels = labels_service.list(search=f"name={_sanitize_search_value(name_or_id)}")
        return labels[0] if labels else None

    @require_connection
    def list_affinity_groups(self, cluster: str) -> List[Dict]:
        """List affinity groups in a cluster

        Args:
            cluster: Cluster name or ID

        Returns:
            List of affinity groups
        """
        cluster_obj = self._find_cluster(cluster)
        if not cluster_obj:
            raise ValueError(f"Cluster not found: {cluster}")

        cluster_service = self.connection.system_service().clusters_service().cluster_service(cluster_obj.id)
        affinity_groups_service = cluster_service.affinity_groups_service()

        try:
            groups = affinity_groups_service.list()
        except Exception as e:
            logger.error(f"Failed to get affinity groups: {e}")
            groups = []

        result = []
        for group in groups:
            # Get associated VMs
            vms = []
            if group.vms:
                vms = [{"id": vm.id, "name": vm.name} for vm in group.vms]

            result.append({
                "id": group.id,
                "name": group.name,
                "cluster_id": cluster_obj.id,
                "cluster_name": cluster_obj.name,
                "positive": group.positive if hasattr(group, 'positive') else True,
                "enforcing": group.enforcing if hasattr(group, 'enforcing') else False,
                "vms": vms,
                "vm_count": len(vms),
            })

        return result

    @require_connection
    def get_affinity_group(self, cluster: str, name_or_id: str) -> Optional[Dict]:
        """Get affinity group details"""
        cluster_obj = self._find_cluster(cluster)
        if not cluster_obj:
            raise ValueError(f"Cluster not found: {cluster}")

        cluster_service = self.connection.system_service().clusters_service().cluster_service(cluster_obj.id)
        affinity_groups_service = cluster_service.affinity_groups_service()

        # Find affinity group
        try:
            # Try to get by ID
            group_service = affinity_groups_service.affinity_group_service(name_or_id)
            group = group_service.get()
        except Exception:
            # Search by name
            groups = affinity_groups_service.list(search=f"name={_sanitize_search_value(name_or_id)}")
            if not groups:
                return None
            group = groups[0]

        # Get associated VMs
        vms = []
        if group.vms:
            vms = [
                {
                    "id": vm.id,
                    "name": vm.name,
                    "status": "",  # Requires an extra query
                }
                for vm in group.vms
            ]

        return {
            "id": group.id,
            "name": group.name,
            "cluster_id": cluster_obj.id,
            "cluster_name": cluster_obj.name,
            "positive": group.positive if hasattr(group, 'positive') else True,
            "enforcing": group.enforcing if hasattr(group, 'enforcing') else False,
            "vms": vms,
            "vm_count": len(vms),
            "description": "",  # affinity group has no description field
        }

    @require_connection
    def create_affinity_group(self, name: str, cluster: str,
                             positive: bool = True,
                             enforcing: bool = False,
                             vms: List[str] = None) -> Dict[str, Any]:
        """Create affinity group

        Args:
            name: Affinity group name
            cluster: Cluster name or ID
            positive: True=positive (same host), False=anti-affinity (different hosts)
            enforcing: True=enforce, False=permit
            vms: List of VM names or IDs

        Returns:
            Creation result
        """
        cluster_obj = self._find_cluster(cluster)
        if not cluster_obj:
            raise ValueError(f"Cluster not found: {cluster}")

        cluster_service = self.connection.system_service().clusters_service().cluster_service(cluster_obj.id)
        affinity_groups_service = cluster_service.affinity_groups_service()

        # Check if it already exists
        existing = affinity_groups_service.list(search=f"name={_sanitize_search_value(name)}")
        if existing:
            raise ValueError(f"Affinity group already exists: {name}")

        # Resolve the VM list
        vm_refs = []
        if vms:
            for vm_name in vms:
                vm = self._find_vm(vm_name)
                if vm:
                    vm_refs.append(sdk.types.Vm(id=vm.id))

        try:
            group = affinity_groups_service.add(
                sdk.types.AffinityGroup(
                    name=name,
                    positive=positive,
                    enforcing=enforcing,
                    vms=vm_refs if vm_refs else None,
                )
            )

            return {
                "success": True,
                "message": f"Affinity group {name} created",
                "affinity_group_id": group.id,
                "positive": positive,
                "enforcing": enforcing,
                "vm_count": len(vm_refs),
            }
        except Exception as e:
            raise RuntimeError(f"Failed to create affinity group: {e}")

    @require_connection
    def update_affinity_group(self, cluster: str, name_or_id: str,
                             new_name: str = None,
                             positive: bool = None,
                             enforcing: bool = None) -> Dict[str, Any]:
        """Update affinity group"""
        cluster_obj = self._find_cluster(cluster)
        if not cluster_obj:
            raise ValueError(f"Cluster not found: {cluster}")

        cluster_service = self.connection.system_service().clusters_service().cluster_service(cluster_obj.id)
        affinity_groups_service = cluster_service.affinity_groups_service()

        # Find affinity group
        group = None
        group_id = None
        try:
            group_service = affinity_groups_service.affinity_group_service(name_or_id)
            group = group_service.get()
            group_id = name_or_id
        except Exception:
            groups = affinity_groups_service.list(search=f"name={_sanitize_search_value(name_or_id)}")
            if not groups:
                raise ValueError(f"Affinity group not found: {name_or_id}")
            group = groups[0]
            group_id = group.id

        group_service = affinity_groups_service.affinity_group_service(group_id)

        # Update attributes
        if new_name:
            group.name = new_name
        if positive is not None:
            group.positive = positive
        if enforcing is not None:
            group.enforcing = enforcing

        try:
            group_service.update(group)
            return {"success": True, "message": f"Affinity group updated"}
        except Exception as e:
            raise RuntimeError(f"Failed to update affinity group: {e}")

    @require_connection
    def delete_affinity_group(self, cluster: str, name_or_id: str) -> Dict[str, Any]:
        """Delete affinity group"""
        cluster_obj = self._find_cluster(cluster)
        if not cluster_obj:
            raise ValueError(f"Cluster not found: {cluster}")

        cluster_service = self.connection.system_service().clusters_service().cluster_service(cluster_obj.id)
        affinity_groups_service = cluster_service.affinity_groups_service()

        # Find affinity group
        group_id = None
        group_name = None
        try:
            group_service = affinity_groups_service.affinity_group_service(name_or_id)
            group = group_service.get()
            group_id = name_or_id
            group_name = group.name
        except Exception:
            groups = affinity_groups_service.list(search=f"name={_sanitize_search_value(name_or_id)}")
            if not groups:
                raise ValueError(f"Affinity group not found: {name_or_id}")
            group_id = groups[0].id
            group_name = groups[0].name

        group_service = affinity_groups_service.affinity_group_service(group_id)

        try:
            group_service.remove()
            return {"success": True, "message": f"Affinity group {group_name} deleted"}
        except Exception as e:
            raise RuntimeError(f"Failed to delete affinity group: {e}")

    @require_connection
    def add_vm_to_affinity_group(self, cluster: str, affinity_group: str,
                                 vm: str) -> Dict[str, Any]:
        """Add a VM to an affinity group"""
        cluster_obj = self._find_cluster(cluster)
        if not cluster_obj:
            raise ValueError(f"Cluster not found: {cluster}")

        vm_obj = self._find_vm(vm)
        if not vm_obj:
            raise ValueError(f"VM not found: {vm}")

        cluster_service = self.connection.system_service().clusters_service().cluster_service(cluster_obj.id)
        affinity_groups_service = cluster_service.affinity_groups_service()

        # Find affinity group
        group_id = None
        try:
            group_service = affinity_groups_service.affinity_group_service(affinity_group)
            group = group_service.get()
            group_id = affinity_group
        except Exception:
            groups = affinity_groups_service.list(search=f"name={_sanitize_search_value(affinity_group)}")
            if not groups:
                raise ValueError(f"Affinity group not found: {affinity_group}")
            group_id = groups[0].id

        group_service = affinity_groups_service.affinity_group_service(group_id)
        vms_service = group_service.vms_service()

        try:
            vms_service.add(sdk.types.Vm(id=vm_obj.id))
            return {
                "success": True,
                "message": f"VM {vm_obj.name} added to affinity group",
            }
        except Exception as e:
            raise RuntimeError(f"Failed to add VM to affinity group: {e}")

    @require_connection
    def remove_vm_from_affinity_group(self, cluster: str, affinity_group: str,
                                      vm: str) -> Dict[str, Any]:
        """Remove a VM from an affinity group"""
        cluster_obj = self._find_cluster(cluster)
        if not cluster_obj:
            raise ValueError(f"Cluster not found: {cluster}")

        vm_obj = self._find_vm(vm)
        if not vm_obj:
            raise ValueError(f"VM not found: {vm}")

        cluster_service = self.connection.system_service().clusters_service().cluster_service(cluster_obj.id)
        affinity_groups_service = cluster_service.affinity_groups_service()

        # Find affinity group
        group_id = None
        try:
            group_service = affinity_groups_service.affinity_group_service(affinity_group)
            group = group_service.get()
            group_id = affinity_group
        except Exception:
            groups = affinity_groups_service.list(search=f"name={_sanitize_search_value(affinity_group)}")
            if not groups:
                raise ValueError(f"Affinity group not found: {affinity_group}")
            group_id = groups[0].id

        group_service = affinity_groups_service.affinity_group_service(group_id)
        vms_service = group_service.vms_service()
        vm_service = vms_service.vm_service(vm_obj.id)

        try:
            vm_service.remove()
            return {
                "success": True,
                "message": f"VM {vm_obj.name} removed from affinity group",
            }
        except Exception as e:
            raise RuntimeError(f"Failed to remove VM from affinity group: {e}")

    # -- Affinity Label management --------------------------------------------------

    @require_connection
    def list_affinity_labels(self) -> List[Dict]:
        """List affinity labels

        Returns:
            List of affinity labels
        """
        labels_service = self.connection.system_service().affinity_labels_service()

        try:
            labels = labels_service.list()
        except Exception as e:
            logger.error(f"Failed to get affinity labels: {e}")
            return []

        return [
            {
                "id": l.id,
                "name": l.name,
                "description": l.read_only if hasattr(l, 'read_only') else False,
                "vm_count": len(l.vms) if l.vms else 0,
                "host_count": len(l.hosts) if l.hosts else 0,
            }
            for l in labels
        ]

    @require_connection
    def get_affinity_label(self, name_or_id: str) -> Optional[Dict]:
        """Get affinity label details

        Args:
            name_or_id: Label name or ID

        Returns:
            Label details
        """
        label = self._find_affinity_label(name_or_id)
        if not label:
            return None

        # Get associated VMs
        vms = []
        if label.vms:
            vms = [
                {"id": vm.id, "name": vm.name}
                for vm in label.vms
            ]

        # Get associated hosts
        hosts = []
        if label.hosts:
            hosts = [
                {"id": h.id, "name": h.name}
                for h in label.hosts
            ]

        return {
            "id": label.id,
            "name": label.name,
            "read_only": label.read_only if hasattr(label, 'read_only') else False,
            "vms": vms,
            "vm_count": len(vms),
            "hosts": hosts,
            "host_count": len(hosts),
        }

    @require_connection
    def create_affinity_label(self, name: str) -> Dict[str, Any]:
        """Create affinity label

        Args:
            name: Label name

        Returns:
            Creation result
        """
        labels_service = self.connection.system_service().affinity_labels_service()

        # Check if it already exists
        existing = labels_service.list(search=f"name={_sanitize_search_value(name)}")
        if existing:
            raise ValueError(f"Affinity label already exists: {name}")

        try:
            label = labels_service.add(
                sdk.types.AffinityLabel(name=name)
            )

            return {
                "success": True,
                "message": f"Affinity label {name} created",
                "label_id": label.id,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to create affinity label: {e}")

    @require_connection
    def delete_affinity_label(self, name_or_id: str) -> Dict[str, Any]:
        """Delete affinity label

        Args:
            name_or_id: Label name or ID

        Returns:
            Deletion result
        """
        label = self._find_affinity_label(name_or_id)
        if not label:
            raise ValueError(f"Affinity label not found: {name_or_id}")

        labels_service = self.connection.system_service().affinity_labels_service()
        label_service = labels_service.affinity_label_service(label.id)

        try:
            label_service.remove()
            return {"success": True, "message": f"Affinity label {label.name} deleted"}
        except Exception as e:
            raise RuntimeError(f"Failed to delete affinity label: {e}")

    @require_connection
    def assign_affinity_label(self, label: str, resource_type: str,
                             resource: str) -> Dict[str, Any]:
        """Assign an affinity label to a resource

        Args:
            label: Label name or ID
            resource_type: Resource type (vm or host)
            resource: Resource name or ID

        Returns:
            Assignment result
        """
        if resource_type.lower() not in ["vm", "host"]:
            raise ValueError("resource_type must be 'vm' or 'host'")

        label_obj = self._find_affinity_label(label)
        if not label_obj:
            raise ValueError(f"Affinity label not found: {label}")

        labels_service = self.connection.system_service().affinity_labels_service()
        label_service = labels_service.affinity_label_service(label_obj.id)

        try:
            if resource_type.lower() == "vm":
                vm = self._find_vm(resource)
                if not vm:
                    raise ValueError(f"VM not found: {resource}")
                vms_service = label_service.vms_service()
                vms_service.add(sdk.types.Vm(id=vm.id))
            else:
                host = self._find_host(resource)
                if not host:
                    raise ValueError(f"Host not found: {resource}")
                hosts_service = label_service.hosts_service()
                hosts_service.add(sdk.types.Host(id=host.id))

            return {
                "success": True,
                "message": f"Affinity label {label_obj.name} assigned to {resource_type}",
            }
        except Exception as e:
            raise RuntimeError(f"Failed to assign affinity label: {e}")

    @require_connection
    def unassign_affinity_label(self, label: str, resource_type: str,
                               resource: str) -> Dict[str, Any]:
        """Remove an affinity label from a resource

        Args:
            label: Label name or ID
            resource_type: Resource type (vm or host)
            resource: Resource name or ID

        Returns:
            Removal result
        """
        if resource_type.lower() not in ["vm", "host"]:
            raise ValueError("resource_type must be 'vm' or 'host'")

        label_obj = self._find_affinity_label(label)
        if not label_obj:
            raise ValueError(f"Affinity label not found: {label}")

        labels_service = self.connection.system_service().affinity_labels_service()
        label_service = labels_service.affinity_label_service(label_obj.id)

        try:
            if resource_type.lower() == "vm":
                vm = self._find_vm(resource)
                if not vm:
                    raise ValueError(f"VM not found: {resource}")
                vms_service = label_service.vms_service()
                vm_service = vms_service.vm_service(vm.id)
                vm_service.remove()
            else:
                host = self._find_host(resource)
                if not host:
                    raise ValueError(f"Host not found: {resource}")
                hosts_service = label_service.hosts_service()
                host_service = hosts_service.host_service(host.id)
                host_service.remove()

            return {
                "success": True,
                "message": f"Affinity label {label_obj.name} removed from {resource_type}",
            }
        except Exception as e:
            raise RuntimeError(f"Failed to remove affinity label: {e}")


# MCP tool registry
MCP_TOOLS = {
    # Affinity groups
    "affinity_group_list": {"method": "list_affinity_groups", "description": "List affinity groups"},
    "affinity_group_get": {"method": "get_affinity_group", "description": "Get affinity group details"},
    "affinity_group_create": {"method": "create_affinity_group", "description": "Create affinity group"},
    "affinity_group_update": {"method": "update_affinity_group", "description": "Update affinity group"},
    "affinity_group_delete": {"method": "delete_affinity_group", "description": "Delete affinity group"},
    "affinity_group_add_vm": {"method": "add_vm_to_affinity_group", "description": "Add VM to affinity group"},
    "affinity_group_remove_vm": {"method": "remove_vm_from_affinity_group", "description": "Remove a VM from an affinity group"},

    # Affinity labels
    "affinity_label_list": {"method": "list_affinity_labels", "description": "List affinity labels"},
    "affinity_label_get": {"method": "get_affinity_label", "description": "Get affinity label details"},
    "affinity_label_create": {"method": "create_affinity_label", "description": "Create affinity label"},
    "affinity_label_delete": {"method": "delete_affinity_label", "description": "Delete affinity label"},
    "affinity_label_assign": {"method": "assign_affinity_label", "description": "Assign an affinity label to a resource"},
    "affinity_label_unassign": {"method": "unassign_affinity_label", "description": "Remove an affinity label from a resource"},
}
