import os
from django.core.files.storage import default_storage
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import ChatSession, ChatMessage
from .serializers import ChatSessionDetailSerializer, ChatSessionSerializer

from .models import IngestedContent
from .serializers import (
    IngestRequestSerializer,
    IngestedContentSerializer
)
from .AI.src.api_services import ingest_data_to_vector_db, generate_rag_response


class IngestContentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = IngestRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile = request.user.profile
        org_id = serializer.validated_data.get("organization_id")

        created = []

        # Normalize inputs
        files = serializer.validated_data.get("files", [])
        urls = serializer.validated_data.get("urls", [])

        # ---------- FILE INGESTION ----------
        for file in files:
            path = default_storage.save(f"uploads/{file.name}", file)

            content = IngestedContent.objects.create(
                uploaded_by=profile,
                organization_id=org_id,
                file_name=file.name,
                data_url=path,
                content_type="file",
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
                organization_id=org_id,
                file_name=url,
                data_url=url,
                content_type="url",
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
        profile = request.user.profile

        chat_id = request.data.get("chat_id")
        query = request.data.get("query")
        system_prompt = request.data.get("system_prompt")
        org_id = request.data.get("organization_id")

        if not query:
            return Response(
                {"error": "query is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1️⃣ Get or create chat
        if chat_id:
            chat = ChatSession.objects.get(id=chat_id, user=profile)
        else:
            chat = ChatSession.objects.create(
                user=profile,
                organization_id=org_id,
                title=query[:50]
            )

        # 2️⃣ Store user message
        ChatMessage.objects.create(
            chat=chat,
            role="user",
            content=query
        )

        # 3️⃣ Build history
        history = list(
            chat.messages.values("role", "content")
        )

        # 4️⃣ Generate RAG response
        answer = generate_rag_response(
            client_id=str(profile.id),
            user_query=query,
            system_prompt=system_prompt,
            chat_history=history
        )

        # 5️⃣ Store assistant message
        ChatMessage.objects.create(
            chat=chat,
            role="assistant",
            content=answer
        )

        chat.save()  # updates updated_at

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
