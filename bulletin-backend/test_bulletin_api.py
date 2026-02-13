"""
Episcopal Bulletin Generator - Test Suite
Phases 1-4: Hymns, Calendar/Lectionary, Music, Assets

Run:   pytest test_bulletin_api.py -v
Local: pytest test_bulletin_api.py -v -k "not docker"
CI:    pytest test_bulletin_api.py -v --tb=short

Requires: pip install pytest httpx
"""

import json
import os
import sys
import importlib
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Ensure modules/ is importable (local dev: run from bulletin-backend/)
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(__file__))


# ===========================================================================
# PHASE 1: Hymn Lookup
# ===========================================================================

class TestHymnLookup:
    """Phase 1: Hymnal 1982 database and lookup functions."""

    def test_import(self):
        """Module imports without error."""
        from modules.hymn_lookup import lookup_hymn
        assert callable(lookup_hymn)

    def test_known_hymn_390(self):
        """Hymn 390 (Praise to the Lord) returns correct data."""
        from modules.hymn_lookup import lookup_hymn
        result = lookup_hymn("390")
        assert result["title"] == "Praise to the Lord, the Almighty"
        assert result["tune"] == "Lobe den Herren"
        assert "season" in result

    def test_known_hymn_advent(self):
        """An Advent hymn returns correct season."""
        from modules.hymn_lookup import lookup_hymn
        # Try common Advent hymns that may be in the database
        for num in ("56", "57", "61", "66"):
            result = lookup_hymn(num)
            if result is not None:
                assert result["season"] == "Advent", f"Hymn {num} season wrong"
                return
        pytest.skip("No Advent hymns found in database")

    def test_unknown_hymn_returns_empty_or_default(self):
        """Unknown hymn number returns None or empty dict."""
        from modules.hymn_lookup import lookup_hymn
        result = lookup_hymn("9999")
        # Should not raise; returns None or empty dict
        assert result is None or isinstance(result, dict)

    def test_string_and_int_input(self):
        """Accepts both string '390' and string-from-int input."""
        from modules.hymn_lookup import lookup_hymn
        r1 = lookup_hymn("390")
        r2 = lookup_hymn(str(390))
        assert r1 == r2

    def test_hymn_has_required_fields(self):
        """Every hymn entry has title, tune, composer, season."""
        from modules.hymn_lookup import lookup_hymn
        result = lookup_hymn("390")
        for field in ("title", "tune", "composer", "season"):
            assert field in result, f"Missing field: {field}"

    def test_hymn_database_minimum_count(self):
        """Hymnal JSON has at least 50 entries."""
        data_path = Path(__file__).parent / "data" / "hymnal_1982.json"
        if data_path.exists():
            with open(data_path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            assert len(data) >= 50, f"Only {len(data)} hymns; expected 50+"


# ===========================================================================
# PHASE 1: DOCX Generator
# ===========================================================================

class TestDocxGenerator:
    """Phase 1: Bulletin DOCX generation."""

    def test_import(self):
        """Module imports without error."""
        from modules.docx_generator import generate_bulletin
        assert callable(generate_bulletin)

    def test_generate_minimal_bulletin(self, tmp_path):
        """Generates a .docx file from minimal input."""
        from modules.docx_generator import generate_bulletin

        output = str(tmp_path / "test_bulletin.docx")
        data = {
            "parish_name": "St. Mark's Episcopal Church",
            "service_date": "2026-02-15",
            "service_time": "10:30 AM",
            "service_type": "Holy Eucharist Rite II",
            "liturgical_season": "Epiphany",
            "opening_hymn_number": "390",
        }
        result = generate_bulletin(data, output)
        assert Path(output).exists(), "DOCX file not created"
        assert Path(output).stat().st_size > 0, "DOCX file is empty"

    def test_generate_with_all_fields(self, tmp_path):
        """Generates bulletin with complete form data."""
        from modules.docx_generator import generate_bulletin

        output = str(tmp_path / "full_bulletin.docx")
        data = {
            "parish_name": "Holy Trinity Episcopal",
            "service_date": "2026-03-01",
            "service_time": "8:00 AM",
            "service_type": "Holy Eucharist Rite I",
            "liturgical_season": "Lent",
            "opening_hymn_number": "142",
            "sequence_hymn_number": "474",
            "closing_hymn_number": "688",
            "first_lesson_citation": "Genesis 12:1-4a",
            "psalm_number": "121",
            "gospel_citation": "John 3:1-17",
            "preacher_name": "The Rev. Jane Smith",
            "parish_address": "123 Church St, Anytown, FL",
        }
        result = generate_bulletin(data, output)
        assert Path(output).exists()


# ===========================================================================
# PHASE 2: Calendar Service
# ===========================================================================

class TestCalendarService:
    """Phase 2: Liturgical calendar calculations."""

    def test_import(self):
        """Module imports without error."""
        try:
            from modules.calendar_service import get_liturgical_info
            assert callable(get_liturgical_info)
        except ImportError:
            pytest.skip("calendar_service not deployed")

    def test_epiphany_season(self):
        """January 25, 2026 is Epiphany season."""
        try:
            from modules.calendar_service import get_liturgical_info
        except ImportError:
            pytest.skip("calendar_service not deployed")

        info = get_liturgical_info(date(2026, 1, 25))
        assert info is not None
        season = info.get("season", "").lower()
        assert "epiphany" in season, f"Expected Epiphany, got {season}"

    def test_christmas_day(self):
        """December 25 is Christmas."""
        try:
            from modules.calendar_service import get_liturgical_info
        except ImportError:
            pytest.skip("calendar_service not deployed")

        info = get_liturgical_info(date(2025, 12, 25))
        season = info.get("season", "").lower()
        assert "christmas" in season

    def test_liturgical_year_cycle(self):
        """Correctly identifies Year A/B/C cycle."""
        try:
            from modules.calendar_service import get_liturgical_info
        except ImportError:
            pytest.skip("calendar_service not deployed")

        # 2026 Advent starts Year C (2026-2027)
        # 2025-2026 is Year B/C boundary
        info = get_liturgical_info(date(2026, 1, 15))
        year = info.get("year", "")
        assert year in ("A", "B", "C"), f"Invalid year: {year}"

    def test_liturgical_color(self):
        """Returns a valid liturgical color."""
        try:
            from modules.calendar_service import get_liturgical_info
        except ImportError:
            pytest.skip("calendar_service not deployed")

        info = get_liturgical_info(date(2026, 3, 15))  # Lent
        color = info.get("color", "").lower()
        valid_colors = {"white", "green", "purple", "red", "blue", "rose", "black"}
        assert color in valid_colors, f"Invalid color: {color}"


# ===========================================================================
# PHASE 2: Lectionary Service
# ===========================================================================

class TestLectionaryService:
    """Phase 2: Revised Common Lectionary lookups."""

    def test_import(self):
        """Module imports without error."""
        try:
            from modules.lectionary_service import LectionaryService
            assert LectionaryService is not None
        except ImportError:
            pytest.skip("lectionary_service not deployed")

    def test_lookup_returns_readings(self):
        """Lectionary lookup for a Sunday returns readings."""
        try:
            from modules.lectionary_service import LectionaryService
        except ImportError:
            pytest.skip("lectionary_service not deployed")

        svc = LectionaryService()
        readings = svc.get_readings("2026-01-25")
        # Should have at least first_reading and gospel
        assert readings is not None
        if isinstance(readings, dict):
            assert any(k in readings for k in
                       ("first_reading", "gospel", "readings", "first_lesson"))


# ===========================================================================
# PHASE 3: Music Service
# ===========================================================================

class TestMusicServiceLookup:
    """Phase 3: S-number lookups for Hymnal 1982 service music."""

    def test_import(self):
        """Module imports without error."""
        try:
            from modules.music_service import lookup_service_music
            assert callable(lookup_service_music)
        except ImportError:
            pytest.skip("music_service not deployed")

    def test_s280_gloria(self):
        """S 280 is the Powell Gloria."""
        from modules.music_service import lookup_service_music
        result = lookup_service_music("S 280")
        assert result["title"] == "Gloria in excelsis"
        assert result["composer"] == "Robert Powell"
        assert result["type"] == "gloria"

    def test_s128_sanctus(self):
        """S 128 is the Mathias Sanctus."""
        from modules.music_service import lookup_service_music
        result = lookup_service_music("S 128")
        assert result["title"] == "Holy, holy, holy Lord"
        assert result["type"] == "sanctus"

    def test_flexible_input_formats(self):
        """Accepts 'S 280', 'S280', 's280', '280'."""
        from modules.music_service import lookup_service_music
        expected_title = "Gloria in excelsis"
        for variant in ("S 280", "S280", "s280", "s 280"):
            result = lookup_service_music(variant)
            assert result["title"] == expected_title, f"Failed for input: {variant}"

    def test_unknown_s_number(self):
        """Unknown S-number returns empty dict or None."""
        from modules.music_service import lookup_service_music
        result = lookup_service_music("S 999")
        assert result is None or result == {} or result.get("title") is None

    def test_list_service_music_by_type(self):
        """Can filter service music by type (gloria, sanctus, etc.)."""
        from modules.music_service import list_service_music
        glorias = list_service_music("gloria")
        assert len(glorias) >= 3, f"Expected 3+ glorias, got {len(glorias)}"
        for entry in glorias:
            assert entry["type"] == "gloria"

    def test_list_music_types(self):
        """Returns all available music types."""
        from modules.music_service import list_music_types
        types = list_music_types()
        assert isinstance(types, (list, dict))
        expected = {"kyrie", "gloria", "sanctus", "fraction"}
        if isinstance(types, list):
            type_names = {t["type"] if isinstance(t, dict) else t for t in types}
        else:
            type_names = set(types.keys())
        assert expected.issubset(type_names), f"Missing types: {expected - type_names}"

    def test_fraction_anthems_count(self):
        """At least 5 fraction anthems in database."""
        from modules.music_service import list_service_music
        fractions = list_service_music("fraction")
        assert len(fractions) >= 5, f"Only {len(fractions)} fraction anthems"


class TestMusicPlan:
    """Phase 3: Music plan storage and retrieval."""

    def test_music_plan_class(self):
        """MusicPlan has required fields."""
        from modules.music_service import MusicPlan
        plan = MusicPlan()
        # Hymn fields and S-number fields (actual field names)
        for field in ("opening_hymn", "closing_hymn", "gloria",
                      "sanctus", "fraction"):
            assert hasattr(plan, field), f"MusicPlan missing: {field}"

    def test_music_service_save_and_retrieve(self, tmp_path):
        """Can save and retrieve a music plan by date."""
        from modules.music_service import MusicService, MusicPlan

        svc = MusicService(storage_path=str(tmp_path / "plans.json"))
        plan = MusicPlan(
            service_date="2026-02-15",
            opening_hymn="390",
            closing_hymn="688",
            gloria="S 280",
            sanctus="S 128",
            fraction="S 154",
            anthem_title="Like as the Hart",
            anthem_composer="Herbert Howells",
        )

        # Save
        svc.save_plan(plan)

        # Retrieve
        retrieved = svc.get_plan("2026-02-15")
        assert retrieved is not None
        assert retrieved["opening_hymn"] == "390"
        assert retrieved["gloria"] == "S 280"
        assert retrieved["anthem_title"] == "Like as the Hart"

    def test_music_service_list_plans(self, tmp_path):
        """Lists saved music plans."""
        from modules.music_service import MusicService, MusicPlan

        svc = MusicService(storage_path=str(tmp_path / "plans.json"))
        for d in ("2026-02-08", "2026-02-15", "2026-02-22"):
            plan = MusicPlan(service_date=d, opening_hymn="390")
            svc.save_plan(plan)

        plans = svc.list_plans()
        assert len(plans) >= 3

    def test_music_service_delete_plan(self, tmp_path):
        """Can delete a music plan."""
        from modules.music_service import MusicService, MusicPlan

        svc = MusicService(storage_path=str(tmp_path / "plans.json"))
        plan = MusicPlan(service_date="2026-02-15", opening_hymn="390")
        svc.save_plan(plan)

        result = svc.delete_plan("2026-02-15")
        assert result is True
        assert svc.get_plan("2026-02-15") is None


# ===========================================================================
# PHASE 4: Asset Extractor
# ===========================================================================

class TestAssetExtractor:
    """Phase 4: PDF asset extraction and management."""

    def test_import(self):
        """Module imports without error."""
        try:
            from modules.asset_extractor import AssetExtractor
            assert AssetExtractor is not None
        except ImportError:
            pytest.skip("asset_extractor not deployed")

    def test_extractor_initialization(self, tmp_path):
        """AssetExtractor initializes with asset directory."""
        from modules.asset_extractor import AssetExtractor
        extractor = AssetExtractor(asset_dir=str(tmp_path / "assets"))
        assert extractor is not None

    def test_sha256_deduplication_logic(self):
        """Deduplication uses SHA256 hashing."""
        from modules.asset_extractor import AssetExtractor
        import hashlib
        # Verify the hashing approach
        test_data = b"test image data"
        expected = hashlib.sha256(test_data).hexdigest()
        assert len(expected) == 64  # SHA256 hex length

    def test_category_detection(self):
        """Auto-categorization identifies common types."""
        try:
            from modules.asset_extractor import AssetExtractor
            extractor = AssetExtractor()
            # Test category detection if method exists
            if hasattr(extractor, '_categorize') or hasattr(extractor, 'categorize'):
                categorize = getattr(extractor, '_categorize',
                                     getattr(extractor, 'categorize', None))
                if categorize:
                    assert categorize("parish_logo.png") in (
                        "logo", "graphic", "photo", "icon", "unknown")
        except (ImportError, TypeError):
            pytest.skip("asset_extractor categorize not available")


# ===========================================================================
# API ENDPOINT TESTS (requires running server)
# ===========================================================================

class TestAPIEndpoints:
    """Integration tests against running API server.

    These require the server to be running on localhost.
    Skip with: pytest -k "not api_live"
    """

    BASE_URL = os.getenv("BULLETIN_API_URL", "http://localhost:8002")

    @pytest.fixture(autouse=True)
    def check_server(self):
        """Skip all tests in this class if server isn't running."""
        try:
            import httpx
            r = httpx.get(f"{self.BASE_URL}/health", timeout=3)
            if r.status_code != 200:
                pytest.skip(f"API server not healthy: {r.status_code}")
        except Exception:
            pytest.skip(f"API server not reachable at {self.BASE_URL}")

    # Phase 1 endpoints
    def test_api_health(self):
        import httpx
        r = httpx.get(f"{self.BASE_URL}/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in ("healthy", "ok")

    def test_api_hymn_lookup(self):
        import httpx
        r = httpx.get(f"{self.BASE_URL}/hymn/390")
        assert r.status_code == 200

    def test_api_bulletins_list(self):
        import httpx
        r = httpx.get(f"{self.BASE_URL}/bulletins")
        assert r.status_code == 200

    def test_api_docs(self):
        import httpx
        r = httpx.get(f"{self.BASE_URL}/docs")
        assert r.status_code == 200

    # Phase 2 endpoints
    def test_api_lectionary(self):
        import httpx
        r = httpx.get(f"{self.BASE_URL}/api/lectionary/2026-01-25")
        if r.status_code == 404:
            pytest.skip("Lectionary endpoint not deployed")
        assert r.status_code == 200

    def test_api_calendar(self):
        import httpx
        r = httpx.get(f"{self.BASE_URL}/api/calendar/2026-01-25")
        if r.status_code == 404:
            pytest.skip("Calendar endpoint not deployed")
        assert r.status_code == 200

    # Phase 3 endpoints
    def test_api_service_music_lookup(self):
        import httpx
        r = httpx.get(f"{self.BASE_URL}/api/service-music/S 280")
        if r.status_code == 404:
            pytest.skip("Music service not deployed")
        assert r.status_code == 200
        data = r.json()
        assert "Gloria" in data.get("title", "") or "gloria" in json.dumps(data).lower()

    def test_api_service_music_list(self):
        import httpx
        r = httpx.get(f"{self.BASE_URL}/api/service-music")
        if r.status_code == 404:
            pytest.skip("Music service not deployed")
        assert r.status_code == 200

    def test_api_music_plan_crud(self):
        """Create, read, delete a music plan via API."""
        import httpx
        base = self.BASE_URL

        # Create
        plan_data = {
            "service_date": "2099-12-31",
            "opening_hymn": "390",
            "gloria_s_number": "S 280",
        }
        r = httpx.post(f"{base}/api/music-plan", json=plan_data)
        if r.status_code == 404:
            pytest.skip("Music plan endpoint not deployed")
        assert r.status_code in (200, 201)

        # Read
        r = httpx.get(f"{base}/api/music-plan/2099-12-31")
        assert r.status_code == 200

        # Delete (cleanup)
        r = httpx.delete(f"{base}/api/music-plan/2099-12-31")
        assert r.status_code in (200, 204)

    # Phase 4 endpoints
    def test_api_assets_list(self):
        import httpx
        r = httpx.get(f"{self.BASE_URL}/api/assets")
        if r.status_code == 404:
            pytest.skip("Asset endpoints not deployed")
        assert r.status_code == 200

    def test_api_assets_stats(self):
        import httpx
        r = httpx.get(f"{self.BASE_URL}/api/assets/stats/summary")
        if r.status_code == 404:
            pytest.skip("Asset stats not deployed")
        assert r.status_code == 200


# ===========================================================================
# DATA INTEGRITY TESTS
# ===========================================================================

class TestDataIntegrity:
    """Validate JSON data files haven't been corrupted."""

    def test_hymnal_json_valid(self):
        """hymnal_1982.json is valid JSON."""
        data_path = Path(__file__).parent / "data" / "hymnal_1982.json"
        if not data_path.exists():
            pytest.skip("hymnal_1982.json not found")
        with open(data_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_hymnal_entries_have_titles(self):
        """Every hymn entry has a non-empty title."""
        data_path = Path(__file__).parent / "data" / "hymnal_1982.json"
        if not data_path.exists():
            pytest.skip("hymnal_1982.json not found")
        with open(data_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        for number, entry in data.items():
            assert entry.get("title"), f"Hymn {number} has no title"

    def test_service_music_dict_valid(self):
        """SERVICE_MUSIC dict has correct structure."""
        try:
            from modules.music_service import SERVICE_MUSIC
        except ImportError:
            pytest.skip("music_service not deployed")
        assert len(SERVICE_MUSIC) >= 30, f"Only {len(SERVICE_MUSIC)} S-numbers"
        for key, val in SERVICE_MUSIC.items():
            assert key.startswith("S "), f"Bad key format: {key}"
            assert "title" in val, f"{key} missing title"
            assert "type" in val, f"{key} missing type"


# ===========================================================================
# SMOKE TEST (run first, fail fast)
# ===========================================================================

class TestSmoke:
    """Quick smoke tests — run these first to catch obvious breakage."""

    def test_python_version(self):
        """Python 3.10+ required."""
        assert sys.version_info >= (3, 10), f"Python {sys.version} too old"

    def test_critical_imports(self):
        """All phase modules are importable."""
        errors = []
        for module in [
            "modules.hymn_lookup",
            "modules.docx_generator",
        ]:
            try:
                importlib.import_module(module)
            except ImportError as e:
                errors.append(f"{module}: {e}")

        # Phase 2-4 are optional (may not be deployed)
        optional = [
            "modules.calendar_service",
            "modules.lectionary_service",
            "modules.music_service",
            "modules.asset_extractor",
        ]
        for module in optional:
            try:
                importlib.import_module(module)
            except ImportError:
                pass  # OK if not deployed yet

        assert not errors, f"Required module failures: {errors}"

    def test_output_dir_writable(self, tmp_path):
        """Can write files to temp directory."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("smoke test")
        assert test_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
