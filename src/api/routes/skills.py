"""Public skill metadata (help-panel vocabulary)."""

from fastapi import APIRouter, Query

from src.skills.vocabulary import help_catalog

router = APIRouter()


@router.get("/phrases")
async def skill_phrases(
    lang: str = Query(default="en", min_length=2, max_length=2),
) -> dict:
    """Return the ten canonical trigger phrases per skill for one language.

    Public: the help panel needs this before/without extra auth hops.
    """
    code = lang.lower()
    catalog = help_catalog(code)
    return {"lang": code if code in {"en", "de", "hu"} else "en", "skills": catalog}
