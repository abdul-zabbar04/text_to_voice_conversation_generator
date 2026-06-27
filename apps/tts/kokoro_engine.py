from pathlib import Path
from functools import lru_cache

import soundfile as sf
from kokoro_onnx import Kokoro
from django.conf import settings


class KokoroEngineError(Exception):
    """Raised when TTS synthesis fails or an invalid voice is requested."""
    pass


@lru_cache(maxsize=1)
def get_engine() -> Kokoro:
    """
    Loads and caches a single Kokoro instance for the lifetime of the
    process. Loading the ONNX model + voice pack is relatively expensive
    (disk read + session init), so we do it once per worker process,
    not once per request.

    lru_cache(maxsize=1) with no arguments acts as a simple memoized
    singleton here.
    """
    model_path = str(settings.BASE_DIR / "models" / "kokoro-v1.0.onnx")
    voices_path = str(settings.BASE_DIR / "models" / "voices-v1.0.bin")

    if not Path(model_path).exists():
        raise KokoroEngineError(f"Kokoro model file not found at: {model_path}")
    if not Path(voices_path).exists():
        raise KokoroEngineError(f"Kokoro voices file not found at: {voices_path}")

    return Kokoro(model_path=model_path, voices_path=voices_path)


def get_available_voices() -> list[str]:
    """
    Returns the list of valid Kokoro voice IDs (e.g. 'am_adam', 'af_sarah').
    Used by serializers to validate user-submitted voice_map values
    dynamically, rather than hardcoding a list that could go stale.
    """
    engine = get_engine()
    return engine.get_voices()


def synthesize_to_file(
    text: str,
    voice: str,
    output_path: str | Path,
    speed: float = 1.0,
    lang: str = "en-us",
) -> Path:
    """
    Synthesizes a single line of text into a WAV file using the given voice.

    Args:
        text: the dialogue text to speak.
        voice: a valid Kokoro voice ID (e.g. 'am_adam').
        output_path: where to write the resulting WAV file.
        speed: playback speed multiplier (1.0 = normal).
        lang: language code passed to the phonemizer.

    Returns:
        Path to the written WAV file.

    Raises:
        KokoroEngineError: if the voice is invalid or synthesis fails.
    """
    engine = get_engine()

    available_voices = engine.get_voices()
    if voice not in available_voices:
        raise KokoroEngineError(
            f"Unknown voice '{voice}'. Available voices: {', '.join(available_voices)}"
        )

    if not text or not text.strip():
        raise KokoroEngineError("Cannot synthesize empty text.")

    try:
        samples, sample_rate = engine.create(text, voice=voice, speed=speed, lang=lang)
    except Exception as e:
        raise KokoroEngineError(f"Synthesis failed for voice '{voice}': {e}") from e

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        sf.write(str(output_path), samples, sample_rate)
    except Exception as e:
        raise KokoroEngineError(f"Failed to write WAV file '{output_path}': {e}") from e

    return output_path