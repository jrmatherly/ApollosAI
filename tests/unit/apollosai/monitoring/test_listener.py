"""Tests for ApollosAIMonitoringListener structured logging."""

import logging
from unittest.mock import MagicMock

from apollosai.monitoring.listener import ApollosAIMonitoringListener


def test_listener_on_create_conversation(caplog):
    """L7: Verify on_create_conversation logs with expected structured data."""
    listener = ApollosAIMonitoringListener()
    with caplog.at_level(logging.INFO):
        listener.on_create_conversation()
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.message == 'create_conversation'
    assert record.signal == 'create_conversation'


def test_listener_on_session_start(caplog):
    """L7: Verify on_agent_session_start logs with structured session data."""
    listener = ApollosAIMonitoringListener()
    with caplog.at_level(logging.INFO):
        listener.on_agent_session_start(success=True, duration=1.5)
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.message == 'agent_session_start'
    assert record.signal == 'agent_session_start'
    assert record.success is True
    assert record.duration == 1.5


def test_listener_on_session_start_failure(caplog):
    """L7: Verify on_agent_session_start correctly logs failures."""
    listener = ApollosAIMonitoringListener()
    with caplog.at_level(logging.INFO):
        listener.on_agent_session_start(success=False, duration=0.1)
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.success is False
    assert record.duration == 0.1


def test_listener_get_instance():
    instance = ApollosAIMonitoringListener.get_instance(config=MagicMock())
    assert isinstance(instance, ApollosAIMonitoringListener)
