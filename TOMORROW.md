# Next Session

## Step 1 — Streamlit UI, Phase 1 (~3-4 hours)

All live tests are done. Discord, Slack, and Docker are confirmed working.
The only thing left to build is the browser interface.

Open `docs/STREAMLIT_PLAN.md` and start Phase 1.

### What to do first

1. Add `streamlit==1.35.0` to `requirements.txt`
2. Run `pip install streamlit==1.35.0`
3. Create `app.py` in the project root

### What Phase 1 includes

- Page title and description
- File uploader — baseline spec (V1)
- File uploader — target spec (V2)
- "Run Sentinel" button
- Results section:
  - Summary bar: X CRITICAL / Y MEDIUM / Z LOW
  - One colored card per finding (red, yellow, blue)
  - Clean diff message if no findings
- Download button for `output/changelog.mdx`

### Run command

```bash
streamlit run app.py
```

---

## Completed

- [x] Discord live test — HTTP 204, 6 CRITICAL findings delivered
- [x] Slack live test — HTTP 200, delivered
- [x] Docker build + run — full pipeline inside container, exits 0
