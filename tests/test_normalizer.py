"""Unit-тесты нормализатора. Без сети и БД — только чистые функции."""

from __future__ import annotations

import pytest

from scraper.models.product import ScrapedProduct
from scraper.normalizer import category_map
from scraper.normalizer.category_map import lookup
from scraper.normalizer.inci_map import extract_actives
from scraper.normalizer.normalizer import normalize
from scraper.normalizer.pao_parser import parse_pao


# ---------------------------------------------------------------------------
# category_map
# ---------------------------------------------------------------------------

class TestCategoryMap:
    def test_obf_exact(self) -> None:
        assert lookup("foundations") == "base"

    def test_obf_with_language_prefix(self) -> None:
        assert lookup("en:foundations") == "base"

    def test_wb_russian(self) -> None:
        assert lookup("Тональный крем") == "base"

    def test_wb_serum(self) -> None:
        assert lookup("Сыворотка") == "skincare_active"

    def test_wb_cleanser(self) -> None:
        assert lookup("Пенка для умывания") == "cleanser"

    def test_decorative(self) -> None:
        assert lookup("mascaras") == "decorative"

    def test_partial_match(self) -> None:
        # "face-creams-with-spf" содержит "face-creams"
        assert lookup("face-creams-with-spf") == "skincare_active"

    def test_unknown_returns_none(self) -> None:
        assert lookup("dental-floss") is None

    def test_empty_returns_none(self) -> None:
        assert lookup("") is None


class TestCategoryMapPartialMatch:
    """Неточное совпадение: выигрывает самый длинный ключ, порядок слов не важен.

    Русскоязычные источники отдают свободные фразы и попадают именно сюда,
    а неверный product_type не уходит в карантин — карточка молча приезжает
    в каталог с чужой категорией.
    """

    def test_longest_key_wins_over_generic(self) -> None:
        # "гидрофильное масло" (cleanser) длиннее, чем "масло" и "масло для лица"
        assert lookup("Гидрофильное масло для лица") == "cleanser"

    def test_generic_key_still_matches_when_alone(self) -> None:
        # обратная сторона: без уточнения "масло для лица" остаётся уходом
        assert lookup("Масло для лица питательное") == "skincare_active"

    def test_reversed_word_order(self) -> None:
        # в рознице порядок слов произвольный: "крем тональный" = "тональный крем"
        assert lookup("Крем тональный") == "base"

    def test_reversed_word_order_with_extra_words(self) -> None:
        assert lookup("Крем тональный для сухой кожи, 30 мл") == "base"

    def test_sunscreen_not_swallowed_by_cream(self) -> None:
        assert lookup("Солнцезащитный крем SPF 50") == "skincare_active"

    def test_cleansing_gel_not_swallowed_by_gel_cream(self) -> None:
        assert lookup("Гель для умывания с AHA") == "cleanser"

    def test_makeup_remover_milk(self) -> None:
        assert lookup("Молочко для снятия макияжа мягкое") == "cleanser"

    def test_single_word_key_needs_substring_not_tokens(self) -> None:
        # однословные ключи ищутся подстрокой; слова из разных ключей
        # не должны складываться в ложное совпадение
        assert lookup("dental-floss") is None

    def test_order_of_declaration_does_not_matter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # страховка на рост словаря: обобщённый ключ объявлен ПЕРВЫМ,
        # уточняющий — последним, выиграть должен уточняющий
        monkeypatch.setattr(
            category_map,
            "_ALL",
            {"крем": "skincare_active", "тональный крем": "base"},
        )
        assert lookup("крем тональный увлажняющий") == "base"


# ---------------------------------------------------------------------------
# pao_parser
# ---------------------------------------------------------------------------

class TestPaoParser:
    def test_months_short(self) -> None:
        assert parse_pao("12M") == 12

    def test_months_with_space(self) -> None:
        assert parse_pao("12 M") == 12

    def test_months_english(self) -> None:
        assert parse_pao("6 months") == 6

    def test_months_russian(self) -> None:
        assert parse_pao("12 мес") == 12

    def test_months_russian_full(self) -> None:
        assert parse_pao("6 месяцев") == 6

    def test_years_english(self) -> None:
        assert parse_pao("2 years") == 24

    def test_years_short(self) -> None:
        assert parse_pao("2Y") == 24

    def test_years_russian(self) -> None:
        assert parse_pao("3 года") == 36

    def test_combined(self) -> None:
        assert parse_pao("2 years 6 months") == 30

    def test_embedded_in_text(self) -> None:
        assert parse_pao("Срок годности после вскрытия: 12 мес.") == 12

    def test_none_input(self) -> None:
        assert parse_pao(None) is None

    def test_empty_string(self) -> None:
        assert parse_pao("") is None

    def test_no_pao_info(self) -> None:
        assert parse_pao("нет информации") is None

    def test_too_large_rejected(self) -> None:
        assert parse_pao("200M") is None


# ---------------------------------------------------------------------------
# inci_map
# ---------------------------------------------------------------------------

class TestInciMap:
    def test_exact_match(self) -> None:
        assert "niacinamide" in extract_actives("Water, Glycerin, Niacinamide")

    def test_synonym(self) -> None:
        assert "niacinamide" in extract_actives("Nicotinamide, Aqua")

    def test_vitamin_c_variants(self) -> None:
        codes = extract_actives("Ascorbic Acid, Sodium Ascorbyl Phosphate")
        assert codes.count("vitamin_c") == 1  # дедупликация

    def test_retinol_derivative(self) -> None:
        assert "retinol" in extract_actives("Retinyl Palmitate, Aqua")

    def test_ceramides(self) -> None:
        codes = extract_actives("Ceramide NP, Ceramide AP, Aqua")
        assert codes.count("ceramides") == 1

    def test_unknown_ingredient_ignored(self) -> None:
        assert extract_actives("Aqua, Glycerin, Parfum") == []

    def test_empty_string(self) -> None:
        assert extract_actives("") == []

    def test_order_preserved(self) -> None:
        codes = extract_actives("Niacinamide, Retinol, Hyaluronic Acid")
        assert codes == ["niacinamide", "retinol", "hyaluronic_acid"]

    def test_trailing_dot(self) -> None:
        # Некоторые источники добавляют точку в конце
        assert "retinol" in extract_actives("Retinol.")


# ---------------------------------------------------------------------------
# normalizer (интеграционный — все части вместе)
# ---------------------------------------------------------------------------

class TestNormalize:
    def _make(self, **kwargs) -> ScrapedProduct:
        defaults = dict(
            source="test",
            source_id="123",
            name="Test Product",
            raw_category="foundations",
        )
        return ScrapedProduct(**(defaults | kwargs))

    def test_product_type_resolved(self) -> None:
        result = normalize(self._make(raw_category="mascaras"))
        assert result.product_type is not None
        assert result.product_type.value == "decorative"

    def test_unknown_category_sets_needs_review(self) -> None:
        result = normalize(self._make(raw_category="unknown-stuff"))
        assert result.product_type is None
        assert result.needs_review is True

    def test_known_category_not_needs_review(self) -> None:
        result = normalize(self._make(raw_category="foundations"))
        assert result.needs_review is False

    def test_actives_extracted(self) -> None:
        result = normalize(self._make(ingredients_text="Niacinamide, Retinol, Aqua"))
        assert "niacinamide" in result.active_codes
        assert "retinol" in result.active_codes

    def test_pao_parsed(self) -> None:
        result = normalize(self._make(pao_raw="12M"))
        assert result.pao_months == 12

    def test_texture_from_name(self) -> None:
        result = normalize(self._make(name="Matte Powder Foundation", raw_category="foundations"))
        assert result.texture is not None
        assert result.texture.value == "powder"

    def test_finish_matte_from_name(self) -> None:
        result = normalize(self._make(name="Super Matte Serum", raw_category="serums"))
        assert result.finish is not None
        assert result.finish.value == "matte"

    def test_gtin_preserved(self) -> None:
        result = normalize(self._make(gtin="4607086565757"))
        assert result.gtin == "4607086565757"

    def test_source_saved_in_attributes(self) -> None:
        result = normalize(self._make(source="wildberries", source_id="999"))
        assert result.attributes["scraper_source"] == "wildberries"
        assert result.attributes["scraper_source_id"] == "999"

    def test_spf_passed_through(self) -> None:
        result = normalize(self._make(attributes_raw={"spf": 50, "vegan": True}))
        assert result.attributes["spf"] == 50
        assert result.attributes["vegan"] is True

    def test_name_stripped(self) -> None:
        result = normalize(self._make(name="  Foundation  "))
        assert result.name == "Foundation"

    def test_brand_stripped(self) -> None:
        result = normalize(self._make(brand="  L'Oréal  "))
        assert result.brand == "L'Oréal"
