"""
Phase 2 App Patcher - Adds lectionary endpoints to app.py
Usage: python patch_app_phase2.py <path_to_app.py>
"""
import sys
import os


def patch_app(app_path):
    with open(app_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()

    # Check if already patched
    if 'calendar_service' in content:
        print('  [=] app.py already contains Phase 2 imports. No changes made.')
        return

    # --- Add imports after existing module imports ---
    import_lines = [
        '',
        '# Phase 2: Liturgical Calendar + Lectionary',
        'from modules.calendar_service import get_calendar_info',
        'from modules.lectionary_service import LectionaryService',
        'import os',
        '',
        '# Initialize lectionary service (offline-first)',
        '_lectionary = LectionaryService(',
        '    redis_url=os.getenv("REDIS_URL", "redis://redis:6379"),',
        '    daily_office_path=os.getenv("DAILY_OFFICE_PATH", "/app/data/daily-office"),',
        '    lectserve_base=os.getenv("LECTSERVE_URL", "https://lectserve.com"),',
        ')',
    ]
    import_block = '\n'.join(import_lines) + '\n'

    # Find insertion point: after the last 'from modules.' import line
    lines = content.split('\n')
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith('from modules.'):
            insert_idx = i + 1

    if insert_idx > 0:
        lines.insert(insert_idx, import_block)
    else:
        # Fallback: insert before 'app = FastAPI'
        for i, line in enumerate(lines):
            if line.startswith('app = FastAPI'):
                lines.insert(i, import_block)
                break

    content = '\n'.join(lines)

    # --- Add endpoint code ---
    endpoint_lines = [
        '',
        '',
        '# =====================================================================',
        '# PHASE 2: LECTIONARY ENDPOINTS',
        '# =====================================================================',
        '',
        '@app.get("/api/lectionary/{date_str}")',
        'async def get_lectionary(date_str: str):',
        '    """Get liturgical calendar info and RCL readings for a date (YYYY-MM-DD)."""',
        '    from datetime import datetime',
        '    try:',
        '        dt = datetime.strptime(date_str, "%Y-%m-%d").date()',
        '    except ValueError:',
        '        from fastapi import HTTPException',
        '        raise HTTPException(status_code=400, detail="Invalid date. Use YYYY-MM-DD.")',
        '    cal = get_calendar_info(dt)',
        '    readings = _lectionary.get_readings(dt, day_name=cal.get("day_name"))',
        '    return {"date": dt.isoformat(), "calendar": cal, "readings": readings}',
        '',
        '',
        '@app.get("/api/calendar/{date_str}")',
        'async def get_calendar(date_str: str):',
        '    """Get liturgical calendar info only (YYYY-MM-DD)."""',
        '    from datetime import datetime',
        '    try:',
        '        dt = datetime.strptime(date_str, "%Y-%m-%d").date()',
        '    except ValueError:',
        '        from fastapi import HTTPException',
        '        raise HTTPException(status_code=400, detail="Invalid date. Use YYYY-MM-DD.")',
        '    return get_calendar_info(dt)',
    ]
    endpoint_code = '\n'.join(endpoint_lines) + '\n'

    # Insert before 'if __name__' or append
    if 'if __name__' in content:
        content = content.replace('if __name__', endpoint_code + '\nif __name__')
    else:
        content += endpoint_code

    with open(app_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)

    print('  [OK] app.py patched with lectionary endpoints')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python patch_app_phase2.py <path_to_app.py>')
        sys.exit(1)
    patch_app(sys.argv[1])
