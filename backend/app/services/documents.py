"""Download tender documents and extract their text (PDF, DOCX, and ZIPs containing those)."""

import io
import logging
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath

import httpx
import pymupdf
from docx import Document

logger = logging.getLogger(__name__)

MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024
MAX_PDF_PAGES = 300
# Protection against zip bombs: limit files and total uncompressed size.
MAX_ZIP_FILES = 20
MAX_ZIP_UNCOMPRESSED_BYTES = 80 * 1024 * 1024

SUPPORTED_FORMATS = {"pdf", "docx", "zip"}


class DocumentError(Exception):
    """A document couldn't be downloaded or read."""


@dataclass
class ExtractedDocument:
    title: str
    # Text of each page (PDF) or chunk of paragraphs (DOCX), in reading order.
    pages: list[str] = field(default_factory=list)

    @property
    def char_count(self) -> int:
        return sum(len(page) for page in self.pages)


def guess_format(filename: str, declared: str | None = None) -> str | None:
    if declared and declared.lower() in SUPPORTED_FORMATS:
        return declared.lower()
    suffix = PurePosixPath(filename.lower()).suffix.lstrip(".")
    return suffix if suffix in SUPPORTED_FORMATS else None


def download(client: httpx.Client, url: str, max_bytes: int = MAX_DOWNLOAD_BYTES) -> bytes:
    """Download a file, refusing anything larger than `max_bytes`."""
    try:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            declared = int(response.headers.get("content-length") or 0)
            if declared > max_bytes:
                raise DocumentError(f"File is too large ({declared // 1_048_576} MB)")
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    raise DocumentError("File is too large")
                chunks.append(chunk)
            return b"".join(chunks)
    except httpx.HTTPError as error:
        raise DocumentError(f"Download failed: {error}") from error


def extract_pdf(data: bytes) -> list[str]:
    try:
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            return [page.get_text() for page in pdf.pages(0, min(len(pdf), MAX_PDF_PAGES))]
    except (pymupdf.FileDataError, RuntimeError, ValueError) as error:
        raise DocumentError(f"Could not read PDF: {error}") from error


def extract_docx(data: bytes, paragraphs_per_chunk: int = 40) -> list[str]:
    try:
        document = Document(io.BytesIO(data))
    except Exception as error:  # python-docx raises a variety of errors for bad files
        raise DocumentError(f"Could not read DOCX: {error}") from error

    lines = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                lines.append(" | ".join(dict.fromkeys(cells)))  # merged cells repeat text
    return [
        "\n".join(lines[i : i + paragraphs_per_chunk])
        for i in range(0, len(lines), paragraphs_per_chunk)
    ]


def extract_zip(data: bytes) -> list[ExtractedDocument]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as error:
        raise DocumentError("Could not open ZIP file") from error

    members = [
        info
        for info in archive.infolist()
        if not info.is_dir() and guess_format(info.filename) in {"pdf", "docx"}
    ][:MAX_ZIP_FILES]
    if sum(info.file_size for info in members) > MAX_ZIP_UNCOMPRESSED_BYTES:
        raise DocumentError("ZIP contents are too large")

    documents = []
    for info in members:
        content = archive.read(info)
        try:
            pages = (
                extract_pdf(content)
                if info.filename.lower().endswith(".pdf")
                else extract_docx(content)
            )
        except DocumentError as error:
            logger.info("Skipping %s in ZIP: %s", info.filename, error)
            continue
        documents.append(ExtractedDocument(title=PurePosixPath(info.filename).name, pages=pages))
    return documents


def extract(data: bytes, title: str, file_format: str) -> list[ExtractedDocument]:
    """Extract text from a downloaded file. ZIPs can contain several documents."""
    if file_format == "pdf":
        return [ExtractedDocument(title=title, pages=extract_pdf(data))]
    if file_format == "docx":
        return [ExtractedDocument(title=title, pages=extract_docx(data))]
    if file_format == "zip":
        return extract_zip(data)
    raise DocumentError(f"Unsupported format: {file_format}")
