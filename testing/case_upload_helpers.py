"""
Shared helper for driving Case Mode's upload-based folder picker from tests.

/case/start and /case/<job_id>/rescan no longer accept a server-side `folder_path` — case folders
are uploaded from the browser's own native folder picker (<input type="file" webkitdirectory>,
see case.js/app.js), each file's path relative to the picked folder preserved via
`file.webkitRelativePath` as the multipart part's filename (matches the browser's own
`body.append("files", file, file.webkitRelativePath)` call exactly). This builds the same shape of
request directly, without a browser actually performing a file-picker click, since Playwright's
`page.request` layer talks HTTP directly and has no access to real OS file dialogs.
"""
import json
import urllib.request
from pathlib import Path

from playwright.sync_api import FormData


def list_case_files(folder: Path) -> list:
    """Every file under `folder` (recursively) as (relative_filename, content_bytes) pairs, the
    relative_filename including `folder`'s own top-level name — the plain-data form both the
    Playwright-based and urllib-based builders below share."""
    top_name = folder.name
    return [
        (f"{top_name}/{p.relative_to(folder).as_posix()}", p.read_bytes())
        for p in sorted(folder.rglob("*")) if p.is_file()
    ]


def build_multipart_bytes(fields: dict, files: list) -> tuple:
    """Raw multipart/form-data body builder for scripts that drive the app with plain `urllib`
    rather than Playwright's request context (e.g. a long-running script polling status without
    needing a browser at all for that part). `fields` are plain text parts; `files` is a list of
    (filename, content_bytes) all sent under the "files" field name, matching what case.js's
    appendFilesToFormData actually sends. Returns (body_bytes, content_type_header_value)."""
    boundary = "----lfaCaseUploadBoundary"
    parts = []
    for name, value in fields.items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode("utf-8")
        )
    for filename, content in files:
        header = (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"files\"; filename=\"{filename}\"\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8")
        parts.append(header + content + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def urllib_start_case(app_url: str, plaintiff_name: str, folder: Path, priority_hint: str = "",
                       detail_level: str = "standard", timeout: float = 60) -> str:
    """Plain-urllib equivalent of start_case() below, for scripts with no Playwright `page`."""
    fields = {"plaintiff_name": plaintiff_name, "priority_hint": priority_hint, "detail_level": detail_level}
    body, content_type = build_multipart_bytes(fields, list_case_files(folder))
    req = urllib.request.Request(
        f"{app_url}/case/start", data=body, method="POST", headers={"Content-Type": content_type},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if "error" in data:
        raise RuntimeError(f"/case/start failed: {data['error']}")
    return data["job_id"]


def build_case_files_formdata(folder: Path) -> FormData:
    """One FormData with a "files" entry per file under `folder` (recursively), each carrying its
    path relative to `folder`'s OWN PARENT (i.e. including the picked folder's own top-level name)
    as its filename — exactly what a real webkitRelativePath looks like for a folder named
    `folder.name` picked via the browser's native dialog."""
    fd = FormData()
    for filename, content in list_case_files(folder):
        mime = "application/pdf" if filename.lower().endswith(".pdf") else "application/octet-stream"
        fd.append("files", {"name": filename, "mimeType": mime, "buffer": content})
    return fd


def start_case(page, app_url: str, plaintiff_name: str, folder: Path, priority_hint: str = "",
               detail_level: str = "standard") -> str:
    """POSTs /case/start with `folder`'s files uploaded as though picked via the native folder
    picker. Returns the new job_id, raising an AssertionError with the server's error message if
    the request didn't succeed."""
    fd = build_case_files_formdata(folder)
    fd.set("plaintiff_name", plaintiff_name)
    fd.set("priority_hint", priority_hint)
    fd.set("detail_level", detail_level)
    resp = page.request.post(f"{app_url}/case/start", multipart=fd)
    data = resp.json()
    assert "job_id" in data, f"case/start failed: {data}"
    return data["job_id"]


def rescan_case(page, app_url: str, job_id: str, folder: Path):
    """POSTs /case/<job_id>/rescan with `folder`'s CURRENT files uploaded, as though the reviewer
    re-picked the same folder via the native picker after adding files to it. Returns the raw
    APIResponse (not just its json) so callers can check status codes for the failure-path tests
    (e.g. a rescan attempted with no files at all)."""
    fd = build_case_files_formdata(folder)
    return page.request.post(f"{app_url}/case/{job_id}/rescan", multipart=fd)
