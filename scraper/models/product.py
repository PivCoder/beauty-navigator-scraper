from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ProductType(str, Enum):
    skincare_active = "skincare_active"
    base = "base"
    decorative = "decorative"
    cleanser = "cleanser"


class Texture(str, Enum):
    cream = "cream"
    stick = "stick"
    liquid = "liquid"
    powder = "powder"
    gel = "gel"


class Finish(str, Enum):
    matte = "matte"
    satin = "satin"
    shimmer = "shimmer"
    creamy = "creamy"


class ScrapedProduct(BaseModel):
    """Сырые данные как есть из источника — без трансформаций."""

    source: str
    source_id: str
    gtin: str | None = None
    name: str
    brand: str | None = None
    raw_category: str = ""
    shade: str | None = None
    ingredients_text: str | None = None
    pao_raw: str | None = None
    # Всё остальное (SPF, vegan, color_family…) — в свободном словаре
    attributes_raw: dict = Field(default_factory=dict)


class NormalizedProduct(BaseModel):
    """Нормализованный продукт, готовый к отправке в Admin Import API."""

    source: str
    source_id: str
    gtin: str | None = None
    name: str
    brand: str | None = None
    shade: str | None = None
    product_type: ProductType | None = None  # None → needs_review
    texture: Texture | None = None
    finish: Finish | None = None
    pao_months: int | None = None
    active_codes: list[str] = Field(default_factory=list)
    attributes: dict = Field(default_factory=dict)
    needs_review: bool = False  # True если product_type не определён
