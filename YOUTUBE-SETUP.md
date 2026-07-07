# YouTube upload — one-time setup

The **YouTube** button on each clip is hidden until you complete these steps.
This is the one feature ClipStudio can't do fully offline — Google requires
your own OAuth credentials. Takes about 5 minutes.

## 1. Install the Google client libraries

```bash
.venv\Scripts\pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
```

(They're intentionally not in `requirements.txt` so the default install stays lean.)

## 2. Create an OAuth client

1. Go to <https://console.cloud.google.com/> and create (or pick) a project.
2. **APIs & Services → Library →** enable **YouTube Data API v3**.
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID.**
   - Application type: **Desktop app**.
4. Download the JSON and save it as **`client_secret.json`** in the ClipStudio
   project root (next to `run.bat`).
5. On the **OAuth consent screen**, add your own Google account under
   **Test users** (while the app is in "Testing").

## 3. Connect

Restart ClipStudio. The app now detects the credentials. The first upload opens
a browser window asking you to sign in and grant access; after that a token is
saved to `data/youtube_token.json` and you won't be asked again.

## Notes / limits

- While your OAuth app is in **Testing**, uploads are forced to **private** and
  you get roughly **6 uploads/day** (the API's default 10,000-unit quota).
- Category defaults to **People & Blogs** (id 22); tags come from the clip.
- Nothing here is billed — it uses your own free Google quota.

> This path is built but **unverified in this build** because it needs your
> credentials. If anything errors after setup, tell me the message and I'll fix it.
