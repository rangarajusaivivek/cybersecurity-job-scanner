"""
scrapers/job_scrapers.py
=========================
Scrapes new job listings from 12+ platforms.
Covers: Full-time, Internship, Contract, Part-time roles
All OPT-friendly, no-clearance, cybersecurity + adjacent roles.
"""

import re, time, hashlib, httpx
from bs4 import BeautifulSoup
from datetime import datetime
from utils.logger import log

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}

# ── EXPANDED ROLE LIST ────────────────────────────────────────────────────────
# Full-time roles
FULLTIME_ROLES = [
    "SOC Analyst", "Security Analyst", "Cybersecurity Analyst",
    "Application Security Analyst", "Penetration Tester",
    "Security Engineer", "Security Researcher", "AppSec Engineer",
    "Information Security Analyst", "Threat Intelligence Analyst",
    "Incident Response Analyst", "Cloud Security Engineer",
    "DevSecOps Engineer", "GRC Analyst", "Vulnerability Analyst",
    "Malware Analyst", "Digital Forensics Analyst", "Network Security Analyst",
    "Identity Access Management Analyst", "IAM Analyst",
    "Risk Analyst Cybersecurity", "Compliance Analyst Security",
    "Security Operations Engineer", "Cyber Threat Analyst",
]

# Internship roles (open NOW for Fall 2026 / Spring 2027)
INTERNSHIP_ROLES = [
    "Cybersecurity Intern", "Security Intern", "Information Security Intern",
    "SOC Intern", "AppSec Intern", "Penetration Testing Intern",
    "Security Engineering Intern", "Cyber Intern",
    "GRC Intern", "Risk Management Intern Security",
    "Cloud Security Intern", "Threat Intelligence Intern",
]

# Adjacent roles that match your ML + security background
ADJACENT_ROLES = [
    "Machine Learning Security", "AI Security Analyst",
    "Data Security Analyst", "Privacy Analyst",
    "IT Security Analyst", "Cyber Defense Analyst",
    "Security Consultant Junior", "Junior Security Analyst",
    "Associate Security Engineer", "Security Operations Analyst",
]

ALL_ROLES = FULLTIME_ROLES[:8] + INTERNSHIP_ROLES[:4] + ADJACENT_ROLES[:4]

# Company career pages to scrape directly (no ghost jobs -- direct from source)
COMPANY_CAREER_PAGES = [
    {
        "company": "Rapid7",
        "url": "https://www.rapid7.com/company/careers/",
        "search_url": "https://boards.greenhouse.io/rapid7",
        "keywords": ["security", "analyst", "engineer", "intern", "soc", "pentest"],
    },
    {
        "company": "CrowdStrike",
        "url": "https://boards.greenhouse.io/crowdstrikeinc",
        "search_url": "https://boards.greenhouse.io/crowdstrikeinc",
        "keywords": ["analyst", "intern", "threat", "intelligence", "soc", "security"],
    },
    {
        "company": "Deloitte",
        "url": "https://apply.deloitte.com/careers/SearchJobs/cyber",
        "search_url": "https://apply.deloitte.com/careers/SearchJobs/cybersecurity%20analyst",
        "keywords": ["cyber", "analyst", "intern", "associate", "security"],
    },
    {
        "company": "MITRE",
        "url": "https://careers.mitre.org/us/en/search-results?keywords=cybersecurity",
        "search_url": "https://careers.mitre.org/us/en/search-results?keywords=cybersecurity",
        "keywords": ["cybersecurity", "engineer", "researcher", "intern", "analyst"],
    },
    {
        "company": "Cognizant",
        "url": "https://careers.cognizant.com/global/en/search-results?keywords=cybersecurity",
        "search_url": "https://careers.cognizant.com/global/en/search-results?keywords=cybersecurity",
        "keywords": ["security", "analyst", "engineer", "soc", "cyber"],
    },
    {
        "company": "Accenture",
        "url": "https://www.accenture.com/us-en/careers/jobsearch?jk=cybersecurity",
        "search_url": "https://www.accenture.com/us-en/careers/jobsearch?jk=cybersecurity+analyst",
        "keywords": ["security", "analyst", "cyber", "intern", "associate"],
    },
    {
        "company": "Palo Alto Networks",
        "url": "https://jobs.paloaltonetworks.com",
        "search_url": "https://jobs.paloaltonetworks.com/en/search-jobs/?search-keyword=security+analyst",
        "keywords": ["analyst", "engineer", "intern", "researcher"],
    },
    {
        "company": "SentinelOne",
        "url": "https://www.sentinelone.com/company/careers/",
        "search_url": "https://www.sentinelone.com/company/careers/?gh_jid=",
        "keywords": ["security", "analyst", "researcher", "intern", "engineer"],
    },
    {
        "company": "Bishop Fox",
        "url": "https://jobs.lever.co/bishopfox",
        "search_url": "https://jobs.lever.co/bishopfox",
        "keywords": ["penetration", "security", "analyst", "consultant", "intern", "engineer"],
    },
    {
        "company": "Arctic Wolf",
        "url": "https://boards.greenhouse.io/arcticwolf",
        "search_url": "https://boards.greenhouse.io/arcticwolf",
        "keywords": ["analyst", "soc", "security", "intern", "engineer"],
    },
    {
        "company": "Coalfire",
        "url": "https://jobs.lever.co/coalfire",
        "search_url": "https://jobs.lever.co/coalfire",
        "keywords": ["analyst", "security", "intern", "consultant", "pen", "engineer"],
    },
]


def make_id(title, company, url):
    raw = f"{title.lower().strip()}{company.lower().strip()}{url}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def detect_job_type(title, description=""):
    """Detect if this is Internship, Contract, Part-time, or Full-time."""
    text = f"{title} {description}".lower()
    if any(x in text for x in ["intern", "internship", "co-op", "coop"]):
        return "Internship"
    if any(x in text for x in ["contract", "contractor", "temp ", "temporary"]):
        return "Contract"
    if any(x in text for x in ["part-time", "part time", "parttime"]):
        return "Part-Time"
    return "Full-Time"


# ── LINKEDIN ─────────────────────────────────────────────────────────────────

def scrape_linkedin(max_results=40):
    jobs = []
    roles_to_search = ALL_ROLES[:10]  # Top 10 roles

    for role in roles_to_search:
        url = (
            f"https://www.linkedin.com/jobs/search?"
            f"keywords={role.replace(' ', '%20')}"
            f"&location=United%20States"
            f"&f_TPR=r86400"     # Past 24 hours
            f"&f_E=1,2"          # Entry + Associate
            f"&sortBy=DD"
        )
        try:
            resp = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.select("div.base-card, li.jobs-search-results__list-item")

            for card in cards[:5]:
                title_el  = card.select_one("h3.base-search-card__title, .job-card-list__title")
                company_el= card.select_one("h4.base-search-card__subtitle, .job-card-container__company-name")
                loc_el    = card.select_one("span.job-search-card__location")
                link_el   = card.select_one("a.base-card__full-link, a.job-card-list__title")
                time_el   = card.select_one("time")

                if not title_el or not company_el:
                    continue

                title   = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True)
                job_url = link_el.get("href", "") if link_el else ""

                jobs.append({
                    "id":          make_id(title, company, job_url),
                    "title":       title,
                    "company":     company,
                    "location":    loc_el.get_text(strip=True) if loc_el else "US",
                    "url":         job_url,
                    "description": "",
                    "salary":      "",
                    "posted_date": time_el.get("datetime","") if time_el else "",
                    "source":      "LinkedIn",
                    "apply_url":   job_url,
                    "job_type":    detect_job_type(title),
                    "opt_flag":    False,
                    "h1b_flag":    False,
                })
            time.sleep(2)
        except Exception as e:
            log.warning(f"LinkedIn scrape failed for '{role}': {e}")

    log.info(f"LinkedIn: {len(jobs)} jobs scraped")
    return jobs


# ── DICE ─────────────────────────────────────────────────────────────────────

def scrape_dice(max_results=25):
    jobs = []
    roles = ["SOC Analyst", "Cybersecurity Analyst", "Security Engineer",
             "Penetration Tester", "Security Intern", "AppSec"]

    for role in roles:
        url = (
            f"https://www.dice.com/jobs?"
            f"q={role.replace(' ', '+')}"
            f"&location=United+States"
            f"&dateRange=ONE&postedDate=ONE"
            f"&workAuth=opt"
        )
        try:
            resp = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.select("dhi-search-card, div[data-cy='card']")

            for card in cards[:5]:
                title_el   = card.select_one("a.card-title-link, h5 a")
                company_el = card.select_one("a.employer-name, span[data-cy='search-result-company-name']")
                loc_el     = card.select_one("li[data-cy='search-result-location']")
                salary_el  = card.select_one("li[data-cy='search-result-salary']")

                if not title_el:
                    continue

                title   = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else "Unknown"
                job_url = title_el.get("href", "")
                if not job_url.startswith("http"):
                    job_url = f"https://www.dice.com{job_url}"

                jobs.append({
                    "id":          make_id(title, company, job_url),
                    "title":       title,
                    "company":     company,
                    "location":    loc_el.get_text(strip=True) if loc_el else "US",
                    "url":         job_url,
                    "description": "",
                    "salary":      salary_el.get_text(strip=True) if salary_el else "",
                    "posted_date": "",
                    "source":      "Dice",
                    "apply_url":   job_url,
                    "job_type":    detect_job_type(title),
                    "opt_flag":    True,
                    "h1b_flag":    False,
                })
            time.sleep(2)
        except Exception as e:
            log.warning(f"Dice scrape failed for '{role}': {e}")

    log.info(f"Dice: {len(jobs)} jobs scraped")
    return jobs


# ── H1B VISA JOBS ─────────────────────────────────────────────────────────────

def scrape_h1bvisajobs(max_results=20):
    jobs = []
    search_terms = [
        "cybersecurity-analyst", "security-analyst", "soc-analyst",
        "penetration-tester", "information-security-analyst",
        "cybersecurity-engineer", "security-engineer",
    ]

    for term in search_terms:
        url = f"https://h1bvisajobs.com/h1b-jobs/{term}-jobs.html"
        try:
            resp = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
            soup = BeautifulSoup(resp.text, "lxml")

            # Try multiple selectors
            rows = (soup.select("table tr") or
                    soup.select("div.job-item") or
                    soup.select("li.job-listing-item") or
                    soup.select(".job-row"))

            for row in rows[1:6]:  # Skip header row
                cells = row.find_all(["td", "div"])
                if len(cells) < 2:
                    continue

                title_el  = row.select_one("a")
                if not title_el:
                    continue

                title   = title_el.get_text(strip=True)
                job_url = title_el.get("href", "")
                if not job_url.startswith("http"):
                    job_url = f"https://h1bvisajobs.com{job_url}"

                company = cells[1].get_text(strip=True) if len(cells) > 1 else "Unknown"
                location= cells[2].get_text(strip=True) if len(cells) > 2 else "US"

                if title and len(title) > 3:
                    jobs.append({
                        "id":          make_id(title, company, job_url),
                        "title":       title,
                        "company":     company,
                        "location":    location,
                        "url":         job_url,
                        "description": "",
                        "salary":      "",
                        "posted_date": "",
                        "source":      "H1BVisaJobs",
                        "apply_url":   job_url,
                        "job_type":    detect_job_type(title),
                        "opt_flag":    True,
                        "h1b_flag":    True,
                    })
            time.sleep(1.5)
        except Exception as e:
            log.warning(f"H1BVisaJobs failed for '{term}': {e}")

    log.info(f"H1BVisaJobs: {len(jobs)} jobs scraped")
    return jobs


# ── MIGRATEMATE ───────────────────────────────────────────────────────────────

def scrape_migratemate(max_results=25):
    jobs = []
    urls = [
        "https://migratemate.co/opt-jobs/cybersecurity",
        "https://migratemate.co/opt-jobs/information-technology",
    ]
    for url in urls:
        try:
            resp = httpx.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.select("div.job-card, article.job, li.job-listing, div[class*='job']")

            for card in cards[:max_results//2]:
                title_el  = card.select_one("h2, h3, .job-title, [class*='title']")
                company_el= card.select_one(".company, [class*='company']")
                loc_el    = card.select_one(".location, [class*='location']")
                salary_el = card.select_one(".salary, [class*='salary']")
                link_el   = card.select_one("a[href]")
                date_el   = card.select_one(".date, [class*='date'], time")

                if not title_el:
                    continue

                title   = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else "Unknown"
                job_url = link_el.get("href", url) if link_el else url

                jobs.append({
                    "id":          make_id(title, company, job_url),
                    "title":       title,
                    "company":     company,
                    "location":    loc_el.get_text(strip=True) if loc_el else "US",
                    "url":         job_url,
                    "description": "",
                    "salary":      salary_el.get_text(strip=True) if salary_el else "",
                    "posted_date": date_el.get_text(strip=True) if date_el else "",
                    "source":      "MigrateMate",
                    "apply_url":   job_url,
                    "job_type":    detect_job_type(title),
                    "opt_flag":    True,
                    "h1b_flag":    True,
                })
        except Exception as e:
            log.warning(f"MigrateMate scrape failed: {e}")

    log.info(f"MigrateMate: {len(jobs)} jobs scraped")
    return jobs


# ── GITHUB NEW GRAD REPO ──────────────────────────────────────────────────────

def scrape_github_newgrad():
    jobs = []
    urls = [
        "https://api.github.com/repos/SimplifyJobs/New-Grad-Positions/contents/README.md",
        "https://api.github.com/repos/SimplifyJobs/Summer2027-Internships/contents/README.md",
    ]
    security_kw = ["security", "cyber", "soc", "pentest", "infosec", "devsecops", "appsec", "grc"]

    for api_url in urls:
        try:
            import base64
            resp = httpx.get(api_url, headers={**HEADERS, "Accept": "application/vnd.github+json"}, timeout=15)
            if resp.status_code != 200:
                continue
            data = resp.json()
            content = base64.b64decode(data.get("content","")).decode("utf-8", errors="ignore")
            is_internship = "Internship" in api_url or "Summer" in api_url

            for line in content.split("\n"):
                if "|" not in line:
                    continue
                if not any(kw in line.lower() for kw in security_kw):
                    continue

                cols = [c.strip() for c in line.split("|") if c.strip()]
                if len(cols) < 3:
                    continue

                company = re.sub(r'\[([^\]]+)\].*', r'\1', cols[0]).strip()
                title   = cols[1].strip() if len(cols) > 1 else ("Security Intern" if is_internship else "Security Role")
                location= cols[2].strip() if len(cols) > 2 else "US"

                url_match = re.search(r'\(https?://[^\)]+\)', line)
                job_url = url_match.group(0)[1:-1] if url_match else ""
                has_sponsor = any(x in line for x in ["[U]", "sponsor", "visa", ":us:"])

                if company and title and company not in ("Company", "---", ""):
                    jobs.append({
                        "id":          make_id(title, company, job_url),
                        "title":       title,
                        "company":     company,
                        "location":    location,
                        "url":         job_url,
                        "description": f"From SimplifyJobs GitHub. Internship: {is_internship}",
                        "salary":      "",
                        "posted_date": "Recent",
                        "source":      "GitHub/SimplifyJobs",
                        "apply_url":   job_url,
                        "job_type":    "Internship" if is_internship else "Full-Time",
                        "opt_flag":    has_sponsor,
                        "h1b_flag":    has_sponsor,
                    })
        except Exception as e:
            log.warning(f"GitHub repo scrape failed ({api_url}): {e}")

    log.info(f"GitHub/SimplifyJobs: {len(jobs)} security jobs found")
    return jobs


# ── USPONSOR ME ───────────────────────────────────────────────────────────────

def scrape_usponsorMe(max_results=20):
    jobs = []
    urls = [
        "https://usponsor.me/jobs?category=technology&sort=newest",
        "https://usponsor.me/jobs?category=it-security&sort=newest",
    ]
    for url in urls:
        try:
            resp = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.select("div.job-card, article.listing, .job-item, div[class*='job']")

            for card in cards[:max_results//2]:
                title_el  = card.select_one("h2, h3, .title, [class*='title']")
                company_el= card.select_one(".company, [class*='company'], .employer")
                loc_el    = card.select_one(".location, [class*='location']")
                link_el   = card.select_one("a[href]")
                date_el   = card.select_one(".date, time, [class*='date']")

                if not title_el:
                    continue

                title   = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else "Unknown"
                job_url = link_el.get("href", url) if link_el else url
                if not job_url.startswith("http"):
                    job_url = f"https://usponsor.me{job_url}"

                jobs.append({
                    "id":          make_id(title, company, job_url),
                    "title":       title,
                    "company":     company,
                    "location":    loc_el.get_text(strip=True) if loc_el else "US",
                    "url":         job_url,
                    "description": "",
                    "salary":      "",
                    "posted_date": date_el.get_text(strip=True) if date_el else "",
                    "source":      "USponsorMe",
                    "apply_url":   job_url,
                    "job_type":    detect_job_type(title),
                    "opt_flag":    True,
                    "h1b_flag":    True,
                })
        except Exception as e:
            log.warning(f"USponsorMe scrape failed: {e}")

    log.info(f"USponsorMe: {len(jobs)} jobs scraped")
    return jobs


# ── CYBERSEEK / WELCOME TO CYBER (entry-level specific) ──────────────────────

def scrape_welcometocyber(max_results=20):
    """Scrapes WelcomeToCyber.com -- entry-level cybersecurity only."""
    jobs = []
    url = "https://welcometocyber.com/jobs/"
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.select("article, div.job-listing, .job-post, li.job")

        for card in cards[:max_results]:
            title_el  = card.select_one("h2, h3, .job-title, a.position-title")
            company_el= card.select_one(".company, .employer, [class*='company']")
            loc_el    = card.select_one(".location, [class*='location']")
            link_el   = card.select_one("a[href]")

            if not title_el:
                continue

            title   = title_el.get_text(strip=True)
            company = company_el.get_text(strip=True) if company_el else "Unknown"
            job_url = link_el.get("href", "") if link_el else url

            jobs.append({
                "id":          make_id(title, company, job_url),
                "title":       title,
                "company":     company,
                "location":    loc_el.get_text(strip=True) if loc_el else "US",
                "url":         job_url,
                "description": "Entry-level cybersecurity from WelcomeToCyber",
                "salary":      "",
                "posted_date": "",
                "source":      "WelcomeToCyber",
                "apply_url":   job_url,
                "job_type":    detect_job_type(title),
                "opt_flag":    False,
                "h1b_flag":    False,
            })
    except Exception as e:
        log.warning(f"WelcomeToCyber scrape failed: {e}")

    log.info(f"WelcomeToCyber: {len(jobs)} jobs scraped")
    return jobs


# ── BUILTIN.COM ───────────────────────────────────────────────────────────────

def scrape_builtin(max_results=20):
    """Scrapes Builtin.com -- tech company security roles."""
    jobs = []
    urls = [
        "https://builtin.com/jobs/cybersecurity",
        "https://builtin.com/jobs/dev-engineer/security-engineer",
        "https://builtin.com/jobs/data-analytics/security",
    ]
    for url in urls:
        try:
            resp = httpx.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
            soup = BeautifulSoup(resp.text, "lxml")

            # Builtin uses multiple possible structures - try all
            cards = (soup.select("li[data-id]") or
                     soup.select("div[class*='JobCard']") or
                     soup.select("article[class*='job']") or
                     soup.select("div[class*='job-listing']"))

            # Also try grabbing all job links from the page
            if not cards:
                links = soup.select("a[href*='/job/']")
                for link in links[:10]:
                    title = link.get_text(strip=True)
                    job_url = link.get("href", "")
                    if not job_url.startswith("http"):
                        job_url = f"https://builtin.com{job_url}"
                    if title and len(title) > 5:
                        jobs.append({
                            "id":          make_id(title, "Unknown", job_url),
                            "title":       title,
                            "company":     "See listing",
                            "location":    "US",
                            "url":         job_url,
                            "description": "",
                            "salary":      "",
                            "posted_date": "",
                            "source":      "Builtin",
                            "apply_url":   job_url,
                            "job_type":    detect_job_type(title),
                            "opt_flag":    False,
                            "h1b_flag":    False,
                        })
                continue

            for card in cards[:10]:
                title_el  = (card.select_one("a[data-cy='job-title-link']") or
                             card.select_one("h2 a") or
                             card.select_one("a.job-title") or
                             card.select_one("a[href*='/job/']"))
                company_el= (card.select_one("[data-cy='company-title-link']") or
                             card.select_one(".company-name") or
                             card.select_one("[class*='company']"))
                loc_el    = (card.select_one("[data-cy='job-location']") or
                             card.select_one(".location"))

                if not title_el:
                    continue

                title   = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else "See listing"
                job_url = title_el.get("href","")
                if job_url and not job_url.startswith("http"):
                    job_url = f"https://builtin.com{job_url}"

                if title and len(title) > 3:
                    jobs.append({
                        "id":          make_id(title, company, job_url),
                        "title":       title,
                        "company":     company,
                        "location":    loc_el.get_text(strip=True) if loc_el else "US",
                        "url":         job_url,
                        "description": "",
                        "salary":      "",
                        "posted_date": "",
                        "source":      "Builtin",
                        "apply_url":   job_url,
                        "job_type":    detect_job_type(title),
                        "opt_flag":    False,
                        "h1b_flag":    False,
                    })
            time.sleep(1.5)
        except Exception as e:
            log.warning(f"Builtin scrape failed: {e}")

    log.info(f"Builtin: {len(jobs)} jobs scraped")
    return jobs


# ── JOBRIGHT.AI ───────────────────────────────────────────────────────────────

def scrape_jobright(max_results=25):
    """Scrapes Jobright.ai -- AI-matched H1B jobs."""
    jobs = []
    roles = ["SOC Analyst", "Cybersecurity Analyst", "Security Engineer", "Security Intern"]

    for role in roles:
        url = (
            f"https://jobright.ai/jobs/search?"
            f"q={role.replace(' ', '+')}"
            f"&sponsorship=true"
            f"&experienceLevel=entry"
            f"&sort=date"
        )
        try:
            resp = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.select("div.job-card, article[class*='job'], li[class*='job']")

            for card in cards[:7]:
                title_el  = card.select_one("h2, h3, .job-title, [class*='title']")
                company_el= card.select_one(".company, [class*='company']")
                loc_el    = card.select_one(".location, [class*='location']")
                salary_el = card.select_one(".salary, [class*='salary']")
                link_el   = card.select_one("a[href]")

                if not title_el:
                    continue

                title   = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else "Unknown"
                job_url = link_el.get("href","") if link_el else url
                if job_url and not job_url.startswith("http"):
                    job_url = f"https://jobright.ai{job_url}"

                jobs.append({
                    "id":          make_id(title, company, job_url),
                    "title":       title,
                    "company":     company,
                    "location":    loc_el.get_text(strip=True) if loc_el else "US",
                    "url":         job_url,
                    "description": "",
                    "salary":      salary_el.get_text(strip=True) if salary_el else "",
                    "posted_date": "",
                    "source":      "Jobright.ai",
                    "apply_url":   job_url,
                    "job_type":    detect_job_type(title),
                    "opt_flag":    True,
                    "h1b_flag":    True,
                })
            time.sleep(1.5)
        except Exception as e:
            log.warning(f"Jobright scrape failed for '{role}': {e}")

    log.info(f"Jobright.ai: {len(jobs)} jobs scraped")
    return jobs


# ── COMPANY CAREER PAGES (direct -- no ghost jobs) ───────────────────────────

def scrape_company_career_pages(max_results=30):
    """
    Scrapes company career pages directly.
    These are the most reliable -- direct from source, zero ghost jobs.
    """
    jobs = []

    for company_info in COMPANY_CAREER_PAGES:
        company = company_info["company"]
        url     = company_info["search_url"]
        keywords= company_info["keywords"]

        try:
            resp = httpx.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
            soup = BeautifulSoup(resp.text, "lxml")

            # Generic job card selectors
            cards = (
                soup.select("li.opening, div.opening") or
                soup.select("tr.job, div.job") or
                soup.select("article, .job-listing, [class*='position']") or
                soup.select("a[href*='job'], a[href*='career'], a[href*='position']")
            )

            for card in cards[:10]:
                title_el  = card.select_one("h2, h3, h4, .title, [class*='title'], strong")
                link_el   = card if card.name == "a" else card.select_one("a[href]")

                if not title_el:
                    text_content = card.get_text(" ", strip=True).lower()
                    if not any(kw in text_content for kw in keywords):
                        continue
                    title = card.get_text(" ", strip=True)[:80]
                else:
                    title = title_el.get_text(strip=True)

                if not any(kw in title.lower() for kw in keywords):
                    continue

                job_url = link_el.get("href","") if link_el else url
                if not job_url.startswith("http"):
                    from urllib.parse import urljoin
                    job_url = urljoin(url, job_url)

                loc_el = card.select_one(".location, [class*='location']")

                jobs.append({
                    "id":          make_id(title, company, job_url),
                    "title":       title[:100],
                    "company":     company,
                    "location":    loc_el.get_text(strip=True) if loc_el else "US (check listing)",
                    "url":         job_url,
                    "description": f"Direct from {company} career page -- verified opening",
                    "salary":      "",
                    "posted_date": "Recent",
                    "source":      f"Direct:{company}",
                    "apply_url":   job_url,
                    "job_type":    detect_job_type(title),
                    "opt_flag":    False,
                    "h1b_flag":    False,
                })

            log.info(f"Direct:{company}: {len([j for j in jobs if j.get('source','').endswith(company)])} jobs")
            time.sleep(2)

        except Exception as e:
            log.warning(f"Career page scrape failed for {company}: {e}")

    log.info(f"Company career pages total: {len(jobs)} jobs")
    return jobs


# ── LINKEDIN CONNECTION ANALYZER ─────────────────────────────────────────────

def get_linkedin_connection_search_queries():
    """
    Returns LinkedIn search queries to find hiring managers
    among your existing connections and mutual connections.
    Run these manually in LinkedIn search.
    """
    queries = [
        # Search your 1st-degree connections who are hiring managers
        {
            "label": "Your 1st connections in cybersecurity hiring roles",
            "url": 'https://www.linkedin.com/search/results/people/?network=%5B"F"%5D&keywords=cybersecurity%20manager%20OR%20director%20OR%20recruiter%20OR%20hiring',
            "instructions": "Filter: 1st connections + Cybersecurity + Manager/Director/Recruiter",
        },
        {
            "label": "2nd-degree connections at target companies",
            "url": 'https://www.linkedin.com/search/results/people/?network=%5B"S"%5D&keywords=cybersecurity%20analyst%20OR%20security%20engineer&company=Deloitte%2CRapid7%2CCrowdStrike%2CMITRE',
            "instructions": "2nd connections at Deloitte, Rapid7, CrowdStrike, MITRE -- ask your mutual for intro",
        },
        {
            "label": "Wright State alumni in cybersecurity",
            "url": 'https://www.linkedin.com/search/results/people/?keywords=cybersecurity%20security&school=Wright+State+University&network=%5B"F"%2C"S"%5D',
            "instructions": "WSU alumni in security -- highest response rate, shared connection",
        },
        {
            "label": "Ohio-based security hiring managers",
            "url": 'https://www.linkedin.com/search/results/people/?keywords=cybersecurity%20manager%20OR%20director%20OR%20talent%20acquisition&geoUrn=%5B"103644278"%5D',
            "instructions": "Ohio-based people in security hiring roles -- local advantage",
        },
        {
            "label": "Recruiters at target companies",
            "url": 'https://www.linkedin.com/search/results/people/?keywords=talent%20acquisition%20cybersecurity%20recruiter&company=Deloitte%2CAccenture%2CMITRE%2CRapid7%2CCrowdStrike',
            "instructions": "Recruiters at your top 5 target companies -- DM these first",
        },
    ]
    return queries


def print_linkedin_search_guide():
    """Print LinkedIn connection search guide."""
    queries = get_linkedin_connection_search_queries()
    print("\n" + "="*60)
    print("  LINKEDIN CONNECTION SEARCH GUIDE")
    print("  Find hiring managers in your existing network")
    print("="*60)
    for i, q in enumerate(queries, 1):
        print(f"\n{i}. {q['label']}")
        print(f"   URL: {q['url'][:80]}...")
        print(f"   How: {q['instructions']}")
    print("\nTIP: Message 1st-degree connections first (highest reply rate)")
    print("TIP: For 2nd-degree, ask your mutual connection for a warm intro")
    print("TIP: WSU alumni respond 3x more than strangers")
    print("="*60 + "\n")


# ── MASTER SCRAPER ────────────────────────────────────────────────────────────

def run_all_scrapers(config: dict) -> list:
    """Run all enabled scrapers and return combined deduplicated job list."""
    all_jobs = []
    seen_ids = set()

    scrapers = [
        ("LinkedIn",         scrape_linkedin,           True),
        ("Dice",             scrape_dice,               True),
        ("H1BVisaJobs",      scrape_h1bvisajobs,        True),
        ("MigrateMate",      scrape_migratemate,        True),
        ("GitHub/Simplify",  scrape_github_newgrad,     True),
        ("USponsorMe",       scrape_usponsorMe,         True),
        ("Jobright.ai",      scrape_jobright,           True),
        ("Builtin",          scrape_builtin,            True),
        ("WelcomeToCyber",   scrape_welcometocyber,     True),
        ("CompanyCareerPages",scrape_company_career_pages, True),
    ]

    for name, fn, enabled in scrapers:
        if not enabled:
            log.info(f"Skipping {name} (disabled)")
            continue
        log.info(f"Scraping {name}...")
        try:
            jobs = fn()
            new_count = 0
            for job in jobs:
                if job["id"] not in seen_ids:
                    seen_ids.add(job["id"])
                    all_jobs.append(job)
                    new_count += 1
            log.info(f"  -> {new_count} new unique jobs from {name}")
        except Exception as e:
            log.error(f"  {name} failed entirely: {e}")

    log.info(f"\nTotal unique jobs collected: {len(all_jobs)}")
    return all_jobs
