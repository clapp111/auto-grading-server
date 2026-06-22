import fitz  # PyMuPDF


# PDF.js 기본 렌더링 배율(96dpi) 기준으로 저장된 좌표를 가정.
# PDF 내부 좌표계(72dpi)로 변환하는 비율.
_SCREEN_TO_PDF = 72 / 96


def crop_region(pdf_bytes: bytes, page: int, x: int, y: int, w: int, h: int) -> bytes:
    """PDF에서 지정 region을 JPEG 바이트로 반환한다.

    page: 1-indexed 페이지 번호
    x, y, w, h: 프론트엔드 96dpi 기준 픽셀 좌표
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pdf_page = doc[page - 1]

    # 화면 픽셀 → PDF 포인트 변환
    px = x * _SCREEN_TO_PDF
    py = y * _SCREEN_TO_PDF
    pw = w * _SCREEN_TO_PDF
    ph = h * _SCREEN_TO_PDF

    clip = fitz.Rect(px, py, px + pw, py + ph)

    # 2x 업스케일로 OCR 인식률 향상
    mat = fitz.Matrix(2, 2)
    pixmap = pdf_page.get_pixmap(matrix=mat, clip=clip)
    return pixmap.tobytes("jpeg")
