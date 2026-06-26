from datetime import datetime, timezone


def _build_progress(current: int, total: int, stage: str, message: str) -> dict:
    percent = 0 if total == 0 else int(current * 100 / total)
    return {
        "current": current,
        "total": total,
        "percent": percent,
        "stage": stage,
        "message": message,
        "lastUpdatedAt": datetime.now(timezone.utc).isoformat(),
    }
