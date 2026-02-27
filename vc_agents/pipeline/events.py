"""Pipeline event system for live progress tracking."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class EventType(str, Enum):
    PIPELINE_START = "pipeline_start"
    PIPELINE_COMPLETE = "pipeline_complete"
    PIPELINE_ERROR = "pipeline_error"

    STAGE_START = "stage_start"
    STAGE_COMPLETE = "stage_complete"

    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"

    PROVIDER_CALL = "provider_call"
    PROVIDER_RESULT = "provider_result"
    PROVIDER_ERROR = "provider_error"

    LOG = "log"


@dataclass
class PipelineEvent:
    type: EventType
    stage: str = ""
    step: str = ""
    provider: str = ""
    idea_id: str = ""
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "stage": self.stage,
            "step": self.step,
            "provider": self.provider,
            "idea_id": self.idea_id,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp,
        }


# Type alias for event callbacks
EventCallback = Callable[[PipelineEvent], None]


def noop_callback(event: PipelineEvent) -> None:
    """Default no-op callback."""
    pass
