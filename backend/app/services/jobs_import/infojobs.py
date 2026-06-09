import html
import re
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.jobs_import.upsert import load_existing_jobs, upsert_job
from app.services.nlp.skills import detect_skills

SOURCE = "infojobs"


def sync_infojobs_jobs(db: Session, search_terms: list[str], limit: int | None = None) -> dict:
    if not settings.INFOJOBS_CLIENT_ID or not settings.INFOJOBS_CLIENT_SECRET:
        return {
            "source": SOURCE,
            "search_terms": search_terms,
            "imported": 0,
            "updated": 0,
            "skipped": 1,
            "attribution": "InfoJobs omitido: faltan INFOJOBS_CLIENT_ID e INFOJOBS_CLIENT_SECRET.",
        }

    max_records = limit or settings.PROFILE_JOB_IMPORT_LIMIT
    imported = 0
    updated = 0
    skipped = 0
    processed = 0
    seen_ids: set[str] = set()
    existing_jobs = load_existing_jobs(db, SOURCE)

    auth = (settings.INFOJOBS_CLIENT_ID, settings.INFOJOBS_CLIENT_SECRET)
    headers = {"Accept": "application/json"}
    with httpx.Client(auth=auth, headers=headers, timeout=18.0, follow_redirects=True) as client:
        for term in _search_terms(search_terms):
            if processed >= max_records:
                break
            response = client.get(settings.INFOJOBS_API_URL, params={"q": term, "maxResults": max_records})
            if response.status_code >= 400:
                skipped += 1
                continue

            for item in _items(response.json()):
                if processed >= max_records:
                    break
                external_id = str(item.get("id") or item.get("offerId") or "").strip()
                if not external_id or external_id in seen_ids:
                    skipped += 1
                    continue
                seen_ids.add(external_id)

                detail_payload = _fetch_detail(client, external_id) or item
                detail = _normalize_offer(detail_payload, external_id)
                if not detail:
                    skipped += 1
                    continue

                result = upsert_job(db, SOURCE, detail, existing_jobs)
                processed += 1
                if result == "imported":
                    imported += 1
                elif result == "updated":
                    updated += 1

    db.commit()
    return {
        "source": SOURCE,
        "search_terms": search_terms,
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "attribution": "Ofertas obtenidas desde InfoJobs mediante API oficial.",
    }


def _search_terms(search_terms: list[str]) -> list[str]:
    fallback = ["java", "python", "angular", "backend", "full stack"]
    terms = [term.strip().lower() for term in search_terms if term and term.strip()] + fallback
    unique_terms: list[str] = []
    for term in terms:
        if term not in unique_terms:
            unique_terms.append(term)
    return unique_terms[:5]


def _items(payload: Any) -> list[dict]:
    if isinstance(payload, dict):
        raw_items = payload.get("items") or payload.get("offers") or payload.get("data") or []
        return [item for item in raw_items if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _fetch_detail(client: httpx.Client, external_id: str) -> dict | None:
    detail_url = f"{settings.INFOJOBS_API_URL.rstrip('/')}/{external_id}"
    response = client.get(detail_url)
    if response.status_code >= 400:
        return None
    payload = response.json()
    return payload if isinstance(payload, dict) else None


def _normalize_offer(payload: dict, external_id: str) -> dict | None:
    title = _clean(_first(payload, "title", "jobTitle", "name"))
    if not title:
        return None

    description = _clean(_first(payload, "description", "profileDescription", "summary", "requirementMin"))
    requirements = _build_requirements(description)
    link = _extract_url(payload)
    salary_min, salary_max, salary_currency = _salary(payload)

    return {
        "external_id": external_id,
        "title": title[:255],
        "company": _clean(_company(payload)),
        "description": description or title,
        "requirements": requirements,
        "location": _clean(_location(payload)) or "España",
        "modality": _infer_modality(payload, description),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": salary_currency,
        "contract_type": _clean(_dictionary_value(payload.get("contractType"))) or None,
        "published_at": _parse_datetime(
            _first(payload, "published", "publicationDate", "publishedAt", "date")
        ),
        "url": link,
    }


def _first(payload: dict, *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _company(payload: dict) -> str | None:
    author = payload.get("author") or payload.get("company")
    if isinstance(author, dict):
        return _first(author, "name", "companyName")
    return author if isinstance(author, str) else None


def _location(payload: dict) -> str | None:
    city = payload.get("city")
    province = payload.get("province")
    if isinstance(city, str) and isinstance(province, dict):
        province_name = province.get("value") or province.get("name")
        return f"{city}, {province_name}" if province_name else city
    if isinstance(city, str):
        return city
    if isinstance(province, dict):
        return province.get("value") or province.get("name")
    return province if isinstance(province, str) else None


def _extract_url(payload: dict) -> str | None:
    for key in ("link", "url", "uri"):
        value = payload.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value
    return None


def _dictionary_value(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("value", "name", "label"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
    return value if isinstance(value, str) else None


def _salary(payload: dict) -> tuple[float | None, float | None, str | None]:
    minimum = _number(payload, "salaryMin", "minPay", "minimumSalary")
    maximum = _number(payload, "salaryMax", "maxPay", "maximumSalary")
    currency = _first(payload, "salaryCurrency", "currency") or ("EUR" if minimum or maximum else None)
    return minimum, maximum, currency


def _number(payload: dict, *keys: str) -> float | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            normalized = re.sub(r"[^\d,.-]", "", value).replace(".", "").replace(",", ".")
            try:
                return float(normalized)
            except ValueError:
                continue
    return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    except ValueError:
        pass
    for date_format in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:10], date_format)
        except ValueError:
            continue
    return None


def _infer_modality(payload: dict, description: str) -> str:
    combined = " ".join(
        str(value)
        for value in [
            payload.get("teleworking"),
            payload.get("workDay"),
            payload.get("contractType"),
            description,
        ]
        if value
    ).lower()
    if "remoto" in combined or "teletrabajo" in combined or "remote" in combined:
        return "remoto"
    if "híbrido" in combined or "hibrido" in combined or "hybrid" in combined:
        return "hibrido"
    return "presencial/no indicada"


def _build_requirements(description: str) -> str:
    detected = [skill["name"] for skill in detect_skills(description)]
    if detected:
        return ", ".join(detected)
    return "Requisitos no estructurados; revisar descripción de la oferta."


def _clean(value: str | None) -> str:
    if not value:
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", value)
    without_entities = html.unescape(without_tags)
    return re.sub(r"\s+", " ", without_entities).strip()
