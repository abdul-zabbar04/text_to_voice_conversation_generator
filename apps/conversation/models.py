import uuid
from django.db import models


class ConversationJob(models.Model):
    """
    Tracks a single conversation-to-speech generation request from
    submission through completion (or failure).
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    script = models.TextField(
        help_text="Raw conversation script as submitted by the user."
    )
    voice_map = models.JSONField(
        help_text="Mapping of speaker name -> Kokoro voice ID, e.g. {'Host': 'am_adam'}."
    )
    keep_chunks = models.BooleanField(
        default=False,
        help_text="If True, intermediate chunk_*.wav files are preserved on disk."
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    audio_file = models.FileField(
        upload_to="outputs/",
        null=True,
        blank=True,
        help_text="Final merged MP3 file, populated once status=completed."
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Populated when status=failed, with a human-readable reason."
    )
    duration_seconds = models.FloatField(
        null=True,
        blank=True,
        help_text="Wall-clock time the generation task took, for monitoring."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"ConversationJob({self.id}, status={self.status})"

    @property
    def is_terminal(self) -> bool:
        """True if the job has reached a final state (no longer processing)."""
        return self.status in {self.Status.COMPLETED, self.Status.FAILED}