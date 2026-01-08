# apps/content/urls.py

from django.urls import path
from .views import IngestContentAPIView, ChatListAPIView, RAGChatAPIView

urlpatterns = [
    path("ingest/", IngestContentAPIView.as_view(), name="ingest-content"),
    path("sessions/", ChatListAPIView.as_view(), name="chat-sessions"),
    path("rag/", RAGChatAPIView.as_view(), name="rag-chat"),
]
