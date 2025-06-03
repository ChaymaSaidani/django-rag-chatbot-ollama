from django.urls import reverse
import requests
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from .models import Document, ChatSession, ChatMessage
from .serializers import DocumentSerializer, ChatSessionSerializer, ChatMessageSerializer
from django.shortcuts import get_object_or_404
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from django.contrib.auth import authenticate, login
from dateutil import parser
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings
from graphene_django.views import GraphQLView
from rest_framework.authentication import TokenAuthentication


class DRFAuthGraphQLView(GraphQLView):
    def get_context(self, request):
        user_auth_tuple = TokenAuthentication().authenticate(request)
        if user_auth_tuple:
            request.user, request.auth = user_auth_tuple
        else:
            request.user = None
        return request
    
class CustomAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                         context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'email': user.email
        })

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            token, created = Token.objects.get_or_create(user=user)
            request.session['auth_token'] = token.key
            return redirect('index')  
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials'})
    
    return render(request, 'login.html')



class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Document.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def destroy(self, request, *args, **kwargs):
     instance = self.get_object()
     if instance.owner != request.user:
        return Response(status=status.HTTP_403_FORBIDDEN)
     self.perform_destroy(instance)
     return Response(status=status.HTTP_204_NO_CONTENT)

class ChatSessionViewSet(viewsets.ModelViewSet):
    serializer_class = ChatSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
     instance = self.get_object()
     if instance.user != request.user:
        return Response(status=status.HTTP_403_FORBIDDEN)
     self.perform_destroy(instance)
     return Response(status=status.HTTP_204_NO_CONTENT)

        

class ChatMessageViewSet(viewsets.ModelViewSet):
    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChatMessage.objects.filter(
            session__user=self.request.user,
            session_id=self.kwargs['session_pk']
        ).order_by('created_at')

    def perform_create(self, serializer):
        session = get_object_or_404(
            ChatSession,
            id=self.kwargs['session_pk'],
            user=self.request.user
        )
     
        message = serializer.save(session=session, is_user=True)

        
        from .tasks import generate_chat_response
        generate_chat_response.delay(session.id, message.id)

    def create(self, request, *args, **kwargs):
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


 
@login_required
def chat_view(request, session_id):
    auth_token = request.user.auth_token.key
    headers = {
        "Authorization": f"Token {auth_token}"
    }
    api_url = f"{settings.API_BASE_URL}/chat-sessions/{session_id}/"

    response = requests.get(api_url, headers=headers)

    if response.status_code == 404:
       
        return redirect('index')  

    if response.status_code != 200:
       
        return redirect('index')

    session = response.json()

    return render(request, "chat.html", {
        "session": session,
        "api_url": reverse('session-messages-list', args=[session_id]),
        "send_url": reverse('session-messages-list', args=[session_id]),
        "auth_token": auth_token
    })

@login_required
def index(request):
    auth_header = {"Authorization": f"Token {request.user.auth_token.key}"}

    if request.method == "POST":
        
        if request.POST.get("form_type") == "session":
            title = request.POST.get("title")
            if title:
                requests.post(
                    f"{settings.API_BASE_URL}/chat-sessions/",
                    data={"title": title},
                    headers=auth_header
                )

       
        elif request.POST.get("form_type") == "document":
            title = request.POST.get("doc_title")
            file = request.FILES.get("doc_file")
            if title and file:
                requests.post(
                    f"{settings.API_BASE_URL}/documents/",
                    data={"title": title},
                    files={"file": file},
                    headers=auth_header
                )

       
        elif "delete_session_id" in request.POST:
            session_id = request.POST.get("delete_session_id")
            if session_id:
                requests.delete(
                    f"{settings.API_BASE_URL}/chat-sessions/{session_id}/",
                    headers=auth_header
                )

      
        elif "delete_document_id" in request.POST:
            document_id = request.POST.get("delete_document_id")
            if document_id:
                requests.delete(
                    f"{settings.API_BASE_URL}/documents/{document_id}/",
                    headers=auth_header
                )

        return redirect("index")

    
    sessions_response = requests.get(
        f"{settings.API_BASE_URL}/chat-sessions/",
        headers=auth_header
    )
    chat_sessions = sessions_response.json() if sessions_response.status_code == 200 else []

    
    for session in chat_sessions:
        if "created_at" in session and session["created_at"]:
            session["created_at"] = parser.parse(session["created_at"])

  
    docs_response = requests.get(
        f"{settings.API_BASE_URL}/documents/",
        headers=auth_header
    )
    documents = docs_response.json() if docs_response.status_code == 200 else []

    
    for doc in documents:
        if "uploaded_at" in doc and doc["uploaded_at"]:
            doc["uploaded_at"] = parser.parse(doc["uploaded_at"])

    return render(request, "index.html", {
        "sessions": chat_sessions,
        "documents": documents
    })