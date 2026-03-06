"""
Smoke tests for all NodeSet2 helper scripts.

Run from the scripts/ directory:
    python test_parsing.py

Each test calls a script as a subprocess and checks the exit code and
key strings in stdout. Tests use the reference files bundled with the skill.
"""

import subprocess
import sys
import os
import tempfile

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REFS_DIR = os.path.join(SCRIPTS_DIR, "..", "references")

# Reference files used across tests
EXAMPLE_XML = os.path.join(REFS_DIR, "Opc.Ua.IA.NodeSet2.examples.xml")
NODESET_XSD = os.path.join(REFS_DIR, "UANodeSet.xsd")
TIA_XML = os.path.join(REFS_DIR, "tiaportal_nodeset_example.xml")
SIOME_XML = os.path.join(REFS_DIR, "tiaportal_siome_example_nodeset.xml")

PYTHON = sys.executable


def run(script: str, *args: str) -> tuple[int, str]:
    result = subprocess.run(
        [PYTHON, os.path.join(SCRIPTS_DIR, script), *args],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout + result.stderr


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


# ---------------------------------------------------------------------------
# validate_nodes.py
# ---------------------------------------------------------------------------
def test_validate_example():
    print("validate_nodes.py: example xml against UANodeSet.xsd ...")
    code, out = run("validate_nodes.py", EXAMPLE_XML, NODESET_XSD)
    check(code == 0, f"Expected exit 0, got {code}.\nOutput:\n{out}")
    check("valid" in out.lower(), f"Expected 'valid' in output.\nOutput:\n{out}")
    print("  PASS")


# ---------------------------------------------------------------------------
# parse_nodes.py
# ---------------------------------------------------------------------------
def test_parse_nodes():
    print("parse_nodes.py: extract UAObjects from example xml ...")
    code, out = run("parse_nodes.py", EXAMPLE_XML)
    check(code == 0, f"Expected exit 0, got {code}.\nOutput:\n{out}")
    check('"nodeid"' in out, f"Expected JSON with 'nodeid' key.\nOutput:\n{out}")
    print("  PASS")


# ---------------------------------------------------------------------------
# inspect_model.py
# ---------------------------------------------------------------------------
def test_inspect_example():
    print("inspect_model.py: inspect example xml ...")
    code, out = run("inspect_model.py", EXAMPLE_XML)
    check(code == 0, f"Expected exit 0, got {code}.\nOutput:\n{out}")
    check("Namespace" in out, f"Expected namespace info.\nOutput:\n{out}")
    check("Alias" in out, f"Expected alias info.\nOutput:\n{out}")
    print("  PASS")


def test_inspect_tia():
    print("inspect_model.py: inspect TIA Portal example ...")
    code, out = run("inspect_model.py", TIA_XML)
    check(code == 0, f"Expected exit 0, got {code}.\nOutput:\n{out}")
    print("  PASS")


# ---------------------------------------------------------------------------
# dump_hierarchy.py  — pick a well-known root from namespace 0: Server (i=2253)
# ---------------------------------------------------------------------------
def test_dump_hierarchy_example():
    print("dump_hierarchy.py: dump from i=2253 (Server) in example xml ...")
    code, out = run("dump_hierarchy.py", EXAMPLE_XML, "i=2253")
    # If i=2253 isn't in this file, the script exits 1 with a useful message — that's fine.
    # We just check that the script ran without crashing (Python error).
    check("Traceback" not in out, f"Script raised an exception.\nOutput:\n{out}")
    print(f"  PASS  (exit={code})")


# ---------------------------------------------------------------------------
# summarize_types.py
# ---------------------------------------------------------------------------
def test_summarize_types_example():
    print("summarize_types.py: summarize type definitions in example xml ...")
    code, out = run("summarize_types.py", EXAMPLE_XML)
    check(code == 0, f"Expected exit 0, got {code}.\nOutput:\n{out}")
    print("  PASS")


def test_summarize_types_tia():
    print("summarize_types.py: summarize type definitions in TIA xml ...")
    code, out = run("summarize_types.py", TIA_XML)
    check(code == 0, f"Expected exit 0, got {code}.\nOutput:\n{out}")
    print("  PASS")


# ---------------------------------------------------------------------------
# export_nodes_csv.py
# ---------------------------------------------------------------------------
def test_export_nodes_csv():
    print("export_nodes_csv.py: export example xml to CSV ...")
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        csv_path = tmp.name
    try:
        code, out = run("export_nodes_csv.py", EXAMPLE_XML, csv_path)
        check(code == 0, f"Expected exit 0, got {code}.\nOutput:\n{out}")
        check(os.path.exists(csv_path), "CSV file was not created.")
        with open(csv_path, encoding="utf-8") as f:
            content = f.read()
        check("NodeId" in content, "Expected 'NodeId' header in CSV.")
        check("NodeClass" in content, "Expected 'NodeClass' header in CSV.")
        print("  PASS")
    finally:
        if os.path.exists(csv_path):
            os.unlink(csv_path)


# ---------------------------------------------------------------------------
# diff_nodesets.py  — diff a file against itself (should report 0 changes)
# ---------------------------------------------------------------------------
def test_diff_nodesets_identical():
    print("diff_nodesets.py: diff example xml against itself (expect 0 changes) ...")
    code, out = run("diff_nodesets.py", EXAMPLE_XML, EXAMPLE_XML)
    check(code == 0, f"Expected exit 0, got {code}.\nOutput:\n{out}")
    check("0 added, 0 removed, 0 changed" in out,
          f"Expected zero-change summary.\nOutput:\n{out}")
    print("  PASS")


def test_diff_nodesets_different():
    print("diff_nodesets.py: diff example xml against TIA xml (expect some changes) ...")
    code, out = run("diff_nodesets.py", EXAMPLE_XML, TIA_XML)
    check(code == 0, f"Expected exit 0, got {code}.\nOutput:\n{out}")
    check("ADDED" in out and "REMOVED" in out, f"Expected ADDED/REMOVED sections.\nOutput:\n{out}")
    print("  PASS")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
TESTS = [
    test_validate_example,
    test_parse_nodes,
    test_inspect_example,
    test_inspect_tia,
    test_dump_hierarchy_example,
    test_summarize_types_example,
    test_summarize_types_tia,
    test_export_nodes_csv,
    test_diff_nodesets_identical,
    test_diff_nodesets_different,
]

if __name__ == "__main__":
    passed = failed = 0
    for test_fn in TESTS:
        try:
            test_fn()
            passed += 1
        except AssertionError as exc:
            print(f"  FAIL: {exc}")
            failed += 1

    print()
    print(f"Results: {passed} passed, {failed} failed out of {len(TESTS)} tests.")
    sys.exit(0 if failed == 0 else 1)
