#!/usr/bin/env python3
"""Render a football 'match day' scoreboard of GitHub stats as an SVG.

Usage:
  GITHUB_TOKEN=... python matchday.py <login> <out.svg>
  python matchday.py --mock <out.svg>      # render with sample data
"""
import datetime as dt
import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

QUERY = """
query($login: String!) {
  user(login: $login) {
    login
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if payload.get("errors"):
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    u = payload["data"]["user"]
    cc = u["contributionsCollection"]
    days = [d for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    langs = {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            langs.setdefault(n, [0, e["node"]["color"] or "#9e9e9e"])
            langs[n][0] += e["size"]
    return {
        "login": u["login"],
        "contributions": cc["contributionCalendar"]["totalContributions"],
        "commits": cc["totalCommitContributions"],
        "prs": cc["totalPullRequestContributions"],
        "issues": cc["totalIssueContributions"],
        "stars": sum(r["stargazerCount"] for r in u["repositories"]["nodes"]),
        "repos": u["repositories"]["totalCount"],
        "days": [(d["date"], d["contributionCount"]) for d in days],
        "langs": [(k, v[0], v[1]) for k, v in langs.items()],
    }


def mock():
    import random
    random.seed(7)
    today = dt.date(2026, 9, 30)
    days = []
    for i in range(365, -1, -1):
        d = today - dt.timedelta(days=i)
        days.append((d.isoformat(), random.choice([0, 0, 0, 0, 1, 2, 3, 5])))
    return {
        "login": "AnKIT7-ops", "contributions": sum(c for _, c in days), "commits": 93,
        "prs": 3, "issues": 0, "stars": 0, "repos": 10, "days": days,
        "langs": [("Python", 820000, "#3572A5"), ("Jupyter Notebook", 300000, "#DA5B0B"),
                  ("HTML", 90000, "#e34c26"), ("JavaScript", 60000, "#f1e05a"),
                  ("C", 40000, "#555555"), ("Dockerfile", 5000, "#384d54"), ("CSS", 3000, "#563d7c")],
    }


def streaks(days):
    counts = [c for _, c in days]
    longest = run = 0
    for c in counts:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    cur = 0
    i = len(counts) - 1
    if i >= 0 and counts[i] == 0:  # today not played yet: don't break the run
        i -= 1
    while i >= 0 and counts[i] > 0:
        cur += 1
        i -= 1
    return cur, longest


def form(days, n=5):
    weeks = []
    for k in range(n):
        chunk = days[len(days) - 7 * (k + 1): len(days) - 7 * k]
        weeks.append(sum(c for _, c in chunk))
    res = []
    for total in reversed(weeks):
        res.append("W" if total >= 3 else "D" if total >= 1 else "L")
    return res


def possession(langs, top=5):
    langs = sorted(langs, key=lambda x: -x[1])
    total = sum(s for _, s, _ in langs) or 1
    head = [(n, s / total, c) for n, s, c in langs[:top]]
    rest = sum(s for _, s, _ in langs[top:]) / total
    if rest > 0.0005:
        head.append(("Other", rest, "#8d8d8d"))
    return head


FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"
MONO = "'DejaVu Sans Mono', 'Courier New', monospace"
LIME = "#C6F432"


def ball(cx, cy, r):
    return (f'<g transform="translate({cx},{cy})"><circle r="{r}" fill="#fff" stroke="#111" stroke-width="1.2"/>'
            f'<polygon points="0,{-r*0.42:.1f} {r*0.4:.1f},{-r*0.13:.1f} {r*0.25:.1f},{r*0.34:.1f} '
            f'{-r*0.25:.1f},{r*0.34:.1f} {-r*0.4:.1f},{-r*0.13:.1f}" fill="#111"/></g>')


def render(d):
    W, H = 860, 520
    cur, longest = streaks(d["days"])
    frm = form(d["days"])
    poss = possession(d["langs"])
    end = dt.date.fromisoformat(d["days"][-1][0]) if d["days"] else dt.date.today()
    start = end - dt.timedelta(days=365)
    season = f"SEASON {start.year % 100:02d}/{end.year % 100:02d}"

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         f'role="img" aria-label="Match day stats for {escape(d["login"])}">']
    o.append('<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
             '<stop offset="0" stop-color="#0a2e14"/><stop offset="1" stop-color="#06180b"/></linearGradient>'
             '<clipPath id="card"><rect width="860" height="520" rx="16"/></clipPath></defs>')
    o.append('<g clip-path="url(#card)"><rect width="860" height="520" fill="url(#bg)"/>')
    for i in range(0, W, 86):  # mowing stripes
        if (i // 86) % 2 == 0:
            o.append(f'<rect x="{i}" y="0" width="86" height="{H}" fill="#ffffff" opacity="0.025"/>')
    # faint pitch lines
    o.append('<g fill="none" stroke="#ffffff" stroke-opacity="0.07" stroke-width="2">'
             '<line x1="430" y1="0" x2="430" y2="520"/><circle cx="430" cy="260" r="70"/>'
             '<rect x="-2" y="160" width="90" height="200"/><rect x="772" y="160" width="90" height="200"/></g>')

    # ---- scoreboard ----
    o.append('<rect x="150" y="22" width="560" height="78" rx="12" fill="#030a05" stroke="#1f5c2e" stroke-width="1.5"/>')
    o.append(f'<text x="290" y="58" text-anchor="middle" font-family="{FONT}" font-size="20" font-weight="800" fill="#fff" letter-spacing="1">ANKIT FC</text>')
    o.append(f'<text x="290" y="80" text-anchor="middle" font-family="{FONT}" font-size="11" fill="#8fbf9a">@{escape(d["login"])}</text>')
    o.append(f'<text x="570" y="58" text-anchor="middle" font-family="{FONT}" font-size="20" font-weight="800" fill="#fff" letter-spacing="1">BUGS UTD</text>')
    o.append(f'<text x="570" y="80" text-anchor="middle" font-family="{FONT}" font-size="11" fill="#8fbf9a">legacy code · flaky tests</text>')
    o.append('<rect x="382" y="34" width="96" height="46" rx="8" fill="#0d1f12" stroke="#2e7d32"/>')
    o.append(f'<text x="430" y="68" text-anchor="middle" font-family="{MONO}" font-size="28" font-weight="700" fill="{LIME}">{d["contributions"]}<tspan fill="#5d7a63">-</tspan>0</text>')
    o.append(f'<text x="430" y="95" text-anchor="middle" font-family="{FONT}" font-size="9.5" font-weight="700" fill="#8fbf9a" letter-spacing="2">{season} · LIVE</text>')
    o.append('<circle cx="690" cy="40" r="5" fill="#ff3b30"><animate attributeName="opacity" values="1;0.2;1" dur="1.6s" repeatCount="indefinite"/></circle>')
    o.append(ball(170, 40, 9))

    # ---- stat tiles (left) ----
    tiles = [
        ("GOALS", d["contributions"], "contributions · last 12 months"),
        ("SHOTS ON TARGET", d["commits"], "commits"),
        ("ASSISTS", d["prs"], "pull requests"),
        ("TACKLES", d["issues"], "issues opened"),
        ("FAN VOTES", d["stars"], "stars earned"),
        ("SQUAD SIZE", d["repos"], "public repos"),
    ]
    tx0, ty0, tw, th, gap = 24, 118, 170, 74, 10
    for idx, (label, val, sub) in enumerate(tiles):
        c, r = idx % 3, idx // 3
        x, y = tx0 + c * (tw + gap), ty0 + r * (th + gap)
        o.append(f'<rect x="{x}" y="{y}" width="{tw}" height="{th}" rx="10" fill="#000" fill-opacity="0.35" stroke="#ffffff" stroke-opacity="0.08"/>')
        o.append(f'<text x="{x+14}" y="{y+22}" font-family="{FONT}" font-size="10" font-weight="700" fill="#8fbf9a" letter-spacing="1.2">{label}</text>')
        o.append(f'<text x="{x+14}" y="{y+52}" font-family="{MONO}" font-size="26" font-weight="700" fill="#fff">{val}</text>')
        o.append(f'<text x="{x+14}" y="{y+66}" font-family="{FONT}" font-size="10" fill="#6f9479">{escape(sub)}</text>')

    # ---- unbeaten run + form (right) ----
    rx, ry, rw, rh = 574, 118, 262, 158
    o.append(f'<rect x="{rx}" y="{ry}" width="{rw}" height="{rh}" rx="10" fill="#000" fill-opacity="0.35" stroke="#ffffff" stroke-opacity="0.08"/>')
    o.append(f'<text x="{rx+16}" y="{ry+24}" font-family="{FONT}" font-size="10" font-weight="700" fill="#8fbf9a" letter-spacing="1.2">UNBEATEN RUN</text>')
    o.append(f'<text x="{rx+16}" y="{ry+64}" font-family="{MONO}" font-size="36" font-weight="700" fill="{LIME}">{cur}<tspan font-size="14" fill="#8fbf9a"> day{"s" if cur != 1 else ""}</tspan></text>')
    o.append(f'<text x="{rx+150}" y="{ry+24}" font-family="{FONT}" font-size="10" font-weight="700" fill="#8fbf9a" letter-spacing="1.2">CLUB RECORD</text>')
    o.append(f'<text x="{rx+150}" y="{ry+64}" font-family="{MONO}" font-size="36" font-weight="700" fill="#fff">{longest}<tspan font-size="14" fill="#8fbf9a"> day{"s" if longest != 1 else ""}</tspan></text>')
    o.append(f'<text x="{rx+16}" y="{ry+100}" font-family="{FONT}" font-size="10" font-weight="700" fill="#8fbf9a" letter-spacing="1.2">FORM · LAST 5 WEEKS</text>')
    colors = {"W": ("#2ecc71", "#04210f"), "D": ("#9e9e9e", "#111"), "L": ("#e74c3c", "#fff")}
    for i, res in enumerate(frm):
        fx = rx + 16 + i * 46
        bg, fg = colors[res]
        o.append(f'<rect x="{fx}" y="{ry+110}" width="38" height="30" rx="6" fill="{bg}"/>')
        o.append(f'<text x="{fx+19}" y="{ry+131}" text-anchor="middle" font-family="{FONT}" font-size="15" font-weight="800" fill="{fg}">{res}</text>')

    # ---- possession by language (bottom) ----
    px, py, pw = 24, 300, 812
    o.append(f'<text x="{px}" y="{py}" font-family="{FONT}" font-size="10" font-weight="700" fill="#8fbf9a" letter-spacing="1.2">POSSESSION · LANGUAGES ACROSS PUBLIC REPOS</text>')
    bx = px
    o.append(f'<clipPath id="pbar"><rect x="{px}" y="{py+12}" width="{pw}" height="22" rx="11"/></clipPath><g clip-path="url(#pbar)">')
    for name, frac, color in poss:
        w = pw * frac
        o.append(f'<rect x="{bx:.1f}" y="{py+12}" width="{w+0.6:.1f}" height="22" fill="{color}"/>')
        if w > 46:
            o.append(f'<text x="{bx + w/2:.1f}" y="{py+27}" text-anchor="middle" font-family="{FONT}" font-size="11" font-weight="700" fill="#fff" stroke="#000" stroke-opacity="0.35" stroke-width="2" paint-order="stroke">{frac*100:.0f}%</text>')
        bx += w
    o.append('</g>')
    lx, ly = px, py + 60
    for name, frac, color in poss:
        label = f"{name} {frac*100:.1f}%"
        o.append(f'<circle cx="{lx+6}" cy="{ly-4}" r="5" fill="{color}"/>')
        o.append(f'<text x="{lx+16}" y="{ly}" font-family="{FONT}" font-size="12" fill="#d7e8da">{escape(label)}</text>')
        lx += 22 + len(label) * 6.6
        if lx > px + pw - 120:
            lx, ly = px, ly + 22

    # ---- momentum: weekly contributions over the season ----
    counts = [c for _, c in d["days"]]
    weekly = [sum(counts[i:i + 7]) for i in range(max(0, len(counts) - 364), len(counts), 7)]
    my = ly + 34
    o.append(f'<text x="{px}" y="{my}" font-family="{FONT}" font-size="10" font-weight="700" fill="#8fbf9a" letter-spacing="1.2">MOMENTUM · WEEKLY ACTIVITY</text>')
    base, mh = my + 50, 36
    o.append(f'<line x1="{px}" y1="{base}" x2="{px+pw}" y2="{base}" stroke="#ffffff" stroke-opacity="0.15"/>')
    peak = max(weekly) if weekly and max(weekly) > 0 else 1
    bw = pw / max(len(weekly), 1)
    for i, v in enumerate(weekly):
        h = 0 if v == 0 else max(2, mh * v / peak)
        col = LIME if i >= len(weekly) - 5 else "#2ecc71"
        o.append(f'<rect x="{px + i*bw + 1:.1f}" y="{base - h:.1f}" width="{bw - 2:.1f}" height="{h:.1f}" rx="1.5" fill="{col}" fill-opacity="{0.95 if v else 0}"/>')

    # ---- footer ----
    o.append(f'<line x1="24" y1="{H-44}" x2="836" y2="{H-44}" stroke="#ffffff" stroke-opacity="0.08"/>')
    o.append(f'<text x="24" y="{H-20}" font-family="{FONT}" font-size="11" fill="#6f9479">Tactic: gegenpress every bug · Formation: 4-3-3 · Home ground: GitHub</text>')
    o.append(f'<text x="836" y="{H-20}" text-anchor="end" font-family="{FONT}" font-size="11" fill="#6f9479">Updated {end.isoformat()}</text>')
    o.append('</g></svg>')
    return "\n".join(o)


def main():
    args = sys.argv[1:]
    if args and args[0] == "--mock":
        data, out = mock(), args[1]
    else:
        login, out = args[0], args[1]
        data = fetch(login, os.environ["GITHUB_TOKEN"])
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(data))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
