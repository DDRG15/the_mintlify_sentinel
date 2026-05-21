# First Thing Tomorrow

## Step 1 — Live Notification Test (15 min)

1. Open Discord → go to the channel you want alerts in
2. Channel Settings → Integrations → Webhooks → New Webhook → Copy URL
3. Open `.env.example`, copy it to `.env`, paste the URL replacing `PASTE_YOUR_DISCORD_WEBHOOK_URL_HERE`
4. Run the live test:

```bash
python main.py --discord-webhook YOUR_DISCORD_WEBHOOK_URL_HERE
```

5. Confirm the message appears in Discord with the correct format (red embed, 6 CRITICAL findings listed)
6. If Slack is ready too, test that at the same time with `--slack-webhook`

---

## Step 2 — Start Streamlit UI (rest of the session)

Once the live test passes, open `docs/STREAMLIT_PLAN.md` and start Phase 1.

The first file to create is `app.py` in the project root.
