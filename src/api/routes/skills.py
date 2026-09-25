"""Public skill metadata (help-panel vocabulary)."""

from typing import Any

from fastapi import APIRouter, Query

from src.skills.vocabulary import help_catalog

router = APIRouter()


@router.get("/phrases")
async def skill_phrases(
    lang: str = Query(default="en", min_length=2, max_length=2),
) -> dict[str, Any]:
    """Return display trigger phrases per skill for one language (at least ten display phrases per skill; a skill's help key may combine several intent tables).

    Public: the help panel needs this before/without extra auth hops.
    """
    code = lang.lower()
    catalog = help_catalog(code)
    return {"lang": code if code in {"en", "de", "hu"} else "en", "skills": catalog}
