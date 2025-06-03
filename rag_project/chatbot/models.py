import pickle
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

User = get_user_model()

class Document(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/')
    file_type = models.CharField(max_length=10, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)

    def clean(self):
        """Validate file type before saving"""
        valid_extensions = ['pdf', 'docx', 'txt']
        ext = self.file.name.split('.')[-1].lower()
        if ext not in valid_extensions:
            raise ValidationError(f'Unsupported file extension. Allowed: {", ".join(valid_extensions)}')
        self.file_type = ext

    def save(self, *args, **kwargs):
        is_new = self.pk is None  
        self.full_clean()
        super().save(*args, **kwargs)

        if is_new:
            from .tasks import process_document 
            process_document.delay(self.id)
    def __str__(self):
        return f"{self.title} ({self.file_type})"

class Embedding(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='embeddings')
    embedding = models.BinaryField()  
    text_chunk = models.TextField()
    chunk_index = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        try:
           
            vector = pickle.loads(self.embedding)
            expected_dim = 384  
            if not isinstance(vector, list) or len(vector) != expected_dim:
                raise ValidationError(f"Embedding must be a list of {expected_dim} floats.")
        except Exception:
            raise ValidationError("Invalid embedding format. Must be a pickled list of floats.")

    def save(self, *args, **kwargs):
        self.full_clean()  
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Embedding {self.chunk_index} for {self.document.title}"

class ChatSession(models.Model):
    """Tracks a conversation session between user and bot"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Chat with {self.user.username} at {self.created_at}"

class ChatMessage(models.Model):
    """Stores individual messages in a chat session"""
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    message = models.TextField()
    is_user = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    references = models.ManyToManyField(Embedding, blank=True)  

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        role = "User" if self.is_user else "Bot"
        return f"{role} message at {self.created_at}"
