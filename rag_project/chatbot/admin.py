from django.contrib import admin
from .models import Document, ChatSession, ChatMessage

admin.site.register(Document)
admin.site.register(ChatSession)
admin.site.register(ChatMessage)