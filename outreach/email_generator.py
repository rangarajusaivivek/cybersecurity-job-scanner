"""
outreach/email_generator.py
============================
Generates personalised cold emails for each high-scoring job using Claude.
Emails are tailored to:
- The specific company and role
- Sai's thesis / VAPT / cert background
- OPT framing as a benefit
- The hiring manager's name (if found)
"""

import os
from anthropic import Anthropic
from utils.logger import log

client = Anthropic()

CANDIDATE_BIO = """
- Name: Sai Vivek Rangaraju
- Degree: MS Cybersecurity, Wright State University (May 2026), GPA 3.2
- Work Auth: F-1 OPT — available immediately, zero sponsorship cost for first 3 years
- Certifications: CEH, Azure Fundamentals, Google Cybersecurity, CNSP, ACP, OPSWAT CIP
- Publications: 
    1. MS Thesis on OhioLINK (2026): ML-Assisted PUF Attack and Defense Framework Using CRP-Based Modeling
    2. Computers & Security Journal (Elsevier): FUVCT VPN Anomaly Detection — Patent Awarded
- Experience: 6 months VAPT intern at Ryna Group — tested 5+ ASP.NET apps, 20% risk reduction, NIST/ISO 27001 compliance
- GitHub: github.com/rangarajusaivivek (5 security repos including PUF framework, VPN detector, PenTest toolkit)
- Portfolio: rangarajusaivivek.github.io
- LinkedIn: linkedin.com/in/rangarajusaivivek
- Thesis URL: https://etd.ohiolink.edu/acprod/odb_etd/etd/r/1501/10?clear=10&p10_accession_num=wright1780358128143017
"""

EMAIL_TEMPLATES = {
    "research":     "Emphasise the published MS thesis and Elsevier paper. Lead with the OhioLINK publication. Good for MITRE, universities, Palo Alto Unit 42, CrowdStrike intelligence.",
    "consulting":   "Emphasise VAPT experience and Big 4 pipeline. Lead with live pen testing at Ryna Group and CEH. Good for Deloitte, Accenture, EY, NCC Group, Coalfire.",
    "vendor":       "Emphasise security tools expertise (Metasploit, Burp Suite, Nmap). Good for Rapid7 (built Metasploit), CrowdStrike, SentinelOne, Bishop Fox.",
    "ohio_local":   "Emphasise Ohio location (30 min from Dayton), local candidate advantage. Good for Fortress SRM, Cleveland Clinic, OhioHealth, WSU IT.",
    "ml_security":  "Emphasise ML+security intersection, C-AI/MLPen, thesis research. Good for Anthropic, SentinelOne, Capital One ML-security teams.",
    "default":      "Balanced approach. Lead with publications, then VAPT, then certs. Good for all others.",
}


def classify_company(company: str, role: str) -> str:
    """Pick the best email template for the company."""
    company_lower = company.lower()
    role_lower = role.lower()

    if any(x in company_lower for x in ["mitre", "university", "ohio", "clinic", "health"]):
        return "ohio_local" if any(x in company_lower for x in ["ohio", "clinic", "health"]) else "research"
    if any(x in company_lower for x in ["deloitte", "accenture", "ey", "ernst", "kpmg", "pwc", "ncc", "coalfire", "bishop fox"]):
        return "consulting"
    if any(x in company_lower for x in ["rapid7", "crowdstrike", "sentinelone", "palo alto", "secureworks"]):
        return "vendor"
    if any(x in company_lower for x in ["anthropic", "capital one", "openai"]):
        return "ml_security"
    if "fortress" in company_lower or "ohio" in company_lower:
        return "ohio_local"
    return "default"


def generate_cold_email(job: dict, hiring_manager_name: str = None) -> dict:
    """
    Generate a personalised cold email for a job using Claude.

    Returns dict with:
    - subject: email subject line
    - body: full email body
    - template_type: which template was used
    """
    template_type = classify_company(job.get("company", ""), job.get("title", ""))
    template_guidance = EMAIL_TEMPLATES[template_type]

    hm_greeting = f"Hi {hiring_manager_name}," if hiring_manager_name else "Hi,"
    if hiring_manager_name and "." in hiring_manager_name:
        first = hiring_manager_name.split(".")[0].capitalize()
        hm_greeting = f"Hi {first},"
    elif hiring_manager_name:
        hm_greeting = f"Hi {hiring_manager_name.split()[0]},"

    prompt = f"""Write a cold email from Sai Vivek Rangaraju applying for a job.

CANDIDATE BACKGROUND:
{CANDIDATE_BIO}

JOB DETAILS:
- Title: {job.get('title', 'N/A')}
- Company: {job.get('company', 'N/A')}
- Location: {job.get('location', 'N/A')}
- Source: {job.get('source', 'N/A')}
- Salary: {job.get('salary', 'Not specified')}
- AI Talking Point: {job.get('talking_point', '')}

TEMPLATE STRATEGY: {template_guidance}

EMAIL REQUIREMENTS:
1. Start with: "{hm_greeting}"
2. Opening: One specific, compelling hook (NOT generic). Reference something specific about THIS company or role.
3. Paragraph 2: Most relevant credential for THIS role (thesis OR VAPT experience — pick the stronger one)
4. Paragraph 3: OPT status framed as a benefit: "I'm on F-1 OPT — authorized immediately, zero cost or paperwork for the first 3 years. With my MS degree I qualify for STEM OPT extension, giving us 3 years before any H-1B decision."
5. Call to action: Ask for 15-min call — specific and direct
6. Signature: Full professional signature with LinkedIn + GitHub + thesis link

CONSTRAINTS:
- Maximum 200 words in the body (recruiters stop reading after this)
- No buzzwords: "passionate about", "dedicated to", "excited to", "leverage"
- No generic openers like "I hope this email finds you well"
- Sound like a human researcher, not a resume robot
- The OPT paragraph must be word-for-word as specified above

Respond with JSON only (no markdown):
{{
  "subject": "<compelling subject line — specific to this role>",
  "body": "<full email body>",
  "word_count": <integer>
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        import json
        result = json.loads(response.content[0].text)
        result["template_type"] = template_type
        result["company"] = job.get("company", "")
        result["role"] = job.get("title", "")
        result["job_url"] = job.get("url", "")
        return result
    except Exception as e:
        log.error(f"Email generation failed for {job.get('company')}: {e}")
        return {
            "subject": f"MS Cybersecurity Grad (CEH + Published Research) — {job.get('title', 'Role')} at {job.get('company', '')}",
            "body": f"""{hm_greeting}

My MS thesis on ML-assisted PUF attack modeling just published on OhioLINK (Wright State, 2026), and I have 6 months of live VAPT experience at Ryna Group. I'm applying for the {job.get('title', 'role')} at {job.get('company', 'your company')}.

I'm on F-1 OPT — authorized immediately, zero cost or paperwork for the first 3 years. With my MS degree I qualify for STEM OPT extension, giving us 3 years before any H-1B decision.

Would you have 15 minutes this week? I'd love to tell you more about my research and VAPT work.

Best,
Sai Vivek Rangaraju
MS Cybersecurity, Wright State University 2026
LinkedIn: linkedin.com/in/rangarajusaivivek
GitHub: github.com/rangarajusaivivek
Portfolio: rangarajusaivivek.github.io
Thesis: https://etd.ohiolink.edu/acprod/odb_etd/etd/r/1501/10?clear=10&p10_accession_num=wright1780358128143017""",
            "template_type": template_type,
            "word_count": 130,
            "company": job.get("company", ""),
            "role": job.get("title", ""),
            "job_url": job.get("url", ""),
        }


def save_emails(emails: list[dict], output_dir: str = "data/cold_emails"):
    """Save generated emails to text files."""
    import os
    os.makedirs(output_dir, exist_ok=True)
    for i, email in enumerate(emails):
        company_slug = re.sub(r'[^a-z0-9]', '_', email.get('company', 'unknown').lower())
        filename = f"{output_dir}/{i+1:02d}_{company_slug}_cold_email.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"TO: [Find hiring manager email via hunter.io]\n")
            f.write(f"SUBJECT: {email.get('subject', '')}\n")
            f.write(f"JOB URL: {email.get('job_url', '')}\n")
            f.write(f"TEMPLATE: {email.get('template_type', '')}\n")
            f.write(f"WORD COUNT: {email.get('word_count', '')}\n")
            f.write("-" * 50 + "\n\n")
            f.write(email.get('body', ''))
        log.info(f"Saved email: {filename}")

import re
