#!/usr/bin/env python3
"""Publish bank earnings reports to this GitHub Pages site. Standard library only.

Add (or refresh) one bank:
  python3 scripts/publish.py add --slug ophc-q3-2026 --report path/to/report.html \
      --media path/to/bank-folder [--media path/to/bank-folder/video] \
      --bank "OptimumBank Holdings" --ticker OPHC --quarter "Q3 2026" \
      --released 2026-11-12 --headline "One-line headline"

      --method "One paragraph: basis, adjustments, how ratios were computed, consensus and
                peer sources, caveats. Data was read on Nov 13, 2026." \
      --source "OptimumBank Q3 2026 earnings release (GlobeNewswire)|https://..." \
      --source "Zacks earnings preview (TradingView)|https://..."

Replace only the Method and sources section of a bank already on the site:
  python3 scripts/publish.py method --slug ophc-q3-2026 --method "..." --source "Label|URL" ...

Rebuild every bank page and the home page from what is already in the repo:
  python3 scripts/publish.py build

Every page also gets Open Graph and Twitter tags pointing at a 1200x630 share card:
og.png at the root for the home page, <slug>/og.png for each bank. `add` writes the bank's
card figures to <slug>/og.json and renders the card with scripts/og.py (needs cairosvg and
the Inter font); its price line comes from data/prices/<TICKER>.csv.

Every page's Method and sources section is rendered from templates/method-and-sources.html,
so all banks share PNC's layout: one method paragraph, a bulleted list of named source links,
then "Not investment advice." on its own line.
"""
import argparse, html, json, os, re, shutil, sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "reports.json")
SITE_TITLE = "Bank Earnings Reports"
SITE_URL = "https://dmgerbino.github.io/bank-earnings-reports/"
SITE_DESC = "Quarterly earnings from U.S. banks, each with a report, an infographic and a short narrated video."
OG_MARK = ("<!-- pub:og -->", "<!-- /pub:og -->")
MEDIA_EXT = (".mp4", ".srt", ".png", ".svg", ".jpg", ".webp")
MAX_BYTES = 50 * 1024 * 1024
METHOD_TEMPLATE = os.path.join(ROOT, "templates", "method-and-sources.html")
METHOD_MARK = ("<!-- pub:method -->", "<!-- /pub:method -->")


def load():
    if not os.path.exists(MANIFEST):
        return []
    return json.load(open(MANIFEST))


def save(rows):
    with open(MANIFEST, "w") as f:
        json.dump(rows, f, indent=2)
        f.write("\n")


def find(files, pattern):
    for f in sorted(files):
        if re.search(pattern, f):
            return f
    return None


def media_block(slug, row):
    d = os.path.join(ROOT, slug)
    files = os.listdir(d)
    full = find(files, r"(?<!short)-captioned\.mp4$")
    short = find(files, r"-short-captioned\.mp4$")
    full_clean = find(files, r"(?<!short)-clean\.mp4$")
    short_clean = find(files, r"-short-clean\.mp4$")
    full_srt = find(files, r"(?<!short)\.srt$")
    short_srt = find(files, r"-short\.srt$")
    poster = find(files, r"-mobile\.png$")
    info = find(files, r"-infographic\.png$") or find(files, r"-infographic\.svg$") or poster or find(files, r"-mobile\.svg$")
    name = html.escape(row["bank"])
    out = ['<!-- pub:media --><section class="pub-media" aria-label="Video and infographic">']
    vids = [(full, "Full video", full_srt), (short, "60-second cut", short_srt)]
    vids = [v for v in vids if v[0]]
    if vids:
        out.append('<h2>Watch</h2><div class="pub-vids">')
        for src, label, _ in vids:
            p = f' poster="{poster}"' if poster else ""
            out.append(f'<figure><video controls playsinline preload="metadata"{p} src="{src}"></video>'
                       f'<figcaption>{label}</figcaption></figure>')
        out.append("</div>")
    if info:
        out.append(f'<h2>Infographic</h2><a class="pub-img" href="{info}">'
                   f'<img src="{info}" alt="{name} {html.escape(row["quarter"])} earnings infographic" loading="lazy"></a>')
    dl = []
    for f, label in [(full_clean, "Full video, no captions"), (short_clean, "60-second cut, no captions"),
                     (full_srt, "Captions (.srt)"), (short_srt, "60-second captions (.srt)"),
                     (poster, "Mobile graphic (PNG)"), (find(files, r"-mobile\.svg$"), "Mobile graphic (SVG)"),
                     (find(files, r"-infographic\.svg$"), "Infographic (SVG)")]:
        if f and not (f == info and f.endswith(".png")):
            dl.append(f'<a href="{f}" download>{label}</a>')
    if dl:
        out.append('<p class="pub-dl">Downloads: ' + " · ".join(dl) + "</p>")
    out.append("</section><!-- /pub:media -->")
    return "".join(out) if (vids or info) else ""


PUB_CSS = """<style>
.pub-nav{max-width:46rem;margin:0 auto;padding:12px 16px 0;font:600 .875rem/1.4 var(--sans,system-ui,-apple-system,sans-serif)}
.pub-nav a,.pub-media a{color:var(--accent,var(--brand,#2A6DB0))}
.pub-media{margin:1.5rem 0;font-family:var(--sans,system-ui,-apple-system,sans-serif)}
.pub-vids{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr));gap:16px;max-width:520px}
.pub-vids figure{margin:0}
.pub-vids video{display:block;width:100%;aspect-ratio:9/16;background:#000;border-radius:10px}
.pub-vids figcaption{font-size:.875rem;color:var(--muted,#5A626C);margin-top:6px}
.pub-img img{display:block;width:100%;max-width:520px;height:auto;border-radius:10px;border:1px solid var(--rule,var(--border,#DDE1E6))}
.pub-dl{font-size:.875rem;color:var(--muted,#5A626C);line-height:1.8}
</style>"""


def render_method(method, sources):
    """Fill the fixed Method and sources template. sources: list of "Label|URL" strings."""
    if not method or not method.strip():
        sys.exit("--method is required: one paragraph explaining the method, ending with the date the data was read.")
    if not sources:
        sys.exit("At least one --source \"Label|URL\" is required.")
    items = []
    for s in sources:
        if "|" not in s:
            sys.exit(f"--source must be \"Label|URL\", got: {s}")
        label, url = (x.strip() for x in s.rsplit("|", 1))
        if not label or not re.match(r"https?://", url):
            sys.exit(f"--source needs a plain-English label and an http(s) URL, got: {s}")
        items.append(f'<li><a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener">'
                     f'{html.escape(label, quote=False)}</a></li>')
    t = open(METHOD_TEMPLATE, encoding="utf-8").read()
    # Drop the explanatory comment, keep the pub:method markers.
    t = re.sub(r"<!--(?! /?pub:method).*?-->\n?", "", t, flags=re.S)
    text = " ".join(method.split())
    text = re.sub(r"\s*Not investment advice\.?\s*$", "", text)
    return (t.replace("{{METHOD}}", html.escape(text, quote=False))
             .replace("{{SOURCES}}", "\n".join(items)).strip())


def swap_method(src, block):
    """Put block in place of the report's existing Method and sources section."""
    a, b = METHOD_MARK
    i = src.find(a)
    if i >= 0:
        j = src.find(b, i)
        return src[:i] + block + src[j + len(b):]
    m = re.search(r"<h2[^>]*>\s*Method (?:and|&amp;|&) sources\s*</h2>", src, re.I)
    if not m:
        sys.exit("No 'Method and sources' heading found in report.html to replace.")
    start = m.start()
    sec = re.search(r"<section[^>]*>\s*$", src[:start])
    if sec:
        start = sec.start()
        end = src.find("</section>", m.end()) + len("</section>")
    else:
        ends = [k for k in (src.find(t, m.end()) for t in ("<h2", "</div>", "</main>", "<script", "</body>")) if k >= 0]
        end = min(ends) if ends else len(src)
    return src[:start] + block + "\n" + src[end:].lstrip("\n")


def set_method(slug, method, sources):
    path = os.path.join(ROOT, slug, "report.html")
    src = open(path, encoding="utf-8").read()
    open(path, "w", encoding="utf-8").write(swap_method(src, render_method(method, sources)))


def build_page(slug, row):
    d = os.path.join(ROOT, slug)
    src = open(os.path.join(d, "report.html"), encoding="utf-8").read()
    if METHOD_MARK[0] not in src:
        print(f"Warning: {slug}/report.html does not use templates/method-and-sources.html; "
              f"run: python3 scripts/publish.py method --slug {slug} --method ... --source ...", file=sys.stderr)
    if not re.match(r"\s*<!doctype", src, re.I):
        src = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
               '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>\n'
               + src + "\n</body></html>\n")
    tags = bank_og(slug, row)
    if tags:
        h = re.search(r"</head>", src, re.I)
        src = src[:h.start()] + tags + "\n" + src[h.start():]
    nav = PUB_CSS + '<nav class="pub-nav"><a href="../">← All bank earnings reports</a></nav>'
    m = re.search(r"<body[^>]*>", src, re.I)
    src = src[:m.end()] + "\n" + nav + "\n" + src[m.end():]
    block = media_block(slug, row)
    if block:
        i = src.find('class="lede"')
        if i < 0:
            i = src.find("</h1>")
        end = src.find("\n", i)
        h = src.find("</header>", i)
        if 0 <= h < i + 400:
            end = h + len("</header>")
        src = src[:end] + "\n" + block + src[end:]
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(src)


def og_tags(title, desc, url, image, alt, kind="article"):
    """Open Graph and Twitter card tags. url and image must be absolute."""
    e = lambda x: html.escape(x, quote=True)
    tags = [
        ("property", "og:type", kind), ("property", "og:site_name", SITE_TITLE),
        ("property", "og:title", title), ("property", "og:description", desc),
        ("property", "og:url", url), ("property", "og:image", image),
        ("property", "og:image:width", "1200"), ("property", "og:image:height", "630"),
        ("property", "og:image:alt", alt),
        ("name", "twitter:card", "summary_large_image"), ("name", "twitter:title", title),
        ("name", "twitter:description", desc), ("name", "twitter:image", image),
        ("name", "twitter:image:alt", alt),
    ]
    return (OG_MARK[0] + "\n" + "\n".join(f'<meta {k}="{n}" content="{e(v)}">' for k, n, v in tags)
            + "\n" + OG_MARK[1])


def bank_og(slug, row):
    """Tags for one bank page, or "" when it has no share card yet."""
    if not os.path.exists(os.path.join(ROOT, slug, "og.png")):
        print(f"Warning: {slug}/og.png missing, so the page has no share tags. "
              f"Run: python3 scripts/og.py {slug}", file=sys.stderr)
        return ""
    v = row.get("updated") or row.get("added") or row["released"]
    v = f"{v}-{card_version()}"
    title = f'{row["bank"]} ({row["ticker"]}) {row["quarter"]} earnings'
    return og_tags(title, row["headline"], f"{SITE_URL}{slug}/", f"{SITE_URL}{slug}/og.png?v={v}",
                   f'{row["bank"]} {row["quarter"]} earnings card: price chart, net income and EPS')


def card_version():
    """CARD_VERSION from scripts/og.py, read as text so pages build without cairosvg."""
    m = re.search(r'^CARD_VERSION = "([^"]+)"', open(os.path.join(ROOT, "scripts", "og.py")).read(), re.M)
    return m.group(1) if m else "1"


def render_cards(rows, slugs=(), force=False):
    """Render missing share cards (or the named ones). Needs cairosvg."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import og
    if force or not os.path.exists(os.path.join(ROOT, "og.png")):
        og.brand_png()
    for r in rows:
        png = os.path.join(ROOT, r["slug"], "og.png")
        if (force or r["slug"] in slugs or not os.path.exists(png)) and og.load_spec(r["slug"]):
            og.bank_png(r)


def fmt_date(s):
    y, m, dd = map(int, s.split("-"))
    return date(y, m, dd).strftime("%b %-d, %Y")


def build_index(rows):
    rows = sorted(rows, key=lambda r: (r["released"], r.get("added", "")), reverse=True)
    cards = []
    for r in rows:
        d = os.path.join(ROOT, r["slug"])
        thumb = find(os.listdir(d), r"-mobile\.png$") if os.path.isdir(d) else None
        t = (f'<img src="{r["slug"]}/{thumb}" alt="" loading="lazy" width="72" height="90">' if thumb
             else '<span class="ph" aria-hidden="true"></span>')
        cards.append(
            f'<li><a href="{r["slug"]}/">{t}<span class="tx">'
            f'<span class="nm">{html.escape(r["bank"])} <span class="tk">{html.escape(r["ticker"])}</span></span>'
            f'<span class="mt">{html.escape(r["quarter"])} · released {fmt_date(r["released"])}</span>'
            f'<span class="hl">{html.escape(r["headline"])}</span></span></a></li>')
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{SITE_TITLE}</title>
<meta name="description" content="{SITE_DESC}">
{og_tags(SITE_TITLE, SITE_DESC, SITE_URL, SITE_URL + "og.png?v=" + card_version(), "Bank Earnings Reports by @dmgerbino", "website")}
<style>
:root{{--bg:#F6F7F9;--surface:#FFFFFF;--fg:#11161C;--muted:#56606C;--rule:#D9DEE4;--accent:#2A6DB0;color-scheme:light}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#000000;--surface:#0D0F12;--fg:#F0EDEA;--muted:#A39F99;--rule:#25292E;--accent:#5B9BD5;color-scheme:dark}}}}
:root[data-theme="dark"]{{--bg:#000000;--surface:#0D0F12;--fg:#F0EDEA;--muted:#A39F99;--rule:#25292E;--accent:#5B9BD5;color-scheme:dark}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font:1rem/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:46rem;margin:0 auto;padding:2rem max(16px,env(safe-area-inset-right,0px)) 4rem max(16px,env(safe-area-inset-left,0px))}}
h1{{font-size:1.75rem;line-height:1.2;margin:0 0 .5rem;text-wrap:balance}}
.sub{{color:var(--muted);margin:0 0 1.5rem;max-width:60ch}}
ul{{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:12px}}
li a{{display:flex;gap:14px;align-items:flex-start;background:var(--surface);border:1px solid var(--rule);border-radius:12px;padding:12px;color:inherit;text-decoration:none;min-width:0}}
li a:hover,li a:focus-visible{{border-color:var(--accent)}}
li a:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}
img,.ph{{flex:none;width:72px;height:90px;border-radius:8px;object-fit:cover;background:#000;display:block}}
.tx{{display:flex;flex-direction:column;gap:2px;min-width:0}}
.nm{{font-weight:650}}.tk{{color:var(--accent);font-weight:600;font-size:.875rem;margin-left:4px}}
.mt{{color:var(--muted);font-size:.875rem}}
.hl{{margin-top:4px;line-height:1.4}}
footer{{margin-top:2.5rem;color:var(--muted);font-size:.875rem}}
footer a{{color:var(--accent)}}
</style></head><body><main>
<h1>{SITE_TITLE}</h1>
<p class="sub">Quarterly results from U.S. banks. Each report compares the quarter with estimates and peers, with an infographic and a short narrated video. Newest first.</p>
<ul>
{chr(10).join(cards)}
</ul>
<footer>By <a href="https://dmgerbino.com">dmgerbino.com</a>. Not investment advice.</footer>
</main></body></html>
"""
    open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(page)
    open(os.path.join(ROOT, ".nojekyll"), "w").close()


def check_sizes():
    big = []
    for dp, _, fs in os.walk(ROOT):
        if "/.git" in dp:
            continue
        for f in fs:
            p = os.path.join(dp, f)
            if os.path.getsize(p) > MAX_BYTES:
                big.append(p)
    if big:
        sys.exit("Files over 50 MB (GitHub will reject or warn): " + ", ".join(big))


def cmd_add(a):
    rows = load()
    d = os.path.join(ROOT, a.slug)
    os.makedirs(d, exist_ok=True)
    if os.path.abspath(a.report) != os.path.join(d, "report.html"):
        shutil.copyfile(a.report, os.path.join(d, "report.html"))
    for m in a.media or []:
        for f in os.listdir(m):
            p = os.path.join(m, f)
            if os.path.isfile(p) and f.lower().endswith(MEDIA_EXT):
                shutil.copyfile(p, os.path.join(d, f))
    if a.method or a.source:
        set_method(a.slug, a.method, a.source)
    elif METHOD_MARK[0] not in open(os.path.join(d, "report.html"), encoding="utf-8").read():
        sys.exit("Give --method and --source so the page uses the Method and sources template.")
    set_og_spec(a)
    today = date.today().isoformat()
    row = {"slug": a.slug, "bank": a.bank, "ticker": a.ticker, "quarter": a.quarter,
           "released": a.released, "headline": a.headline, "added": today}
    old = next((r for r in rows if r["slug"] == a.slug), None)
    if old:  # a redone report keeps its first-published date
        row["added"] = old.get("added", today)
        if row["added"] != today:
            row["updated"] = today
    rows = [r for r in rows if r["slug"] != a.slug] + [row]
    save(rows)
    render_cards(rows, slugs=[a.slug])
    cmd_build(None)


def set_og_spec(a):
    """Write <slug>/og.json from the --exchange/--net-income/--eps flags and place the prices."""
    path = os.path.join(ROOT, a.slug, "og.json")
    spec = json.load(open(path)) if os.path.exists(path) else {}
    for k in ("exchange", "net_income_label", "net_income", "net_income_note", "eps_label", "eps", "eps_note"):
        v = getattr(a, k)
        if v is not None:
            spec[k] = v
    if a.no_eps:
        for k in ("eps_label", "eps", "eps_note"):
            spec.pop(k, None)
    missing = [k for k in ("exchange", "net_income", "net_income_note") if not spec.get(k)]
    if missing:
        sys.exit("The share card needs --" + ", --".join(m.replace("_", "-") for m in missing)
                 + " (see README, Share cards).")
    if spec.get("eps") and not spec.get("eps_note"):
        sys.exit("--eps needs --eps-note naming the consensus it beat or missed.")
    prices = os.path.join(ROOT, "data", "prices", f"{a.ticker.upper()}.csv")
    if a.prices:
        os.makedirs(os.path.dirname(prices), exist_ok=True)
        if os.path.abspath(a.prices) != prices:
            shutil.copyfile(a.prices, prices)
    elif not os.path.exists(prices):
        sys.exit(f"Give --prices path/to/{a.ticker.upper()}.csv (date,close for the 90 days to release).")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2, ensure_ascii=False)
        f.write("\n")


def cmd_method(a):
    if not os.path.exists(os.path.join(ROOT, a.slug, "report.html")):
        sys.exit(f"No {a.slug}/report.html in the repo.")
    set_method(a.slug, a.method, a.source)
    cmd_build(None)


def cmd_og(a):
    rows = load()
    render_cards(rows, slugs=a.slug, force=not a.slug)
    cmd_build(None)


def cmd_build(_):
    rows = load()
    for r in rows:
        build_page(r["slug"], r)
    build_index(rows)
    check_sizes()
    print(f"Built {len(rows)} report page(s) and index.html")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("add")
    for k in ("slug", "report", "bank", "ticker", "quarter", "released", "headline"):
        p.add_argument("--" + k, required=True)
    p.add_argument("--media", action="append")
    p.add_argument("--method", help="Method paragraph for the Method and sources section")
    p.add_argument("--source", action="append", help='"Label|URL", repeat for each source')
    # Share card (scripts/og.py). Required for a new bank; kept from og.json on a redo.
    p.add_argument("--exchange", help='Listing exchange as the release writes it: "NYSE", "Nasdaq", "NYSE American"')
    p.add_argument("--net-income", dest="net_income", help='Card figure, e.g. "$2.10B" or "$392K"')
    p.add_argument("--net-income-note", dest="net_income_note",
                   help='Change vs year-ago quarter, e.g. "▲ 15.1% vs. Q3 2025" or "▲ from −$2.7M in Q3 2025"')
    p.add_argument("--net-income-label", dest="net_income_label", help='Default "Net income"')
    p.add_argument("--eps", help='Only when a real pre-release consensus exists, e.g. "$5.09"')
    p.add_argument("--eps-label", dest="eps_label", help='e.g. "Adjusted EPS" or "Diluted EPS"')
    p.add_argument("--eps-note", dest="eps_note", help='e.g. "Beat $4.97 consensus"')
    p.add_argument("--no-eps", dest="no_eps", action="store_true", help="Drop the EPS line from the card")
    p.add_argument("--prices", help="CSV of daily closes (date,close), copied to data/prices/<TICKER>.csv")
    p.set_defaults(fn=cmd_add)
    q = sp.add_parser("method")
    q.add_argument("--slug", required=True)
    q.add_argument("--method", required=True)
    q.add_argument("--source", action="append", required=True)
    q.set_defaults(fn=cmd_method)
    sp.add_parser("build").set_defaults(fn=cmd_build)
    o = sp.add_parser("og", help="Re-render share cards: all, or --slug ones, then rebuild pages")
    o.add_argument("--slug", action="append", default=[])
    o.set_defaults(fn=cmd_og)
    a = ap.parse_args()
    a.fn(a)
