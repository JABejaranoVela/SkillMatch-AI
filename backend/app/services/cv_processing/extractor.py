from pathlib import Path


class CvValidationError(ValueError):
    pass


def extract_text_from_file(
    path: str,
    *,
    max_pages: int | None = None,
    min_text_chars: int | None = None,
) -> str:
    extension = Path(path).suffix.lower()
    if extension == ".pdf":
        return extract_text_from_pdf(
            path,
            max_pages=max_pages,
            min_text_chars=min_text_chars,
        )
    raise CvValidationError("Tipo de archivo no permitido. Sube un PDF.")


def extract_text_from_pdf(
    path: str,
    *,
    max_pages: int | None = None,
    min_text_chars: int | None = None,
) -> str:
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise CvValidationError("El PDF está protegido o no se puede leer.") from exc
    return extract_text_from_pdf_bytes(
        data,
        max_pages=max_pages,
        min_text_chars=min_text_chars,
    )


def extract_text_from_pdf_bytes(
    data: bytes,
    *,
    max_pages: int | None = None,
    min_text_chars: int | None = None,
) -> str:
    import fitz

    if not data.startswith(b"%PDF-"):
        raise CvValidationError("El archivo no contiene un PDF válido.")

    try:
        with fitz.open(stream=data, filetype="pdf") as document:
            if document.needs_pass or document.is_encrypted:
                raise CvValidationError("El PDF está protegido o no se puede leer.")
            if document.page_count <= 0:
                raise CvValidationError("El archivo no contiene un PDF válido.")
            if max_pages is not None and document.page_count > max_pages:
                raise CvValidationError(f"El PDF supera el máximo de {max_pages} páginas.")
            text = "\n".join(page.get_text("text") for page in document)
    except CvValidationError:
        raise
    except Exception as exc:
        raise CvValidationError("El PDF está protegido o no se puede leer.") from exc

    if min_text_chars is not None and len(" ".join(text.split())) < min_text_chars:
        raise CvValidationError("No se ha podido extraer suficiente texto del PDF.")
    return text


def extract_text_from_docx(_path: str) -> str:
    raise CvValidationError("Tipo de archivo no permitido. Sube un PDF.")
