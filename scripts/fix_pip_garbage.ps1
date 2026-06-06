# Remove pastas "~*" corrompidas no site-packages (pip que falhou no meio do uninstall).
# Sintoma: import google.api_core trava/quebra ao ler METADATA.
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { Write-Error "python nao encontrado no PATH"; exit 1 }
$sp = Join-Path (Split-Path (Split-Path $py)) "Lib\site-packages"
if (-not (Test-Path $sp)) { Write-Error "site-packages nao encontrado: $sp"; exit 1 }

$removed = @()
Get-ChildItem $sp -Directory | Where-Object { $_.Name -match '^~' } | ForEach-Object {
    Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    $removed += $_.Name
}

Write-Host "site-packages: $sp"
Write-Host "Removidas $($removed.Count) pastas corrompidas."
if ($removed.Count -gt 0) { $removed | ForEach-Object { Write-Host "  - $_" } }
Write-Host "Teste: python -c `"import google.api_core; print('OK')`""