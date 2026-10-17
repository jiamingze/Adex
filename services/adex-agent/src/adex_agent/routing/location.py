"""Consented turn context is transient observation, not user memory or a tool instruction."""

from datetime import datetime, timezone
import math
import re


def relevant(text):
    return bool(re.search(r"天气|下雨|气温|附近|周边|我这边|我这里|我在哪|当前位置", text))


def current_location(value, now=None):
    if not isinstance(value, dict) or value.get("source") not in ("manual", "device"):
        return None
    try:
        now = now or datetime.now(timezone.utc)
        observed = datetime.fromisoformat(value["observed_at"].replace("Z", "+00:00"))
        if observed.tzinfo is None or not -60 <= (now - observed).total_seconds() <= 900:
            return None
        result = {
            "source": value["source"],
            "label": str(value.get("label", ""))[:120],
            "observed_at": observed.isoformat(),
        }
        if value["source"] == "device":
            lat, lon = float(value["latitude"]), float(value["longitude"])
            if not math.isfinite(lat) or not math.isfinite(lon) or abs(lat) > 90 or abs(lon) > 180:
                return None
            result.update(latitude=round(lat, 2), longitude=round(lon, 2))
        elif not result["label"].strip():
            return None
        return result
    except (KeyError, ValueError, TypeError):
        return None
