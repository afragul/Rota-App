from app.core.themes import filter_for_bad_weather


def test_kotu_havada_acik_hava_elenir():
    """acik_hava, indoor temaların yanından elenmeli."""
    result = filter_for_bad_weather(["yemek", "acik_hava", "kafe"])

    assert result == ["yemek", "kafe"]


def test_kotu_havada_karma_temalar_kalir():
    """tarihi/eglence gibi karma temalar elenmemeli."""
    result = filter_for_bad_weather(["tarihi", "eglence"])

    assert result == ["tarihi", "eglence"]


def test_sadece_acik_hava_secilmisse_orijinal_korunur():
    """Eleme listeyi boşaltırsa kullanıcının açık seçimi ezilmemeli."""
    result = filter_for_bad_weather(["acik_hava"])

    assert result == ["acik_hava"]
