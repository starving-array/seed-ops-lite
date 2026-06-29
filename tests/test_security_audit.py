"""Unit tests for the Security Audit quality gate scans."""

from pathlib import Path
from unittest.mock import patch

from security_audit import run_security_audit


def test_secret_scan_pem_key(tmp_path: Path) -> None:
    """Verify detection of PEM private keys."""
    # Write a dummy PEM private key file
    pem_file = tmp_path / "private.pem"
    pem_file.write_text(
        "-----BEGIN RSA PRIVATE KEY-----\nMOCK_KEY_DATA\n-----END RSA PRIVATE KEY-----",
        encoding="utf-8",
    )

    with (
        patch("security_audit.get_repo_root", return_value=tmp_path),
        patch(
            "security_audit.is_file_ignored", return_value=True
        ),  # mock hygiene checks pass
    ):
        result = run_security_audit()

    assert result.success is False  # PEM Key is CRITICAL
    assert "PEM Key" in "".join(result.details)
    assert "private.pem" in result.message or "private.pem" in "".join(result.details)


def test_secret_scan_aws_key_id(tmp_path: Path) -> None:
    """Verify detection of AWS Access Key IDs."""
    aws_file = tmp_path / "aws_creds.py"
    aws_file.write_text("aws_id = 'AKIA1234567890ABCDEF'", encoding="utf-8")

    with (
        patch("security_audit.get_repo_root", return_value=tmp_path),
        patch("security_audit.is_file_ignored", return_value=True),
    ):
        result = run_security_audit()

    assert result.success is False  # AWS Key ID is CRITICAL
    assert "AWS Key ID" in "".join(result.details)


def test_secret_scan_aws_secret_key(tmp_path: Path) -> None:
    """Verify detection of AWS Secret Access Keys."""
    aws_file = tmp_path / "aws_creds.py"
    aws_file.write_text(
        "aws_secret_access_key = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'",
        encoding="utf-8",
    )

    with (
        patch("security_audit.get_repo_root", return_value=tmp_path),
        patch("security_audit.is_file_ignored", return_value=True),
    ):
        result = run_security_audit()

    assert result.success is False  # AWS Secret Access Key is CRITICAL
    assert "AWS Secret Access Key" in "".join(result.details)


def test_secret_scan_jwt_secret(tmp_path: Path) -> None:
    """Verify detection of JWT secrets."""
    jwt_file = tmp_path / "config.py"
    jwt_file.write_text(
        "token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c'",
        encoding="utf-8",
    )

    with (
        patch("security_audit.get_repo_root", return_value=tmp_path),
        patch("security_audit.is_file_ignored", return_value=True),
    ):
        result = run_security_audit()

    assert result.success is False  # JWT is HIGH
    assert "JWT Secret" in "".join(result.details)


def test_secret_scan_bearer_token(tmp_path: Path) -> None:
    """Verify detection of Bearer tokens."""
    bearer_file = tmp_path / "api.py"
    bearer_file.write_text("auth = 'Bearer abc123XYZ_token-value'", encoding="utf-8")

    with (
        patch("security_audit.get_repo_root", return_value=tmp_path),
        patch("security_audit.is_file_ignored", return_value=True),
    ):
        result = run_security_audit()

    assert result.success is False  # Bearer is HIGH
    assert "Bearer Token" in "".join(result.details)


def test_secret_scan_api_key(tmp_path: Path) -> None:
    """Verify detection of generic API keys."""
    api_file = tmp_path / "api.py"
    api_file.write_text("api_key = 'secret_token_12345'", encoding="utf-8")

    with (
        patch("security_audit.get_repo_root", return_value=tmp_path),
        patch("security_audit.is_file_ignored", return_value=True),
    ):
        result = run_security_audit()

    assert result.success is False  # API Key is HIGH
    assert "API Key" in "".join(result.details)


def test_secret_scan_ignores_env_file(tmp_path: Path) -> None:
    """Verify that secret scan ignores the .env file contents."""
    env_file = tmp_path / ".env"
    env_file.write_text("AKIA1234567890ABCDEF", encoding="utf-8")

    with (
        patch("security_audit.get_repo_root", return_value=tmp_path),
        patch("security_audit.is_file_ignored", return_value=True),
    ):
        result = run_security_audit()

    # Even though .env has an AWS Key ID, secret scan ignores .env.
    # So secret scan status will be PASS.
    assert "No secrets detected" in result.message


def test_hygiene_env_not_ignored(tmp_path: Path) -> None:
    """Verify failure when .env file is not ignored by git check-ignore."""
    with (
        patch("security_audit.get_repo_root", return_value=tmp_path),
        patch(
            "security_audit.is_file_ignored",
            side_effect=lambda _, name: name != ".env",
        ),
    ):
        result = run_security_audit()

    assert result.success is False
    assert ".env not ignored" in result.message


def test_hygiene_seed_not_ignored(tmp_path: Path) -> None:
    """Verify failure when .seed directory is not ignored by git check-ignore."""
    with (
        patch("security_audit.get_repo_root", return_value=tmp_path),
        patch(
            "security_audit.is_file_ignored",
            side_effect=lambda _, name: name != ".seed",
        ),
    ):
        result = run_security_audit()

    assert result.success is False
    assert ".seed not ignored" in result.message


def test_hygiene_certificate_files(tmp_path: Path) -> None:
    """Verify detection of certificate files."""
    cert_file = tmp_path / "cert.crt"
    cert_file.write_text("cert", encoding="utf-8")

    with (
        patch("security_audit.get_repo_root", return_value=tmp_path),
        patch("security_audit.is_file_ignored", return_value=True),
    ):
        result = run_security_audit()

    assert result.success is False  # Certificates are HIGH severity
    assert "Certificate/key file found" in "".join(result.details)


def test_hygiene_credential_files(tmp_path: Path) -> None:
    """Verify detection of credential files."""
    cred_file = tmp_path / "secrets.json"
    cred_file.write_text("{}", encoding="utf-8")

    with (
        patch("security_audit.get_repo_root", return_value=tmp_path),
        patch("security_audit.is_file_ignored", return_value=True),
    ):
        result = run_security_audit()

    assert result.success is False  # Credentials are CRITICAL severity
    assert "Credential file found" in "".join(result.details)


def test_dangerous_code_scan(tmp_path: Path) -> None:
    """Verify detection of dangerous python code patterns."""
    dangerous_patterns = [
        ("eval_test.py", "eval('x')"),
        ("exec_test.py", "exec('x')"),
        ("pickle_test.py", "pickle.loads(x)"),
        ("yaml_test.py", "yaml.load(x)"),
        ("subprocess_test.py", "subprocess.run(cmd, shell=True)"),
    ]

    for filename, code in dangerous_patterns:
        file = tmp_path / filename
        file.write_text(code, encoding="utf-8")

    with (
        patch("security_audit.get_repo_root", return_value=tmp_path),
        patch("security_audit.is_file_ignored", return_value=True),
    ):
        result = run_security_audit()

    assert result.success is False
    details_str = "".join(result.details)
    assert "eval()" in details_str
    assert "exec()" in details_str
    assert "pickle.loads()" in details_str
    assert "yaml.load()" in details_str
    assert "shell=True" in details_str
