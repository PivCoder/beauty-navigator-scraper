"""Маппинг INCI-имён ингредиентов в коды активов нашего каталога.

INCI (International Nomenclature of Cosmetic Ingredients) — международный стандарт.
Один active.code может соответствовать нескольким INCI-именам (синонимы, производные).

Источники для расширения словаря:
- https://incibeauty.com
- https://incidecoder.com
- Open Beauty Facts ingredient tagger
"""

from __future__ import annotations

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


def extract_actives(ingredients_text: str) -> list[str]:
    """Парсит INCI-строку ингредиентов, возвращает дедуплицированные коды активов."""
    if not ingredients_text:
        return []
    tokens = [t.strip().lower().rstrip(".") for t in ingredients_text.split(",")]
    seen: set[str] = set()
    result: list[str] = []
    for token in tokens:
        code = INCI_TO_CODE.get(token)
        if code and code not in seen:
            seen.add(code)
            result.append(code)
    return result
