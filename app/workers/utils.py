from datetime import datetime


def _build_progress(current: int, total: int, stage: str, message: str) -> dict:
    percent = 0 if total == 0 else int(current * 100 / total)
    return {
        "current": current,
        "total": total,
        "percent": percent,
        "stage": stage,
        "message": message,
        "lastUpdatedAt": datetime.utcnow().isoformat() + "Z",
    }
