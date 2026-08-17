#!/usr/bin/env python3
"""
Cybersecurity Job Scanner -- Sai Vivek Rangaraju
Daily schedule: 8am + 2pm + 6pm scans, 9pm EOD report
Usage:
  py main.py --schedule   # Full daily loop (recommended)
  py main.py --no-ai      # Single scan, no API cost
  py main.py --stats      # Show tracker stats
  py main.py --eod        # Generate EOD report now
  py main.py --setup-sheets  # Google Sheets setup guide
"""
import sys, io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import os, time, argparse, schedule
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger import log
from utils.config_loader import load_config
from scrapers.job_scrapers import run_all_scrapers
from filters.job_scorer import score_job
from outreach.email_generator import generate_cold_email, save_emails
from outreach.hiring_manager_finder import find_hiring_manager
from tracker.application_tracker import add_jobs_to_tracker, get_stats, export_to_excel, get_follow_ups_due, load_tracker
from digest.daily_digest import send_digest
from digest.batch_applier import generate_batch_html
from digest.eod_summary import generate_eod_report

console = Console()
SCAN_COUNTS = {"morning": 0, "afternoon": 0, "evening": 0}


def banner(label=""):
    console.print(Panel.fit(
        f"[bold cyan]Cybersecurity Job Scanner{' -- ' + label if label else ''}[/bold cyan]\n"
        f"[dim]Sai Vivek Rangaraju | MS Cybersecurity WSU 2026 | F-1 OPT[/dim]\n"
        f"[dim]{datetime.now().strftime('%A, %B %d, %Y -- %I:%M %p')}[/dim]",
        border_style="cyan"
    ))


def show_stats():
    stats = get_stats()
    t = Table(title="Campaign Stats", border_style="cyan")
    t.add_column("Metric", style="bold")
    t.add_column("Value", style="cyan")
    for k, v in stats.items():
        if not isinstance(v, dict):
            t.add_row(k.replace("_"," ").title(), str(v))
    console.print(t)
    fups = get_follow_ups_due()
    if fups:
        console.print(f"\n[bold red]{len(fups)} follow-up(s) due today![/bold red]")
        for f in fups[:5]:
            console.print(f"  - {f.get('company')} -- {f.get('title')}")


def run_scan(config, args, scan_label="Manual"):
    run_stats = {"start_time": datetime.now().isoformat(), "scan": scan_label}
    banner(scan_label)

    # STEP 1: SCRAPE
    console.print(f"\n[bold cyan]STEP 1: Scraping platforms...[/bold cyan]")
    raw_jobs = run_all_scrapers(config)
    run_stats["raw_jobs"] = len(raw_jobs)
    console.print(f"  -> {len(raw_jobs)} raw jobs collected")

    if not raw_jobs:
        console.print("[yellow]No new jobs found.[/yellow]")
        return run_stats

    # STEP 2: SCORE
    console.print("\n[bold cyan]STEP 2: Scoring jobs...[/bold cyan]")
    use_ai = not getattr(args, "no_ai", False)
    scored_jobs = []
    for i, job in enumerate(raw_jobs):
        scored = score_job(job, use_ai=use_ai)
        if scored["score"] > 0:
            scored_jobs.append(scored)
        if (i+1) % 10 == 0:
            console.print(f"  Scored {i+1}/{len(raw_jobs)}...")

    apply_jobs  = [j for j in scored_jobs if j.get("verdict") == "APPLY"]
    investigate = [j for j in scored_jobs if j.get("verdict") == "INVESTIGATE"]
    skipped     = [j for j in scored_jobs if j.get("verdict") == "SKIP"]
    run_stats.update({"apply": len(apply_jobs), "investigate": len(investigate)})
    console.print(f"  -> APPLY: {len(apply_jobs)} | INVESTIGATE: {len(investigate)} | SKIP: {len(skipped)}")

    if apply_jobs:
        t = Table(title=f"Top Matches -- {scan_label}", border_style="red")
        t.add_column("Score", width=6)
        t.add_column("Title")
        t.add_column("Company")
        t.add_column("Source", width=12)
        for job in sorted(apply_jobs, key=lambda x: x.get("score",0), reverse=True)[:8]:
            t.add_row(str(job.get("score",0)), job.get("title","")[:45],
                      job.get("company","")[:25], job.get("source","")[:12])
        console.print(t)

    # STEP 3: HIRING MANAGERS
    no_email = getattr(args, "no_email", False)
    emails, emails_generated = [], 0

    if not no_email and use_ai:
        console.print("\n[bold cyan]STEP 3: Finding hiring managers...[/bold cyan]")
        for job in sorted(apply_jobs, key=lambda x: x.get("score",0), reverse=True)[:10]:
            try:
                hm = find_hiring_manager(job)
                job.update({"hm_name": hm.get("name",""), "hm_email": hm.get("email",""), "hm_linkedin": hm.get("linkedin","")})
                if hm.get("email"):
                    console.print(f"  [OK] {hm['name']} <{hm['email']}> at {job['company']}")
                else:
                    console.print(f"  [SEARCH] {job['company']}: {hm.get('search_query','')[:60]}")
                time.sleep(0.5)
            except Exception as e:
                log.warning(f"HM finder failed: {e}")

        # STEP 4: EMAILS
        console.print("\n[bold cyan]STEP 4: Generating cold emails...[/bold cyan]")
        for job in sorted(apply_jobs, key=lambda x: x.get("score",0), reverse=True)[:8]:
            try:
                email = generate_cold_email(job, job.get("hm_name"))
                emails.append(email)
                console.print(f"  [EMAIL] {job.get('company')} -- {email.get('subject','')[:50]}")
                time.sleep(0.3)
            except Exception as e:
                log.warning(f"Email gen failed: {e}")
        if emails and not getattr(args, "dry_run", False):
            save_emails(emails)
            emails_generated = len(emails)

    run_stats["emails_generated"] = emails_generated

    # STEP 5: SAVE + SYNC
    dry_run = getattr(args, "dry_run", False)
    if not dry_run:
        console.print("\n[bold cyan]STEP 5: Saving to tracker...[/bold cyan]")
        new_count, dup_count = add_jobs_to_tracker(apply_jobs + investigate)
        console.print(f"  -> {new_count} new, {dup_count} duplicates skipped")
        export_to_excel()
        console.print("  -> Excel: data/jobs_tracker.xlsx")

        # Google Sheets sync
        from utils.sheets_sync import is_configured, sync_tracker_to_sheets, sync_daily_summary_to_sheets
        if is_configured():
            console.print("\n[bold cyan]Syncing to Google Sheets...[/bold cyan]")
            df = load_tracker()
            if sync_tracker_to_sheets(df):
                console.print("  -> Synced! Check Google Sheets app on your phone.")
            sync_daily_summary_to_sheets(run_stats, scan_label)
        else:
            console.print("  [dim](Google Sheets not set up -- run: py main.py --setup-sheets)[/dim]")

        run_stats["new_saved"] = new_count

    # STEP 6: BATCH HTML
    if not dry_run:
        console.print("\n[bold cyan]STEP 6: Generating apply_today.html...[/bold cyan]")
        path = generate_batch_html(apply_jobs + investigate, emails)
        abs_path = os.path.abspath(path)
        console.print(f"  -> Open in browser: file:///{abs_path.replace(os.sep, '/')}")

    # STEP 7: DIGEST
    console.print("\n[bold cyan]STEP 7: Sending digest...[/bold cyan]")
    if not dry_run:
        send_digest(sorted(apply_jobs + investigate, key=lambda x: x.get("score",0), reverse=True),
                    emails_generated, run_stats)

    # Update scan counter
    sk = scan_label.lower().split()[0]
    if sk in SCAN_COUNTS:
        SCAN_COUNTS[sk] = len(raw_jobs)

    elapsed = (datetime.now() - datetime.fromisoformat(run_stats["start_time"])).seconds
    console.print(Panel(
        f"[bold green][OK] {scan_label.upper()} COMPLETE[/bold green]\n"
        f"[cyan]{len(raw_jobs)}[/cyan] scraped -> [red]{len(apply_jobs)}[/red] APPLY -> "
        f"[yellow]{emails_generated}[/yellow] emails -> [dim]{elapsed}s[/dim]",
        border_style="green"
    ))

    fups = get_follow_ups_due()
    if fups:
        console.print(f"\n[bold yellow][TIME] {len(fups)} follow-up(s) due today[/bold yellow]")
        for f in fups[:3]:
            console.print(f"  - {f.get('company')} -- {f.get('title')}")

    # Print LinkedIn connection search guide once per morning scan
    if "morning" in scan_label.lower() or "manual" in scan_label.lower():
        from scrapers.job_scrapers import print_linkedin_search_guide
        print_linkedin_search_guide()

    run_stats.update({"total_applied": get_stats().get("total_applied",0),
                      "interviews": get_stats().get("interviews",0)})
    return run_stats


def run_schedule(config, args):
    console.print(Panel(
        "[bold cyan]FULL DAILY SCHEDULE ACTIVE[/bold cyan]\n\n"
        "[green]08:00 AM[/green] -- Morning Scan\n"
        "[green]02:00 PM[/green] -- Afternoon Scan\n"
        "[green]06:00 PM[/green] -- Evening Scan\n"
        "[green]09:00 PM[/green] -- End-of-Day Report -> Telegram + HTML\n\n"
        "[dim]Leave this window open. Press Ctrl+C to stop.[/dim]\n"
        "[dim]Check Google Sheets app on your phone for live results.[/dim]",
        border_style="cyan"
    ))

    schedule.every().day.at("08:00").do(lambda: run_scan(config, args, "Morning Scan"))
    schedule.every().day.at("14:00").do(lambda: run_scan(config, args, "Afternoon Scan"))
    schedule.every().day.at("18:00").do(lambda: run_scan(config, args, "Evening Scan"))
    schedule.every().day.at("21:00").do(lambda: generate_eod_report(SCAN_COUNTS))

    now = datetime.now()
    console.print(f"\n[dim]Current time: {now.strftime('%I:%M %p')}[/dim]")

    # Run morning scan immediately if starting fresh
    if now.hour < 8 or (now.hour == 8 and now.minute < 5):
        console.print("[dim]Waiting for 8:00 AM morning scan...[/dim]")
    else:
        console.print("[cyan]Running immediate scan since schedule already started today...[/cyan]")
        run_scan(config, args, "Immediate Scan")

    console.print("[dim]Scheduler running. Next scan in the queue:[/dim]")
    for job in schedule.jobs[:4]:
        console.print(f"  [dim]{job.next_run.strftime('%I:%M %p')} -- {job.job_func.__name__ if hasattr(job.job_func, '__name__') else 'scan'}[/dim]")

    while True:
        schedule.run_pending()
        time.sleep(30)


def main():
    parser = argparse.ArgumentParser(description="Cybersecurity Job Scanner")
    parser.add_argument("--no-ai",       action="store_true", help="Skip AI scoring (no API cost)")
    parser.add_argument("--no-email",    action="store_true", help="Skip email generation")
    parser.add_argument("--dry-run",     action="store_true", help="Scrape + score only, no saving")
    parser.add_argument("--stats",       action="store_true", help="Show campaign stats")
    parser.add_argument("--eod",         action="store_true", help="Generate end-of-day report now")
    parser.add_argument("--schedule",    action="store_true", help="Run full daily schedule (recommended)")
    parser.add_argument("--once",        action="store_true", help="Run one scan and exit")
    parser.add_argument("--setup-sheets",action="store_true", help="Google Sheets setup guide")
    args = parser.parse_args()

    if args.stats:
        banner()
        show_stats()
        return

    if args.eod:
        banner("End-of-Day Report")
        generate_eod_report(SCAN_COUNTS)
        return

    if args.setup_sheets:
        from utils.sheets_sync import setup_google_sheets_instructions
        setup_google_sheets_instructions()
        return

    config = load_config()

    if args.schedule:
        run_schedule(config, args)
    else:
        run_scan(config, args, "Manual Scan")


if __name__ == "__main__":
    main()
