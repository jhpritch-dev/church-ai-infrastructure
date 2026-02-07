"""
Lectionary Service - RCL Readings with 4-tier offline-first lookup.
Tiers: Redis cache -> local JSON -> LectServe API -> built-in Year A data.
"""

import json
import logging
import os
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Optional, Any, List

logger = logging.getLogger(__name__)

# -- Built-in Year A readings (RCL) --
# Ordered list: most specific patterns first to avoid substring collisions
BUILTIN_YEAR_A = [
    # Advent
    ("The First Sunday of Advent", {
        "first_lesson": "Isaiah 2:1-5",
        "psalm": "Psalm 122",
        "second_lesson": "Romans 13:11-14",
        "gospel": "Matthew 24:36-44",
    }),
    ("The Second Sunday of Advent", {
        "first_lesson": "Isaiah 11:1-10",
        "psalm": "Psalm 72:1-7, 18-19",
        "second_lesson": "Romans 15:4-13",
        "gospel": "Matthew 3:1-12",
    }),
    ("The Third Sunday of Advent", {
        "first_lesson": "Isaiah 35:1-10",
        "psalm": "Psalm 146:4-9 or Canticle 15",
        "second_lesson": "James 5:7-10",
        "gospel": "Matthew 11:2-11",
    }),
    ("The Fourth Sunday of Advent", {
        "first_lesson": "Isaiah 7:10-16",
        "psalm": "Psalm 80:1-7, 16-18",
        "second_lesson": "Romans 1:1-7",
        "gospel": "Matthew 1:18-25",
    }),
    # Christmas
    ("Christmas", {
        "first_lesson": "Isaiah 9:2-7",
        "psalm": "Psalm 96",
        "second_lesson": "Titus 2:11-14",
        "gospel": "Luke 2:1-20",
    }),
    # Epiphany
    ("The Epiphany", {
        "first_lesson": "Isaiah 60:1-6",
        "psalm": "Psalm 72:1-7, 10-14",
        "second_lesson": "Ephesians 3:1-12",
        "gospel": "Matthew 2:1-12",
    }),
    ("The First Sunday after the Epiphany", {
        "first_lesson": "Isaiah 42:1-9",
        "psalm": "Psalm 29",
        "second_lesson": "Acts 10:34-43",
        "gospel": "Matthew 3:13-17",
    }),
    ("The Second Sunday after the Epiphany", {
        "first_lesson": "Isaiah 49:1-7",
        "psalm": "Psalm 40:1-12",
        "second_lesson": "1 Corinthians 1:1-9",
        "gospel": "John 1:29-42",
    }),
    ("The Third Sunday after the Epiphany", {
        "first_lesson": "Isaiah 9:1-4",
        "psalm": "Psalm 27:1, 5-13",
        "second_lesson": "1 Corinthians 1:10-18",
        "gospel": "Matthew 4:12-23",
    }),
    ("The Fourth Sunday after the Epiphany", {
        "first_lesson": "Micah 6:1-8",
        "psalm": "Psalm 15",
        "second_lesson": "1 Corinthians 1:18-31",
        "gospel": "Matthew 5:1-12",
    }),
    ("The Fifth Sunday after the Epiphany", {
        "first_lesson": "Isaiah 58:1-9a",
        "psalm": "Psalm 112:1-9",
        "second_lesson": "1 Corinthians 2:1-12",
        "gospel": "Matthew 5:13-20",
    }),
    ("The Sixth Sunday after the Epiphany", {
        "first_lesson": "Deuteronomy 30:15-20",
        "psalm": "Psalm 119:1-8",
        "second_lesson": "1 Corinthians 3:1-9",
        "gospel": "Matthew 5:21-37",
    }),
    ("The Seventh Sunday after the Epiphany", {
        "first_lesson": "Leviticus 19:1-2, 9-18",
        "psalm": "Psalm 119:33-40",
        "second_lesson": "1 Corinthians 3:10-11, 16-23",
        "gospel": "Matthew 5:38-48",
    }),
    ("The Last Sunday after the Epiphany", {
        "first_lesson": "Exodus 24:12-18",
        "psalm": "Psalm 2 or Psalm 99",
        "second_lesson": "2 Peter 1:16-21",
        "gospel": "Matthew 17:1-9",
    }),
    # Lent
    ("The First Sunday in Lent", {
        "first_lesson": "Genesis 2:15-17; 3:1-7",
        "psalm": "Psalm 32",
        "second_lesson": "Romans 5:12-19",
        "gospel": "Matthew 4:1-11",
    }),
    ("The Second Sunday in Lent", {
        "first_lesson": "Genesis 12:1-4a",
        "psalm": "Psalm 121",
        "second_lesson": "Romans 4:1-5, 13-17",
        "gospel": "John 3:1-17",
    }),
    ("The Third Sunday in Lent", {
        "first_lesson": "Exodus 17:1-7",
        "psalm": "Psalm 95",
        "second_lesson": "Romans 5:1-11",
        "gospel": "John 4:5-42",
    }),
    ("The Fourth Sunday in Lent", {
        "first_lesson": "1 Samuel 16:1-13",
        "psalm": "Psalm 23",
        "second_lesson": "Ephesians 5:8-14",
        "gospel": "John 9:1-41",
    }),
    ("The Fifth Sunday in Lent", {
        "first_lesson": "Ezekiel 37:1-14",
        "psalm": "Psalm 130",
        "second_lesson": "Romans 8:6-11",
        "gospel": "John 11:1-45",
    }),
    ("Palm Sunday", {
        "first_lesson": "Isaiah 50:4-9a",
        "psalm": "Psalm 31:9-16",
        "second_lesson": "Philippians 2:5-11",
        "gospel": "Matthew 26:14-27:66",
    }),
    # Easter
    ("Easter Day", {
        "first_lesson": "Acts 10:34-43",
        "psalm": "Psalm 118:1-2, 14-24",
        "second_lesson": "Colossians 3:1-4",
        "gospel": "Matthew 28:1-10",
    }),
    ("The Second Sunday of Easter", {
        "first_lesson": "Acts 2:14a, 22-32",
        "psalm": "Psalm 16",
        "second_lesson": "1 Peter 1:3-9",
        "gospel": "John 20:19-31",
    }),
    ("The Third Sunday of Easter", {
        "first_lesson": "Acts 2:14a, 36-41",
        "psalm": "Psalm 116:1-3, 10-17",
        "second_lesson": "1 Peter 1:17-23",
        "gospel": "Luke 24:13-35",
    }),
    ("The Day of Pentecost", {
        "first_lesson": "Acts 2:1-21",
        "psalm": "Psalm 104:25-35, 37",
        "second_lesson": "1 Corinthians 12:3b-13",
        "gospel": "John 20:19-23",
    }),
    # Trinity
    ("Trinity Sunday", {
        "first_lesson": "Genesis 1:1-2:4a",
        "psalm": "Psalm 8",
        "second_lesson": "2 Corinthians 13:11-13",
        "gospel": "Matthew 28:16-20",
    }),
]


class LectionaryService:
    """4-tier offline-first RCL lookup service."""

    def __init__(
        self,
        redis_url: str = None,
        daily_office_path: str = None,
        lectserve_base: str = "https://lectserve.com",
    ):
        self.redis_client = None
        self.daily_office_path = Path(daily_office_path) if daily_office_path else None
        self.lectserve_base = lectserve_base

        # Try Redis connection
        if redis_url:
            try:
                import redis as redis_lib
                self.redis_client = redis_lib.from_url(redis_url, decode_responses=True)
                self.redis_client.ping()
                logger.info("Redis connected for lectionary cache")
            except Exception as e:
                logger.warning(f"Redis not available: {e}")
                self.redis_client = None

    # -- Tier 1: Redis Cache --

    def _cache_get(self, key: str) -> Optional[Dict]:
        if not self.redis_client:
            return None
        try:
            data = self.redis_client.get(key)
            return json.loads(data) if data else None
        except Exception:
            return None

    def _cache_set(self, key: str, data: Dict, ttl: int = 86400 * 7):
        if not self.redis_client:
            return
        try:
            self.redis_client.setex(key, ttl, json.dumps(data))
        except Exception:
            pass

    # -- Tier 2: Local JSON (daily-office repo) --

    def _lookup_daily_office(self, dt: date) -> Optional[Dict]:
        if not self.daily_office_path:
            return None
        try:
            json_dir = self.daily_office_path / "json" / "readings"
            # Daily Office uses Year One/Two
            year_num = dt.year
            advent = date(dt.year, 11, 27)  # approximate
            if dt < advent:
                year_num = dt.year - 1
            filename = "year-one.json" if year_num % 2 == 1 else "year-two.json"
            filepath = json_dir / filename
            if not filepath.exists():
                return None
            with open(filepath, "r", encoding="utf-8") as f:
                offices = json.load(f)
            # Match by month/day pattern
            target = dt.strftime("%B %d").replace(" 0", " ")
            for office in offices:
                if office.get("day", "") == target:
                    return {"source": "daily-office-json", "readings": office}
            return None
        except Exception as e:
            logger.warning(f"Daily Office lookup failed: {e}")
            return None

    # -- Tier 3: LectServe API --

    def _lookup_lectserve(self, dt: date) -> Optional[Dict]:
        try:
            import httpx
            url = f"{self.lectserve_base}/date/{dt.isoformat()}?lect=rcl"
            resp = httpx.get(url, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                return {"source": "lectserve", "readings": data}
            return None
        except Exception as e:
            logger.debug(f"LectServe unavailable: {e}")
            return None

    # -- Tier 4: Built-in Year A data --

    def _lookup_builtin(self, day_name: str) -> Optional[Dict]:
        """Ordered pattern matching to avoid substring collisions."""
        if not day_name:
            return None
        name_lower = day_name.lower().strip()
        for pattern, readings in BUILTIN_YEAR_A:
            if pattern.lower() == name_lower:
                return {"source": "builtin-year-a", "readings": readings}
        # Partial match fallback (longest match wins)
        best_match = None
        best_len = 0
        for pattern, readings in BUILTIN_YEAR_A:
            p_lower = pattern.lower()
            if p_lower in name_lower and len(p_lower) > best_len:
                best_match = {"source": "builtin-year-a", "readings": readings}
                best_len = len(p_lower)
        return best_match

    # -- Public API --

    def get_readings(self, dt, day_name: str = None) -> Dict[str, Any]:
        """
        Get RCL readings for a date using 4-tier strategy.
        Returns dict with source, readings, and metadata.
        """
        if isinstance(dt, str):
            dt = datetime.strptime(dt, "%Y-%m-%d").date()
        elif isinstance(dt, datetime):
            dt = dt.date()

        cache_key = f"rcl:{dt.isoformat()}"

        # Tier 1: Redis
        cached = self._cache_get(cache_key)
        if cached:
            cached["source"] = "redis-cache"
            return cached

        # Tier 2: Local JSON
        result = self._lookup_daily_office(dt)

        # Tier 3: LectServe API
        if not result:
            result = self._lookup_lectserve(dt)

        # Tier 4: Built-in
        if not result and day_name:
            result = self._lookup_builtin(day_name)

        if result:
            self._cache_set(cache_key, result)
            return result

        return {"source": "none", "readings": None, "message": "No readings found"}
