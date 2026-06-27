import random


# Natural pause range (in milliseconds) inserted when the speaker changes.
# These are fallback defaults; actual values are normally pulled from
# Django settings (PAUSE_MIN_MS / PAUSE_MAX_MS) so they're configurable
# without touching code.
DEFAULT_PAUSE_MIN_MS = 300
DEFAULT_PAUSE_MAX_MS = 500


def get_pause_duration_ms(
    previous_speaker: str | None,
    current_speaker: str,
    pause_min_ms: int = DEFAULT_PAUSE_MIN_MS,
    pause_max_ms: int = DEFAULT_PAUSE_MAX_MS,
) -> int:
    """
    Determines how much silence (in ms) to insert before the current
    speaker's audio chunk, based on whether the speaker changed.

    Rules:
        - No pause before the very first chunk (previous_speaker is None).
        - No pause if the same speaker continues talking (rare in this
          format, since each script line is a separate speaker turn, but
          handled for correctness/robustness).
        - A random pause within [pause_min_ms, pause_max_ms] when the
          speaker changes, to sound more natural than a fixed duration.

    Raises:
        ValueError: if pause_min_ms > pause_max_ms (misconfiguration).
    """
    if pause_min_ms > pause_max_ms:
        raise ValueError(
            f"pause_min_ms ({pause_min_ms}) cannot be greater than "
            f"pause_max_ms ({pause_max_ms})"
        )

    if previous_speaker is None:
        return 0

    if previous_speaker == current_speaker:
        return 0

    return random.randint(pause_min_ms, pause_max_ms)


def build_pause_schedule(
    speaker_sequence: list[str],
    pause_min_ms: int = DEFAULT_PAUSE_MIN_MS,
    pause_max_ms: int = DEFAULT_PAUSE_MAX_MS,
) -> list[int]:
    """
    Given an ordered list of speakers (one per dialogue line, in script
    order), returns a list of the same length where each element is the
    pause duration (ms) to insert BEFORE that line's audio chunk.

    Example:
        speakers = ["Host", "Guest1", "Guest1", "Host"]
        -> [0, <random 300-500>, 0, <random 300-500>]
        (no pause before first line, no pause between consecutive
        same-speaker lines, pause inserted on every speaker change)
    """
    schedule: list[int] = []
    previous_speaker: str | None = None

    for speaker in speaker_sequence:
        pause = get_pause_duration_ms(
            previous_speaker, speaker, pause_min_ms, pause_max_ms
        )
        schedule.append(pause)
        previous_speaker = speaker

    return schedule