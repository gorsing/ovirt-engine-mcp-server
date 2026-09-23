#!/usr/bin/env python3
"""Tests for EventsMCP class - events module tests."""
import pytest
from unittest.mock import MagicMock
from datetime import datetime


def _create_mock_event(event_id="event-123", description="Test event", severity="normal"):
    """Create a mock Event object"""
    mock_event = MagicMock()
    mock_event.id = event_id
    mock_event.code = 1000
    mock_event.description = description
    mock_event.severity = MagicMock()
    mock_event.severity.value = severity
    mock_event.time = datetime.now()
    mock_event.user = MagicMock()
    mock_event.user.name = "admin"
    mock_event.user.id = "user-123"
    mock_event.cluster = None
    mock_event.host = None
    mock_event.vm = None
    mock_event.data_center = None
    mock_event.origin = "system"
    mock_event.custom_id = ""
    return mock_event


class TestEventsMCPListEvents:
    """Tests for the list_events method"""

    def test_list_events_empty(self):
        """Test an empty event list"""
        from ovirt_engine_mcp_server.mcp_events import EventsMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_events_service = MagicMock()
        mock_events_service.list.return_value = []

        mock_ovirt.connection.system_service.return_value.events_service.return_value = mock_events_service

        events_mcp = EventsMCP(mock_ovirt)
        result = events_mcp.list_events()

        assert result == []

    def test_list_events_with_data(self):
        """Test event list with data"""
        from ovirt_engine_mcp_server.mcp_events import EventsMCP

        mock_events = [
            _create_mock_event("event-1", "VM started", "normal"),
            _create_mock_event("event-2", "Host down", "error"),
        ]

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_events_service = MagicMock()
        mock_events_service.list.return_value = mock_events

        mock_ovirt.connection.system_service.return_value.events_service.return_value = mock_events_service

        events_mcp = EventsMCP(mock_ovirt)
        result = events_mcp.list_events()

        assert len(result) == 2
        assert result[0]["description"] == "VM started"
        assert result[1]["severity"] == "error"

    def test_list_events_with_severity_filter(self):
        """Test filtering events by severity"""
        from ovirt_engine_mcp_server.mcp_events import EventsMCP

        mock_events = [
            _create_mock_event("event-1", "Alert 1", "alert"),
            _create_mock_event("event-2", "Normal 1", "normal"),
            _create_mock_event("event-3", "Alert 2", "alert"),
        ]

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_events_service = MagicMock()
        mock_events_service.list.return_value = mock_events

        mock_ovirt.connection.system_service.return_value.events_service.return_value = mock_events_service

        events_mcp = EventsMCP(mock_ovirt)
        result = events_mcp.list_events(severity="alert")

        assert len(result) == 2
        for event in result:
            assert event["severity"] == "alert"

    def test_list_events_with_pagination(self):
        """Test paginated event fetching"""
        from ovirt_engine_mcp_server.mcp_events import EventsMCP

        mock_events = [_create_mock_event(f"event-{i}", f"Event {i}", "normal") for i in range(10)]

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_events_service = MagicMock()
        mock_events_service.list.return_value = mock_events

        mock_ovirt.connection.system_service.return_value.events_service.return_value = mock_events_service

        events_mcp = EventsMCP(mock_ovirt)
        result = events_mcp.list_events(page=2, page_size=3)

        # Should return items 4-6 (indices 3-5)
        assert len(result) == 3

    def test_list_events_not_connected(self):
        """Test that an exception is raised when not connected"""
        from ovirt_engine_mcp_server.mcp_events import EventsMCP
        from ovirt_engine_mcp_server.errors import OvirtConnectionError

        mock_ovirt = MagicMock()
        mock_ovirt.connected = False

        events_mcp = EventsMCP(mock_ovirt)

        with pytest.raises(OvirtConnectionError):
            events_mcp.list_events()


class TestEventsMCPGetAlerts:
    """Tests for the get_alerts method"""

    def test_get_alerts(self):
        """Test fetching alert events"""
        from ovirt_engine_mcp_server.mcp_events import EventsMCP

        mock_events = [
            _create_mock_event("event-1", "Alert 1", "alert"),
            _create_mock_event("event-2", "Normal 1", "normal"),
        ]

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_events_service = MagicMock()
        mock_events_service.list.return_value = mock_events

        mock_ovirt.connection.system_service.return_value.events_service.return_value = mock_events_service

        events_mcp = EventsMCP(mock_ovirt)
        result = events_mcp.get_alerts()

        assert len(result) == 1
        assert result[0]["severity"] == "alert"


class TestEventsMCPGetErrors:
    """Tests for the get_errors method"""

    def test_get_errors(self):
        """Test fetching error events"""
        from ovirt_engine_mcp_server.mcp_events import EventsMCP

        mock_events = [
            _create_mock_event("event-1", "Error 1", "error"),
            _create_mock_event("event-2", "Normal 1", "normal"),
            _create_mock_event("event-3", "Error 2", "error"),
        ]

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_events_service = MagicMock()
        mock_events_service.list.return_value = mock_events

        mock_ovirt.connection.system_service.return_value.events_service.return_value = mock_events_service

        events_mcp = EventsMCP(mock_ovirt)
        result = events_mcp.get_errors()

        assert len(result) == 2


class TestEventsMCPGetWarnings:
    """Tests for the get_warnings method"""

    def test_get_warnings(self):
        """Test fetching warning events"""
        from ovirt_engine_mcp_server.mcp_events import EventsMCP

        mock_events = [
            _create_mock_event("event-1", "Warning 1", "warning"),
            _create_mock_event("event-2", "Normal 1", "normal"),
        ]

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_events_service = MagicMock()
        mock_events_service.list.return_value = mock_events

        mock_ovirt.connection.system_service.return_value.events_service.return_value = mock_events_service

        events_mcp = EventsMCP(mock_ovirt)
        result = events_mcp.get_warnings()

        assert len(result) == 1
        assert result[0]["severity"] == "warning"


class TestEventsMCPGetEvent:
    """Tests for the get_event method"""

    def test_get_event_success(self):
        """Test fetching single event details"""
        from ovirt_engine_mcp_server.mcp_events import EventsMCP

        mock_event = _create_mock_event()
        mock_event.cluster = MagicMock()
        mock_event.cluster.name = "Default"
        mock_event.cluster.id = "cluster-123"
        mock_event.host = MagicMock()
        mock_event.host.name = "host1"
        mock_event.host.id = "host-123"
        mock_event.vm = MagicMock()
        mock_event.vm.name = "vm1"
        mock_event.vm.id = "vm-123"

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_event_service = MagicMock()
        mock_event_service.get.return_value = mock_event

        mock_events_service = MagicMock()
        mock_events_service.event_service.return_value = mock_event_service

        mock_ovirt.connection.system_service.return_value.events_service.return_value = mock_events_service

        events_mcp = EventsMCP(mock_ovirt)
        result = events_mcp.get_event("event-123")

        assert result is not None
        assert result["id"] == "event-123"
        assert result["cluster"] == "Default"
        assert result["host"] == "host1"
        assert result["vm"] == "vm1"

    def test_get_event_not_found(self):
        """Test event does not exist"""
        from ovirt_engine_mcp_server.mcp_events import EventsMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_event_service = MagicMock()
        mock_event_service.get.side_effect = Exception("Not found")

        mock_events_service = MagicMock()
        mock_events_service.event_service.return_value = mock_event_service

        mock_ovirt.connection.system_service.return_value.events_service.return_value = mock_events_service

        events_mcp = EventsMCP(mock_ovirt)
        result = events_mcp.get_event("nonexistent")

        assert result is None


class TestEventsMCPSearchEvents:
    """Tests for the search_events method"""

    def test_search_events(self):
        """Test searching events"""
        from ovirt_engine_mcp_server.mcp_events import EventsMCP

        mock_events = [
            _create_mock_event("event-1", "VM started", "normal"),
        ]

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_events_service = MagicMock()
        mock_events_service.list.return_value = mock_events

        mock_ovirt.connection.system_service.return_value.events_service.return_value = mock_events_service

        events_mcp = EventsMCP(mock_ovirt)
        result = events_mcp.search_events("vm.name = test-vm")

        assert len(result) == 1


class TestEventsMCPGetEventsSummary:
    """Tests for the get_events_summary method"""

    def test_get_events_summary(self):
        """Test fetching the event statistics summary"""
        from ovirt_engine_mcp_server.mcp_events import EventsMCP

        mock_events = [
            _create_mock_event("event-1", "Alert 1", "alert"),
            _create_mock_event("event-2", "Error 1", "error"),
            _create_mock_event("event-3", "Warning 1", "warning"),
            _create_mock_event("event-4", "Normal 1", "normal"),
            _create_mock_event("event-5", "Normal 2", "normal"),
        ]

        # Add cluster information
        mock_events[0].cluster = MagicMock()
        mock_events[0].cluster.name = "Cluster1"
        mock_events[4].cluster = MagicMock()
        mock_events[4].cluster.name = "Cluster1"

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_events_service = MagicMock()
        mock_events_service.list.return_value = mock_events

        mock_ovirt.connection.system_service.return_value.events_service.return_value = mock_events_service

        events_mcp = EventsMCP(mock_ovirt)
        result = events_mcp.get_events_summary()

        assert result["total"] == 5
        assert result["alert"] == 1
        assert result["error"] == 1
        assert result["warning"] == 1
        assert result["normal"] == 2
        assert "Cluster1" in result["by_cluster"]


class TestEventsMCPAcknowledgeEvent:
    """Tests for the acknowledge_event method"""

    def test_acknowledge_event_success(self):
        """Test successful event acknowledgment"""
        from ovirt_engine_mcp_server.mcp_events import EventsMCP

        mock_event = _create_mock_event()
        mock_event.acknowledged = False

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_event_service = MagicMock()
        mock_event_service.get.return_value = mock_event

        mock_events_service = MagicMock()
        mock_events_service.event_service.return_value = mock_event_service

        mock_ovirt.connection.system_service.return_value.events_service.return_value = mock_events_service

        events_mcp = EventsMCP(mock_ovirt)
        result = events_mcp.acknowledge_event("event-123")

        assert result["success"] is True


class TestEventsMCPClearAlerts:
    """Tests for the clear_alerts method"""

    def test_clear_alerts(self):
        """Test clearing alert events"""
        from ovirt_engine_mcp_server.mcp_events import EventsMCP

        mock_alerts = [
            _create_mock_event("event-1", "Alert 1", "alert"),
            _create_mock_event("event-2", "Alert 2", "alert"),
        ]

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        mock_events_service = MagicMock()
        mock_events_service.list.return_value = mock_alerts
        mock_events_service.event_service.return_value.remove.return_value = None

        mock_ovirt.connection.system_service.return_value.events_service.return_value = mock_events_service

        events_mcp = EventsMCP(mock_ovirt)
        result = events_mcp.clear_alerts()

        assert result["success"] is True
        assert result["cleared_count"] == 2


class TestEventsMCPTools:
    """Tests for the MCP_TOOLS registry"""

    def test_mcp_tools_defined(self):
        """Test that the MCP tool registry is defined"""
        from ovirt_engine_mcp_server.mcp_events import MCP_TOOLS

        expected_tools = [
            "event_list",
            "event_get",
            "event_search",
            "event_alerts",
            "event_errors",
            "event_warnings",
            "event_summary",
            "event_acknowledge",
            "event_clear_alerts",
        ]

        for tool in expected_tools:
            assert tool in MCP_TOOLS, f"Missing tool: {tool}"
            assert "method" in MCP_TOOLS[tool]
            assert "description" in MCP_TOOLS[tool]


class TestEventsMCPUnsupportedCollections:
    """oVirt 4.5 REST exposes no event-subscription collection.

    ``/api/eventsubscriptions`` and ``/api/events/{id}/subscriptions`` are 404,
    so the tool must report "unsupported" instead of silently returning ``[]``.
    """

    @pytest.mark.parametrize("user", [None, "admin@internal"])
    def test_list_event_subscriptions_reports_unsupported_api(self, user):
        from ovirt_engine_mcp_server.mcp_events import EventsMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True

        with pytest.raises(ValueError, match="Event subscriptions unavailable"):
            EventsMCP(mock_ovirt).list_event_subscriptions(user)
