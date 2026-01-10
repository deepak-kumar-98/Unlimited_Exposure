import os
from django.core.files.storage import default_storage
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied


from .models import ChatSession, ChatMessage, SystemSettings, Organization
from .serializers import ChatSessionDetailSerializer, ChatSessionSerializer, SystemSettingsCreateSerializer, ChatMessageSerializer

from .models import IngestedContent
from .serializers import (
    IngestRequestSerializer,
    IngestedContentSerializer
)
from .AI.src.api_services import ingest_data_to_vector_db, generate_rag_response


from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from accounts.models import Profile
from .models import IngestedContent


class IngestContentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 🔒 Enforce profile existence
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return Response(
                {"error": "Profile not found. Please complete account verification."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = IngestRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # 🔒 Always derive org from profile (never from request)
        organization = profile.organization

        created = []

        files = serializer.validated_data.get("files", [])
        urls = serializer.validated_data.get("urls", [])

        # ---------- FILE INGESTION ----------
        for file in files:
            path = default_storage.save(f"uploads/{file.name}", file)

            content = IngestedContent.objects.create(
                uploaded_by=profile,
                organization=organization,
                file_name=file.name,
                data_url=path,
                content_type=IngestedContent.FILE,
                ingestion_status="processing"
            )

            result = ingest_data_to_vector_db(
                client_id=str(profile.id),
                content_source=default_storage.path(path),
                is_url=False
            )

            content.chunk_count = result.get("chunks", 0)
            content.ingestion_status = result.get("status")
            content.save()

            created.append(content)

        # ---------- URL INGESTION ----------
        for url in urls:
            content = IngestedContent.objects.create(
                uploaded_by=profile,
                organization=organization,
                file_name=url,
                data_url=url,
                content_type=IngestedContent.URL,
                ingestion_status="processing"
            )

            result = ingest_data_to_vector_db(
                client_id=str(profile.id),
                content_source=url,
                is_url=True
            )

            content.chunk_count = result.get("chunks", 0)
            content.ingestion_status = result.get("status")
            content.save()

            created.append(content)

        return Response(
            IngestedContentSerializer(created, many=True).data,
            status=status.HTTP_201_CREATED
        )



class RAGChatAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 🔒 Enforce profile existence
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return Response(
                {"error": "Profile not found. Please complete account setup."},
                status=status.HTTP_403_FORBIDDEN
            )

        query = request.data.get("query")
        chat_id = request.data.get("chat_id")

        if not query:
            return Response(
                {"error": "query is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        organization = profile.organization

        # 1️⃣ Resolve system prompt (ORG → GLOBAL fallback)
        system_settings = (
            SystemSettings.objects.filter(
                organization=organization,
                is_active=True
            ).order_by("-created_at")
            .first()
        )

        if not system_settings:
            system_settings = (
                SystemSettings.objects.filter(
                    organization__isnull=True,
                    is_active=True
                ).order_by("-created_at")
                .first()
            )

        system_prompt = system_settings.system_prompt if system_settings else None

        # 2️⃣ Get or create chat session
        if chat_id:
            chat = ChatSession.objects.get(
                id=chat_id,
                user=profile
            )
        else:
            chat = ChatSession.objects.create(
                user=profile,
                organization=organization,
                title=query[:50]
            )

        # 3️⃣ Store user message
        ChatMessage.objects.create(
            chat=chat,
            role=ChatMessage.USER,
            content=query
        )

        # 4️⃣ Build conversation history (last N messages)
        history = list(
            chat.messages.order_by("created_at")
            .values("role", "content")
        )

        # 5️⃣ Generate RAG response
        answer = generate_rag_response(
            client_id=str(profile.id),
            user_query=query,
            system_prompt=system_prompt,
            chat_history=history
        )

        # 6️⃣ Store assistant message
        ChatMessage.objects.create(
            chat=chat,
            role=ChatMessage.ASSISTANT,
            content=answer
        )

        chat.save(update_fields=["updated_at"])

        return Response(
            ChatSessionDetailSerializer(chat).data,
            status=status.HTTP_200_OK
        )




class ChatListAPIView(ListAPIView):
    serializer_class = ChatSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ChatSession.objects.filter(
            user=self.request.user.profile
        ).order_by("-updated_at")



class CreateSystemSettingsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SystemSettingsCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile = request.user.profile

        # 🔹 Read organization_id from query params
        organization_id = request.query_params.get("organization_id")

        organization = None
        if organization_id:
            try:
                organization = Organization.objects.get(id=organization_id)
            except Organization.DoesNotExist:
                return Response(
                    {"error": "Invalid organization_id"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # 🔹 Deactivate previous active prompt for same scope
        SystemSettings.objects.filter(
            organization=organization,
            is_active=True
        ).update(is_active=False)

        # 🔹 Create new system prompt
        system_settings = SystemSettings.objects.create(
            system_prompt=serializer.validated_data["system_prompt"],
            organization=organization,
            created_by=profile,
            is_active=True
        )

        return Response(
            {
                "id": system_settings.id,
                "system_prompt": system_settings.system_prompt,
                "organization": organization.id if organization else None,
                "created_at": system_settings.created_at,
            },
            status=status.HTTP_201_CREATED
        )




class ChatMessagesAPIView(ListAPIView):
    serializer_class = ChatMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        chat_id = self.kwargs.get("chat_id")

        try:
            profile = self.request.user.profile
        except Profile.DoesNotExist:
            raise PermissionDenied("Profile not found")

        try:
            chat = ChatSession.objects.get(
                id=chat_id,
                user=profile   # 🔒 prevents access to others' chats
            )
        except ChatSession.DoesNotExist:
            raise NotFound("Chat session not found")

        return chat.messages.order_by("created_at")
