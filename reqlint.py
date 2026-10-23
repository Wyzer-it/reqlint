#!/usr/bin/env python3
"""reqlint — a small linter for ambiguous/weak language in requirements text.

Checks each requirement line against well-known ambiguity patterns from the
INCOSE Guide for Writing Requirements and common EARS-syntax conventions.
No proprietary detection logic — pure rule-based, public-domain patterns.
"""
import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict

__version__ = "0.2.0"

AMBIGUOUS_WORDS = {
    "appropriate", "adequate", "sufficient", "reasonable", "acceptable",
    "user-friendly", "flexible", "efficient", "robust", "seamless",
    "state-of-the-art", "easy", "fast", "quickly", "significant",
    "various", "clearly", "normal", "typical", "minimal", "maximal",
    "as needed", "as required", "if possible", "if practical",
    "and/or", "etc", "tbd", "to be determined",
    # Quantity and timing words that testers judged a defect in at least half
    # their uses in the QuRE dataset (see README). Words that were mostly
    # harmless in context ("close", "detail", "special") are deliberately left out.
    "several", "certain", "early", "few",
}

# Inflected forms that carry the same vagueness as their base term
# ("adequately specified"). The finding names the form actually found.
AMBIGUOUS_WORD_FORMS = {
    "adequate": ("adequately",),
    "appropriate": ("appropriately",),
    "sufficient": ("sufficiently",),
    "reasonable": ("reasonably",),
}
_AMBIGUOUS_PATTERNS = {
    w: re.compile(r"\b(" + "|".join(re.escape(f) for f in (w,) + AMBIGUOUS_WORD_FORMS.get(w, ())) + r")\b")
    for w in AMBIGUOUS_WORDS
}

WEAK_MODALS = {"should", "may", "might", "could", "can"}
STRONG_MODAL = "shall"

VAGUE_PRONOUNS = {"it", "this", "that", "these", "those"}

UNIT_HINT_WORDS = {"fast", "quickly", "slow", "large", "small", "long", "short"}
UNIT_PATTERN = re.compile(r"\d+(\.\d+)?\s*(ms|s|sec|seconds?|minutes?|mb|gb|kb|%|hz|km|m\b)", re.I)

# Fixed technical terms and connectives that contain a unit hint word but state
# no relative quantity: "short circuit", "short to ground", "long-range radar",
# "as long as". Removed before the missing-unit check.
UNIT_HINT_EXEMPT_PATTERN = re.compile(
    r"\bshort[\s-]*(circuit\w*|cut\w*"
    r"|to\s+(ground|gnd|battery|batt|ubatt?|vbatt?|power|supply|plus|minus))\b"
    r"|\b(short|long)[\s-]+range\b"
    r"|\bas\s+long\s+as\b",
    re.I,
)


@dataclass
class Finding:
    rule: str
    severity: str
    message: str


@dataclass
class LineReport:
    line_number: int
    text: str
    findings: list = field(default_factory=list)


def check_ambiguous_words(text: str) -> list:
    lowered = text.lower()
    hits = [m.group(0) for m in (p.search(lowered) for p in _AMBIGUOUS_PATTERNS.values()) if m]
    return [
        Finding("ambiguous-word", "medium", f'Ambiguous term "{w}" — replace with a measurable criterion.')
        for w in hits
    ]


def check_modal_strength(text: str) -> list:
    lowered = text.lower()
    findings = []
    for w in WEAK_MODALS:
        if re.search(rf"\b{re.escape(w)}\b", lowered):
            findings.append(Finding(
                "weak-modal", "high",
                f'Uses "{w}" — a binding requirement should use "{STRONG_MODAL}" for testability.'
            ))
    return findings


def check_missing_units(text: str) -> list:
    lowered = UNIT_HINT_EXEMPT_PATTERN.sub(" ", text.lower())
    hits = [w for w in UNIT_HINT_WORDS if re.search(rf"\b{re.escape(w)}\b", lowered)]
    if hits and not UNIT_PATTERN.search(text):
        return [Finding(
            "missing-unit", "high",
            f'Uses relative term(s) {hits} with no measurable unit or threshold nearby.'
        )]
    return []


def check_vague_pronoun_lead(text: str) -> list:
    first_word = re.match(r"\s*([A-Za-z']+)", text)
    if first_word and first_word.group(1).lower() in VAGUE_PRONOUNS:
        return [Finding(
            "vague-pronoun", "low",
            f'Starts with vague pronoun "{first_word.group(1)}" — name the actual subject.'
        )]
    return []


RULES = [check_ambiguous_words, check_modal_strength, check_missing_units, check_vague_pronoun_lead]


def lint_line(line_number: int, text: str) -> LineReport:
    report = LineReport(line_number=line_number, text=text)
    for rule in RULES:
        report.findings.extend(rule(text))
    return report


def lint_file(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f if l.strip()]
    return [lint_line(i + 1, line) for i, line in enumerate(lines)]


def main():
    parser = argparse.ArgumentParser(description="Lint a requirements text file for ambiguous/weak language.")
    parser.add_argument("file", help="Path to a text file, one requirement per line")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a human-readable report")
    parser.add_argument("--fail-on", choices=["low", "medium", "high"], default=None,
                         help="Exit with status 1 if any finding at or above this severity is present")
    parser.add_argument("--version", action="version", version=f"reqlint {__version__}")
    args = parser.parse_args()

    reports = lint_file(args.file)
    severity_rank = {"low": 0, "medium": 1, "high": 2}
    worst = -1

    if args.json:
        print(json.dumps([
            {"line_number": r.line_number, "text": r.text,
             "findings": [asdict(f) for f in r.findings]}
            for r in reports
        ], indent=2))
    else:
        flagged = [r for r in reports if r.findings]
        if not flagged:
            print(f"reqlint: {len(reports)} requirement(s) checked, no issues found.")
        for r in flagged:
            print(f"\nL{r.line_number}: {r.text}")
            for f in r.findings:
                print(f"  [{f.severity:6}] {f.rule}: {f.message}")
        print(f"\n{len(flagged)}/{len(reports)} requirement(s) flagged.")

    for r in reports:
        for f in r.findings:
            worst = max(worst, severity_rank[f.severity])

    if args.fail_on and worst >= severity_rank[args.fail_on]:
        sys.exit(1)


if __name__ == "__main__":
    main()
