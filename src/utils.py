"""Shared safety and formatting helpers."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SENSITIVE_QUERY_KEYS = {"authkey", "auth_key", "token", "cookie"}


def mask_secret(value: str, visible: int = 6) -> str:
    """Mask a secret while leaving a small prefix/suffix for identification."""
    if not value:
        return ""
    if len(value) <= visible * 2:
        return "*" * len(value)
    return f"{value[:visible]}{'*' * 8}{value[-visible:]}"


def sanitize_url(url: str) -> str:
    """Return a URL safe for display or logs."""
    try:
        parts = urlsplit(url)
        sanitized = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            if key.lower() in SENSITIVE_QUERY_KEYS:
                value = mask_secret(value)
            sanitized.append((key, value))
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(sanitized), parts.fragment)
        )
    except Exception:
        return "<invalid URL>"


def redact_authkey(text: str) -> str:
    """Best-effort redaction for exception messages before they reach the UI."""
    if not text:
        return text
    return re.sub(
        r"(?i)(authkey(?:=|%3D))([^&\s]+)",
        lambda match: f"{match.group(1)}<REDACTED>",
        str(text),
    )

