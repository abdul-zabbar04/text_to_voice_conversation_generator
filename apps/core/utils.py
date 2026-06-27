import os
import shutil
import uuid
from pathlib import Path


def generate_unique_filename(prefix: str = "conversation", extension: str = "mp3") -> str:
    """
    Generates a unique filename like: conversation_7f82aa.mp3
    Uses 6 hex characters from a UUID4 for brevity + uniqueness.
    """
    unique_part = uuid.uuid4().hex[:6]
    return f"{prefix}_{unique_part}.{extension}"


def generate_job_id() -> str:
    """
    Generates a full UUID4 string, used as job/session identifier
    for grouping chunks belonging to one conversation generation request.
    """
    return str(uuid.uuid4())


def ensure_dir(path: Path | str) -> Path:
    """
    Ensures a directory exists, creates it (including parents) if missing.
    Returns the Path object for convenience/chaining.
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_job_temp_dir(temp_root: Path | str, job_id: str) -> Path:
    """
    Returns (and creates) a per-job temp directory, e.g.:
    media/temp/<job_id>/
    This isolates chunk files between concurrent generation requests.
    """
    job_dir = Path(temp_root) / job_id
    return ensure_dir(job_dir)


def cleanup_dir(path: Path | str, ignore_errors: bool = True) -> None:
    """
    Recursively deletes a directory and its contents.
    Used to remove chunk files after merging, unless keep_chunks=True.
    """
    path = Path(path)
    if path.exists():
        shutil.rmtree(path, ignore_errors=ignore_errors)


def chunk_filename(index: int) -> str:
    """
    Generates a zero-padded chunk filename, e.g.:
    chunk_000.wav, chunk_001.wav, ...
    """
    return f"chunk_{index:03d}.wav"


def safe_join(base_dir: Path | str, filename: str) -> Path:
    """
    Joins a filename to a base directory, but blocks path traversal
    (e.g. someone passing '../../etc/passwd' as a filename).
    """
    base_dir = Path(base_dir).resolve()
    target = (base_dir / filename).resolve()
    if not str(target).startswith(str(base_dir)):
        raise ValueError(f"Unsafe path detected: {filename}")
    return target