"""Парсер Open Beauty Facts (OBF).

Два способа забора данных:
  * по GTIN — точечный запрос карточки товара (для barcode-сканера);
  * по категории — постраничный обход поиска (для наполнения каталога).

Слои разделены намеренно:
  * `to_scraped_product` — чистая функция, JSON → ScrapedProduct. Без I/O,
    тестируется без сети;
  * `OpenBeautyFactsClient` — только HTTP: ретраи, троттлинг, пагинация.

Данные отдаются в виде ScrapedProduct «как есть». Приведение к нашим типам —
задача `scraper.normalizer`, парсер в неё не лезет.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from scraper.models.product import ScrapedProduct

SOURCE = "open_beauty_facts"

# URL и User-Agent — параметры клиента, а не константы в местах вызова.
DEFAULT_BASE_URL = "https://world.openbeautyfacts.org"

# User-Agent намеренно обезличен: в исходниках не должно быть указаний на то,
# чей это проект — репозиторий уходит дальше, чем хотелось бы.
#
# OBF просит клиентов представляться и оставлять контакт; без этого выше шанс
# попасть под ограничение по частоте. Компромисс: строка честно сообщает, что
# это импортёр каталога, но ничего не говорит о владельце. Если понадобится
# указать контакт — задать OBF_USER_AGENT через окружение, тогда он останется
# на машине оператора и не попадёт в git.
USER_AGENT_ENV_VAR = "OBF_USER_AGENT"
FALLBACK_USER_AGENT = "cosmetics-catalog-importer/0.1"


def default_user_agent() -> str:
    """User-Agent из окружения, иначе обезличенное значение по умолчанию.

    Читается при создании клиента, а не при импорте модуля, — иначе значение
    нельзя было бы подменить в тестах.
    """
    return os.environ.get(USER_AGENT_ENV_VAR) or FALLBACK_USER_AGENT

# Запрашиваем только нужные поля — ответ на порядок меньше полного документа.
PRODUCT_FIELDS = (
    "code,product_name,product_name_en,generic_name,brands,"
    "categories,categories_tags,ingredients_text,ingredients_text_en,"
    "periods_after_opening,labels_tags,quantity,image_url"
)

# Документированные лимиты OBF: 100 запросов/мин на карточку товара,
# 10 запросов/мин на поиск. Держим паузу с запасом.
PRODUCT_MIN_INTERVAL = 0.6
SEARCH_MIN_INTERVAL = 6.0

DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_ATTEMPTS = 4

_GTIN_RE = re.compile(r"^\d{8,14}$")

# Коды, на которых имеет смысл повторить запрос
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class OpenBeautyFactsError(RuntimeError):
    """Ошибка обращения к OBF, пережившая все повторы."""


class _RetryableResponse(RuntimeError):
    """Внутренний сигнал tenacity: ответ получен, но стоит повторить."""


# ---------------------------------------------------------------------------
# Чистое преобразование JSON → ScrapedProduct
# ---------------------------------------------------------------------------

def _first_nonempty(payload: dict[str, Any], *keys: str) -> str | None:
    """Первое непустое строковое значение из перечисленных ключей."""
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _pick_category(payload: dict[str, Any]) -> str:
    """Категория для нормализатора: все теги одной строкой.

    Отдаём весь список, а не один тег. Соблазн взять последний как «самый
    точный» разбивается о реальные данные — теги ничем не упорядочены:

        L'Oréal Paris mascara →
            ["en:makeup", "en:eyes", "en:eyes-makeup", "en:mascara", "nl:Beauty"]

    Последний здесь `nl:Beauty`, и тушь уехала бы в needs_review, хотя нужный
    тег лежит рядом. Склейка даёт `category_map.lookup` шанс найти любой из
    тегов частичным совпадением; приоритет при нескольких совпадениях задаёт
    порядок ключей в самой карте, а не случайный порядок тегов в ответе.

    Формат склейки повторяет поле `categories` того же OBF, поэтому основной
    путь и запасной дают строку одного вида.
    """
    tags = payload.get("categories_tags")
    if isinstance(tags, list):
        cleaned = [t.strip() for t in tags if isinstance(t, str) and t.strip()]
        if cleaned:
            return ", ".join(cleaned)
    return _first_nonempty(payload, "categories") or ""


def _extract_labels(payload: dict[str, Any]) -> dict[str, bool]:
    """vegan / cruelty_free из labels_tags — единственные метки, которые
    нормализатор переносит дальше."""
    tags = payload.get("labels_tags")
    if not isinstance(tags, list):
        return {}

    normalized = {t.split(":", 1)[-1] for t in tags if isinstance(t, str)}
    labels: dict[str, bool] = {}
    if "vegan" in normalized:
        labels["vegan"] = True
    if normalized & {"cruelty-free", "no-animal-testing"}:
        labels["cruelty_free"] = True
    return labels


def to_scraped_product(payload: dict[str, Any]) -> ScrapedProduct | None:
    """JSON карточки OBF → ScrapedProduct.

    Возвращает None, если запись непригодна: без кода её не с чем связать,
    без названия она бесполезна в каталоге. Такие записи в OBF не редкость —
    база пополняется пользователями.
    """
    if not isinstance(payload, dict):
        return None

    code = payload.get("code")
    code = str(code).strip() if code is not None else ""
    if not code:
        return None

    name = _first_nonempty(payload, "product_name", "product_name_en", "generic_name")
    if not name:
        return None

    attributes_raw: dict[str, Any] = {}
    attributes_raw.update(_extract_labels(payload))

    tags = payload.get("categories_tags")
    if isinstance(tags, list):
        attributes_raw["categories_tags"] = [t for t in tags if isinstance(t, str)]
    for key in ("quantity", "image_url"):
        value = _first_nonempty(payload, key)
        if value:
            attributes_raw[key] = value

    return ScrapedProduct(
        source=SOURCE,
        source_id=code,
        # В OBF code и есть штрихкод, но мусорные значения вроде "0000" не редкость
        gtin=code if _GTIN_RE.match(code) else None,
        name=name,
        brand=_first_nonempty(payload, "brands"),
        raw_category=_pick_category(payload),
        ingredients_text=_first_nonempty(payload, "ingredients_text", "ingredients_text_en"),
        pao_raw=_first_nonempty(payload, "periods_after_opening"),
        attributes_raw=attributes_raw,
    )


# ---------------------------------------------------------------------------
# HTTP-клиент
# ---------------------------------------------------------------------------

class OpenBeautyFactsClient:
    """Асинхронный клиент OBF.

    Использовать как контекстный менеджер:

        async with OpenBeautyFactsClient() as client:
            product = await client.fetch_by_gtin("3600541234567")

    В тестах подменяется транспорт, сеть не нужна:

        transport = httpx.MockTransport(handler)
        async with OpenBeautyFactsClient(transport=transport) as client:
            ...
    """

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        user_agent: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        transport: httpx.AsyncBaseTransport | None = None,
        product_min_interval: float = PRODUCT_MIN_INTERVAL,
        search_min_interval: float = SEARCH_MIN_INTERVAL,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._max_attempts = max_attempts
        self._product_min_interval = product_min_interval
        self._search_min_interval = search_min_interval
        self._last_request_at = 0.0
        self._throttle_lock = asyncio.Lock()
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            headers={
                "User-Agent": user_agent or default_user_agent(),
                "Accept": "application/json",
            },
            transport=transport,
            follow_redirects=True,
        )

    async def __aenter__(self) -> OpenBeautyFactsClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    # -- внутреннее ---------------------------------------------------------

    async def _throttle(self, min_interval: float) -> None:
        """Выдерживает паузу между запросами. OBF — бесплатный публичный
        сервис, и вежливость здесь не формальность: за долбёжку блокируют."""
        if min_interval <= 0:
            return
        async with self._throttle_lock:
            delay = min_interval - (time.monotonic() - self._last_request_at)
            if delay > 0:
                await asyncio.sleep(delay)
            self._last_request_at = time.monotonic()

    async def _get_json(
        self, url: str, params: dict[str, Any], min_interval: float
    ) -> dict[str, Any] | None:
        """GET с повторами. None — ресурс отсутствует (404).

        Повторяем только то, что имеет шанс пройти со второй попытки:
        сетевые сбои, 429 и 5xx. На 4xx повторять бессмысленно.
        """

        @retry(
            retry=retry_if_exception_type((httpx.TransportError, _RetryableResponse)),
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential(multiplier=1, min=1, max=30),
            reraise=True,
        )
        async def _attempt() -> httpx.Response | None:
            await self._throttle(min_interval)
            response = await self._client.get(url, params=params)
            if response.status_code == 404:
                return None
            if response.status_code in _RETRYABLE_STATUS:
                raise _RetryableResponse(f"{response.status_code} от {url}")
            if response.status_code >= 400:
                raise OpenBeautyFactsError(f"{url} вернул {response.status_code}")
            return response

        try:
            response = await _attempt()
        except _RetryableResponse as exc:
            raise OpenBeautyFactsError(f"{url}: повторы исчерпаны ({exc})") from exc
        except httpx.TransportError as exc:
            raise OpenBeautyFactsError(f"{url}: сеть недоступна ({exc})") from exc

        if response is None:
            return None

        try:
            payload = response.json()
        except ValueError as exc:
            raise OpenBeautyFactsError(f"{url}: ответ не является JSON") from exc

        if not isinstance(payload, dict):
            raise OpenBeautyFactsError(f"{url}: ожидался JSON-объект")
        return payload

    # -- публичное ----------------------------------------------------------

    async def fetch_by_gtin(self, gtin: str) -> ScrapedProduct | None:
        """Карточка по штрихкоду. None — товара нет в базе.

        Формат GTIN проверяем до запроса: бэкенд принимает 8–14 цифр
        (`GET /api/v1/catalog/products/by-gtin/{gtin}`), и слать заведомо
        негодное значение в публичный API незачем.
        """
        code = gtin.strip()
        if not _GTIN_RE.match(code):
            raise ValueError(f"GTIN должен быть 8–14 цифр, получено: {gtin!r}")

        payload = await self._get_json(
            f"/api/v2/product/{code}.json",
            {"fields": PRODUCT_FIELDS},
            self._product_min_interval,
        )
        if payload is None:
            return None

        # v2 отдаёт 404 на отсутствующий товар, но встречается и 200 со status=0
        if payload.get("status") == 0:
            return None

        product = payload.get("product")
        if not isinstance(product, dict):
            return None
        return to_scraped_product(product)

    async def iter_by_category(
        self,
        category: str,
        *,
        page_size: int = 100,
        max_pages: int = 10,
    ) -> AsyncIterator[ScrapedProduct]:
        """Постраничный обход категории.

        `category` — тег OBF без языкового префикса, например "foundations"
        или "mascaras". Обход прекращается, когда страница пуста, набрано
        `count` записей или исчерпан `max_pages` — последнее страхует от
        бесконечного цикла, если сервер вернёт неожиданную пагинацию.

        Записи без кода или названия пропускаются молча: в OBF их заметная
        доля, и падать из-за них при массовом импорте неправильно.
        """
        if page_size < 1:
            raise ValueError(f"page_size должен быть ≥ 1, получено: {page_size}")

        seen = 0
        for page in range(1, max_pages + 1):
            payload = await self._get_json(
                "/api/v2/search",
                {
                    "categories_tags_en": category,
                    "fields": PRODUCT_FIELDS,
                    "page": page,
                    "page_size": page_size,
                },
                self._search_min_interval,
            )
            if payload is None:
                return

            products = payload.get("products")
            if not isinstance(products, list) or not products:
                return

            for item in products:
                if not isinstance(item, dict):
                    continue
                scraped = to_scraped_product(item)
                if scraped is not None:
                    yield scraped

            seen += len(products)
            count = payload.get("count")
            if isinstance(count, int) and seen >= count:
                return

    async def fetch_by_category(
        self,
        category: str,
        *,
        page_size: int = 100,
        max_pages: int = 10,
    ) -> list[ScrapedProduct]:
        """`iter_by_category`, собранный в список. Для небольших выборок."""
        return [
            product
            async for product in self.iter_by_category(
                category, page_size=page_size, max_pages=max_pages
            )
        ]
