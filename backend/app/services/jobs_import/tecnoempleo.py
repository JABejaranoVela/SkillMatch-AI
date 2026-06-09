import html
import re
import unicodedata
from datetime import datetime, timedelta
from urllib.parse import urljoin

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.job import Job
from app.services.jobs_import.upsert import load_existing_jobs, upsert_job
from app.services.nlp.skills import detect_skills

SOURCE = "tecnoempleo"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; SkillMatchAI/0.1; "
        "+https://localhost/academic-project)"
    )
}


def sync_tecnoempleo_jobs(db: Session, search_terms: list[str], limit: int | None = None) -> dict:
    max_records = limit or settings.PROFILE_JOB_IMPORT_LIMIT
    imported = 0
    updated = 0
    skipped = 0
    processed = 0
    seen_urls: set[str] = set()
    existing_jobs = load_existing_jobs(db, SOURCE)

    with httpx.Client(headers=HEADERS, timeout=25.0, follow_redirects=True) as client:
        for term in _search_terms_for_spain(search_terms):
            if processed >= max_records:
                break

            listing_url = f"{settings.TECNOEMPLEO_BASE_URL}/ofertas-trabajo/{_slug(term)}"
            response = client.get(listing_url)
            if response.status_code >= 400:
                skipped += 1
                continue

            for offer_url in _extract_offer_urls(_response_text(response)):
                if processed >= max_records:
                    break
                if offer_url in seen_urls:
                    continue
                seen_urls.add(offer_url)

                detail = _fetch_offer_detail(client, offer_url)
                if not detail:
                    skipped += 1
                    continue

                result = upsert_job(db, SOURCE, detail, existing_jobs)
                processed += 1
                if result == "imported":
                    imported += 1
                elif result == "updated":
                    updated += 1

    _normalize_existing_tecnoempleo_jobs(db)
    db.commit()
    return {
        "source": SOURCE,
        "search_terms": search_terms,
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "attribution": "Ofertas obtenidas desde Tecnoempleo, portal IT de empleo en España.",
    }


def _search_terms_for_spain(search_terms: list[str]) -> list[str]:
    priority = [
        "java spring boot",
        "desarrollador java",
        "programador java",
        "fullstack angular",
        "python",
        "typescript",
        "sql",
    ]
    normalized = [term.strip().lower() for term in search_terms if term and term.strip()]
    terms = normalized + priority

    unique_terms: list[str] = []
    for term in terms:
        if term and term not in unique_terms:
            unique_terms.append(term)
    return unique_terms[:6]


def _slug(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")


def _extract_offer_urls(html_text: str) -> list[str]:
    urls: list[str] = []
    pattern = r'href=["\']([^"\']+/rf-[^"\']+)["\']'
    for match in re.finditer(pattern, html_text, flags=re.I):
        url = urljoin(settings.TECNOEMPLEO_BASE_URL, html.unescape(match.group(1)))
        if url not in urls:
            urls.append(url)
    return urls[:20]


def _fetch_offer_detail(client: httpx.Client, url: str) -> dict | None:
    response = client.get(url)
    if response.status_code >= 400:
        return None

    raw_text = _response_text(response)
    text = _clean_html(raw_text)
    title = _extract_title(raw_text)
    if not title:
        return None

    description = _extract_description(text)
    salary_min, salary_max = _extract_salary(text)
    return {
        "external_id": _external_id(url),
        "title": title,
        "company": _extract_company(text, title),
        "description": description,
        "requirements": _build_requirements(description),
        "location": _extract_location(text),
        "modality": _infer_modality(text),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": "EUR" if salary_min or salary_max else None,
        "contract_type": _extract_contract_type(text),
        "published_at": _extract_published_at(text),
        "url": url,
    }


def _extract_title(raw_html: str) -> str | None:
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", raw_html, flags=re.I | re.S)
    if h1:
        return _clean_html(h1.group(1))

    title = re.search(r"<title[^>]*>(.*?)</title>", raw_html, flags=re.I | re.S)
    if not title:
        return None
    return _clean_html(title.group(1)).split(" - ")[0].strip()


def _extract_company(text: str, title: str) -> str | None:
    after = text.split(title, 1)
    if len(after) < 2:
        return None
    words = after[1].strip().split()
    value = " ".join(words[:4]).strip()
    return value[:120] or None


def _extract_description(text: str) -> str:
    description = text
    for marker in (
        "Descripcion de la oferta de empleo",
        "Descripción de la oferta de empleo",
        "Descripcion",
        "Descripción",
    ):
        if marker in text:
            description = text.split(marker, 1)[1]
            break

    for marker in (
        "Otros detalles de la oferta",
        "Datos principales de la oferta",
        "Nunca debes compartir",
    ):
        if marker in description:
            description = description.split(marker, 1)[0]

    return description.strip()[:3000] or text[:3000]


def _extract_location(text: str) -> str | None:
    patterns = [
        r"(Madrid(?:\s*\(Hibrido\)|\s*\(Híbrido\))?)",
        r"(Barcelona(?:\s*\(Hibrido\)|\s*\(Híbrido\))?)",
        r"(Malaga|Málaga|Sevilla|Valencia|Bilbao|Zaragoza|Alicante)",
        r"(100%\s*(?:remoto|En remoto))",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return match.group(1)
    return "España"


def _infer_modality(text: str) -> str:
    normalized = text.lower()
    if "100% remoto" in normalized or "100% en remoto" in normalized or "teletrabajo" in normalized:
        return "remoto"
    if "hibrido" in normalized or "híbrido" in normalized:
        return "hibrido"
    return "presencial/no indicada"


def _extract_salary(text: str) -> tuple[float | None, float | None]:
    range_match = re.search(
        r"(\d{2,3}(?:[.\s]\d{3})+)\s*(?:€|euros?)?\s*[-–a]\s*"
        r"(\d{2,3}(?:[.\s]\d{3})+)\s*(?:€|euros?)",
        text,
        flags=re.I,
    )
    if range_match:
        return _salary_number(range_match.group(1)), _salary_number(range_match.group(2))

    single_match = re.search(
        r"(?:salario|remuneraci[oó]n)[^\d]{0,20}(\d{2,3}(?:[.\s]\d{3})+)\s*(?:€|euros?)",
        text,
        flags=re.I,
    )
    if single_match:
        value = _salary_number(single_match.group(1))
        return value, value
    return None, None


def _salary_number(value: str) -> float:
    return float(re.sub(r"[.\s]", "", value))


def _extract_contract_type(text: str) -> str | None:
    normalized = text.lower()
    contract_types = (
        ("contrato indefinido", "Contrato indefinido"),
        ("indefinido", "Contrato indefinido"),
        ("contrato temporal", "Contrato temporal"),
        ("temporal", "Contrato temporal"),
        ("autónomo", "Autónomo"),
        ("autonomo", "Autónomo"),
        ("freelance", "Freelance"),
        ("prácticas", "Prácticas"),
        ("practicas", "Prácticas"),
    )
    for signal, label in contract_types:
        if signal in normalized:
            return label
    return None


def _extract_published_at(text: str) -> datetime | None:
    relative = re.search(r"publicad[ao]\s+hace\s+(\d+)\s+(hora|d[ií]a|semana)s?", text, flags=re.I)
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2).lower()
        if unit.startswith("hora"):
            return datetime.now() - timedelta(hours=amount)
        if unit.startswith(("día", "dia")):
            return datetime.now() - timedelta(days=amount)
        return datetime.now() - timedelta(weeks=amount)

    date_match = re.search(r"(?:publicad[ao]\s*(?:el)?\s*)(\d{1,2}/\d{1,2}/\d{4})", text, flags=re.I)
    if date_match:
        try:
            return datetime.strptime(date_match.group(1), "%d/%m/%Y")
        except ValueError:
            return None
    return None


def _build_requirements(description: str) -> str:
    detected = [skill["name"] for skill in detect_skills(description)]
    if detected:
        return ", ".join(detected)
    return "Requisitos no estructurados; revisar descripción de la oferta."


def _external_id(url: str) -> str:
    match = re.search(r"/rf-([^/?#]+)", url)
    return match.group(1) if match else url


def _clean_html(value: str) -> str:
    without_scripts = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", value, flags=re.I | re.S)
    without_tags = re.sub(r"<[^>]+>", " ", without_scripts)
    without_entities = html.unescape(without_tags)
    cleaned = re.sub(r"\s+", " ", without_entities).strip()
    return _fix_mojibake(cleaned)


def _response_text(response: httpx.Response) -> str:
    response.encoding = "utf-8"
    return response.text


def _fix_mojibake(value: str) -> str:
    replacements = {
        "Espa\uff83\uff71a": "España",
        "Descripci\uff83\uff73n": "Descripción",
        "descripci\uff83\uff73n": "descripción",
        "H\uff83\uff6dbrido": "Híbrido",
        "h\uff83\uff6dbrido": "híbrido",
        "M\uff83\uff61laga": "Málaga",
    }
    fixed = value
    for source, target in replacements.items():
        fixed = fixed.replace(source, target)
    if fixed != value:
        return fixed

    for encoding in ("cp932", "latin1"):
        try:
            return value.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return value


def _normalize_existing_tecnoempleo_jobs(db: Session) -> None:
    jobs = db.scalars(select(Job).where(Job.source == SOURCE)).all()
    for job in jobs:
        for field in ("title", "company", "description", "requirements", "location", "modality"):
            value = getattr(job, field)
            if isinstance(value, str):
                fixed = _fix_mojibake(value)
                if fixed != value:
                    setattr(job, field, fixed)
                    job.embedding = None
