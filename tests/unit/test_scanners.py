"""Unit tests for deterministic scanners, secret detection, redaction, and code pattern rules."""

from tracenest.config import TraceNestConfig
from tracenest.models import ChangeType, FileChange, FindingSeverity
from tracenest.scanners.rules import run_all_scanners, scan_file_for_code_patterns
from tracenest.scanners.secrets import scan_file_for_secrets


def test_secret_detection_and_redaction():
    fake_aws_key = "AKIA1234567890ABCDEF"
    fake_gh_token = "ghp_1234567890abcdefghijklmnopqrstuvwxyzAB"
    fake_openai = "sk-1234567890abcdefghijklmnopqrstuv"
    diff = f"""
@@ -1 +1,4 @@
+aws_key = "{fake_aws_key}"
+gh_pat = "{fake_gh_token}"
+oa_key = "{fake_openai}"
"""
    findings = scan_file_for_secrets("config.py", diff)
    assert len(findings) == 3

    # Ensure raw secret is strictly redacted in evidence
    evidence_text = " ".join(f.evidence for f in findings)
    assert fake_aws_key not in evidence_text
    assert fake_gh_token not in evidence_text
    assert fake_openai not in evidence_text
    assert "[REDACTED]" in evidence_text


def test_false_positive_keywords_ignored():
    diff = """
+aws_dummy = "AKIA0000000000EXAMPLE" # example key
+token = "sk-placeholder-dummy-key"
"""
    findings = scan_file_for_secrets("test_auth.py", diff)
    assert len(findings) == 0


def test_sensitive_config_file_guard():
    config = TraceNestConfig()
    changes = [
        FileChange(path=".env.production", change_type=ChangeType.ADDED, additions=10),
        FileChange(
            path=".github/workflows/deploy.yml", change_type=ChangeType.MODIFIED, additions=5
        ),
        FileChange(path="certs/server.pem", change_type=ChangeType.ADDED, additions=20),
    ]
    findings = run_all_scanners(changes, config)
    rule_ids = {f.rule_id for f in findings}

    assert "CFG-ENV-FILE" in rule_ids
    assert "CFG-GH-WORKFLOW" in rule_ids
    assert "CFG-CERT-KEY" in rule_ids


def test_scope_boundary_violation():
    config = TraceNestConfig()
    config.scope.include_paths = ["src"]
    config.rules.scope_guard = True

    changes = [
        FileChange(path="src/main.py", change_type=ChangeType.MODIFIED, additions=1),
        FileChange(
            path="infrastructure/terraform.tf", change_type=ChangeType.MODIFIED, additions=10
        ),
    ]
    findings = run_all_scanners(changes, config)
    scope_findings = [f for f in findings if f.rule_id == "SCP-OUT-OF-SCOPE"]

    assert len(scope_findings) == 1
    assert scope_findings[0].file_path == "infrastructure/terraform.tf"


def test_dependency_modifications_detected():
    config = TraceNestConfig()
    changes = [
        FileChange(path="requirements.txt", change_type=ChangeType.MODIFIED, additions=1),
        FileChange(path="package.json", change_type=ChangeType.MODIFIED, additions=2),
    ]
    findings = run_all_scanners(changes, config)
    rule_ids = {f.rule_id for f in findings}

    assert "DEP-PY-REQ" in rule_ids
    assert "DEP-JS-PKG" in rule_ids


def test_code_patterns_detected():
    diff = """
@@ -0,0 +1,7 @@
+result = eval(user_input)
+subprocess.Popen(cmd, shell=True)
+os.system("rm -rf /")
+data = pickle.loads(raw_bytes)
+resp = httpx.get(url, verify=False)
+os.environ["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
+"""
    findings = scan_file_for_code_patterns("handler.py", diff)
    rule_ids = {f.rule_id for f in findings}

    assert "PAT-PY-EVAL" in rule_ids
    assert "PAT-PY-SHELL-TRUE" in rule_ids
    assert "PAT-PY-OS-SYSTEM" in rule_ids
    assert "PAT-PY-INSECURE-DESERIALIZATION" in rule_ids
    assert "PAT-NET-VERIFY-FALSE" in rule_ids
    assert "PAT-NET-INSECURE-TLS-ENV" in rule_ids


def test_suppression_and_severity_threshold():
    config = TraceNestConfig()
    config.rules.severity_threshold = FindingSeverity.CRITICAL
    config.rules.suppressions = ["CFG-ENV-FILE"]

    changes = [
        FileChange(path=".env.production", change_type=ChangeType.ADDED),  # Suppressed by rule_id
        FileChange(
            path="package.json", change_type=ChangeType.MODIFIED
        ),  # MEDIUM severity (below CRITICAL)
    ]
    findings = run_all_scanners(changes, config)
    assert len(findings) == 0
