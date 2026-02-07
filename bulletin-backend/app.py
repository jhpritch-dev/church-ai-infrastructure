"""
Episcopal Bulletin Generation API
FastAPI + DOCX + Hymn Lookup
Runs in both Docker (/app/output) and local Windows (./output) environments.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Annotated

from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

# Ensure local imports work regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.hymn_lookup import lookup_hymn
from modules.docx_generator import generate_bulletin

# Phase 2: Liturgical Calendar + Lectionary
from modules.calendar_service import get_calendar_info
from modules.lectionary_service import LectionaryService
import os

# Initialize lectionary service (offline-first)
_lectionary = LectionaryService(
    redis_url=os.getenv("REDIS_URL", "redis://redis:6379"),
    daily_office_path=os.getenv("DAILY_OFFICE_PATH", "/app/data/daily-office"),
    lectserve_base=os.getenv("LECTSERVE_URL", "https://lectserve.com"),
)


# ============================================================================
# CONFIGURATION - auto-detect Docker vs local Windows
# ============================================================================

if os.path.exists("/app"):
    # Running inside Docker container
    OUTPUT_PATH = Path("/app/output")
    ASSETS_PATH = Path("/app/assets")
    TEMPLATES_PATH = Path("/app/templates")
else:
    # Running locally on Windows
    OUTPUT_PATH = Path(os.path.dirname(os.path.abspath(__file__))) / "output"
    ASSETS_PATH = Path(os.path.dirname(os.path.abspath(__file__))) / "assets"
    TEMPLATES_PATH = Path(os.path.dirname(os.path.abspath(__file__))) / "templates"

# Ensure directories exist
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
ASSETS_PATH.mkdir(parents=True, exist_ok=True)
TEMPLATES_PATH.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Episcopal Bulletin Generation API",
    description="Generate liturgical bulletins with BCP, RCL, hymns, and DOCX output",
    version="1.0.0",
)


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class BulletinForm(BaseModel):
    """Form data for bulletin generation."""
    # Core service info
    parish_name: str = Field("", description="Parish name")
    service_date: str = Field("", description="Date YYYY-MM-DD")
    service_time: str = Field("", description="Service time")
    service_type: str = Field("", description="e.g., Holy Eucharist Rite II")
    liturgical_season: str = Field("", description="Liturgical season")

    # Hymns (numbers only - lookup_hymn fills titles/tunes)
    opening_hymn_number: str = Field("", description="Opening hymn number")
    sequence_hymn_number: str = Field("", description="Sequence hymn number")
    communion_hymn_1_number: str = Field("", description="Communion hymn 1 number")
    communion_hymn_2_number: str = Field("", description="Communion hymn 2 number")
    closing_hymn_number: str = Field("", description="Closing hymn number")

    # Liturgy numbers
    gloria_number: str = Field("", description="Gloria number")
    sanctus_number: str = Field("", description="Sanctus number")
    fraction_number: str = Field("", description="Fraction anthem number")

    # Scripture
    first_lesson_citation: str = Field("", description="First lesson citation")
    psalm_number: str = Field("", description="Psalm number")
    second_lesson_citation: str = Field("", description="Second lesson citation")
    gospel_citation: str = Field("", description="Gospel citation")

    # Sermon
    sermon_title: str = Field("", description="Sermon title")
    preacher_name: str = Field("", description="Preacher name")

    # Optional participants
    rector_name: str = Field("", description="Rector")
    music_director_name: str = Field("", description="Music director")
    organist_name: str = Field("", description="Organist")

    # Footer
    parish_address: str = Field("", description="Parish address")
    parish_phone: str = Field("", description="Parish phone")
    parish_website: str = Field("", description="Parish website")


class BulletinListResponse(BaseModel):
    """Response for /bulletins endpoint."""
    bulletins: List[dict]
    count: int


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    return {
        "message": "Episcopal Bulletin Generation API",
        "version": "1.0.0",
        "docs": "/docs",
        "form": "/form",
        "health": "/health",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "modules": ["hymn_lookup", "docx_generator"],
        "output_path": str(OUTPUT_PATH),
        "output_exists": OUTPUT_PATH.exists(),
    }


@app.get("/hymn/{hymn_number}")
async def get_hymn(hymn_number: str):
    """Lookup hymn by number from the Hymnal 1982."""
    hymn = lookup_hymn(hymn_number)
    if hymn is None:
        raise HTTPException(status_code=404, detail=f"Hymn {hymn_number} not found")
    return {"hymn_number": hymn_number, "data": hymn}


@app.post("/generate")
async def generate_bulletin_endpoint(
    parish_name: str = Form(""),
    service_date: str = Form(""),
    service_time: str = Form(""),
    service_type: str = Form(""),
    liturgical_season: str = Form(""),
    opening_hymn_number: str = Form(""),
    sequence_hymn_number: str = Form(""),
    communion_hymn_1_number: str = Form(""),
    communion_hymn_2_number: str = Form(""),
    closing_hymn_number: str = Form(""),
    gloria_number: str = Form(""),
    sanctus_number: str = Form(""),
    fraction_number: str = Form(""),
    first_lesson_citation: str = Form(""),
    psalm_number: str = Form(""),
    second_lesson_citation: str = Form(""),
    gospel_citation: str = Form(""),
    sermon_title: str = Form(""),
    preacher_name: str = Form(""),
    rector_name: str = Form(""),
    music_director_name: str = Form(""),
    organist_name: str = Form(""),
    parish_address: str = Form(""),
    parish_phone: str = Form(""),
    parish_website: str = Form(""),
):
    """Generate a DOCX bulletin from form data."""
    form_data = {
        "parish_name": parish_name,
        "service_date": service_date,
        "service_time": service_time,
        "service_type": service_type,
        "liturgical_season": liturgical_season,
        "opening_hymn_number": opening_hymn_number,
        "sequence_hymn_number": sequence_hymn_number,
        "communion_hymn_1_number": communion_hymn_1_number,
        "communion_hymn_2_number": communion_hymn_2_number,
        "closing_hymn_number": closing_hymn_number,
        "gloria_number": gloria_number,
        "sanctus_number": sanctus_number,
        "fraction_number": fraction_number,
        "first_lesson_citation": first_lesson_citation,
        "psalm_number": psalm_number,
        "second_lesson_citation": second_lesson_citation,
        "gospel_citation": gospel_citation,
        "sermon_title": sermon_title,
        "preacher_name": preacher_name,
        "rector_name": rector_name,
        "music_director_name": music_director_name,
        "organist_name": organist_name,
        "parish_address": parish_address,
        "parish_phone": parish_phone,
        "parish_website": parish_website,
    }

    # Enrich with hymn details
    for field in [
        "opening_hymn_number",
        "sequence_hymn_number",
        "communion_hymn_1_number",
        "communion_hymn_2_number",
        "closing_hymn_number",
    ]:
        num = form_data.get(field, "")
        if num:
            hymn = lookup_hymn(num)
            if hymn:
                base = field.replace("_number", "")
                form_data[f"{base}_title"] = hymn.get("title", "")
                form_data[f"{base}_tune"] = hymn.get("tune", "")

    # Generate filename
    date_part = service_date.replace("-", "") if service_date else "undated"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"bulletin_{date_part}_{timestamp}.docx"
    output_path = OUTPUT_PATH / output_filename

    try:
        generated_path = generate_bulletin(form_data, str(output_path))
        return JSONResponse({
            "status": "success",
            "output_file": output_filename,
            "download_url": f"/output/{output_filename}",
            "message": "Bulletin generated successfully",
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@app.get("/bulletins")
async def list_bulletins(limit: int = 20, offset: int = 0):
    """List recently generated bulletins."""
    docx_files = sorted(OUTPUT_PATH.glob("*.docx"), key=lambda f: f.stat().st_mtime, reverse=True)
    bulletins = []
    for docx_file in docx_files[offset : offset + limit]:
        bulletins.append(
            {
                "filename": docx_file.name,
                "size": docx_file.stat().st_size,
                "modified": datetime.fromtimestamp(docx_file.stat().st_mtime).isoformat(),
                "download_url": f"/output/{docx_file.name}",
            }
        )
    return BulletinListResponse(bulletins=bulletins, count=len(bulletins))


@app.get("/output/{filename:path}")
async def download_bulletin(filename: str):
    """Download a generated bulletin."""
    file_path = OUTPUT_PATH / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Bulletin not found")
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/form")
async def bulletin_form():
    """HTML form for generating bulletins (test UI)."""
    return HTMLResponse(
        """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Episcopal Bulletin Generator</title>
  <style>
    body { font-family: 'Georgia', serif; max-width: 720px; margin: 2rem auto; padding: 0 1rem; color: #333; }
    h1 { color: #8B0000; border-bottom: 2px solid #8B0000; padding-bottom: 0.5rem; }
    h2 { color: #555; margin-top: 1.5rem; }
    label { display: block; margin: 0.4rem 0; }
    input, select { padding: 0.3rem 0.5rem; width: 100%; box-sizing: border-box; margin-bottom: 0.3rem; }
    fieldset { border: 1px solid #ccc; padding: 1rem; margin: 1rem 0; border-radius: 4px; }
    legend { font-weight: bold; color: #8B0000; }
    button { background: #8B0000; color: white; border: none; padding: 0.75rem 2rem; font-size: 1rem; cursor: pointer; border-radius: 4px; margin-top: 1rem; }
    button:hover { background: #a00; }
    .links { margin-top: 1rem; }
    .links a { margin-right: 1rem; }
  </style>
</head>
<body>
  <h1>Episcopal Bulletin Generator</h1>
  <p>Phase 1 &mdash; Generate DOCX bulletins with hymn lookup</p>

  <form method="POST" action="/generate">
    <fieldset>
      <legend>Service Information</legend>
      <label>Parish Name: <input name="parish_name" value="St. Mark's Episcopal Church"></label>
      <label>Date (YYYY-MM-DD): <input name="service_date" type="date" value="2026-02-08"></label>
      <label>Time: <input name="service_time" value="10:30 AM"></label>
      <label>Type: <input name="service_type" value="Holy Eucharist Rite II"></label>
      <label>Liturgical Season: <input name="liturgical_season" value="Epiphany"></label>
    </fieldset>

    <fieldset>
      <legend>Hymns (Hymnal 1982 numbers)</legend>
      <label>Opening Hymn #: <input name="opening_hymn_number" value="390" placeholder="e.g. 390"></label>
      <label>Sequence Hymn #: <input name="sequence_hymn_number" placeholder="e.g. 488"></label>
      <label>Communion Hymn 1 #: <input name="communion_hymn_1_number" placeholder="e.g. 325"></label>
      <label>Communion Hymn 2 #: <input name="communion_hymn_2_number"></label>
      <label>Closing Hymn #: <input name="closing_hymn_number" placeholder="e.g. 376"></label>
    </fieldset>

    <fieldset>
      <legend>Liturgical Music</legend>
      <label>Gloria (S-number): <input name="gloria_number" placeholder="e.g. S-280"></label>
      <label>Sanctus (S-number): <input name="sanctus_number" placeholder="e.g. S-125"></label>
      <label>Fraction Anthem (S-number): <input name="fraction_number" placeholder="e.g. S-154"></label>
    </fieldset>

    <fieldset>
      <legend>Scripture Readings</legend>
      <label>First Lesson: <input name="first_lesson_citation" value="Isaiah 6:1-8"></label>
      <label>Psalm: <input name="psalm_number" value="138"></label>
      <label>Second Lesson: <input name="second_lesson_citation" value="1 Corinthians 15:1-11"></label>
      <label>Gospel: <input name="gospel_citation" value="Luke 5:1-11"></label>
    </fieldset>

    <fieldset>
      <legend>Sermon</legend>
      <label>Title: <input name="sermon_title"></label>
      <label>Preacher: <input name="preacher_name"></label>
    </fieldset>

    <fieldset>
      <legend>Participants</legend>
      <label>Rector: <input name="rector_name"></label>
      <label>Music Director: <input name="music_director_name"></label>
      <label>Organist: <input name="organist_name"></label>
    </fieldset>

    <fieldset>
      <legend>Parish Footer</legend>
      <label>Address: <input name="parish_address"></label>
      <label>Phone: <input name="parish_phone"></label>
      <label>Website: <input name="parish_website"></label>
    </fieldset>

    <button type="submit">Generate Bulletin (DOCX)</button>
  </form>

  <div class="links">
    <h2>Quick Links</h2>
    <a href="/bulletins">View Generated Bulletins</a>
    <a href="/hymn/390">Test Hymn Lookup (390)</a>
    <a href="/health">Health Check</a>
    <a href="/docs">API Docs (Swagger)</a>
  </div>
</body>
</html>"""
    )


# ============================================================================
# RUN
# ============================================================================



# =====================================================================
# PHASE 2: LECTIONARY ENDPOINTS
# =====================================================================

@app.get("/api/lectionary/{date_str}")
async def get_lectionary(date_str: str):
    """Get liturgical calendar info and RCL readings for a date (YYYY-MM-DD)."""
    from datetime import datetime
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid date. Use YYYY-MM-DD.")
    cal = get_calendar_info(dt)
    readings = _lectionary.get_readings(dt, day_name=cal.get("day_name"))
    return {"date": dt.isoformat(), "calendar": cal, "readings": readings}


@app.get("/api/calendar/{date_str}")
async def get_calendar(date_str: str):
    """Get liturgical calendar info only (YYYY-MM-DD)."""
    from datetime import datetime
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid date. Use YYYY-MM-DD.")
    return get_calendar_info(dt)

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
