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
from project.serializers import IngestRequestSerializer
from .src.document_processor import DocumentProcessor


class AgentAPI(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        name = request.data.get("name")
        try:
            user_profile = request.user.profile
            organization = Organization.objects.get(owner=user_profile)

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
