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
# /route/legs için ayrı sayaç: /plan'dan çok daha sık tetiklenen bir aksiyon
# (her durak sil/sırala/ekle çağırır), aynı sayaca karışırsa ikisi birbirini
# etkiler.
_legs_counts: dict[str, tuple[date, int]] = defaultdict(lambda: (date.min, 0))
# Mekân arama (Google Text Search) için ayrı sayaç; diğerlerinin kotasını tüketmesin.
_search_counts: dict[str, tuple[date, int]] = defaultdict(lambda: (date.min, 0))


def _gunluk_hak_var_mi(counts: dict[str, tuple[date, int]], ip: str, limit: int) -> bool:
    """counts[ip]'i günceller, bugünkü kota doluysa False döner."""
    today = date.today()
    last_day, count = counts[ip]
    if last_day != today:
        count = 0
    if count >= limit:
        return False
    counts[ip] = (today, count + 1)
    return True


def enforce_guest_plan_limit(request: Request, user_id: str | None) -> None:
    """Giriş yapmamış (user_id yok) istekler için günlük plan üretme kotası.

    Frontend'deki aynı amaçlı localStorage sayacının (guestLimit.ts,
    GUEST_PLAN_LIMIT) yerini almaz, tamamlar: localStorage curl ya da
    gizli sekmeyle bastırılabiliyordu, bu gerçek bir sunucu tarafı sınır.
    """
    if user_id is not None:
        return
    ip = get_remote_address(request)
    if not _gunluk_hak_var_mi(_counts, ip, get_settings().guest_daily_plan_limit):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Günlük misafir plan hakkınız doldu. Giriş yapıp devam edebilirsiniz.",
            headers={"X-Guest-Limit-Reached": "1"},
        )


def enforce_guest_legs_limit(request: Request, user_id: str | None) -> None:
    """Giriş yapmamış istekler için günlük /route/legs çağrı kotası.

    /plan'ın günlük kotasından ayrı bir sayaç kullanır (bkz. _legs_counts):
    TRANSIT modunda tek bir /route/legs çağrısı birden çok Google Routes
    isteğine yol açabiliyor (bkz. MAX_LEG_STOPS), bu yüzden slowapi'nin
    dakikalık limitine ek bir günlük üst sınır var.
    """
    if user_id is not None:
        return
    ip = get_remote_address(request)
    if not _gunluk_hak_var_mi(_legs_counts, ip, get_settings().guest_daily_legs_limit):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Günlük misafir durak düzenleme hakkınız doldu. Giriş yapıp devam edin.",
            headers={"X-Guest-Limit-Reached": "1"},
        )


def enforce_guest_search_limit(request: Request, user_id: str | None) -> None:
    """Giriş yapmamış istekler için günlük mekân arama kotası (her arama ücretli bir
    Google Text Search çağrısı). /plan ve /route/legs sayaçlarından ayrıdır."""
    if user_id is not None:
        return
    ip = get_remote_address(request)
    if not _gunluk_hak_var_mi(_search_counts, ip, get_settings().guest_daily_search_limit):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Günlük misafir arama hakkınız doldu. Giriş yapıp devam edebilirsiniz.",
            headers={"X-Guest-Limit-Reached": "1"},
        )
