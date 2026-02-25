import os
from django.core.files.storage import default_storage
from rest_framework.views import APIView
from project.models import Agent, IngestedContent
from accounts.models import Organization, Profile
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound
from project.serializers import AgentSerializer
from .src.document_processor import DocumentProcessor
from .src.api_services import extract_text_from_file, scrape_website_content


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
            processor = DocumentProcessor(agent_id=str(agent.id))

            # Handle file upload if present
            uploaded_files = request.FILES.getlist('file')
            if uploaded_files:
                for file in uploaded_files:
                    file_path = default_storage.save(
                        f"uploaded_files/{organization.name}/{file.name}",
                        file
                    )
                    full_path = default_storage.path(file_path)
                    ext = os.path.splitext(file.name)[1].lower()
                    
                    # Use process_pdf for PDFs, extract_text_from_file + process_text for others
                    if ext == '.pdf':
                        result = processor.process_pdf(full_path)
                    else:
                        extracted_text = extract_text_from_file(full_path)
                        if not extracted_text.strip():
                            return Response({"error": "Failed to extract text from file"}, status=status.HTTP_400_BAD_REQUEST)
                        result = processor.process_text(extracted_text, source=file.name)
                    
                    if result["status"] == "success":
                        IngestedContent.objects.create(
                            agent=agent,
                            uploaded_by=user_profile,
                            organization=organization,
                            file_name=file.name,
                            content_type=IngestedContent.FILE,
                            data_url=file_path,
                            chunk_count=result["chunks"],
                            ingestion_status="completed"
                        )

            
            # Handle URL scraping if present
            urls = request.data.get('url', [])
            if urls and not isinstance(urls, list):
                urls = [urls]
            
            for url in urls:
                if url and url.strip():
                    # Validate URL format
                    if not url.startswith(('http://', 'https://')):
                        url = 'https://' + url
                    
                    try:
                        scraped_text = scrape_website_content(url)
                        if not scraped_text.strip():
                            print(f"Warning: No content scraped from {url}")
                            continue
                        
                        result = processor.process_text(scraped_text, source=url)
                        
                        if result["status"] == "success":
                            IngestedContent.objects.create(
                                agent=agent,
                                uploaded_by=user_profile,
                                organization=organization,
                                file_name=url,
                                content_type=IngestedContent.URL,
                                data_url=url,
                                chunk_count=result["chunks"],
                                ingestion_status="completed"
                            )
                    except Exception as e:
                        print(f"Error scraping URL {url}: {str(e)}")
                        continue
            
            return Response({
                        "message": "Agent created and URL content processed successfully",
                        "agent_id": agent.id
                    }, status=status.HTTP_201_CREATED)

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
            queryset = Agent.objects.filter(organization=organization)
            total_count = queryset.count()

            # Parse limit / offset
            try:
                limit = int(request.query_params.get('limit', 10))
                offset = int(request.query_params.get('offset', 0))
                if limit < 1 or offset < 0:
                    raise ValueError
            except (ValueError, TypeError):
                return Response(
                    {"error": "limit must be a positive integer and offset must be >= 0"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            agents = queryset[offset: offset + limit]
            serializer = AgentSerializer(agents, many=True)

            # Build next / previous URLs
            base_url = request.build_absolute_uri(request.path)

            next_offset = offset + limit
            next_url = (
                f"{base_url}?limit={limit}&offset={next_offset}"
                if next_offset < total_count else None
            )

            prev_offset = offset - limit
            previous_url = (
                f"{base_url}?limit={limit}&offset={max(prev_offset, 0)}"
                if offset > 0 else None
            )

            return Response({
                "count": total_count,
                "next": next_url,
                "previous": previous_url,
                "results": serializer.data,
            }, status=status.HTTP_200_OK)

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


    def delete(self, request, id):
        try:
            agent = self.get_object(id, request.user.profile)
            agent_name = agent.name
            
            # Clean up vector database entries for this agent
            try:
                processor = DocumentProcessor(agent_id=str(agent.id))
                processor.delete_agent_vectors()
            except Exception as e:
                print(f"Error deleting vectors for agent {agent.id}: {e}")
            
            # Delete the agent (cascade will delete related IngestedContent)
            agent.delete()
            
            return Response(
                {"message": f"Agent '{agent_name}' and all associated data deleted successfully"},
                status=status.HTTP_200_OK
            )
        except NotFound as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

