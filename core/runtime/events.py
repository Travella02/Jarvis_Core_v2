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
    CLIENT_COMMAND_ACCEPTED = "runtime.client.command.accepted"
    CLIENT_COMMAND_STARTED = "runtime.client.command.started"
    CLIENT_COMMAND_COMPLETED = "runtime.client.command.completed"
    CLIENT_COMMAND_CANCEL_REQUESTED = "runtime.client.command.cancel.requested"
    CLIENT_COMMAND_CANCELLED = "runtime.client.command.cancelled"
    CLIENT_COMMAND_FAILED = "runtime.client.command.failed"


__all__ = ["RuntimeEventType"]
