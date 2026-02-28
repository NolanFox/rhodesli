"""
Run after interactive testing to analyze session 80 results.
Reads the interactive log and produces a summary.
"""


def synthesize():
    with open("docs/session_logs/session-80-interactive-log.md") as f:
        content = f.read()

    # Count results
    pass_count = content.count("| PASS |") + content.count("| Pass |")
    fail_count = content.count("| FAIL |") + content.count("| Fail |")
    fix_count = content.lower().count("| yes |") + content.lower().count("| fixed |")

    # Count UX issues by severity
    p0 = content.lower().count("| p0 |")
    p1 = content.lower().count("| p1 |")
    p2 = content.lower().count("| p2 |")

    total = pass_count + fail_count
    if total == 0:
        print("No test results recorded yet.")
        return

    print(f"""
=== SESSION 80 SYNTHESIS ===
Tests: {pass_count} passed, {fail_count} failed
Fixes applied: {fix_count}
UX issues: {p0} P0, {p1} P1, {p2} P2

Pass rate: {pass_count / total * 100:.0f}% (target: 80%+)
""")

    lines = content.split("\n")
    tree_issues = sum(1 for line in lines if "Tree" in line and ("FAIL" in line or "Fail" in line))
    card_issues = sum(
        1 for line in lines if ("People" in line or "card" in line.lower()) and ("FAIL" in line or "Fail" in line)
    )

    if tree_issues > 2:
        print("WARNING: Tree has systemic issues - may need architectural review")
    if card_issues > 2:
        print("WARNING: Face cards have systemic issues - component consistency problem")

    print("Full log: docs/session_logs/session-80-interactive-log.md")


if __name__ == "__main__":
    synthesize()
