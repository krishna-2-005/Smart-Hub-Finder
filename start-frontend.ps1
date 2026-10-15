# Starts the React dashboard on http://localhost:5173 (proxies /api to the backend).
# Pass -Https to serve on https://<LAN-IP>:5173 for testing GPS on a phone (self-signed certificate).
param([switch]$Https)
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$root\frontend"
if ($Https) { npm run dev:https } else { npm run dev }
