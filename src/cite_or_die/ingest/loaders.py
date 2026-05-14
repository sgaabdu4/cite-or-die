from io import BytesIO
from pathlib import Path

from docx import Document
from pypdf import PdfReader


def load_document(filename: str, content_type: str, data: bytes) -> list[tuple[str, int | None]]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf" or content_type == "application/pdf":
        reader = PdfReader(BytesIO(data))
        return [
            (page.extract_text() or "", index + 1)
            for index, page in enumerate(reader.pages)
            if (page.extract_text() or "").strip()
        ]
    if suffix == ".docx":
        document = Document(BytesIO(data))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        return [(text, None)] if text.strip() else []
    text = data.decode("utf-8", errors="replace")
    return [(text, None)] if text.strip() else []
