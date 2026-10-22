"""National thresholds of the Code de l'urbanisme, coded once.

Sources (checked 2026-10-22 against notary / commune / CAUE guides, not service-public.fr itself):
- extensions: DP 5-20 m2; up to 40 m2 in a U zone of a PLU; PC above. Architect if total floor area > 150 m2.
- annexes (shed, garage): DP 5-20 m2, PC above.
- uncovered pools: DP 10-100 m2, PC above; a cover higher than 1.80 m needs a PC.
- facade / roof changes (windows, solar panels): DP.
- forms: DP -> CERFA 16702 (since 2025-01-01), PC for a house -> CERFA 13406.
- review time: DP 1 month, PC (house) 2 months, +1 month near a historic monument (ABF opinion).
Verify on service-public.fr before relying on it; the 2026-07-27 simplification decree may move details.
"""

DP_FORM = "CERFA 16702 (déclaration préalable, constructions et travaux)"
PC_FORM = "CERFA 13406 (permis de construire, maison individuelle)"

PROJECT_TYPES = ["extension", "annex", "pool", "solar_roof", "facade_windows", "fence", "heat_pump"]


def check(project_type: str, area_m2: float = 0, existing_floor_area_m2: float = 0,
          zone_type: str = "U", has_plu: bool = True, protected: bool = False,
          pool_cover_height_m: float = 0) -> dict:
    """Return the authorisation the national code requires for a project."""
    reasons: list[str] = []
    auth = "none"
    a = float(area_m2 or 0)
    total = float(existing_floor_area_m2 or 0) + a
    urban_plu = has_plu and str(zone_type).upper().startswith("U")

    if project_type == "extension":
        if a < 5:
            auth = "declaration_prealable" if protected else "none"
            reasons.append("Under 5 m²: no authorisation, except in a protected area (then a déclaration préalable).")
        elif a <= 20:
            auth = "declaration_prealable"
            reasons.append("5–20 m² of new floor area: déclaration préalable.")
        elif a <= 40 and urban_plu:
            if total > 150:
                auth = "permis_de_construire"
                reasons.append("20–40 m² in a U zone would be a DP, but the house passes 150 m² in total: permis de construire.")
            else:
                auth = "declaration_prealable"
                reasons.append("20–40 m² in a U zone of a PLU: déclaration préalable.")
        else:
            auth = "permis_de_construire"
            reasons.append("Over 40 m² (or over 20 m² outside a U zone of a PLU): permis de construire.")
    elif project_type == "annex":
        if a < 5:
            auth = "declaration_prealable" if protected else "none"
            reasons.append("Annex under 5 m²: none, except in a protected area.")
        elif a <= 20:
            auth = "declaration_prealable"
            reasons.append("Annex 5–20 m²: déclaration préalable.")
        else:
            auth = "permis_de_construire"
            reasons.append("Annex over 20 m²: permis de construire.")
    elif project_type == "pool":
        if pool_cover_height_m > 1.8 and a > 10:
            auth = "permis_de_construire"
            reasons.append("Pool with a cover higher than 1.80 m: permis de construire.")
        elif a <= 10:
            auth = "declaration_prealable" if protected else "none"
            reasons.append("Pool up to 10 m²: none, except in a protected area.")
        elif a <= 100:
            auth = "declaration_prealable"
            reasons.append("Uncovered pool 10–100 m²: déclaration préalable.")
        else:
            auth = "permis_de_construire"
            reasons.append("Pool over 100 m²: permis de construire.")
    elif project_type in ("solar_roof", "facade_windows"):
        auth = "declaration_prealable"
        reasons.append("Changes the external appearance of the building: déclaration préalable.")
    elif project_type == "fence":
        auth = "declaration_prealable" if protected else "check_commune"
        reasons.append("Fences need a déclaration préalable in protected areas or where the commune requires it.")
    elif project_type == "heat_pump":
        auth = "declaration_prealable" if protected else "check_commune"
        reasons.append("Outdoor units usually need nothing, but a DP in protected areas or if visible on the facade.")
    else:
        return {"error": f"unknown project_type {project_type}; use one of {PROJECT_TYPES}"}

    architect = auth == "permis_de_construire" and total > 150
    months = {"declaration_prealable": 1, "permis_de_construire": 2}.get(auth, 0)
    if protected and months:
        months += 1
        reasons.append("Historic-monument surroundings: the Architecte des Bâtiments de France must give an opinion (+1 month).")
    return {
        "authorisation": auth,
        "form": {"declaration_prealable": DP_FORM, "permis_de_construire": PC_FORM}.get(auth),
        "review_time_months": months,
        "architect_required": architect,
        "total_floor_area_after_m2": total,
        "reasons": reasons,
        "source": "Code de l'urbanisme (R421-9 to R421-17); thresholds checked 2026-10-22, verify on service-public.fr",
    }
