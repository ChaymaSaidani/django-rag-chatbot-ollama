

---

# Django RAG Chatbot - Step-by-Step Setup Guide

Welcome! This guide will help you get the **Django RAG Chatbot** project up and running from scratch — no matter your experience level. Follow each step carefully.

---
# Project Structure

rag_project/
│
├── chatbot/ # Django app for chatbot logic
│ ├── init.py
│ ├── admin.py # Admin site configuration
│ ├── apps.py
│ ├── models.py # Database models
│ ├── schema.py # GraphQL schema
│ ├── serializers.py # DRF serializers
│ ├── tasks.py # Celery tasks (RAG processing)
│ ├── views.py # Django REST API views
│ └── pycache/
│
├── faiss_indices/ # FAISS vector index directory
│ └── doc_*.index # Auto-generated index files
│
├── rag_project/ # Django project config
│ ├── init.py
│ ├── celery.py # Celery app setup
│ ├── settings.py # Project settings
│ ├── urls.py # URL routing
│ └── pycache/
│
├── templates/ # Frontend templates
│ ├── chat.html # Chat interface
│ ├── index.html # Dashboard
│ └── login.html # Login UI
│
├── media/ # User-uploaded files
├── .gitignore
├── requirements.txt # Python dependencies
└── README.md # Documentation
---

## 1. Clone the project repository

Open your terminal or command prompt and run:

```bash
git clone https://github.com/yourusername/django-rag-chatbot.git
cd django-rag-chatbot
```

---

## 2. (Optional but Recommended) Create a Python Virtual Environment

A virtual environment keeps your project dependencies isolated from your system Python.

* Create it:

```bash
python -m venv venv
```

* Activate it:

> **Windows:**

```bash
venv\Scripts\activate
```

> **Linux/macOS:**

```bash
source venv/bin/activate
```

You’ll know it’s active when your terminal prompt starts with `(venv)`.

---

## 3. Install Python dependencies

Make sure you’re in your project root folder (where `requirements.txt` is) and run:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4. Install and start Redis (Required for Celery)

Redis is a message broker used by Celery to run background tasks.

* **Windows:**
  Download and install Redis from [https://redis.io/docs/getting-started/installation/install-redis-on-windows/](https://redis.io/docs/getting-started/installation/install-redis-on-windows/). Then run:

```bash
redis-server
```

* **macOS:**
  Use Homebrew:

```bash
brew install redis
brew services start redis
```

* **Linux (Ubuntu/Debian):**

```bash
sudo apt update
sudo apt install redis-server
sudo systemctl enable redis-server.service
sudo systemctl start redis-server.service
```

Test Redis is running by typing:

```bash
redis-cli ping
```

You should get:

```
PONG
```

---

## 5. Setup environment variables

Create a `.env` file in the project root folder with the following (replace placeholders as needed):

```
SECRET_KEY=your_django_secret_key
DEBUG=True
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
FAISS_INDEX_PATH=./faiss_indices
```

---

## 6. Apply database migrations

Run:

```bash
python manage.py migrate
```

---

## 7. Create a superuser (optional but recommended)

```bash
python manage.py createsuperuser
```

Follow the prompts to create your admin login.

---

## 8. Start Celery worker for background tasks

Open a new terminal, activate your virtual environment again, then run:

```bash
celery -A rag_project worker --pool=gevent --loglevel=info
```

This keeps Celery running to process document indexing and chatbot requests.

---

## 9. Run Django development server

Back to your main terminal:

```bash
python manage.py runserver
```

Visit [http://localhost:8000](http://localhost:8000) in your browser.

---

## 10. Optional: Install and use Ollama with Mistral AI model

Ollama serves AI models locally to power chatbot responses.

* **Install Ollama**: [https://ollama.com/download](https://ollama.com/download)

* **Run the Mistral model:**

```bash
ollama run mistral
```

* **Or serve the model persistently:**

```bash
ollama serve
```

Make sure your `.env` or project settings point to Ollama’s API endpoint if you want to use Ollama instead of other LLM providers.

---

## Usage Overview

* Upload documents through the web interface to `media/`.
* Documents get indexed asynchronously via Celery into `faiss_indices/`.
* Chat with the bot to get answers augmented by your uploaded documents.
* Use Django admin for advanced management.

---

## Troubleshooting

* **Redis errors?** Make sure Redis is running and reachable at `redis://localhost:6379/0`.
* **Celery not processing tasks?** Restart the Celery worker.
* **Virtual environment not activating?** Double-check the command for your OS.
* **New code changes to tasks?** Restart Celery worker to load updates.

---

## Thanks for using this project!

Feel free to open issues or contribute via pull requests.

---



