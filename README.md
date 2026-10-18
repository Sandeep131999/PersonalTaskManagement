# Daymark

A personal task planner with a React calendar, dashboard, and reports. Tasks can be Pending, On hold, or Completed. The FastAPI backend stores tasks in a private Google spreadsheet.

## Deploy it

Deploy the **backend to Render** and the **frontend to Vercel**. Deploy the backend first so you can use its URL when setting up the frontend.

### 1. Prepare Google Sheets

1. In [Google Cloud Console](https://console.cloud.google.com/), create a project and enable **Google Sheets API**.
2. Create a **service account**, then create and download a JSON key. Keep this key private.
3. Create a Google spreadsheet. Copy its ID from the URL: the part after `/spreadsheets/d/` and before `/edit`.
4. Share the spreadsheet with the service account's `client_email` from the JSON key, with **Editor** access. The sheet can remain private.

The app creates a `Tasks` worksheet and its column headers automatically.

### 2. Deploy the backend to Render

1. Push this project to a GitHub repository.
2. In Render, create a **New → Web Service** connected to the repository.
3. Set **Root Directory** to `backend`.
4. Use these commands:

   **Build command**
   ```sh
   uv sync --locked
   ```

   **Start command**
   ```sh
   uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

5. Add these environment variables in Render (**Environment**). Use the raw JSON contents of the service-account key as the value of `GOOGLE_SERVICE_ACCOUNT_JSON`—not the local file path.

   | Variable | Value |
   | --- | --- |
   | `GOOGLE_SHEETS_SPREADSHEET_ID` | Spreadsheet ID copied in step 1 |
   | `GOOGLE_SERVICE_ACCOUNT_JSON` | Full contents of the downloaded JSON key |
   | `API_ACCESS_TOKEN` | A new secret token you generate; see below |
   | `APP_TIMEZONE` | `Asia/Kolkata` (or your timezone) |
   | `CORS_ORIGINS` | Your Vercel site URL; update after deploying the frontend |

6. Deploy. The backend URL will look like `https://your-service.onrender.com`. Check `https://your-service.onrender.com/api/health`.

Generate a strong API token locally in PowerShell; do not share it or commit it:

```powershell
uv run --project backend python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Deploy the frontend to Vercel

1. In Vercel, import the same GitHub repository.
2. Set **Root Directory** to `frontend` and the framework preset to **Vite**.
3. Add this environment variable before deploying:

   | Variable | Value |
   | --- | --- |
   | `VITE_API_URL` | Your Render backend URL, e.g. `https://your-service.onrender.com` |

4. Deploy. Copy the Vercel site URL, e.g. `https://your-app.vercel.app`.
5. In Render, set `CORS_ORIGINS` to that exact Vercel site URL (no trailing slash), then redeploy/restart the backend.
6. Open the Vercel site. In **Your workspace → API access**, enter the same `API_ACCESS_TOKEN` value configured in Render, then select **Verify & Save**.

The frontend keeps the token in the current browser tab's session storage. Anyone who has the token can access the API, so keep it private. The API docs are public at `<Render URL>/docs`.

## Run locally

1. Configure `backend/.env` using `backend/.env.example`. Set the spreadsheet ID, JSON credentials (or `GOOGLE_APPLICATION_CREDENTIALS` file path), optional API token, and timezone.
2. In one terminal:

   ```powershell
   cd backend
   uv sync
   uv run uvicorn app.main:app --reload
   ```

3. In another terminal:

   ```powershell
   cd frontend
   npm install
   Copy-Item .env.example .env
   npm run dev
   ```

4. Open the Vite URL shown in the terminal. If you configured `API_ACCESS_TOKEN`, enter it in **Your workspace → API access**.

## Notes

- Keep service-account keys and API tokens out of Git, screenshots, and chat. If a token or key was shared, replace it.
- Google Sheets is intended here for a single user and light usage; it does not provide full database transaction guarantees.
- Render's free web services may sleep when idle, so the first request after a period of inactivity can take longer.
