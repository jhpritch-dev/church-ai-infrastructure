"""
Phase 3: Music Service
Episcopal Bulletin Generator

Structured music data entry for bulletin generation.
The church musician provides selections; the admin enters them here.

Features:
  - Service music S-number lookup (Gloria, Sanctus, Fraction, etc.)
  - Hymn number integration (delegates to hymn_lookup)
  - Structured placeholders for anthem, prelude, postlude
  - Music plan storage per service date
  - Future hook: musician submission endpoint

No AI/Ollama — music selection is the musician's job.
Ollama handles natural-language bulletin orchestration elsewhere.
"""

import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Service Music S-Numbers (Hymnal 1982, Service Music section)
# These are the "S-" numbers printed in the front of the hymnal.
# Covers the most commonly used settings in Episcopal parishes.
# ---------------------------------------------------------------------------
SERVICE_MUSIC = {
    # Kyrie
    "S 86":  {"title": "Kyrie eleison", "setting": "Missa de Sancta Maria Magdalena", "composer": "Healey Willan", "type": "kyrie"},
    "S 91":  {"title": "Kyrie eleison", "setting": "Franz Schubert", "composer": "Franz Schubert", "type": "kyrie"},
    "S 96":  {"title": "Lord, have mercy upon us", "setting": "New Plainsong", "composer": "David Hurd", "type": "kyrie"},

    # Gloria
    "S 201": {"title": "Gloria in excelsis", "setting": "Plainsong", "composer": "Plainsong", "type": "gloria"},
    "S 202": {"title": "Gloria in excelsis", "setting": "Plainsong", "composer": "Plainsong", "type": "gloria"},
    "S 204": {"title": "Gloria in excelsis", "setting": "Missa de Sancta Maria Magdalena", "composer": "Healey Willan", "type": "gloria"},
    "S 277": {"title": "Gloria in excelsis", "setting": "New Plainsong", "composer": "David Hurd", "type": "gloria"},
    "S 278": {"title": "Gloria in excelsis", "setting": "Mathias", "composer": "William Mathias", "type": "gloria"},
    "S 280": {"title": "Gloria in excelsis", "setting": "Powell", "composer": "Robert Powell", "type": "gloria"},

    # Trisagion
    "S 99":  {"title": "Holy God, Holy and Mighty", "setting": "Trisagion", "composer": "Alexander Archangelsky", "type": "trisagion"},
    "S 100": {"title": "Trisagion", "setting": "New Plainsong", "composer": "David Hurd", "type": "trisagion"},
    "S 102": {"title": "Trisagion", "setting": "Byzantine chant", "composer": "Plainsong", "type": "trisagion"},

    # Sanctus
    "S 113": {"title": "Holy, holy, holy Lord", "setting": "Plainsong", "composer": "Plainsong", "type": "sanctus"},
    "S 114": {"title": "Holy, holy, holy Lord", "setting": "Healey Willan", "composer": "Healey Willan", "type": "sanctus"},
    "S 124": {"title": "Holy, holy, holy Lord", "setting": "New Plainsong", "composer": "David Hurd", "type": "sanctus"},
    "S 125": {"title": "Holy, holy, holy Lord", "setting": "Proulx", "composer": "Richard Proulx", "type": "sanctus"},
    "S 128": {"title": "Holy, holy, holy Lord", "setting": "Mathias", "composer": "William Mathias", "type": "sanctus"},
    "S 129": {"title": "Holy, holy, holy Lord", "setting": "Powell", "composer": "Robert Powell", "type": "sanctus"},
    "S 130": {"title": "Holy, holy, holy Lord", "setting": "Schubert/Proulx", "composer": "Franz Schubert, arr. Richard Proulx", "type": "sanctus"},

    # Fraction Anthems
    "S 151": {"title": "Christ our Passover", "setting": "Plainsong", "composer": "Plainsong", "type": "fraction"},
    "S 152": {"title": "Christ our Passover", "setting": "Ambrosian chant", "composer": "Plainsong", "type": "fraction"},
    "S 154": {"title": "Christ our Passover", "setting": "New Plainsong", "composer": "David Hurd", "type": "fraction"},
    "S 155": {"title": "Christ our Passover", "setting": "Near", "composer": "Gerald Near", "type": "fraction"},
    "S 158": {"title": "O Lamb of God", "setting": "Agnus Dei (Healey Willan)", "composer": "Healey Willan", "type": "fraction"},
    "S 161": {"title": "O Lamb of God", "setting": "New Plainsong", "composer": "David Hurd", "type": "fraction"},
    "S 163": {"title": "O Lamb of God", "setting": "Powell", "composer": "Robert Powell", "type": "fraction"},
    "S 164": {"title": "Jesus, Lamb of God", "setting": "Schubert/Proulx", "composer": "Franz Schubert, arr. Richard Proulx", "type": "fraction"},
    "S 167": {"title": "The disciples knew the Lord Jesus", "setting": "Mode 6 melody", "composer": "Plainsong", "type": "fraction"},
    "S 169": {"title": "My flesh is food indeed", "setting": "Mode 1 melody", "composer": "Plainsong", "type": "fraction"},
    "S 171": {"title": "Be known to us, Lord Jesus", "setting": "Mode 6 melody", "composer": "Plainsong", "type": "fraction"},
    "S 172": {"title": "Christ our Passover", "setting": "Martens", "composer": "Edmund Martens", "type": "fraction"},

    # Sursum Corda / Preface Responses
    "S 112": {"title": "The Lord be with you / Lift up your hearts", "setting": "Plainsong", "composer": "Plainsong", "type": "sursum_corda"},
    "S 120": {"title": "Sursum Corda", "setting": "Willan", "composer": "Healey Willan", "type": "sursum_corda"},

    # Doxology
    "S 176": {"title": "Amen (Dresden)", "setting": "Dresden Amen", "composer": "J.G. Naumann", "type": "amen"},
    "S 142": {"title": "Amen (McNeil Robinson)", "setting": "Robinson", "composer": "McNeil Robinson", "type": "amen"},

    # Memorial Acclamation
    "S 133": {"title": "Christ has died", "setting": "Plainsong", "composer": "Plainsong", "type": "memorial_acclamation"},
    "S 135": {"title": "Christ has died", "setting": "New Plainsong", "composer": "David Hurd", "type": "memorial_acclamation"},
    "S 138": {"title": "Christ has died", "setting": "Mathias", "composer": "William Mathias", "type": "memorial_acclamation"},
}

# Service music types and their liturgical positions
MUSIC_TYPES = {
    "kyrie": "Kyrie / Lord have mercy",
    "gloria": "Gloria in excelsis (omitted in Lent/Advent)",
    "trisagion": "Trisagion (alternative to Gloria/Kyrie)",
    "sanctus": "Sanctus / Holy, holy, holy",
    "fraction": "Fraction Anthem / Agnus Dei",
    "sursum_corda": "Sursum Corda / Lift up your hearts",
    "amen": "Great Amen / Doxology",
    "memorial_acclamation": "Memorial Acclamation",
}


def lookup_service_music(s_number: str) -> Optional[dict]:
    """
    Look up a service music setting by S-number.

    Accepts formats: "S 280", "S280", "s 280", "s280", "280"
    """
    # Normalize input
    s = s_number.strip().upper()
    if not s.startswith("S"):
        s = f"S {s}"
    if s[1] != " ":
        s = f"S {s[1:]}"

    entry = SERVICE_MUSIC.get(s)
    if entry:
        return {**entry, "s_number": s}

    return None


def list_service_music(music_type: Optional[str] = None) -> list[dict]:
    """List all service music entries, optionally filtered by type."""
    results = []
    for s_num, entry in SERVICE_MUSIC.items():
        if music_type and entry.get("type") != music_type:
            continue
        results.append({**entry, "s_number": s_num})
    return sorted(results, key=lambda x: x["s_number"])


def list_music_types() -> dict:
    """Return all service music types with descriptions."""
    return MUSIC_TYPES


class MusicPlan:
    """
    Structured music data for a single service.

    The musician provides these selections; the admin enters them.
    All fields are optional — fill in what you have.
    """

    def __init__(
        self,
        service_date: Optional[str] = None,
        service_type: str = "Holy Eucharist Rite II",
        # Hymns (numbers — resolved via hymn_lookup)
        opening_hymn: str = "",
        sequence_hymn: str = "",
        offertory_hymn: str = "",
        communion_hymn_1: str = "",
        communion_hymn_2: str = "",
        closing_hymn: str = "",
        # Service music (S-numbers)
        gloria: str = "",
        kyrie: str = "",
        trisagion: str = "",
        sanctus: str = "",
        fraction: str = "",
        memorial_acclamation: str = "",
        sursum_corda: str = "",
        amen: str = "",
        # Choral / instrumental (free text from musician)
        anthem_title: str = "",
        anthem_composer: str = "",
        anthem_voicing: str = "",
        prelude_title: str = "",
        prelude_composer: str = "",
        postlude_title: str = "",
        postlude_composer: str = "",
        communion_voluntary: str = "",
        # Soloists / instrumentalists
        soloist: str = "",
        instrumentalists: str = "",
        # Notes from musician
        musician_notes: str = "",
    ):
        self.service_date = service_date
        self.service_type = service_type
        self.opening_hymn = opening_hymn
        self.sequence_hymn = sequence_hymn
        self.offertory_hymn = offertory_hymn
        self.communion_hymn_1 = communion_hymn_1
        self.communion_hymn_2 = communion_hymn_2
        self.closing_hymn = closing_hymn
        self.gloria = gloria
        self.kyrie = kyrie
        self.trisagion = trisagion
        self.sanctus = sanctus
        self.fraction = fraction
        self.memorial_acclamation = memorial_acclamation
        self.sursum_corda = sursum_corda
        self.amen = amen
        self.anthem_title = anthem_title
        self.anthem_composer = anthem_composer
        self.anthem_voicing = anthem_voicing
        self.prelude_title = prelude_title
        self.prelude_composer = prelude_composer
        self.postlude_title = postlude_title
        self.postlude_composer = postlude_composer
        self.communion_voluntary = communion_voluntary
        self.soloist = soloist
        self.instrumentalists = instrumentalists
        self.musician_notes = musician_notes

    def to_dict(self) -> dict:
        """Serialize for JSON / API response / DOCX generator."""
        return {k: v for k, v in self.__dict__.items() if v}

    def enrich_service_music(self) -> dict:
        """
        Resolve all S-numbers to full titles for bulletin display.

        Returns dict of position -> resolved info.
        """
        resolved = {}
        s_fields = {
            "gloria": self.gloria,
            "kyrie": self.kyrie,
            "trisagion": self.trisagion,
            "sanctus": self.sanctus,
            "fraction": self.fraction,
            "memorial_acclamation": self.memorial_acclamation,
            "sursum_corda": self.sursum_corda,
            "amen": self.amen,
        }

        for position, s_number in s_fields.items():
            if s_number:
                info = lookup_service_music(s_number)
                if info:
                    resolved[position] = info
                else:
                    resolved[position] = {
                        "s_number": s_number,
                        "title": f"(S-number {s_number} not found)",
                        "type": position,
                    }

        return resolved

    @classmethod
    def from_dict(cls, data: dict) -> "MusicPlan":
        """Create a MusicPlan from a dict (e.g., API request body)."""
        valid_fields = cls.__init__.__code__.co_varnames[1:]  # skip 'self'
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


class MusicService:
    """
    Manages music plans for services.

    Storage: JSON file (offline-first), with Redis cache when available.
    Future: musician submission form feeds directly into this.
    """

    def __init__(
        self,
        storage_path: Optional[str] = None,
        redis_client=None,
    ):
        self.redis = redis_client
        self.storage_path = Path(
            storage_path or os.getenv("MUSIC_PLANS_PATH", "./data/music_plans.json")
        )
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.plans: dict[str, dict] = {}
        self._load()

    def _load(self):
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8-sig") as f:
                    self.plans = json.load(f)
                logger.info("Loaded %d music plans", len(self.plans))
            except Exception as exc:
                logger.warning("Failed to load music plans: %s", exc)

    def _save(self):
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self.plans, f, indent=2, ensure_ascii=False)

    def save_plan(self, plan: MusicPlan) -> dict:
        """Save a music plan for a service date."""
        if not plan.service_date:
            raise ValueError("service_date is required")
        data = plan.to_dict()
        data["enriched_service_music"] = plan.enrich_service_music()
        self.plans[plan.service_date] = data
        self._save()

        # Cache in Redis if available
        if self.redis:
            try:
                import asyncio
                # Fire-and-forget cache update
                cache_key = f"music:plan:{plan.service_date}"
                asyncio.get_event_loop().create_task(
                    self.redis.setex(cache_key, 86400, json.dumps(data))
                )
            except Exception:
                pass

        return data

    def get_plan(self, service_date: str) -> Optional[dict]:
        """Retrieve music plan for a specific date."""
        return self.plans.get(service_date)

    def list_plans(self, limit: int = 20) -> list[dict]:
        """List recent music plans, newest first."""
        sorted_dates = sorted(self.plans.keys(), reverse=True)
        return [
            {"date": d, **self.plans[d]}
            for d in sorted_dates[:limit]
        ]

    def delete_plan(self, service_date: str) -> bool:
        """Remove a music plan."""
        if service_date in self.plans:
            del self.plans[service_date]
            self._save()
            return True
        return False
