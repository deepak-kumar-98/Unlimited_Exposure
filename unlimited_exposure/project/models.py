# apps/content/models.py

import uuid
from django.db import models
from django.contrib.auth.models import User
from accounts.models import Profile, Organization


class IngestedContent(models.Model):
    FILE = "file"
    URL = "url"

    CONTENT_TYPES = [
        (FILE, "File"),
        (URL, "URL"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Ownership
    uploaded_by = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="uploaded_contents"
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="contents",
        null=True,
        blank=True
    )

    # Metadata
    file_name = models.CharField(max_length=255)
    content_type = models.CharField(
        max_length=10,
        choices=CONTENT_TYPES
    )

    # Where data comes from
    data_url = models.CharField(
        max_length=1000,
        help_text="Local file path or external URL"
    )

    # Stats
    chunk_count = models.PositiveIntegerField(default=0)
    ingestion_status = models.CharField(
        max_length=50,
        default="pending"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.file_name} ({self.content_type})"



class ChatSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    title = models.CharField(
        max_length=255,
        help_text="Auto-generated from first user query"
    )

    user = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="chat_sessions"
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.user})"


class ChatMessage(models.Model):
    USER = "user"
    ASSISTANT = "assistant"

    ROLES = [
        (USER, "user"),
        (ASSISTANT, "assistant"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    chat = models.ForeignKey(
        "ChatSession",
        on_delete=models.CASCADE,
        related_name="messages"
    )

    role = models.CharField(
        max_length=20,
        choices=ROLES
    )

    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:30]}"



class SystemSettings(models.Model):
    """
    Stores system-level configuration for chat / RAG.
    Currently supports only system_prompt.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    system_prompt = models.TextField(
        help_text="System instruction used for RAG / chat responses"
    )

    # Scope (optional but IMPORTANT)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="system_settings",
        null=True,
        blank=True
    )

    created_by = models.ForeignKey(
        Profile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_system_settings"
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        scope = self.organization.name if self.organization else "Global"
        return f"SystemSettings ({scope})"





