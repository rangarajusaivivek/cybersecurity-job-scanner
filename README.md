# 🔐 Cybersecurity Job Scanner — Sai Vivek Rangaraju

Automated daily job market scanner built for F-1 OPT cybersecurity job search.

## What This Does

Runs every morning and:
1. **Scrapes** new cybersecurity jobs posted in the last 24 hours across 15+ platforms
2. **Filters** for OPT-friendly + no clearance required + entry level
3. **Scores** each job against your background (thesis, VAPT, CEH, certs)
4. **Finds** hiring manager contacts for top matches
5. **Generates** personalized cold emails using Claude AI
6. **Tracks** all applications in a Google Sheet / CSV
7. **Sends** you a morning digest via email/Telegram

## Setup (5 minutes)

```bash
git clone <this-repo>
cd job_scanner
pip install -r requirements.txt
cp config/config.example.yaml config/config.yaml
# Edit config.yaml with your details
python main.py
```

## Run Daily (automated)

```bash
# Add to crontab — runs at 8:00 AM daily
crontab -e
# Add: 0 8 * * * cd /path/to/job_scanner && python main.py
```

## Author
Sai Vivek Rangaraju | MS Cybersecurity, Wright State University 2026
- LinkedIn: linkedin.com/in/rangarajusaivivek
- GitHub: github.com/rangarajusaivivek
- Portfolio: rangarajusaivivek.github.io
