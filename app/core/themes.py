"""Tema adlarını Google Places türlerine eşleyen harita."""

THEME_TYPES: dict[str, list[str]] = {
    "tarihi": ["historical_landmark", "museum", "tourist_attraction"],
    "alisveris": ["shopping_mall", "clothing_store", "market"],
    "kafe": ["cafe", "bakery", "coffee_shop"],
    "yemek": ["restaurant", "meal_takeaway"],
    "acik_hava": ["park", "garden", "hiking_area"],
    "eglence": ["movie_theater", "amusement_park", "bowling_alley"],
}

DEFAULT_THEMES = ["yemek", "kafe", "tarihi"]

# Sadece açık havada anlamlı temalar. Diğerleri ("tarihi", "eglence" gibi) hem
# indoor hem outdoor mekan türü barındırdığı için karma kabul edilir, elenmez.
OUTDOOR_ONLY_THEMES = {"acik_hava"}


def types_for(themes: list[str]) -> list[str]:
    """Tema listesini tekrarsız Google tür listesine çevirir."""
    result: list[str] = []
    for theme in themes:
        for t in THEME_TYPES.get(theme, []):
            if t not in result:
                result.append(t)
    return result


def filter_for_bad_weather(themes: list[str]) -> list[str]:
    """Kötü havada sadece açık havada anlamlı temaları eler.

    Eleme sonucu liste tamamen boşalırsa (ör. kullanıcı yalnızca "acik_hava"
    seçmiş), kullanıcının açık seçimini ezmemek için orijinal listeyi
    olduğu gibi döneriz.
    """
    filtered = [t for t in themes if t not in OUTDOOR_ONLY_THEMES]
    return filtered or themes
