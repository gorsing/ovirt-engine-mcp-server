#!/usr/bin/env python3
"""
oVirt MCP Server - Model Context Protocol server for oVirt/RHV.

Provides 30+ tools for managing VMs, hosts, clusters, networks,
storage domains, templates, snapshots, and disks via MCP protocol.
"""

import asyncio
import functools
import logging
import signal
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .config import Config, load_config, sanitize_log_message
from .errors import (
    OvirtMCPError,
    OvirtConnectionError,
    NotFoundError,
    OvirtPermissionError,
    ValidationError as OvirtValidationError,
    OvirtTimeoutError,
    SDKError,
)
from .ovirt_mcp import OvirtMCP
from .validation import validate_tool_args, ValidationError
from .mcp_extensions import (
    NetworkMCP,
    ClusterMCP,
    TemplateMCP,
    MCP_TOOLS as EXTENSIONS_MCP_TOOLS,
)
from .mcp_datacenter import DataCenterMCP, MCP_TOOLS as DATACENTER_MCP_TOOLS
from .mcp_host_extended import HostExtendedMCP, MCP_TOOLS as HOST_EXTENDED_MCP_TOOLS
from .mcp_storage_extended import StorageExtendedMCP, MCP_TOOLS as STORAGE_EXTENDED_MCP_TOOLS
from .mcp_disk_extended import DiskExtendedMCP, MCP_TOOLS as DISK_EXTENDED_MCP_TOOLS
from .mcp_events import EventsMCP, MCP_TOOLS as EVENTS_MCP_TOOLS
from .mcp_affinity import AffinityMCP, MCP_TOOLS as AFFINITY_MCP_TOOLS
from .mcp_rbac import RbacMCP, MCP_TOOLS as RBAC_MCP_TOOLS
from .mcp_vm_extended import VmExtendedMCP, MCP_TOOLS as VM_EXTENDED_MCP_TOOLS
from .mcp_template_extended import TemplateExtendedMCP, MCP_TOOLS as TEMPLATE_EXTENDED_MCP_TOOLS
from .mcp_quota import QuotaMCP, MCP_TOOLS as QUOTA_MCP_TOOLS
from .mcp_system import SystemMCP, MCP_TOOLS as SYSTEM_MCP_TOOLS

# Merge all MCP_TOOLS
MCP_TOOLS = {
    **EXTENSIONS_MCP_TOOLS,
    **DATACENTER_MCP_TOOLS,
    **HOST_EXTENDED_MCP_TOOLS,
    **STORAGE_EXTENDED_MCP_TOOLS,
    **DISK_EXTENDED_MCP_TOOLS,
    **EVENTS_MCP_TOOLS,
    **AFFINITY_MCP_TOOLS,
    **RBAC_MCP_TOOLS,
    **VM_EXTENDED_MCP_TOOLS,
    **TEMPLATE_EXTENDED_MCP_TOOLS,
    **QUOTA_MCP_TOOLS,
    **SYSTEM_MCP_TOOLS,
}

logger = logging.getLogger(__name__)

# -- Tool schemas ------------------------------------------------------

TOOL_SCHEMAS: Dict[str, dict] = {
    # VM tools
    "vm_list": {
        "type": "object",
        "properties": {
            "cluster": {"type": "string", "description": "Cluster name (optional, for filtering)"},
            "status": {"type": "string", "description": "VM status filter (up/down)"},
        },
    },
    "vm_get": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "VM name or ID"}},
        "required": ["name_or_id"],
    },
    "vm_create": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "VM name"},
            "cluster": {"type": "string", "description": "Target cluster"},
            "memory_mb": {"type": "number", "description": "Memory (MB), default 4096"},
            "cpu_cores": {"type": "number", "description": "CPU cores, default 2"},
            "template": {"type": "string", "description": "Template name, default Blank"},
            "disk_size_gb": {"type": "number", "description": "Disk size (GB), default 50"},
            "description": {"type": "string", "description": "VM description"},
        },
        "required": ["name", "cluster"],
    },
    "vm_start": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "VM name or ID"}},
        "required": ["name_or_id"],
    },
    "vm_stop": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM name or ID"},
            "graceful": {"type": "boolean", "description": "Graceful shutdown, default true"},
        },
        "required": ["name_or_id"],
    },
    "vm_restart": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "VM name or ID"}},
        "required": ["name_or_id"],
    },
    "vm_delete": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM name or ID"},
            "force": {"type": "boolean", "description": "Force delete, default false"},
        },
        "required": ["name_or_id"],
    },
    "vm_update_resources": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM name or ID"},
            "memory_mb": {"type": "number", "description": "New memory (MB)"},
            "cpu_cores": {"type": "number", "description": "New CPU cores"},
        },
        "required": ["name_or_id"],
    },
    "vm_rename": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Current VM name or ID"},
            "new_name": {"type": "string", "description": "New name"},
        },
        "required": ["name_or_id", "new_name"],
    },
    "vm_stats": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "VM name or ID"}},
        "required": ["name_or_id"],
    },

    # Snapshot tools
    "snapshot_list": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "VM name or ID"}},
        "required": ["name_or_id"],
    },
    "snapshot_create": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM name or ID"},
            "description": {"type": "string", "description": "Snapshot description"},
        },
        "required": ["name_or_id"],
    },
    "snapshot_restore": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM name or ID"},
            "snapshot_id": {"type": "string", "description": "Snapshot ID"},
        },
        "required": ["name_or_id", "snapshot_id"],
    },
    "snapshot_delete": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM name or ID"},
            "snapshot_id": {"type": "string", "description": "Snapshot ID"},
        },
        "required": ["name_or_id", "snapshot_id"],
    },

    # Disk tools
    "disk_list": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM name or ID (optional)"},
            "storage_domain": {"type": "string", "description": "Storage domain name (optional)"},
        },
    },
    "disk_create": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Disk name"},
            "size_gb": {"type": "number", "description": "Disk size (GB)"},
            "storage_domain": {"type": "string", "description": "Storage domain name"},
            "format": {"type": "string", "description": "Disk format (cow/raw), default cow"},
        },
        "required": ["name", "size_gb"],
    },
    "disk_attach": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM name or ID"},
            "disk_id": {"type": "string", "description": "Disk ID"},
        },
        "required": ["name_or_id", "disk_id"],
    },

    # Network tools
    "network_list": {
        "type": "object",
        "properties": {"cluster": {"type": "string", "description": "Cluster name (optional)"}},
    },
    "network_create": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Network name"},
            "datacenter": {"type": "string", "description": "Data center name"},
            "vlan": {"type": "string", "description": "VLAN ID (optional)"},
            "description": {"type": "string", "description": "Description"},
            "mtu": {"type": "number", "description": "MTU"},
        },
        "required": ["name", "datacenter"],
    },
    "network_update": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Network name"},
            "new_name": {"type": "string", "description": "New name"},
            "description": {"type": "string", "description": "New description"},
            "mtu": {"type": "number", "description": "New MTU"},
        },
        "required": ["name"],
    },
    "network_delete": {
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Network name"}},
        "required": ["name"],
    },
    "nic_list": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "VM name or ID"}},
        "required": ["name_or_id"],
    },
    "nic_add": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM name or ID"},
            "nic_name": {"type": "string", "description": "NIC name"},
            "network": {"type": "string", "description": "Network name"},
        },
        "required": ["name_or_id", "nic_name", "network"],
    },
    "nic_remove": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM name or ID"},
            "nic_name": {"type": "string", "description": "NIC name"},
        },
        "required": ["name_or_id", "nic_name"],
    },

    # Host tools
    "host_list": {
        "type": "object",
        "properties": {"cluster": {"type": "string", "description": "Cluster name (optional)"}},
    },
    "host_activate": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Host name or ID"}},
        "required": ["name_or_id"],
    },
    "host_deactivate": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Host name or ID"}},
        "required": ["name_or_id"],
    },

    # Cluster tools
    "cluster_list": {"type": "object", "properties": {}},
    "cluster_get": {
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Cluster name"}},
        "required": ["name"],
    },
    "cluster_memory_usage": {
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Cluster name"}},
        "required": ["name"],
    },
    "cluster_hosts": {
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Cluster name"}},
        "required": ["name"],
    },
    "cluster_vms": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Cluster name"},
            "status": {"type": "string", "description": "VM status filter (optional)"},
        },
        "required": ["name"],
    },
    "cluster_cpu_load": {
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Cluster name"}},
        "required": ["name"],
    },

    # Storage tools
    "storage_list": {"type": "object", "properties": {}},
    "storage_attach": {
        "type": "object",
        "properties": {
            "storage_name": {"type": "string", "description": "Storage domain name"},
            "dc_name": {"type": "string", "description": "Data center name"},
        },
        "required": ["storage_name", "dc_name"],
    },

    # Template tools
    "template_list": {
        "type": "object",
        "properties": {"cluster": {"type": "string", "description": "Cluster name (optional)"}},
    },
    "template_vm_create": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "VM name"},
            "template": {"type": "string", "description": "Template name"},
            "cluster": {"type": "string", "description": "Target cluster"},
            "memory_mb": {"type": "number", "description": "Memory (MB) (optional)"},
            "cpu_cores": {"type": "number", "description": "CPU cores (optional)"},
        },
        "required": ["name", "template", "cluster"],
    },

    # DataCenter tools
    "datacenter_list": {"type": "object", "properties": {}},
    "datacenter_get": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Data center name or ID"}},
        "required": ["name_or_id"],
    },
    "datacenter_create": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Data center name"},
            "storage_type": {"type": "string", "description": "Storage type (nfs/fc/iscsi etc.), default nfs"},
            "description": {"type": "string", "description": "Description"},
        },
        "required": ["name"],
    },
    "datacenter_update": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Data center name or ID"},
            "new_name": {"type": "string", "description": "New name (optional)"},
            "description": {"type": "string", "description": "New description (optional)"},
        },
        "required": ["name_or_id"],
    },
    "datacenter_delete": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Data center name or ID"}},
        "required": ["name_or_id"],
    },

    # Host Extended tools
    "host_get": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Host name or ID"}},
        "required": ["name_or_id"],
    },
    "host_add": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Host name"},
            "cluster": {"type": "string", "description": "Cluster name"},
            "address": {"type": "string", "description": "Host address"},
            "password": {"type": "string", "description": "SSH password (optional)"},
            "ssh_port": {"type": "number", "description": "SSH port, default 22"},
        },
        "required": ["name", "cluster", "address"],
    },
    "host_remove": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Host name or ID"},
            "force": {"type": "boolean", "description": "Force remove, default false"},
        },
        "required": ["name_or_id"],
    },
    "host_stats": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Host name or ID"}},
        "required": ["name_or_id"],
    },
    "host_devices": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Host name or ID"}},
        "required": ["name_or_id"],
    },

    # Storage Extended tools
    "storage_get": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Storage domain name or ID"}},
        "required": ["name_or_id"],
    },
    "storage_create": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Storage domain name"},
            "storage_type": {"type": "string", "description": "Storage type (nfs/fc/iscsi etc.)"},
            "host": {"type": "string", "description": "Host name"},
            "path": {"type": "string", "description": "Storage path"},
            "datacenter": {"type": "string", "description": "Data center name (optional)"},
            "description": {"type": "string", "description": "Description"},
            "domain_type": {"type": "string", "description": "Domain type (data/iso/export), default data"},
        },
        "required": ["name", "storage_type", "host", "path"],
    },
    "storage_delete": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Storage domain name or ID"},
            "force": {"type": "boolean", "description": "Force delete, default false"},
        },
        "required": ["name_or_id"],
    },
    "storage_detach": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Storage domain name or ID"},
            "datacenter": {"type": "string", "description": "Data center name (optional)"},
        },
        "required": ["name_or_id"],
    },
    "storage_attach_to_dc": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Storage domain name or ID"},
            "datacenter": {"type": "string", "description": "Data center name"},
        },
        "required": ["name_or_id", "datacenter"],
    },
    "storage_stats": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Storage domain name or ID"}},
        "required": ["name_or_id"],
    },

    # Disk Extended tools
    "disk_get": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Disk name or ID"}},
        "required": ["name_or_id"],
    },
    "disk_delete": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Disk name or ID"},
            "force": {"type": "boolean", "description": "Force delete, default false"},
        },
        "required": ["name_or_id"],
    },
    "disk_resize": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Disk name or ID"},
            "new_size_gb": {"type": "number", "description": "New size (GB)"},
        },
        "required": ["name_or_id", "new_size_gb"],
    },
    "disk_detach": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Disk name or ID"},
            "vm_name_or_id": {"type": "string", "description": "VM name or ID"},
        },
        "required": ["name_or_id", "vm_name_or_id"],
    },
    "disk_move": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Disk name or ID"},
            "target_storage_domain": {"type": "string", "description": "Target storage domain name"},
        },
        "required": ["name_or_id", "target_storage_domain"],
    },
    "disk_stats": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Disk name or ID"}},
        "required": ["name_or_id"],
    },

    # Events tools
    "event_list": {
        "type": "object",
        "properties": {
            "search": {"type": "string", "description": "Search filter (optional)"},
            "severity": {"type": "string", "description": "Severity filter (error/warning/info/alert)"},
            "page": {"type": "number", "description": "Page number, default 1"},
            "page_size": {"type": "number", "description": "Items per page, default 50"},
        },
    },
    "event_get": {
        "type": "object",
        "properties": {"event_id": {"type": "string", "description": "Event ID"}},
        "required": ["event_id"],
    },
    "event_search": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "page": {"type": "number", "description": "Page number, default 1"},
            "page_size": {"type": "number", "description": "Items per page, default 50"},
        },
        "required": ["query"],
    },
    "event_alerts": {
        "type": "object",
        "properties": {
            "page": {"type": "number", "description": "Page number, default 1"},
            "page_size": {"type": "number", "description": "Items per page, default 50"},
        },
    },
    "event_errors": {
        "type": "object",
        "properties": {
            "page": {"type": "number", "description": "Page number, default 1"},
            "page_size": {"type": "number", "description": "Items per page, default 50"},
        },
    },
    "event_warnings": {
        "type": "object",
        "properties": {
            "page": {"type": "number", "description": "Page number, default 1"},
            "page_size": {"type": "number", "description": "Items per page, default 50"},
        },
    },
    "event_summary": {
        "type": "object",
        "properties": {"hours": {"type": "number", "description": "Summarize the last N hours, default 24"}},
    },
    "event_acknowledge": {
        "type": "object",
        "properties": {"event_id": {"type": "string", "description": "Event ID"}},
        "required": ["event_id"],
    },
    "event_clear_alerts": {"type": "object", "properties": {}},

    # Affinity Group tools
    "affinity_group_list": {
        "type": "object",
        "properties": {"cluster": {"type": "string", "description": "Cluster name"}},
        "required": ["cluster"],
    },
    "affinity_group_get": {
        "type": "object",
        "properties": {
            "cluster": {"type": "string", "description": "Cluster name"},
            "name_or_id": {"type": "string", "description": "Affinity group name or ID"},
        },
        "required": ["cluster", "name_or_id"],
    },
    "affinity_group_create": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Affinity group name"},
            "cluster": {"type": "string", "description": "Cluster name"},
            "positive": {"type": "boolean", "description": "True=affinity, False=anti-affinity, default True"},
            "enforcing": {"type": "boolean", "description": "True=enforced, False=soft rule, default False"},
            "vms": {"type": "array", "items": {"type": "string"}, "description": "List of VM names or IDs"},
        },
        "required": ["name", "cluster"],
    },
    "affinity_group_update": {
        "type": "object",
        "properties": {
            "cluster": {"type": "string", "description": "Cluster name"},
            "name_or_id": {"type": "string", "description": "Affinity group name or ID"},
            "new_name": {"type": "string", "description": "New name (optional)"},
            "positive": {"type": "boolean", "description": "True=affinity, False=anti-affinity"},
            "enforcing": {"type": "boolean", "description": "True=enforced, False=soft rule"},
        },
        "required": ["cluster", "name_or_id"],
    },
    "affinity_group_delete": {
        "type": "object",
        "properties": {
            "cluster": {"type": "string", "description": "Cluster name"},
            "name_or_id": {"type": "string", "description": "Affinity group name or ID"},
        },
        "required": ["cluster", "name_or_id"],
    },
    "affinity_group_add_vm": {
        "type": "object",
        "properties": {
            "cluster": {"type": "string", "description": "Cluster name"},
            "affinity_group": {"type": "string", "description": "Affinity group name or ID"},
            "vm": {"type": "string", "description": "VM name or ID"},
        },
        "required": ["cluster", "affinity_group", "vm"],
    },
    "affinity_group_remove_vm": {
        "type": "object",
        "properties": {
            "cluster": {"type": "string", "description": "Cluster name"},
            "affinity_group": {"type": "string", "description": "Affinity group name or ID"},
            "vm": {"type": "string", "description": "VM name or ID"},
        },
        "required": ["cluster", "affinity_group", "vm"],
    },

    # RBAC - User tools
    "user_groups": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "User name or ID"}
        },
        "required": ["name_or_id"],
    },
    "user_list": {
        "type": "object",
        "properties": {"search": {"type": "string", "description": "Search filter (optional)"}},
    },
    "user_get": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "User name or ID"}},
        "required": ["name_or_id"],
    },

    # RBAC - Group tools
    "group_list": {
        "type": "object",
        "properties": {"search": {"type": "string", "description": "Search filter (optional)"}},
    },
    "group_get": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Group name or ID"}},
        "required": ["name_or_id"],
    },

    # RBAC - Role tools
    "role_list": {"type": "object", "properties": {}},
    "role_get": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Role name or ID"}},
        "required": ["name_or_id"],
    },
    "role_create": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Role name"},
            "description": {"type": "string", "description": "Description (optional)"},
            "administrative": {"type": "boolean", "description": "Whether the role is administrative, default false"},
            "permit_ids": {"type": "array", "items": {"type": "string"}, "description": "List of permit IDs"},
        },
        "required": ["name"],
    },
    "role_delete": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Role name or ID"}},
        "required": ["name_or_id"],
    },

    # RBAC - Permit tools
    "permit_list": {"type": "object", "properties": {}},

    # RBAC - Permission tools
    "permission_list": {
        "type": "object",
        "properties": {
            "resource_type": {"type": "string", "description": "Resource type (vm/host/cluster/datacenter/network/storagedomain/template)"},
            "resource_id": {"type": "string", "description": "Resource ID or name"},
        },
        "required": ["resource_type", "resource_id"],
    },
    "permission_assign": {
        "type": "object",
        "properties": {
            "resource_type": {"type": "string", "description": "Resource type (vm/host/cluster/datacenter/network/storagedomain/template)"},
            "resource_id": {"type": "string", "description": "Resource ID or name"},
            "user_or_group": {"type": "string", "description": "Principal type (user or group)"},
            "role_name": {"type": "string", "description": "Role name or ID"},
            "principal_name": {"type": "string", "description": "User or group name"},
        },
        "required": ["resource_type", "resource_id", "user_or_group", "role_name", "principal_name"],
    },
    "permission_revoke": {
        "type": "object",
        "properties": {
            "resource_type": {"type": "string", "description": "Resource type"},
            "resource_id": {"type": "string", "description": "Resource ID or name"},
            "permission_id": {"type": "string", "description": "Permission ID"},
        },
        "required": ["resource_type", "resource_id", "permission_id"],
    },

    # RBAC - Tag tools
    "tag_list": {"type": "object", "properties": {}},
    "tag_create": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Tag name"},
            "description": {"type": "string", "description": "Description (optional)"},
            "parent_name": {"type": "string", "description": "Parent tag name (optional)"},
        },
        "required": ["name"],
    },
    "tag_delete": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Label name or ID"}},
        "required": ["name_or_id"],
    },
    "tag_assign": {
        "type": "object",
        "properties": {
            "resource_type": {"type": "string", "description": "Resource type (vm/host/cluster/datacenter/network/storagedomain/template)"},
            "resource_id": {"type": "string", "description": "Resource ID or name"},
            "tag_name": {"type": "string", "description": "Tag name or ID"},
        },
        "required": ["resource_type", "resource_id", "tag_name"],
    },
    "tag_unassign": {
        "type": "object",
        "properties": {
            "resource_type": {"type": "string", "description": "Resource type"},
            "resource_id": {"type": "string", "description": "Resource ID or name"},
            "tag_name": {"type": "string", "description": "Tag name or ID"},
        },
        "required": ["resource_type", "resource_id", "tag_name"],
    },
    "tag_list_resources": {
        "type": "object",
        "properties": {
            "resource_type": {"type": "string", "description": "Resource type"},
            "resource_id": {"type": "string", "description": "Resource ID or name"},
        },
        "required": ["resource_type", "resource_id"],
    },

    # -- VM Extended tools -----------------------------------------------------
    "vm_migrate": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM name or ID"},
            "target_host": {"type": "string", "description": "Target host name or ID (optional)"},
        },
        "required": ["name_or_id"],
    },
    "vm_console": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM name or ID"},
            "console_type": {"type": "string", "description": "Console type (spice/vnc), default spice"},
        },
        "required": ["name_or_id"],
    },
    "vm_cdrom_list": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "VM name or ID"}},
        "required": ["name_or_id"],
    },
    "vm_cdrom_update": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM name or ID"},
            "cdrom_id": {"type": "string", "description": "CDROM ID"},
            "iso_file": {"type": "string", "description": "ISO file path"},
            "eject": {"type": "boolean", "description": "Whether to eject the CD"},
        },
        "required": ["name_or_id", "cdrom_id"],
    },
    "vm_hostdevice_list": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "VM name or ID"}},
        "required": ["name_or_id"],
    },
    "vm_hostdevice_attach": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM name or ID"},
            "device_name": {"type": "string", "description": "Device name"},
        },
        "required": ["name_or_id", "device_name"],
    },
    "vm_hostdevice_detach": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM name or ID"},
            "device_name": {"type": "string", "description": "Device name"},
        },
        "required": ["name_or_id", "device_name"],
    },
    "vm_mediated_device_list": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "VM name or ID"}},
        "required": ["name_or_id"],
    },
    "vm_numa_list": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "VM name or ID"}},
        "required": ["name_or_id"],
    },
    "vm_watchdog_list": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "VM name or ID"}},
        "required": ["name_or_id"],
    },
    "vm_watchdog_update": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM name or ID"},
            "watchdog_id": {"type": "string", "description": "Watchdog ID"},
            "action": {"type": "string", "description": "Trigger action (none/reset/poweroff/shutdown/dump)"},
        },
        "required": ["name_or_id", "watchdog_id"],
    },
    "vm_pin_to_host": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM name or ID"},
            "host": {"type": "string", "description": "Host name or ID"},
            "pin_policy": {"type": "string", "description": "Pin policy (user/resizable/migratable)"},
        },
        "required": ["name_or_id", "host"],
    },
    "vm_session_list": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "VM name or ID"}},
        "required": ["name_or_id"],
    },
    "vm_pool_list": {
        "type": "object",
        "properties": {"cluster": {"type": "string", "description": "Cluster name (optional)"}},
    },
    "vm_pool_get": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "VM pool name or ID"}},
        "required": ["name_or_id"],
    },
    "vm_pool_create": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Pool name"},
            "template": {"type": "string", "description": "Template name"},
            "cluster": {"type": "string", "description": "Cluster name"},
            "size": {"type": "number", "description": "Pool size, default 5"},
            "description": {"type": "string", "description": "Description"},
            "max_user_vms": {"type": "number", "description": "Max VMs per user, default 1"},
            "prestarted_vms": {"type": "number", "description": "Prestarted VMs, default 0"},
            "stateful": {"type": "boolean", "description": "Stateful, default false"},
        },
        "required": ["name", "template", "cluster"],
    },
    "vm_pool_delete": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM pool name or ID"},
            "force": {"type": "boolean", "description": "Force delete"},
        },
        "required": ["name_or_id"],
    },
    "vm_pool_update": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM pool name or ID"},
            "new_name": {"type": "string", "description": "New name"},
            "size": {"type": "number", "description": "New size"},
            "description": {"type": "string", "description": "New description"},
            "prestarted_vms": {"type": "number", "description": "Prestarted VMs"},
        },
        "required": ["name_or_id"],
    },
    "vm_checkpoint_list": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "VM name or ID"}},
        "required": ["name_or_id"],
    },
    "vm_checkpoint_create": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM name or ID"},
            "description": {"type": "string", "description": "Checkpoint description"},
        },
        "required": ["name_or_id"],
    },
    "vm_checkpoint_restore": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM name or ID"},
            "checkpoint_id": {"type": "string", "description": "Checkpoint ID"},
        },
        "required": ["name_or_id", "checkpoint_id"],
    },
    "vm_checkpoint_delete": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "VM name or ID"},
            "checkpoint_id": {"type": "string", "description": "Checkpoint ID"},
        },
        "required": ["name_or_id", "checkpoint_id"],
    },

    # -- Template Extended tools -----------------------------------------------
    "template_get": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Template name or ID"}},
        "required": ["name_or_id"],
    },
    "template_create": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Template name"},
            "vm": {"type": "string", "description": "Source VM name or ID"},
            "description": {"type": "string", "description": "Description"},
            "cluster": {"type": "string", "description": "Target cluster (optional)"},
        },
        "required": ["name", "vm"],
    },
    "template_delete": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Template name or ID"},
            "force": {"type": "boolean", "description": "Force delete"},
        },
        "required": ["name_or_id"],
    },
    "template_update": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Template name or ID"},
            "new_name": {"type": "string", "description": "New name"},
            "description": {"type": "string", "description": "New description"},
            "memory_mb": {"type": "number", "description": "Memory (MB)"},
            "cpu_cores": {"type": "number", "description": "CPU cores"},
        },
        "required": ["name_or_id"],
    },
    "template_disk_list": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Template name or ID"}},
        "required": ["name_or_id"],
    },
    "template_nic_list": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Template name or ID"}},
        "required": ["name_or_id"],
    },
    "instance_type_list": {"type": "object", "properties": {}},
    "instance_type_get": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Instance type name or ID"}},
        "required": ["name_or_id"],
    },

    # -- Quota tools -----------------------------------------------------------
    "quota_list": {
        "type": "object",
        "properties": {"datacenter": {"type": "string", "description": "Data center name or ID"}},
        "required": ["datacenter"],
    },
    "quota_get": {
        "type": "object",
        "properties": {
            "datacenter": {"type": "string", "description": "Data center name or ID"},
            "name_or_id": {"type": "string", "description": "Quota name or ID"},
        },
        "required": ["datacenter", "name_or_id"],
    },
    "quota_create": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Quota name"},
            "datacenter": {"type": "string", "description": "Data center name"},
            "description": {"type": "string", "description": "Description"},
            "cluster_hard_limit_pct": {"type": "number", "description": "Cluster hard limit percentage"},
            "storage_hard_limit_pct": {"type": "number", "description": "Storage hard limit percentage"},
        },
        "required": ["name", "datacenter"],
    },
    "quota_update": {
        "type": "object",
        "properties": {
            "datacenter": {"type": "string", "description": "Data center name or ID"},
            "name_or_id": {"type": "string", "description": "Quota name or ID"},
            "new_name": {"type": "string", "description": "New name"},
            "description": {"type": "string", "description": "New description"},
            "cluster_hard_limit_pct": {"type": "number", "description": "Cluster hard limit percentage"},
            "storage_hard_limit_pct": {"type": "number", "description": "Storage hard limit percentage"},
        },
        "required": ["datacenter", "name_or_id"],
    },
    "quota_delete": {
        "type": "object",
        "properties": {
            "datacenter": {"type": "string", "description": "Data center name or ID"},
            "name_or_id": {"type": "string", "description": "Quota name or ID"},
        },
        "required": ["datacenter", "name_or_id"],
    },
    "quota_cluster_limit_list": {
        "type": "object",
        "properties": {
            "datacenter": {"type": "string", "description": "Data center name or ID"},
            "name_or_id": {"type": "string", "description": "Quota name or ID"},
        },
        "required": ["datacenter", "name_or_id"],
    },
    "quota_storage_limit_list": {
        "type": "object",
        "properties": {
            "datacenter": {"type": "string", "description": "Data center name or ID"},
            "name_or_id": {"type": "string", "description": "Quota name or ID"},
        },
        "required": ["datacenter", "name_or_id"],
    },

    # -- System tools ----------------------------------------------------------
    "system_get": {"type": "object", "properties": {}},
    "system_option_list": {
        "type": "object",
        "properties": {"category": {"type": "string", "description": "Option category (optional)"}},
    },
    "job_list": {
        "type": "object",
        "properties": {
            "page": {"type": "number", "description": "Page number"},
            "page_size": {"type": "number", "description": "Items per page"},
        },
    },
    "job_get": {
        "type": "object",
        "properties": {"job_id": {"type": "string", "description": "Job ID"}},
        "required": ["job_id"],
    },
    "job_cancel": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "Job ID"},
            "force": {"type": "boolean", "description": "Force cancel"},
        },
        "required": ["job_id"],
    },
    "system_statistics": {"type": "object", "properties": {}},

    # -- Network Extended tools ------------------------------------------------
    "network_get": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Network name or ID"}},
        "required": ["name_or_id"],
    },
    "vnic_profile_list": {
        "type": "object",
        "properties": {"network": {"type": "string", "description": "Network name (optional)"}},
    },
    "vnic_profile_get": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Profile name or ID"}},
        "required": ["name_or_id"],
    },
    "vnic_profile_create": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Profile name"},
            "network": {"type": "string", "description": "Network name"},
            "description": {"type": "string", "description": "Description"},
            "port_mirroring": {"type": "boolean", "description": "Enable port mirroring"},
        },
        "required": ["name", "network"],
    },
    "vnic_profile_update": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Profile name or ID"},
            "new_name": {"type": "string", "description": "New name"},
            "description": {"type": "string", "description": "New description"},
            "port_mirroring": {"type": "boolean", "description": "Port mirroring setting"},
        },
        "required": ["name_or_id"],
    },
    "vnic_profile_delete": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Profile name or ID"}},
        "required": ["name_or_id"],
    },
    "network_filter_list": {"type": "object", "properties": {}},
    "mac_pool_list": {"type": "object", "properties": {}},
    "qos_list": {
        "type": "object",
        "properties": {"datacenter": {"type": "string", "description": "Data center name (optional)"}},
    },

    # -- Cluster Extended tools ------------------------------------------------
    "cluster_create": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Cluster name"},
            "datacenter": {"type": "string", "description": "Data center name"},
            "cpu_type": {"type": "string", "description": "CPU type"},
            "description": {"type": "string", "description": "Description"},
            "gluster_service": {"type": "boolean", "description": "Whether to enable Gluster service"},
            "threads_per_core": {"type": "number", "description": "Threads per core"},
        },
        "required": ["name", "datacenter", "cpu_type"],
    },
    "cluster_update": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Cluster name or ID"},
            "new_name": {"type": "string", "description": "New name"},
            "description": {"type": "string", "description": "New description"},
            "threads_per_core": {"type": "number", "description": "Threads per core"},
        },
        "required": ["name_or_id"],
    },
    "cluster_delete": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Cluster name or ID"}},
        "required": ["name_or_id"],
    },
    "cpu_profile_list": {
        "type": "object",
        "properties": {"cluster": {"type": "string", "description": "Cluster name or ID"}},
        "required": ["cluster"],
    },
    "cpu_profile_get": {
        "type": "object",
        "properties": {
            "cluster": {"type": "string", "description": "Cluster name or ID"},
            "name_or_id": {"type": "string", "description": "Profile name or ID"},
        },
        "required": ["cluster", "name_or_id"],
    },

    # -- Host Extended tools ---------------------------------------------------
    "host_nic_list": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Host name or ID"}},
        "required": ["name_or_id"],
    },
    "host_nic_update": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Host name or ID"},
            "nic_name": {"type": "string", "description": "NIC name"},
            "custom_properties": {"type": "object", "description": "Custom properties"},
        },
        "required": ["name_or_id", "nic_name"],
    },
    "host_numa_get": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Host name or ID"}},
        "required": ["name_or_id"],
    },
    "host_hook_list": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Host name or ID"}},
        "required": ["name_or_id"],
    },
    "host_fence": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Host name or ID"},
            "action": {"type": "string", "description": "Action type (restart/start/stop/status)"},
        },
        "required": ["name_or_id"],
    },
    "host_network_update": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Host name or ID"},
            "network": {"type": "string", "description": "Network name"},
            "nic": {"type": "string", "description": "NIC name (optional)"},
            "vlan_id": {"type": "number", "description": "VLAN ID (optional)"},
            "bond": {"type": "string", "description": "Bond interface name (optional)"},
        },
        "required": ["name_or_id", "network"],
    },
    "host_device_update": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Host name or ID"},
            "device_name": {"type": "string", "description": "Device name"},
            "enabled": {"type": "boolean", "description": "Whether enabled"},
        },
        "required": ["name_or_id", "device_name"],
    },
    "host_storage_list": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Host name or ID"}},
        "required": ["name_or_id"],
    },
    "host_install": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Host name or ID"},
            "root_password": {"type": "string", "description": "root password"},
            "ssh_key": {"type": "string", "description": "SSH public key"},
            "override_iptables": {"type": "boolean", "description": "Override iptables rules"},
        },
        "required": ["name_or_id"],
    },
    "host_iscsi_discover": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Host name or ID"},
            "address": {"type": "string", "description": "iSCSI target address"},
            "port": {"type": "number", "description": "Port number, default 3260"},
            "username": {"type": "string", "description": "CHAP username (optional)"},
            "password": {"type": "string", "description": "CHAP password (optional)"},
        },
        "required": ["name_or_id", "address"],
    },
    "host_iscsi_login": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Host name or ID"},
            "address": {"type": "string", "description": "iSCSI target address"},
            "target": {"type": "string", "description": "Target name"},
            "port": {"type": "number", "description": "Port number, default 3260"},
            "username": {"type": "string", "description": "CHAP username (optional)"},
            "password": {"type": "string", "description": "CHAP password (optional)"},
        },
        "required": ["name_or_id", "address", "target"],
    },

    # -- Storage Extended tools ------------------------------------------------
    "storage_refresh": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Storage domain name or ID"}},
        "required": ["name_or_id"],
    },
    "storage_update": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Storage domain name or ID"},
            "new_name": {"type": "string", "description": "New name"},
            "description": {"type": "string", "description": "New description"},
            "warning_low_space": {"type": "number", "description": "Low space warning threshold (GB)"},
            "critical_low_space": {"type": "number", "description": "Critical low space threshold (GB)"},
        },
        "required": ["name_or_id"],
    },
    "storage_files": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Storage domain name or ID"}},
        "required": ["name_or_id"],
    },
    "storage_connections_list": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Storage domain name or ID (optional)"}},
    },
    "storage_available_disks": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Storage domain name or ID"}},
        "required": ["name_or_id"],
    },
    "storage_export_vms": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Export domain name or ID"}},
        "required": ["name_or_id"],
    },
    "storage_import_vm": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Export domain name or ID"},
            "vm_name": {"type": "string", "description": "VM name to import"},
            "cluster": {"type": "string", "description": "Target cluster"},
            "storage_domain": {"type": "string", "description": "Target storage domain (optional)"},
            "clone": {"type": "boolean", "description": "Whether to clone"},
        },
        "required": ["name_or_id", "vm_name", "cluster"],
    },
    "disk_snapshot_list": {
        "type": "object",
        "properties": {"disk_name_or_id": {"type": "string", "description": "Disk name or ID"}},
        "required": ["disk_name_or_id"],
    },
    "iscsi_bond_list": {"type": "object", "properties": {}},

    # -- Disk Extended tools ---------------------------------------------------
    "disk_update": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Disk name or ID"},
            "new_name": {"type": "string", "description": "New name"},
            "description": {"type": "string", "description": "New description"},
            "shareable": {"type": "boolean", "description": "Whether shareable"},
            "wipe_after_delete": {"type": "boolean", "description": "Wipe after delete"},
        },
        "required": ["name_or_id"],
    },
    "disk_sparsify": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Disk name or ID"}},
        "required": ["name_or_id"],
    },
    "disk_export": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Disk name or ID"},
            "export_domain": {"type": "string", "description": "Export domain name"},
        },
        "required": ["name_or_id", "export_domain"],
    },

    # -- Events Extended tools -------------------------------------------------
    "event_subscription_list": {
        "type": "object",
        "properties": {"user": {"type": "string", "description": "User name (optional)"}},
    },
    "bookmark_list": {"type": "object", "properties": {}},

    # -- Affinity Extended tools -----------------------------------------------
    "affinity_label_list": {"type": "object", "properties": {}},
    "affinity_label_get": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Label name or ID"}},
        "required": ["name_or_id"],
    },
    "affinity_label_create": {
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Label name"}},
        "required": ["name"],
    },
    "affinity_label_delete": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "Label name or ID"}},
        "required": ["name_or_id"],
    },
    "affinity_label_assign": {
        "type": "object",
        "properties": {
            "label": {"type": "string", "description": "Label name or ID"},
            "resource_type": {"type": "string", "description": "Resource type (vm or host)"},
            "resource": {"type": "string", "description": "Resource name or ID"},
        },
        "required": ["label", "resource_type", "resource"],
    },
    "affinity_label_unassign": {
        "type": "object",
        "properties": {
            "label": {"type": "string", "description": "Label name or ID"},
            "resource_type": {"type": "string", "description": "Resource type (vm or host)"},
            "resource": {"type": "string", "description": "Resource name or ID"},
        },
        "required": ["label", "resource_type", "resource"],
    },

    # -- RBAC Extended tools ---------------------------------------------------
    "user_create": {
        "type": "object",
        "properties": {
            "user_name": {"type": "string", "description": "User name (format: user@domain)"},
            "domain": {"type": "string", "description": "Domain name"},
            "email": {"type": "string", "description": "Email"},
            "department": {"type": "string", "description": "Department"},
        },
        "required": ["user_name", "domain"],
    },
    "user_update": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "User name or ID"},
            "email": {"type": "string", "description": "New email"},
            "department": {"type": "string", "description": "New department"},
        },
        "required": ["name_or_id"],
    },
    "user_delete": {
        "type": "object",
        "properties": {"name_or_id": {"type": "string", "description": "User name or ID"}},
        "required": ["name_or_id"],
    },
    "role_update": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Role name or ID"},
            "new_name": {"type": "string", "description": "New name"},
            "description": {"type": "string", "description": "New description"},
        },
        "required": ["name_or_id"],
    },
    "filter_list": {"type": "object", "properties": {}},
}

DEFAULT_SCHEMA = {"type": "object", "properties": {}}

# -- Extension method mapping -----------------------------------------
# Methods that live on extension classes rather than OvirtMCP directly
EXTENSION_METHODS = {
    # NetworkMCP
    "list_vnics": "network_mcp",
    "create_network": "network_mcp",
    "update_network": "network_mcp",
    "delete_network": "network_mcp",
    # ClusterMCP
    "get_cluster": "cluster_mcp",
    "get_cluster_memory_usage": "cluster_mcp",
    "list_cluster_hosts": "cluster_mcp",
    "list_cluster_vms": "cluster_mcp",
    "get_cluster_cpu_load": "cluster_mcp",
    # TemplateMCP
    "get_template": "template_extended_mcp",
    "clone_template": "template_mcp",
    "create_vm_from_template": "template_mcp",
    # DataCenterMCP
    "list_datacenters": "datacenter_mcp",
    "get_datacenter": "datacenter_mcp",
    "create_datacenter": "datacenter_mcp",
    "update_datacenter": "datacenter_mcp",
    "delete_datacenter": "datacenter_mcp",
    # HostExtendedMCP
    "get_host": "host_extended_mcp",
    "add_host": "host_extended_mcp",
    "remove_host": "host_extended_mcp",
    "get_host_stats": "host_extended_mcp",
    "get_host_devices": "host_extended_mcp",
    # StorageExtendedMCP
    "get_storage_domain": "storage_extended_mcp",
    "create_storage_domain": "storage_extended_mcp",
    "delete_storage_domain": "storage_extended_mcp",
    "detach_storage_domain": "storage_extended_mcp",
    "attach_storage_domain": "storage_extended_mcp",
    "get_storage_domain_stats": "storage_extended_mcp",
    # DiskExtendedMCP
    "get_disk": "disk_extended_mcp",
    "delete_disk": "disk_extended_mcp",
    "resize_disk": "disk_extended_mcp",
    "detach_disk": "disk_extended_mcp",
    "move_disk": "disk_extended_mcp",
    "get_disk_stats": "disk_extended_mcp",
    # EventsMCP
    "list_events": "events_mcp",
    "get_event": "events_mcp",
    "search_events": "events_mcp",
    "get_alerts": "events_mcp",
    "get_errors": "events_mcp",
    "get_warnings": "events_mcp",
    "get_events_summary": "events_mcp",
    "acknowledge_event": "events_mcp",
    "clear_alerts": "events_mcp",
    # AffinityMCP
    "list_affinity_groups": "affinity_mcp",
    "get_affinity_group": "affinity_mcp",
    "create_affinity_group": "affinity_mcp",
    "update_affinity_group": "affinity_mcp",
    "delete_affinity_group": "affinity_mcp",
    "add_vm_to_affinity_group": "affinity_mcp",
    "remove_vm_from_affinity_group": "affinity_mcp",
    # RbacMCP
    "list_users": "rbac_mcp",
    "get_user": "rbac_mcp",
    "create_user": "rbac_mcp",
    "update_user": "rbac_mcp",
    "delete_user": "rbac_mcp",
    "list_user_groups": "rbac_mcp",
    "list_groups": "rbac_mcp",
    "get_group": "rbac_mcp",
    "list_roles": "rbac_mcp",
    "get_role": "rbac_mcp",
    "create_role": "rbac_mcp",
    "update_role": "rbac_mcp",
    "delete_role": "rbac_mcp",
    "list_permits": "rbac_mcp",
    "list_permissions": "rbac_mcp",
    "assign_permission": "rbac_mcp",
    "revoke_permission": "rbac_mcp",
    "list_tags": "rbac_mcp",
    "create_tag": "rbac_mcp",
    "delete_tag": "rbac_mcp",
    "assign_tag": "rbac_mcp",
    "unassign_tag": "rbac_mcp",
    "list_resource_tags": "rbac_mcp",
    "list_filters": "rbac_mcp",

    # VmExtendedMCP
    "migrate_vm": "vm_extended_mcp",
    "get_vm_console": "vm_extended_mcp",
    "list_vm_cdroms": "vm_extended_mcp",
    "update_vm_cdrom": "vm_extended_mcp",
    "list_vm_host_devices": "vm_extended_mcp",
    "attach_vm_host_device": "vm_extended_mcp",
    "detach_vm_host_device": "vm_extended_mcp",
    "list_vm_mediated_devices": "vm_extended_mcp",
    "list_vm_numa_nodes": "vm_extended_mcp",
    "list_vm_watchdogs": "vm_extended_mcp",
    "update_vm_watchdog": "vm_extended_mcp",
    "pin_vm_to_host": "vm_extended_mcp",
    "list_vm_sessions": "vm_extended_mcp",
    "list_vm_pools": "vm_extended_mcp",
    "get_vm_pool": "vm_extended_mcp",
    "create_vm_pool": "vm_extended_mcp",
    "delete_vm_pool": "vm_extended_mcp",
    "update_vm_pool": "vm_extended_mcp",
    "list_vm_checkpoints": "vm_extended_mcp",
    "create_vm_checkpoint": "vm_extended_mcp",
    "restore_vm_checkpoint": "vm_extended_mcp",
    "delete_vm_checkpoint": "vm_extended_mcp",

    # TemplateExtendedMCP
    "get_template_extended": "template_extended_mcp",
    "create_template": "template_extended_mcp",
    "delete_template": "template_extended_mcp",
    "update_template": "template_extended_mcp",
    "list_template_disks": "template_extended_mcp",
    "list_template_nics": "template_extended_mcp",
    "list_instance_types": "template_extended_mcp",
    "get_instance_type": "template_extended_mcp",

    # QuotaMCP
    "list_quotas": "quota_mcp",
    "get_quota": "quota_mcp",
    "create_quota": "quota_mcp",
    "update_quota": "quota_mcp",
    "delete_quota": "quota_mcp",
    "list_quota_cluster_limits": "quota_mcp",
    "list_quota_storage_limits": "quota_mcp",

    # SystemMCP
    "get_system_info": "system_mcp",
    "list_system_options": "system_mcp",
    "list_jobs": "system_mcp",
    "get_job": "system_mcp",
    "cancel_job": "system_mcp",
    "get_system_statistics": "system_mcp",

    # NetworkMCP extended
    "get_network": "network_mcp",
    "list_vnic_profiles": "network_mcp",
    "get_vnic_profile": "network_mcp",
    "create_vnic_profile": "network_mcp",
    "update_vnic_profile": "network_mcp",
    "delete_vnic_profile": "network_mcp",
    "list_network_filters": "network_mcp",
    "list_mac_pools": "network_mcp",
    "list_qos": "network_mcp",

    # ClusterMCP extended
    "create_cluster": "cluster_mcp",
    "update_cluster": "cluster_mcp",
    "delete_cluster": "cluster_mcp",
    "list_cpu_profiles": "cluster_mcp",
    "get_cpu_profile": "cluster_mcp",

    # HostExtendedMCP extended
    "list_host_nics": "host_extended_mcp",
    "update_host_nic": "host_extended_mcp",
    "get_host_numa": "host_extended_mcp",
    "list_host_hooks": "host_extended_mcp",
    "fence_host": "host_extended_mcp",
    "update_host_network": "host_extended_mcp",
    "update_host_device": "host_extended_mcp",
    "list_host_storage": "host_extended_mcp",
    "install_host": "host_extended_mcp",
    "iscsi_discover": "host_extended_mcp",
    "iscsi_login": "host_extended_mcp",

    # StorageExtendedMCP extended
    "refresh_storage_domain": "storage_extended_mcp",
    "update_storage_domain": "storage_extended_mcp",
    "list_storage_files": "storage_extended_mcp",
    "list_storage_connections": "storage_extended_mcp",
    "list_available_disks": "storage_extended_mcp",
    "list_export_vms": "storage_extended_mcp",
    "import_vm_from_export": "storage_extended_mcp",
    "list_disk_snapshots": "storage_extended_mcp",
    "list_iscsi_bonds": "storage_extended_mcp",

    # DiskExtendedMCP extended
    "update_disk": "disk_extended_mcp",
    "sparsify_disk": "disk_extended_mcp",
    "export_disk": "disk_extended_mcp",

    # EventsMCP extended
    "list_event_subscriptions": "events_mcp",
    "list_bookmarks": "events_mcp",

    # AffinityMCP extended
    "list_affinity_labels": "affinity_mcp",
    "get_affinity_label": "affinity_mcp",
    "create_affinity_label": "affinity_mcp",
    "delete_affinity_label": "affinity_mcp",
    "assign_affinity_label": "affinity_mcp",
    "unassign_affinity_label": "affinity_mcp",
}

# Instance attributes holding the extension modules above. Used as a
# last-resort scan in ``_resolve_handler`` so a method missing from
# EXTENSION_METHODS still resolves instead of failing with
# "Method not found" at call time.
EXTENSION_INSTANCE_ATTRS = (
    "network_mcp",
    "cluster_mcp",
    "template_mcp",
    "rbac_mcp",
    "datacenter_mcp",
    "host_extended_mcp",
    "storage_extended_mcp",
    "disk_extended_mcp",
    "events_mcp",
    "affinity_mcp",
    "vm_extended_mcp",
    "template_extended_mcp",
    "quota_mcp",
    "system_mcp",
)


class OvirtMCPServer:
    """oVirt MCP Server — bridges MCP protocol to oVirt Engine SDK."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.server = Server("ovirt-mcp")
        self.connection = OvirtMCP(config)

        # Initialize extension modules
        self.network_mcp = NetworkMCP(self.connection)
        self.cluster_mcp = ClusterMCP(self.connection)
        self.template_mcp = TemplateMCP(self.connection)
        self.rbac_mcp = RbacMCP(self.connection)
        self.datacenter_mcp = DataCenterMCP(self.connection)
        self.host_extended_mcp = HostExtendedMCP(self.connection)
        self.storage_extended_mcp = StorageExtendedMCP(self.connection)
        self.disk_extended_mcp = DiskExtendedMCP(self.connection)
        self.events_mcp = EventsMCP(self.connection)
        self.affinity_mcp = AffinityMCP(self.connection)
        self.vm_extended_mcp = VmExtendedMCP(self.connection)
        self.template_extended_mcp = TemplateExtendedMCP(self.connection)
        self.quota_mcp = QuotaMCP(self.connection)
        self.system_mcp = SystemMCP(self.connection)

        # Build tool registry
        self.tool_handlers: Dict[str, Callable[..., Any]] = {}
        self.tool_descriptions: Dict[str, str] = {}
        self._build_tool_registry()
        self._register_handlers()

        logger.info(f"Registered {len(self.tool_handlers)} MCP tools")

    def _resolve_handler(self, method_name: str) -> Optional[Callable[..., Any]]:
        """Resolve a method name to its handler function."""
        # Check extension classes first
        ext_attr = EXTENSION_METHODS.get(method_name)
        if ext_attr:
            instance = getattr(self, ext_attr, None)
            if instance and hasattr(instance, method_name):
                return getattr(instance, method_name)

        # Fall back to OvirtMCP
        if hasattr(self.connection, method_name):
            return getattr(self.connection, method_name)

        # Last resort: scan every extension instance. EXTENSION_METHODS is a
        # hand-maintained allow-list and used to omit several real methods
        # (list_cluster_hosts, list_cluster_vms, get_cluster_cpu_load,
        # create_vm_from_template), which surfaced as "Method not found".
        for attr in EXTENSION_INSTANCE_ATTRS:
            instance = getattr(self, attr, None)
            if instance is not None and hasattr(instance, method_name):
                return getattr(instance, method_name)

        return None

    def _build_tool_registry(self) -> None:
        """Build unified tool registry from MCP_TOOLS definition."""
        for tool_name, tool_info in MCP_TOOLS.items():
            method_name = tool_info.get("method")
            description = tool_info.get("description", tool_name)

            handler = self._resolve_handler(method_name)
            if handler:
                self.tool_handlers[tool_name] = handler
                self.tool_descriptions[tool_name] = description
            else:
                logger.warning(f"Method not found for tool {tool_name}: {method_name}")

    def _register_handlers(self) -> None:
        """Register MCP protocol handlers."""

        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            tools = []
            for name, description in self.tool_descriptions.items():
                schema = TOOL_SCHEMAS.get(name, DEFAULT_SCHEMA)
                tools.append(
                    Tool(name=name, description=description, inputSchema=schema)
                )
            return tools

        @self.server.call_tool()
        async def call_tool(
            name: str, arguments: Dict[str, Any]
        ) -> List[TextContent]:
            try:
                # Validate input
                validated = validate_tool_args(name, arguments or {})

                handler = self.tool_handlers.get(name)
                if not handler:
                    return [
                        TextContent(type="text", text=f"Unknown tool: {name}")
                    ]

                # Execute handler in thread pool (SDK calls are sync)
                result = await asyncio.get_event_loop().run_in_executor(
                    None, functools.partial(handler, **validated)
                )
                # A *_get lookup that resolves to None means "not found";
                # formatting it plainly reported a bogus success.
                if result is None and name.endswith("_get"):
                    return [
                        TextContent(
                            type="text",
                            text=f"Resource not found: {arguments}",
                        )
                    ]
                return [TextContent(type="text", text=self._format_result(result))]

            except OvirtMCPError as e:
                logger.error(f"Tool error [{name}]: {e.code} - {e.message}")
                return [
                    TextContent(
                        type="text",
                        text=f"[{e.code}] {e.message}"
                        + (" (retryable)" if e.retryable else ""),
                    )
                ]
            except Exception as e:
                logger.error(f"Tool execution failed [{name}]", exc_info=True)
                return [
                    TextContent(
                        type="text",
                        text=f"Operation failed: {type(e).__name__}: {e}",
                    )
                ]

    def initialize(self) -> None:
        """Connect to oVirt Engine."""
        logger.info("Connecting to oVirt Engine...")
        if not self.connection.connect():
            raise RuntimeError("Failed to connect to oVirt Engine")
        logger.info("Connected to oVirt Engine")

    async def start(self) -> None:
        """Start the MCP server using stdio transport."""
        async with stdio_server() as streams:
            await self.server.run(
                streams[0], streams[1], self.server.create_initialization_options()
            )

    @staticmethod
    def _format_result(data: Any) -> str:
        """Format tool result for MCP text response."""
        if data is None:
            return "Operation successful"
        if isinstance(data, str):
            return data
        if isinstance(data, list):
            if not data:
                return "No matching results found"
            items = []
            for x in data[:20]:
                if isinstance(x, dict):
                    items.append(
                        "  - " + ", ".join(f"{k}: {v}" for k, v in list(x.items())[:6])
                    )
                else:
                    items.append(f"  - {x}")
            return "Query results:\n" + "\n".join(items)
        if isinstance(data, dict):
            if data.get("error"):
                return f"{data['error']}"
            if data.get("success"):
                return f"{data.get('message', 'Operation successful')}"
            return "Results:\n" + "\n".join(
                f"  {k}: {v}" for k, v in list(data.items())[:15]
            )
        if not data:
            return "Operation successful"
        return str(data)


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="oVirt MCP Server - MCP protocol server for oVirt/RHV"
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )
    args = parser.parse_args()

    # Setup logging
    config = load_config(args.config)
    logging.basicConfig(
        level=getattr(logging, config.mcp_log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    server = OvirtMCPServer(config)
    server.initialize()

    # Graceful shutdown
    def _shutdown(signum: int, frame: Any) -> None:
        logger.info(f"Received signal {signum}, shutting down...")
        if server.connection:
            try:
                server.connection.disconnect()
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info("Starting oVirt MCP Server (stdio transport)...")
    asyncio.run(server.start())


if __name__ == "__main__":
    main()
