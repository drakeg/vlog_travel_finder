from __future__ import annotations

import time
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from .settings_service import get_setting


@dataclass(frozen=True)
class LatestVideo:
    video_id: str
    title: str

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"

    @property
    def thumbnail_url(self) -> str:
        return f"https://i.ytimg.com/vi/{self.video_id}/hqdefault.jpg"

    @property
    def embed_url(self) -> str:
        return f"https://www.youtube.com/embed/{self.video_id}"


_CACHE: dict[str, tuple[float, LatestVideo | None]] = {}
_CACHE_TTL_SECONDS = 300


def _extract_channel_id(channel_value: str | None) -> str | None:
    raw = (channel_value or "").strip()
    if not raw:
        return None

    if raw.startswith("UC") and " " not in raw and "/" not in raw:
        return raw

    try:
        parsed = urlparse(raw)
    except Exception:
        return None

    path = (parsed.path or "").strip("/")
    parts = [p for p in path.split("/") if p]
    # Expect /channel/<UC...>
    if len(parts) >= 2 and parts[0] == "channel" and parts[1].startswith("UC"):
        return parts[1]

    return None


def _fetch_rss(channel_id: str) -> str:
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "vlog-site/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _parse_latest_video(rss_xml: str) -> LatestVideo | None:
    try:
        root = ET.fromstring(rss_xml)
    except Exception:
        return None

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
    }

    entry = root.find("atom:entry", ns)
    if entry is None:
        return None

    video_id_el = entry.find("yt:videoId", ns)
    title_el = entry.find("atom:title", ns)
    video_id = (video_id_el.text or "").strip() if video_id_el is not None else ""
    title = (title_el.text or "").strip() if title_el is not None else ""

    if not video_id:
        return None

    return LatestVideo(video_id=video_id, title=title or "Latest video")


def get_latest_video(*, db: Session) -> LatestVideo | None:
    channel_id = _extract_channel_id(get_setting(db, "youtube_channel"))
    if not channel_id:
        return None

    now = time.time()
    cached = _CACHE.get(channel_id)
    if cached is not None:
        cached_at, value = cached
        if now - cached_at < _CACHE_TTL_SECONDS:
            return value

    try:
        rss = _fetch_rss(channel_id)
        latest = _parse_latest_video(rss)
    except Exception:
        latest = None

    _CACHE[channel_id] = (now, latest)
    return latest
