from datetime import datetime

from app.services.jobs_import.infojobs import _normalize_offer
from app.services.jobs_import.tecnoempleo import (
    _extract_contract_type,
    _extract_published_at,
    _extract_salary,
)


def test_normalizes_infojobs_offer_metadata() -> None:
    offer = _normalize_offer(
        {
            "title": "Backend Developer",
            "description": "Desarrollo de APIs con Python y FastAPI.",
            "salaryMin": "35.000 €",
            "salaryMax": "45.000 €",
            "salaryCurrency": "EUR",
            "contractType": {"value": "Indefinido"},
            "published": "2026-06-08T10:30:00Z",
        },
        "offer-1",
    )

    assert offer is not None
    assert offer["salary_min"] == 35000.0
    assert offer["salary_max"] == 45000.0
    assert offer["contract_type"] == "Indefinido"
    assert offer["published_at"] == datetime(2026, 6, 8, 10, 30)


def test_extracts_tecnoempleo_offer_metadata() -> None:
    text = (
        "Oferta publicada el 08/06/2026. Contrato indefinido. "
        "Salario 30.000 € - 42.000 €."
    )

    assert _extract_salary(text) == (30000.0, 42000.0)
    assert _extract_contract_type(text) == "Contrato indefinido"
    assert _extract_published_at(text) == datetime(2026, 6, 8)
