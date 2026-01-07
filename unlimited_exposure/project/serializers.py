# apps/content/serializers.py

from rest_framework import serializers
from .models import IngestedContent

class IngestedContentSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.StringRelatedField(read_only=True)
    organization = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = IngestedContent
        fields = [
            "id",
            "file_name",
            "content_type",
            "data_url",
            "chunk_count",
            "ingestion_status",
            "uploaded_by",
            "organization",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "chunk_count",
            "ingestion_status",
            "created_at",
            "updated_at",
        ]


class IngestRequestSerializer(serializers.Serializer):
    files = serializers.ListField(
        child=serializers.FileField(),
        required=False
    )
    urls = serializers.ListField(
        child=serializers.URLField(),
        required=False
    )
    organization_id = serializers.UUIDField(required=False)

    def validate(self, data):
        if not data.get("files") and not data.get("urls"):
            raise serializers.ValidationError(
                "Provide at least one file or one URL."
            )
        return data
