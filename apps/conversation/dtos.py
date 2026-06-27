from dataclasses import dataclass, field
from enum import Enum


class JobStatus(str, Enum):
    """
    Mirrors the possible states of a conversation generation job.
    Stored as plain strings in the DB (see models.py in the next step),
    but used here as an enum for type safety in business logic.
    """
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ConversationGenerateRequest:
    """
    Represents a validated, parsed request to generate a conversation.
    This is what views.py builds after validating raw input, and what
    gets passed down into services.py.
    """
    script: str
    voice_map: dict[str, str]
    keep_chunks: bool = False


@dataclass
class ConversationGenerateResult:
    """
    Represents the outcome of submitting a generation job.
    Returned by services.py back up to views.py for the API response.
    """
    job_id: str
    status: JobStatus


@dataclass
class JobStatusResult:
    """
    Represents the current state of a job, used for the status-check
    endpoint. audio_file_url and error_message are mutually exclusive
    in practice (only one will be populated depending on status).
    """
    job_id: str
    status: JobStatus
    audio_file_url: str | None = None
    error_message: str | None = None
    duration_seconds: float | None = None


@dataclass
class SpeakerSegment:
    """
    Represents one synthesized audio chunk tied to a speaker.
    Used internally during the merge step (tts app) to know which
    chunk belongs to which speaker, for pause-insertion logic.
    """
    speaker: str
    chunk_path: str
    line_number: int


@dataclass
class ConversationGenerationPlan:
    """
    The fully resolved plan for generating a conversation - parsed lines
    paired with their resolved voice IDs, ready to hand to the TTS engine.
    Built by services.py, consumed by tasks.py / tts app.
    """
    job_id: str
    segments: list[SpeakerSegment] = field(default_factory=list)
    keep_chunks: bool = False