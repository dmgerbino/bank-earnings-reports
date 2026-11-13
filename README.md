# bank-earnings-reports
Destination for bank earnings reports created by dmgerbino's AI agents.

Live site: https://dmgerbino.github.io/bank-earnings-reports/ (GitHub Pages, branch `main`, folder `/`).

## Layout

- `index.html` — home page listing every bank, newest release first. Generated; don't edit by hand.
- `reports.json` — the list the home page is built from (slug, bank, ticker, quarter, release date, headline).
- `<ticker>-<quarter>-<year>/` — one folder per report, e.g. `pnc-q3-2026/`:
  - `report.html` — the report exactly as the earnings-report skill made it (source).
  - `index.html` — the published page: the report plus a back link, the videos and the infographic. Generated.
  - Media from infographic-to-video-v2: `*-captioned.mp4`, `*-short-captioned.mp4`, `*-clean.mp4`, `*-short-clean.mp4`, `*.srt`, `*-mobile.png/.svg`, and `*-infographic.png/.svg`.
- `.nojekyll` — tells GitHub Pages to serve files as they are.

## Adding a new bank (what each scan does at the end)

1. Run the earnings-report skill, then infographic-to-video-v2, so you have the report HTML and a folder of media.
2. From the repo root, run:

   ```
   python3 scripts/publish.py add --slug ophc-q3-2026 \
     --report path/to/report.html \
     --media path/to/bank-folder --media path/to/bank-folder/video \
     --bank "OptimumBank Holdings" --ticker OPHC --quarter "Q3 2026" \
     --released 2026-11-12 \
     --headline "The report's one-line headline"
   ```

   It copies the report and media into the bank's folder, builds that folder's `index.html`, adds the bank to `reports.json`, rebuilds the home page, and stops if any file is over 50 MB. Running it again for the same slug replaces that bank's entry.
3. Commit and push to `main`:

   ```
   git add -A && git commit -m "Add OPHC Q3 2026" && git push origin main
   ```

   Pages updates within a minute or two.

To rebuild every page from what's already in the repo (after changing the script, say): `python3 scripts/publish.py build`.

The script needs only Python 3, no packages and no build step.
