#!/usr/bin/env python3
"""
oVirt MCP Server - RBAC management module
Provides user, group, role, permission, and tag management
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


class RbacMCP(BaseMCP):
    """RBAC management MCP"""

    def __init__(self, ovirt_mcp):
        super().__init__(ovirt_mcp)

    # -- Resource lookup helpers (not provided by BaseMCP)-------------------------------

    def _find_group(self, name_or_id: str) -> Optional[Any]:
        """Find group (by name or ID)"""
        groups_service = self.connection.system_service().groups_service()

        # Try to find by ID first
        try:
            group = groups_service.group_service(name_or_id).get()
            if group:
                return group
        except Exception:
            pass

        # Search by name
        groups = groups_service.list(search=f"name={_sanitize_search_value(name_or_id)}")
        return groups[0] if groups else None

    def _find_tag(self, name_or_id: str) -> Optional[Any]:
        """Find tag (by name or ID)"""
        tags_service = self.connection.system_service().tags_service()

        # Try to find by ID first
        try:
            tag = tags_service.tag_service(name_or_id).get()
            if tag:
                return tag
        except Exception:
            pass

        # Search by name
        tags = tags_service.list(search=f"name={_sanitize_search_value(name_or_id)}")
        return tags[0] if tags else None

    def _get_resource_service(self, resource_type: str, resource_id: str) -> Optional[Any]:
        """Get the service for the resource type

        Args:
            resource_type: Resource type (vm, host, cluster, datacenter, network, storagedomain, template)
            resource_id: Resource ID

        Returns:
            Service object for the resource
        """
        system_service = self.connection.system_service()
        resource_type_lower = resource_type.lower()

        service_map = {
            "vm": lambda: system_service.vms_service().vm_service(resource_id),
            "host": lambda: system_service.hosts_service().host_service(resource_id),
            "cluster": lambda: system_service.clusters_service().cluster_service(resource_id),
            "datacenter": lambda: system_service.data_centers_service().data_center_service(resource_id),
            "network": lambda: system_service.networks_service().network_service(resource_id),
            "storagedomain": lambda: system_service.storage_domains_service().storage_domain_service(resource_id),
            "template": lambda: system_service.templates_service().template_service(resource_id),
        }

        if resource_type_lower not in service_map:
            raise ValueError(f"Unsupported resource type: {resource_type}, supported types: {list(service_map.keys())}")

        return service_map[resource_type_lower]()

    def _find_resource_by_type(self, resource_type: str, name_or_id: str) -> Optional[Any]:
        """Find resource by type"""
        resource_type_lower = resource_type.lower()

        # Lookup logic for each resource type
        find_map = {
            "vm": lambda: self._find_vm(name_or_id),
            "host": lambda: self._find_host(name_or_id),
            "cluster": lambda: self._find_cluster(name_or_id),
            "datacenter": lambda: self._find_datacenter(name_or_id),
            "network": lambda: self._find_network(name_or_id),
            "storagedomain": lambda: self._find_storage_domain(name_or_id),
            "template": lambda: self._find_template(name_or_id),
        }

        if resource_type_lower not in find_map:
            raise ValueError(f"Unsupported resource type: {resource_type}")

        return find_map[resource_type_lower]()

    # -- User management ----------------------------------------------------------

    @require_connection
    def list_users(self, search: str = None) -> List[Dict]:
        """List users

        Args:
            search: Search filter (optional)

        Returns:
            List of users
        """
        users_service = self.connection.system_service().users_service()

        try:
            if search:
                users = users_service.list(search=_sanitize_search_value(search))
            else:
                users = users_service.list()
        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            return []

        result = []
        for user in users:
            result.append({
                "id": user.id,
                "name": user.name,
                "user_name": user.user_name,
                "principal": user.principal,
                "email": user.email if hasattr(user, 'email') else "",
                "domain": user.domain.name if user.domain else "",
                "department": user.department if hasattr(user, 'department') else "",
            })

        return result

    @require_connection
    def get_user(self, name_or_id: str) -> Optional[Dict]:
        """Get user details

        Args:
            name_or_id: User name or ID

        Returns:
            User details
        """
        user = self._find_user(name_or_id)
        if not user:
            return None

        # Get permission list for the user
        permissions = []
        try:
            user_service = self.connection.system_service().users_service().user_service(user.id)
            perms_service = user_service.permissions_service()
            perms = perms_service.list()
            permissions = [
                {
                    "id": p.id,
                    "role": p.role.name if p.role else "",
                    "object_id": p.object.id if p.object else "",
                    "object_type": p.object.type if p.object and hasattr(p.object, 'type') else "",
                }
                for p in perms[:20]  # Limit the count
            ]
        except Exception as e:
            logger.debug(f"Failed to get user permissions: {e}")

        return {
            "id": user.id,
            "name": user.name,
            "user_name": user.user_name,
            "principal": user.principal,
            "email": user.email if hasattr(user, 'email') else "",
            "domain": user.domain.name if user.domain else "",
            "department": user.department if hasattr(user, 'department') else "",
            "permissions": permissions,
            "permission_count": len(permissions),
        }

    # -- Group management ---------------------------------------------------------

    @require_connection
    def list_groups(self, search: str = None) -> List[Dict]:
        """List groups

        Args:
            search: Search filter (optional)

        Returns:
            List of groups
        """
        groups_service = self.connection.system_service().groups_service()

        try:
            if search:
                groups = groups_service.list(search=_sanitize_search_value(search))
            else:
                groups = groups_service.list()
        except Exception as e:
            logger.error(f"Failed to list groups: {e}")
            return []

        result = []
        for group in groups:
            result.append({
                "id": group.id,
                "name": group.name,
                "domain": group.domain.name if group.domain else "",
            })

        return result

    @require_connection
    def get_group(self, name_or_id: str) -> Optional[Dict]:
        """Get group details

        Args:
            name_or_id: Group name or ID

        Returns:
            Group details
        """
        group = self._find_group(name_or_id)
        if not group:
            return None

        # Get permission list for the group
        permissions = []
        try:
            group_service = self.connection.system_service().groups_service().group_service(group.id)
            perms_service = group_service.permissions_service()
            perms = perms_service.list()
            permissions = [
                {
                    "id": p.id,
                    "role": p.role.name if p.role else "",
                    "object_id": p.object.id if p.object else "",
                    "object_type": p.object.type if p.object and hasattr(p.object, 'type') else "",
                }
                for p in perms[:20]  # Limit the count
            ]
        except Exception as e:
            logger.debug(f"Failed to get group permissions: {e}")

        return {
            "id": group.id,
            "name": group.name,
            "domain": group.domain.name if group.domain else "",
            "permissions": permissions,
            "permission_count": len(permissions),
        }

    # -- Role management ----------------------------------------------------------

    @require_connection
    def list_roles(self) -> List[Dict]:
        """List all roles

        Returns:
            List of roles
        """
        roles_service = self.connection.system_service().roles_service()

        try:
            roles = roles_service.list()
        except Exception as e:
            logger.error(f"Failed to list roles: {e}")
            return []

        result = []
        for role in roles:
            result.append({
                "id": role.id,
                "name": role.name,
                "description": role.description or "",
                "administrative": role.administrative if hasattr(role, 'administrative') else False,
            })

        return result

    @require_connection
    def get_role(self, name_or_id: str) -> Optional[Dict]:
        """Get role details (including permit list)

        Args:
            name_or_id: Role name or ID

        Returns:
            Role details
        """
        role = self._find_role(name_or_id)
        if not role:
            return None

        # Get permit list for the role
        permits = []
        try:
            role_service = self.connection.system_service().roles_service().role_service(role.id)
            permits_service = role_service.permits_service()
            permit_list = permits_service.list()
            permits = [
                {
                    "id": p.id,
                    "name": p.name,
                    "administrative": p.administrative if hasattr(p, 'administrative') else False,
                }
                for p in permit_list
            ]
        except Exception as e:
            logger.debug(f"Failed to get role permits: {e}")

        return {
            "id": role.id,
            "name": role.name,
            "description": role.description or "",
            "administrative": role.administrative if hasattr(role, 'administrative') else False,
            "permits": permits,
            "permit_count": len(permits),
        }

    @require_connection
    def create_role(self, name: str, description: str = "",
                   administrative: bool = False,
                   permit_ids: List[str] = None) -> Dict[str, Any]:
        """Create role

        Args:
            name: Role name
            description: Description
            administrative: Whether it is an administrative role
            permit_ids: List of permit IDs

        Returns:
            Creation result
        """
        roles_service = self.connection.system_service().roles_service()

        # Check whether it already exists
        existing = roles_service.list(search=f"name={_sanitize_search_value(name)}")
        if existing:
            raise ValueError(f"Role already exists: {name}")

        # Build the permit list
        permits = []
        if permit_ids:
            for permit_id in permit_ids:
                permits.append(sdk.types.Permit(id=permit_id))

        try:
            role = roles_service.add(
                sdk.types.Role(
                    name=name,
                    description=description,
                    administrative=administrative,
                    permits=permits if permits else None,
                )
            )

            return {
                "success": True,
                "message": f"Role {name} created",
                "role_id": role.id,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to create role: {e}")

    @require_connection
    def delete_role(self, name_or_id: str) -> Dict[str, Any]:
        """Delete role

        Args:
            name_or_id: Role name or ID

        Returns:
            Deletion result
        """
        role = self._find_role(name_or_id)
        if not role:
            raise ValueError(f"Role not found: {name_or_id}")

        # Check whether it is a built-in system role
        if hasattr(role, 'administrative') and role.id in ['00000000-0000-0000-0000-000000000001',
                                                            '00000000-0000-0000-0000-000000000002']:
            raise ValueError("Cannot delete built-in system roles")

        roles_service = self.connection.system_service().roles_service()
        role_service = roles_service.role_service(role.id)

        try:
            role_service.remove()
            return {"success": True, "message": f"Role {role.name} deleted"}
        except Exception as e:
            raise RuntimeError(f"Failed to delete role: {e}")

    # -- Permit management --------------------------------------------------------

    @require_connection
    def list_permits(self) -> List[Dict]:
        """List all permits

        Returns:
            List of permits
        """
        # Aggregate by collecting permits of all roles
        permits_map = {}  # Deduplicate by id

        try:
            roles_service = self.connection.system_service().roles_service()
            roles = roles_service.list()

            for role in roles:
                try:
                    role_service = roles_service.role_service(role.id)
                    permits_service = role_service.permits_service()
                    permit_list = permits_service.list()

                    for p in permit_list:
                        if p.id not in permits_map:
                            permits_map[p.id] = {
                                "id": p.id,
                                "name": p.name,
                                "administrative": p.administrative if hasattr(p, 'administrative') else False,
                            }
                except Exception as e:
                    logger.debug(f"Failed to get permits for role {role.name}: {e}")

        except Exception as e:
            logger.error(f"Failed to list permissions: {e}")
            return []

        return list(permits_map.values())

    # -- Permission management ----------------------------------------------------

    @require_connection
    def list_permissions(self, resource_type: str, resource_id: str) -> List[Dict]:
        """List resource permissions

        Args:
            resource_type: Resource type (vm, host, cluster, datacenter, network, storagedomain, template)
            resource_id: Resource ID

        Returns:
            List of permissions
        """
        # Find the resource first
        resource = self._find_resource_by_type(resource_type, resource_id)
        if not resource:
            raise ValueError(f"Resource not found: {resource_type}/{resource_id}")

        # Get permissions_service for the resource
        resource_service = self._get_resource_service(resource_type, resource.id)
        permissions_service = resource_service.permissions_service()

        try:
            permissions = permissions_service.list()
        except Exception as e:
            logger.error(f"Failed to list permissions: {e}")
            return []

        result = []
        for perm in permissions:
            result.append({
                "id": perm.id,
                "role": self._role_name(perm.role),
                "role_id": perm.role.id if perm.role else "",
                "user": self._user_name(perm.user),
                "user_id": perm.user.id if perm.user else "",
                "group": self._group_name(perm.group),
                "group_id": perm.group.id if perm.group else "",
            })

        return result

    @require_connection
    def assign_permission(self, resource_type: str, resource_id: str,
                         user_or_group: str, role_name: str,
                         principal_name: str) -> Dict[str, Any]:
        """Assign permission

        Args:
            resource_type: Resource type (vm, host, cluster, datacenter, network, storagedomain, template)
            resource_id: Resource ID or name
            user_or_group: Principal type (user or group)
            role_name: Role name or ID
            principal_name: User name or group name

        Returns:
            Assignment result
        """
        # Validate parameters
        if user_or_group.lower() not in ["user", "group"]:
            raise ValueError("user_or_group must be 'user' or 'group'")

        # Find the resource
        resource = self._find_resource_by_type(resource_type, resource_id)
        if not resource:
            raise ValueError(f"Resource not found: {resource_type}/{resource_id}")

        # Find the role
        role = self._find_role(role_name)
        if not role:
            raise ValueError(f"Role not found: {role_name}")

        # Find the user or group
        user_obj = None
        group_obj = None

        if user_or_group.lower() == "user":
            user_obj = self._find_user(principal_name)
            if not user_obj:
                raise ValueError(f"User not found: {principal_name}")
        else:
            group_obj = self._find_group(principal_name)
            if not group_obj:
                raise ValueError(f"Group not found: {principal_name}")

        # Get permissions_service for the resource
        resource_service = self._get_resource_service(resource_type, resource.id)
        permissions_service = resource_service.permissions_service()

        # Build the permission object
        try:
            if user_obj:
                permission = sdk.types.Permission(
                    user=sdk.types.User(id=user_obj.id),
                    role=sdk.types.Role(id=role.id),
                )
            else:
                permission = sdk.types.Permission(
                    group=sdk.types.Group(id=group_obj.id),
                    role=sdk.types.Role(id=role.id),
                )

            result = permissions_service.add(permission)

            return {
                "success": True,
                "message": f"Assigned role {role.name} to {user_or_group} {principal_name}",
                "permission_id": result.id,
                "resource_type": resource_type,
                "resource_id": resource.id,
                "role": role.name,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to assign permission: {e}")

    @require_connection
    def revoke_permission(self, resource_type: str, resource_id: str,
                         permission_id: str) -> Dict[str, Any]:
        """Revoke permission

        Args:
            resource_type: Resource type
            resource_id: Resource ID or name
            permission_id: Permission ID

        Returns:
            Revocation result
        """
        # Find the resource
        resource = self._find_resource_by_type(resource_type, resource_id)
        if not resource:
            raise ValueError(f"Resource not found: {resource_type}/{resource_id}")

        # Get permissions_service for the resource
        resource_service = self._get_resource_service(resource_type, resource.id)
        permissions_service = resource_service.permissions_service()
        permission_service = permissions_service.permission_service(permission_id)

        try:
            permission_service.remove()
            return {"success": True, "message": f"Permission {permission_id} revoked"}
        except Exception as e:
            raise RuntimeError(f"Failed to revoke permission: {e}")

    # -- Tag management -----------------------------------------------------------

    @require_connection
    def list_tags(self) -> List[Dict]:
        """List all tags

        Returns:
            List of tags
        """
        tags_service = self.connection.system_service().tags_service()

        try:
            tags = tags_service.list()
        except Exception as e:
            logger.error(f"Failed to list tags: {e}")
            return []

        result = []
        for tag in tags:
            result.append({
                "id": tag.id,
                "name": tag.name,
                "description": tag.description or "",
                "parent_id": tag.parent.id if tag.parent else "",
            })

        return result

    @require_connection
    def create_tag(self, name: str, description: str = "",
                  parent_name: str = None) -> Dict[str, Any]:
        """Create tag

        Args:
            name: Tag name
            description: Description
            parent_name: Parent tag name (optional)

        Returns:
            Creation result
        """
        tags_service = self.connection.system_service().tags_service()

        # Check whether it already exists
        existing = tags_service.list(search=f"name={_sanitize_search_value(name)}")
        if existing:
            raise ValueError(f"Tag already exists: {name}")

        # Build the tag object
        parent_tag = None
        if parent_name:
            parent = self._find_tag(parent_name)
            if not parent:
                raise ValueError(f"Parent tag not found: {parent_name}")
            parent_tag = sdk.types.Tag(id=parent.id)

        try:
            tag = tags_service.add(
                sdk.types.Tag(
                    name=name,
                    description=description,
                    parent=parent_tag,
                )
            )

            return {
                "success": True,
                "message": f"Tag {name} created",
                "tag_id": tag.id,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to create tag: {e}")

    @require_connection
    def delete_tag(self, name_or_id: str) -> Dict[str, Any]:
        """Delete tag

        Args:
            name_or_id: Tag name or ID

        Returns:
            Deletion result
        """
        tag = self._find_tag(name_or_id)
        if not tag:
            raise ValueError(f"Tag not found: {name_or_id}")

        tags_service = self.connection.system_service().tags_service()
        tag_service = tags_service.tag_service(tag.id)

        try:
            tag_service.remove()
            return {"success": True, "message": f"Tag {tag.name} deleted"}
        except Exception as e:
            raise RuntimeError(f"Failed to delete tag: {e}")

    @require_connection
    def assign_tag(self, resource_type: str, resource_id: str,
                  tag_name: str) -> Dict[str, Any]:
        """Assign tag to resource

        Args:
            resource_type: Resource type (vm, host, cluster, datacenter, network, storagedomain, template)
            resource_id: Resource ID or name
            tag_name: Tag name or ID

        Returns:
            Assignment result
        """
        # Find the resource
        resource = self._find_resource_by_type(resource_type, resource_id)
        if not resource:
            raise ValueError(f"Resource not found: {resource_type}/{resource_id}")

        # Find the tag
        tag = self._find_tag(tag_name)
        if not tag:
            raise ValueError(f"Tag not found: {tag_name}")

        # Get tags_service for the resource
        resource_service = self._get_resource_service(resource_type, resource.id)
        tags_service = resource_service.tags_service()

        # Check whether it is already assigned
        try:
            existing_tags = tags_service.list()
            for existing in existing_tags:
                if existing.id == tag.id:
                    return {"success": True, "message": f"Tag {tag.name} assigned to resource"}
        except Exception:
            pass

        # Assign the tag
        try:
            tags_service.add(sdk.types.Tag(id=tag.id))

            return {
                "success": True,
                "message": f"Tag {tag.name} assigned to {resource_type}",
                "tag_id": tag.id,
                "resource_type": resource_type,
                "resource_id": resource.id,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to assign tag: {e}")

    @require_connection
    def unassign_tag(self, resource_type: str, resource_id: str,
                    tag_name: str) -> Dict[str, Any]:
        """Remove tag from resource

        Args:
            resource_type: Resource type
            resource_id: Resource ID or name
            tag_name: Tag name or ID

        Returns:
            Removal result
        """
        # Find the resource
        resource = self._find_resource_by_type(resource_type, resource_id)
        if not resource:
            raise ValueError(f"Resource not found: {resource_type}/{resource_id}")

        # Find the tag
        tag = self._find_tag(tag_name)
        if not tag:
            raise ValueError(f"Tag not found: {tag_name}")

        # Get tags_service for the resource
        resource_service = self._get_resource_service(resource_type, resource.id)
        tags_service = resource_service.tags_service()
        tag_service = tags_service.tag_service(tag.id)

        try:
            tag_service.remove()
            return {"success": True, "message": f"Tag {tag.name} removed from resource"}
        except Exception as e:
            raise RuntimeError(f"Failed to remove tag: {e}")

    @require_connection
    def list_resource_tags(self, resource_type: str, resource_id: str) -> List[Dict]:
        """List resource tags

        Args:
            resource_type: Resource type
            resource_id: Resource ID or name

        Returns:
            List of tags
        """
        # Find the resource
        resource = self._find_resource_by_type(resource_type, resource_id)
        if not resource:
            raise ValueError(f"Resource not found: {resource_type}/{resource_id}")

        # Get tags_service for the resource
        resource_service = self._get_resource_service(resource_type, resource.id)
        tags_service = resource_service.tags_service()

        try:
            tags = tags_service.list()
        except Exception as e:
            logger.error(f"Failed to list resource tags: {e}")
            return []

        result = []
        for tag in tags:
            result.append({
                "id": tag.id,
                "name": tag.name,
                "description": tag.description or "",
            })

        return result

    # -- Extended user management --------------------------------------------------------

    @require_connection
    def create_user(self, user_name: str, domain: str,
                   email: str = None, department: str = None) -> Dict[str, Any]:
        """Create user

        Args:
            user_name: User name (format: user@domain)
            domain: Domain name
            email: Email address
            department: Department

        Returns:
            Creation result
        """
        users_service = self.connection.system_service().users_service()

        # Find the domain
        domains_service = self.connection.system_service().domains_service()
        domains = domains_service.list(search=f"name={_sanitize_search_value(domain)}")
        if not domains:
            raise ValueError(f"Domain not found: {domain}")

        try:
            user = users_service.add(
                sdk.types.User(
                    user_name=user_name,
                    domain=sdk.types.Domain(id=domains[0].id),
                    email=email,
                    department=department,
                )
            )

            return {
                "success": True,
                "message": f"User {user_name} created",
                "user_id": user.id,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to create user: {e}")

    @require_connection
    def update_user(self, name_or_id: str, email: str = None,
                   department: str = None) -> Dict[str, Any]:
        """Update user

        Args:
            name_or_id: User name or ID
            email: New email
            department: New department

        Returns:
            Update result
        """
        user = self._find_user(name_or_id)
        if not user:
            raise ValueError(f"User not found: {name_or_id}")

        users_service = self.connection.system_service().users_service()
        user_service = users_service.user_service(user.id)

        if email is not None:
            user.email = email
        if department is not None:
            user.department = department

        try:
            user_service.update(user)
            return {"success": True, "message": f"User updated"}
        except Exception as e:
            raise RuntimeError(f"Failed to update user: {e}")

    @require_connection
    def delete_user(self, name_or_id: str) -> Dict[str, Any]:
        """Delete user

        Args:
            name_or_id: User name or ID

        Returns:
            Deletion result
        """
        user = self._find_user(name_or_id)
        if not user:
            raise ValueError(f"User not found: {name_or_id}")

        users_service = self.connection.system_service().users_service()
        user_service = users_service.user_service(user.id)

        try:
            user_service.remove()
            return {"success": True, "message": f"User {user.name} deleted"}
        except Exception as e:
            raise RuntimeError(f"Failed to delete user: {e}")

    @require_connection
    def list_user_groups(self, name_or_id: str) -> List[Dict]:
        """List groups for a user

        Args:
            name_or_id: User name or ID

        Returns:
            List of groups
        """
        user = self._find_user(name_or_id)
        if not user:
            raise ValueError(f"User not found: {name_or_id}")

        users_service = self.connection.system_service().users_service()
        user_service = users_service.user_service(user.id)
        groups_service = user_service.groups_service()

        try:
            groups = groups_service.list()
        except Exception as e:
            logger.error(f"Failed to get user groups: {e}")
            return []

        return [
            {
                "id": g.id,
                "name": g.name,
                "domain": g.domain.name if g.domain else "",
            }
            for g in groups
        ]

    # -- Extended role management --------------------------------------------------------

    @require_connection
    def update_role(self, name_or_id: str, new_name: str = None,
                   description: str = None,
                   administrative: bool = None) -> Dict[str, Any]:
        """Update role

        Args:
            name_or_id: Role name or ID
            new_name: New name
            description: New description
            administrative: Whether it is an administrative role

        Returns:
            Update result
        """
        role = self._find_role(name_or_id)
        if not role:
            raise ValueError(f"Role not found: {name_or_id}")

        roles_service = self.connection.system_service().roles_service()
        role_service = roles_service.role_service(role.id)

        if new_name:
            role.name = new_name
        if description is not None:
            role.description = description
        if administrative is not None:
            role.administrative = administrative

        try:
            role_service.update(role)
            return {"success": True, "message": f"Role updated"}
        except Exception as e:
            raise RuntimeError(f"Failed to update role: {e}")

    # -- Filter management ----------------------------------------------------------

    @require_connection
    def list_filters(self) -> List[Dict]:
        """List permission filters

        Returns:
            List of filters
        """
        # oVirt 4.5 REST exposes no permission-filter collection (the API root
        # lists no `filters`, and `/api/filters`, `/api/permissionfilters`
        # are 404), so SystemService has no `filters_service`. Fail loudly
        # instead of crashing with AttributeError or reporting an empty list.
        raise ValueError(
            "Permission filters unavailable: current oVirt API does not provide a permission filters collection"
        )


# MCP tool registry
MCP_TOOLS = {
    # User management
    "user_list": {"method": "list_users", "description": "List users"},
    "user_get": {"method": "get_user", "description": "Get user details"},
    "user_create": {"method": "create_user", "description": "Create user"},
    "user_update": {"method": "update_user", "description": "Update user"},
    "user_delete": {"method": "delete_user", "description": "Delete user"},
    "user_groups": {"method": "list_user_groups", "description": "List groups for a user"},

    # Group management
    "group_list": {"method": "list_groups", "description": "List groups"},
    "group_get": {"method": "get_group", "description": "Get group details"},

    # Role management
    "role_list": {"method": "list_roles", "description": "List roles"},
    "role_get": {"method": "get_role", "description": "Get role details"},
    "role_create": {"method": "create_role", "description": "Create role"},
    "role_update": {"method": "update_role", "description": "Update role"},
    "role_delete": {"method": "delete_role", "description": "Delete role"},

    # Permit management
    "permit_list": {"method": "list_permits", "description": "List all permits"},

    # Permission management
    "permission_list": {"method": "list_permissions", "description": "List resource permissions"},
    "permission_assign": {"method": "assign_permission", "description": "Assign permission"},
    "permission_revoke": {"method": "revoke_permission", "description": "Revoke permission"},

    # Tag management
    "tag_list": {"method": "list_tags", "description": "List all tags"},
    "tag_create": {"method": "create_tag", "description": "Create tag"},
    "tag_delete": {"method": "delete_tag", "description": "Delete tag"},
    "tag_assign": {"method": "assign_tag", "description": "Assign tag to resource"},
    "tag_unassign": {"method": "unassign_tag", "description": "Remove tag from resource"},
    "tag_list_resources": {"method": "list_resource_tags", "description": "List resource tags"},

    # Filter management
    "filter_list": {"method": "list_filters", "description": "List permission filters"},
}
