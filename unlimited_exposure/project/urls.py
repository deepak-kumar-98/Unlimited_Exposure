# apps/content/urls.py

from django.urls import path
from .views import ActiveSystemPromptAPIView, ChatMessagesAPIView, CreateSystemSettingsAPIView, GenerateSystemPromptAPIView, IngestContentAPIView, ChatListAPIView, PreviewSystemPromptAPIView, RAGChatAPIView, KnowledgeBaseAPIView

urlpatterns = [
    path("ingest/", IngestContentAPIView.as_view(), name="ingest-content"),
    path("knowledge-base/", KnowledgeBaseAPIView.as_view(), name="knowledge-base"),
    path("sessions/", ChatListAPIView.as_view(), name="chat-sessions"),
    path("rag/", RAGChatAPIView.as_view(), name="rag-chat"),
    # path("system-prompt/", CreateSystemSettingsAPIView.as_view(), name="create-system-prompt"),
    path(
        "chats/<uuid:chat_id>/",
        ChatMessagesAPIView.as_view(),
        name="chat-messages"
    ),
    path("system-prompt/preview/", PreviewSystemPromptAPIView.as_view()),
    path("system-prompt/", GenerateSystemPromptAPIView.as_view()),
    path("system-prompt/active/", ActiveSystemPromptAPIView.as_view()),
]

