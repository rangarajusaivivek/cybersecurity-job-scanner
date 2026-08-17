"""
outreach/hiring_manager_finder.py
===================================
Finds likely hiring manager email + LinkedIn profile for each job.
Uses hunter.io API (25 free lookups/month) + pattern guessing.
"""

import os
import httpx
import re
from utils.logger import log

HUNTER_KEY = os.getenv("HUNTER_API_KEY", "")

# Email patterns by company domain
EMAIL_PATTERNS = {
    "default":       ["{first}@{domain}", "{first}.{last}@{domain}"],
    "google":        ["{first}@google.com"],
    "microsoft":     ["{first}.{last}@microsoft.com"],
    "amazon":        ["{first}@amazon.com"],
    "deloitte":      ["{first}.{last}@deloitte.com"],
    "accenture":     ["{first}.{last}@accenture.com", "{first}.m.{last}@accenture.com"],
    "ey":            ["{first}.{last}@ey.com"],
    "kpmg":          ["{first}.{last}@kpmg.com"],
    "pwc":           ["{first}.{last}@pwc.com"],
    "crowdstrike":   ["{first}.{last}@crowdstrike.com"],
    "rapid7":        ["{first}@rapid7.com", "{first}.{last}@rapid7.com"],
    "sentinelone":   ["{first}@sentinelone.com"],
    "mitre":         ["{first}.{last}@mitre.org"],
    "capitalone":    ["{first}.{last}@capitalone.com"],
    "cognizant":     ["{first}.{last}@cognizant.com"],
    "fortresssrm":   ["{first}@fortresssrm.com"],
}

# LinkedIn search queries for each company type
LINKEDIN_SEARCHES = {
    "Deloitte":         "site:linkedin.com 'Deloitte' 'Cyber' 'Manager' 'Columbus' OR 'Ohio'",
    "Accenture":        "site:linkedin.com 'Accenture' 'Security' 'Manager' 'Analyst'",
    "Rapid7":           "site:linkedin.com 'Rapid7' 'Penetration Testing' 'Manager'",
    "CrowdStrike":      "site:linkedin.com 'CrowdStrike' 'Intelligence' 'Director' OR 'Manager'",
    "MITRE":            "site:linkedin.com 'MITRE' 'Cybersecurity Engineer' OR 'Researcher'",
    "Fortress SRM":     "site:linkedin.com 'Fortress SRM' 'SOC' OR 'Security' 'Director'",
    "Bishop Fox":       "site:linkedin.com 'Bishop Fox' 'Penetration' 'Manager'",
    "default":          "site:linkedin.com '{company}' 'cybersecurity' 'manager' OR 'director'",
}


def get_company_domain(company: str) -> str:
    """Map company name to email domain."""
    company_lower = company.lower().strip()
    domain_map = {
        "microsoft": "microsoft.com",
        "amazon": "amazon.com",
        "google": "google.com",
        "meta": "meta.com",
        "apple": "apple.com",
        "deloitte": "deloitte.com",
        "accenture": "accenture.com",
        "ey": "ey.com",
        "ernst & young": "ey.com",
        "kpmg": "kpmg.com",
        "pwc": "pwc.com",
        "pricewaterhousecoopers": "pwc.com",
        "crowdstrike": "crowdstrike.com",
        "palo alto": "paloaltonetworks.com",
        "rapid7": "rapid7.com",
        "sentinelone": "sentinelone.com",
        "secureworks": "secureworks.com",
        "mitre": "mitre.org",
        "cognizant": "cognizant.com",
        "tcs": "tcs.com",
        "tata consultancy": "tcs.com",
        "infosys": "infosys.com",
        "wipro": "wipro.com",
        "capital one": "capitalone.com",
        "jpmorgan": "jpmorgan.com",
        "fortress srm": "fortresssrm.com",
        "arctic wolf": "arcticwolf.com",
        "bishop fox": "bishopfox.com",
        "ncc group": "nccgroup.com",
        "coalfire": "coalfire.com",
    }
    for key, domain in domain_map.items():
        if key in company_lower:
            return domain
    # Fallback: guess domain from company name
    slug = re.sub(r'[^a-z0-9]', '', company_lower)
    return f"{slug}.com"


def hunter_domain_search(domain: str, role_keywords: list = None) -> list[dict]:
    """
    Use hunter.io API to find email addresses at a company domain.
    Free tier: 25 searches/month. Each search returns multiple contacts.
    """
    if not HUNTER_KEY:
        log.warning("No Hunter API key — skipping domain search")
        return []

    url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={HUNTER_KEY}&type=professional"
    if role_keywords:
        # Filter for security/IT titles
        url += f"&department=it"

    try:
        resp = httpx.get(url, timeout=10)
        data = resp.json()
        contacts = []

        for email_data in data.get("data", {}).get("emails", [])[:5]:
            email = email_data.get("value", "")
            first = email_data.get("first_name", "")
            last = email_data.get("last_name", "")
            position = email_data.get("position", "")
            linkedin = email_data.get("linkedin", "")
            confidence = email_data.get("confidence", 0)

            # Filter for likely hiring managers (managers, directors, leads, recruiters)
            pos_lower = position.lower()
            if any(kw in pos_lower for kw in ["manager", "director", "lead", "head", "recruiter", "talent", "hiring"]):
                contacts.append({
                    "name": f"{first} {last}".strip(),
                    "email": email,
                    "title": position,
                    "linkedin": linkedin,
                    "confidence": confidence,
                    "domain": domain,
                })

        log.info(f"Hunter.io found {len(contacts)} contacts at {domain}")
        return contacts

    except Exception as e:
        log.warning(f"Hunter.io search failed for {domain}: {e}")
        return []


def guess_email(first: str, last: str, domain: str, company: str = "") -> list[str]:
    """Generate likely email variations when hunter.io doesn't have data."""
    first = first.lower().strip()
    last = last.lower().strip()
    f_init = first[0] if first else ""

    patterns_to_try = [
        f"{first}@{domain}",
        f"{first}.{last}@{domain}",
        f"{f_init}{last}@{domain}",
        f"{first}_{last}@{domain}",
        f"{first}-{last}@{domain}",
    ]

    # Use company-specific patterns if known
    co_lower = company.lower()
    for key, patterns in EMAIL_PATTERNS.items():
        if key != "default" and key in co_lower:
            patterns_to_try = [
                p.format(first=first, last=last, domain=domain, f_init=f_init)
                for p in patterns
            ]
            break

    return patterns_to_try


def find_hiring_manager(job: dict) -> dict:
    """
    Main function: find the best hiring manager contact for a job.
    Returns: {name, email, title, linkedin, confidence, search_query}
    """
    company = job.get("company", "")
    role = job.get("title", "")
    domain = get_company_domain(company)

    # Try Hunter.io first
    contacts = hunter_domain_search(domain)
    if contacts:
        best = contacts[0]
        log.info(f"Found HM: {best['name']} ({best['email']}) at {company}")
        return {
            **best,
            "source": "hunter.io",
            "search_query": f"Found via hunter.io domain search for {domain}",
        }

    # Fallback: return LinkedIn search query for manual lookup
    search_template = LINKEDIN_SEARCHES.get(company, LINKEDIN_SEARCHES["default"])
    search_query = search_template.format(company=company)

    return {
        "name": None,
        "email": None,
        "title": "Hiring Manager / Security Team Lead",
        "linkedin": None,
        "confidence": 0,
        "source": "manual_lookup_needed",
        "search_query": search_query,
        "domain": domain,
        "email_patterns": guess_email("firstname", "lastname", domain, company),
    }
