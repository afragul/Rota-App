from app.services.places import _to_place


def test_tam_veriyle_donusum():
    """Google'ın eksiksiz cevabı doğru şekilde Place'e çevrilmeli."""
    raw = {
        "id": "ChIJ123",
        "displayName": {"text": "Kitap Kahve", "languageCode": "tr"},
        "formattedAddress": "Osmangazi, Bursa",
        "location": {"latitude": 40.1885, "longitude": 29.0610},
        "rating": 4.6,
        "userRatingCount": 312,
        "types": ["cafe", "food"],
    }

    place = _to_place(raw)

    assert place.place_id == "ChIJ123"
    assert place.name == "Kitap Kahve"          # iç içe yapı düzleşti mi
    assert place.latitude == 40.1885
    assert place.rating == 4.6
    assert place.types == ["cafe", "food"]


def test_puansiz_mekan():
    """Hiç yorum almamış mekânda rating alanları None olmalı, patlamamalı."""
    raw = {
        "id": "ChIJ456",
        "displayName": {"text": "Yeni Açılan Kafe", "languageCode": "tr"},
        "location": {"latitude": 40.19, "longitude": 29.06},
        # rating, userRatingCount, formattedAddress, types YOK
    }

    place = _to_place(raw)

    assert place.rating is None
    assert place.user_rating_count is None
    assert place.address is None
    assert place.types == []      # varsayılan boş liste