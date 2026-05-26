"""Push bytes to S3 for a previously created upload session.

This is the missing primitive between ``courses uploads create`` (which
returns presigned URLs) and ``courses uploads complete`` (which seals
the version once every PUT has landed).  Without it, authors had to
write their own ``curl``/``requests`` loop against the presigned URLs.

Design notes
------------
- The handler is intentionally a *primitive*: it does not call ``create``
  or ``complete``.  Composing the three is the job of a higher-level
  ``publish`` workflow.  Keeping each step a primitive lets agents
  retry exactly the file that failed without re-issuing presigned URLs
  or sealing a half-uploaded version.
- The session JSON is whatever ``create_upload_session`` returns.  The
  caller can pass it via ``--session-file PATH`` or ``--session-file -``
  to read from stdin.
- Local files are located via the same ``--file [PATH=]LOCAL`` syntax
  as ``uploads create`` for consistency.  The ``PATH`` half is matched
  against each session entry's ``filename``.
- Network failures are surfaced as exit code 6 with a per-file
  breakdown so the caller can re-run with only the failed files.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from cli._errors import print_err, validate_uuid_id

from .uploads import _resolve_upload_files

# Exit codes used by ``handle_uploads_push``.
EXIT_OK = 0
EXIT_BAD_ARGS = 2
EXIT_SESSION_MISMATCH = 3
EXIT_MISSING_FILES = 4
EXIT_UPLOAD_FAILED = 6

DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT_S = 60.0


def _read_session(path: str) -> dict[str, Any] | None:
    """Load the upload-session JSON from *path* (``-`` for stdin)."""
    try:
        raw = (
            sys.stdin.read()
            if path == "-"
            else Path(path).read_text(encoding="utf-8")
        )
    except OSError as exc:
        print_err(f"could not read session file: {exc}")
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print_err(f"session file is not valid JSON: {exc}")
        return None
    if not isinstance(data, dict):
        print_err("session JSON must be an object")
        return None
    return data


def _put_one(
    upload: dict[str, Any],
    local_path: Path,
    max_retries: int,
    timeout: float,
) -> tuple[bool, str]:
    """PUT *local_path* to ``upload['put_url']`` with retries.

    Returns ``(success, message)``.  Retries on transient httpx
    errors and HTTP 5xx; aborts immediately on 4xx (presigned URL
    rejected — usually a content-length / header mismatch).
    """
    import httpx

    url = upload.get("put_url")
    headers = upload.get("required_headers") or {}
    if not isinstance(url, str) or not url:
        return False, "missing put_url"

    last_err = ""
    for attempt in range(max_retries + 1):
        try:
            with local_path.open("rb") as fh:
                response = httpx.request(
                    upload.get("method", "PUT"),
                    url,
                    content=fh,
                    headers=headers,
                    timeout=timeout,
                )
        except httpx.RequestError as exc:
            last_err = f"network error: {exc}"
        else:
            if 200 <= response.status_code < 300:
                return True, f"HTTP {response.status_code}"
            if 400 <= response.status_code < 500:
                # Client errors won't recover on retry.
                return False, (
                    f"HTTP {response.status_code}: {response.text[:200]}"
                )
            last_err = f"HTTP {response.status_code}"
        if attempt < max_retries:
            # Linear backoff is enough — presigned URLs are short-lived.
            time.sleep(0.5 * (attempt + 1))
    return False, last_err or "exhausted retries"


def _build_filename_map(
    file_specs: list[str],
) -> dict[str, Path] | None:
    """Resolve --file specs to a ``{upload_path: local_path}`` map."""
    resolved = _resolve_upload_files(file_specs)
    if resolved is None:
        return None
    return dict(resolved)


def _validate_session_ids(
    session: dict[str, Any],
    course_id: str,
    version_id: str,
) -> bool:
    """Refuse to push if the session is for a different course/version."""
    s_course = str(session.get("course_id", ""))
    s_version = str(session.get("version_id", ""))
    if s_course and s_course != course_id:
        print_err(
            f"session is for course {s_course}, "
            f"but command was invoked with {course_id}"
        )
        return False
    if s_version and s_version != version_id:
        print_err(
            f"session is for version {s_version}, "
            f"but command was invoked with {version_id}"
        )
        return False
    return True


def _prepare_push(
    args: argparse.Namespace,
) -> tuple[int, list[dict[str, Any]] | None, dict[str, Path] | None]:
    """Validate args + session and return ``(rc, uploads, file_map)``.

    On any validation failure the returned ``rc`` is non-zero and the
    other two values are ``None``.  Split out of ``handle_uploads_push``
    purely to keep the handler under the project's cyclomatic-complexity
    budget — the logic is otherwise sequential.
    """
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id, None, None
    bad_id = validate_uuid_id(args.version_id, "VERSION_ID")
    if bad_id is not None:
        return bad_id, None, None
    if not args.files:
        print_err("Error: at least one --file is required")
        return EXIT_BAD_ARGS, None, None
    session = _read_session(args.session_file)
    if session is None:
        return EXIT_BAD_ARGS, None, None
    if not _validate_session_ids(session, args.course_id, args.version_id):
        return EXIT_SESSION_MISMATCH, None, None
    file_map = _build_filename_map(args.files)
    if file_map is None:
        return EXIT_BAD_ARGS, None, None
    uploads = session.get("uploads") or []
    if not isinstance(uploads, list) or not uploads:
        print_err("session has no uploads to push")
        return EXIT_BAD_ARGS, None, None
    missing = [
        u.get("filename")
        for u in uploads
        if isinstance(u, dict) and u.get("filename") not in file_map
    ]
    if missing:
        print_err(
            "no local file provided for: " + ", ".join(str(m) for m in missing)
        )
        return EXIT_MISSING_FILES, None, None
    return EXIT_OK, uploads, file_map


def _emit_results(
    results: list[dict[str, Any]],
    failures: int,
    json_output: bool,
) -> None:
    if json_output:
        print(
            json.dumps(
                {"results": results, "failures": failures},
                indent=2,
                sort_keys=True,
            )
        )
        return
    for r in results:
        status = "OK" if r["ok"] else "FAIL"
        print(f"  [{status}] {r['filename']}: {r['detail']}")
    print(f"Pushed {len(results) - failures}/{len(results)} files.")


def handle_uploads_push(args: argparse.Namespace) -> int:
    """Push every file in the upload session to its presigned URL."""
    rc, uploads, file_map = _prepare_push(args)
    if rc != EXIT_OK or uploads is None or file_map is None:
        return rc

    results: list[dict[str, Any]] = []
    failures = 0
    # COMMON_PARSER leaves --max-retries / --timeout as None when the
    # caller omits them; fall back to push-specific defaults.
    max_retries = (
        args.max_retries
        if args.max_retries is not None
        else DEFAULT_MAX_RETRIES
    )
    timeout = args.timeout if args.timeout is not None else DEFAULT_TIMEOUT_S
    for upload in uploads:
        filename = upload.get("filename", "")
        local = file_map[filename]
        ok, msg = _put_one(upload, local, max_retries, timeout)
        results.append({"filename": filename, "ok": ok, "detail": msg})
        if not ok:
            failures += 1

    _emit_results(results, failures, getattr(args, "json_output", False))
    return EXIT_OK if failures == 0 else EXIT_UPLOAD_FAILED
