"""Главный нормализатор: ScrapedProduct → NormalizedProduct."""

from __future__ import annotations

import re

from scraper.models.product import Finish, NormalizedProduct, ProductType, ScrapedProduct, Texture
from scraper.normalizer import category_map, inci_map, pao_parser

# Текстура: ищем ключевые слова в названии/категории продукта
_TEXTURE_KEYWORDS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bstick\b|\bстик\b|\bкарандаш\b", re.I), "stick"),
    (re.compile(r"\bpowder\b|\bпудра\b|\brассыпч", re.I), "powder"),
    (re.compile(r"\bgel\b|\bгель\b", re.I), "gel"),
    (re.compile(r"\bliquid\b|\bжидк", re.I), "liquid"),
    (re.compile(r"\bcream\b|\bкрем\b|\bмусс\b|\bmousse\b", re.I), "cream"),
]

# Покрытие: ищем в названии
_FINISH_KEYWORDS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bmatte\b|\bматов|\bматт", re.I), "matte"),
    (re.compile(r"\bshimmer\b|\bсияни|\bблёст|\bглиттер\b|\bglitter\b", re.I), "shimmer"),
    (re.compile(r"\bsatin\b|\bатлас|\bсатин", re.I), "satin"),
    (re.compile(r"\bcreamy\b|\bкремов", re.I), "creamy"),
]


def _infer_texture(text: str) -> Texture | None:
    for pattern, value in _TEXTURE_KEYWORDS:
        if pattern.search(text):
            return Texture(value)
    return None


def _infer_finish(text: str) -> Finish | None:
    for pattern, value in _FINISH_KEYWORDS:
        if pattern.search(text):
            return Finish(value)
    return None


def normalize(raw: ScrapedProduct) -> NormalizedProduct:
    """Преобразует сырой продукт из источника в нормализованный формат."""

    # 1. Тип продукта по категории источника
    product_type_str = category_map.lookup(raw.raw_category)
    product_type = ProductType(product_type_str) if product_type_str else None

    # 2. Активы из INCI-строки
    active_codes = inci_map.extract_actives(raw.ingredients_text or "")

    # 3. PAO
    pao_months = pao_parser.parse_pao(raw.pao_raw)

    # 4. Текстура и покрытие — по ключевым словам в названии + категории
    search_text = f"{raw.name} {raw.raw_category}"
    texture = _infer_texture(search_text)
    finish = _infer_finish(search_text)

    # 5. Атрибуты — очищаем и переносим полезные поля из attributes_raw
    attributes: dict = {}
    for key in ("spf", "vegan", "cruelty_free", "color_family", "application_zone"):
        if key in raw.attributes_raw:
            attributes[key] = raw.attributes_raw[key]
    # Всегда сохраняем источник для аудита
    attributes["scraper_source"] = raw.source
    attributes["scraper_source_id"] = raw.source_id

    return NormalizedProduct(
        source=raw.source,
        source_id=raw.source_id,
        gtin=raw.gtin,
        name=raw.name.strip(),
        brand=raw.brand.strip() if raw.brand else None,
        shade=raw.shade,
        product_type=product_type,
        texture=texture,
        finish=finish,
        pao_months=pao_months,
        active_codes=active_codes,
        attributes=attributes,
        needs_review=(product_type is None),
    )
