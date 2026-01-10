# apps/content/serializers.py

from rest_framework import serializers
from .models import IngestedContent
from .models import ChatSession, ChatMessage, SystemSettings

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


# class IngestRequestSerializer(serializers.Serializer):
#     files = serializers.ListField(
#         child=serializers.FileField(),
#         required=False
#     )
#     urls = serializers.ListField(
#         child=serializers.URLField(),
#         required=False
#     )
#     organization_id = serializers.UUIDField(required=False)

#     def validate(self, data):
#         if not data.get("files") and not data.get("urls"):
#             raise serializers.ValidationError(
#                 "Provide at least one file or one URL."
#             )
#         return data


class IngestRequestSerializer(serializers.Serializer):
    files = serializers.ListField(
        child=serializers.FileField(),
        required=False
    )
    urls = serializers.ListField(
        child=serializers.URLField(),
        required=False
    )

    def validate(self, data):
        if not data.get("files") and not data.get("urls"):
            raise serializers.ValidationError(
                "Provide at least one file or one URL."
            )
        return data



class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ["id", "role", "content", "created_at"]


class ChatSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = ["id", "title", "created_at", "updated_at"]


class ChatSessionDetailSerializer(serializers.ModelSerializer):
    messages = ChatMessageSerializer(many=True)

    class Meta:
        model = ChatSession
        fields = ["id", "title", "messages", "created_at", "updated_at"]


class SystemSettingsCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSettings
        fields = ["system_prompt"]


class SystemSettingsSerializer(serializers.ModelSerializer):
    organization = serializers.SerializerMethodField()
    
    def get_organization(self, obj):
        """Return organization ID if exists, otherwise None"""
        return obj.organization.id if obj.organization else None
    
    class Meta:
        model = SystemSettings
        fields = [
            "id",
            "system_prompt",
            "organization",
            "is_active",
            "created_at",
            "updated_at"
        ]
