from django.contrib.auth.models import User
from accounts.models import Organization, OrganizationMember
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

        # Determine if this email belongs to an existing user
        is_existing_user = User.objects.filter(email__iexact=email).exists()

        # Send invitation email
        try:
            email_type = "organization_invitation:invite-existing" if is_existing_user else "organization_invitation:invite"
            SendUserEmail(
                to_email=new_member.email,
                email_type=email_type,
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


def _serialize_organization(org, role=None, membership=None):
    """Build full org info dict with optional role and membership details."""
    data = {
        "id": str(org.id),
        "name": org.name,
        "created_at": org.created_at.isoformat() if org.created_at else None,
        "updated_at": org.updated_at.isoformat() if org.updated_at else None,
        "owner": None,
    }
    if org.owner:
        data["owner"] = {
            "id": org.owner.id,
            "email": org.owner.user.email if org.owner.user else None,
            "name": org.owner.user.get_full_name() if org.owner.user else None,
        }
    if role is not None:
        data["role"] = role
    if membership:
        data["invitation_accepted"] = membership.invitation_accepted
        data["added_to_organization"] = membership.added_to_organization.isoformat() if membership.added_to_organization else None
    return data


class UserOrganizationsAPI(APIView):
    """GET /organizations/ - Returns current org info and all orgs the user is a member of."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = request.user.profile
        current_org = profile.organization

        # Current organization (full info)
        membership = OrganizationMember.objects.filter(
            organization=current_org, user=profile
        ).first()
        current_org_role = membership.role if membership else (
            OrganizationMember.OWNER if current_org.owner_id == profile.id else None
        )
        if current_org.owner_id == profile.id and not current_org_role:
            current_org_role = OrganizationMember.OWNER

        organization = _serialize_organization(
            current_org, role=current_org_role, membership=membership
        )

        # All organizations user is a member of
        all_organizations = []
        seen_org_ids = set()

        for m in OrganizationMember.objects.filter(user=profile).select_related("organization"):
            org_id = str(m.organization_id)
            if org_id not in seen_org_ids:
                seen_org_ids.add(org_id)
                all_organizations.append(_serialize_organization(m.organization, role=m.role, membership=m))

        for org in Organization.objects.filter(owner=profile):
            org_id = str(org.id)
            if org_id not in seen_org_ids:
                seen_org_ids.add(org_id)
                all_organizations.append(_serialize_organization(org, role=OrganizationMember.OWNER))

        return Response({
            "organization": organization,
            "all_organizations": all_organizations,
        })


class OrganizationMembersAPI(APIView):
    """
    GET /auth/organization/members/ - List all members of the current user's organization.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = request.user.profile
        organization = profile.organization

        members_qs = OrganizationMember.objects.filter(
            organization=organization
        ).select_related("user__user")

        members = []
        for member in members_qs:
            user_profile = member.user  # Profile or None
            user_obj = user_profile.user if user_profile else None

            members.append({
                "id": member.id,
                "email": member.email,
                "role": member.role,
                "invitation_accepted": member.invitation_accepted,
                "added_to_organization": member.added_to_organization.isoformat() if member.added_to_organization else None,
                "created_at": member.created_at.isoformat() if member.created_at else None,
                "updated_at": member.updated_at.isoformat() if member.updated_at else None,
                "user": {
                    "id": user_obj.id if user_obj else None,
                    "name": user_obj.get_full_name() if user_obj else None,
                    "email": user_obj.email if user_obj else None,
                } if user_obj else None,
            })

        owner_profile = organization.owner
        owner_user = owner_profile.user if owner_profile else None

        return Response({
            "organization": {
                "id": str(organization.id),
                "name": organization.name,
                "owner": {
                    "id": owner_user.id if owner_user else None,
                    "name": owner_user.get_full_name() if owner_user else None,
                    "email": owner_user.email if owner_user else None,
                } if owner_user else None,
            },
            "members": members,
        })


class OrganizationMemberDeleteAPI(APIView):
    """
    DELETE /auth/organization/members/<int:member_id>/ - Revoke a member's access.

    Rules:
    - Only an OWNER of the organization can delete members.
    - OWNER members cannot be deleted.
    - You can only delete members from your own organization.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, member_id):
        profile = request.user.profile
        organization = profile.organization

        # Check that requester is an owner of this organization
        is_owner = (
            organization.owner_id == profile.id
            or OrganizationMember.objects.filter(
                organization=organization,
                user=profile,
                role=OrganizationMember.OWNER,
                invitation_accepted=True,
            ).exists()
        )

        if not is_owner:
            return Response(
                {"error": "Only organization owners can revoke member access"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Find the member in this organization
        try:
            member = OrganizationMember.objects.get(id=member_id, organization=organization)
        except OrganizationMember.DoesNotExist:
            return Response(
                {"error": "Member not found in your organization"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Never allow deleting owners
        if member.role == OrganizationMember.OWNER:
            return Response(
                {"error": "Owner cannot be removed from the organization"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        member.delete()

        return Response(
            {"message": "Member access revoked successfully"},
            status=status.HTTP_200_OK,
        )
