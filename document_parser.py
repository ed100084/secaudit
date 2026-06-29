"""Document parsing helpers for uploaded audit framework source files."""
from pathlib import Path

import PyPDF2
from docx import Document as DocxDocument
from openpyxl import load_workbook


def parse_pdf(file_path: str) -> str:
    text_parts = []
    with open(file_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return "\n".join(text_parts)


def parse_docx(file_path: str) -> str:
    doc = DocxDocument(file_path)
    text_parts = []
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            text_parts.append(paragraph.text)
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells)
            if row_text.strip(" |"):
                text_parts.append(row_text)
    return "\n".join(text_parts)


def parse_xlsx(file_path: str) -> str:
    workbook = load_workbook(file_path, read_only=True, data_only=True)
    text_parts = []
    try:
        for sheet_name in workbook.sheetnames:
            worksheet = workbook[sheet_name]
            text_parts.append(f"=== {sheet_name} ===")
            for row in worksheet.iter_rows(values_only=True):
                row_text = " | ".join(str(cell) if cell is not None else "" for cell in row)
                if row_text.strip(" |"):
                    text_parts.append(row_text)
    finally:
        workbook.close()
    return "\n".join(text_parts)


def parse_file(file_path: str) -> str:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8")
    parsers = {
        ".pdf": parse_pdf,
        ".docx": parse_docx,
        ".xlsx": parse_xlsx,
        ".xls": parse_xlsx,
    }
    parser = parsers.get(suffix)
    if not parser:
        raise ValueError(f"不支援的檔案格式: {suffix}")
    return parser(str(path))