from rest_framework import serializers
from .models import Document, ChatSession, ChatMessage
from django.core.exceptions import ValidationError

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id', 'title', 'file', 'file_type', 'uploaded_at', 'processed']
        read_only_fields = ['file_type', 'uploaded_at', 'processed']
    
    def validate_file(self, value):
        # File validation happens in model clean()
        return value

class ChatSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = ['id', 'title', 'created_at']

class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'session', 'message', 'is_user', 'created_at', 'references']
        read_only_fields = ['is_user', 'created_at', 'references']