import os
from django.core.files.storage import default_storage
from rest_framework.views import APIView
from project.models import Agent, IngestedContent, AgentSettings
from accounts.models import Organization, Profile, OrganizationMember
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound
from project.serializers import AgentSerializer, AgentSettingsSerializer
from .src.document_processor import DocumentProcessor
from .src.api_services import extract_text_from_file, scrape_website_content


class AgentAPI(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        name = request.data.get("name")
        try:
            org_id = request.query_params.get("org_id") or request.data.get("org_id")
            user_profile = request.user.profile

            if not org_id:
                return Response({"error": "org_id is required"}, status=status.HTTP_400_BAD_REQUEST)

            member = OrganizationMember.objects.filter(organization=org_id, user=user_profile, role__in=[OrganizationMember.OWNER, OrganizationMember.ADMIN]).first()

            if not member:
                return Response({"error": "You do not have permission to perform this action"}, status=status.HTTP_403_FORBIDDEN)

            if not user_profile.subscription:
                return Response(
                    {"error": "Please purchase any plan"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            organization = Organization.objects.get(owner=user_profile)

            if Agent.objects.filter(organization=organization, name=name).exists():
                return Response(
                    {"error": "Agent with this name already exists"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            agent = Agent.objects.create(name=name, organization=organization, created_by=user_profile)
            
            # Create default agent settings
            AgentSettings.objects.create(
                agent=agent,
                theme_color=request.data.get('theme_color'),
                is_embedded=request.data.get('is_embedded', False),
                chatbot_dimension=request.data.get('chatbot_dimension'),
                text_colour=request.data.get('text_colour', '#00000099'),
                header_color=request.data.get('header_color', '#070706'),
                header_text_color=request.data.get('header_text_color', 'white'),
                collecting_leads=request.data.get('collecting_leads', False)
            )
            
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
                    
                    # Route to appropriate processor based on file extension
                    if ext == '.pdf':
                        result = processor.process_pdf(full_path)
                    elif ext == '.csv':
                        result = processor.process_csv(full_path)
                    elif ext in ['.xlsx', '.xls']:
                        result = processor.process_xlsx(full_path)
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
                        scraped_text = scrape_website_content(url, is_sitemap=False)
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
            
            # Handle sitemap scraping if present
            sitemap = request.data.get('sitemap')
            if sitemap and sitemap.strip():
                # Validate sitemap URL format
                if not sitemap.startswith(('http://', 'https://')):
                    sitemap = 'https://' + sitemap
                
                try:
                    scraped_text = scrape_website_content(sitemap, is_sitemap=True)
                    if not scraped_text.strip():
                        print(f"Warning: No content scraped from sitemap {sitemap}")
                    else:
                        result = processor.process_text(scraped_text, source=sitemap)
                        
                        if result["status"] == "success":
                            IngestedContent.objects.create(
                                agent=agent,
                                uploaded_by=user_profile,
                                organization=organization,
                                file_name=f"Sitemap: {sitemap}",
                                content_type=IngestedContent.URL,
                                data_url=sitemap,
                                chunk_count=result["chunks"],
                                ingestion_status="completed"
                            )
                except Exception as e:
                    print(f"Error scraping sitemap {sitemap}: {str(e)}")
            
            return Response({
                        "message": "Agent created and content processed successfully",
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

            # Read org_id from query params
            org_id = request.query_params.get("org_id")
            if not org_id:
                return Response(
                    {"error": "org_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Ensure the user belongs to this organization (any role)
            member = OrganizationMember.objects.filter(
                organization=org_id,
                user=user_profile,
            ).first()
            if not member:
                return Response(
                    {"error": "You do not have permission to access this organization's agents"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            try:
                organization = Organization.objects.get(id=org_id)
            except Organization.DoesNotExist:
                return Response(
                    {"error": "Organization not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

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

            # Build next / previous URLs (preserve org_id)
            base_url = request.build_absolute_uri(request.path)

            next_offset = offset + limit
            next_url = (
                f"{base_url}?org_id={org_id}&limit={limit}&offset={next_offset}"
                if next_offset < total_count else None
            )

            prev_offset = offset - limit
            previous_url = (
                f"{base_url}?org_id={org_id}&limit={limit}&offset={max(prev_offset, 0)}"
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
        except Exception as e:
            return Response({"error": "An unexpected error occurred while fetching agents.", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
        except Exception as e:
             return Response({"error": "An unexpected error occurred retrieving the agent.", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
        except Exception as e:
            return Response({"error": "An unexpected error occurred updating the agent.", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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


class AgentSettingsDetailAPI(APIView):

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_agent(self, agent_id, user_profile):
        """Verify agent exists and user has access"""
        try:
            agent = Agent.objects.get(id=agent_id)
        except Agent.DoesNotExist:
            return None, "not_found"
        
        member = OrganizationMember.objects.filter(
            user=user_profile,
            organization=agent.organization
        ).first()
        
        if not member:
            return None, "no_permission"
        
        return agent, None

    def get(self, request, agent_id):
        """Get agent settings by agent_id"""
        try:
            agent, error = self.get_agent(agent_id, request.user.profile)
            
            if error == "not_found":
                return Response(
                    {"error": "Agent not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            if error == "no_permission":
                return Response(
                    {"error": "You do not have permission to access this agent"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            try:
                settings = AgentSettings.objects.get(agent=agent)
                serializer = AgentSettingsSerializer(settings)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except AgentSettings.DoesNotExist:
                return Response(
                    {"error": "Agent settings not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
        except Exception as e:
            return Response(
                {"error": "An unexpected error occurred", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def patch(self, request, agent_id):
        """Update agent settings by agent_id"""
        try:
            agent, error = self.get_agent(agent_id, request.user.profile)
            
            if error == "not_found":
                return Response(
                    {"error": "Agent not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            if error == "no_permission":
                return Response(
                    {"error": "You do not have permission to access this agent"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if user has admin/owner role
            member = OrganizationMember.objects.filter(
                user=request.user.profile,
                organization=agent.organization,
                role__in=[OrganizationMember.OWNER, OrganizationMember.ADMIN]
            ).first()
            
            if not member:
                return Response(
                    {"error": "You do not have permission to update agent settings"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            try:
                settings = AgentSettings.objects.get(agent=agent)
            except AgentSettings.DoesNotExist:
                return Response(
                    {"error": "Agent settings not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            serializer = AgentSettingsSerializer(settings, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response(
                {"error": "An unexpected error occurred", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

