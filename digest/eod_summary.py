"""
digest/eod_summary.py
======================
End-of-Day Summary Report -- sent at 9:00 PM every day.
Shows:
- Total jobs scanned today across all 3 runs
- How many you applied to
- Cold emails sent
- Recruiters connected on LinkedIn
- Follow-ups pending
- Tomorrow's priority list

Sent via Telegram + saved as HTML for browser viewing.
"""

import os
from datetime import datetime, date
from tracker.application_tracker import load_tracker, get_stats, get_follow_ups_due
from utils.logger import log

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "")


def get_todays_stats() -> dict:
    """Pull today's specific stats from the tracker."""
    df = load_tracker()
    today_str = date.today().strftime("%Y-%m-%d")

    if df.empty:
        return {}

    todays = df[df.get("date_found", df.index.astype(str)) == today_str] if "date_found" in df.columns else df

    overall = get_stats()

    return {
        "date":           today_str,
        "jobs_found_today":   len(todays),
        "applied_today":      len(todays[todays["status"] == "Applied"]) if "status" in todays.columns else 0,
        "emails_today":       len(todays[todays["status"] == "Cold Email Sent"]) if "status" in todays.columns else 0,
        "apply_worthy_today": len(todays[todays["verdict"] == "APPLY"]) if "verdict" in todays.columns else 0,
        "total_applied":      overall.get("total_applied", 0),
        "total_emails":       overall.get("cold_emails", 0),
        "interviews":         overall.get("interviews", 0),
        "follow_ups_due":     len(get_follow_ups_due()),
        "avg_score":          overall.get("avg_score", 0),
        "top_companies":      overall.get("top_companies", {}),
    }


def build_eod_telegram(stats: dict, scan_counts: dict) -> str:
    """Build End-of-Day Telegram message."""
    today = datetime.now().strftime("%A, %B %d")

    # Progress bar for goal (target: 10 apps/day)
    applied = stats.get("applied_today", 0)
    goal = 10
    filled = min(applied, goal)
    bar = "[" + "#" * filled + "-" * (goal - filled) + "]"

    msg = f"""
=== END OF DAY REPORT | {today} ===

TODAY'S SCANS:
  Morning (8am):  {scan_counts.get('morning', 0)} jobs found
  Afternoon (2pm): {scan_counts.get('afternoon', 0)} jobs found
  Evening (6pm):  {scan_counts.get('evening', 0)} jobs found
  Total today:    {stats.get('jobs_found_today', 0)} unique jobs

TODAY'S ACTIVITY:
  Applied:        {stats.get('applied_today', 0)}/10 {bar}
  Cold emails:    {stats.get('emails_today', 0)}
  APPLY-rated:    {stats.get('apply_worthy_today', 0)}

CAMPAIGN TOTAL:
  All applications: {stats.get('total_applied', 0)}
  Cold emails sent: {stats.get('total_emails', 0)}
  Interviews:       {stats.get('interviews', 0)}
  Follow-ups due:   {stats.get('follow_ups_due', 0)}
  Avg match score:  {stats.get('avg_score', 0)}/100

TOMORROW MORNING:
  - Check follow-ups: {stats.get('follow_ups_due', 0)} pending
  - Scanner runs at 8:00 AM automatically
  - Open apply_today.html to start applying

Keep pushing. September is your peak window.
Sai Vivek Rangaraju | rangarajusaivivek.github.io
""".strip()
    return msg


def build_eod_html(stats: dict, scan_counts: dict) -> str:
    """Build End-of-Day HTML report."""
    today = datetime.now().strftime("%A, %B %d, %Y")
    applied = stats.get("applied_today", 0)
    goal = 10
    pct = min(int(applied / goal * 100), 100)

    top_cos = stats.get("top_companies", {})
    top_cos_html = "".join(
        f'<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1a2e45">'
        f'<span>{co}</span><span style="color:#00d4ff;font-weight:600">{cnt} jobs</span></div>'
        for co, cnt in list(top_cos.items())[:8]
    )

    scan_rows = "".join(
        f'<tr><td style="padding:8px;color:#5a7a9a">{scan}</td>'
        f'<td style="padding:8px;font-weight:600;color:#e2eaf4">{count}</td>'
        f'<td style="padding:8px;color:#00e676">Completed</td></tr>'
        for scan, count in [
            ("Morning Scan (8:00 AM)", scan_counts.get("morning", 0)),
            ("Afternoon Scan (2:00 PM)", scan_counts.get("afternoon", 0)),
            ("Evening Scan (6:00 PM)",  scan_counts.get("evening", 0)),
        ]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>End of Day Report -- {today}</title>
<style>
  :root {{ --bg:#050a0f; --card:#0b1420; --border:#1a2e45; --text:#e2eaf4;
           --muted:#5a7a9a; --accent:#00d4ff; --green:#00e676; --orange:#ff9800; }}
  * {{ box-sizing:border-box; margin:0; padding:0 }}
  body {{ font-family:-apple-system,Arial,sans-serif; background:var(--bg); color:var(--text); padding:20px }}
  .container {{ max-width:680px; margin:0 auto }}
  .banner {{ background:linear-gradient(135deg,#0A1628,#112240); border:1px solid var(--border);
             border-radius:12px; padding:24px; margin-bottom:20px; text-align:center }}
  .banner h1 {{ font-size:22px; margin-bottom:6px }}
  .banner p  {{ color:var(--muted); font-size:13px }}
  .card {{ background:var(--card); border:1px solid var(--border); border-radius:10px;
           padding:18px; margin-bottom:16px }}
  .card h2 {{ font-size:14px; color:var(--accent); margin-bottom:14px;
              text-transform:uppercase; letter-spacing:.06em }}
  .stat-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:12px }}
  .stat {{ background:#060e18; border-radius:8px; padding:14px; text-align:center }}
  .stat .num {{ font-size:28px; font-weight:700; color:var(--accent) }}
  .stat .lbl {{ font-size:11px; color:var(--muted); margin-top:4px }}
  .progress-wrap {{ margin:14px 0 }}
  .progress-label {{ display:flex; justify-content:space-between; font-size:12px;
                     color:var(--muted); margin-bottom:6px }}
  .progress-bar {{ height:10px; background:#1a2e45; border-radius:5px; overflow:hidden }}
  .progress-fill {{ height:100%; border-radius:5px;
                    background:linear-gradient(90deg,var(--accent),#006aff);
                    transition:width .4s }}
  table {{ width:100%; border-collapse:collapse }}
  th {{ background:#060e18; color:var(--muted); font-size:11px; padding:8px;
        text-align:left; text-transform:uppercase; letter-spacing:.05em }}
  td {{ padding:8px; border-bottom:1px solid var(--border); font-size:13px }}
  .tip {{ background:#0a1e0a; border:1px solid #2d5a40; border-radius:8px;
          padding:14px; font-size:13px; color:#a5d6a7; line-height:1.7 }}
  .footer {{ text-align:center; color:var(--muted); font-size:11px; margin-top:20px }}
</style>
</head>
<body>
<div class="container">

  <div class="banner">
    <h1>End of Day Report</h1>
    <p>{today} | Sai Vivek Rangaraju | F-1 OPT</p>
  </div>

  <!-- TODAY'S SCANS -->
  <div class="card">
    <h2>Today's Scans</h2>
    <table>
      <thead><tr><th>Scan</th><th>Jobs Found</th><th>Status</th></tr></thead>
      <tbody>{scan_rows}</tbody>
      <tfoot><tr>
        <td style="font-weight:600;padding:8px">Total Unique Jobs</td>
        <td style="font-weight:700;color:var(--accent);padding:8px">{stats.get('jobs_found_today', 0)}</td>
        <td></td>
      </tr></tfoot>
    </table>
  </div>

  <!-- TODAY'S ACTIVITY -->
  <div class="card">
    <h2>Today's Activity</h2>
    <div class="progress-wrap">
      <div class="progress-label">
        <span>Applications today</span>
        <span style="color:var(--accent)">{applied} / {goal} goal</span>
      </div>
      <div class="progress-bar">
        <div class="progress-fill" style="width:{pct}%"></div>
      </div>
    </div>
    <div class="stat-grid">
      <div class="stat"><div class="num">{stats.get('applied_today', 0)}</div><div class="lbl">Applied Today</div></div>
      <div class="stat"><div class="num">{stats.get('emails_today', 0)}</div><div class="lbl">Cold Emails Sent</div></div>
      <div class="stat"><div class="num">{stats.get('apply_worthy_today', 0)}</div><div class="lbl">APPLY-Rated Jobs</div></div>
      <div class="stat"><div class="num">{stats.get('follow_ups_due', 0)}</div><div class="lbl">Follow-ups Due</div></div>
    </div>
  </div>

  <!-- CAMPAIGN TOTALS -->
  <div class="card">
    <h2>Campaign Totals</h2>
    <div class="stat-grid">
      <div class="stat"><div class="num">{stats.get('total_applied', 0)}</div><div class="lbl">Total Applied</div></div>
      <div class="stat"><div class="num">{stats.get('total_emails', 0)}</div><div class="lbl">Cold Emails Total</div></div>
      <div class="stat"><div class="num">{stats.get('interviews', 0)}</div><div class="lbl">Interviews</div></div>
      <div class="stat"><div class="num">{stats.get('avg_score', 0)}</div><div class="lbl">Avg Match Score</div></div>
    </div>
  </div>

  <!-- TOP COMPANIES -->
  {'<div class="card"><h2>Top Companies in Tracker</h2>' + top_cos_html + '</div>' if top_cos_html else ''}

  <!-- TOMORROW'S PLAN -->
  <div class="tip">
    <strong>Tomorrow's priority list:</strong><br>
    - Morning scan runs at 8:00 AM automatically<br>
    - {stats.get('follow_ups_due', 0)} follow-up(s) to send first thing<br>
    - Open apply_today.html -> apply to all APPLY-rated jobs<br>
    - Send cold emails to hiring managers for top matches<br>
    - Post 1 LinkedIn update (thesis / VAPT / cert content)<br>
    - September is your peak window. Keep the pace.
  </div>

  <div class="footer">
    Sai Vivek Rangaraju | MS Cybersecurity WSU 2026 | CEH | F-1 OPT<br>
    <a href="https://rangarajusaivivek.github.io" style="color:var(--accent)">Portfolio</a> |
    <a href="https://linkedin.com/in/rangarajusaivivek" style="color:var(--accent)">LinkedIn</a>
  </div>
</div>
</body>
</html>"""


def send_eod_telegram(text: str) -> bool:
    """Send EOD summary via Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        log.info("Telegram not configured -- EOD report saved locally only")
        return False
    try:
        import httpx
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            httpx.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT, "text": chunk},
                timeout=10,
            )
        log.info("EOD report sent via Telegram")
        return True
    except Exception as e:
        log.error(f"Telegram EOD send failed: {e}")
        return False


def generate_eod_report(scan_counts: dict = None):
    """
    Generate and send the end-of-day report.
    Called automatically at 9:00 PM by the scheduler.
    """
    if scan_counts is None:
        scan_counts = {"morning": 0, "afternoon": 0, "evening": 0}

    stats  = get_todays_stats()
    text   = build_eod_telegram(stats, scan_counts)
    html   = build_eod_html(stats, scan_counts)

    # Save locally always
    os.makedirs("data", exist_ok=True)
    today_str = date.today().strftime("%Y%m%d")
    with open(f"data/eod_report_{today_str}.html", "w", encoding="utf-8") as f:
        f.write(html)
    with open(f"data/eod_report_{today_str}.txt", "w", encoding="utf-8") as f:
        f.write(text)

    # Send via Telegram
    send_eod_telegram(text)

    # Print to console
    print("\n" + "=" * 52)
    print(text)
    print("=" * 52)
    print(f"EOD HTML report saved: data/eod_report_{today_str}.html")

    return stats
