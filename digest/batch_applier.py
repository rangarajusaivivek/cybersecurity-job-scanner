"""
digest/batch_applier.py
========================
Generates a daily "Application Batch" HTML file.
Opens in your browser — one page with all today's top jobs
pre-loaded with apply links, cold emails ready to copy,
and Simplify.jobs auto-fill compatible links.

Open it every morning. Click Apply. Simplify fills the form. You submit.
20-30 minutes for 10-15 applications.
"""

import os
from datetime import datetime
from tracker.application_tracker import get_stats, get_follow_ups_due
from utils.logger import log


def generate_batch_html(jobs: list[dict], emails: list[dict] = None,
                        output_path: str = "data/apply_today.html") -> str:
    """
    Generate the daily application batch HTML.
    - Top scored APPLY jobs with one-click apply links
    - Cold email drafts pre-loaded (copy-paste to Gmail)
    - Follow-ups due today
    - Progress tracker
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    today     = datetime.now().strftime("%A, %B %d, %Y")
    apply_jobs = sorted(
        [j for j in jobs if j.get("verdict") == "APPLY"],
        key=lambda x: x.get("score", 0), reverse=True
    )[:15]
    stats      = get_stats()
    follow_ups = get_follow_ups_due()
    email_map  = {e.get("company", "").lower(): e for e in (emails or [])}

    # -- Job cards HTML ---------------------------------------------------------
    job_cards = ""
    for i, job in enumerate(apply_jobs):
        score    = job.get("score", 0)
        opt_tag  = '<span class="tag green">[OK] OPT Signal</span>' if job.get("opt_flag") else '<span class="tag warn">[?] Check OPT</span>'
        h1b_tag  = '<span class="tag green">[OK] H1B History</span>' if job.get("h1b_flag") else ''
        reasons  = job.get("reasons", [])
        reasons_html = " | ".join(str(r) for r in reasons[:3]) if isinstance(reasons, list) else str(reasons)[:120]
        email    = email_map.get(job.get("company", "").lower(), {})
        hm_email = job.get("hm_email", "")
        hm_name  = job.get("hm_name", "Hiring Manager")

        email_section = ""
        if email.get("body"):
            subj = email.get("subject", "").replace('"', '&quot;')
            body = email.get("body", "").replace("\n", "&#10;").replace('"', '&quot;')
            email_section = f"""
            <div class="email-block">
              <div class="email-header">
                [EMAIL] Cold Email — ready to send
                {f'<span class="hm-badge">To: {hm_name} &lt;{hm_email}&gt;</span>' if hm_email else '<span class="hm-badge warn">[WARN] Find HM email via hunter.io</span>'}
              </div>
              <div class="email-subject"><b>Subject:</b> {email.get('subject','')}</div>
              <textarea class="email-body" onclick="this.select()" readonly>{email.get('body','')}</textarea>
              <div style="display:flex;gap:8px;margin-top:6px">
                {'<a class="btn-email" href="mailto:' + hm_email + '?subject=' + subj + '&body=' + body + '">📨 Open in Gmail</a>' if hm_email else ''}
                <button class="btn-copy" onclick="navigator.clipboard.writeText(this.closest(\'.email-block\').querySelector(\'.email-body\').value);this.textContent=\'[OK] Copied!\';setTimeout(()=>this.textContent=\'[LIST] Copy Email\',2000)">[LIST] Copy Email</button>
                <button class="btn-copy" onclick="navigator.clipboard.writeText(this.closest(\'.email-block\').querySelector(\'.email-subject\').textContent.replace(\'Subject: \',\'\'));this.textContent=\'[OK] Copied!\';setTimeout(()=>this.textContent=\'[LIST] Copy Subject\',2000)">[LIST] Copy Subject</button>
              </div>
            </div>"""

        hm_lookup = ""
        if not hm_email and job.get("hm_search"):
            hm_lookup = f"""
            <div class="hm-lookup">
              [SEARCH] <b>Find HM:</b>
              <a href="https://www.linkedin.com/search/results/people/?keywords={job.get('company','').replace(' ','%20')}%20cybersecurity%20manager" target="_blank">LinkedIn Search</a> ·
              <a href="https://hunter.io/search/{job.get('company','').lower().replace(' ','-')}.com" target="_blank">Hunter.io</a>
            </div>"""

        score_color = "#dc3545" if score >= 80 else "#fd7e14" if score >= 65 else "#6c757d"

        job_cards += f"""
        <div class="job-card" id="job-{i}">
          <div class="job-header">
            <div class="job-left">
              <div class="job-score" style="background:{score_color}">{score}</div>
              <div>
                <div class="job-title">{job.get('title','')}</div>
                <div class="job-company">{job.get('company','')} · {job.get('location','')} · {job.get('source','')}</div>
                <div class="job-salary">{job.get('salary','Salary not listed')}</div>
              </div>
            </div>
            <div class="job-actions">
              <a class="btn-apply" href="{job.get('apply_url', job.get('url',''))}" target="_blank">[APPLY] Apply Now</a>
              <button class="btn-done" onclick="markDone(this,{i})">[OK] Mark Applied</button>
            </div>
          </div>
          <div class="job-tags">
            {opt_tag} {h1b_tag}
            <span class="tag blue">{job.get('source','')}</span>
            {'<span class="tag green">[LOC] Ohio/Local</span>' if any(x in str(job.get('location','')).lower() for x in ['ohio','dayton','columbus','cleveland','fairborn']) else ''}
          </div>
          <div class="job-reasons">{reasons_html}</div>
          {hm_lookup}
          {email_section}
        </div>"""

    # -- Follow-ups HTML --------------------------------------------------------
    followup_cards = ""
    for f in follow_ups[:5]:
        followup_cards += f"""
        <div class="followup-card">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <div>
              <div style="font-weight:600;font-size:14px">{f.get('company','')} — {f.get('title','')}</div>
              <div style="font-size:12px;color:var(--color-text-secondary)">Applied: {f.get('applied_date','')} · Status: {f.get('status','')}</div>
              {'<div style="font-size:12px;color:var(--color-text-info)">[EMAIL] ' + f.get('hm_email','') + '</div>' if f.get('hm_email') else ''}
            </div>
            {'<a class="btn-apply" style="background:#fd7e14" href="mailto:' + f.get('hm_email','') + '?subject=Following%20Up%20on%20My%20Application%20—%20' + f.get('title','').replace(' ','%20') + '" target="_blank">[EMAIL] Send Follow-up</a>' if f.get('hm_email') else '<span style="color:var(--color-text-secondary);font-size:12px">Find email to follow up</span>'}
          </div>
        </div>"""

    if not followup_cards:
        followup_cards = '<p style="color:var(--color-text-secondary);padding:1rem">No follow-ups due today. Keep applying!</p>'

    # -- Full HTML --------------------------------------------------------------
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Apply Today — {today}</title>
<style>
  :root {{
    --bg: #050a0f; --bg-card: #0b1420; --border: #1a2e45; --border-hi: #1e4d7a;
    --text: #e2eaf4; --muted: #5a7a9a; --accent: #00d4ff; --green: #00e676;
    --orange: #ff9800; --red: #ff5252; --mono: 'JetBrains Mono',monospace;
    --color-text-primary: #e2eaf4; --color-text-secondary: #5a7a9a;
    --color-text-info: #00d4ff; --color-background-success: rgba(0,230,118,.12);
    --color-text-success: #00e676; --color-background-warning: rgba(255,152,0,.12);
    --color-text-warning: #ff9800; --color-border-tertiary: #1a2e45;
  }}
  * {{ box-sizing:border-box; margin:0; padding:0 }}
  body {{ font-family: -apple-system,Arial,sans-serif; background:var(--bg); color:var(--text); padding:0 }}
  a {{ color:var(--accent); text-decoration:none }}

  /* NAV */
  .topbar {{ background:#0b1420; border-bottom:1px solid var(--border); padding:12px 24px; display:flex; justify-content:space-between; align-items:center; position:sticky; top:0; z-index:100 }}
  .topbar-title {{ font-family:var(--mono); font-size:13px; color:var(--accent) }}
  .topbar-stats {{ display:flex; gap:16px; font-size:12px; color:var(--muted) }}
  .topbar-stats span {{ color:var(--text) }}

  /* MAIN LAYOUT */
  .container {{ max-width:960px; margin:0 auto; padding:20px 16px }}
  .section-head {{ font-size:18px; font-weight:700; margin:28px 0 12px; color:var(--text) }}
  .section-sub {{ font-size:12px; color:var(--muted); margin-top:-8px; margin-bottom:12px }}

  /* PROGRESS BAR */
  .progress-wrap {{ background:var(--bg-card); border:1px solid var(--border); border-radius:8px; padding:16px; margin-bottom:20px }}
  .progress-label {{ font-size:13px; color:var(--muted); margin-bottom:8px; display:flex; justify-content:space-between }}
  .progress-bar {{ height:8px; background:#1a2e45; border-radius:4px; overflow:hidden }}
  .progress-fill {{ height:100%; background:linear-gradient(90deg,var(--accent),#006aff); border-radius:4px; transition:width .4s }}

  /* JOB CARDS */
  .job-card {{ background:var(--bg-card); border:1px solid var(--border); border-radius:10px; padding:18px; margin-bottom:12px; transition:border-color .2s }}
  .job-card:hover {{ border-color:var(--border-hi) }}
  .job-card.done {{ opacity:.5; border-color:var(--green); }}
  .job-header {{ display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:10px }}
  .job-left {{ display:flex; gap:14px; align-items:flex-start; flex:1 }}
  .job-score {{ width:44px; height:44px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:15px; font-weight:700; color:white; flex-shrink:0 }}
  .job-title {{ font-size:15px; font-weight:600; margin-bottom:3px }}
  .job-company {{ font-size:12px; color:var(--muted); margin-bottom:2px }}
  .job-salary {{ font-size:12px; color:var(--accent) }}
  .job-actions {{ display:flex; flex-direction:column; gap:6px; flex-shrink:0 }}
  .job-tags {{ display:flex; flex-wrap:wrap; gap:4px; margin:8px 0 }}
  .job-reasons {{ font-size:11px; color:var(--muted); line-height:1.5; margin-top:4px }}

  /* TAGS */
  .tag {{ padding:2px 8px; border-radius:12px; font-size:11px; font-weight:500 }}
  .tag.green {{ background:rgba(0,230,118,.15); color:var(--green) }}
  .tag.warn {{ background:rgba(255,152,0,.15); color:var(--orange) }}
  .tag.blue {{ background:rgba(0,212,255,.12); color:var(--accent) }}

  /* BUTTONS */
  .btn-apply {{ background:var(--accent); color:#050a0f; font-weight:700; font-size:13px; padding:8px 16px; border-radius:6px; white-space:nowrap; display:inline-block; text-align:center; border:none; cursor:pointer }}
  .btn-apply:hover {{ opacity:.85 }}
  .btn-done {{ background:transparent; border:1px solid var(--border); color:var(--muted); font-size:12px; padding:8px 14px; border-radius:6px; cursor:pointer; white-space:nowrap }}
  .btn-done:hover {{ border-color:var(--green); color:var(--green) }}
  .btn-copy {{ background:transparent; border:1px solid var(--border-hi); color:var(--accent); font-size:11px; padding:5px 12px; border-radius:5px; cursor:pointer }}
  .btn-copy:hover {{ background:rgba(0,212,255,.1) }}
  .btn-email {{ background:#1a3a2a; color:var(--green); font-size:11px; padding:5px 12px; border-radius:5px; border:1px solid #2d5a40 }}

  /* EMAIL BLOCK */
  .email-block {{ background:#060e18; border:1px solid var(--border-hi); border-radius:8px; padding:14px; margin-top:12px }}
  .email-header {{ font-size:12px; font-weight:600; color:var(--accent); margin-bottom:8px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px }}
  .email-subject {{ font-size:12px; color:var(--muted); padding:6px 0; border-bottom:1px solid var(--border) }}
  .email-body {{ width:100%; min-height:120px; background:#050a0f; color:var(--text); border:1px solid var(--border); border-radius:6px; padding:10px; font-size:12px; line-height:1.7; resize:vertical; margin-top:8px; font-family:inherit }}
  .hm-badge {{ font-size:11px; padding:3px 8px; border-radius:12px; background:rgba(0,230,118,.12); color:var(--green) }}
  .hm-badge.warn {{ background:rgba(255,152,0,.12); color:var(--orange) }}

  /* HM LOOKUP */
  .hm-lookup {{ font-size:12px; color:var(--muted); margin-top:8px; padding:8px; background:#060e18; border-radius:6px; border-left:3px solid var(--border-hi) }}
  .hm-lookup a {{ color:var(--accent); margin:0 4px }}

  /* FOLLOWUP */
  .followup-card {{ background:var(--bg-card); border:1.5px solid #fd7e14; border-radius:8px; padding:14px; margin-bottom:10px }}

  /* SIMPLIFY TIP */
  .simplify-tip {{ background:#0a1e0a; border:1px solid #2d5a40; border-radius:8px; padding:14px; margin-bottom:20px; font-size:13px }}

  /* COUNTERS */
  .counter {{ font-size:12px; font-family:var(--mono); color:var(--muted) }}
  #applied-count {{ color:var(--green); font-weight:700 }}
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-title">&gt; apply_today.sh <span style="color:var(--green)">● running</span></div>
  <div class="topbar-stats">
    <span>Applied today: <span id="applied-count">0</span>/{len(apply_jobs)}</span>
    <span>Total campaign: <span>{stats.get('total_applied',0)}</span></span>
    <span>Interviews: <span>{stats.get('interviews',0)}</span></span>
    <span style="color:var(--muted)">{today}</span>
  </div>
</div>

<div class="container">

  <!-- PROGRESS -->
  <div class="progress-wrap" style="margin-top:16px">
    <div class="progress-label">
      <span>Today's application progress</span>
      <span class="counter"><span id="progress-text">0/{len(apply_jobs)}</span> jobs applied</span>
    </div>
    <div class="progress-bar"><div class="progress-fill" id="progress-fill" style="width:0%"></div></div>
  </div>

  <!-- SIMPLIFY TIP -->
  <div class="simplify-tip">
    💡 <b>Speed tip:</b> Install <a href="https://simplify.jobs/download" target="_blank">Simplify.jobs extension</a> in Chrome. When you click "Apply Now" below, it auto-fills the application form for you. You just review and click Submit. Saves ~5 min per application.
    <span style="color:var(--muted);font-size:11px;margin-left:8px">· Works on Greenhouse, Lever, Workday, Indeed, and most company career pages</span>
  </div>

  <!-- FOLLOW-UPS DUE -->
  {'<div class="section-head" style="color:#fd7e14">[TIME] Follow-ups Due Today (' + str(len(follow_ups)) + ')</div><div class="section-sub">Send these before applying to new jobs — they were hot leads 5 days ago</div>' + followup_cards if follow_ups else ''}

  <!-- APPLY JOBS -->
  <div class="section-head">[HIGH] Apply Now — {len(apply_jobs)} Top Matches Today</div>
  <div class="section-sub">Sorted by match score. Apply within 72 hours of posting for best callback rate.</div>

  {job_cards if job_cards else '<p style="color:var(--muted);padding:2rem 0">No new APPLY-rated jobs today. Check the INVESTIGATE list or try a manual search.</p>'}

  <div style="margin-top:30px;padding:16px;background:var(--bg-card);border-radius:8px;border:1px solid var(--border);font-size:12px;color:var(--muted);text-align:center">
    Sai Vivek Rangaraju · MS Cybersecurity WSU 2026 · CEH · F-1 OPT ·
    <a href="https://rangarajusaivivek.github.io">Portfolio</a> ·
    <a href="https://linkedin.com/in/rangarajusaivivek">LinkedIn</a> ·
    <a href="https://github.com/rangarajusaivivek">GitHub</a>
  </div>
</div>

<script>
  let appliedCount = 0;
  const total = {len(apply_jobs)};

  function markDone(btn, idx) {{
    const card = document.getElementById('job-' + idx);
    if (card.classList.contains('done')) {{
      card.classList.remove('done');
      btn.textContent = '[OK] Mark Applied';
      appliedCount = Math.max(0, appliedCount - 1);
    }} else {{
      card.classList.add('done');
      btn.textContent = '✔ Applied!';
      btn.style.color = 'var(--green)';
      btn.style.borderColor = 'var(--green)';
      appliedCount++;
    }}
    document.getElementById('applied-count').textContent = appliedCount;
    document.getElementById('progress-text').textContent = appliedCount + '/' + total;
    document.getElementById('progress-fill').style.width = (appliedCount/total*100) + '%';
  }}

  // Auto-open first apply link hint
  document.querySelectorAll('.btn-apply').forEach((btn, i) => {{
    btn.addEventListener('click', () => {{
      setTimeout(() => {{
        const doneBtn = btn.closest('.job-card').querySelector('.btn-done');
        if (doneBtn && !btn.closest('.job-card').classList.contains('done')) {{
          doneBtn.style.animation = 'pulse 0.5s';
        }}
      }}, 2000);
    }});
  }});
</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    log.info(f"Batch HTML saved: {output_path} ({len(apply_jobs)} jobs)")
    return output_path
