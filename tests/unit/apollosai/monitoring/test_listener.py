from unittest.mock import MagicMock

from apollosai.monitoring.listener import ApollosAIMonitoringListener


def test_listener_on_create_conversation():
    listener = ApollosAIMonitoringListener()
    listener.on_create_conversation()  # should not raise


def test_listener_on_session_start():
    listener = ApollosAIMonitoringListener()
    listener.on_agent_session_start(success=True, duration=1.5)  # should not raise


def test_listener_get_instance():
    instance = ApollosAIMonitoringListener.get_instance(config=MagicMock())
    assert isinstance(instance, ApollosAIMonitoringListener)
