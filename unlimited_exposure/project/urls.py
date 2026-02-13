# apps/content/urls.py

from django.urls import path
from .views import ActiveSystemPromptAPIView, ChatMessagesAPIView, CreateSystemSettingsAPIView, GenerateSystemPromptAPIView, IngestContentAPIView, ChatListAPIView, PreviewSystemPromptAPIView, RAGChatAPIView, KnowledgeBaseAPIView, KnowledgeBaseDeleteAPIView
from .AI.agent_apis import AgentAPI, AgentDetailAPI

urlpatterns = [
    path("agents/", AgentAPI.as_view(), name="agents"),
    path("agents/<uuid:id>/", AgentDetailAPI.as_view(), name="agent-detail"),
    path("ingest/", IngestContentAPIView.as_view(), name="ingest-content"),
    path("knowledge-base/", KnowledgeBaseAPIView.as_view(), name="knowledge-base"),
    path("knowledge-base/<uuid:id>/", KnowledgeBaseDeleteAPIView.as_view(), name="delete-knowledge-base"),
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

