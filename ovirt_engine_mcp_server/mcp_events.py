#!/usr/bin/env python3
"""
oVirt MCP Server - events module
Provides event queries and alert management
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


class EventsMCP(BaseMCP):
    """Events MCP"""

    def __init__(self, ovirt_mcp):
        super().__init__(ovirt_mcp)

    @require_connection
    def list_events(self, search: str = None, severity: str = None,
                   page: int = 1, page_size: int = 50) -> List[Dict]:
        """List events

        Args:
            search: Search expression (optional)
            severity: Severity filter (error/warning/info/normal/alert)
            page: Page number, starting at 1
            page_size: Items per page, default 50

        Returns:
            List of events
        """
        events_service = self.connection.system_service().events_service()

        # Build the search query
        search_query = ""
        if search:
            search_query = _sanitize_search_value(search)

        # Fetch events
        try:
            # SDK uses the max parameter to limit the number of results
            max_results = page * page_size
            events = events_service.list(
                search=search_query if search_query else None,
                max=max_results
            )

            # Filter by severity
            if severity:
                severity_lower = severity.lower()
                events = [e for e in events if e.severity and e.severity.value.lower() == severity_lower]

            # Apply pagination
            start_idx = (page - 1) * page_size
            events = events[start_idx:start_idx + page_size]

        except Exception as e:
            logger.error(f"Failed to fetch events: {e}")
            events = []

        result = []
        for event in events:
            result.append({
                "id": event.id,
                "code": event.code if hasattr(event, 'code') else 0,
                "description": event.description or "",
                "severity": str(event.severity.value) if event.severity else "normal",
                "time": str(event.time) if event.time else "",
                "user": self._user_name(event.user),
                "cluster": self._cluster_name(event.cluster),
                "host": self._host_name(event.host),
                "vm": self._vm_name(event.vm),
                "data_center": self._data_center_name(event.data_center),
                "origin": event.origin if hasattr(event, 'origin') else "",
                "custom_id": event.custom_id if hasattr(event, 'custom_id') else "",
            })

        return result

    def get_alerts(self, page: int = 1, page_size: int = 50) -> List[Dict]:
        """Get alert events (all events with severity=alert)"""
        return self.list_events(severity="alert", page=page, page_size=page_size)

    def get_errors(self, page: int = 1, page_size: int = 50) -> List[Dict]:
        """Get error events"""
        return self.list_events(severity="error", page=page, page_size=page_size)

    def get_warnings(self, page: int = 1, page_size: int = 50) -> List[Dict]:
        """Get warning events"""
        return self.list_events(severity="warning", page=page, page_size=page_size)

    @require_connection
    def get_event(self, event_id: str) -> Optional[Dict]:
        """Get details of a single event"""
        try:
            event_service = self.connection.system_service().events_service().event_service(event_id)
            event = event_service.get()

            return {
                "id": event.id,
                "code": event.code if hasattr(event, 'code') else 0,
                "description": event.description or "",
                "severity": str(event.severity.value) if event.severity else "normal",
                "time": str(event.time) if event.time else "",
                "user": self._user_name(event.user),
                "user_id": event.user.id if event.user else "",
                "cluster": self._cluster_name(event.cluster),
                "cluster_id": event.cluster.id if event.cluster else "",
                "host": self._host_name(event.host),
                "host_id": event.host.id if event.host else "",
                "vm": self._vm_name(event.vm),
                "vm_id": event.vm.id if event.vm else "",
                "data_center": self._data_center_name(event.data_center),
                "data_center_id": event.data_center.id if event.data_center else "",
                "template": self._template_name(event.template),
                "storage_domain": self._storage_domain_name(event.storage_domain),
                "origin": event.origin if hasattr(event, 'origin') else "",
                "custom_id": event.custom_id if hasattr(event, 'custom_id') else "",
                "flood_rate": event.flood_rate if hasattr(event, 'flood_rate') else 0,
                "correlation_id": event.correlation_id if hasattr(event, 'correlation_id') else "",
            }
        except Exception as e:
            logger.debug(f"Failed to fetch events: {e}")
            return None

    def search_events(self, query: str, page: int = 1, page_size: int = 50) -> List[Dict]:
        """Search events

        Supported search fields:
        - vm.name: VM name
        - host.name: Host name
        - cluster.name: Cluster name
        - severity: Severity
        - time: Time range

        Examples:
        - "vm.name = myvm"
        - "severity = alert"
        - "time > yesterday"
        """
        return self.list_events(search=query, page=page, page_size=page_size)

    @require_connection
    def get_events_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get event statistics summary

        Args:
            hours: Count events from the last N hours, default 24

        Returns:
            Event counts per severity level
        """
        events_service = self.connection.system_service().events_service()

        # Fetch recent events (using SDK-supported parameters)
        try:
            # Filter with the from_date parameter (if the SDK supports it)
            events = events_service.list(max=500)
        except Exception as e:
            logger.error(f"Failed to fetch events: {e}")
            return {"error": str(e)}

        # Count events per severity level
        summary = {
            "total": len(events),
            "alert": 0,
            "error": 0,
            "warning": 0,
            "normal": 0,
            "info": 0,
            "by_cluster": {},
            "by_host": {},
            "by_vm": {},
        }

        for event in events:
            severity = str(event.severity.value) if event.severity else "normal"
            if severity in summary:
                summary[severity] += 1

            # Count by cluster
            if event.cluster:
                cluster_name = event.cluster.name
                summary["by_cluster"][cluster_name] = summary["by_cluster"].get(cluster_name, 0) + 1

            # Count by host
            if event.host:
                host_name = event.host.name
                summary["by_host"][host_name] = summary["by_host"].get(host_name, 0) + 1

            # Count by VM
            if event.vm:
                vm_name = event.vm.name
                summary["by_vm"][vm_name] = summary["by_vm"].get(vm_name, 0) + 1

        return summary

    @require_connection
    def acknowledge_event(self, event_id: str) -> Dict[str, Any]:
        """Acknowledge an event"""
        try:
            event_service = self.connection.system_service().events_service().event_service(event_id)
            # Mark as read/acknowledged
            event = event_service.get()
            if hasattr(event, 'acknowledged'):
                event.acknowledged = True
                event_service.update(event)

            return {"success": True, "message": f"Event {event_id} acknowledged"}
        except Exception as e:
            raise RuntimeError(f"Failed to acknowledge event: {e}")

    @require_connection
    def clear_alerts(self) -> Dict[str, Any]:
        """Clear all alert events"""
        try:
            events_service = self.connection.system_service().events_service()
            alerts = events_service.list(search="severity=alert")

            cleared_count = 0
            for alert in alerts:
                try:
                    event_service = events_service.event_service(alert.id)
                    event_service.remove()
                    cleared_count += 1
                except Exception as e:
                    logger.debug(f"Failed to clear event {alert.id}: {e}")

            return {
                "success": True,
                "message": f"Cleared {cleared_count} alert events",
                "cleared_count": cleared_count,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to clear alerts: {e}")

    # -- Event subscription management --------------------------------------------------------

    @require_connection
    def list_event_subscriptions(self, user: str = None) -> List[Dict]:
        """List event subscriptions

        Args:
            user: User name (optional)

        Returns:
            List of event subscriptions
        """
        # oVirt 4.5 REST has no event-subscription collection: SystemService
        # exposes no `event_subscriptions_service`, and both
        # `/api/eventsubscriptions` and `/api/events/{id}/subscriptions`
        # return 404. Raise instead of silently reporting an empty list.
        _ = user  # accepted for schema compatibility
        raise ValueError(
            "Event subscriptions unavailable: the current oVirt API provides no event subscriptions collection"
        )

    # -- Bookmark management ------------------------------------------------------------

    @require_connection
    def list_bookmarks(self) -> List[Dict]:
        """List bookmarks

        Returns:
            List of bookmarks
        """
        try:
            bookmarks_service = self.connection.system_service().bookmarks_service()
            bookmarks = bookmarks_service.list()
        except Exception as e:
            logger.error(f"Failed to fetch bookmarks: {e}")
            return []

        return [
            {
                "id": b.id,
                "name": b.name,
                "value": b.value if hasattr(b, 'value') else "",
            }
            for b in bookmarks
        ]


# MCP tool registry
MCP_TOOLS = {
    "event_list": {"method": "list_events", "description": "List events"},
    "event_get": {"method": "get_event", "description": "Get event details"},
    "event_search": {"method": "search_events", "description": "Search events"},
    "event_alerts": {"method": "get_alerts", "description": "Get alert events"},
    "event_errors": {"method": "get_errors", "description": "Get error events"},
    "event_warnings": {"method": "get_warnings", "description": "Get warning events"},
    "event_summary": {"method": "get_events_summary", "description": "Get event statistics summary"},
    "event_acknowledge": {"method": "acknowledge_event", "description": "Acknowledge event"},
    "event_clear_alerts": {"method": "clear_alerts", "description": "Clear alert events"},

    # Newly added tools
    "event_subscription_list": {"method": "list_event_subscriptions", "description": "List event subscriptions"},
    "bookmark_list": {"method": "list_bookmarks", "description": "List bookmarks"},
}
