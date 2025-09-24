from docx import Document


def read_docx(file_path):
    doc = Document(file_path)
    full_text = []

    for para in doc.paragraphs:
        if para.text.strip():  # пропускаємо пусті строки
            full_text.append(para.text.strip())

    return "\n".join(full_text)
