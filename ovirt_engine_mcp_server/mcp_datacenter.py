#!/usr/bin/env python3
"""
oVirt MCP Server - data center management module
Provides CRUD operations for data centers
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


class DataCenterMCP(BaseMCP):
    """Data center management MCP"""

    def __init__(self, ovirt_mcp):
        super().__init__(ovirt_mcp)

    @require_connection
    def list_datacenters(self) -> List[Dict]:
        """List all data centers"""
        dcs_service = self.connection.system_service().data_centers_service()
        dcs = dcs_service.list()

        result = []
        for dc in dcs:
            result.append({
                "id": dc.id,
                "name": dc.name,
                "description": dc.description or "",
                "status": str(dc.status.value) if dc.status else "unknown",
                "storage_type": str(dc.storage_type.value) if getattr(dc, "storage_type", None) else "nfs",
                "version": f"{dc.version.major}.{dc.version.minor}" if dc.version else "",
                "supported_versions": [
                    f"{v.major}.{v.minor}" for v in dc.supported_versions
                ] if dc.supported_versions else [],
            })

        return result

    @require_connection
    def get_datacenter(self, name_or_id: str) -> Optional[Dict]:
        """Get data center details"""
        dc = self._find_datacenter(name_or_id)
        if not dc:
            return None

        # Get associated clusters
        clusters = []
        try:
            dc_service = self.connection.system_service().data_centers_service().data_center_service(dc.id)
            clusters_service = dc_service.clusters_service()
            cluster_list = clusters_service.list()
            clusters = [{"id": c.id, "name": c.name} for c in cluster_list]
        except Exception as e:
            logger.debug(f"Failed to get data center clusters: {e}")

        # Get associated storage domains
        storage_domains = []
        try:
            sd_service = dc_service.storage_domains_service()
            sd_list = sd_service.list()
            storage_domains = [{"id": s.id, "name": s.name, "type": str(s.type.value)} for s in sd_list]
        except Exception as e:
            logger.debug(f"Failed to get data center storage domains: {e}")

        # Get associated networks
        networks = []
        try:
            networks_service = dc_service.networks_service()
            net_list = networks_service.list()
            networks = [{"id": n.id, "name": n.name} for n in net_list[:10]]  # Limit the count
        except Exception as e:
            logger.debug(f"Failed to get data center networks: {e}")

        return {
            "id": dc.id,
            "name": dc.name,
            "description": dc.description or "",
            "status": str(dc.status.value) if dc.status else "unknown",
            "storage_type": str(dc.storage_type.value) if getattr(dc, "storage_type", None) else "nfs",
            "version": f"{dc.version.major}.{dc.version.minor}" if dc.version else "",
            "mac_pool": dc.mac_pool.name if dc.mac_pool else "",
            "clusters": clusters,
            "storage_domains": storage_domains,
            "networks": networks,
        }

    @require_connection
    def create_datacenter(self, name: str, storage_type: str = "nfs",
                         description: str = "") -> Dict[str, Any]:
        """Create data center"""
        # Validate storage type
        valid_types = ["nfs", "fc", "iscsi", "localfs", "posixfs", "glusterfs"]
        if storage_type.lower() not in valid_types:
            raise ValueError(f"Invalid storage type: {storage_type}, valid values: {valid_types}")

        dcs_service = self.connection.system_service().data_centers_service()

        # Check whether it already exists
        existing = dcs_service.list(search=f"name={_sanitize_search_value(name)}")
        if existing:
            raise ValueError(f"Data center already exists: {name}")

        # Create the data center
        try:
            dc = dcs_service.add(
                sdk.types.DataCenter(
                    name=name,
                    description=description,
                    storage_type=sdk.types.StorageType(storage_type.lower()),
                    version=sdk.types.Version(major=4, minor=7),  # Default version
                )
            )
            return {
                "success": True,
                "message": f"Data center {name} created",
                "datacenter_id": dc.id,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to create data center: {e}")

    @require_connection
    def update_datacenter(self, name_or_id: str, new_name: str = None,
                         description: str = None) -> Dict[str, Any]:
        """Update data center"""
        dc = self._find_datacenter(name_or_id)
        if not dc:
            raise ValueError(f"Data center not found: {name_or_id}")

        dc_service = self.connection.system_service().data_centers_service().data_center_service(dc.id)

        # Get current data center information
        current_dc = dc_service.get()

        # Update attributes
        if new_name:
            current_dc.name = new_name
        if description is not None:
            current_dc.description = description

        try:
            dc_service.update(current_dc)
            return {"success": True, "message": f"Data center updated"}
        except Exception as e:
            raise RuntimeError(f"Failed to update data center: {e}")

    @require_connection
    def delete_datacenter(self, name_or_id: str) -> Dict[str, Any]:
        """Delete data center"""
        dc = self._find_datacenter(name_or_id)
        if not dc:
            raise ValueError(f"Data center not found: {name_or_id}")

        dc_service = self.connection.system_service().data_centers_service().data_center_service(dc.id)

        try:
            dc_service.remove()
            return {"success": True, "message": f"Data center {dc.name} deleted"}
        except Exception as e:
            raise RuntimeError(f"Failed to delete data center: {e}")


# MCP tool registry
MCP_TOOLS = {
    "datacenter_list": {"method": "list_datacenters", "description": "List data centers"},
    "datacenter_get": {"method": "get_datacenter", "description": "Get data center details"},
    "datacenter_create": {"method": "create_datacenter", "description": "Create data center"},
    "datacenter_update": {"method": "update_datacenter", "description": "Update data center"},
    "datacenter_delete": {"method": "delete_datacenter", "description": "Delete data center"},
}
