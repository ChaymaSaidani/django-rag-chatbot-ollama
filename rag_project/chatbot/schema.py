import graphene
from graphene_django import DjangoObjectType

from chatbot.tasks import generate_chat_response
from .models import Document, ChatSession, ChatMessage


class DocumentType(DjangoObjectType):
    class Meta:
        model = Document
        fields = "__all__"

class ChatSessionType(DjangoObjectType):
    class Meta:
        model = ChatSession
        fields = "__all__"

class ChatMessageType(DjangoObjectType):
    class Meta:
        model = ChatMessage
        fields = "__all__"


class Query(graphene.ObjectType):
    documents = graphene.List(DocumentType)
    chat_sessions = graphene.List(ChatSessionType)
    chat_messages = graphene.List(ChatMessageType, session_id=graphene.Int(required=True))

    def resolve_documents(self, info):
        user = info.context.user
        if not user.is_authenticated:
            return Document.objects.none()
        return Document.objects.filter(owner=user)

    def resolve_chat_sessions(self, info):
        user = info.context.user
        if not user.is_authenticated:
            return ChatSession.objects.none()
        return ChatSession.objects.filter(user=user)

    def resolve_chat_messages(self, info, session_id):
        user = info.context.user
        if not user.is_authenticated:
            return ChatMessage.objects.none()
        return ChatMessage.objects.filter(session__user=user, session_id=session_id)


class CreateDocument(graphene.Mutation):
    class Arguments:
        title = graphene.String(required=True)
        file = graphene.String(required=True)  

    document = graphene.Field(DocumentType)

    @classmethod
    def mutate(cls, root, info, title, file):
        user = info.context.user
        if not user or not user.is_authenticated:
            raise Exception("Authentication required")

       
        document = Document.objects.create(title=title, owner=user)
        return CreateDocument(document=document)
    
class CreateChatMessage(graphene.Mutation):
    class Arguments:
        session_id = graphene.Int(required=True)
        message = graphene.String(required=True)

    chat_message = graphene.Field(ChatMessageType)

    def mutate(self, info, session_id, message):
        user = info.context.user
        if not user.is_authenticated:
            raise Exception("Authentication required")

        try:
            session = ChatSession.objects.get(id=session_id, user=user)
        except ChatSession.DoesNotExist:
            raise Exception("Chat session not found")

        
        chat_message = ChatMessage.objects.create(
            session=session,
            message=message,
            is_user=True
        )

        
        generate_chat_response.delay(session_id, chat_message.id)

        return CreateChatMessage(chat_message=chat_message)

class Mutation(graphene.ObjectType):
    create_document = CreateDocument.Field()
    create_chat_message = CreateChatMessage.Field()


schema = graphene.Schema(query=Query, mutation=Mutation)
