#!/usr/bin/env python3
"""Tests for :class:`BaseMCP` resource lookup.

Guards the service accessor names: ``vm_pools_service().pool_service()`` and
``vnic_profiles_service().profile_service()`` are the real SDK accessors —
the code used to call ``vm_pool_service()`` / ``vnic_profile_service()``,
which made lookups by id fall through to a name search (and crash in the
fallback paths).
"""
from types import SimpleNamespace

import pytest
from unittest.mock import MagicMock

from ovirt_engine_mcp_server.base_mcp import (
    RESOURCE_SERVICE_GETTERS,
    RESOURCE_SERVICE_NAMES,
    BaseMCP,
)


def _mcp() -> BaseMCP:
    ovirt = MagicMock()
    ovirt.connected = True
    return BaseMCP(ovirt)


class TestResourceLookupAccessors:
    def test_vm_pool_lookup_uses_pool_service(self):
        mcp = _mcp()
        pools = mcp.connection.system_service.return_value.vm_pools_service.return_value
        pools.pool_service.return_value.get.return_value = SimpleNamespace(
            id="pool-1", name="my_pool"
        )

        pool = mcp._find_vm_pool("pool-1")

        assert pool.name == "my_pool"
        pools.pool_service.assert_called_once_with("pool-1")

    def test_vnic_profile_lookup_uses_profile_service(self):
        mcp = _mcp()
        profiles = (
            mcp.connection.system_service.return_value
            .vnic_profiles_service.return_value
        )
        profiles.profile_service.return_value.get.return_value = SimpleNamespace(
            id="v-1", name="ovirtmgmt"
        )

        profile = mcp._find_vnic_profile("v-1")

        assert profile.name == "ovirtmgmt"
        profiles.profile_service.assert_called_once_with("v-1")

    def test_every_resource_type_has_getter_and_accessor(self):
        assert set(RESOURCE_SERVICE_GETTERS) == set(RESOURCE_SERVICE_NAMES)

    def test_data_center_scoped_types_are_not_registered(self):
        """QoS / iSCSI bonds have no SystemService getter — they are scoped to
        a data center, and the old entries pointed at non-existent services."""
        mcp = _mcp()

        for resource_type in ("qos", "iscsi_bond"):
            assert resource_type not in RESOURCE_SERVICE_GETTERS
            assert resource_type not in RESOURCE_SERVICE_NAMES
            with pytest.raises(ValueError, match="Unknown resource type"):
                mcp._find_resource(resource_type, "x")

    def test_unknown_resource_type_raises(self):
        with pytest.raises(ValueError, match="Unknown resource type"):
            _mcp()._find_resource("no_such_type", "x")
