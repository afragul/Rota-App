from app.services.weather import is_bad_weather


def test_yagmurlu_kod_kotu_sayilir():
    assert is_bad_weather(63) is True  # yağmurlu


def test_firtina_kodu_kotu_sayilir():
    assert is_bad_weather(95) is True  # gök gürültülü fırtına


def test_acik_kod_kotu_sayilmaz():
    assert is_bad_weather(0) is False  # açık


def test_parcali_bulutlu_kod_kotu_sayilmaz():
    assert is_bad_weather(2) is False  # parçalı bulutlu
