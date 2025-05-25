from celery import shared_task
import os
import numpy as np
import faiss
import pickle
import openai
from django.conf import settings

# Updated LangChain imports
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings  # Correct import for OpenAI embeddings

# Import models inside functions to avoid circular imports

@shared_task(bind=True)
def process_document(self, document_id):
    """Process document and generate embeddings"""
    from .models import Document, Embedding
    
    try:
        document = Document.objects.get(id=document_id)
        
        # Document loading
        loader = {
            'pdf': PyPDFLoader,
            'docx': Docx2txtLoader,
            'txt': TextLoader
        }[document.file_type](document.file.path)
        
        # Text splitting
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        chunks = text_splitter.split_documents(loader.load())
        
        # Initialize embeddings model
        embeddings_model = (
            OpenAIEmbeddings(openai_api_key=settings.OPENAI_API_KEY)
            if getattr(settings, 'OPENAI_API_KEY', None)
            else HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        )
        
        # Process chunks
        embeddings = []
        for i, chunk in enumerate(chunks):
            embedding = embeddings_model.embed_query(chunk.page_content)
            embeddings.append(embedding)
            
            Embedding.objects.create(
                document=document,
                embedding=pickle.dumps(embedding),
                text_chunk=chunk.page_content,
                chunk_index=i
            )
        
        # Create and save FAISS index
        dimension = len(embeddings[0])
        index = faiss.IndexFlatL2(dimension)
        index.add(np.array(embeddings).astype('float32'))
        
        os.makedirs(settings.FAISS_INDEX_PATH, exist_ok=True)
        faiss.write_index(index, os.path.join(settings.FAISS_INDEX_PATH, f'doc_{document_id}.index'))
        
        document.processed = True
        document.save()
        return f"Processed {document.title} ({len(chunks)} chunks)"
    
    except Exception as e:
        document.processed = False
        document.save()
        raise self.retry(exc=e, countdown=60)

@shared_task
def generate_chat_response(session_id, message_id):
    """Generate AI response using RAG"""
    from .models import ChatMessage, ChatSession, Document, Embedding
    
    try:
        message = ChatMessage.objects.get(id=message_id)
        session = ChatSession.objects.get(id=session_id)
        
        # Initialize embeddings
        embeddings_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        # Load and merge FAISS indices
        indices = []
        embeddings_data = []
        
        for doc in Document.objects.filter(owner=session.user, processed=True):
            index_path = os.path.join(settings.FAISS_INDEX_PATH, f'doc_{doc.id}.index')
            if os.path.exists(index_path):
                indices.append(faiss.read_index(index_path))
                embeddings_data.extend([{
                    'text': emb.text_chunk,
                    'embedding': pickle.loads(emb.embedding),
                    'document': doc.title
                } for emb in Embedding.objects.filter(document=doc)])
        
        if not indices:
            return "Please upload and process documents first."
        
        # Merge indices if multiple exist
        merged_index = indices[0]
        for index in indices[1:]:
            faiss.merge_into(merged_index, index, shift_ids=True)
        
        # Semantic search
        query_embedding = embeddings_model.embed_query(message.message)
        _, indices = merged_index.search(np.array([query_embedding]).astype('float32'), k=3)
        
        # Build context
        context = "\n\n".join(
            f"From {embeddings_data[i]['document']}:\n{embeddings_data[i]['text']}"
            for i in indices[0]
        )
        
        # Generate response
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"Use this context:\n{context}"},
                {"role": "user", "content": message.message}
            ]
        )
        
        # Save response
        response_message = ChatMessage.objects.create(
            session=session,
            message=response.choices[0].message['content'],
            is_user=False
        )
        
        # Add references
        for i in indices[0]:
            response_message.references.add(
                Embedding.objects.get(
                    text_chunk=embeddings_data[i]['text'],
                    document__title=embeddings_data[i]['document']
                )
            )
        
        return response_message.message
    
    except Exception as e:
        return f"Error: {str(e)}"