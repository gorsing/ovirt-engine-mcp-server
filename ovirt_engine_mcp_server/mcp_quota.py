#!/usr/bin/env python3
"""
oVirt MCP Server - quota module
Provides quota creation, query, update, delete, and cluster/storage limit management
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


class QuotaMCP(BaseMCP):
    """Quota MCP"""

    def __init__(self, ovirt_mcp):
        super().__init__(ovirt_mcp)

    def _find_quota(self, datacenter: str, name_or_id: str) -> Optional[Any]:
        """Find a quota"""
        dc = self._find_datacenter(datacenter)
        if not dc:
            return None

        dc_service = self.connection.system_service().data_centers_service().data_center_service(dc.id)
        quotas_service = dc_service.quotas_service()

        try:
            quota = quotas_service.quota_service(name_or_id).get()
            if quota:
                return quota
        except Exception:
            pass

        quotas = quotas_service.list(search=f"name={_sanitize_search_value(name_or_id)}")
        return quotas[0] if quotas else None

    @require_connection
    def list_quotas(self, datacenter: str) -> List[Dict]:
        """List quotas in a data center

        Args:
            datacenter: Data center name or ID

        Returns:
            List of quotas
        """
        dc = self._find_datacenter(datacenter)
        if not dc:
            raise ValueError(f"Data center not found: {datacenter}")

        dc_service = self.connection.system_service().data_centers_service().data_center_service(dc.id)
        quotas_service = dc_service.quotas_service()

        try:
            quotas = quotas_service.list()
        except Exception as e:
            logger.error(f"Failed to fetch quota list: {e}")
            return []

        return [
            {
                "id": q.id,
                "name": q.name,
                "description": q.description if hasattr(q, 'description') else "",
                "data_center": dc.name,
                "cluster_hard_limit_pct": q.cluster_hard_limit_pct if hasattr(q, 'cluster_hard_limit_pct') else 0,
                "storage_hard_limit_pct": q.storage_hard_limit_pct if hasattr(q, 'storage_hard_limit_pct') else 0,
            }
            for q in quotas
        ]

    @require_connection
    def get_quota(self, datacenter: str, name_or_id: str) -> Optional[Dict]:
        """Get quota details

        Args:
            datacenter: Data center name or ID
            name_or_id: Quota name or ID

        Returns:
            Quota details
        """
        dc = self._find_datacenter(datacenter)
        if not dc:
            raise ValueError(f"Data center not found: {datacenter}")

        quota = self._find_quota(datacenter, name_or_id)
        if not quota:
            return None

        # Get cluster limits
        cluster_limits = []
        if hasattr(quota, 'cluster_hard_limit_pct') and quota.cluster_hard_limit_pct:
            cluster_limits.append({
                "type": "hard_limit_pct",
                "value": quota.cluster_hard_limit_pct,
            })

        # Get storage limits
        storage_limits = []
        if hasattr(quota, 'storage_hard_limit_pct') and quota.storage_hard_limit_pct:
            storage_limits.append({
                "type": "hard_limit_pct",
                "value": quota.storage_hard_limit_pct,
            })

        return {
            "id": quota.id,
            "name": quota.name,
            "description": quota.description if hasattr(quota, 'description') else "",
            "data_center": dc.name,
            "data_center_id": dc.id,
            "cluster_hard_limit_pct": quota.cluster_hard_limit_pct if hasattr(quota, 'cluster_hard_limit_pct') else 0,
            "storage_hard_limit_pct": quota.storage_hard_limit_pct if hasattr(quota, 'storage_hard_limit_pct') else 0,
            "cluster_limits": cluster_limits,
            "storage_limits": storage_limits,
        }

    @require_connection
    def create_quota(self, name: str, datacenter: str,
                    description: str = "",
                    cluster_hard_limit_pct: int = 0,
                    storage_hard_limit_pct: int = 0) -> Dict[str, Any]:
        """Create a quota

        Args:
            name: Quota name
            datacenter: Data center name
            description: Description
            cluster_hard_limit_pct: Cluster hard limit percentage
            storage_hard_limit_pct: Storage hard limit percentage

        Returns:
            Creation result
        """
        dc = self._find_datacenter(datacenter)
        if not dc:
            raise ValueError(f"Data center not found: {datacenter}")

        dc_service = self.connection.system_service().data_centers_service().data_center_service(dc.id)
        quotas_service = dc_service.quotas_service()

        # Check whether the quota already exists
        existing = quotas_service.list(search=f"name={_sanitize_search_value(name)}")
        if existing:
            raise ValueError(f"Quota already exists: {name}")

        try:
            quota = quotas_service.add(
                sdk.types.Quota(
                    name=name,
                    description=description,
                    cluster_hard_limit_pct=cluster_hard_limit_pct if cluster_hard_limit_pct > 0 else None,
                    storage_hard_limit_pct=storage_hard_limit_pct if storage_hard_limit_pct > 0 else None,
                )
            )

            return {
                "success": True,
                "message": f"Quota {name} created",
                "quota_id": quota.id,
                "data_center": dc.name,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to create quota: {e}")

    @require_connection
    def update_quota(self, datacenter: str, name_or_id: str,
                    new_name: str = None, description: str = None,
                    cluster_hard_limit_pct: int = None,
                    storage_hard_limit_pct: int = None) -> Dict[str, Any]:
        """Update a quota

        Args:
            datacenter: Data center name or ID
            name_or_id: Quota name or ID
            new_name: New name
            description: New description
            cluster_hard_limit_pct: Cluster hard limit percentage
            storage_hard_limit_pct: Storage hard limit percentage

        Returns:
            Update result
        """
        dc = self._find_datacenter(datacenter)
        if not dc:
            raise ValueError(f"Data center not found: {datacenter}")

        quota = self._find_quota(datacenter, name_or_id)
        if not quota:
            raise ValueError(f"Quota not found: {name_or_id}")

        dc_service = self.connection.system_service().data_centers_service().data_center_service(dc.id)
        quotas_service = dc_service.quotas_service()
        quota_service = quotas_service.quota_service(quota.id)

        if new_name:
            quota.name = new_name
        if description is not None:
            quota.description = description
        if cluster_hard_limit_pct is not None:
            quota.cluster_hard_limit_pct = cluster_hard_limit_pct
        if storage_hard_limit_pct is not None:
            quota.storage_hard_limit_pct = storage_hard_limit_pct

        try:
            quota_service.update(quota)
            return {"success": True, "message": f"Quota updated"}
        except Exception as e:
            raise RuntimeError(f"Failed to update quota: {e}")

    @require_connection
    def delete_quota(self, datacenter: str, name_or_id: str) -> Dict[str, Any]:
        """Delete a quota

        Args:
            datacenter: Data center name or ID
            name_or_id: Quota name or ID

        Returns:
            Deletion result
        """
        dc = self._find_datacenter(datacenter)
        if not dc:
            raise ValueError(f"Data center not found: {datacenter}")

        quota = self._find_quota(datacenter, name_or_id)
        if not quota:
            raise ValueError(f"Quota not found: {name_or_id}")

        dc_service = self.connection.system_service().data_centers_service().data_center_service(dc.id)
        quotas_service = dc_service.quotas_service()
        quota_service = quotas_service.quota_service(quota.id)

        try:
            quota_service.remove()
            return {"success": True, "message": f"Quota {quota.name} deleted"}
        except Exception as e:
            raise RuntimeError(f"Failed to delete quota: {e}")

    @require_connection
    def list_quota_cluster_limits(self, datacenter: str, name_or_id: str) -> List[Dict]:
        """List quota cluster limits

        Args:
            datacenter: Data center name or ID
            name_or_id: Quota name or ID

        Returns:
            List of cluster limits
        """
        quota = self._find_quota(datacenter, name_or_id)
        if not quota:
            raise ValueError(f"Quota not found: {name_or_id}")

        dc = self._find_datacenter(datacenter)
        dc_service = self.connection.system_service().data_centers_service().data_center_service(dc.id)
        quotas_service = dc_service.quotas_service()
        quota_service = quotas_service.quota_service(quota.id)

        try:
            limits = quota_service.quota_cluster_limits_service().list()
        except Exception as e:
            logger.error(f"Failed to fetch cluster limits: {e}")
            return []

        return [
            {
                "id": l.id,
                "cluster": l.cluster.name if hasattr(l, 'cluster') and l.cluster else "",
                "memory_mb": int(l.memory_limit) if hasattr(l, 'memory_limit') else 0,
                "cpu": l.cpu_limit if hasattr(l, 'cpu_limit') else 0,
                "vcpu": l.vcpu_limit if hasattr(l, 'vcpu_limit') else 0,
            }
            for l in limits
        ]

    @require_connection
    def list_quota_storage_limits(self, datacenter: str, name_or_id: str) -> List[Dict]:
        """List quota storage limits

        Args:
            datacenter: Data center name or ID
            name_or_id: Quota name or ID

        Returns:
            List of storage limits
        """
        quota = self._find_quota(datacenter, name_or_id)
        if not quota:
            raise ValueError(f"Quota not found: {name_or_id}")

        dc = self._find_datacenter(datacenter)
        dc_service = self.connection.system_service().data_centers_service().data_center_service(dc.id)
        quotas_service = dc_service.quotas_service()
        quota_service = quotas_service.quota_service(quota.id)

        try:
            limits = quota_service.quota_storage_limits_service().list()
        except Exception as e:
            logger.error(f"Failed to fetch storage limits: {e}")
            return []

        return [
            {
                "id": l.id,
                "storage_domain": l.storage_domain.name if hasattr(l, 'storage_domain') and l.storage_domain else "",
                "limit_gb": int((l.limit or 0) / (1024**3)),
                "usage_gb": int((l.usage or 0) / (1024**3)),
            }
            for l in limits
        ]


# MCP tool registry
MCP_TOOLS = {
    "quota_list": {"method": "list_quotas", "description": "List quotas in a data center"},
    "quota_get": {"method": "get_quota", "description": "Get quota details"},
    "quota_create": {"method": "create_quota", "description": "Create quota"},
    "quota_update": {"method": "update_quota", "description": "Update quota"},
    "quota_delete": {"method": "delete_quota", "description": "Delete quota"},
    "quota_cluster_limit_list": {"method": "list_quota_cluster_limits", "description": "List quota cluster limits"},
    "quota_storage_limit_list": {"method": "list_quota_storage_limits", "description": "List quota storage limits"},
}
