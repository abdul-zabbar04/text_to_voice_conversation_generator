import re
from dataclasses import dataclass


class ScriptParseError(Exception):
    """Raised when the conversation script fails to parse or validate."""
    pass


@dataclass(frozen=True)
class DialogueLine:
    """
    Represents a single parsed line of dialogue.
    speaker: name as written in the script (e.g. "Host", "Guest1")
    text: the spoken text, with whitespace trimmed
    line_number: original line number in the raw script (for error messages)
    """
    speaker: str
    text: str
    line_number: int


# Matches lines like "Host: Hello everyone."
# Speaker name: letters, digits, underscore only (no spaces, no special chars)
LINE_PATTERN = re.compile(r"^([A-Za-z0-9_]+):\s*(.*)$")


def parse_script(raw_script: str, max_lines: int | None = None) -> list[DialogueLine]:
    """
    Parses raw conversation script text into a list of DialogueLine objects.

    Expected format per line:
        SpeakerName: dialogue text here

    Raises ScriptParseError on:
        - empty script
        - lines that don't match "Speaker: text" format
        - lines with a speaker but empty text
        - exceeding max_lines (if provided)
    """
    if not raw_script or not raw_script.strip():
        raise ScriptParseError("Script is empty.")

    raw_lines = raw_script.strip().splitlines()
    parsed: list[DialogueLine] = []

    for idx, raw_line in enumerate(raw_lines, start=1):
        stripped = raw_line.strip()

        if not stripped:
            # Skip blank lines silently (allows spacing for readability)
            continue

        match = LINE_PATTERN.match(stripped)
        if not match:
            raise ScriptParseError(
                f"Line {idx}: invalid format. Expected 'Speaker: text', got: '{stripped}'"
            )

        speaker, text = match.groups()
        text = text.strip()

        if not text:
            raise ScriptParseError(f"Line {idx}: speaker '{speaker}' has no dialogue text.")

        parsed.append(DialogueLine(speaker=speaker, text=text, line_number=idx))

    if not parsed:
        raise ScriptParseError("Script contains no valid dialogue lines after parsing.")

    if max_lines is not None and len(parsed) > max_lines:
        raise ScriptParseError(
            f"Script has {len(parsed)} lines, which exceeds the maximum allowed ({max_lines})."
        )

    return parsed


def get_unique_speakers(lines: list[DialogueLine]) -> set[str]:
    """Returns the set of distinct speaker names found in the parsed script."""
    return {line.speaker for line in lines}


def validate_voice_map(lines: list[DialogueLine], voice_map: dict[str, str]) -> None:
    """
    Ensures every speaker found in the script has a corresponding entry
    in voice_map. Raises ScriptParseError listing any missing speakers.

    Note: this does NOT validate whether the voice_map values are valid
    Kokoro voice IDs — that's the tts app's responsibility (it owns the
    list of available voices).
    """
    speakers = get_unique_speakers(lines)
    missing = speakers - voice_map.keys()
    if missing:
        missing_sorted = ", ".join(sorted(missing))
        raise ScriptParseError(
            f"Missing voice mapping for speaker(s): {missing_sorted}"
        )