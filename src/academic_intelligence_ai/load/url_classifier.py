"""
Classify documents by URL patterns and print a flat category breakdown table.
Temporary exploratory script — not part of the pipeline.
"""

import re
import sqlite3
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

DB_PATH = Path("data/academic.db")

SERBIAN_REPLACEMENTS = str.maketrans({
    "š": "s", "Š": "s",
    "č": "c", "Č": "c",
    "ć": "c", "Ć": "c",
    "đ": "d", "Đ": "d",
    "ž": "z", "Ž": "z",
})

STUDIJE_SEGMENTS = {
    "studije", "knjiga-predmeta", "predmeti", "nastavni-materijal", "osnovne",
    "master", "integrisane-akademske-studije", "nastava", "akreditacija",
    "studies", "study-programs", "nb-program", "turizam", "turizam-archive",
    "animacija-u-turizmu", "animacija-u-turizmu-cir", "upis",
}
VESTI_SEGMENTS = {"vesti", "obavestenja", "arhiva", "najave", "konkursi", "radionice", "dogadjaji"}
O_DEP_SEGMENTS = {
    "o-departmanu", "o-fakultetu", "o-nama", "katedra-za-turizam",
    "katedra-za-turizam-cir", "katedra-za-hotelijerstvo-cir",
    "katedra-za-geoekologiju-cir", "katedra-za-regionalnu-geografiju",
    "katedra-za-regionalnu-geografiju-cir", "hotelijerstvo-katedra",
    "gastronomija-katedra-cir", "drustvena-geografija", "drustvena-geografija-cir",
    "chair-of-tourism", "chair-of-hotel-management", "chair-of-social-geography",
    "chair-of-regional-geography", "chair-of-geo-ecology", "chair-of-gastronomy",
    "tourist-animation-and-ethno-tourism", "about-us",
    "about-the-department", "sekretarijat", "secretariat", "secretariate",
    "rukovodstvo", "kontakt", "contact", "nenastavno-osoblje-departmana",
    "international-relations", "alumni", "marketinski-tim", "saradnja-sa-privredom",
    "biblioteka-departmana", "akreditovani-studijski-programi",
    "rukovodioci-i-savetnici-na-studijskim-programima",
}
OSOBLJE_SEGMENTS = {"imenik", "knjiga-nastavnika"}
NAUKA_ISTR_SEGMENTS = {
    "nauka", "istrazivanja", "projekti", "research", "naukamediji",
    "medjunarodna-saradnja", "nauka-eng", "projects",
}


def normalize(segment: str) -> str:
    """Lowercase, transliterate Serbian chars, keep only a-z0-9, collapse hyphens."""
    segment = segment.lower().translate(SERBIAN_REPLACEMENTS)
    segment = re.sub(r"[^a-z0-9\-_]", "", segment)
    return re.sub(r"[\-_]+", "-", segment).strip("-")


def get_segments(url: str) -> list[str]:
    """Return normalized non-empty path segments, skipping segments with extensions."""
    try:
        path = urlparse(url).path
    except Exception:
        return []
    result = []
    for part in path.split("/"):
        part = part.strip()
        if not part or "." in part:
            continue
        n = normalize(part)
        if n and len(n) > 2:
            result.append(n)
    return result


DATE_BASED_RE = re.compile(r"/\d{4}/\d{2}/")
OSOBLJE_SLUG_RE = re.compile(r"/(dr-|prof-|docent|profesor|nastavnik|assistant)")
THESIS_FILE_RE = re.compile(
    r"(master.rad|diplomski.rad|doktorska.disertacija|diplomski_rad|master_rad"
    r"|[/_-]master[_\-\s]|[/_-]diplomski[_\-\s]|doktorske"
    r"|zavrsni.rad|zavrsni_rad|diplomsk.rad)",
    re.IGNORECASE,
)
STUDIJE_UPLOAD_PATHS = {"nastavni-materijal", "akreditacija", "nastava", "upis"}
DEPT_CODE_RE = re.compile(r"/uploads/\d{4}/(DF|DMI|DBE|DGTH|DH|DGT|DMI|PMF)/", re.IGNORECASE)
STUDIJE_FILENAME_RE = re.compile(r"(GODINA|godina|OAS-|MAS-|DAS-|nastavni.plan|plan.i.program|semestar)", re.IGNORECASE)

NABAVKE_SLUG_RE = re.compile(
    r"(oprema|odrzavanje|potrosni|rezervni|delovi|servisiranje|pribor|partijama"
    r"|nabavka|gradjevinski|popravke|tehnicke|dokumentacije|usluge-odrzavanja"
    r"|usluge|servis-)",
    re.IGNORECASE,
)
STUDENTI_SLUG_RE = re.compile(
    r"(obavestenje|konkurs|upis|budzet|skolarina|stipendij|ispitni|rokovi"
    r"|raspored|nastave|studente|studenata|prijemni|rang-lista"
    r"|prijemnog|pripremna|polaganje|rok-|rang-liste|izmena"
    r"|termini.ispita|studentskih.praksi|prakse|praksa)",
    re.IGNORECASE,
)
NAUKA_SLUG_RE = re.compile(
    r"(research|development|watertour|projekat|projekti|inovacij"
    r"|medjunarodn|international|conference|konferencij"
    r"|istrazivacka|razvoj|zivotne|voda-|karata|metoda|primena)",
    re.IGNORECASE,
)
VESTI_SLUG_RE = re.compile(
    r"(dijalog|kultura|vece|predavanje|seminar|radionica|simpozijum"
    r"|promocij|dodela|nagrada|izlozb|obiljezavanj)",
    re.IGNORECASE,
)
OSOBLJE_SLUG_WORDS_RE = re.compile(
    r"/(dr-|prof-|docent|profesor|nastavnik|assistant|saradnik|msc-|biografija)",
    re.IGNORECASE,
)
CYRILLIC_URL_RE = re.compile(r"(%d0%|%d1%|-cir/|-cir$|/sr_cyr/|/sr_cyr$)")
DBE_COURSE_FILE_RE = re.compile(r"/files/\d+/[a-z]{2,5}\d{3}", re.IGNORECASE)
DBE_CV_FILE_RE = re.compile(r"/files/\d+/cv[_\-]", re.IGNORECASE)

# DGT chair sub-pages with staff profiles
DGT_CHAIR_STAFF_RE = re.compile(
    r"/(gastronomija-katedra|geoekologija|katedra-lovni-turizam"
    r"|nastavnici-sa-drugih-visokoskolskih-ustanova)/\w",
    re.IGNORECASE,
)
# DGT/other EU and international research project slugs
DGT_PROJECT_RE = re.compile(
    r"/(clear-climate|creategreen|digingeoteach|digitour|geodigipract|interclim"
    r"|tourcomserbia|mekst|strength-\d{4}|pronacul|palmculture|lifedu|watertour"
    r"|egea-|cost-akcija|icb\d{4}|inkluzija-roma|improving-the-environment"
    r"|demografska-istrazivanja|natural-hazards|loess-research|odrzivi-i-ekoturizam"
    r"|geographic-information|geografski-informacioni|gis-dan)",
    re.IGNORECASE,
)


def classify(url: str) -> str:
    """Assign a single flat category label based on URL patterns."""
    seg_set = set(get_segments(url))

    # Pagination — no real content
    if "_page=" in url or re.search(r"/page/\d+", url):
        return "pagination-no-content"

    # Infrastructure
    if "download.php" in url:
        return "download-redirect"
    if "_extern" in url:
        return "external-microsite"
    if "wp-content" in url and "uploads" in url:
        # Theses: publikacije/ folder or thesis filename pattern
        if "/uploads/publikacije/" in url or THESIS_FILE_RE.search(url):
            return "student-theses-pdf"
        # Study documents: named sub-folders
        sub_path = url.split("/uploads/")[-1].split("/")[0].lower() if "/uploads/" in url else ""
        if sub_path in STUDIJE_UPLOAD_PATHS:
            return "study-documents-pdf"
        # Study program PDFs: dept code in path or studije filename pattern
        if DEPT_CODE_RE.search(url) or STUDIJE_FILENAME_RE.search(url):
            return "study-documents-pdf"
        return "misc-pdf-uploads"
    if "wp-content" in url:
        return "wp-infrastructure"

    # Science / publications
    if "pannonica" in url:
        return "journal-papers-pannonica"
    if "zbornik" in url:
        return "conference-proceedings"
    if "abstracts" in url:
        return "conference-abstracts"
    if "laboratorije" in url and "reference" in url:
        return "lab-reference-lists"
    if "publikacije" in seg_set:
        return "student-theses-html"
    if "dokumentacija" in seg_set:
        return "dgt-scientific-docs"

    # Content categories
    if seg_set & STUDIJE_SEGMENTS:
        return "study-programs"
    if seg_set & VESTI_SEGMENTS:
        return "news-announcements"
    if seg_set & O_DEP_SEGMENTS:
        return "department-info"
    if seg_set & OSOBLJE_SEGMENTS:
        return "staff-pages"
    if seg_set & NAUKA_ISTR_SEGMENTS:
        return "research-projects"
    if "javne-nabavke" in seg_set:
        return "public-procurement"

    # Professor/staff pages by slug pattern
    if OSOBLJE_SLUG_RE.search(url) or OSOBLJE_SLUG_WORDS_RE.search(url):
        return "staff-pages"

    # Cyrillic duplicate pages
    if CYRILLIC_URL_RE.search(url):
        return "cyrillic-duplicate"

    # Student-related pages without date
    if STUDENTI_SLUG_RE.search(url):
        return "news-announcements"

    # Old dbe site: /files/529/ are staff CVs
    if "/files/529/" in url:
        return "staff-pages"
    # Old dbe site: /files/N/cv_ are staff CVs
    if DBE_CV_FILE_RE.search(url):
        return "staff-pages"
    # Old dbe site: /files/N/XX000 pattern are course documents
    if DBE_COURSE_FILE_RE.search(url):
        return "study-documents-pdf"

    # Department chair pages (katedra-za- without specific segment match)
    if re.search(r"/katedra-za-", url):
        return "department-info"

    # DGT bachelor/master/doctoral study program pages (oas-/mas-/das- prefixes)
    if re.search(r"/(oas|mas|das)-[a-z]", url):
        return "study-programs"

    # DGT chair sub-pages with staff profiles
    if DGT_CHAIR_STAFF_RE.search(url):
        return "staff-pages"

    # Visiting professors / guest lecturers
    if seg_set & {"visiting-professors", "gostujuci-profesori", "professors"}:
        return "staff-pages"

    # EU/international research projects
    if DGT_PROJECT_RE.search(url):
        return "research-projects"

    # DGT cultural evening events and similar
    if re.search(r"-vece(/|$)|vece-sa-|-noc(/|$)|noc-biologije|noc_biologije", url, re.IGNORECASE):
        return "news-announcements"

    # SCALA project (dmi)
    if "scala" in seg_set:
        return "research-projects"

    # Known but unclassified patterns
    if "ipa" in seg_set:
        return "dmi-ipa-project"
    if "files" in seg_set:
        return "file-listing-pages"
    if "lafib" in seg_set:
        return "dh-lafib-lab"
    if "docs" in seg_set:
        return "docs-pages"
    if "tag" in seg_set:
        return "wordpress-tag-page"
    if "webservisi" in seg_set:
        return "dbe-web-services"

    # WordPress date-based posts — classify by slug keywords
    if DATE_BASED_RE.search(url):
        if NABAVKE_SLUG_RE.search(url):
            return "public-procurement"
        if STUDENTI_SLUG_RE.search(url):
            return "news-announcements"
        if NAUKA_SLUG_RE.search(url):
            return "research-projects"
        if VESTI_SLUG_RE.search(url):
            return "news-announcements"
        return "blog-post-unclassified"

    return "unclassified"


DESCRIPTIONS: dict[str, str] = {
    "study-programs":         "HTML pages about study programs, courses, enrollment",
    "study-documents-pdf":    "PDF files of study plans, curricula, course syllabi",
    "student-theses-pdf":     "PDF files of bachelor, master and doctoral theses",
    "student-theses-html":    "HTML listing pages of student theses (df dept)",
    "news-announcements":     "News, announcements, exam schedules, competitions",
    "department-info":        "About department/faculty pages, chairs, contacts",
    "staff-pages":            "Professor and staff profile pages",
    "research-projects":      "Research groups, projects, international cooperation",
    "public-procurement":     "Equipment procurement, maintenance, construction",
    "journal-papers-pannonica":"Scientific papers from Pannonica journal (geography)",
    "conference-proceedings": "Papers from conference proceedings (zbornik)",
    "conference-abstracts":   "Abstracts from conferences",
    "dgt-scientific-docs":    "dgt dept documentation (mostly scientific papers)",
    "lab-reference-lists":    "Bibliography/reference lists for lab equipment",
    "misc-pdf-uploads":       "Miscellaneous PDF uploads (conferences, bulletins, etc.)",
    "blog-post-unclassified": "WordPress date-based posts, content unclear from URL",
    "download-redirect":      "WordPress download.php redirect links, no real content",
    "external-microsite":     "External conference microsites hosted on dgt",
    "wp-infrastructure":      "WordPress infrastructure files (plugins, scripts)",
    "pagination-no-content":  "WordPress pagination pages (?_page=, /page/N/)",
    "cyrillic-duplicate":     "Cyrillic versions of pages (duplicates of Latin pages)",
    "file-listing-pages":     "Study program catalogs and staff CVs from old dbe site (/files/ URLs)",
    "dbe-unknown-segment":    "Pages with /529/ segment (dbe dept, purpose unclear)",
    "dmi-ipa-project":        "IPA project pages (dmi dept)",
    "wordpress-tag-page":     "WordPress tag archive pages",
    "dbe-web-services":       "Web service pages (dbe dept)",
    "dh-lafib-lab":           "LAFIB laboratory pages (dh chemistry dept)",
    "docs-pages":             "Pages with /docs/ segment",
    "unclassified":           "Not matched by any classification rule",
}


RELEVANT = {
    "study-programs",
    "news-announcements",
    "department-info",
    "study-documents-pdf",
    "staff-pages",
    "research-projects",
    "file-listing-pages",
}

MAYBE_RELEVANT = {
    "misc-pdf-uploads",
    "unclassified",
    "dh-lafib-lab",
    "docs-pages",
    "dbe-web-services",
}

NOT_RELEVANT = {
    "student-theses-pdf",
    "student-theses-html",
    "download-redirect",
    "journal-papers-pannonica",
    "pagination-no-content",
    "dgt-scientific-docs",
    "conference-proceedings",
    "cyrillic-duplicate",
    "external-microsite",
    "public-procurement",
    "wordpress-tag-page",
    "lab-reference-lists",
    "conference-abstracts",
    "wp-infrastructure",
    "dmi-ipa-project",
    "dbe-unknown-segment",
    "blog-post-unclassified",
}


def print_indexed_table(title: str, cats: dict[str, tuple[int, str]], total: int) -> None:
    """Print a table where cats maps category -> (count, relevance_label)."""
    subtotal = sum(n for n, _ in cats.values())
    print(f"\n{'=' * 105}")
    print(f"  {title}  --  {subtotal} docs  ({subtotal * 100 / total:.1f}%)")
    print(f"{'=' * 105}")
    print(f"  {'Category':<28} {'Count':>6}  {'%':<6}  {'Relevance':<10}  Description")
    print(f"  {'-' * 98}")
    for cat, (n, relevance) in sorted(cats.items(), key=lambda x: (-x[1][0],)):
        desc = DESCRIPTIONS.get(cat, "")
        print(f"  {cat:<28} {n:>6}  {n * 100 / total:<6.1f}  {relevance:<10}  {desc}")


def print_table(title: str, cats: dict[str, int], total: int) -> None:
    subtotal = sum(cats.values())
    print(f"\n{'=' * 105}")
    print(f"  {title}  --  {subtotal} docs  ({subtotal * 100 / total:.1f}%)")
    print(f"{'=' * 105}")
    print(f"  {'Category':<28} {'Count':>6}  {'%':<6}  Description")
    print(f"  {'-' * 98}")
    for cat, n in sorted(cats.items(), key=lambda x: -x[1]):
        desc = DESCRIPTIONS.get(cat, "")
        print(f"  {cat:<28} {n:>6}  {n * 100 / total:<6.1f}  {desc}")


def main():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT url FROM documents WHERE url IS NOT NULL AND url != ''"
    ).fetchall()
    conn.close()

    counts: Counter = Counter(classify(r[0]) for r in rows)
    total = sum(counts.values())
    print(f"Total documents: {total}")

    relevant = {c: n for c, n in counts.items() if c in RELEVANT}
    maybe = {c: n for c, n in counts.items() if c in MAYBE_RELEVANT}
    not_rel = {c: n for c, n in counts.items() if c in NOT_RELEVANT}
    other = {c: n for c, n in counts.items() if c not in RELEVANT | MAYBE_RELEVANT | NOT_RELEVANT}

    # Merge RELEVANT + MAYBE_RELEVANT into one table with relevance column
    combined = {}
    for cat, n in relevant.items():
        combined[cat] = (n, "High")
    for cat, n in maybe.items():
        combined[cat] = (n, "Medium")

    print_indexed_table("RELEVANT + MAYBE RELEVANT", combined, total)
    print_table("NOT RELEVANT", not_rel, total)
    if other:
        print_table("UNCATEGORIZED (check classify())", other, total)


if __name__ == "__main__":
    main()
