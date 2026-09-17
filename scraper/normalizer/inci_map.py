"""Маппинг INCI-имён ингредиентов в коды активов нашего каталога.

INCI (International Nomenclature of Cosmetic Ingredients) — международный стандарт.
Один active.code может соответствовать нескольким INCI-именам (синонимы, производные).

Источники для расширения словаря:
- https://incibeauty.com
- https://incidecoder.com
- Open Beauty Facts ingredient tagger
"""

from __future__ import annotations

import re

# INCI-имя (нижний регистр) → наш active.code
INCI_TO_CODE: dict[str, str] = {
    # ── Витамин C ──────────────────────────────────────────────────────────
    "ascorbic acid": "vitamin_c",
    "sodium ascorbyl phosphate": "vitamin_c",
    "ascorbyl glucoside": "vitamin_c",
    "magnesium ascorbyl phosphate": "vitamin_c",
    "ascorbyl tetraisopalmitate": "vitamin_c",
    "3-o-ethyl ascorbic acid": "vitamin_c",
    "ethyl ascorbic acid": "vitamin_c",
    # ── Ретиноиды ──────────────────────────────────────────────────────────
    "retinol": "retinol",
    "retinyl palmitate": "retinol",
    "retinyl acetate": "retinol",
    "retinaldehyde": "retinol",
    "retinal": "retinol",
    "hydroxypinacolone retinoate": "retinol",
    "granactive retinoid": "retinol",
    # ── Ниацинамид ─────────────────────────────────────────────────────────
    "niacinamide": "niacinamide",
    "nicotinamide": "niacinamide",
    "vitamin b3": "niacinamide",
    # ── Гиалуроновая кислота ───────────────────────────────────────────────
    "hyaluronic acid": "hyaluronic_acid",
    "sodium hyaluronate": "hyaluronic_acid",
    "hydrolyzed hyaluronic acid": "hyaluronic_acid",
    "sodium hyaluronate crosspolymer": "hyaluronic_acid",
    "potassium hyaluronate": "hyaluronic_acid",
    # ── Салициловая кислота (BHA) ──────────────────────────────────────────
    "salicylic acid": "salicylic_acid",
    "beta hydroxy acid": "salicylic_acid",
    # ── Гликолевая кислота (AHA) ───────────────────────────────────────────
    "glycolic acid": "glycolic_acid",
    "alpha hydroxy acid": "glycolic_acid",
    # ── Молочная кислота (AHA) ─────────────────────────────────────────────
    "lactic acid": "lactic_acid",
    "ammonium lactate": "lactic_acid",
    # ── Миндальная кислота (AHA) ───────────────────────────────────────────
    "mandelic acid": "mandelic_acid",
    # ── Пептиды ────────────────────────────────────────────────────────────
    "palmitoyl tripeptide-1": "peptides",
    "palmitoyl tripeptide-38": "peptides",
    "palmitoyl tetrapeptide-7": "peptides",
    "acetyl hexapeptide-3": "peptides",
    "acetyl hexapeptide-8": "peptides",
    "sh-oligopeptide-1": "peptides",
    "matrixyl": "peptides",
    "argireline": "peptides",
    # ── Азелаиновая кислота ────────────────────────────────────────────────
    "azelaic acid": "azelaic_acid",
    # ── Транексамовая кислота ──────────────────────────────────────────────
    "tranexamic acid": "tranexamic_acid",
    # ── Феруловая кислота ──────────────────────────────────────────────────
    "ferulic acid": "ferulic_acid",
    # ── Центелла ───────────────────────────────────────────────────────────
    "centella asiatica extract": "centella",
    "asiaticoside": "centella",
    "madecassoside": "centella",
    "asiatic acid": "centella",
    "madecassic acid": "centella",
    # ── Ниацинамид-соседи (не путать) ─────────────────────────────────────
    "panthenol": "panthenol",
    "provitamin b5": "panthenol",
    "dexpanthenol": "panthenol",
    # ── Бакучиол (растительный ретинол-аналог) ─────────────────────────────
    "bakuchiol": "bakuchiol",
    # ── Резвератрол ────────────────────────────────────────────────────────
    "resveratrol": "resveratrol",
    # ── Коллаген ───────────────────────────────────────────────────────────
    "hydrolyzed collagen": "collagen",
    "soluble collagen": "collagen",
    "collagen": "collagen",
    # ── Церамиды ───────────────────────────────────────────────────────────
    "ceramide np": "ceramides",
    "ceramide ap": "ceramides",
    "ceramide eop": "ceramides",
    "ceramide ng": "ceramides",
    "ceramide eg": "ceramides",
    "ceramide 1": "ceramides",
    "ceramide 2": "ceramides",
    "ceramide 3": "ceramides",
    "ceramide 6 ii": "ceramides",
    # ── SPF-фильтры (UV) ───────────────────────────────────────────────────
    "zinc oxide": "zinc_oxide",
    "titanium dioxide": "titanium_dioxide",
    "avobenzone": "chemical_spf",
    "octinoxate": "chemical_spf",
    "octocrylene": "chemical_spf",
    "homosalate": "chemical_spf",
    "octisalate": "chemical_spf",
    "oxybenzone": "chemical_spf",
    # ── Масла ──────────────────────────────────────────────────────────────
    "rosehip oil": "rosehip_oil",
    "rosa canina fruit oil": "rosehip_oil",
    "rosa rubiginosa seed oil": "rosehip_oil",
    "jojoba seed oil": "jojoba_oil",
    "simmondsia chinensis seed oil": "jojoba_oil",
    "argan oil": "argan_oil",
    "argania spinosa kernel oil": "argan_oil",
    "squalane": "squalane",
    "squalene": "squalane",
}


# ── Аллергены отдушек, декларируемые по Регламенту ЕС 1223/2009 (Приложение III) ──
# Эти 26 веществ производитель обязан указывать в составе отдельно — именно потому,
# что они вызывают контактную аллергию. Для продукта, который проверяет аллергены,
# они важнее списка активов: в реальных составах OBF linalool встретился 406 раз,
# limonene — 395, и ни один из них словарь не знал.
# Коды намеренно раздельные: аллергия на лимонен не означает аллергию на линалоол.
INCI_TO_CODE.update({
    "amyl cinnamal": "amyl_cinnamal",
    "amylcinnamyl alcohol": "amylcinnamyl_alcohol",
    "anise alcohol": "anise_alcohol",
    "benzyl alcohol": "benzyl_alcohol",
    "benzyl benzoate": "benzyl_benzoate",
    "benzyl cinnamate": "benzyl_cinnamate",
    "benzyl salicylate": "benzyl_salicylate",
    "butylphenyl methylpropional": "butylphenyl_methylpropional",  # Lilial
    "lilial": "butylphenyl_methylpropional",
    "cinnamal": "cinnamal",
    "cinnamyl alcohol": "cinnamyl_alcohol",
    "citral": "citral",
    "citronellol": "citronellol",
    "coumarin": "coumarin",
    "eugenol": "eugenol",
    "farnesol": "farnesol",
    "geraniol": "geraniol",
    "hexyl cinnamal": "hexyl_cinnamal",
    "hydroxycitronellal": "hydroxycitronellal",
    "hydroxyisohexyl 3-cyclohexene carboxaldehyde": "hicc",
    "lyral": "hicc",
    "isoeugenol": "isoeugenol",
    "limonene": "limonene",
    "d-limonene": "limonene",
    "linalool": "linalool",
    "methyl 2-octynoate": "methyl_2_octynoate",
    "alpha-isomethyl ionone": "alpha_isomethyl_ionone",
    "evernia prunastri extract": "oakmoss",
    "evernia prunastri": "oakmoss",
    "evernia furfuracea extract": "treemoss",
    "evernia furfuracea": "treemoss",
})

# Коды аллергенов отдушек — отдельно, чтобы отличать их от активов:
# активы участвуют в правилах конфликтов, аллергены — только в проверке аллергии.
FRAGRANCE_ALLERGEN_CODES: frozenset[str] = frozenset({
    "amyl_cinnamal", "amylcinnamyl_alcohol", "anise_alcohol", "benzyl_alcohol",
    "benzyl_benzoate", "benzyl_cinnamate", "benzyl_salicylate",
    "butylphenyl_methylpropional", "cinnamal", "cinnamyl_alcohol", "citral",
    "citronellol", "coumarin", "eugenol", "farnesol", "geraniol", "hexyl_cinnamal",
    "hydroxycitronellal", "hicc", "isoeugenol", "limonene", "linalool",
    "methyl_2_octynoate", "alpha_isomethyl_ionone", "oakmoss", "treemoss",
})


def split_ingredients(ingredients_text: str) -> list[str]:
    """Режет INCI-строку на отдельные ингредиенты и приводит их к виду словаря.

    Живые составы устроены грязнее, чем «через запятую»:
      - скобки с индексом красителя: "Titanium Dioxide (CI 77891)";
      - регистр гуляет вплоть до полностью заглавного (Topface);
      - разделителем бывает перевод строки или несколько пробелов (FRENCHI);
      - у многосекционных товаров составов несколько подряд, иногда с маркерами
        плиток "[a-1]", иногда без них вовсе;
      - хвост "может содержать" / "+/-" перечисляет красители всех оттенков линейки.
    """
    if not ingredients_text:
        return []

    text = ingredients_text.lower()
    # Хвост возможных красителей — это не состав конкретного товара.
    text = re.split(r"может содержать|may contain|\+/-|\+\s*/\s*-", text)[0]
    text = re.sub(r"\[[a-z]?-?\d+\]", " ", text)   # маркеры плиток палетки
    text = re.sub(r"\([^)]*\)", " ", text)          # скобки: (CI 77891), (Water)

    parts = re.split(r"[,;\n\u2022]+|\s{2,}", text)
    out: list[str] = []
    for part in parts:
        token = re.sub(r"\s+", " ", part).strip(" .*[]•-")
        if 2 < len(token) < 60:
            out.append(token)
    return out


def extract_actives(ingredients_text: str) -> list[str]:
    """Парсит INCI-строку ингредиентов, возвращает дедуплицированные коды активов."""
    seen: set[str] = set()
    result: list[str] = []
    for token in split_ingredients(ingredients_text):
        code = INCI_TO_CODE.get(token)
        if code and code not in seen:
            seen.add(code)
            result.append(code)
    return result
