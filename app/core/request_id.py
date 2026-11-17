import re
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id_var

HEADER = "X-Request-ID"
# Dışarıdan gelen numara log'a yazıldığı için yalnızca zararsız karakterler ve makul uzunluk
# kabul edilir (log injection); aksi halde yenisi üretilir.
_GECERLI = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class RequestIdMiddleware:
    """Her isteğe bir numara verir: log satırlarına (request_id_var) ve yanıt başlığına yazılır.

    Saf ASGI olarak yazıldı: bağlam değişkeni istek boyunca (hata işleyicileri dahil) görünür.
    Sıfırlanmaz: her istek kendi görevinde (kendi bağlam kopyasında) çalışır.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        gelen = Headers(scope=scope).get(HEADER)
        request_id = gelen if gelen and _GECERLI.match(gelen) else uuid.uuid4().hex
        request_id_var.set(request_id)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[HEADER] = request_id
            await send(message)

        await self.app(scope, receive, send_with_id)
