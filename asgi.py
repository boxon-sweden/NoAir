# ASGI entrypoint. Start with: uvicorn asgi:app --host 0.0.0.0 --port 8000
from app import create_app
app = create_app()
