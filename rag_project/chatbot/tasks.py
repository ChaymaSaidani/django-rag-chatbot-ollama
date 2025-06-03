from celery import shared_task
import os
import numpy as np
import faiss
import pickle
from django.conf import settings

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

        # Adapt cluster count (nlist)
        dimension = len(embeddings[0])
        np_embeddings = np.array(embeddings).astype('float32')

        n_vectors = len(np_embeddings)
        nlist = min(100, n_vectors)  # cap at 100, but can't be > n_vectors
        if nlist < 1:
            nlist = 1

        quantizer = faiss.IndexFlatL2(dimension)
        index = faiss.IndexIVFFlat(quantizer, dimension, nlist, faiss.METRIC_L2)
        index.train(np_embeddings)
        index.add(np_embeddings)

        os.makedirs(settings.FAISS_INDEX_PATH, exist_ok=True)
        index_path = os.path.join(settings.FAISS_INDEX_PATH, f'doc_{document_id}.index')
        faiss.write_index(index, index_path)

        document.processed = True
        document.save()
        return f"Processed {document.title} ({n_vectors} chunks)"

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

        indices = []
        embeddings_data = []

        for doc in Document.objects.filter(owner=session.user, processed=True):
            index_path = os.path.join(settings.FAISS_INDEX_PATH, f'doc_{doc.id}.index')
            if os.path.exists(index_path):
                try:
                    idx = faiss.read_index(index_path)
                    indices.append(idx)
                    embeddings_data.extend([
                        {
                            'text': emb.text_chunk,
                            'embedding': pickle.loads(emb.embedding),
                            'document': doc.title
                        }
                        for emb in Embedding.objects.filter(document=doc)
                    ])
                except Exception as e:
                    return f"Error reading index for document {doc.id}: {str(e)}"

        if not indices:
            return "Please upload and process documents first."

        # Merge indices (IVF only)
        merged_index = indices[0]
        for idx in indices[1:]:
            try:
                faiss.merge_into(merged_index, idx, shift_ids=True)
            except Exception as e:
                return f"Error merging indices: {str(e)}"

        # Perform similarity search
        D, I = merged_index.search(np.array([query_embedding]).astype('float32'), k=3)

        context = "\n\n".join(
            f"From {embeddings_data[i]['document']}:\n{embeddings_data[i]['text']}"
            for i in I[0] if i >= 0 and i < len(embeddings_data)
        )

        llm = Ollama(model="mistral")
        prompt = f"Use the following context to answer the user's question.\n\nContext:\n{context}\n\nQuestion: {message.message}"
        response_text = llm.invoke(prompt)

        response_message = ChatMessage.objects.create(
            session=session,
            message=response_text,
            is_user=False
        )

        for i in I[0]:
            if i >= 0 and i < len(embeddings_data):
                response_message.references.add(
                    Embedding.objects.get(
                        text_chunk=embeddings_data[i]['text'],
                        document__title=embeddings_data[i]['document']
                    )
                )

        return response_message.message

    except Exception as e:
        return f"Error: {str(e)}"
