from docx import Document
import re


def load_docx_text(file_path: str) -> str:
    """
    Load and clean text from a .docx file.

    Args:
        file_path (str): Path to the .docx file.

    Returns:
        str: Extracted and cleaned text.
    """
    document = Document(file_path)
    full_text = []

    for para in document.paragraphs:
        text = para.text.strip()
        if text:
            full_text.append(text)

    # Join and clean extra whitespace
    raw_text = "\n".join(full_text)
    cleaned_text = re.sub(r"\n{2,}", "\n\n", raw_text).strip()

    return cleaned_text
