"""Jarvis Core v2 runtime/state/event foundation."""

from .client_stream import RuntimeEventStream, RuntimeSync
from .commands import (
    ClientCancelReceipt,
    ClientCommandError,
    ClientCommandReceipt,
    ClientCommandRecord,
    ClientCommandStatus,
    RuntimeCommandGateway,
    command_record_to_dict,
)
from .events import RuntimeEventType
from .health import (
    ComponentHealth,
    ComponentHealthState,
    HealthRegistry,
    HealthSnapshot,
    RuntimeHealthState,
)
from .models import (
    ConversationProjection,
    EventBatch,
    RuntimeLifecycleState,
    RuntimeSnapshot,
)
from .providers import IntelligenceProviderRouter, ProviderRoute, ProviderRouteError
from .runtime import JarvisRuntime, RuntimeLifecycleError
from .protocol import PROTOCOL_NAME, PROTOCOL_VERSION
from .settings import RuntimeSettings, RuntimeSettingsError

__all__ = [
    "ComponentHealth",
    "ClientCancelReceipt",
    "ClientCommandError",
    "ClientCommandReceipt",
    "ClientCommandRecord",
    "ClientCommandStatus",
    "PROTOCOL_NAME",
    "PROTOCOL_VERSION",
    "ComponentHealthState",
    "ConversationProjection",
    "EventBatch",
    "HealthRegistry",
    "HealthSnapshot",
    "IntelligenceProviderRouter",
    "JarvisRuntime",
    "ProviderRoute",
    "ProviderRouteError",
    "RuntimeCommandGateway",
    "RuntimeEventStream",
    "RuntimeEventType",
    "RuntimeHealthState",
    "RuntimeLifecycleError",
    "RuntimeLifecycleState",
    "RuntimeSettings",
    "RuntimeSettingsError",
    "RuntimeSnapshot",
    "RuntimeSync",
    "command_record_to_dict",
]
