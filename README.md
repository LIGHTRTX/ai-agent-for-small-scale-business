# TEJAS Business Agent

This project discovers local businesses, enriches their contact details, classifies their industry, and prepares outreach emails.

## Streamlit dashboard

The dashboard entry point is `app.py`.

Run it locally with:

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

Local Streamlit runs use the project `.env` file or `GROQ_API_KEY` from the environment. The dashboard never displays the key.

## Deploy to Streamlit Community Cloud

1. Push this project to a GitHub repository. Keep `.env`, `logs/`, and generated `output/` files out of the repository.
2. Open [share.streamlit.io](https://share.streamlit.io/) and choose **Create app**.
3. Select the repository, branch, and `app.py` as the main file.
4. In the app settings, open **Secrets** and add:

```toml
GROQ_API_KEY = "your-groq-api-key"
```

5. Deploy the app. Streamlit Community Cloud will provide a shareable URL in this format:

```text
https://your-app-name.streamlit.app
```

Use that hosted URL when presenting the dashboard. Do not put the API key in source code or commit it to GitHub.

Community Cloud storage is ephemeral. New CSV rows and generated lead packages written by the running app can disappear after a restart or redeploy. The app seeds a small synthetic demo dataset on first launch when no CSV exists; it uses reserved `.example` contact details, not private leads. Use the dashboard for the hosted demo, and use the CLI or a durable database for persistent production storage.

## CLI commands

```bash
python3 main.py savekey YOUR_GROQ_KEY
python3 main.py test
python3 main.py run
```

The CLI and Streamlit dashboard use the same workflow service. Existing leads are stored in `data/businesses.csv`; generated lead packages are written under `output/`.
