import re


def classify(query: str) -> str:
    text = query.lower()
    if re.fullmatch(
        r"\s*(?:(?:hi|hello|hey)(?:\s+(?:there|sai guru))?|good\s+(?:morning|afternoon|evening)|"
        r"how are you|thanks|thank you)[\s!?.]*",
        text,
    ):
        return "DIRECT"
    analytics = bool(
        re.search(
            r"(employee growth|headcount|employees by department|how many employees|"
            r"employees? (?:joined|hired)|monthly (?:joins|hires)|count (?:of )?employees)",
            text,
        )
    )
    documents = bool(
        re.search(r"\b(policy|policies|handbook|guidelines|documentation|documents?|files?|sources?)\b", text)
    )
    if analytics and documents:
        return "HYBRID"
    if analytics:
        return "SQL"
    company_context = bool(
        re.search(
            r"\b(saitech|our|we|company|organization|workplace|internal|uploaded|knowledge base|"
            r"employees?|contractors?|annual leave|sick leave|paid leave|vacation|pto|"
            r"expenses?|reimbursement|remote work|work from home|sev[1-4]|incident response|"
            r"onboarding|offboarding|payroll|salary|salaries|benefits|"
            r"reviewers?|approvals?|pull requests?|code review|"
            r"workspace|data exports?|download links?|retention)\b",
            text,
        )
    )
    # Operational questions may omit "our" or "policy". Search evidence before
    # answering them; an unsuccessful search uses the explicitly labeled fallback.
    return "DOCUMENT" if documents or company_context else "DIRECT"


def is_followup(query: str) -> bool:
    text = query.lower().strip()
    return bool(
        re.search(r"\b(it|that|this policy|they|those|he|she|his|her)\b", text)
        or re.match(r"(?:what about|how about|and\b|also\b)", text)
        or re.fullmatch(
            r"(?:tell me more|explain (?:more|further)|go on|continue|why|give (?:me )?an example|make (?:it )?(?:shorter|simpler))[.!?]*",
            text,
        )
    )


def rewrite(query: str, history: list[dict]) -> str:
    cleaned = " ".join(query.split())
    if is_followup(cleaned) and history:
        users = [m["content"] for m in reversed(history) if m["role"] == "user"]
        previous = next((content for content in users if not is_followup(content)), users[0] if users else "")
        if previous:
            return f"{previous[:500]} Follow-up: {cleaned}"
    return cleaned
