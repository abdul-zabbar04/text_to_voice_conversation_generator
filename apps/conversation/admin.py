from django.contrib import admin
from .models import ConversationJob


@admin.register(ConversationJob)
class ConversationJobAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "created_at", "duration_seconds", "keep_chunks")
    list_filter = ("status", "keep_chunks", "created_at")
    readonly_fields = ("id", "created_at", "updated_at")
    search_fields = ("id",)