"""Local, deterministic policy checks. Findings contain rule IDs, never matched values."""

import re
import unicodedata
from dataclasses import dataclass, replace
from typing import Literal

from app.core.config import get_settings

REFUSAL = "I can't help bypass access controls, expose credentials, or follow instructions that override workspace safeguards."
SENSITIVE_OUTPUT = "I couldn't safely return that answer because it contained protected information. Please ask without credentials or sensitive identifiers."

# These are supported formats, not a claim to recognize every secret or identifier.
SECRET_PATTERNS = [
    re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        re.S,
    ),
    re.compile(
        r"\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|lsv2_[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})\b"
    ),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    re.compile(r"(?i)\b(?:postgres(?:ql)?(?:\+asyncpg)?|mysql|mongodb(?:\+srv)?)://[^\s/@]+:[^\s/@]+@[^\s]+"),
    re.compile(
        r"(?i)\b(?:api[_ -]?key|access[_ -]?token|jwt[_ -]?secret|password|client[_ -]?secret)\s*[:=]\s*[\"']?[A-Za-z0-9_./+~!@#$%^&*=-]{8,}[\"']?"
    ),
]
SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
CARD = re.compile(r"(?<![\w\d])(?:\d[ -]?){12,18}\d(?![\w\d])")
INSTRUCTIONS = {
    "override_instructions": re.compile(
        r"\b(?:ignore|disregard|override|forget|bypass)\b.{0,80}\b(?:previous|prior|system|developer|safety|security|access|all)\b.{0,50}\b(?:instructions?|prompts?|rules?|restrictions?|controls?|checks?)\b",
        re.I,
    ),
    "hidden_prompt": re.compile(
        r"\b(?:reveal|show|print|dump|repeat|display|return)\b.{0,60}\b(?:system|developer|hidden)\s+(?:prompts?|messages?|instructions?)\b",
        re.I,
    ),
    "credential_extraction": re.compile(
        r"\b(?:reveal|show|print|dump|send|extract|give|list|steal|exfiltrate)\b.{0,80}?\b(?:api[_ -]?keys?|jwt[_ -]?secrets?|database\s+passwords?|private\s+keys?|access[_ -]?tokens?|credentials?)\b",
        re.I,
    ),
    "role_bypass": re.compile(
        r"\b(?:bypass|disable|ignore|circumvent)\b.{0,40}\b(?:role|permission|authorization|authentication|tenant|access)\b.{0,30}\b(?:checks?|controls?|restrictions?|isolation|rules?)\b",
        re.I,
    ),
    "role_impersonation": re.compile(
        r"\b(?:pretend|act as|assume the role of)\b.{0,35}\b(?:admin|administrator|system|developer)\b",
        re.I,
    ),
}


@dataclass(frozen=True)
class Decision:
    action: Literal["ALLOW", "REDACT", "CLARIFY", "REFUSE"]
    text: str
    rules: tuple[str, ...] = ()

    def metadata(self):
        return {
            "action": self.action,
            "rules": list(self.rules),
            "policy_version": "1",
            "enabled": get_settings().guardrails_enabled,
        }


def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFKC", text) if unicodedata.category(c) != "Cf")


def luhn(value):
    digits = [int(c) for c in value if c.isdigit() and c.isascii()]
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    total = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def redact(text):
    cfg = get_settings()
    if not cfg.guardrails_enabled:
        return text
    text = normalize(text)
    # Also protect the credentials actually configured in this process, even if their
    # provider uses an unfamiliar token format. Never return them as a finding.
    for name in (
        "llm_api_key",
        "inference_api_key",
        "jwt_secret",
        "langsmith_api_key",
        "seed_admin_password",
    ):
        value = getattr(cfg, name, "")
        if len(value) >= 12:
            text = text.replace(value, "[REDACTED_SECRET]")
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED_SECRET]", text)
    if cfg.guardrails_redact_identifiers:
        text = SSN.sub("[REDACTED_IDENTIFIER]", text)
        text = CARD.sub(lambda m: "[REDACTED_IDENTIFIER]" if luhn(m[0]) else m[0], text)
    return text


def redact_value(value):
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, dict):
        # Resource identities are authorization references, not free-text content.
        # Redacting digit-heavy IDs can break citations and source-access checks.
        return {
            key: item if isinstance(key, str) and (key == "id" or key.endswith("_id")) else redact_value(item)
            for key, item in value.items()
        }
    return value


def inspect(text, *, stage="input"):
    if not get_settings().guardrails_enabled:
        return Decision("ALLOW", text, ("policy_disabled",))
    if not normalize(text).strip():
        if stage == "input":
            return Decision("CLARIFY", "Please enter a question using visible text.", ("empty_question",))
        if stage == "output":
            return Decision("REFUSE", SENSITIVE_OUTPUT, ("empty_output",))
    clean = redact(text)
    probe = " ".join(normalize(text).split())
    # A quoted attack discussed as an example is legitimate security education.
    # Requests to execute/follow that example are still inspected in full.
    educational = re.match(r"\s*(?:explain|define|what (?:is|are)|how (?:can|do|does|to))\b", probe, re.I)
    if educational and not re.search(r"\b(?:follow|obey|execute|perform)\b", probe, re.I):
        probe = re.sub(r"\"[^\"]*\"|'[^']*'|`[^`]*`", "quoted example", probe)
    rules = ()
    if stage != "output":
        rules = tuple(
            name
            for name, pattern in INSTRUCTIONS.items()
            if any(
                not re.search(
                    r"\b(?:do not|don't|never|must not|should not|cannot|can't)\s*$",
                    probe[max(0, match.start() - 20) : match.start()],
                    re.I,
                )
                and not (
                    name == "credential_extraction"
                    and re.match(
                        r"(?:show|give)\s+(?:me\s+)?how\s+to\s+(?:securely\s+)?(?:rotate|protect|store|revoke|manage|configure|create)\b",
                        match[0],
                        re.I,
                    )
                )
                for match in pattern.finditer(probe)
            )
        )
    if rules:
        return Decision("REFUSE", REFUSAL, rules)
    if clean != normalize(text):
        if stage == "input" and clean.strip() in {"[REDACTED_SECRET]", "[REDACTED_IDENTIFIER]"}:
            return Decision(
                "CLARIFY",
                "Please ask a question without including credentials or sensitive identifiers.",
                ("sensitive_data",),
            )
        return Decision(
            "REFUSE" if stage == "output" else "REDACT",
            SENSITIVE_OUTPUT if stage == "output" else clean,
            ("sensitive_data",),
        )
    return Decision("ALLOW", clean)


def screen_candidates(candidates):
    """Withhold instruction-bearing chunks before reranking or generation."""
    safe, excluded, redacted = [], 0, 0
    for item in candidates:
        decisions = [
            inspect(value, stage="context") for value in (item.document, item.section or "", item.text)
        ]
        if any(decision.action == "REFUSE" for decision in decisions):
            excluded += 1
            continue
        metadata = redact_value(item.serialize())
        redacted += int(metadata != item.serialize())
        safe.append(replace(item, **metadata))
    action = "REFUSE" if excluded and not safe else "REDACT" if excluded or redacted else "ALLOW"
    return safe, {
        "action": action,
        "rules": ["untrusted_instructions"] if excluded else ["sensitive_data"] if redacted else [],
        "excluded_chunks": excluded,
        "redacted_chunks": redacted,
        "policy_version": "1",
    }
