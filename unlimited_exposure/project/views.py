import os
from django.core.files.storage import default_storage
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from django.db.models import Q
import hashlib


from .models import ChatSession, ChatMessage, SystemSettings, Organization, Agent
from .serializers import ChatSessionDetailSerializer, ChatSessionSerializer, GenerateSystemPromptSerializer, PreviewSystemPromptSerializer, SystemSettingsCreateSerializer, SystemSettingsSerializer, ChatMessageSerializer

from .models import IngestedContent
from .serializers import (
    IngestRequestSerializer,
    IngestedContentSerializer,
)
from .AI.src.api_services import generate_dynamic_system_prompt, ingest_data_to_vector_db, generate_rag_response
from .AI.src.vector_store import VectorStore


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
        
        # Get agent_id from query params or request data
        agent_id = request.query_params.get("agent_id") or request.data.get("agent_id")
        agent = None
        
        # If agent_id is provided, verify it belongs to the user's organization
        if agent_id:
            try:
                agent = Agent.objects.get(id=agent_id, organization=organization)
            except Agent.DoesNotExist:
                return Response(
                    {"error": "Agent not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND
                )

        created = []

        files = serializer.validated_data.get("files", [])
        urls = serializer.validated_data.get("urls", [])

        # ---------- FILE INGESTION ----------
        for file in files:
            path = default_storage.save(f"uploads/{file.name}", file)

            content = IngestedContent.objects.create(
                agent=agent,
                uploaded_by=profile,
                organization=organization,
                file_name=file.name,
                data_url=path,
                content_type=IngestedContent.FILE,
                ingestion_status="processing"
            )

            # Use agent-based ingestion if agent is provided
            if agent:
                from .AI.src.document_processor import DocumentProcessor
                processor = DocumentProcessor(agent_id=str(agent.id))
                result = processor.process_pdf(default_storage.path(path))
            else:
                # Fallback to old client-based ingestion
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
                agent=agent,
                uploaded_by=profile,
                organization=organization,
                file_name=url,
                data_url=url,
                content_type=IngestedContent.URL,
                ingestion_status="processing"
            )

            # Use agent-based ingestion if agent is provided
            if agent:
                from .AI.src.document_processor import DocumentProcessor
                processor = DocumentProcessor(agent_id=str(agent.id))
                # For URLs, use process_text method (you may need to fetch URL content first)
                # This is a simplified version - you might need to add URL fetching logic
                result = ingest_data_to_vector_db(
                    client_id=str(profile.id),
                    content_source=url,
                    is_url=True
                )
            else:
                # Fallback to old client-based ingestion
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


class KnowledgeBaseAPIView(ListAPIView):
    """
    Get all ingested content (knowledge base) for the user's organization.
    Optionally filter by agent_id to get agent-specific knowledge base.
    """
    serializer_class = IngestedContentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            profile = self.request.user.profile
        except Profile.DoesNotExist:
            raise PermissionDenied("Profile not found")
        
        user_organization = profile.organization
        
        # Get agent_id from query params if provided
        agent_id = self.request.query_params.get("agent_id")
        
        # Base query: filter by organization or uploaded_by
        base_query = Q(organization=user_organization) | Q(uploaded_by=profile)
        
        # If agent_id is provided, filter by agent
        if agent_id:
            try:
                # Verify the agent belongs to the user's organization
                agent = Agent.objects.get(id=agent_id, organization=user_organization)
                # Filter by agent
                return IngestedContent.objects.filter(
                    base_query & Q(agent=agent)
                ).order_by("-created_at")
            except Agent.DoesNotExist:
                raise PermissionDenied("Agent not found or access denied")
        
        # Return all ingested content for the user's organization
        return IngestedContent.objects.filter(base_query).order_by("-created_at")


class KnowledgeBaseDeleteAPIView(APIView):
    """
    Delete a specific ingested content by ID.
    Users can only delete content from their organization or content they uploaded.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, id):
        """
        Delete ingested content by ID.
        """
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return Response(
                {"error": "Profile not found. Please complete account setup."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            ingested_content = IngestedContent.objects.get(id=id)
        except IngestedContent.DoesNotExist:
            raise NotFound("Ingested content not found")

        user_organization = profile.organization
        can_delete = (
            ingested_content.organization == user_organization or
            ingested_content.uploaded_by == profile
        )

        if not can_delete:
            return Response(
                {"error": "You do not have permission to delete this content"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Delete vectors from the agent's vector database
        if ingested_content.agent:
            try:
                from .AI.src.document_processor import DocumentProcessor
                
                # Get the document source for deletion
                if ingested_content.content_type == IngestedContent.FILE:
                    try:
                        full_path = default_storage.path(ingested_content.data_url)
                        document_source = os.path.basename(full_path)
                    except Exception as e:
                        print(f"⚠️ Warning: Could not get storage path, using file_name as fallback: {e}")
                        document_source = ingested_content.file_name
                else:
                    document_source = ingested_content.data_url
                
                # Use DocumentProcessor to delete from agent's vector database
                processor = DocumentProcessor(agent_id=str(ingested_content.agent.id))
                result = processor.delete_document(document_source)
                
                if result.get("status") == "success":
                    print(f"✅ Deleted vectors for document '{document_source}' from agent {ingested_content.agent.id}")
                else:
                    print(f"⚠️ Warning: Failed to delete vectors: {result.get('error')}")
                    
            except Exception as e:
                print(f"❌ Error deleting from agent vector database: {e}")
                import traceback
                traceback.print_exc()
        else:
            # Fallback to old client-based deletion for backward compatibility
            if ingested_content.content_type == IngestedContent.FILE:
                try:
                    full_path = default_storage.path(ingested_content.data_url)
                    document_id = os.path.basename(full_path)
                except Exception as e:
                    print(f"⚠️ Warning: Could not get storage path, using file_name as fallback: {e}")
                    document_id = os.path.basename(ingested_content.file_name)
            else:
                document_id = ingested_content.data_url
            
            client_id = str(ingested_content.uploaded_by.id)
            
            try:
                vector_store = VectorStore()
                deleted_chunks = vector_store.delete_documents(client_id, document_id)
                print(f"✅ Deleted {deleted_chunks} chunks from vector database for client_id={client_id}, document_id={document_id}")
                if deleted_chunks == 0:
                    print(f"⚠️ Warning: No chunks found with document_id={document_id}. Trying alternative formats...")
                    
                    if ingested_content.content_type == IngestedContent.FILE:
                        alt_document_id = ingested_content.file_name
                        deleted_chunks = vector_store.delete_documents(client_id, alt_document_id)
                        if deleted_chunks > 0:
                            print(f"✅ Deleted {deleted_chunks} chunks using alternative document_id={alt_document_id}")
                        else:
                            alt_document_id = os.path.basename(ingested_content.data_url)
                            deleted_chunks = vector_store.delete_documents(client_id, alt_document_id)
                            if deleted_chunks > 0:
                                print(f"✅ Deleted {deleted_chunks} chunks using alternative document_id={alt_document_id}")
                            else:
                                print(f"⚠️ Warning: No chunks found to delete with any document_id format. client_id={client_id}, tried: {document_id}, {ingested_content.file_name}, {alt_document_id}")
                    else:
                        print(f"⚠️ Warning: No chunks found to delete. client_id={client_id}, document_id={document_id}")
                else:
                    print(f"✅ Successfully deleted {deleted_chunks} embedding chunks")
                    
            except Exception as e:
                print(f"❌ Error deleting from vector database: {e}")
                import traceback
                traceback.print_exc()
        
        # Delete the ingested content record
        ingested_content.delete()

        return Response(
            {"message": "Ingested content deleted successfully"},
            status=status.HTTP_200_OK
        )



class CreateSystemSettingsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Retrieve active system setting for an organization.
        If organization_id is provided, returns active prompt for that organization.
        If not provided, returns active global prompt (organization is null).
        """
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return Response(
                {"error": "Profile not found. Please complete account setup."},
                status=status.HTTP_403_FORBIDDEN
            )

        # 🔹 Read organization_id from query params
        organization_id = request.query_params.get("org_id")

        organization = None
        if organization_id:
            try:
                organization = Organization.objects.get(id=organization_id)
                
                # 🔒 Access control: User must be from the requested organization
                if organization != profile.organization:
                    return Response(
                        {"error": "You do not have permission to access this organization's settings"},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Organization.DoesNotExist:
                return Response(
                    {"error": "Invalid org_id"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # 🔹 Get active system setting for the organization (or global if org is None)
        system_settings = (
            SystemSettings.objects.filter(
                organization=organization,
                is_active=True
            )
            .order_by("-created_at")
            .first()
        )

        if not system_settings:
            # Return 404 with clear message if no active setting found
            if organization:
                return Response(
                    {
                        "error": "No active system setting found",
                        "message": f"No active system prompt found for organization {organization.name}",
                        "organization_id": str(organization.id)
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            else:
                return Response(
                    {
                        "error": "No active system setting found",
                        "message": "No active global system prompt found"
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

        return Response(
            {"system_prompt": system_settings.system_prompt},
            status=status.HTTP_200_OK
        )

    def post(self, request):
        serializer = SystemSettingsCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile = request.user.profile

        # 🔹 Read organization_id from query params
        organization_id = request.query_params.get("org_id")

        organization = None
        if organization_id:
            try:
                organization = Organization.objects.get(id=organization_id)
            except Organization.DoesNotExist:
                return Response(
                    {"error": "Invalid org_id"},
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




class ChatMessagesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, chat_id):
        """
        Retrieve a chat session with all its messages.
        Returns chat session details including messages array.
        """
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            raise PermissionDenied("Profile not found")

        try:
            chat = ChatSession.objects.prefetch_related('messages').get(
                id=chat_id,
                user=profile   # 🔒 prevents access to others' chats
            )
        except ChatSession.DoesNotExist:
            raise NotFound("Chat session not found")

        # Use ChatSessionDetailSerializer to return the desired format
        serializer = ChatSessionDetailSerializer(chat)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PreviewSystemPromptAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            return Response(
                {"error": "Profile not found. Please complete account setup."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get personas from query params (comma-separated string)
        personas_param = request.query_params.get("personas", "")
        
        personas = []
        if personas_param:
            personas = [
                p.strip().lower()
                for p in personas_param.split(",")
                if p.strip()
            ]

        prompt = generate_dynamic_system_prompt(
            client_id=str(profile.id),
            personas=personas if personas else None
        )

        return Response(
            {
                "personas": personas or ["default"],
                "system_prompt": prompt
            },
            status=status.HTTP_200_OK
        )


class GenerateSystemPromptAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = GenerateSystemPromptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile = request.user.profile
        organization = profile.organization

        # Check if agent_id is provided
        agent_id = request.query_params.get("agent_id")
        
        if agent_id:
            # Update Agent instead of creating SystemSettings
            try:
                agent = Agent.objects.get(id=agent_id, organization=organization)
                
                # Extract data from request
                system_prompt = serializer.validated_data.get("system_prompt")
                personas = serializer.validated_data.get("personas", [])
                
                # Update agent fields
                if system_prompt:
                    agent.system_prompt = system_prompt
                
                # Store all personas in role field (as a list)
                if personas:
                    agent.role = personas
                else:
                    # Set default role if no personas provided
                    agent.role = ["Support Agent"]
                
                agent.save()
                
                # Return agent data in similar format
                from .serializers import AgentSerializer
                agent_serializer = AgentSerializer(agent)
                
                return Response(
                    {
                        "id": str(agent.id),
                        "agent_id": str(agent.id),
                        "system_prompt": agent.system_prompt,
                        "role": agent.role,
                        "updated_at": agent.updated_at,
                        "source": "agent"
                    },
                    status=status.HTTP_200_OK
                )
                
            except Agent.DoesNotExist:
                return Response(
                    {"error": "Agent not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Original logic: Create organization-level SystemSettings
        personas = [
            p.strip().lower()
            for p in serializer.validated_data.get("personas", [])
            if p.strip()
        ]

        system_prompt = serializer.validated_data["system_prompt"]

        # Deactivate previous active prompt
        SystemSettings.objects.filter(
            organization=organization,
            is_active=True
        ).update(is_active=False)

        settings = SystemSettings.objects.create(
            system_prompt=system_prompt,
            personas=personas or ["default"],
            organization=organization,
            created_by=profile,
            is_active=True
        )

        return Response(
            {
                "id": settings.id,
                "personas": settings.personas,
                "system_prompt": settings.system_prompt,
                "created_at": settings.created_at,
                "source": "organization"
            },
            status=status.HTTP_201_CREATED
        )


class ActiveSystemPromptAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = request.user.profile
        organization = profile.organization

        agent_id = request.query_params.get("agent_id")
        
        # 1. Start with response structure
        response = {
            "active_system_prompt": None,
            "active_personas": ["default"],
            "source": "none"
        }

        # 2. If agent_id is provided, try to get Agent's prompt first
        if agent_id:
            try:
                agent = Agent.objects.get(id=agent_id, organization=organization)
                
                # A. Check for explicit system_prompt on Agent
                if agent.system_prompt:
                    response.update({
                        "id": str(agent.id),
                        "active_system_prompt": agent.system_prompt,
                        "active_personas": [agent.role] if agent.role else ["assistant"],
                        "updated_at": agent.updated_at,
                        "source": "agent_specific"
                    })
                    return Response(response, status=status.HTTP_200_OK)
                
                # B. Dynamic generation based on Role if no explicit prompt
                elif agent.role:
                     from .AI.src.api_services import generate_dynamic_system_prompt
                     try:
                        dynamic_prompt = generate_dynamic_system_prompt(
                            client_id=str(agent.created_by.id) if agent.created_by else str(profile.id),
                            personas=[agent.role]
                        )
                        response.update({
                            "id": str(agent.id),
                            "active_system_prompt": dynamic_prompt,
                            "active_personas": [agent.role],
                            "updated_at": agent.updated_at,
                            "source": "agent_dynamic_role"
                        })
                        return Response(response, status=status.HTTP_200_OK)
                     except Exception as e:
                         print(f"Error generating dynamic prompt for agent {agent.id}: {e}")

            except Agent.DoesNotExist:
                return Response(
                    {"error": "Agent not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND
                )

        # 3. Fallback to Organization/Global System Settings
        active = SystemSettings.objects.filter(
            organization=organization,
            is_active=True
        ).first()

        if active:
            response.update({
                "id": str(active.id),
                "active_system_prompt": active.system_prompt,
                "active_personas": active.personas,
                "updated_at": active.updated_at,
                "source": "organization_settings"
            })
            
        return Response(response, status=status.HTTP_200_OK)
