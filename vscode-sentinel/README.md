# Sentinel VS Code Extension

Sentinel extension for on-call workflows backed by the Sentinel FastAPI service.

## Features
- Dedicated **Sentinel** Activity Bar view with grouped incident tree.
- Incident detail webview with pipeline progress, RCA evidence, verification, rollback, and timeline.
- Command palette operations for trigger/create/approve/reject/retry/refresh/diff.
- Status bar health and active incident summary.
- Virtual patch diff viewer from backend `patch_text`.

## Settings
- `sentinel.serverUrl` (default: `http://127.0.0.1:8000`)
- `sentinel.pollIntervalMs` (default: `5000`)
- `sentinel.autoRefresh` (default: `true`)

## Development
```bash
cd /Users/abhinavprakash/Desktop/Sentinal/vscode-sentinel
npm install
npm run compile
```

Run extension tests:
```bash
npm test
```

Create VSIX:
```bash
npm run package
```
