import os
from django.core.files.storage import default_storage
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import IngestedContent
from .serializers import (
    IngestRequestSerializer,
    IngestedContentSerializer
)
from .AI.src.api_services import ingest_data_to_vector_db


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
