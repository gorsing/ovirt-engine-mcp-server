#!/usr/bin/env python3
"""Resolving oVirt reference objects to human-readable names.

oVirt list payloads return references (``cluster``, ``host``, ``vm`` …) with
only an ``id`` populated — ``ref.name`` comes back as ``None``, which used to
leak into tool output as ``cluster: None`` and made client-side filtering by
name return nothing. Following the link once and caching it keeps the output
correct without repeating the lookup for every row.

Shared by :class:`OvirtMCP` (``ovirt_mcp``) and :class:`BaseMCP` (the
extension modules) so both sides resolve consistently.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class LinkNameMixin:
    """``_link_name`` and its typed wrappers; needs ``self.connection``."""

    # Reference kind -> (list service accessor, item service accessor) on the
    # system service.
    _LINK_SERVICES = {
        "cluster": ("clusters_service", "cluster_service"),
        "host": ("hosts_service", "host_service"),
        "data_center": ("data_centers_service", "data_center_service"),
        "network": ("networks_service", "network_service"),
        "vm": ("vms_service", "vm_service"),
        "storage_domain": ("storage_domains_service", "storage_domain_service"),
        "template": ("templates_service", "template_service"),
        "user": ("users_service", "user_service"),
        "role": ("roles_service", "role_service"),
        "group": ("groups_service", "group_service"),
        # NB: the accessor is ``profile_service``, not ``vnic_profile_service``
        "vnic_profile": ("vnic_profiles_service", "profile_service"),
    }

    def _link_obj(self, kind: str, ref: Any) -> Any:
        """Fetch the object a reference points at (cached; None on failure)."""
        if not ref:
            return None
        ref_id = getattr(ref, "id", None)
        if not ref_id:
            return None
        cache = getattr(self, "_link_obj_cache", None)
        if cache is None:
            cache = {}
            self._link_obj_cache = cache
        key = (kind, ref_id)
        if key in cache:
            return cache[key]
        list_attr, item_attr = self._LINK_SERVICES[kind]
        try:
            service = getattr(self.connection.system_service(), list_attr)()
            cache[key] = getattr(service, item_attr)(ref_id).get()
        except Exception as e:
            logger.debug(f"Failed to fetch {kind} {ref_id}: {e}")
            cache[key] = None
        return cache[key]

    def _link_name(self, kind: str, ref: Any) -> str:
        """Resolve a reference to the name of the object it points at.

        Returns the inline name when the payload carries one, otherwise
        follows the link. Results are cached per instance.
        """
        if not ref:
            return ""
        if ref.name:
            return ref.name
        if not ref.id:
            return ""
        cache = getattr(self, "_link_name_cache", None)
        if cache is None:
            cache = {}
            self._link_name_cache = cache
        key = (kind, ref.id)
        if key in cache:
            return cache[key]
        list_attr, item_attr = self._LINK_SERVICES[kind]
        try:
            service = getattr(self.connection.system_service(), list_attr)()
            target = getattr(service, item_attr)(ref.id).get()
            cache[key] = target.name or ""
        except Exception as e:
            logger.debug(f"Failed to resolve {kind} name for {ref.id}: {e}")
            cache[key] = ""
        return cache[key]

    def _cluster_name(self, ref: Any) -> str:
        """Resolve a cluster reference to its name."""
        return self._link_name("cluster", ref)

    def _host_name(self, ref: Any) -> str:
        """Resolve a host reference to its name."""
        return self._link_name("host", ref)

    def _data_center_name(self, ref: Any) -> str:
        """Resolve a data center reference to its name."""
        return self._link_name("data_center", ref)

    def _network_name(self, ref: Any) -> str:
        """Resolve a network reference to its name."""
        return self._link_name("network", ref)

    def _vm_name(self, ref: Any) -> str:
        """Resolve a VM reference to its name."""
        return self._link_name("vm", ref)

    def _storage_domain_name(self, ref: Any) -> str:
        """Resolve a storage domain reference to its name."""
        return self._link_name("storage_domain", ref)

    def _template_name(self, ref: Any) -> str:
        """Resolve a template reference to its name."""
        return self._link_name("template", ref)

    def _user_name(self, ref: Any) -> str:
        """Resolve a user reference to its name."""
        return self._link_name("user", ref)

    def _role_name(self, ref: Any) -> str:
        """Resolve a role reference to its name."""
        return self._link_name("role", ref)

    def _group_name(self, ref: Any) -> str:
        """Resolve a group reference to its name."""
        return self._link_name("group", ref)

    def _vnic_profile_name(self, ref: Any) -> str:
        """Resolve a VNIC profile reference to its name."""
        return self._link_name("vnic_profile", ref)

    @staticmethod
    def _storage_domain_ref(disk: Any) -> Any:
        """The storage domain a disk lives on.

        ``Disk.storage_domain`` is None on live engines — the populated
        reference is ``storage_domains``.
        """
        ref = getattr(disk, "storage_domain", None)
        if ref:
            return ref
        refs = getattr(disk, "storage_domains", None) or []
        return refs[0] if refs else None
