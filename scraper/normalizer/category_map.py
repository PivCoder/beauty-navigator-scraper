"""Маппинг категорий из источников в наш ProductType.

Ключи — нижний регистр, без лишних пробелов.
Значения — строковые литералы ProductType (не импортируем Enum чтобы не тащить зависимость).

Порядок объявления ключей на результат НЕ влияет: при неточном совпадении
`lookup` выбирает самый длинный подошедший ключ (см. комментарий там же).
Пополнять карту можно в любом месте — уточняющий ключ всегда перебьёт
обобщённый.
"""

from __future__ import annotations

import re

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


_WORD_RE = re.compile(r"[a-zа-яё0-9]+")


def _tokens(text: str) -> list[str]:
    """Слова строки в нижнем регистре: дефисы и пробелы — одинаковые разделители."""
    return _WORD_RE.findall(text)


def _matches(pattern: str, key: str, key_tokens: frozenset[str]) -> bool:
    """Подходит ли ключ карты `pattern` под входную категорию `key`.

    Сначала обычное вхождение подстрокой (как было), затем — только для
    многословных ключей — совпадение по словам в любом порядке: в рознице
    "крем тональный" встречается не реже, чем "тональный крем".
    Для однословных ключей подстроки достаточно, а проверка по словам ничего
    не добавила бы, кроме ложных срабатываний.
    """
    if pattern in key:
        return True
    pattern_tokens = _tokens(pattern)
    if len(pattern_tokens) < 2:
        return False
    return all(token in key_tokens for token in pattern_tokens)


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
    # Частичное совпадение — берём САМЫЙ ДЛИННЫЙ подходящий ключ, а не первый
    # попавшийся. Обобщённые ключи ("крем", "масло") объявлены раньше
    # уточняющих ("солнцезащитный крем", "гидрофильное масло"), и выбор по
    # порядку словаря отдавал их: "гидрофильное масло для лица" уезжало в
    # skincare_active вместо cleanser. Длина ключа = его специфичность,
    # поэтому результат не зависит от порядка объявления и не поедет при
    # пополнении карты. При равной длине выигрывает объявленный первым.
    key_tokens = frozenset(_tokens(key))
    best: str | None = None
    best_len = 0
    for pattern, product_type in _ALL.items():
        if len(pattern) > best_len and _matches(pattern, key, key_tokens):
            best, best_len = product_type, len(pattern)
    return best
