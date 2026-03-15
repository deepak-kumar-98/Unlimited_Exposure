from django.contrib import admin
from .models import IngestedContent, Agent, AgentSettings, ChatSession, ChatMessage, SystemSettings

admin.site.register(IngestedContent)
admin.site.register(Agent)
admin.site.register(AgentSettings)
admin.site.register(ChatSession)
admin.site.register(ChatMessage)
admin.site.register(SystemSettings)