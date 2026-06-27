import shutil
import time
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile

from apps.core.utils import (
    generate_unique_filename,
    get_job_temp_dir,
    chunk_filename,
    cleanup_dir,
)
from apps.conversation.parser import (
    parse_script,
    validate_voice_map,
    ScriptParseError,
)
from apps.conversation.models import ConversationJob
from apps.tts.kokoro_engine import synthesize_to_file, KokoroEngineError
from apps.tts.audio_merger import merge_audio_chunks, get_audio_duration_seconds, AudioMergeError


class ConversationGenerationError(Exception):
    """
    Raised when the end-to-end generation pipeline fails for reasons
    that should be recorded on the job as a failure (parse errors,
    synthesis errors, merge errors). Wraps the underlying cause.
    """
    pass


def create_conversation_job(script: str, voice_map: dict[str, str], keep_chunks: bool = False) -> ConversationJob:
    """
    Validates the script + voice_map and persists a new ConversationJob
    in PENDING state. Does NOT perform synthesis - that happens in
    run_conversation_generation(), normally invoked from a Celery task.

    Raises:
        ScriptParseError: if the script is malformed or voice_map is
                           missing entries for speakers in the script.
    """
    lines = parse_script(script, max_lines=settings.MAX_SCRIPT_LINES)
    validate_voice_map(lines, voice_map)

    job = ConversationJob.objects.create(
        script=script,
        voice_map=voice_map,
        keep_chunks=keep_chunks,
    )
    return job


def run_conversation_generation(job_id: str) -> ConversationJob:
    """
    Executes the full generation pipeline for a given job:
        1. Re-parse the stored script (source of truth lives in the DB row).
        2. Synthesize each dialogue line into its own WAV chunk.
        3. Merge all chunks into a single MP3, with natural pauses.
        4. Save the final MP3 onto the job's audio_file field.
        5. Update job status to COMPLETED or FAILED accordingly.
        6. Clean up the temp chunk directory unless keep_chunks=True.

    This function is synchronous/blocking by design - it's meant to be
    called from within a Celery task, not directly from a request/response
    cycle.

    Returns the updated ConversationJob (for convenience in tests/tasks).
    """
    job = ConversationJob.objects.get(id=job_id)
    job.status = ConversationJob.Status.PROCESSING
    job.save(update_fields=["status"])

    start_time = time.monotonic()
    job_temp_dir = get_job_temp_dir(settings.TEMP_DIR, str(job.id))

    try:
        lines = parse_script(job.script, max_lines=settings.MAX_SCRIPT_LINES)
        validate_voice_map(lines, job.voice_map)

        chunk_paths: list[Path] = []
        speakers: list[str] = []

        for idx, line in enumerate(lines):
            voice_id = job.voice_map[line.speaker]
            chunk_path = job_temp_dir / chunk_filename(idx)

            synthesize_to_file(
                text=line.text,
                voice=voice_id,
                output_path=chunk_path,
            )

            chunk_paths.append(chunk_path)
            speakers.append(line.speaker)

        final_filename = generate_unique_filename(prefix="conversation", extension="mp3")
        merged_temp_path = job_temp_dir / final_filename

        merge_audio_chunks(
            chunk_paths=chunk_paths,
            speakers=speakers,
            output_path=merged_temp_path,
            pause_min_ms=settings.PAUSE_MIN_MS,
            pause_max_ms=settings.PAUSE_MAX_MS,
        )

        duration = get_audio_duration_seconds(merged_temp_path)

        with open(merged_temp_path, "rb") as f:
            job.audio_file.save(final_filename, ContentFile(f.read()))

        job.status = ConversationJob.Status.COMPLETED
        job.duration_seconds = round(duration, 2)
        job.error_message = None
        job.save(update_fields=["status", "duration_seconds", "error_message", "audio_file"])

    except (ScriptParseError, KokoroEngineError, AudioMergeError) as e:
        job.status = ConversationJob.Status.FAILED
        job.error_message = str(e)
        job.save(update_fields=["status", "error_message"])
        raise ConversationGenerationError(str(e)) from e

    except Exception as e:
        # Catch-all for unexpected errors (disk full, permission errors,
        # etc.) - still recorded on the job so the API consumer sees a
        # FAILED status rather than the job hanging in PROCESSING forever.
        job.status = ConversationJob.Status.FAILED
        job.error_message = f"Unexpected error: {e}"
        job.save(update_fields=["status", "error_message"])
        raise ConversationGenerationError(str(e)) from e

    finally:
        if not job.keep_chunks:
            cleanup_dir(job_temp_dir)
        # If keep_chunks=True, job_temp_dir (containing chunk_*.wav files
        # and the pre-save copy of the final mp3) is left on disk for
        # inspection, at media/temp/<job_id>/

    return job