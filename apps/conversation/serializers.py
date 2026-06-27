from rest_framework import serializers
from django.conf import settings

from apps.conversation.parser import parse_script, validate_voice_map, ScriptParseError
from apps.conversation.models import ConversationJob
from apps.tts.kokoro_engine import get_available_voices, KokoroEngineError


class ConversationGenerateSerializer(serializers.Serializer):
    """
    Validates the incoming POST body for /api/conversation/generate/.

    Expected shape:
        {
            "script": "Host: Hello.\nGuest1: Hi.",
            "voice_map": {"Host": "am_adam", "Guest1": "af_sarah"},
            "keep_chunks": false
        }
    """
    script = serializers.CharField(allow_blank=False, trim_whitespace=False)
    voice_map = serializers.DictField(
        child=serializers.CharField(allow_blank=False),
        allow_empty=False,
    )
    keep_chunks = serializers.BooleanField(default=False, required=False)

    def validate_script(self, value):
        try:
            parsed_lines = parse_script(value, max_lines=settings.MAX_SCRIPT_LINES)
        except ScriptParseError as e:
            raise serializers.ValidationError(str(e))
        # Stash parsed lines on the serializer instance so validate()
        # doesn't need to re-parse the script a second time.
        self._parsed_lines = parsed_lines
        return value

    def validate_voice_map(self, value):
        try:
            available_voices = get_available_voices()
        except KokoroEngineError as e:
            # If the model files are missing/misconfigured, fail loudly
            # here rather than letting every request silently 500 deep
            # inside a Celery task later.
            raise serializers.ValidationError(f"TTS engine unavailable: {e}")

        invalid_voices = {v for v in value.values() if v not in available_voices}
        if invalid_voices:
            raise serializers.ValidationError(
                f"Unknown voice id(s): {', '.join(sorted(invalid_voices))}. "
                f"Call GET /api/conversation/voices/ for the full valid list."
            )
        return value

    def validate(self, attrs):
        # Cross-field check: every speaker in the script must have an
        # entry in voice_map. Reuses parsed lines from validate_script
        # if available, otherwise re-parses (defensive fallback).
        parsed_lines = getattr(self, "_parsed_lines", None)
        if parsed_lines is None:
            parsed_lines = parse_script(attrs["script"], max_lines=settings.MAX_SCRIPT_LINES)

        try:
            validate_voice_map(parsed_lines, attrs["voice_map"])
        except ScriptParseError as e:
            raise serializers.ValidationError({"voice_map": str(e)})

        return attrs


class ConversationJobStatusSerializer(serializers.ModelSerializer):
    """
    Shapes a ConversationJob into the JSON returned by the status-check
    endpoint. audio_file_url is built as an absolute URL only once the
    job is completed - otherwise it's null.
    """
    audio_file_url = serializers.SerializerMethodField()

    class Meta:
        model = ConversationJob
        fields = [
            "id",
            "status",
            "audio_file_url",
            "error_message",
            "duration_seconds",
            "keep_chunks",
            "created_at",
            "updated_at",
        ]

    def get_audio_file_url(self, obj: ConversationJob) -> str | None:
        if obj.status != ConversationJob.Status.COMPLETED or not obj.audio_file:
            return None
        request = self.context.get("request")
        if request is not None:
            return request.build_absolute_uri(obj.audio_file.url)
        return obj.audio_file.url