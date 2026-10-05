from collections import defaultdict
from datetime import date

from fastapi import HTTPException, Request, status
from slowapi.util import get_remote_address

from app.core.config import get_settings

# IP -> (son görülen gün, o gündeki istek sayısı). Tek process içinde
# bellekte tutulur; birincil savunma Google/Groq konsollarındaki harcama
# limitleri (bkz. README) — bu ek bir katman, process yeniden başlayınca
# ya da çoklu worker'da sıfırlanır. Kalıcı/paylaşımlı bir sayaç gerekirse
# Redis'e taşınabilir.
_counts: dict[str, tuple[date, int]] = defaultdict(lambda: (date.min, 0))


def enforce_guest_plan_limit(request: Request, user_id: str | None) -> None:
    """Giriş yapmamış (user_id yok) istekler için günlük plan üretme kotası.

    Frontend'deki aynı amaçlı localStorage sayacının (guestLimit.ts,
    GUEST_PLAN_LIMIT) yerini almaz, tamamlar: localStorage curl ya da
    gizli sekmeyle bastırılabiliyordu, bu gerçek bir sunucu tarafı sınır.
    """
    if user_id is not None:
        return
    ip = get_remote_address(request)
    today = date.today()
    last_day, count = _counts[ip]
    if last_day != today:
        count = 0
    if count >= get_settings().guest_daily_plan_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Günlük misafir plan hakkınız doldu. Giriş yapıp devam edebilirsiniz.",
            headers={"X-Guest-Limit-Reached": "1"},
        )
    _counts[ip] = (today, count + 1)
