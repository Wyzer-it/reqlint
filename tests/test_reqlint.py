"""Tests for the reqlint rules and CLI.

Each rule is tested for both the finding it should make and the finding it
should not make — a linter that flags everything is as useless as one that
flags nothing.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import reqlint  # noqa: E402

REQLINT_PY = str(Path(__file__).resolve().parent.parent / "reqlint.py")


def rules_fired(text):
    """Return the set of rule names reqlint reports for a single line."""
    return {f.rule for f in reqlint.lint_line(1, text).findings}


# --- ambiguous-word ---------------------------------------------------------

@pytest.mark.parametrize("text", [
    "The UI shall be user-friendly.",
    "The system shall provide an appropriate response.",
    "The log shall be written as required.",
    "The interface shall be TBD.",
])
def test_ambiguous_words_are_flagged(text):
    assert "ambiguous-word" in rules_fired(text)


def test_multiword_ambiguous_phrases_are_flagged():
    assert "ambiguous-word" in rules_fired("The system shall log transactions if practical.")


@pytest.mark.parametrize("text", [
    "The system shall support several languages.",
    "Under certain conditions the relay shall open.",
    "The fault shall be detected early.",
    "The component shall tolerate a few dropouts.",
])
def test_quantity_weak_words_are_flagged(text):
    assert "ambiguous-word" in rules_fired(text)


def test_inflected_ambiguous_word_is_flagged_with_the_form_found():
    findings = reqlint.lint_line(1, "A segment is adequately specified by two points.").findings
    messages = [f.message for f in findings if f.rule == "ambiguous-word"]
    assert len(messages) == 1 and '"adequately"' in messages[0]


def test_precise_requirement_has_no_ambiguity_finding():
    text = "The gateway shall reject malformed packets and return an HTTP 400 status code."
    assert "ambiguous-word" not in rules_fired(text)


def test_ambiguous_match_is_whole_word_only():
    # "clearly" is ambiguous; "clear" inside another word must not trigger it
    assert "ambiguous-word" not in rules_fired("The buffer shall clear within 5 ms.")


# --- weak-modal -------------------------------------------------------------

@pytest.mark.parametrize("modal", ["should", "may", "might", "could", "can"])
def test_weak_modals_are_flagged(modal):
    assert "weak-modal" in rules_fired(f"The system {modal} log all transactions.")


def test_shall_is_not_flagged_as_weak():
    assert "weak-modal" not in rules_fired("The system shall log all transactions.")


def test_weak_modal_is_high_severity():
    findings = reqlint.lint_line(1, "The system should log.").findings
    assert [f.severity for f in findings if f.rule == "weak-modal"] == ["high"]


# --- missing-unit -----------------------------------------------------------

def test_relative_claim_without_unit_is_flagged():
    assert "missing-unit" in rules_fired("The response time shall be fast.")


@pytest.mark.parametrize("text", [
    "The response shall be fast, within 200 ms.",
    "The transfer shall be quick, at least 5 MB per second.",
    "The delay shall be short, under 2 s.",
])
def test_relative_claim_with_a_unit_is_not_flagged(text):
    assert "missing-unit" not in rules_fired(text)


def test_no_relative_term_means_no_missing_unit_finding():
    assert "missing-unit" not in rules_fired("The gateway shall return an HTTP 400 status code.")


@pytest.mark.parametrize("text", [
    "The output shall be protected against short circuits.",
    "The ECU shall detect a short-circuit on the sensor line.",
    "The driver shall report a short to ground and a short to battery.",
    "The long range radar shall send object data on CAN.",
    "The lamp shall stay on as long as the door is open.",
])
def test_technical_terms_with_unit_hint_words_are_not_flagged(text):
    assert "missing-unit" not in rules_fired(text)


def test_exempt_term_does_not_hide_a_real_relative_claim():
    text = "After a short circuit the output shall recover within a short time."
    assert "missing-unit" in rules_fired(text)


# --- vague-pronoun ----------------------------------------------------------

@pytest.mark.parametrize("lead", ["It", "This", "That", "These", "Those"])
def test_vague_pronoun_leads_are_flagged(lead):
    assert "vague-pronoun" in rules_fired(f"{lead} shall handle errors.")


def test_pronoun_is_only_flagged_in_the_lead_position():
    assert "vague-pronoun" not in rules_fired("The handler shall log it on failure.")


def test_vague_pronoun_is_low_severity():
    findings = reqlint.lint_line(1, "It shall handle errors.").findings
    assert [f.severity for f in findings if f.rule == "vague-pronoun"] == ["low"]


# --- file handling ----------------------------------------------------------

def test_blank_lines_are_skipped_and_do_not_consume_numbers(tmp_path):
    spec = tmp_path / "spec.txt"
    spec.write_text(
        "The system shall start within 3 s.\n"
        "\n"
        "   \n"
        "The UI should be user-friendly.\n",
        encoding="utf-8",
    )
    reports = reqlint.lint_file(str(spec))
    assert len(reports) == 2
    # numbering counts requirements, not physical file lines
    assert [r.line_number for r in reports] == [1, 2]
    assert reports[1].findings


def test_clean_file_produces_no_findings(tmp_path):
    spec = tmp_path / "spec.txt"
    spec.write_text("The gateway shall return an HTTP 400 status code.\n", encoding="utf-8")
    assert reqlint.lint_file(str(spec))[0].findings == []


# --- CLI --------------------------------------------------------------------

def run_cli(*args):
    return subprocess.run(
        [sys.executable, REQLINT_PY, *args],
        capture_output=True, text=True,
    )


@pytest.fixture
def flagged_spec(tmp_path):
    spec = tmp_path / "spec.txt"
    spec.write_text("The response time shall be fast.\n", encoding="utf-8")
    return str(spec)


@pytest.fixture
def clean_spec(tmp_path):
    spec = tmp_path / "spec.txt"
    spec.write_text("The gateway shall return an HTTP 400 status code.\n", encoding="utf-8")
    return str(spec)


def test_cli_exits_zero_without_fail_on(flagged_spec):
    assert run_cli(flagged_spec).returncode == 0


def test_fail_on_high_exits_nonzero_when_a_high_finding_exists(flagged_spec):
    assert run_cli(flagged_spec, "--fail-on", "high").returncode == 1


def test_fail_on_high_exits_zero_on_a_clean_file(clean_spec):
    assert run_cli(clean_spec, "--fail-on", "high").returncode == 0


def test_fail_on_low_catches_a_low_severity_finding(tmp_path):
    spec = tmp_path / "spec.txt"
    spec.write_text("It shall handle errors within 5 ms.\n", encoding="utf-8")
    assert run_cli(str(spec), "--fail-on", "low").returncode == 1
    # a low finding must not trip a high-severity gate
    assert run_cli(str(spec), "--fail-on", "high").returncode == 0


def test_json_output_is_valid_and_carries_the_findings(flagged_spec):
    result = run_cli(flagged_spec, "--json")
    payload = json.loads(result.stdout)
    assert payload[0]["line_number"] == 1
    rules = {f["rule"] for f in payload[0]["findings"]}
    assert "missing-unit" in rules


def test_version_flag_reports_the_package_version():
    result = run_cli("--version")
    assert reqlint.__version__ in result.stdout


def test_clean_file_says_so(clean_spec):
    assert "no issues found" in run_cli(clean_spec).stdout
