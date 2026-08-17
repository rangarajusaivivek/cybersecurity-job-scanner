"""
filters/job_scorer.py
======================
Scores each job listing against Sai's profile using:
1. Keyword matching (fast, no API cost)
2. Claude AI deep scoring for top matches (API call)

Returns score 0-100 + reasoning + APPLY/SKIP/INVESTIGATE verdict.
"""

import re
import os
from anthropic import Anthropic
from utils.logger import log

client = Anthropic()

# -- CANDIDATE PROFILE (used in AI scoring prompt) --------------------------
CANDIDATE_PROFILE = """
Name: Sai Vivek Rangaraju
Degree: MS Cybersecurity, Wright State University (May 2026), GPA 3.2
Work Auth: F-1 OPT — available immediately, no sponsorship cost to employer
Certifications: CEH, Azure Fundamentals, Google Cybersecurity, CNSP, ACP, OPSWAT CIP
Publications: 
  - MS Thesis published on OhioLINK (2026): ML-Assisted PUF Attack and Defense Framework
  - Computers and Security Journal (Elsevier): VPN anomaly detection (FUVCT) — Patent Awarded
Experience: 6 months VAPT intern at Ryna Group (Hyderabad) — tested 5+ ASP.NET apps, 20% risk reduction
Skills: VAPT, Penetration Testing, Web App Security, API Security, SOC Analysis, SIEM/Splunk, 
        Burp Suite, Nmap, Metasploit, Wireshark, Python, OWASP Top 10, OWASP API Top 10,
        NIST, MITRE ATT&CK, ISO 27001, Azure, Log Analysis, Incident Response
        ML/AI Security Research, Hardware Security (PUF), Anomaly Detection
GitHub: 5 cybersecurity repos including PUF framework, VPN anomaly detector, PenTest toolkit
Portfolio: rangarajusaivivek.github.io
Location: Fairborn, OH (open to remote + US relocation)
"""

# -- HARD DISQUALIFIERS -----------------------------------------------------
DISQUALIFIERS = [
    r"(?<!no )(?<!not )clearance required",
    r"security clearance",
    r"ts/sci",
    r"top secret",
    r"us citizen",
    r"us citizenship",
    r"must be citizen",
    r"permanent resident only",
    r"active clearance",
    r"secret clearance",
    r"public trust clearance",
    r"dod clearance",
    r"nato clearance",
]

# -- OPT POSITIVE SIGNALS --------------------------------------------------
OPT_SIGNALS = [
    r"\bopt\b",
    r"visa sponsor",
    r"h[- ]?1b",
    r"h1b",
    r"will sponsor",
    r"international student",
    r"work authorization",
    r"stem opt",
    r"e-?verify",
]

# -- ROLE MATCH KEYWORDS ---------------------------------------------------
ROLE_KEYWORDS = {
    "penetration_testing": ["penetration test", "pentest", "pen test", "vapt", "ethical hack",
                            "offensive security", "red team", "burp suite", "metasploit",
                            "vulnerability assess", "exploit", "offensive"],
    "soc_analyst":        ["soc analyst", "security operations", "siem", "splunk", "log analysis",
                           "incident response", "threat detection", "security monitoring",
                           "alert triage", "threat hunting", "edr", "xdr"],
    "appsec":             ["application security", "appsec", "owasp", "api security", "secure coding",
                           "web app security", "code review", "sast", "dast", "devsecops"],
    "research":           ["security researcher", "research", "machine learning", "ml security",
                           "ai security", "hardware security", "puf", "anomaly detection",
                           "threat intelligence", "malware", "forensics"],
    "internship":         ["intern", "internship", "co-op", "coop", "summer intern", "fall intern",
                           "spring intern", "university", "student", "new grad", "recent graduate",
                           "entry level", "associate", "junior", "0-2 years", "1-3 years"],
    "adjacent":           ["grc", "governance risk compliance", "risk analyst", "compliance analyst",
                           "iam", "identity access", "cloud security", "devsecops", "privacy analyst",
                           "it security", "cyber defense", "security consultant", "network security"],
    "certs_match":        ["ceh", "certified ethical hacker", "azure", "google cybersecurity",
                           "cnsp", "acp", "opswat", "nist", "mitre att&ck", "security+", "cissp"],
}

SENIORITY_EXCLUDES = [
    r"\b(senior|sr\.?|lead|principal|staff|director|manager|head of|vp |vice president)\b",
    r"\b(10\+|8\+|7\+|6\+)\s*(years?|yrs?)",
]

ENTRY_SIGNALS = [
    r"\b(entry[\s-]level|new grad|recent grad|0[-–]2 years?|1[-–]3 years?|junior|associate)\b",
]


def keyword_score(job: dict) -> tuple[int, list]:
    """
    Fast keyword-based scoring. Returns (score 0-100, reasons list).
    No API call — instant.
    """
    text = f"{job.get('title', '')} {job.get('description', '')} {job.get('company', '')}".lower()
    reasons = []
    score = 50  # Start at 50

    # -- Hard disqualifiers ------------------------------------------------
    # Strip negative clearance phrases before checking
    clean_text = re.sub(r"no\s+\w+\s+clearance", " ", text, flags=re.I)
    clean_text = re.sub(r"clearance\s+not\s+required", " ", clean_text, flags=re.I)
    clean_text = re.sub(r"without\s+a\s+clearance", " ", clean_text, flags=re.I)
    for pattern in DISQUALIFIERS:
        if re.search(pattern.replace(r"(?<!no )(?<!not )", ""), clean_text, re.I):
            return 0, [f"[NO] DISQUALIFIED: clearance/citizenship required"]

    # -- Seniority exclusion -----------------------------------------------
    for pattern in SENIORITY_EXCLUDES:
        if re.search(pattern, text, re.I):
            score -= 20
            reasons.append(f"[WARN] Senior/experienced role signal found")
            break

    # -- Entry level boost -------------------------------------------------
    for pattern in ENTRY_SIGNALS:
        if re.search(pattern, text, re.I):
            score += 15
            reasons.append("[OK] Entry level / new grad confirmed")
            break

    # -- OPT-friendly signals ----------------------------------------------
    opt_hits = 0
    for pattern in OPT_SIGNALS:
        if re.search(pattern, text, re.I):
            opt_hits += 1
    if opt_hits > 0:
        boost = min(opt_hits * 8, 20)
        score += boost
        reasons.append(f"[OK] {opt_hits} OPT/visa sponsorship signal(s) found (+{boost})")

    # -- Role match scoring ------------------------------------------------
    for category, keywords in ROLE_KEYWORDS.items():
        hits = [kw for kw in keywords if kw in text]
        if hits:
            boost = min(len(hits) * 5, 20)
            score += boost
            reasons.append(f"[OK] {category}: {', '.join(hits[:3])} (+{boost})")

    # -- Tier 1 company bonus ----------------------------------------------
    tier1 = ["fortress srm", "mitre", "deloitte", "accenture", "ey ", "ernst & young",
             "kpmg", "pwc", "rapid7", "crowdstrike", "bishop fox"]
    for co in tier1:
        if co in text:
            score += 10
            reasons.append(f"[OK] Tier 1 target company: {co}")
            break

    # -- Cap at 0-100 ------------------------------------------------------
    score = max(0, min(100, score))
    return score, reasons


def ai_score(job: dict) -> tuple[int, str, str]:
    """
    Deep AI scoring using Claude for jobs that passed keyword filter (score >= 50).
    Returns (score 0-100, reasoning, verdict: APPLY/INVESTIGATE/SKIP).
    Uses one Claude API call per job.
    """
    jd_text = f"""
Title: {job.get('title', 'N/A')}
Company: {job.get('company', 'N/A')}
Location: {job.get('location', 'N/A')}
Posted: {job.get('posted_date', 'N/A')}
Salary: {job.get('salary', 'N/A')}
Description (first 2000 chars):
{job.get('description', '')[:2000]}
    """.strip()

    prompt = f"""You are a job search assistant for an F-1 OPT cybersecurity candidate.

CANDIDATE PROFILE:
{CANDIDATE_PROFILE}

JOB LISTING:
{jd_text}

Score this job 0-100 for this specific candidate. Consider:
1. Is OPT/visa sponsorship explicitly mentioned or strongly implied? (+25 if yes)
2. Does the role match penetration testing, SOC, AppSec, or security research? (+20)
3. Is it entry-level / 0-2 years experience? (+15)
4. Does it require clearance or US citizenship? (score = 0 if yes)
5. Does it align with candidate's published research, VAPT experience, and certs? (+20)
6. Is it a Tier 1 target company (Deloitte, Rapid7, MITRE, etc.)? (+10)
7. Is it remote-friendly or Ohio-based? (+5)

Respond with ONLY valid JSON (no markdown, no explanation outside JSON):
{{
  "score": <integer 0-100>,
  "verdict": "<APPLY|INVESTIGATE|SKIP>",
  "top_reasons": ["<reason1>", "<reason2>", "<reason3>"],
  "opt_signal": "<YES|NO|UNCLEAR>",
  "clearance_required": "<YES|NO>",
  "best_talking_point": "<one sentence connecting candidate's specific background to this role>"
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        import json
        result = json.loads(response.content[0].text)
        return (
            result.get("score", 50),
            " | ".join(result.get("top_reasons", [])),
            result.get("verdict", "INVESTIGATE"),
        )
    except Exception as e:
        log.warning(f"AI scoring failed for {job.get('title')}: {e}")
        return 50, "AI scoring unavailable", "INVESTIGATE"


def score_job(job: dict, use_ai: bool = True) -> dict:
    """
    Main scoring function. Combines keyword + optional AI scoring.
    Returns enriched job dict with score, verdict, reasons.
    """
    # Step 1: Fast keyword filter
    kw_score, reasons = keyword_score(job)

    if kw_score == 0:
        job["score"] = 0
        job["verdict"] = "SKIP"
        job["reasons"] = reasons
        job["talking_point"] = ""
        return job

    # Step 2: AI deep score for promising jobs
    if use_ai and kw_score >= 50:
        ai_s, ai_reasons, verdict = ai_score(job)
        final_score = int(0.4 * kw_score + 0.6 * ai_s)
        reasons.append(f"🤖 AI score: {ai_s}")
        reasons.append(ai_reasons)
    else:
        final_score = kw_score
        # Lower threshold for internships and direct company career page listings
        is_internship = job.get("job_type", "") == "Internship"
        is_direct     = str(job.get("source", "")).startswith("Direct:")
        apply_thresh  = 55 if (is_internship or is_direct) else 70
        verdict = "APPLY" if kw_score >= apply_thresh else "INVESTIGATE" if kw_score >= 45 else "SKIP"
        ai_reasons = ""

    job["score"] = final_score
    job["verdict"] = verdict
    job["reasons"] = reasons
    job["talking_point"] = ai_reasons
    return job
