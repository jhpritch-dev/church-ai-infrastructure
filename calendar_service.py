"""
Calendar Service - Episcopal Liturgical Calendar
Uses liturgical-calendar PyPI package with Episcopal/BCP name mapping.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

# Try to import the liturgical-calendar package
try:
    from liturgical_calendar import liturgical_calendar
    HAS_LITURGICAL_PKG = True
    logger.info("liturgical-calendar package loaded")
except ImportError:
    HAS_LITURGICAL_PKG = False
    logger.warning("liturgical-calendar package not found; using built-in calculator")


def _computus(year: int) -> date:
    """Calculate Easter Sunday (Meeus/Jones/Butcher algorithm)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _first_sunday_of_advent(year: int) -> date:
    """First Sunday of Advent for given year."""
    christmas = date(year, 12, 25)
    days_to_sunday = (christmas.weekday() + 1) % 7
    fourth_sunday = christmas - timedelta(days=days_to_sunday)
    return fourth_sunday - timedelta(weeks=3)


def calculate_rcl_year(dt: date) -> str:
    """
    RCL Year: A, B, or C.
    Year A = years divisible by 3 (based on liturgical year start at Advent).
    """
    advent = _first_sunday_of_advent(dt.year)
    year = dt.year if dt >= advent else dt.year - 1
    return {0: "A", 1: "B", 2: "C"}[year % 3]


def calculate_lectionary_year(dt: date) -> str:
    """Daily Office lectionary year: One (odd) or Two (even)."""
    advent = _first_sunday_of_advent(dt.year)
    year = dt.year if dt >= advent else dt.year - 1
    return "Year One" if year % 2 == 1 else "Year Two"


# -- Church of England -> Episcopal name mapping --

SEASON_MAP = {
    "Advent": "Advent",
    "Christmas": "Christmas",
    "Epiphany": "The Season after the Epiphany",
    "before Lent": "The Season after the Epiphany",
    "Lent": "Lent",
    "Easter": "Easter",
    "Pentecost": "The Season after Pentecost",
    "before Advent": "The Season after Pentecost",
    "Ordinary Time": "The Season after Pentecost",
}

COLOUR_MAP = {
    "Advent": "Purple",
    "Christmas": "White",
    "The Season after the Epiphany": "Green",
    "Lent": "Purple",
    "Easter": "White",
    "The Season after Pentecost": "Green",
}

# Maps (season, weekno) to Episcopal Sunday name
EPIPHANY_NAMES = {
    1: "The First Sunday after the Epiphany: The Baptism of our Lord",
    2: "The Second Sunday after the Epiphany",
    3: "The Third Sunday after the Epiphany",
    4: "The Fourth Sunday after the Epiphany",
    5: "The Fifth Sunday after the Epiphany",
    6: "The Sixth Sunday after the Epiphany",
    7: "The Seventh Sunday after the Epiphany",
    8: "The Eighth Sunday after the Epiphany",
    9: "The Last Sunday after the Epiphany",
}

LENT_NAMES = {
    1: "The First Sunday in Lent",
    2: "The Second Sunday in Lent",
    3: "The Third Sunday in Lent",
    4: "The Fourth Sunday in Lent",
    5: "The Fifth Sunday in Lent",
    6: "Palm Sunday",
}

EASTER_NAMES = {
    1: "Easter Day",
    2: "The Second Sunday of Easter",
    3: "The Third Sunday of Easter",
    4: "The Fourth Sunday of Easter",
    5: "The Fifth Sunday of Easter",
    6: "The Sixth Sunday of Easter",
    7: "The Sunday after the Ascension",
    8: "The Day of Pentecost",
}


def _map_episcopal_name(season: str, weekno: int, cal_name: str) -> str:
    """Map liturgical-calendar output to Episcopal BCP day name."""
    mapped_season = SEASON_MAP.get(season, season)

    if mapped_season == "Advent":
        ordinals = ["First", "Second", "Third", "Fourth"]
        if weekno:
            return f"The {ordinals[min(weekno - 1, 3)]} Sunday of Advent"
        return "Advent"

    if mapped_season == "The Season after the Epiphany":
        if "Epiphany" == cal_name or cal_name == "The Epiphany":
            return "The Epiphany"
        return EPIPHANY_NAMES.get(weekno, f"The Season after the Epiphany (Week {weekno})")

    if mapped_season == "Lent":
        return LENT_NAMES.get(weekno, f"Lent Week {weekno}")

    if mapped_season == "Easter":
        return EASTER_NAMES.get(weekno, f"Easter Week {weekno}")

    if mapped_season == "The Season after Pentecost":
        if weekno and weekno > 0:
            proper = weekno + 1
            return f"Proper {proper} (The Season after Pentecost)"
        return "The Season after Pentecost"

    return cal_name or mapped_season


def get_calendar_info(dt) -> Dict[str, Any]:
    """
    Return full liturgical calendar info for a date.

    Returns dict with keys:
        date, day_name, season, colour, rcl_year,
        lectionary_year, easter_date, is_sunday
    """
    if isinstance(dt, str):
        dt = datetime.strptime(dt, "%Y-%m-%d").date()
    elif isinstance(dt, datetime):
        dt = dt.date()

    result = {
        "date": dt.isoformat(),
        "is_sunday": dt.weekday() == 6,
        "rcl_year": calculate_rcl_year(dt),
        "lectionary_year": calculate_lectionary_year(dt),
        "easter_date": _computus(dt.year).isoformat(),
    }

    if HAS_LITURGICAL_PKG:
        try:
            cal = liturgical_calendar(dt.strftime("%Y-%m-%d"))
            pkg_season = cal.get("season", "")
            weekno = cal.get("weekno", 0)
            cal_name = cal.get("name", "")
            mapped_season = SEASON_MAP.get(pkg_season, pkg_season)
            day_name = _map_episcopal_name(pkg_season, weekno, cal_name)
            result.update({
                "day_name": day_name,
                "season": mapped_season,
                "colour": COLOUR_MAP.get(mapped_season, "Green"),
                "raw_calendar": cal,
            })
            return result
        except Exception as e:
            logger.warning(f"liturgical-calendar failed: {e}, using fallback")

    # Fallback: built-in season calculator
    easter_dt = _computus(dt.year)
    ash_wed = easter_dt - timedelta(days=46)
    pentecost = easter_dt + timedelta(days=49)
    advent = _first_sunday_of_advent(dt.year)
    epiphany = date(dt.year, 1, 6)

    if dt >= advent:
        season = "Advent"
    elif dt >= date(dt.year, 12, 25):
        season = "Christmas"
    elif dt < epiphany:
        season = "Christmas"
    elif dt < ash_wed:
        season = "The Season after the Epiphany"
    elif dt < easter_dt:
        season = "Lent"
    elif dt < pentecost:
        season = "Easter"
    else:
        season = "The Season after Pentecost"

    result.update({
        "day_name": season,
        "season": season,
        "colour": COLOUR_MAP.get(season, "Green"),
    })
    return result
