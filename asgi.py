"""
archi3d/asgi.py — ASGI Application Entry Point
================================================
ASGI (Asynchronous Server Gateway Interface) enables async Django features
and WebSocket support (e.g., for real-time layout streaming in future phases).

In production with async:  uvicorn archi3d.asgi:application
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "archi3d.settings")
application = get_asgi_application()
