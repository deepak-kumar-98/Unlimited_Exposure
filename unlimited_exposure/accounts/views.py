from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token

from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.serializers import UserSerializer, LoginSerializer
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


class VerifyAccount(APIView):
    """
    Email verification:
    - Activate user
    - Create profile
    - Create organization
    - Assign OWNER role
    """

    def get(self, request):
        token_key = request.GET.get('token')

        if not token_key:
            return Response(
                {'error': 'Token is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = Token.objects.get(key=token_key)
            user = token.user

            if user.is_active:
                return Response(
                    {'error': MESSAGES.get('error.email-verified')},
                    status=status.HTTP_409_CONFLICT,
                )

            # 1️⃣ Activate user
            user.is_active = True
            user.save()

            # 2️⃣ Create profile
            profile, _ = Profile.objects.get_or_create(user=user)

            # 3️⃣ Create organization (FIX HERE)
            organization, _ = Organization.objects.get_or_create(
                owner=profile,  # ✅ FIXED
                name=f"{user.first_name}'s Organization",
            )

            # 4️⃣ Assign OWNER role
            OrganizationMember.objects.get_or_create(
                user=profile,
                organization=organization,
                email=user.email,
                role=OrganizationMember.OWNER,
                invitation_accepted=True,
            )

            # 5️⃣ Link profile → organization
            profile.created_organization = organization
            profile.save()

            return Response(
                {'message': MESSAGES.get('success.email-verified')},
                status=status.HTTP_200_OK,
            )

        except Token.DoesNotExist:
            return Response(
                {'error': MESSAGES.get('verify-email.verification-link-expired')},
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
                {'error': MESSAGES.get('chat.user-not-found')},
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
