# Hara's Digital Gallery

Flask web app for Hara Giannopoulos's art: gallery, drawing detail pages, About page, commission requests, and a private admin panel.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. The SQLite database (`gallery.db`) is created and seeded with the first drawings on first run.

**Admin:** http://127.0.0.1:5000/admin (default login `admin` / `changeme`).

## Environment variables (set these in production)

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Long random string for sessions |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Admin login |
| `DATABASE_URL` | e.g. Railway MySQL URL (`mysql://...` is auto-converted to `mysql+pymysql://`). Defaults to SQLite. |

Deploy on Railway with the included `Procfile` (`gunicorn app:app`).

## Structure

- `app.py` — models (`Drawing`, `Order`), public routes, admin routes
- `templates/` — public pages; `templates/admin/` — admin panel
- `static/css/style.css`, `static/js/main.js`
- `static/uploads/` — drawing images (uploaded through admin)

## To update

- **Her photo:** save as `static/img/hara.jpg` and change the filename in `templates/about.html`.
- **Instagram link:** set the `href` in the footer of `templates/base.html`.
- **Drawings:** add / edit / delete from Admin → Drawings. Delete the "Coming Soon" placeholder once real pieces are in.

> Note: on Railway, files saved to `static/uploads` are lost on redeploy. Before launch, move image storage to Cloudinary (or a Railway volume).
