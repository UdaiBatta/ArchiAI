from django.urls import path

from apps.design.consumers import DesignProgressConsumer

websocket_urlpatterns = [
    path("ws/design/<uuid:job_id>/", DesignProgressConsumer.as_asgi()),
]
