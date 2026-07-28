"""Тесты парсера Open Beauty Facts. Без сети — транспорт httpx подменён."""

from __future__ import annotations

import httpx
import pytest

from scraper.models.product import ProductType
from scraper.normalizer import normalize
from scraper.parsers.open_beauty_facts import (
    FALLBACK_USER_AGENT,
    SOURCE,
    USER_AGENT_ENV_VAR,
    OpenBeautyFactsClient,
    OpenBeautyFactsError,
    default_user_agent,
    to_scraped_product,
)

# ---------------------------------------------------------------------------
# Фикстуры данных: урезанные, но правдоподобные ответы OBF
# ---------------------------------------------------------------------------

FOUNDATION = {
    "code": "3600541234567",
    "product_name": "Infaillible 24H Matte Foundation",
    "brands": "L'Oréal Paris",
    "categories": "Make-up, Face make-up, Foundations",
    "categories_tags": ["en:make-up", "en:face-makeups", "en:foundations"],
    "ingredients_text": "Aqua, Glycerin, Niacinamide, Tocopherol",
    "periods_after_opening": "12 M",
    "labels_tags": ["en:vegan", "en:cruelty-free"],
    "quantity": "30 ml",
    "image_url": "https://images.openbeautyfacts.org/x.jpg",
}

MASCARA = {
    "code": "3474636397174",
    "product_name": "Volume Million Lashes",
    "brands": "L'Oréal",
    "categories_tags": ["en:make-up", "en:eye-makeups", "en:mascaras"],
    "periods_after_opening": "6 M",
}

# Ответы живого OBF, снятые вручную 2026-07-27 с
# /api/v2/search?categories_tags_en=mascaras — приведены дословно.
# Именно они вскрыли два дефекта: теги не упорядочены (список кончается на
# `nl:Beauty`) и OBF пишет `en:mascara` в единственном числе.
REAL_STELLARY_MASCARA = {
    "brands": "Stellary",
    "categories_tags": [
        "en:makeup",
        "en:eyes",
        "en:eyes-makeup",
        "en:mascara",
        "en:Black mascaras",
        "en:Cosmetics",
        "en:Eye make-up",
        "en:Make-up",
        "en:Volumizing mascaras",
    ],
    "code": "7640473382857",
    "labels_tags": [],
    "product_name": "Stellary Panther Black Volume Mascara 01 Black - Hypnotic Volume & Defined Lashes",
}

REAL_LOREAL_MASCARA = {
    "brands": "L'Oréal",
    "categories_tags": ["en:makeup", "en:eyes", "en:eyes-makeup", "en:mascara", "nl:Beauty"],
    "code": "30149649",
    "labels_tags": [],
    "product_name": "L'Oréal Paris Panorama mascara black",
}

# Форма ответа поиска, снятая там же. Внимание на page_count: это число
# записей на странице (2), а НЕ количество страниц — при count=72 и page_size=2
# страниц 36. Пагинация считается по count, page_count не используется.
REAL_SEARCH_PAGE = {
    "count": 72,
    "page": 1,
    "page_count": 2,
    "page_size": 2,
    "products": [REAL_STELLARY_MASCARA, REAL_LOREAL_MASCARA],
    "skip": 0,
}


def _json_route(handler):
    """httpx.MockTransport с переданным обработчиком."""
    return httpx.MockTransport(handler)


@pytest.fixture(autouse=True)
def _clean_user_agent_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Убирает OBF_USER_AGENT из окружения перед каждым тестом.

    Иначе набор становится плавающим: у разработчика с выставленной
    переменной падали бы тесты, проверяющие значение по умолчанию.
    Тесты, которым переменная нужна, выставляют её сами.
    """
    monkeypatch.delenv(USER_AGENT_ENV_VAR, raising=False)


# ---------------------------------------------------------------------------
# to_scraped_product — чистая функция, без клиента
# ---------------------------------------------------------------------------

class TestToScrapedProduct:
    def test_maps_core_fields(self) -> None:
        product = to_scraped_product(FOUNDATION)
        assert product is not None
        assert product.source == SOURCE
        assert product.source_id == "3600541234567"
        assert product.gtin == "3600541234567"
        assert product.name == "Infaillible 24H Matte Foundation"
        assert product.brand == "L'Oréal Paris"
        assert product.pao_raw == "12 M"
        assert "Niacinamide" in (product.ingredients_text or "")

    def test_joins_all_category_tags(self) -> None:
        # Отдаём весь список: теги в OBF ничем не упорядочены, «самого точного»
        # по позиции не существует — см. TestRealApiPayloads
        assert to_scraped_product(FOUNDATION).raw_category == (
            "en:make-up, en:face-makeups, en:foundations"
        )

    def test_falls_back_to_categories_string(self) -> None:
        payload = {**FOUNDATION}
        del payload["categories_tags"]
        assert to_scraped_product(payload).raw_category == "Make-up, Face make-up, Foundations"

    def test_labels_become_attributes(self) -> None:
        attrs = to_scraped_product(FOUNDATION).attributes_raw
        assert attrs["vegan"] is True
        assert attrs["cruelty_free"] is True

    def test_no_labels_no_keys(self) -> None:
        attrs = to_scraped_product(MASCARA).attributes_raw
        assert "vegan" not in attrs
        assert "cruelty_free" not in attrs

    def test_name_falls_back_to_english_then_generic(self) -> None:
        assert to_scraped_product({"code": "1", "product_name_en": "Serum"}).name == "Serum"
        assert to_scraped_product({"code": "1", "generic_name": "Крем"}).name == "Крем"

    def test_blank_name_is_not_a_name(self) -> None:
        # В OBF пустые строки встречаются чаще, чем отсутствующие ключи
        assert to_scraped_product({"code": "1", "product_name": "   "}) is None

    def test_rejects_record_without_code(self) -> None:
        assert to_scraped_product({"product_name": "X"}) is None

    def test_rejects_record_without_name(self) -> None:
        assert to_scraped_product({"code": "3600541234567"}) is None

    def test_non_gtin_code_keeps_source_id_but_drops_gtin(self) -> None:
        product = to_scraped_product({"code": "0000", "product_name": "X"})
        assert product is not None
        assert product.source_id == "0000"
        assert product.gtin is None

    def test_numeric_code_is_stringified(self) -> None:
        # json.loads отдаёт int, если код записан без кавычек
        product = to_scraped_product({"code": 3600541234567, "product_name": "X"})
        assert product is not None
        assert product.gtin == "3600541234567"

    def test_garbage_input(self) -> None:
        assert to_scraped_product({}) is None
        assert to_scraped_product("не словарь") is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# User-Agent
# ---------------------------------------------------------------------------

class TestUserAgent:
    def test_default_does_not_leak_project_identity(self) -> None:
        """Значение по умолчанию не должно выдавать, чей это проект.

        Тест-сторож: если кто-то вернёт в код название продукта, домен или
        ссылку на репозиторий, сборка упадёт здесь, а не после того, как
        строка уже засветилась в чужих логах.
        """
        ua = FALLBACK_USER_AGENT.lower()
        for leak in ("beauty", "navigator", "github", "http", ".com", ".ru", "@"):
            assert leak not in ua, f"User-Agent по умолчанию раскрывает проект: {leak!r}"

    def test_env_var_overrides_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(USER_AGENT_ENV_VAR, "custom/9.9 (ops@example.test)")
        assert default_user_agent() == "custom/9.9 (ops@example.test)"

    def test_empty_env_var_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(USER_AGENT_ENV_VAR, "")
        assert default_user_agent() == FALLBACK_USER_AGENT

    def test_no_env_var_uses_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(USER_AGENT_ENV_VAR, raising=False)
        assert default_user_agent() == FALLBACK_USER_AGENT

    async def test_env_var_reaches_the_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(USER_AGENT_ENV_VAR, "from-env/1.0")
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.headers["User-Agent"])
            return httpx.Response(200, json={"status": 1, "product": FOUNDATION})

        async with OpenBeautyFactsClient(transport=_json_route(handler)) as client:
            await client.fetch_by_gtin("3600541234567")

        assert seen == ["from-env/1.0"]

    async def test_explicit_argument_wins_over_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(USER_AGENT_ENV_VAR, "from-env/1.0")
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.headers["User-Agent"])
            return httpx.Response(200, json={"status": 1, "product": FOUNDATION})

        async with OpenBeautyFactsClient(
            transport=_json_route(handler), user_agent="explicit/2.0"
        ) as client:
            await client.fetch_by_gtin("3600541234567")

        assert seen == ["explicit/2.0"]


# ---------------------------------------------------------------------------
# fetch_by_gtin
# ---------------------------------------------------------------------------

class TestFetchByGtin:
    async def test_returns_product(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v2/product/3600541234567.json"
            assert "fields" in request.url.params
            assert request.headers["User-Agent"] == FALLBACK_USER_AGENT
            return httpx.Response(200, json={"status": 1, "product": FOUNDATION})

        async with OpenBeautyFactsClient(transport=_json_route(handler)) as client:
            product = await client.fetch_by_gtin("3600541234567")

        assert product is not None
        assert product.name == "Infaillible 24H Matte Foundation"

    async def test_404_returns_none(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"status": 0, "status_verbose": "not found"})

        async with OpenBeautyFactsClient(transport=_json_route(handler)) as client:
            assert await client.fetch_by_gtin("3600541234567") is None

    async def test_status_zero_returns_none(self) -> None:
        # Основной путь «товара нет»: проверено на живом OBF — отсутствующий
        # штрихкод отдаёт HTTP 200 с {"status":0,"status_verbose":"product not found"},
        # а не 404, как можно было ожидать от REST-семантики
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json={"code": "3600541234567", "status": 0, "status_verbose": "product not found"}
            )

        async with OpenBeautyFactsClient(transport=_json_route(handler)) as client:
            assert await client.fetch_by_gtin("3600541234567") is None

    @pytest.mark.parametrize("bad", ["", "123", "abcdefgh", "3600541234567890", "36005 41234"])
    async def test_invalid_gtin_never_hits_network(self, bad: str) -> None:
        def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
            raise AssertionError("запрос не должен уйти")

        async with OpenBeautyFactsClient(transport=_json_route(handler)) as client:
            with pytest.raises(ValueError, match="GTIN"):
                await client.fetch_by_gtin(bad)

    async def test_retries_then_succeeds(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] < 3:
                return httpx.Response(503)
            return httpx.Response(200, json={"status": 1, "product": FOUNDATION})

        async with OpenBeautyFactsClient(
            transport=_json_route(handler), product_min_interval=0
        ) as client:
            product = await client.fetch_by_gtin("3600541234567")

        assert calls["n"] == 3
        assert product is not None

    async def test_gives_up_after_max_attempts(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(500)

        async with OpenBeautyFactsClient(
            transport=_json_route(handler), max_attempts=2, product_min_interval=0
        ) as client:
            with pytest.raises(OpenBeautyFactsError, match="повторы исчерпаны"):
                await client.fetch_by_gtin("3600541234567")

        assert calls["n"] == 2

    async def test_client_error_is_not_retried(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(400)

        async with OpenBeautyFactsClient(
            transport=_json_route(handler), product_min_interval=0
        ) as client:
            with pytest.raises(OpenBeautyFactsError, match="400"):
                await client.fetch_by_gtin("3600541234567")

        assert calls["n"] == 1, "на 4xx повторять бессмысленно"

    async def test_network_failure_is_wrapped(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("нет сети")

        async with OpenBeautyFactsClient(
            transport=_json_route(handler), max_attempts=2, product_min_interval=0
        ) as client:
            with pytest.raises(OpenBeautyFactsError, match="сеть недоступна"):
                await client.fetch_by_gtin("3600541234567")

    async def test_non_json_body_is_wrapped(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>под нагрузкой</html>")

        async with OpenBeautyFactsClient(
            transport=_json_route(handler), product_min_interval=0
        ) as client:
            with pytest.raises(OpenBeautyFactsError, match="не является JSON"):
                await client.fetch_by_gtin("3600541234567")


# ---------------------------------------------------------------------------
# iter_by_category / fetch_by_category
# ---------------------------------------------------------------------------

class TestFetchByCategory:
    async def test_walks_all_pages(self) -> None:
        pages = {
            1: {"count": 3, "products": [FOUNDATION, MASCARA]},
            2: {"count": 3, "products": [{**FOUNDATION, "code": "1111111111111"}]},
        }
        seen_pages: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v2/search"
            assert request.url.params["categories_tags_en"] == "foundations"
            page = int(request.url.params["page"])
            seen_pages.append(page)
            return httpx.Response(200, json=pages.get(page, {"count": 3, "products": []}))

        async with OpenBeautyFactsClient(
            transport=_json_route(handler), search_min_interval=0
        ) as client:
            products = await client.fetch_by_category("foundations", page_size=2)

        assert seen_pages == [1, 2], "обход должен остановиться по count, а не упереться в max_pages"
        assert [p.source_id for p in products] == [
            "3600541234567",
            "3474636397174",
            "1111111111111",
        ]

    async def test_stops_on_empty_page(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            page = int(request.url.params["page"])
            if page == 1:
                return httpx.Response(200, json={"products": [FOUNDATION]})
            return httpx.Response(200, json={"products": []})

        async with OpenBeautyFactsClient(
            transport=_json_route(handler), search_min_interval=0
        ) as client:
            products = await client.fetch_by_category("foundations")

        assert len(products) == 1

    async def test_max_pages_caps_the_walk(self) -> None:
        # count заведомо больше, чем мы готовы вычитать
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"count": 10_000, "products": [FOUNDATION]})

        async with OpenBeautyFactsClient(
            transport=_json_route(handler), search_min_interval=0
        ) as client:
            products = await client.fetch_by_category("foundations", max_pages=3)

        assert len(products) == 3

    async def test_broken_records_are_skipped_not_fatal(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if int(request.url.params["page"]) == 1:
                return httpx.Response(
                    200,
                    json={
                        "count": 4,
                        "products": [FOUNDATION, {"code": "2"}, "мусор", {"product_name": "X"}],
                    },
                )
            return httpx.Response(200, json={"count": 4, "products": []})

        async with OpenBeautyFactsClient(
            transport=_json_route(handler), search_min_interval=0
        ) as client:
            products = await client.fetch_by_category("foundations")

        assert [p.source_id for p in products] == ["3600541234567"]

    async def test_real_search_envelope(self) -> None:
        """Пагинация на настоящей форме ответа поиска.

        Сторож против ловушки: `page_count` в ответе равен 2, но это число
        записей на странице, а не количество страниц (при count=72 и
        page_size=2 их 36). Тот, кто примет его за общее число страниц,
        остановится на второй и недоберёт каталог.
        """
        seen_pages: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_pages.append(int(request.url.params["page"]))
            return httpx.Response(200, json=REAL_SEARCH_PAGE)

        async with OpenBeautyFactsClient(
            transport=_json_route(handler), search_min_interval=0
        ) as client:
            products = await client.fetch_by_category("mascaras", page_size=2, max_pages=3)

        assert seen_pages == [1, 2, 3]
        assert len(products) == 6, "page_count не должен приниматься за число страниц"
        assert products[0].brand == "Stellary"

    async def test_rejects_bad_page_size(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
            raise AssertionError("запрос не должен уйти")

        async with OpenBeautyFactsClient(transport=_json_route(handler)) as client:
            with pytest.raises(ValueError, match="page_size"):
                await client.fetch_by_category("foundations", page_size=0)


# ---------------------------------------------------------------------------
# Стык с нормализатором: парсер выдаёт то, что нормализатор понимает
# ---------------------------------------------------------------------------

class TestNormalizerIntegration:
    def test_foundation_normalizes_end_to_end(self) -> None:
        result = normalize(to_scraped_product(FOUNDATION))

        assert result.product_type is ProductType.base
        assert result.needs_review is False
        assert result.pao_months == 12
        assert "niacinamide" in result.active_codes
        assert result.attributes["vegan"] is True
        assert result.attributes["scraper_source"] == SOURCE

    def test_mascara_normalizes_to_decorative(self) -> None:
        result = normalize(to_scraped_product(MASCARA))

        assert result.product_type is ProductType.decorative
        assert result.pao_months == 6

    def test_real_stellary_mascara(self) -> None:
        result = normalize(to_scraped_product(REAL_STELLARY_MASCARA))

        assert result.product_type is ProductType.decorative
        assert result.needs_review is False
        assert result.brand == "Stellary"
        assert result.gtin == "7640473382857"

    def test_real_loreal_mascara(self) -> None:
        """Регрессия на баг «берём последний тег».

        Список тегов кончается на `nl:Beauty`; при выборе по позиции живая
        тушь уезжала в needs_review. Плюс OBF пишет `en:mascara` в единственном
        числе — карта на одних множественных формах промахивалась и здесь.
        """
        result = normalize(to_scraped_product(REAL_LOREAL_MASCARA))

        assert result.product_type is ProductType.decorative
        assert result.needs_review is False

    def test_real_records_without_pao(self) -> None:
        # В живой выдаче periods_after_opening отсутствовал у обоих товаров —
        # это норма, а не сбой: поле заполняют пользователи
        assert normalize(to_scraped_product(REAL_LOREAL_MASCARA)).pao_months is None

    def test_unknown_category_flags_review(self) -> None:
        payload = {
            "code": "3600541234567",
            "product_name": "Зубная нить",
            "categories_tags": ["en:dental-floss"],
        }
        result = normalize(to_scraped_product(payload))

        assert result.product_type is None
        assert result.needs_review is True
