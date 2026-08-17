"""
digest/daily_digest.py
========================
Sends a morning digest with:
- New jobs found today (APPLY + INVESTIGATE)
- Follow-ups due today
- Generated cold emails to review
- Market stats

Channels: Email (SendGrid) + Telegram bot
"""

import os
from datetime import datetime
from tracker.application_tracker import get_stats, get_follow_ups_due
from utils.logger import log

SENDGRID_KEY = os.getenv("SENDGRID_API_KEY", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")
DIGEST_EMAIL = os.getenv("DIGEST_EMAIL", "rangarajusaivivek@gmail.com")


def build_digest_text(new_jobs: list[dict], emails_generated: int, run_stats: dict) -> str:
    """Build the daily digest as plain text."""
    today = datetime.now().strftime("%A, %B %d, %Y")
    apply_jobs = [j for j in new_jobs if j.get("verdict") == "APPLY"]
    investigate_jobs = [j for j in new_jobs if j.get("verdict") == "INVESTIGATE"]
    follow_ups = get_follow_ups_due()
    stats = get_stats()

    lines = [
        f"[SECURITY] DAILY JOB SCAN — {today}",
        "=" * 50,
        f"",
        f"[STATS] TODAY'S RESULTS:",
        f"  • New jobs found:     {len(new_jobs)}",
        f"  • APPLY (score ≥70):  {len(apply_jobs)}",
        f"  • Investigate:        {len(investigate_jobs)}",
        f"  • Cold emails ready:  {emails_generated}",
        f"  • Follow-ups due:     {len(follow_ups)}",
        f"",
        f"📈 TOTAL CAMPAIGN STATS:",
        f"  • Total tracked:      {stats.get('total_found', 0)}",
        f"  • Applied to:         {stats.get('total_applied', 0)}",
        f"  • Cold emails sent:   {stats.get('cold_emails', 0)}",
        f"  • Interviews:         {stats.get('interviews', 0)}",
        f"  • Avg match score:    {stats.get('avg_score', 0)}",
        f"",
    ]

    if apply_jobs:
        lines.append("[HIGH] APPLY NOW — Top Matches:")
        lines.append("-" * 40)
        for job in apply_jobs[:10]:
            lines.append(f"  [{job.get('score', 0)}/100] {job.get('title')} @ {job.get('company')}")
            lines.append(f"    [LOC] {job.get('location', 'N/A')} | [SALARY] {job.get('salary', 'Not listed')}")
            lines.append(f"    [WEB] {job.get('source')} | 🔗 {job.get('apply_url', job.get('url', ''))[:80]}")
            if job.get("hm_email"):
                lines.append(f"    [EMAIL] HM: {job.get('hm_name', 'Unknown')} <{job.get('hm_email')}>")
            lines.append(f"    [OK] {' | '.join(str(r) for r in job.get('reasons', [])[:2])}")
            lines.append("")

    if follow_ups:
        lines.append("[TIME] FOLLOW-UPS DUE TODAY:")
        lines.append("-" * 40)
        for f in follow_ups[:5]:
            lines.append(f"  • {f.get('company')} — {f.get('title')}")
            lines.append(f"    Status: {f.get('status')} | Applied: {f.get('applied_date', 'N/A')}")
            if f.get("hm_email"):
                lines.append(f"    Follow up: {f.get('hm_email')}")
            lines.append("")

    if investigate_jobs:
        lines.append("[MED] WORTH INVESTIGATING:")
        lines.append("-" * 40)
        for job in investigate_jobs[:5]:
            lines.append(f"  [{job.get('score', 0)}/100] {job.get('title')} @ {job.get('company')}")
            lines.append(f"    {job.get('source')} | {job.get('apply_url', '')[:70]}")
        lines.append("")

    lines += [
        "-" * 50,
        f"Cold emails saved to: data/cold_emails/",
        f"Full tracker: data/jobs_tracker.xlsx",
        f"Sai Vivek Rangaraju | rangarajusaivivek.github.io",
    ]

    return "\n".join(lines)


def build_digest_html(new_jobs: list[dict], emails_generated: int) -> str:
    """Build HTML version of digest for email."""
    apply_jobs = [j for j in new_jobs if j.get("verdict") == "APPLY"]
    today = datetime.now().strftime("%A, %B %d, %Y")
    stats = get_stats()
    follow_ups = get_follow_ups_due()

    job_rows = ""
    for job in apply_jobs[:15]:
        opt = "[OK]" if job.get("opt_flag") else "[?]"
        h1b = "[OK]" if job.get("h1b_flag") else "[?]"
        hm = f"<br><small>[EMAIL] {job.get('hm_name', '')} &lt;{job.get('hm_email', '')}&gt;</small>" if job.get("hm_email") else ""
        job_rows += f"""
        <tr>
          <td style="font-weight:bold;color:#0A1628">{job.get('score',0)}/100</td>
          <td><strong>{job.get('title','')}</strong><br><small>{job.get('company','')}</small>{hm}</td>
          <td>{job.get('location','')}</td>
          <td>{job.get('salary','—')}</td>
          <td>{opt}</td><td>{h1b}</td>
          <td>{job.get('source','')}</td>
          <td><a href="{job.get('apply_url',job.get('url',''))}" style="color:#006064">Apply →</a></td>
        </tr>"""

    followup_rows = ""
    for f in follow_ups[:5]:
        followup_rows += f"""
        <tr>
          <td>{f.get('company','')}</td>
          <td>{f.get('title','')}</td>
          <td>{f.get('status','')}</td>
          <td>{f.get('applied_date','')}</td>
          <td>{f.get('hm_email','')}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  body {{ font-family: Arial, sans-serif; max-width: 900px; margin: auto; background: #f5f7fa; padding: 20px; }}
  .banner {{ background: #0A1628; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
  .stats {{ display: grid; grid-template-columns: repeat(5,1fr); gap: 10px; margin: 20px 0; }}
  .stat {{ background: white; border-radius: 6px; padding: 12px; text-align: center; border: 1px solid #CFD8DC; }}
  .stat .num {{ font-size: 24px; font-weight: bold; color: #0A1628; }}
  .stat .lbl {{ font-size: 11px; color: #546E7A; }}
  table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; margin: 15px 0; }}
  th {{ background: #0A1628; color: white; padding: 8px; font-size: 11px; }}
  td {{ padding: 8px; border-bottom: 1px solid #f0f0f0; font-size: 12px; vertical-align: top; }}
  tr:nth-child(even) td {{ background: #f9f9f9; }}
  h2 {{ color: #0A1628; margin-top: 25px; }}
</style>
</head><body>
<div class="banner">
  <h2 style="margin:0;color:white">[SECURITY] Daily Cybersecurity Job Scan</h2>
  <p style="margin:5px 0;color:#00C8E8">{today} — Sai Vivek Rangaraju | F-1 OPT</p>
</div>
<div class="stats">
  <div class="stat"><div class="num">{len(apply_jobs)}</div><div class="lbl">Apply Now</div></div>
  <div class="stat"><div class="num">{emails_generated}</div><div class="lbl">Emails Ready</div></div>
  <div class="stat"><div class="num">{len(follow_ups)}</div><div class="lbl">Follow-ups Due</div></div>
  <div class="stat"><div class="num">{stats.get('total_applied',0)}</div><div class="lbl">Total Applied</div></div>
  <div class="stat"><div class="num">{stats.get('interviews',0)}</div><div class="lbl">Interviews</div></div>
</div>
<h2>[HIGH] APPLY NOW — Top Matches</h2>
<table><thead><tr>
  <th>Score</th><th>Role / Company</th><th>Location</th><th>Salary</th>
  <th>OPT</th><th>H1B</th><th>Source</th><th>Apply</th>
</tr></thead><tbody>{job_rows}</tbody></table>
{"<h2>[TIME] Follow-ups Due Today</h2><table><thead><tr><th>Company</th><th>Role</th><th>Status</th><th>Applied</th><th>HM Email</th></tr></thead><tbody>" + followup_rows + "</tbody></table>" if follow_ups else ""}
<hr><p style="font-size:11px;color:#999">
  Sai Vivek Rangaraju · MS Cybersecurity WSU 2026 · CEH · rangarajusaivivek@gmail.com<br>
  <a href="https://rangarajusaivivek.github.io">Portfolio</a> · 
  <a href="https://linkedin.com/in/rangarajusaivivek">LinkedIn</a> · 
  <a href="https://github.com/rangarajusaivivek">GitHub</a>
</p>
</body></html>"""


def send_email_digest(subject: str, html: str, text: str):
    """Send via SendGrid."""
    if not SENDGRID_KEY:
        log.warning("No SendGrid key — digest not emailed")
        return False
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail, Content
        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_KEY)
        message = Mail(
            from_email="noreply@jobscanner.ai",
            to_emails=DIGEST_EMAIL,
            subject=subject,
            html_content=html,
            plain_text_content=text,
        )
        response = sg.send(message)
        log.info(f"Email digest sent: {response.status_code}")
        return True
    except Exception as e:
        log.error(f"Email send failed: {e}")
        return False


def send_telegram_digest(text: str):
    """Send digest via Telegram bot."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        log.warning("No Telegram config — digest not sent via Telegram")
        return False
    try:
        import httpx
        # Split long messages (Telegram limit 4096 chars)
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            resp = httpx.post(url, json={
                "chat_id": TELEGRAM_CHAT,
                "text": chunk,
                "parse_mode": "HTML",
            })
            log.info(f"Telegram sent: {resp.status_code}")
        return True
    except Exception as e:
        log.error(f"Telegram send failed: {e}")
        return False


def send_digest(new_jobs: list[dict], emails_generated: int, run_stats: dict):
    """Send digest through all configured channels."""
    apply_count = len([j for j in new_jobs if j.get("verdict") == "APPLY"])
    today = datetime.now().strftime("%b %d")

    subject = f"[Job Scanner {today}] {apply_count} jobs to APPLY + {len(get_follow_ups_due())} follow-ups due"

    text = build_digest_text(new_jobs, emails_generated, run_stats)
    html = build_digest_html(new_jobs, emails_generated)

    # Save locally always
    os.makedirs("data", exist_ok=True)
    with open(f"data/digest_{datetime.now().strftime('%Y%m%d')}.txt", "w", encoding="utf-8") as f:
        f.write(text)
    with open(f"data/digest_{datetime.now().strftime('%Y%m%d')}.html", "w", encoding="utf-8") as f:
        f.write(html)

    # Send to channels
    send_email_digest(subject, html, text)
    send_telegram_digest(text[:3800])

    log.info(f"Digest sent: {apply_count} APPLY jobs, {emails_generated} emails, {len(get_follow_ups_due())} follow-ups")
    print("\n" + text)
