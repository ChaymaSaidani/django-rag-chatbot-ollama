import graphene
from graphene_django import DjangoObjectType
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

class Mutation(graphene.ObjectType):
    create_document = CreateDocument.Field()


schema = graphene.Schema(query=Query, mutation=Mutation)
