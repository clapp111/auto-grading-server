from datetime import datetime, timezone


def _build_progress(current: int, total: int, stage: str, message: str) -> dict:
    """잡 진행률(progress_json) 딕셔너리를 만든다.

    `total`이 0이면 percent를 0으로 둔다.

    Args:
        current: 현재까지 처리한 항목 수
        total: 전체 처리 대상 수
        stage: 현재 처리 단계 이름 (예: OCR, APPLYING)
        message: 사용자에게 노출할 진행 메시지

    Returns:
        current·total·percent·stage·message·lastUpdatedAt를 담은 진행률 딕셔너리
    """
    percent = 0 if total == 0 else int(current * 100 / total)
    return {
        "current": current,
        "total": total,
        "percent": percent,
        "stage": stage,
        "message": message,
        "lastUpdatedAt": datetime.now(timezone.utc).isoformat(),
    }
