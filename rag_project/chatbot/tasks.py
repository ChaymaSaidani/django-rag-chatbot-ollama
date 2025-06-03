from celery import shared_task
import os
import numpy as np
import faiss
import pickle
from django.conf import settings

from .models import ChatMessage, ChatSession, Document, Embedding

from langchain_ollama import OllamaEmbeddings
from langchain_community.llms import Ollama
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from chatbot.models import ChatMessage, ChatSession, Document, Embedding


@shared_task(bind=True)
def process_document(self, document_id):
    """Process document and generate embeddings."""
    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        print(f"Document with id {document_id} does not exist")
        return

    try:
        loader_class = {
            'pdf': PyPDFLoader,
            'docx': Docx2txtLoader,
            'txt': TextLoader
        }.get(document.file_type)

        if loader_class is None:
            raise ValueError(f"Unsupported file type: {document.file_type}")

        loader = loader_class(document.file.path)

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_documents(loader.load())

        if not chunks:
            raise ValueError("No text chunks were created from the document.")

        embeddings_model = OllamaEmbeddings(model="mistral")
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

        # We no longer save individual FAISS indices for each document
        # since we'll build a unified index at query time
        
        document.processed = True
        document.save()
        return f"Processed {document.title} ({len(chunks)} chunks)"

    except Exception as e:
        document.processed = False
        document.save()
        raise self.retry(exc=e, countdown=60)


@shared_task
def generate_chat_response(session_id, message_id):
    """Generate AI response using RAG with Ollama."""
    try:
        message = ChatMessage.objects.get(id=message_id)
        session = ChatSession.objects.get(id=session_id)

        embeddings_model = OllamaEmbeddings(model="mistral")
        query_embedding = embeddings_model.embed_query(message.message)

        # Collect all embeddings for this user's documents
        embeddings_data = []
        all_embeddings = []

        for doc in Document.objects.filter(owner=session.user, processed=True):
            for emb in Embedding.objects.filter(document=doc):
                embedding = pickle.loads(emb.embedding)
                all_embeddings.append(embedding)
                embeddings_data.append({
                    'text': emb.text_chunk,
                    'embedding': embedding,
                    'document': doc.title,
                    'embedding_id': emb.id
                })

        if not all_embeddings:
            return "Please upload and process documents first."

        # Create FAISS index
        dimension = len(all_embeddings[0])
        np_embeddings = np.array(all_embeddings).astype('float32')

        n_vectors = len(np_embeddings)
        nlist = min(100, max(1, int(n_vectors ** 0.5)))

        quantizer = faiss.IndexFlatL2(dimension)
        index = faiss.IndexIVFFlat(quantizer, dimension, nlist, faiss.METRIC_L2)

        if not index.is_trained:
            index.train(np_embeddings)
        index.add(np_embeddings)

        k = min(10, len(np_embeddings))  # Increased from 3 to 10
        _, indices_found = index.search(np.array([query_embedding]).astype('float32'), k=k)

        # Diversity filtering: include only one chunk per document
        seen_docs = set()
        selected_chunks = []
        for i in indices_found[0]:
            if i >= len(embeddings_data):
                continue
            doc_title = embeddings_data[i]['document']
            if doc_title not in seen_docs:
                selected_chunks.append(embeddings_data[i])
                seen_docs.add(doc_title)
            if len(selected_chunks) >= 3:  # limit to 3 diverse chunks
                break

        context = "\n\n".join(
            f"From {chunk['document']}:\n{chunk['text']}"
            for chunk in selected_chunks
        )

        llm = Ollama(model="mistral")
        prompt = f"""Use the following context to answer the user's question.
If you don't know the answer, just say you don't know, don't try to make up an answer.

Context:
{context}

Question: {message.message}"""

        response_text = llm.invoke(prompt)

        response_message = ChatMessage.objects.create(
            session=session,
            message=response_text,
            is_user=False
        )

        for chunk in selected_chunks:
            try:
                response_message.references.add(
                    Embedding.objects.get(id=chunk['embedding_id'])
                )
            except Embedding.DoesNotExist:
                continue

        return response_message.message

    except Exception as e:
        return f"Error generating response: {str(e)}"
