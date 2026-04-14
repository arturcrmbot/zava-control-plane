from src.server.services.event_bus import EventBus
from src.server.services.state_store import StateStore
from src.server.services.audit_logger import AuditLogger
from src.server.services.sse_hub import SSEHub


class AppState:
    def __init__(self) -> None:
        self.bus = EventBus()
        self.store = StateStore()
        self.audit = AuditLogger()
        self.hub = SSEHub()
        self.orchestration_history: dict[str, list[dict]] = {}


app_state = AppState()
