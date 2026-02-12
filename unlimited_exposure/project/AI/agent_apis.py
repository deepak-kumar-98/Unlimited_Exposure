import os
from django.conf import settings
from django.core.files.storage import default_storage
from rest_framework.views import APIView
from project.models import Agent, IngestedContent
from accounts.models import Organization, Profile
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound
from project.serializers import IngestRequestSerializer, AgentSerializer
from .src.document_processor import DocumentProcessor


class AgentAPI(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        name = request.data.get("name")
        try:
            user_profile = request.user.profile
            organization = Organization.objects.get(owner=user_profile)

            if Agent.objects.filter(organization=organization, name=name).exists():
                return Response(
                    {"error": "Agent with this name already exists"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            agent = Agent.objects.create(name=name, organization=organization, created_by=user_profile)

            # Handle file upload if present
            uploaded_file = request.FILES.get('file')
            if uploaded_file:
                # Save file
                file_path = default_storage.save(
                    f"uploaded_files/{organization.name}/{uploaded_file.name}",
                    uploaded_file
                )
                
                # Process PDF with DocumentProcessor
                processor = DocumentProcessor(agent_id=str(agent.id))
                result = processor.process_pdf(default_storage.path(file_path))
                
                if result["status"] == "success":
                    # Create IngestedContent record
                    IngestedContent.objects.create(
                        agent=agent,
                        uploaded_by=user_profile,
                        organization=organization,
                        file_name=uploaded_file.name,
                        content_type=IngestedContent.FILE,
                        data_url=file_path,
                        chunk_count=result["chunks"],
                        ingestion_status="completed"
                    )
                    
                    return Response({
                        "message": "Agent created and file processed successfully",
                        "agent_id": agent.id,
                        "chunks": result["chunks"]
                    }, status=status.HTTP_201_CREATED)
                else:
                    return Response({"error": result.get("error")}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            return Response({"message": "Agent created successfully", "agent_id": agent.id}, status=status.HTTP_201_CREATED)

        except Profile.DoesNotExist:
            return Response(
                {"error": "Profile not found. Please complete account verification."},
                status=status.HTTP_403_FORBIDDEN
            )
        except Organization.DoesNotExist:
            return Response({"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        try:
            user_profile = request.user.profile
            organization = Organization.objects.get(owner=user_profile)
            agents = Agent.objects.filter(organization=organization)
            serializer = AgentSerializer(agents, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Profile.DoesNotExist:
            return Response(
                {"error": "Profile not found"},
                status=status.HTTP_403_FORBIDDEN
            )
        except Organization.DoesNotExist:
            return Response({"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND)


class AgentDetailAPI(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self, id, user_profile):
        try:
            organization = Organization.objects.get(owner=user_profile)
            return Agent.objects.get(id=id, organization=organization)
        except (Organization.DoesNotExist, Agent.DoesNotExist):
            raise NotFound("Agent not found or you do not have permission to access it.")

    def get(self, request, id):
        try:
            agent = self.get_object(id, request.user.profile)
            serializer = AgentSerializer(agent)
            data = serializer.data
            
            # Check if a specific role is requested for dynamic prompt generation
            requested_role = request.query_params.get("role")
            
            # If role param exists, FORCE generation based on that role
            if requested_role and agent.created_by:
                from .src.api_services import generate_dynamic_system_prompt
                try:
                    dynamic_prompt = generate_dynamic_system_prompt(
                        client_id=str(agent.created_by.id),
                        personas=[requested_role]
                    )
                    data["system_prompt"] = dynamic_prompt
                    # Also update the returned role to match the requested one for consistency in UI
                    data["role"] = requested_role
                except Exception as e:
                    print(f"Error generating dynamic prompt for role '{requested_role}': {e}")

            # Else if no system_prompt is stored, try to generate a default one
            elif not data.get("system_prompt") and agent.created_by:
                from .src.api_services import generate_dynamic_system_prompt
                try:
                    # Provide empty personas list to trigger DB content auto-discovery or default
                    dynamic_prompt = generate_dynamic_system_prompt(
                        client_id=str(agent.created_by.id),
                        personas=[] 
                    )
                    data["system_prompt"] = dynamic_prompt
                except Exception as e:
                    print(f"Error generating dynamic prompt: {e}")
                    
            return Response(data, status=status.HTTP_200_OK)
        except NotFound as e:
             return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, id):
        try:
            agent = self.get_object(id, request.user.profile)
            serializer = AgentSerializer(agent, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except NotFound as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
