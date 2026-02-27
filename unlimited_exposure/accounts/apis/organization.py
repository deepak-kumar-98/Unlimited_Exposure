from accounts.models import OrganizationMember
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from accounts.serializers import AddMembersSerializer
from accounts.senduseremail import SendUserEmail
from accounts.models import InvitationToken

class AddMemberToOrg(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, org_id):

        serializer = AddMembersSerializer(data=request.data)

        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user is part of the organization
        is_member = OrganizationMember.objects.filter(organization=request.user.profile.organization, user=request.user.profile, role=OrganizationMember.OWNER).exists()
        
        if not is_member:
            return Response({'error': 'You must be part of the organization to add members'}, status=403)
        
        
        # Check if user is already a member
        email = serializer.validated_data.get('email')
        if OrganizationMember.objects.filter(organization=request.user.profile.organization, email=email).exists():
            return Response({'error': 'User is already a member'}, status=400)
        
        # Create new member
        new_member = OrganizationMember.objects.create(
            organization=request.user.profile.organization,
            email=serializer.validated_data.get('email'),
            role=serializer.validated_data.get('role')
        )
        
        # Create or get invitation token

        try:
            invite_token = InvitationToken.objects.get(organization_member_id=new_member.id)
        except InvitationToken.DoesNotExist:
            invite_token = InvitationToken.objects.create(
                inviter=request.user,
                organization_member_id=new_member.id,
                invitee_email=new_member.email,
            )

        # Send invitation email
        try:
            SendUserEmail(
                to_email=new_member.email,
                email_type="organization_invitation:invite",
                username=new_member.email.split('@')[0],
                Invitation_token=str(invite_token.id),
                Extra_info={
                    "organization_name": request.user.profile.organization.name,
                    "invited_by": request.user.username,
                    "organization_role": new_member.role
                }
            )

        except Exception as e:
            return Response(
                {
                    'error': 'Somthing went wrong',
                    'invitation_token': str(invite_token.id)
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                'message': 'Member added successfully'
            },
            status=status.HTTP_201_CREATED,
        )



class AcceptInvitationAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Accept invitation (for existing users who are logged in)"""
        invitation_token_id = request.data.get('invitation_token')

        if not invitation_token_id:
            return Response({'error': 'Invitation token is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Case 1: Check if token exists
        try:
            invite_token = InvitationToken.objects.get(id=invitation_token_id)
        except InvitationToken.DoesNotExist:
            return Response({'error': 'Invalid invitation token'}, status=status.HTTP_404_NOT_FOUND)

        # Case 2: Check if token is expired
        if invite_token.is_expired():
            return Response({'error': 'Invitation token has expired'}, status=status.HTTP_400_BAD_REQUEST)

        # Case 3: Get organization member
        try:
            org_member = OrganizationMember.objects.get(id=invite_token.organization_member_id)
        except OrganizationMember.DoesNotExist:
            return Response({'error': 'Organization member not found'}, status=status.HTTP_404_NOT_FOUND)

        # Case 4: Check if already accepted
        if org_member.invitation_accepted:
            return Response({'error': 'Invitation already accepted'}, status=status.HTTP_400_BAD_REQUEST)

        # Case 5: Verify email matches
        if org_member.email != request.user.email:
            return Response({'error': 'Email mismatch. This invitation is for a different email'}, status=status.HTTP_403_FORBIDDEN)

        # Case 6: Link user profile to organization member and accept invitation
        org_member.user = request.user.profile
        org_member.invitation_accepted = True
        org_member.save()

        return Response({
            'message': 'Invitation accepted successfully',
            'organization': org_member.organization.name,
            'role': org_member.role
        }, status=status.HTTP_200_OK)
