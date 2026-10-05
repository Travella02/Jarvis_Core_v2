"""Typed runtime event names for Jarvis Core v2.

Runtime events intentionally share the existing Conversation Core EventBus. 0.0.6
adds names, cursors, and projections; it does not create a second event authority.
"""

from __future__ import annotations

from enum import Enum


class RuntimeEventType(str, Enum):
    LIFECYCLE_CHANGED = "runtime.lifecycle.changed"
    CONVERSATION_ATTACHED = "runtime.conversation.attached"
    CONVERSATION_DETACHED = "runtime.conversation.detached"
    PROVIDER_HEALTH = "runtime.provider.health"
    SETTINGS_LOADED = "runtime.settings.loaded"
    CLIENT_SNAPSHOT = "runtime.client.snapshot"


__all__ = ["RuntimeEventType"]
