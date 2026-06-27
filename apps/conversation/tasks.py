import logging

from celery import shared_task

from apps.conversation.services import run_conversation_generation, ConversationGenerationError

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=0,  # generation failures are usually deterministic (bad voice, bad script)
    # so blind retries won't help; we surface the failure on the job instead.
    name="conversation.generate_audio",
)
def generate_conversation_audio_task(self, job_id: str) -> str:
    """
    Celery task wrapper around run_conversation_generation().

    Takes only a job_id (string) - not the full job object - since
    Celery serializes task arguments (JSON by default per our settings),
    and passing a Django model instance directly would be both wasteful
    and unsafe (stale data if the row changes between enqueue and execution).

    Returns the job_id on success so it's visible in Celery's result
    backend / Flower dashboards. Re-raises ConversationGenerationError
    so Celery records the task itself as FAILED too (in addition to the
    ConversationJob row already being marked FAILED inside services.py) -
    this gives us two independent places to see failure: the job table
    for end users, and Celery's task results for ops/debugging.
    """
    logger.info("Starting conversation generation for job_id=%s", job_id)

    try:
        job = run_conversation_generation(job_id)
        logger.info(
            "Completed conversation generation for job_id=%s in %.2fs",
            job_id,
            job.duration_seconds or 0,
        )
        return job_id

    except ConversationGenerationError as e:
        logger.error("Conversation generation failed for job_id=%s: %s", job_id, e)
        raise