"""
URL configuration for rag_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""


from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedDefaultRouter
from chatbot.views import DocumentViewSet, ChatSessionViewSet, ChatMessageViewSet, CustomAuthToken, login_view, chat_view, DRFAuthGraphQLView, index
from chatbot.schema import schema

router = DefaultRouter()
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'chat-sessions', ChatSessionViewSet, basename='chatsession')

sessions_router = NestedDefaultRouter(router, r'chat-sessions', lookup='session')
sessions_router.register(r'messages', ChatMessageViewSet, basename='session-messages')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/', include(sessions_router.urls)),
    path('api-token-auth/', CustomAuthToken.as_view(), name='api_token_auth'),
    path('login/', login_view, name='login'),
    path('chat/<int:session_id>/', chat_view, name='chat_view'),
    path("graphql/", DRFAuthGraphQLView.as_view(graphiql=True, schema=schema)),
    path('', index, name='index'),
]
