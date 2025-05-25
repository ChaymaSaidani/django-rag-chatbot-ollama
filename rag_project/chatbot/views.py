from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from chatbot.tasks import generate_chat_response
from .models import Document, ChatSession, ChatMessage
from .serializers import DocumentSerializer, ChatSessionSerializer, ChatMessageSerializer
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404

class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Document.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

class ChatSessionViewSet(viewsets.ModelViewSet):
    serializer_class = ChatSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class ChatMessageViewSet(viewsets.ModelViewSet):
    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        session_id = self.kwargs.get('session_id')
        return ChatMessage.objects.filter(session__user=self.request.user, session_id=session_id)

    def perform_create(self, serializer):
     session = get_object_or_404(ChatSession, id=self.kwargs.get('session_id'), user=self.request.user)
     message = serializer.save(session=session, is_user=True)
     generate_chat_response.delay(session.id, message.id)