"""
archi3d/asgi.py — ASGI Application Entry Point
================================================
ASGI (Asynchronous Server Gateway Interface) enables async Django features
and WebSocket support (e.g., for real-time layout streaming in future phases).

In production with async:  uvicorn archi3d.asgi:application
"""
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "archi3d.settings.development")
django_asgi_application = get_asgi_application()

import archi3d.routing  # noqa: E402

application = ProtocolTypeRouter(
	{
		"http": django_asgi_application,
		"websocket": URLRouter(archi3d.routing.websocket_urlpatterns),
	}
)
