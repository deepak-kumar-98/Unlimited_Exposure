from django.contrib.auth.models import User
from rest_framework.views import APIView
import uuid
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from accounts.models import InvitationToken
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.serializers import (
    UserSerializer, LoginSerializer, ForgotPasswordSerializer, 
    ResetPasswordSerializer, ProfileSerializer, TransactionSerializer,
    PlansAndFeatureSerializer
)
from accounts.models import Profile, Organization, OrganizationMember, PlansAndFeature, Transaction
from accounts.senduseremail import SendUserEmail
from accounts.messages import get_response_messages
from accounts.paypal_service import PayPalService

MESSAGES = get_response_messages()


class RegisterUser(APIView):
    """
    Signup:
    - Create inactive user
    - Send verification email
    """

    def post(self, request):
        serializer = UserSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {'error': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data['email'].lower()
        invitation_token = request.data.get('invitation_token')  # Get invitation token from request

        if User.objects.filter(email=email).exists():
            return Response(
                {'error': MESSAGES.get('sign-up.user-exist', 'User already exists')},
                status=status.HTTP_409_CONFLICT,
            )

        user = serializer.save()
        user.is_active = False
        user.save()

        token, _ = Token.objects.get_or_create(user=user)

        # Build token URL with invitation token if provided
        if invitation_token:
            token_url = f'?token={token.key}&invitation_token={invitation_token}'
        else:
            token_url = f'?token={token.key}'

        try:
            SendUserEmail(
                to_email=user.email,
                email_type='auth:account-activate',
                token=token_url,
                username=user.get_full_name(),
            )
        except Exception as e:
            # Non-blocking error logging
            print(f"Failed to send verification email: {e}")

        return Response(
            {'message': MESSAGES.get('success.account-created', 'Account created successfully')},
            status=status.HTTP_201_CREATED,
        )



# class VerifyAccount(APIView):
#     """
#     Email verification:
#     - Activate user
#     - Create profile
#     - Create organization
#     - Assign OWNER role
#     """

#     def get(self, request):
#         token_key = request.GET.get('token')

#         if not token_key:
#             return Response(
#                 {'error': 'Token is required'},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         try:
#             token = Token.objects.get(key=token_key)
#             user = token.user

#             if user.is_active:
#                 return Response(
#                     {'error': MESSAGES.get('error.email-verified', 'Email already verified')},
#                     status=status.HTTP_409_CONFLICT,
#                 )

#             # Activate user
#             user.is_active = True
#             user.save()

#             # Profile
#             profile, _ = Profile.objects.get_or_create(user=user)

#             # Organization
#             organization, _ = Organization.objects.get_or_create(
#                 owner=profile.id,
#                 name=f"{user.first_name}'s Organization",
#             )

#             # Organization member (OWNER)
#             OrganizationMember.objects.get_or_create(
#                 user=profile,
#                 organization=organization,
#                 email=user.email,
#                 role=OrganizationMember.OWNER,
#                 invitation_accepted=True,
#             )

#             profile.created_organization = organization
#             profile.save()

#             return Response(
#                 {'message': MESSAGES.get('success.email-verified', 'Email verified successfully')},
#                 status=status.HTTP_200_OK,
#             )

#         except Token.DoesNotExist:
#             return Response(
#                 {'error': MESSAGES.get('verify-email.verification-link-expired', 'Invalid token')},
#                 status=status.HTTP_404_NOT_FOUND,
#             )


# class VerifyAccount(APIView):
#     """
#     Email verification:
#     - Activate user
#     - Create profile
#     - Create organization
#     - Assign OWNER role
#     """

#     def get(self, request):
#         token_key = request.GET.get('token')

#         if not token_key:
#             return Response(
#                 {'error': 'Token is required'},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         try:
#             token = Token.objects.get(key=token_key)
#             user = token.user

#             if user.is_active:
#                 return Response(
#                     {'error': MESSAGES.get('error.email-verified')},
#                     status=status.HTTP_409_CONFLICT,
#                 )

#             # 1️⃣ Activate user
#             user.is_active = True
#             user.save()

#             # 2️⃣ Create profile
#             profile, _ = Profile.objects.get_or_create(user=user)

#             # 3️⃣ Create organization (FIX HERE)
#             organization, _ = Organization.objects.get_or_create(
#                 owner=profile,  # ✅ FIXED
#                 name=f"{user.first_name}'s Organization",
#             )

#             # 4️⃣ Assign OWNER role
#             OrganizationMember.objects.get_or_create(
#                 user=profile,
#                 organization=organization,
#                 email=user.email,
#                 role=OrganizationMember.OWNER,
#                 invitation_accepted=True,
#             )

#             # 5️⃣ Link profile → organization
#             profile.created_organization = organization
#             profile.save()

#             return Response(
#                 {'message': MESSAGES.get('success.email-verified')},
#                 status=status.HTTP_200_OK,
#             )

#         except Token.DoesNotExist:
#             return Response(
#                 {'error': MESSAGES.get('verify-email.verification-link-expired')},
#                 status=status.HTTP_404_NOT_FOUND,
#             )


class VerifyAccount(APIView):
    """
    Email verification:
    - Activate user (if activation token provided)
    - Accept invitation (if invitation token provided)
    - Both (if both tokens provided)
    """

    def validate_activation_token(self, token_key):
        """Validate and return user from activation token"""
        try:
            token = Token.objects.get(key=token_key)
            user = token.user
            
            if user.is_active:
                return None, {"error": MESSAGES.get("error.email-verified")}, status.HTTP_409_CONFLICT
            
            return user, None, None
        except Token.DoesNotExist:
            return None, {"error": MESSAGES.get("verify-email.verification-link-expired")}, status.HTTP_404_NOT_FOUND

    def validate_invitation_token(self, invitation_token_id, user_email=None):
        """Validate invitation token and return organization member"""
        try:
            invite_token = InvitationToken.objects.get(id=invitation_token_id)
            
            if invite_token.is_expired():
                return None, {"error": "Invitation token has expired"}, status.HTTP_400_BAD_REQUEST
            
            org_member = OrganizationMember.objects.get(id=invite_token.organization_member_id)
            
            if org_member.invitation_accepted:
                return None, {"error": "Invitation already accepted"}, status.HTTP_400_BAD_REQUEST
            
            if user_email and org_member.email != user_email:
                return None, {"error": "Email mismatch"}, status.HTTP_403_FORBIDDEN
            
            return org_member, None, None
        except (InvitationToken.DoesNotExist, OrganizationMember.DoesNotExist):
            return None, {"error": "Invalid invitation"}, status.HTTP_400_BAD_REQUEST

    def get(self, request):
        token_key = request.GET.get("token")
        invitation_token_id = request.GET.get("invitation_token")

        # Case 1: Both tokens provided (New user with invitation)
        if token_key and invitation_token_id:
            # Validate activation token
            user, error, error_status = self.validate_activation_token(token_key)
            if error:
                return Response(error, status=error_status)
            
            # Activate user
            user.is_active = True
            user.save()
            
            # Create user's own primary organization (same as normal registration)
            personal_org = Organization.objects.create(
                name=f"{user.first_name or user.email}'s Organization"
            )

            profile = Profile.objects.create(
                user=user,
                organization=personal_org
            )

            personal_org.owner = profile
            personal_org.save(update_fields=["owner"])

            # Make user OWNER of their own organization
            OrganizationMember.objects.create(
                user=profile,
                organization=personal_org,
                email=user.email,
                role=OrganizationMember.OWNER,
                invitation_accepted=True,
            )



            # Validate invitation token and link user to invited organization
            org_member, error, error_status = self.validate_invitation_token(invitation_token_id, user.email)
            if error:
                return Response(error, status=error_status)

            org_member.user = profile
            org_member.invitation_accepted = True
            org_member.save()
            
            return Response(
                {"message": "Email verified and invitation accepted successfully"},
                status=status.HTTP_200_OK,
            )
        
        # Case 2: Only activation token (Normal registration)
        elif token_key:
            # Validate activation token
            user, error, error_status = self.validate_activation_token(token_key)
            if error:
                return Response(error, status=error_status)
            
            # Activate user
            user.is_active = True
            user.save()
            
            # Create new organization
            organization = Organization.objects.create(
                name=f"{user.first_name or user.email}'s Organization"
            )
            
            # Create profile linked to organization
            profile = Profile.objects.create(
                user=user,
                organization=organization
            )
            
            # Assign owner
            organization.owner = profile
            organization.save(update_fields=["owner"])
            
            # Assign OWNER role
            OrganizationMember.objects.create(
                user=profile,
                organization=organization,
                email=user.email,
                role=OrganizationMember.OWNER,
                invitation_accepted=True,
            )


            
            return Response(
                {"message": MESSAGES.get("success.email-verified")},
                status=status.HTTP_200_OK,
            )
        
        # Case 3: Only invitation token (Existing user accepting invitation)
        elif invitation_token_id:
            # Validate invitation token
            org_member, error, error_status = self.validate_invitation_token(invitation_token_id)
            if error:
                return Response(error, status=error_status)
            
            # Check if user exists with invitee email
            try:
                user = User.objects.get(email=org_member.email)
                
                # Check if user is active
                if not user.is_active:
                    return Response(
                        {"error": "Please verify your email first before accepting invitation"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Check if user has profile
                if not hasattr(user, 'profile'):
                    return Response(
                        {"error": "User profile not found. Please complete registration first"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Link user profile to organization member
                org_member.user = user.profile
                org_member.invitation_accepted = True
                org_member.save()
                
                return Response({
                    "message": "Invitation accepted successfully",
                    "organization": org_member.organization.name,
                    "role": org_member.role
                }, status=status.HTTP_200_OK)
                
            except User.DoesNotExist:
                return Response(
                    {"error": "No account found with this email. Please register first to accept invitation"},
                    status=status.HTTP_404_NOT_FOUND
                )
        # Case 4: No tokens provided
        else:
            return Response(
                {"error": "Token or invitation_token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class LoginView(APIView):

    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {'error': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data['email'].lower()
        password = serializer.validated_data['password']

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response(
                {'error': MESSAGES.get('sign-in.user-not-found')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Email not verified
        if not user.is_active:
            return Response(
                {'error': MESSAGES.get('sign-in.email-verify-error')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        authenticated_user = authenticate(
            request,
            username=user.username,
            password=password,
        )

        if not authenticated_user:
            return Response(
                {'error': MESSAGES.get('sign-in.invalid-credentials')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh = RefreshToken.for_user(authenticated_user)

        return Response(
            {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            status=status.HTTP_200_OK,
        )




# class UserMeView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         user = request.user
#         return Response({
#             "id": user.id,
#             "email": user.email,
#             "name": user.get_full_name()
#         })

class UserMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = request.user.profile
        org = profile.organization
        serializer = ProfileSerializer(profile)

        return Response({
            "id": request.user.id,
            "email": request.user.email,
            "name": request.user.get_full_name(),
            "organization": {
                "id": str(org.id),
                "name": org.name
            },
            "profile": serializer.data
        })


class ForgotPasswordView(APIView):
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        user = User.objects.filter(email__iexact=email).first()

        if user:
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Send email
            try:
                SendUserEmail(
                    to_email=user.email,
                    email_type='auth:Forgot',
                    token=f"{uid}/{token}",
                    username=user.get_full_name()
                )
            except Exception as e:
                print(f"Failed to send reset email: {e}")

        # Always return success to prevent email enumeration
        return Response(
            {'message': MESSAGES.get('forgot-password.password-reset-email')},
            status=status.HTTP_200_OK
        )


class ResetPasswordView(APIView):
    def post(self, request, uidb64, token):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'error': 'Invalid link'}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({'error': 'Invalid or expired token'}, status=status.HTTP_400_BAD_REQUEST)

        serializer.save(user)
        return Response({'message': 'Password has been reset successfully'}, status=status.HTTP_200_OK)


class CreatePayPalOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan_id = request.data.get("plan_id")
        if not plan_id:
            return Response({"error": "plan_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            plan = PlansAndFeature.objects.get(id=plan_id)
        except (PlansAndFeature.DoesNotExist, ValueError):
            return Response({"error": "Invalid plan_id"}, status=status.HTTP_400_BAD_REQUEST)

        paypal_service = PayPalService()
        order = paypal_service.create_order(amount=plan.price, currency="USD")
        
        if not order:
            return Response({"error": "Failed to create PayPal order"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Create Transaction record
        Transaction.objects.create(
            profile=request.user.profile,
            plan=plan,
            paypal_order_id=order["id"],
            amount=plan.price,
            status=Transaction.PENDING
        )

        return Response(order, status=status.HTTP_201_CREATED)


class CapturePayPalOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get("order_id")
        if not order_id:
            return Response({"error": "order_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            transaction = Transaction.objects.get(paypal_order_id=order_id)
        except Transaction.DoesNotExist:
            return Response({"error": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND)

        paypal_service = PayPalService()
        capture = paypal_service.capture_order(order_id)
        
        if not capture:
            transaction.status = Transaction.FAILED
            transaction.save()
            return Response({"error": "Failed to capture PayPal order"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Check if payment was successful
        if capture.get("status") == "COMPLETED":
            transaction.status = Transaction.COMPLETED
            transaction.save()
            
            # Extract billing address from PayPal response
            payer = capture.get("payer", {})
            address_obj = payer.get("address", {})
            billing_address = ""
            if address_obj:
                address_parts = [
                    address_obj.get("address_line_1"),
                    address_obj.get("address_line_2"),
                    address_obj.get("admin_area_2"), # City
                    address_obj.get("admin_area_1"), # State
                    address_obj.get("postal_code"),
                    address_obj.get("country_code")
                ]
                billing_address = ", ".join([p for p in address_parts if p])

            # Update user profile subscription, limits, and billing address
            profile = transaction.profile
            plan = transaction.plan
            profile.update_subscription(plan, billing_address=billing_address)
            
            return Response({"message": "Payment captured and subscription updated", "capture": capture}, status=status.HTTP_200_OK)
        else:
            transaction.status = Transaction.FAILED
            transaction.save()
            return Response({"error": "Payment not completed", "capture": capture}, status=status.HTTP_400_BAD_REQUEST)


class CancelPayPalOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get("order_id")
        if not order_id:
            return Response({"error": "order_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            transaction = Transaction.objects.get(
                paypal_order_id=order_id, 
                profile=request.user.profile
            )
        except Transaction.DoesNotExist:
            return Response({"error": "Transaction not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)

        if transaction.status == Transaction.PENDING:
            transaction.status = Transaction.CANCELLED
            transaction.save()
            return Response({"message": "Transaction cancelled successfully"}, status=status.HTTP_200_OK)
        
        return Response(
            {"error": f"Cannot cancel transaction with status: {transaction.status}"}, 
            status=status.HTTP_400_BAD_REQUEST
        )


class BillingHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        transactions = Transaction.objects.filter(profile=request.user.profile).order_by('-created_at')
        serializer = TransactionSerializer(transactions, many=True)
        
        # Include all available plans
        plans = PlansAndFeature.objects.all()
        plans_serializer = PlansAndFeatureSerializer(plans, many=True)
        
        return Response({
            "history": serializer.data,
            "available_plans": plans_serializer.data
        }, status=status.HTTP_200_OK)
