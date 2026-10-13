# Memecoin Narrative Radar V2 — cloud-hosted Discord alerts

**Runs without an open terminal or PC.** GitHub Actions checks public Bluesky and Google News feeds, filters out low-quality personal chatter, and delivers selected narrative leads via your private Discord webhook.

## Set up with GitHub (no X credits, no always-open Windows terminal)

1. Create a **free GitHub account** if needed: https://github.com/signup.
2. Create a repo at https://github.com/new and call it `memecoin-radar-v2`. Select **Public** to use standard GitHub-hosted Actions for free. (Your webhook remains secret if stored correctly.) You can use a private repo instead, but free monthly Actions minutes can run out when checking every 5 minutes.
3. Upload **`scanner.py`** and **`README.md`** to the repo: click **Add file → Upload files**, drag the two files, and **Commit changes**. Do **not** upload a `.env` file or your webhook address.
4. Add the workflow: in the GitHub repo click **Add file → Create new file**. In the filename box enter exactly `.github/workflows/radar.yml`. Copy the contents from the `radar.yml` file in the ZIP and paste them. Click **Commit changes**. (Windows sometimes hides `.github` folders; this browser method is easiest.)
5. Open **Settings → Secrets and variables → Actions → New repository secret**. Name it **`DISCORD_WEBHOOK`** and paste your **existing Discord webhook URL** as the secret value. Click **Add secret**. Keep the webhook URL private.
6. Open the **Actions** tab → **Memecoin Narrative Radar V2** → **Run workflow**. Select `test_alert` and run. A green successful run plus a new message in Discord confirms the connection.
7. Run it manually **one more time with `test_alert` unchecked**. The first scan quietly learns existing stories (no backlog spam). After that, GitHub schedules scans about every **5 minutes**, even if your computer is off. The next genuinely new story that passes the filter should trigger an alert.

## What you get

- Headlines and links from original Bluesky posts or Google News RSS items
- High-signal filters for animal rescues and names, viral memes, AI-related events, and unusual discoveries
- Less noise: rejects many conversations, ads, token promotions and very short posts
- At most 3 alerts per scheduled scan, with a possible ticker idea and simple narrative explanation
- State/history stored as **post URL hashes** in `state.json` (no secrets); duplicate and similar-story suppression
- Uses only the **Python standard library**; no pip installs or X API keys
- Customizable `MIN_SCORE`, `MAX_ALERTS`, and `MAX_AGE_HOURS` in `radar.yml`

## Important limits

- **Discord does not host code.** GitHub Actions runs the scanner; Discord only receives alerts.
- GitHub has a **5-minute minimum** for scheduled Actions. Scheduled jobs can start later or occasionally be skipped. These are not real-time alerts, and this is **not** an X/Twitter monitor.
- Google News results often link through Google News rather than directly to the publisher; the linked page leads to the source. Bluesky links go to the original post.
- Public Bluesky endpoints can rate-limit, change, or return 403 errors. Google News continues if Bluesky fails.
- GitHub public repo standard hosted runners are generally free; **private repositories have usage quotas** and overages can cost money if billing is enabled. A small public repo is the simplest zero-API-credit option. Public repos expose the scanner code and hashed story state, not your secret webhook.
- Repeatedly pushing state may require GitHub Actions to have **read/write Workflow permissions**. If logs say `Permission denied` on `git push`, open repo **Settings → Actions → General → Workflow permissions** and enable **Read and write permissions** (if available).
- Tickers are creative suggestions only; no guarantee a token is new, real, valuable, or safe.

## How to stop

Open GitHub repo → **Actions** → select **Memecoin Narrative Radar V2** → `...` menu → **Disable workflow**.

## Troubleshooting

- **No Discord test alert?** Check that the repository secret is named *exactly* `DISCORD_WEBHOOK`, and check Actions job logs. If the webhook leaked publicly, regenerate it in Discord.
- **No narrative alerts yet?** First real scan deliberately sends none. Later scans only send newly discovered stories that pass the stronger filter. Be patient; fewer alerts is expected.
- **Actions button missing?** The workflow must be present at `.github/workflows/radar.yml` on the default branch.
- **Bluesky error 403?** Google News still works. Public APIs can restrict automated access.
- **`git push` denied?** Turn on Actions read/write workflow permissions in Settings → Actions → General.

## Optional local one-off test

Run `python scanner.py` with the `DISCORD_WEBHOOK` environment variable set. This isn't required for cloud operation.
