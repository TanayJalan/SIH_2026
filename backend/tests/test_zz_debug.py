"""Temporary debug of the compliance acceptance fixture (deleted after use)."""

from tests.test_compliance_acceptance import acceptance_results


def test_debug(acceptance_results):
    for key, preview in acceptance_results.items():
        print(
            key,
            "score",
            preview.score,
            "status",
            preview.status,
            "nil",
            preview.nil_deficiency,
            "mfail",
            preview.mandatory_failed_count,
            "mmiss",
            preview.mandatory_missing_count,
        )
        for rule in preview.rules:
            if rule.status != "PASS":
                print("  ", rule.code, rule.status, rule.mandatory, rule.severity, rule.message[:100])
