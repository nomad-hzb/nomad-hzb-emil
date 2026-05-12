"""
EMIL Sample Management System — FastAPI Application
====================================================
Converted from the Jupyter/Voila notebook (emil_samples_20251204.ipynb).
Serves a web UI for sample management with an editable AG Grid table.
All NOMAD API calls are made by the browser directly (same origin,
relative paths) — no server-side proxying, no absolute domains.
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from nomad.config import config
from pathlib import Path

# ── Plugin wiring ─────────────────────────────────────────────────────────────
data_upload_api_entry_point = config.get_plugin_entry_point(
    'nomad_hzb_emil.apis:data_upload_api_entry_point'
)

app = FastAPI(
    root_path=f'{config.services.api_base_path}/{data_upload_api_entry_point.prefix}'
)



# ── Configuration (all relative paths, no domains) ───────────────────────────
NOMAD_API_BASE = f'{config.services.api_base_path}/api/v1'      # e.g. /nomad-oasis/api/v1
NOMAD_GUI_BASE = (
    config.services.api_base_path.rsplit('/api', 1)[0] + '/gui'
    if '/api' in config.services.api_base_path
    else '/gui'
)
NOMAD_LOGIN_BASE = config.services.api_base_path                 # redirect target for unauthenticated users

MEASUREMENT_TYPES = [
    'General', 'XRD', 'XRR', 'Bragg-Brentano XRD', 'GIXRD', 'FTS-FID',
    'FTS-TCD', 'Fischer-Tropsch Synthesis', 'Incipient wetness impregnation',
    'ALD', 'XAS', 'HAXPES', 'XRF', 'XPS', 'Physisorption', 'IR',
    'Annodization', 'Microscopy', 'Raman', 'UVvis', 'SEM', 'TEM',
    'Sputtering', 'PECVD', 'NanoFab-Oxford Recipe', 'Estrellas-Oxford Recipe',
]


# ── REST endpoints ────────────────────────────────────────────────────────────
@app.get('/api/measurement-types')
async def api_measurement_types():
    return MEASUREMENT_TYPES

@app.get('/auth/config')
async def auth_config():
    """Return Keycloak config so the frontend can initialize authentication."""
    return {
        'keycloak_url': config.keycloak.public_server_url,
        'keycloak_realm': config.keycloak.realm_name,
        'keycloak_client_id': config.keycloak.client_id,
    }


# ── HTML frontend ─────────────────────────────────────────────────────────────
_TEMPLATE_DIR = Path(__file__).parent


def _render_template(filename: str) -> str:
    html = (_TEMPLATE_DIR / filename).read_text(encoding='utf-8')
    return (
        html
        .replace('__NOMAD_API__', NOMAD_API_BASE)
        .replace('__NOMAD_GUI__', NOMAD_GUI_BASE)
        .replace('__NOMAD_BASE__', NOMAD_LOGIN_BASE)
    )


@app.get('/', response_class=HTMLResponse)
async def root():
    return _render_template('data_upload_ui.html')


@app.get('/file-upload', response_class=HTMLResponse)
async def file_upload():
    return _render_template('file_upload_ui.html')