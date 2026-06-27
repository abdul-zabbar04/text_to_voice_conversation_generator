import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.conversation.models import ConversationJob
from apps.conversation.serializers import (
    ConversationGenerateSerializer,
    ConversationJobStatusSerializer,
)
from apps.conversation.services import create_conversation_job
from apps.conversation.parser import ScriptParseError
from apps.conversation.tasks import generate_conversation_audio_task
from apps.tts.kokoro_engine import get_available_voices, KokoroEngineError

logger = logging.getLogger(__name__)


class ConversationGenerateView(APIView):
    """
    POST /api/conversation/generate/

    Accepts a conversation script + voice map, creates a job, enqueues
    async generation via Celery, and immediately returns a job_id for
    polling. Does NOT block waiting for audio generation to finish.
    """

    def post(self, request):
        serializer = ConversationGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data

        try:
            job = create_conversation_job(
                script=validated["script"],
                voice_map=validated["voice_map"],
                keep_chunks=validated.get("keep_chunks", False),
            )
        except ScriptParseError as e:
            # Defensive: the serializer already validates this, but
            # create_conversation_job re-validates independently since
            # it's also callable directly (e.g. scripts, tests) without
            # going through the serializer at all.
            return Response(
                {"success": False, "error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        generate_conversation_audio_task.delay(str(job.id))
        logger.info("Enqueued conversation generation job_id=%s", job.id)

        return Response(
            {
                "success": True,
                "job_id": str(job.id),
                "status": job.status,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class ConversationJobStatusView(APIView):
    """
    GET /api/conversation/<job_id>/status/

    Returns the current state of a generation job. While PENDING/
    PROCESSING, audio_file_url is null. Once COMPLETED, it contains
    a full URL to the generated MP3.
    """

    def get(self, request, job_id):
        try:
            job = ConversationJob.objects.get(id=job_id)
        except ConversationJob.DoesNotExist:
            return Response(
                {"success": False, "error": "Job not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ConversationJobStatusSerializer(job, context={"request": request})
        return Response({"success": True, **serializer.data})


class AvailableVoicesView(APIView):
    """
    GET /api/conversation/voices/

    Returns the list of valid Kokoro voice IDs, so a frontend can
    populate a voice-picker dynamically instead of hardcoding choices.
    """

    def get(self, request):
        try:
            voices = get_available_voices()
        except KokoroEngineError as e:
            return Response(
                {"success": False, "error": f"TTS engine unavailable: {e}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({"success": True, "voices": voices, "count": len(voices)})