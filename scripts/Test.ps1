$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\python.exe -m compileall -q apps tests
& .\.venv\Scripts\python.exe -c "from pathlib import Path; import yaml; from apps.api.main import app; static=yaml.safe_load(Path('packages/contracts/openapi.yaml').read_text(encoding='utf-8')); assert static == app.openapi(); assert static['info']['version'] == '1.0.7'"
Write-Host "Tests, compilation et contrat OpenAPI ProofForge V1.07 : OK"
