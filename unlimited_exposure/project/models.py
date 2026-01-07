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
