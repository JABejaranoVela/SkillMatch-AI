from pathlib import Path


def extract_text_from_file(path: str) -> str:
    extension = Path(path).suffix.lower()
    if extension == ".pdf":
        return extract_text_from_pdf(path)
    if extension == ".docx":
        return extract_text_from_docx(path)
    raise ValueError(f"Formato no soportado: {extension}")


def extract_text_from_pdf(path: str) -> str:
    import fitz

    parts: list[str] = []
    with fitz.open(path) as document:
        for page in document:
            parts.append(page.get_text("text"))
    return "\n".join(parts)


def extract_text_from_docx(path: str) -> str:
    from docx import Document

    document = Document(path)
    return "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())

