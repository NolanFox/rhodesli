"""Build the self-contained mobile-first Morning Mystery HTML for Nolan (Session 171)."""
import base64, io
from PIL import Image

CASE = '/Users/nolanfox/rhodesli/docs/strategy/2026-07-reengagement/morning-mystery-belle-isle'
IMAGES = {
    '01659': '/Users/nolanfox/rhodesli/raw_photos/01659_p_13akf5twbc1045.jpg',
    '02068': '/Users/nolanfox/rhodesli/raw_photos/02068_p_13akf5twbc3600.jpg',
}

def data_uri(path, maxw=1000, q=72):
    im = Image.open(path).convert('RGB')
    if im.width > maxw:
        im = im.resize((maxw, int(im.height * maxw / im.width)))
    buf = io.BytesIO()
    im.save(buf, format='JPEG', quality=q, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()

uri = {k: data_uri(v) for k, v in IMAGES.items()}
print('img1 kb:', len(uri['01659'])//1024, 'img2 kb:', len(uri['02068'])//1024)

HTML = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Morning Mystery — Belle Isle Young Man</title>
<style>
  :root {{ --bg:#faf7f2; --card:#fff; --ink:#2b2622; --muted:#6b6259; --amber:#b45309; --line:#e7ddd0; --indigo:#4338ca; }}
  @media (prefers-color-scheme: dark) {{ :root {{ --bg:#1a1714; --card:#241f1b; --ink:#ece5da; --muted:#a89e91; --amber:#f0a44a; --line:#3a332c; --indigo:#a5b4fc; }} }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
  .wrap {{ max-width:680px; margin:0 auto; padding:20px 16px 64px; }}
  h1 {{ font-family:Georgia,"Times New Roman",serif; font-size:1.55rem; line-height:1.2; margin:.2em 0 .1em; }}
  h2 {{ font-family:Georgia,serif; font-size:1.15rem; margin:1.4em 0 .4em; }}
  .kicker {{ color:var(--amber); font-weight:700; letter-spacing:.06em; text-transform:uppercase; font-size:.72rem; }}
  .lede {{ color:var(--muted); font-size:.95rem; margin:.3em 0 1em; }}
  .photos {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; margin:12px 0; }}
  .photos figure {{ margin:0; }} .photos img {{ width:100%; border-radius:10px; border:1px solid var(--line); display:block; }}
  .photos figcaption {{ font-size:.72rem; color:var(--muted); margin-top:4px; text-align:center; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px; margin:10px 0; }}
  .card b {{ color:var(--ink); }} .eid {{ color:var(--indigo); font-weight:700; font-size:.78rem; }}
  .contradiction {{ border-left:4px solid var(--amber); }}
  .calls {{ background:var(--card); border:2px dashed var(--amber); border-radius:12px; padding:16px; margin:18px 0; }}
  .calls h2 {{ margin-top:0; }}
  .q {{ margin:14px 0; }} .q p {{ margin:0 0 8px; font-weight:600; }}
  .opt {{ display:block; padding:11px 12px; border:1px solid var(--line); border-radius:9px; margin:6px 0; cursor:pointer; min-height:44px; }}
  .opt input {{ margin-right:8px; }} .opt:has(input:checked) {{ border-color:var(--amber); background:color-mix(in srgb,var(--amber) 10%,transparent); }}
  input[type=text] {{ width:100%; padding:11px; border:1px solid var(--line); border-radius:9px; background:var(--card); color:var(--ink); font-size:16px; }}
  button {{ width:100%; padding:15px; border:0; border-radius:11px; background:var(--amber); color:#fff; font-size:1.02rem; font-weight:700; cursor:pointer; margin:10px 0; min-height:52px; }}
  button.ghost {{ background:transparent; color:var(--amber); border:1.5px solid var(--amber); }}
  #reveal {{ display:none; }}
  table {{ width:100%; border-collapse:collapse; font-size:.86rem; margin:8px 0; }}
  th,td {{ text-align:left; padding:8px 6px; border-bottom:1px solid var(--line); vertical-align:top; }}
  th {{ color:var(--muted); font-weight:600; }}
  .verdict-pill {{ display:inline-block; background:color-mix(in srgb,var(--indigo) 16%,transparent); color:var(--indigo); font-weight:700; padding:2px 9px; border-radius:20px; font-size:.8rem; }}
  .agree {{ color:var(--amber); font-weight:700; }}
  .foot {{ color:var(--muted); font-size:.76rem; margin-top:24px; border-top:1px solid var(--line); padding-top:12px; }}
</style></head>
<body><div class="wrap">
  <div class="kicker">The Rhodesli Research Desk · Morning Mystery</div>
  <h1>The Belle Isle Conservatory Young Man</h1>
  <p class="lede">One case. ~15 minutes. <b>Make your own three calls before you reveal the sealed
  verdicts.</b> Two models investigated this blind overnight; their conclusions are hidden until you tap.</p>

  <div class="photos">
    <figure><img src="{uri['01659']}" alt="Photo 01659"><figcaption>01659 — him + Albert + Irving Fox</figcaption></figure>
    <figure><img src="{uri['02068']}" alt="Photo 02068"><figcaption>02068 — same man, larger group</figcaption></figure>
  </div>

  <h2>The mystery</h2>
  <p>A young man appears in <b>both</b> photos from the Charles Fox (Dayton) collection, an outdoor
  WWI-era outing. In both he stands with <b>Albert Fox</b> and <b>Irving Fox</b>. Never identified;
  once mislabeled "Harry Fox" and detached. Who is he?</p>

  <h2>The evidence</h2>
  <div class="card"><span class="eid">E1</span> <b>Same man in both photos.</b> The two faces match at
  L2 = 0.629 (calibrated 0.914) — same person, high confidence.</div>
  <div class="card"><span class="eid">E2</span> <b>The matcher can't name him.</b> Against all ~3,285
  faces, his nearest non-self match is L2 = 1.208 — different-person territory. Closest confirmed people
  are Fox/Burd relatives, all at weak distances. Honest answer: "family-adjacent, nobody specific."</div>
  <div class="card"><span class="eid">E3-E6</span> <b>He runs with the Fox brothers.</b> Beside Albert
  Fox (b.~1896) and Irving Fox (b.1898) in both frames — they share parents, so they're brothers. In
  1917-18 they're ~21 and ~19. He reads as a peer of that generation.</div>
  <div class="card"><span class="eid">E8, E10</span> <b>When &amp; where.</b> Clothing dates both photos
  ~1915-1922; one shows a conservatory. It matches <b>Belle Isle, Detroit</b> (Library of Congress
  LC-DIG-det-4a17798 + 6 sources) — location strong. The tighter <b>1917-18</b> date (Albert's Detroit
  residence + 1918 draft) is a lead still to re-verify (<span class="eid">E11</span>).</div>
  <div class="card contradiction"><span class="eid">E9 vs E10</span> <b>A contradiction worth seeing.</b>
  The database's current location estimates still say "United States" (01659) and "New York City"
  (02068) — stale, and at odds with the Belle Isle / Detroit research.</div>
  <div class="card"><span class="eid">E7, E12</span> <b>The GEDCOM candidate looks wrong.</b> The identity
  carries a weak (0.30) link to <b>Harry Isaackovitz</b> (b.1881). He'd be ~36-37 here — not a peer of two
  20-year-olds — and no reference photo of him exists to compare against.</div>

  <div class="calls">
    <h2>Your three calls</h2>
    <div class="q"><p>1. Who is he?</p>
      <label class="opt"><input type="radio" name="who">Fox sibling / close relative of Albert &amp; Irving</label>
      <label class="opt"><input type="radio" name="who">Someone outside the family (friend/associate)</label>
      <label class="opt"><input type="radio" name="who">Abstain — not enough to say</label></div>
    <div class="q"><p>2. Keep or drop the Harry Isaackovitz (b.1881) candidate?</p>
      <label class="opt"><input type="radio" name="harry">Keep</label>
      <label class="opt"><input type="radio" name="harry">Drop</label></div>
    <div class="q"><p>3. What one piece of evidence would most cheaply settle it?</p>
      <input type="text" name="lever" placeholder="e.g. an album caption, a labeled photo of the Detroit circle..."></div>
    <button class="ghost" onclick="document.getElementById('reveal').style.display='block';this.style.display='none';document.getElementById('reveal').scrollIntoView({{behavior:'smooth'}});">
      I've made my calls — reveal the sealed verdicts ▼</button>
  </div>

  <div id="reveal">
    <h2>The sealed verdicts</h2>
    <p>Both investigators, independently: <span class="agree">ABSTAIN + DROP the Harry candidate.</span></p>
    <table>
      <tr><th></th><th>Gemini 3.1 Pro</th><th>GPT-5.6-Sol</th></tr>
      <tr><td><b>Verdict</b></td><td><span class="verdict-pill">ABSTAIN</span></td><td><span class="verdict-pill">ABSTAIN</span></td></tr>
      <tr><td><b>Who</b></td><td>Peer of Albert &amp; Irving in Detroit; <b>likely a friend or extended relative</b> not in the DB</td><td>An unidentified peer; a Fox relationship is <b>possible but can't be distinguished</b> from someone outside the family</td></tr>
      <tr><td><b>Harry</b></td><td><b>Drop</b> — age 36-37 vs peers ~20; no reference photo</td><td><b>Drop</b> — same age tension + no reference photo</td></tr>
      <tr><td><b>Cheapest lever</b></td><td>A <b>labeled reference photo</b> of the brothers' Detroit circle</td><td>A <b>contemporaneous album caption</b> naming the three men</td></tr>
    </table>
    <p><b>The bake-off signal:</b> both abstain, but Gemini will infer "family friend/relative" while Sol
    refuses even that. And they want different cheap evidence — a <b>face</b> vs a <b>document</b>. Both are findable.</p>

    <h2>The desk recommends</h2>
    <div class="card">1. <b>Correct the location</b> to Detroit / Belle Isle (E10, strong) — a real historical delta regardless of the identity.<br>
    2. <b>Drop</b> the Harry Isaackovitz candidate (both models, decisively).<br>
    3. Leave the subject unidentified, tag "Fox Detroit outing, 1917-18," and open a
    <b>One-Question Witness Packet</b>: ask whoever holds the Charles Fox album whether either photo is
    captioned, and whether the family remembers a young man in the brothers' Detroit circle.</div>

    <div class="calls">
      <h2>Your adjudication</h2>
      <div class="q"><p>Drop Harry candidate?</p>
        <label class="opt"><input type="radio" name="a_harry">Yes, drop</label>
        <label class="opt"><input type="radio" name="a_harry">No, keep</label></div>
      <div class="q"><p>Correct location to Detroit / Belle Isle?</p>
        <label class="opt"><input type="radio" name="a_loc">Yes</label>
        <label class="opt"><input type="radio" name="a_loc">No</label></div>
      <div class="q"><p>Open a witness packet?</p>
        <label class="opt"><input type="radio" name="a_wit">Yes</label>
        <label class="opt"><input type="radio" name="a_wit">No</label></div>
      <div class="q"><p>Did you play-first (make your calls before revealing) or reveal-first?</p>
        <label class="opt"><input type="radio" name="mode">Play-first</label>
        <label class="opt"><input type="radio" name="mode">Reveal-first</label></div>
      <div class="q"><p>Was this worth opening?</p>
        <label class="opt"><input type="radio" name="worth">Yes</label>
        <label class="opt"><input type="radio" name="worth">No</label></div>
    </div>
  </div>

  <p class="foot">Prep cost ≈ $0.14 of the $2/night cap · inputs hashed in manifest.json · sealed
  verdicts in verdict-gemini.json / verdict-sol.json · nothing in the confirmed identity set was
  modified. Session 171 · The Rhodesli Research Desk.</p>
</div></body></html>"""

open(f'{CASE}/morning-mystery.html', 'w').write(HTML)
print('wrote', f'{CASE}/morning-mystery.html', '(', len(HTML)//1024, 'kb )')
