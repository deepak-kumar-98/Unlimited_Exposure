from django.urls import path
from accounts.views import LoginView, RegisterUser
from accounts.views import VerifyAccount, UserMeView, ForgotPasswordView, ResetPasswordView
from accounts.apis.organization import AddMemberToOrg, AcceptInvitationAPI
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('register/', RegisterUser.as_view()),
    path('verify-email/', VerifyAccount.as_view()),
    path('login/', LoginView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', UserMeView.as_view(), name='user_me'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path('reset-password/<str:uidb64>/<str:token>/', ResetPasswordView.as_view(), name='reset_password'),
    path('organization/invite-member/<str:org_id>/', AddMemberToOrg.as_view(), name='invite_member'),
    path('organization/accept-invitation/', AcceptInvitationAPI.as_view(), name='accept_invitation'),
]
