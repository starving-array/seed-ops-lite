"""Security audit quality gate executor for the Repository Guardian Skill."""

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import subprocess


@dataclass
class SecurityAuditResult:
    """Outcome of running the security audit quality gate."""

    success: bool
    message: str
    details: list[str] = field(default_factory=list)


@dataclass
class Finding:
    """Represents a specific security audit finding."""

    check_type: str
    file_path: str
    line_number: int | None
    description: str
    severity: str
    match_str: str = ""


# Compile regex patterns
SECRET_RULES = [
    {
        "name": "PEM Key",
        "regex": re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----"),
        "severity": "CRITICAL",
        "description": "Detected PEM private key structure.",
    },
    {
        "name": "AWS Key ID",
        "regex": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "severity": "CRITICAL",
        "description": "Detected AWS Access Key ID.",
    },
    {
        "name": "AWS Secret Access Key",
        "regex": re.compile(
            r"(?i)aws_secret(?:_access)?_key\s*[:=]\s*['\"]([A-Za-z0-9/+=]{40})['\"]"
        ),
        "severity": "CRITICAL",
        "description": "Detected AWS Secret Access Key.",
    },
    {
        "name": "JWT Secret",
        "regex": re.compile(
            r"\beyJhbGciOi[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"
        ),
        "severity": "HIGH",
        "description": "Detected JSON Web Token (JWT).",
    },
    {
        "name": "Bearer Token",
        "regex": re.compile(r"\bBearer\s+[A-Za-z0-9_\-\.\~\+\/]+={0,2}\b"),
        "severity": "HIGH",
        "description": "Detected Bearer Token.",
    },
    {
        "name": "API Key",
        "regex": re.compile(
            r"(?i)\b(api[_-]?key|apikey|secret_key|secret_token|auth_token)\b\s*[:=]\s*['\"]([A-Za-z0-9_\-\.]{16,})['\"]"
        ),
        "severity": "HIGH",
        "description": "Detected API key or authorization token.",
    },
]

DANGEROUS_CODE_RULES = [
    {
        "name": "eval()",
        "regex": re.compile(r"\beval\s*\("),
        "severity": "HIGH",
        "description": "Use of eval() is highly dangerous.",
    },
    {
        "name": "exec()",
        "regex": re.compile(r"\bexec\s*\("),
        "severity": "HIGH",
        "description": "Use of exec() is highly dangerous.",
    },
    {
        "name": "pickle.loads()",
        "regex": re.compile(r"\bpickle\.loads\s*\("),
        "severity": "CRITICAL",
        "description": "Insecure deserialization using pickle.loads().",
    },
    {
        "name": "yaml.load()",
        "regex": re.compile(r"\byaml\.load\s*\("),
        "severity": "HIGH",
        "description": "Insecure YAML loading using yaml.load().",
    },
    {
        "name": "shell=True",
        "regex": re.compile(r"\bshell\s*=\s*True\b"),
        "severity": "HIGH",
        "description": "Executing shell command with shell=True is dangerous.",
    },
]

CERT_EXTENSIONS = {".crt", ".pem", ".cer", ".key", ".p12", ".pfx"}
CRED_FILENAMES = {"credentials", "credentials.json", "passwd", "secrets.json"}


def get_repo_root() -> Path:
    """Resolve repository root directory path."""
    # Try git first
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return Path(res.stdout.strip())
    except Exception:
        pass
    # Fallback to walking up parents
    curr = Path(__file__).resolve()
    for parent in curr.parents:
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            return parent
    return curr.parent


def get_repo_files(root: Path) -> list[Path]:
    """Get all non-ignored files in the repository using git ls-files."""
    files = set()
    try:
        tracked_res = subprocess.run(
            ["git", "ls-files"],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if tracked_res.returncode == 0:
            for line in tracked_res.stdout.splitlines():
                line = line.strip()
                if line:
                    files.add(root / line)
    except Exception:
        pass

    try:
        untracked_res = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if untracked_res.returncode == 0:
            for line in untracked_res.stdout.splitlines():
                line = line.strip()
                if line:
                    files.add(root / line)
    except Exception:
        pass

    # If git commands fail, do a manual traversal respecting basic ignores
    if not files:
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip hidden dirs
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for filename in filenames:
                files.add(Path(dirpath) / filename)

    return sorted(list(files))


def is_file_ignored(root: Path, filename: str) -> bool:
    """Check if a file pattern is ignored by git check-ignore."""
    try:
        res = subprocess.run(
            ["git", "check-ignore", "-q", filename],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def run_security_audit() -> SecurityAuditResult:
    """Execute secret scans, repository hygiene checks, and dangerous code audits."""
    root = get_repo_root()
    files = get_repo_files(root)

    findings: list[Finding] = []

    # 1. Secret Scan
    secret_findings_count = 0
    for file_path in files:
        if file_path.name == ".env":
            continue
        # Skip tests and guardian scripts from scanning
        try:
            rel_path = str(file_path.relative_to(root).as_posix())
            if rel_path.startswith("tests/") or rel_path.startswith(".skills/"):
                continue
        except Exception:
            pass
        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                for line_idx, line in enumerate(f, 1):
                    for rule in SECRET_RULES:
                        match = rule["regex"].search(line)
                        if match:
                            findings.append(
                                Finding(
                                    check_type="secret",
                                    file_path=str(file_path.relative_to(root)),
                                    line_number=line_idx,
                                    description=f"{rule['name']} - {rule['description']}",
                                    severity=rule["severity"],
                                    match_str=match.group(0),
                                )
                            )
                            secret_findings_count += 1
        except Exception:
            continue

    # 2. Repository Hygiene Checks
    hygiene_failed = False
    hygiene_details = []

    # Verify .env ignored
    if not is_file_ignored(root, ".env"):
        findings.append(
            Finding(
                check_type="hygiene",
                file_path=".env",
                line_number=None,
                description=".env file is not ignored in .gitignore",
                severity="CRITICAL",
            )
        )
        hygiene_failed = True
        hygiene_details.append(".env not ignored")

    # Verify .seed ignored
    if not is_file_ignored(root, ".seed"):
        findings.append(
            Finding(
                check_type="hygiene",
                file_path=".seed",
                line_number=None,
                description=".seed directory is not ignored in .gitignore",
                severity="CRITICAL",
            )
        )
        hygiene_failed = True
        hygiene_details.append(".seed not ignored")

    # Scan for certificates and credential files
    cert_found_count = 0
    cred_found_count = 0
    for file_path in files:
        try:
            rel_path = str(file_path.relative_to(root).as_posix())
            if rel_path.startswith("tests/") or rel_path.startswith(".skills/"):
                continue
        except Exception:
            pass
        # Check certificates extension
        if file_path.suffix.lower() in CERT_EXTENSIONS:
            findings.append(
                Finding(
                    check_type="hygiene",
                    file_path=str(file_path.relative_to(root)),
                    line_number=None,
                    description=f"Certificate/key file found: {file_path.name}",
                    severity="HIGH",
                )
            )
            hygiene_failed = True
            cert_found_count += 1

        # Check credentials files
        if file_path.name.lower() in CRED_FILENAMES:
            findings.append(
                Finding(
                    check_type="hygiene",
                    file_path=str(file_path.relative_to(root)),
                    line_number=None,
                    description=f"Credential file found: {file_path.name}",
                    severity="CRITICAL",
                )
            )
            hygiene_failed = True
            cred_found_count += 1

    if hygiene_failed:
        if cert_found_count > 0:
            hygiene_details.append(f"{cert_found_count} certificate(s) found")
        if cred_found_count > 0:
            hygiene_details.append(f"{cred_found_count} credential file(s) found")

    # 3. Dangerous Code Scan
    dangerous_code_count = 0
    for file_path in files:
        if file_path.suffix.lower() != ".py":
            continue
        try:
            rel_path = str(file_path.relative_to(root).as_posix())
            if rel_path.startswith("tests/") or rel_path.startswith(".skills/"):
                continue
        except Exception:
            pass
        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                for line_idx, line in enumerate(f, 1):
                    for rule in DANGEROUS_CODE_RULES:
                        match = rule["regex"].search(line)
                        if match:
                            findings.append(
                                Finding(
                                    check_type="dangerous_code",
                                    file_path=str(file_path.relative_to(root)),
                                    line_number=line_idx,
                                    description=f"{rule['name']} - {rule['description']}",
                                    severity=rule["severity"],
                                    match_str=match.group(0),
                                )
                            )
                            dangerous_code_count += 1
        except Exception:
            continue

    # Compile result message
    secret_status = (
        f"[FAIL] ({secret_findings_count} secret(s) detected)"
        if any(f.check_type == "secret" for f in findings)
        else "[PASS] (No secrets detected)"
    )
    hygiene_status = (
        f"[FAIL] ({', '.join(hygiene_details)})"
        if hygiene_failed
        else "[PASS] (Healthy)"
    )
    dangerous_status = (
        f"[FAIL] ({dangerous_code_count} dangerous pattern(s) detected)"
        if dangerous_code_count > 0
        else "[PASS] (No dangerous code detected)"
    )

    message = (
        f"[1/3] Running Secret Scan...         {secret_status}\n"
        f"[2/3] Running Repository Hygiene...  {hygiene_status}\n"
        f"[3/3] Running Dangerous Code Scan... {dangerous_status}"
    )

    # Determine success (Only CRITICAL or HIGH fail the gate)
    success = not any(f.severity in ("CRITICAL", "HIGH") for f in findings)

    # Generate details
    details = []
    for f in findings:
        loc = f"{f.file_path}:{f.line_number}" if f.line_number else f.file_path
        details.append(
            f"[{f.severity}] {f.check_type.upper()}: {loc} - {f.description}"
        )

    return SecurityAuditResult(
        success=success,
        message=message,
        details=details,
    )
