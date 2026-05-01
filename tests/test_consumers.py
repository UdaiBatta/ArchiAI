import pytest
from channels.layers import get_channel_layer
from channels.testing.websocket import WebsocketCommunicator
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

from archi3d.asgi import application


User = get_user_model()


@pytest.mark.anyio
@pytest.mark.django_db
async def test_design_progress_consumer_connects_and_receives_events():
    user = await sync_to_async(User.objects.create_user)(
        email="socket@example.com",
        password="SocketPass123!",
        username="socket",
    )
    token = str(AccessToken.for_user(user))
    communicator = WebsocketCommunicator(
        application,
        f"/ws/design/11111111-1111-1111-1111-111111111111/?token={token}",
    )

    connected, _ = await communicator.connect()
    assert connected is True

    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        "design_progress_11111111-1111-1111-1111-111111111111",
        {
            "type": "progress.update",
            "stage": "parsing",
            "pct": 10,
            "message": "Parsing requirements...",
        },
    )
    message = await communicator.receive_json_from()
    assert message["stage"] == "parsing"
    assert message["pct"] == 10

    await communicator.disconnect()


@pytest.mark.anyio
@pytest.mark.django_db
async def test_design_progress_consumer_rejects_invalid_token():
    communicator = WebsocketCommunicator(
        application,
        "/ws/design/11111111-1111-1111-1111-111111111111/?token=invalid",
    )

    connected, _ = await communicator.connect()
    assert connected is False
