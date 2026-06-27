from pathlib import Path
from pydub import AudioSegment

from apps.tts.audio_pause import build_pause_schedule, DEFAULT_PAUSE_MIN_MS, DEFAULT_PAUSE_MAX_MS


class AudioMergeError(Exception):
    """Raised when chunk loading or merging fails."""
    pass


def merge_audio_chunks(
    chunk_paths: list[str | Path],
    speakers: list[str],
    output_path: str | Path,
    pause_min_ms: int = DEFAULT_PAUSE_MIN_MS,
    pause_max_ms: int = DEFAULT_PAUSE_MAX_MS,
    bitrate: str = "192k",
) -> Path:
    """
    Merges a sequence of WAV audio chunks into a single MP3 file,
    inserting natural pauses between chunks when the speaker changes.

    Args:
        chunk_paths: ordered list of paths to chunk_*.wav files, one
                     per dialogue line, in script order.
        speakers: ordered list of speaker names, same length and order
                  as chunk_paths (chunk_paths[i] was spoken by speakers[i]).
        output_path: where to write the final merged MP3.
        pause_min_ms / pause_max_ms: pause range between speaker changes.
        bitrate: MP3 export bitrate.

    Returns:
        Path to the written output file.

    Raises:
        AudioMergeError: if inputs are mismatched, empty, or any chunk
                          file fails to load.
    """
    if len(chunk_paths) != len(speakers):
        raise AudioMergeError(
            f"chunk_paths length ({len(chunk_paths)}) must match "
            f"speakers length ({len(speakers)})"
        )

    if not chunk_paths:
        raise AudioMergeError("No audio chunks provided to merge.")

    pause_schedule = build_pause_schedule(speakers, pause_min_ms, pause_max_ms)

    merged = AudioSegment.empty()

    for idx, (chunk_path, pause_ms) in enumerate(zip(chunk_paths, pause_schedule)):
        chunk_path = Path(chunk_path)

        if not chunk_path.exists():
            raise AudioMergeError(f"Chunk file not found: {chunk_path}")

        try:
            segment = AudioSegment.from_wav(chunk_path)
        except Exception as e:
            raise AudioMergeError(f"Failed to load chunk '{chunk_path}': {e}") from e

        if pause_ms > 0:
            merged += AudioSegment.silent(duration=pause_ms)

        merged += segment

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        merged.export(str(output_path), format="mp3", bitrate=bitrate)
    except Exception as e:
        raise AudioMergeError(f"Failed to export merged MP3 to '{output_path}': {e}") from e

    return output_path


def get_audio_duration_seconds(file_path: str | Path) -> float:
    """
    Returns the duration of an audio file in seconds.
    Useful for logging/monitoring (e.g. storing on ConversationJob).
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise AudioMergeError(f"Audio file not found: {file_path}")

    try:
        audio = AudioSegment.from_file(file_path)
    except Exception as e:
        raise AudioMergeError(f"Failed to read audio file '{file_path}': {e}") from e

    return len(audio) / 1000.0  # pydub works in milliseconds