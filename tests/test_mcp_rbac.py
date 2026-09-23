#!/usr/bin/env python3
"""Tests for RbacMCP class - RBAC management module tests."""
import pytest
from unittest.mock import MagicMock


def _create_mock_user(user_id="user-123", name="admin", user_name="admin@internal"):
    """Create mock User object"""
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.name = name
    mock_user.user_name = user_name
    mock_user.principal = "admin"
    mock_user.email = "admin@test.com"
    mock_user.domain = MagicMock()
    mock_user.domain.name = "internal"
    return mock_user


def _create_mock_group(group_id="group-123", name="Administrators"):
    """Create mock Group object"""
    mock_group = MagicMock()
    mock_group.id = group_id
    mock_group.name = name
    mock_group.domain = MagicMock()
    mock_group.domain.name = "internal"
    return mock_group


def _create_mock_role(role_id="role-123", name="UserAdmin", administrative=False):
    """Create mock Role object"""
    mock_role = MagicMock()
    mock_role.id = role_id
    mock_role.name = name
    mock_role.description = "User administrator role"
    mock_role.administrative = administrative
    return mock_role


def _create_mock_tag(tag_id="tag-123", name="production"):
    """Create mock Tag object"""
    mock_tag = MagicMock()
    mock_tag.id = tag_id
    mock_tag.name = name
    mock_tag.description = "Production resources"
    mock_tag.parent = None
    return mock_tag


class TestRbacMCPListUsers:
    """Test the list_users method"""

    def test_list_users_empty(self):
        """Test empty user list"""
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_users_service = MagicMock()
        mock_users_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.users_service.return_value = mock_users_service

        rbac_mcp = RbacMCP(mock_ovirt)
        result = rbac_mcp.list_users()

        assert result == []

    def test_list_users_with_data(self):
        """Test user list with data"""
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_users = [_create_mock_user()]

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_users_service = MagicMock()
        mock_users_service.list.return_value = mock_users

        mock_ovirt.connection.system_service.return_value.users_service.return_value = mock_users_service

        rbac_mcp = RbacMCP(mock_ovirt)
        result = rbac_mcp.list_users()

        assert len(result) == 1
        assert result[0]["name"] == "admin"

    def test_list_users_with_search(self):
        """Test user list with search"""
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_users = [_create_mock_user()]

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_users_service = MagicMock()
        mock_users_service.list.return_value = mock_users

        mock_ovirt.connection.system_service.return_value.users_service.return_value = mock_users_service

        rbac_mcp = RbacMCP(mock_ovirt)
        result = rbac_mcp.list_users(search="admin")

        assert len(result) == 1


class TestRbacMCPGetUser:
    """Test the get_user method"""

    def test_get_user_success(self):
        """Test get user details success"""
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_user = _create_mock_user()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_user_service = MagicMock()
        mock_user_service.get.return_value = mock_user
        mock_user_service.permissions_service.return_value.list.return_value = []

        mock_users_service = MagicMock()
        mock_users_service.user_service.return_value = mock_user_service
        mock_users_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.users_service.return_value = mock_users_service

        rbac_mcp = RbacMCP(mock_ovirt)
        result = rbac_mcp.get_user("admin")

        assert result is not None
        assert result["name"] == "admin"
        assert "permissions" in result

    def test_get_user_not_found(self):
        """Test user not found"""
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_users_service = MagicMock()
        mock_users_service.user_service.return_value.get.side_effect = Exception("Not found")
        mock_users_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.users_service.return_value = mock_users_service

        rbac_mcp = RbacMCP(mock_ovirt)
        result = rbac_mcp.get_user("nonexistent")

        assert result is None


class TestRbacMCPListGroups:
    """Test the list_groups method"""

    def test_list_groups_empty(self):
        """Test empty group list"""
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_groups_service = MagicMock()
        mock_groups_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.groups_service.return_value = mock_groups_service

        rbac_mcp = RbacMCP(mock_ovirt)
        result = rbac_mcp.list_groups()

        assert result == []

    def test_list_groups_with_data(self):
        """Test group list with data"""
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_groups = [_create_mock_group()]

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_groups_service = MagicMock()
        mock_groups_service.list.return_value = mock_groups

        mock_ovirt.connection.system_service.return_value.groups_service.return_value = mock_groups_service

        rbac_mcp = RbacMCP(mock_ovirt)
        result = rbac_mcp.list_groups()

        assert len(result) == 1
        assert result[0]["name"] == "Administrators"


class TestRbacMCPGetGroup:
    """Test the get_group method"""

    def test_get_group_success(self):
        """Test get group details success"""
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_group = _create_mock_group()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_group_service = MagicMock()
        mock_group_service.get.return_value = mock_group
        mock_group_service.permissions_service.return_value.list.return_value = []

        mock_groups_service = MagicMock()
        mock_groups_service.group_service.return_value = mock_group_service
        mock_groups_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.groups_service.return_value = mock_groups_service

        rbac_mcp = RbacMCP(mock_ovirt)
        result = rbac_mcp.get_group("Administrators")

        assert result is not None
        assert result["name"] == "Administrators"


class TestRbacMCPListRoles:
    """Test the list_roles method"""

    def test_list_roles_empty(self):
        """Test empty role list"""
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_roles_service = MagicMock()
        mock_roles_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.roles_service.return_value = mock_roles_service

        rbac_mcp = RbacMCP(mock_ovirt)
        result = rbac_mcp.list_roles()

        assert result == []

    def test_list_roles_with_data(self):
        """Test role list with data"""
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_roles = [
            _create_mock_role("role-1", "SuperUser", True),
            _create_mock_role("role-2", "UserAdmin", False),
        ]

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_roles_service = MagicMock()
        mock_roles_service.list.return_value = mock_roles

        mock_ovirt.connection.system_service.return_value.roles_service.return_value = mock_roles_service

        rbac_mcp = RbacMCP(mock_ovirt)
        result = rbac_mcp.list_roles()

        assert len(result) == 2
        assert result[0]["name"] == "SuperUser"


class TestRbacMCPGetRole:
    """Test the get_role method"""

    def test_get_role_success(self):
        """Test get role details success"""
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_role = _create_mock_role()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_role_service = MagicMock()
        mock_role_service.get.return_value = mock_role
        mock_role_service.permits_service.return_value.list.return_value = []

        mock_roles_service = MagicMock()
        mock_roles_service.role_service.return_value = mock_role_service
        mock_roles_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.roles_service.return_value = mock_roles_service

        rbac_mcp = RbacMCP(mock_ovirt)
        result = rbac_mcp.get_role("UserAdmin")

        assert result is not None
        assert result["name"] == "UserAdmin"
        assert "permits" in result


class TestRbacMCPCreateRole:
    """Test the create_role method"""

    def test_create_role_success(self):
        """Test create role success"""
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_role = _create_mock_role()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_roles_service = MagicMock()
        mock_roles_service.list.return_value = []  # name does not conflict
        mock_roles_service.add.return_value = mock_role

        mock_ovirt.connection.system_service.return_value.roles_service.return_value = mock_roles_service

        rbac_mcp = RbacMCP(mock_ovirt)
        result = rbac_mcp.create_role("NewRole", description="Test role")

        assert result["success"] is True
        assert "role_id" in result

    def test_create_role_already_exists(self):
        """Test role already exists"""
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_role = _create_mock_role()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_roles_service = MagicMock()
        mock_roles_service.list.return_value = [mock_role]  # name already exists

        mock_ovirt.connection.system_service.return_value.roles_service.return_value = mock_roles_service

        rbac_mcp = RbacMCP(mock_ovirt)

        with pytest.raises(ValueError, match="already exists"):
            rbac_mcp.create_role("UserAdmin")


class TestRbacMCPDeleteRole:
    """Test the delete_role method"""

    def test_delete_role_success(self):
        """Test delete role success"""
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_role = _create_mock_role()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_role_service = MagicMock()
        mock_roles_service = MagicMock()
        mock_roles_service.role_service.return_value = mock_role_service
        mock_roles_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.roles_service.return_value = mock_roles_service

        # Set _find_role return
        rbac_mcp = RbacMCP(mock_ovirt)
        rbac_mcp._find_role = MagicMock(return_value=mock_role)

        result = rbac_mcp.delete_role("UserAdmin")

        assert result["success"] is True


class TestRbacMCPListPermits:
    """Test the list_permits method"""

    def test_list_permits(self):
        """Test list permits"""
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_permit = MagicMock()
        mock_permit.id = "permit-123"
        mock_permit.name = "login"
        mock_permit.administrative = False

        mock_role = _create_mock_role()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_role_service = MagicMock()
        mock_role_service.permits_service.return_value.list.return_value = [mock_permit]

        mock_roles_service = MagicMock()
        mock_roles_service.list.return_value = [mock_role]
        mock_roles_service.role_service.return_value = mock_role_service

        mock_ovirt.connection.system_service.return_value.roles_service.return_value = mock_roles_service

        rbac_mcp = RbacMCP(mock_ovirt)
        result = rbac_mcp.list_permits()

        assert len(result) == 1
        assert result[0]["name"] == "login"


class TestRbacMCPListPermissions:
    """Test the list_permissions method"""

    def test_list_permissions(self):
        """Test list resource permissions"""
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_vm = MagicMock()
        mock_vm.id = "vm-123"
        mock_vm.name = "test-vm"

        mock_permission = MagicMock()
        mock_permission.id = "perm-123"
        mock_permission.role = MagicMock()
        mock_permission.role.name = "UserAdmin"
        mock_permission.role.id = "role-123"
        mock_permission.user = MagicMock()
        mock_permission.user.name = "admin"
        mock_permission.user.id = "user-123"
        mock_permission.group = None

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        # Mock _find_resource
        rbac_mcp = RbacMCP(mock_ovirt)
        rbac_mcp._find_resource = MagicMock(return_value=mock_vm)

        # Mock permissions service
        mock_permissions_service = MagicMock()
        mock_permissions_service.list.return_value = [mock_permission]

        mock_vm_service = MagicMock()
        mock_vm_service.permissions_service.return_value = mock_permissions_service

        rbac_mcp._get_resource_service = MagicMock(return_value=mock_vm_service)

        result = rbac_mcp.list_permissions("vm", "test-vm")

        assert len(result) == 1
        assert result[0]["role"] == "UserAdmin"


class TestRbacMCPListTags:
    """Test the list_tags method"""

    def test_list_tags_empty(self):
        """Test empty tag list"""
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_tags_service = MagicMock()
        mock_tags_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.tags_service.return_value = mock_tags_service

        rbac_mcp = RbacMCP(mock_ovirt)
        result = rbac_mcp.list_tags()

        assert result == []

    def test_list_tags_with_data(self):
        """Test tag list with data"""
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_tags = [_create_mock_tag()]

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_tags_service = MagicMock()
        mock_tags_service.list.return_value = mock_tags

        mock_ovirt.connection.system_service.return_value.tags_service.return_value = mock_tags_service

        rbac_mcp = RbacMCP(mock_ovirt)
        result = rbac_mcp.list_tags()

        assert len(result) == 1
        assert result[0]["name"] == "production"


class TestRbacMCPCreateTag:
    """Test the create_tag method"""

    def test_create_tag_success(self):
        """Test create tag success"""
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_tag = _create_mock_tag()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_tags_service = MagicMock()
        mock_tags_service.list.return_value = []  # name does not conflict
        mock_tags_service.add.return_value = mock_tag

        mock_ovirt.connection.system_service.return_value.tags_service.return_value = mock_tags_service

        rbac_mcp = RbacMCP(mock_ovirt)
        result = rbac_mcp.create_tag("development", description="Dev resources")

        assert result["success"] is True
        assert "tag_id" in result

    def test_create_tag_already_exists(self):
        """Test tag already exists"""
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_tag = _create_mock_tag()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_tags_service = MagicMock()
        mock_tags_service.list.return_value = [mock_tag]  # name already exists

        mock_ovirt.connection.system_service.return_value.tags_service.return_value = mock_tags_service

        rbac_mcp = RbacMCP(mock_ovirt)

        with pytest.raises(ValueError, match="already exists"):
            rbac_mcp.create_tag("production")


class TestRbacMCPDeleteTag:
    """Test the delete_tag method"""

    def test_delete_tag_success(self):
        """Test delete tag success"""
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_tag = _create_mock_tag()

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_tags_service = MagicMock()
        mock_tags_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.tags_service.return_value = mock_tags_service

        rbac_mcp = RbacMCP(mock_ovirt)
        rbac_mcp._find_tag = MagicMock(return_value=mock_tag)

        result = rbac_mcp.delete_tag("production")

        assert result["success"] is True


class TestRbacMCPTools:
    """Test MCP_TOOLS registry"""

    def test_mcp_tools_defined(self):
        """Test MCP tool registry is defined"""
        from ovirt_engine_mcp_server.mcp_rbac import MCP_TOOLS

        expected_tools = [
            "user_list",
            "user_get",
            "group_list",
            "group_get",
            "role_list",
            "role_get",
            "role_create",
            "role_delete",
            "permit_list",
            "permission_list",
            "permission_assign",
            "permission_revoke",
            "tag_list",
            "tag_create",
            "tag_delete",
            "tag_assign",
            "tag_unassign",
            "tag_list_resources",
        ]

        for tool in expected_tools:
            assert tool in MCP_TOOLS, f"Missing tool: {tool}"
            assert "method" in MCP_TOOLS[tool]
            assert "description" in MCP_TOOLS[tool]


class TestRbacMCPUnsupportedCollections:
    """oVirt 4.5 REST exposes no permission-filter collection.

    ``/api/filters`` and ``/api/permissionfilters`` are 404, so the tool must
    report "unsupported" instead of crashing with AttributeError or pretending
    there are no filters.
    """

    def test_list_filters_reports_unsupported_api(self):
        from ovirt_engine_mcp_server.mcp_rbac import RbacMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        with pytest.raises(ValueError, match="Permission filters unavailable"):
            RbacMCP(mock_ovirt).list_filters()
