import fitz  # PyMuPDF


def crop_region(pdf_bytes: bytes, page: int, x: float, y: float, w: float, h: float) -> bytes:
    """PDF에서 지정 region을 JPEG 바이트로 반환한다.

    page: 1-indexed 페이지 번호
    x, y, w, h: 정규화 좌표 (0.0~1.0), 페이지 크기 기준 비율
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pdf_page = doc[page - 1]

    pw_pt = pdf_page.rect.width
    ph_pt = pdf_page.rect.height

    clip = fitz.Rect(
        x * pw_pt,
        y * ph_pt,
        (x + w) * pw_pt,
        (y + h) * ph_pt,
    )

    # 2x 업스케일로 OCR 인식률 향상
    mat = fitz.Matrix(2, 2)
    pixmap = pdf_page.get_pixmap(matrix=mat, clip=clip)
    return pixmap.tobytes("jpeg")
