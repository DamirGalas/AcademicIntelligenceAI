"""Filter out public procurement PDFs based on keyword matching."""

from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.transform.filter.models import FilterResult

logger = get_logger("transform.filter.procurement")

# Phrases that strongly indicate public procurement documents.
# Both Cyrillic and Latin variants are included.
_KEYWORDS = [
    # Cyrillic
    "јавна набавка",
    "јавне набавке",
    "конкурсна документација",
    "позив за подношење понуда",
    "позив за подношење понуде",
    "обавештење о закљученом уговору",
    "обавештење о покретању",
    "понуђач",
    "набавка мале вредности",
    "окvirni споразум",
    "оквирни споразум",
    "преговарачки поступак",
    # Latin
    "javna nabavka",
    "javne nabavke",
    "konkursna dokumentacija",
    "poziv za podnošenje ponuda",
    "poziv za podnošenje ponude",
    "obaveštenje o zaključenom ugovoru",
    "obaveštenje o pokretanju",
    "ponuđač",
    "nabavka male vrednosti",
    "okvirni sporazum",
    "pregovarački postupak",
]

# How many distinct keywords must match to classify as procurement.
_MIN_KEYWORD_HITS = 2


def filter_procurement(result: FilterResult) -> FilterResult:
    """Check if a kept FilterResult is a public procurement document.

    Takes an already-filtered result (status='keep') and returns a new
    result with status='discard' and reason='procurement' if the text
    matches procurement keywords. Otherwise returns the original unchanged.
    """
    if result.status != "keep":
        return result

    text_lower = result.clean_text.lower()
    hits = sum(1 for kw in _KEYWORDS if kw in text_lower)

    if hits >= _MIN_KEYWORD_HITS:
        logger.debug("Procurement detected (%d keyword hits)", hits)
        return FilterResult(
            status="discard",
            reason="procurement",
            text_hash=result.text_hash,
            clean_text="",
            text_length=result.text_length,
        )

    return result
