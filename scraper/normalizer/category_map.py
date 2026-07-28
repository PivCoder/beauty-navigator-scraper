"""Маппинг категорий из источников в наш ProductType.

Ключи — нижний регистр, без лишних пробелов.
Значения — строковые литералы ProductType (не импортируем Enum чтобы не тащить зависимость).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Open Beauty Facts (OBF) — теги из поля categories_tags / category_properties
# https://world.openbeautyfacts.org/categories
# ---------------------------------------------------------------------------
# Формы единственного числа идут ПЕРВЫМИ и покрывают обе: `lookup` ищет ключ
# как подстроку, а "mascara" входит в "mascaras" — обратное неверно. Реальные
# ответы OBF содержат именно единственное число ("en:mascara"), из-за чего
# карта на одних множественных формах промахивалась мимо живых товаров.
# Сверено с ответом /api/v2/search 2026-07-27.
#
# Слишком общие слова ("makeup", "cream", "powder", "oil") сюда не добавлять:
# из-за частичного совпадения один такой ключ перехватит половину каталога.
_OBF: dict[str, str] = {
    # База / тональные
    "foundation": "base",
    "concealer": "base",
    "primer": "base",
    "face-powder": "base",
    "setting-powder": "base",
    "bb-cream": "base",
    "cc-cream": "base",
    "tinted-moisturizer": "base",
    "foundations": "base",
    "face-makeups": "base",
    "bb-creams": "base",
    "cc-creams": "base",
    "tinted-moisturizers": "base",
    "concealers": "base",
    "primers": "base",
    "setting-powders": "base",
    "face-powders": "base",
    # Декоративная
    "mascara": "decorative",
    "eyeliner": "decorative",
    "eyeshadow": "decorative",
    "lipstick": "decorative",
    "lip-gloss": "decorative",
    "blusher": "decorative",
    "bronzer": "decorative",
    "highlighter": "decorative",
    "nail-polish": "decorative",
    "eyes-makeup": "decorative",
    "eye-make-up": "decorative",
    "eye-makeups": "decorative",
    "mascaras": "decorative",
    "eyeliners": "decorative",
    "eyeshadows": "decorative",
    "lip-products": "decorative",
    "lipsticks": "decorative",
    "lip-glosses": "decorative",
    "blushers": "decorative",
    "bronzers": "decorative",
    "highlighters": "decorative",
    "nail-products": "decorative",
    "nail-polishes": "decorative",
    # Уход с активами
    "serum": "skincare_active",
    "face-serum": "skincare_active",
    "face-cream": "skincare_active",
    "eye-cream": "skincare_active",
    "moisturizer": "skincare_active",
    "facial-oil": "skincare_active",
    "exfoliant": "skincare_active",
    "face-mask": "skincare_active",
    "toner": "skincare_active",
    "essence": "skincare_active",
    "sunscreen": "skincare_active",
    "serums": "skincare_active",
    "face-serums": "skincare_active",
    "face-creams": "skincare_active",
    "moisturizers": "skincare_active",
    "eye-creams": "skincare_active",
    "facial-oils": "skincare_active",
    "exfoliants": "skincare_active",
    "face-masks": "skincare_active",
    "toners": "skincare_active",
    "essences": "skincare_active",
    "sunscreens": "skincare_active",
    "spf-products": "skincare_active",
    # Очищение
    "cleanser": "cleanser",
    "face-wash": "cleanser",
    "micellar-water": "cleanser",
    "makeup-remover": "cleanser",
    "cleansing-oil": "cleanser",
    "cleansing-balm": "cleanser",
    "cleansers": "cleanser",
    "face-washes": "cleanser",
    "micellar-waters": "cleanser",
    "makeup-removers": "cleanser",
    "cleansing-oils": "cleanser",
    "cleansing-balms": "cleanser",
    "foam-cleansers": "cleanser",
}

# ---------------------------------------------------------------------------
# Wildberries — subject_name из карточки товара
# ---------------------------------------------------------------------------
_WB: dict[str, str] = {
    # База
    "тональный крем": "base",
    "тональная основа": "base",
    "тональное средство": "base",
    "консилер": "base",
    "bb-крем": "base",
    "cc-крем": "base",
    "праймер": "base",
    "пудра": "base",
    "рассыпчатая пудра": "base",
    "компактная пудра": "base",
    # Декоративная
    "тушь": "decorative",
    "подводка": "decorative",
    "карандаш для глаз": "decorative",
    "тени для век": "decorative",
    "губная помада": "decorative",
    "помада": "decorative",
    "блеск для губ": "decorative",
    "румяна": "decorative",
    "бронзер": "decorative",
    "хайлайтер": "decorative",
    "лак для ногтей": "decorative",
    # Уход с активами
    "сыворотка": "skincare_active",
    "крем для лица": "skincare_active",
    "крем": "skincare_active",
    "крем-гель для лица": "skincare_active",
    "масло для лица": "skincare_active",
    "масло": "skincare_active",
    "маска для лица": "skincare_active",
    "тонер": "skincare_active",
    "эссенция": "skincare_active",
    "крем для глаз": "skincare_active",
    "крем вокруг глаз": "skincare_active",
    "солнцезащитный крем": "skincare_active",
    "spf-крем": "skincare_active",
    "пилинг": "skincare_active",
    "скраб": "skincare_active",
    # Очищение
    "пенка для умывания": "cleanser",
    "гель для умывания": "cleanser",
    "мицеллярная вода": "cleanser",
    "средство для снятия макияжа": "cleanser",
    "гидрофильное масло": "cleanser",
    "бальзам для умывания": "cleanser",
    "молочко для снятия макияжа": "cleanser",
}

# ---------------------------------------------------------------------------
# Объединённая таблица (OBF-ключи могут приходить с префиксом "en:")
# ---------------------------------------------------------------------------
_ALL: dict[str, str] = {**_OBF, **_WB}


def lookup(raw_category: str) -> str | None:
    """Возвращает ProductType-строку или None если категория неизвестна."""
    key = raw_category.lower().strip()
    # Пробуем точное совпадение
    if key in _ALL:
        return _ALL[key]
    # OBF добавляет префикс языка: "en:foundations" → "foundations"
    if ":" in key:
        key = key.split(":", 1)[1]
        if key in _ALL:
            return _ALL[key]
    # Частичное совпадение — берём первый подходящий ключ
    for pattern, product_type in _ALL.items():
        if pattern in key:
            return product_type
    return None
