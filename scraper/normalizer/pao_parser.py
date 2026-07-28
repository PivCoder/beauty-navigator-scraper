"""Парсер строки PAO (Period After Opening) в целое число месяцев.

Поддерживаемые форматы:
  "12M", "12 M", "12 months", "12 мес", "12 месяцев"
  "2Y", "2 years", "2 года", "2 лет"
  "6 мес.", "36M PAO", "Срок: 12 мес"
"""

from __future__ import annotations

import re

# Порядок важен: сначала месяцы, потом годы (чтобы "2 years 6 months" дал 30)
_MONTH_PATTERN = re.compile(
    r"(\d+)\s*(?:M\b|month[s]?|мес(?:яц(?:ев|а)?)?\.?)",
    re.IGNORECASE,
)
_YEAR_PATTERN = re.compile(
    r"(\d+)\s*(?:Y\b|year[s]?|лет|год(?:а)?)",
    re.IGNORECASE,
)


def parse_pao(raw: str | None) -> int | None:
    """Возвращает PAO в месяцах или None если строка не распознана."""
    if not raw:
        return None

    months = 0
    m = _MONTH_PATTERN.search(raw)
    if m:
        months += int(m.group(1))

    y = _YEAR_PATTERN.search(raw)
    if y:
        months += int(y.group(1)) * 12

    if months == 0:
        return None

    # Санитарная проверка: PAO больше 10 лет — скорее всего мусор
    if months > 120:
        return None

    return months
