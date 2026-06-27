from django.urls import path

from apps.conversation.views import (
    ConversationGenerateView,
    ConversationJobStatusView,
    AvailableVoicesView,
)

app_name = "conversation"

urlpatterns = [
    path("generate/", ConversationGenerateView.as_view(), name="generate"),
    path("voices/", AvailableVoicesView.as_view(), name="voices"),
    path("<uuid:job_id>/status/", ConversationJobStatusView.as_view(), name="job-status"),
]