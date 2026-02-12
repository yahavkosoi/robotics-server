# Robotics Lab File Sharing Server

Local network file-sharing server with:
- Public multi-file upload form (name + per-file description/version)
- Admin login, grouped upload tree, bulk/single download, bulk/single copy-string
- Admin settings for server config, admins, uploader names/grades
- Legacy migration from existing `users.json` + `groups.json`

## Stack
- Backend: FastAPI (Python)
- Frontend: React + Vite (JS) with shadcn-style component structure
- Storage: JSON files + filesystem blobs under `data/`

## Admin Bootstrap (First Run)
On first backend start, the app creates a default admin if `data/admins.json` is empty.

- Username: `Admin`
- Password source: `ROBOTICS_DEFAULT_ADMIN_PASSWORD` environment variable

Do not commit real credentials. Keep local values in `.env` (ignored by git).

## Run Backend
```bash
cd robotics-server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ROBOTICS_DEFAULT_ADMIN_PASSWORD='change-this-before-first-run'
python -m server.run
```
Backend runs on `http://0.0.0.0:8080`.

## Frontend Runtime Note
Do not run the frontend dev server (`npm run dev`) for normal usage.
Only run the Python backend server with `python -m server.run`.

## Runtime Data
The app manages runtime JSON/files under `data/`:
- `data/admins.json`
- `data/sessions.json`
- `data/uploaders.json`
- `data/uploads.json`
- `data/settings.json`
- `data/groups.json`
- `data/files/*`
- `data/migration_reports/*`

These files can contain personal or session data and should stay untracked.

## Legacy Import
In admin settings page, use:
- Users path: `/path/to/users.json`
- Groups path: `/path/to/groups.json`

Or call API:
```bash
POST /api/admin/migrate/import-legacy
{
  "users_path": "/path/to/users.json",
  "groups_path": "/path/to/groups.json"
}
```

## Notes
- File retention default is 30 days; physical files are deleted, metadata is kept.
- Multi-download is intentionally non-ZIP (individual browser downloads).
- Copy format is:
  `fn1, fn2 [v1, v2] {AdminName - Uploader1, Uploader2} (dd-mm-yyyy)`
