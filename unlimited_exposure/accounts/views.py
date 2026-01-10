from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str

from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.serializers import UserSerializer, LoginSerializer, ForgotPasswordSerializer, ResetPasswordSerializer
from accounts.models import Profile, Organization, OrganizationMember
from accounts.senduseremail import SendUserEmail
from accounts.messages import get_response_messages

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

        if User.objects.filter(email=email).exists():
            return Response(
                {'error': MESSAGES.get('sign-up.user-exist', 'User already exists')},
                status=status.HTTP_409_CONFLICT,
            )

        user = serializer.save()
        user.is_active = False
        user.save()

        token, _ = Token.objects.get_or_create(user=user)

        SendUserEmail(
            to_email=user.email,
            email_type='auth:account-activate',
            token=f'?token={token.key}',
            username=user.get_full_name(),
        )

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
    - Activate user
    - Create organization
    - Create profile (linked to org)
    - Assign OWNER role
    """

    def get(self, request):
        token_key = request.GET.get("token")

        if not token_key:
            return Response(
                {"error": "Token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = Token.objects.get(key=token_key)
            user = token.user

            if user.is_active:
                return Response(
                    {"error": MESSAGES.get("error.email-verified")},
                    status=status.HTTP_409_CONFLICT,
                )

            # 1️⃣ Activate user
            user.is_active = True
            user.save()

            # 2️⃣ Create organization FIRST (owner temporarily NULL)
            organization = Organization.objects.create(
                name=f"{user.first_name or user.email}'s Organization"
            )

            # 3️⃣ Create profile linked to organization
            profile = Profile.objects.create(
                user=user,
                organization=organization
            )

            # 4️⃣ Assign owner now that profile exists
            organization.owner = profile
            organization.save(update_fields=["owner"])

            # 5️⃣ Assign OWNER role
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

        except Token.DoesNotExist:
            return Response(
                {"error": MESSAGES.get("verify-email.verification-link-expired")},
                status=status.HTTP_404_NOT_FOUND,
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

        return Response({
            "id": request.user.id,
            "email": request.user.email,
            "name": request.user.get_full_name(),
            "organization": {
                "id": org.id,
                "name": org.name
            }
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
            SendUserEmail(
                to_email=user.email,
                email_type='auth:Forgot',
                token=f"{uid}/{token}",
                username=user.get_full_name()
            )

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
