from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model


User = get_user_model()


class DesignProgressConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        job_id = self.scope["url_route"]["kwargs"].get("job_id")
        token = self._get_query_token()
        if not token:
            await self.close(code=4401)
            return

        user = await self._authenticate_token(token)
        if user is None:
            await self.close(code=4401)
            return

        self.user = user
        self.job_group_name = f"design_progress_{job_id}"

        await self.channel_layer.group_add(self.job_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        job_group_name = getattr(self, "job_group_name", None)
        if job_group_name:
            await self.channel_layer.group_discard(job_group_name, self.channel_name)

    def _get_query_token(self) -> str:
        query_string = self.scope.get("query_string", b"").decode("utf-8")
        params = parse_qs(query_string)
        return (params.get("token", [""])[0] or "").strip()

    async def _authenticate_token(self, token: str):
        try:
            access_token = AccessToken(token)
            user_id = access_token.get("user_id")
        except Exception:
            return None

        if user_id is None:
            return None

        return await sync_to_async(User.objects.filter(id=user_id).first)()

    async def progress_update(self, event):
        await self.send_json(
            {
                "stage": event.get("stage"),
                "pct": event.get("pct", 0),
                "message": event.get("message", ""),
            }
        )

    async def progress_complete(self, event):
        await self.send_json(
            {
                "stage": event.get("stage", "complete"),
                "pct": event.get("pct", 100),
                "message": event.get("message", "Design generation complete."),
                "result": event.get("result", {}),
            }
        )

    async def progress_error(self, event):
        await self.send_json(
            {
                "stage": event.get("stage", "error"),
                "pct": event.get("pct", 0),
                "error": event.get("error", "Unknown error"),
            }
        )
