"""
Self-healing resolvers.

Auto-resolvers that can fix detected issues.
"""

from jarvis.self_heal.resolvers.base import BaseResolver
from jarvis.self_heal.resolvers.restart import RestartResolver
from jarvis.self_heal.resolvers.port_free import PortFreeResolver
from jarvis.self_heal.resolvers.dep_install import DependencyInstallResolver
from jarvis.self_heal.resolvers.cleanup import CleanupResolver

__all__ = [
    "BaseResolver",
    "RestartResolver",
    "PortFreeResolver",
    "DependencyInstallResolver",
    "CleanupResolver",
]
