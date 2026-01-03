from django.urls import path
from accounts.views import LoginView, RegisterUser
from accounts.views import VerifyAccount
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('register/', RegisterUser.as_view()),
    path('verify-email/', VerifyAccount.as_view()),
    path('login/', LoginView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),


]
