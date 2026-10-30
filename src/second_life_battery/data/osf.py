"""Pinned paginated metadata from the OSF public dataset API."""

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def fetch_page(url: str) -> bytes:
    """Use the same bounded transport that works for the provider's file downloads."""
    result = subprocess.run(
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--connect-timeout",
            "10",
            "--max-time",
            "90",
            "--max-filesize",
            str(10 * 1024 * 1024),
            url,
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ConnectionError(f"OSF metadata curl exit {result.returncode}")
    return result.stdout


def inspect_listing(url: str, output: Path) -> dict:
    """Pin folder metadata locally and validate every pagination destination."""
    if output.exists():
        cached = json.loads(output.read_text())
        if cached.get("source_url") != url:
            raise ValueError("Cached OSF listing belongs to a different source URL")
        return cached
    records, pages, seen = [], [], set()
    page_cache = output.with_suffix(".pages.json")
    saved = json.loads(page_cache.read_text()) if page_cache.exists() else {}
    if saved and saved.get("source_url") != url:
        raise ValueError("Cached OSF pages belong to a different source URL")
    cached_pages = {page["url"]: page for page in saved.get("pages", [])}
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    if not {"page", "page[size]"} & {key for key, _ in query}:
        # Verified against this release: OSF accepts up to 100 records per page.
        query.append(("page[size]", "100"))
    next_url = urlunsplit(parts._replace(query=urlencode(query)))
    while next_url:
        target = urlsplit(next_url)
        if target.scheme != "https" or target.hostname != "api.osf.io":
            raise ValueError("Only HTTPS OSF metadata links may be followed")
        if next_url in seen or len(seen) >= 100:
            raise ValueError("Repeated or excessive OSF pagination")
        seen.add(next_url)
        for attempt in range(3):
            try:
                if next_url in cached_pages:
                    content = bytes.fromhex(cached_pages[next_url]["content_hex"])
                    if hashlib.sha256(content).hexdigest() != cached_pages[next_url]["sha256"]:
                        raise ValueError("Cached OSF metadata page changed")
                else:
                    content = fetch_page(next_url)
                break
            except (ConnectionError, TimeoutError):
                if attempt == 2:
                    raise
            time.sleep(attempt + 1)
        if len(content) > 10 * 1024 * 1024:
            raise ValueError("OSF metadata response exceeded 10 MB")
        page = json.loads(content)
        if not isinstance(page.get("data"), list):
            raise ValueError("Expected an OSF folder listing")
        records.extend(page["data"])
        cached_pages[next_url] = {
            "url": next_url,
            "sha256": hashlib.sha256(content).hexdigest(),
            "content_hex": content.hex(),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        partial = page_cache.with_suffix(".json.part")
        partial.write_text(json.dumps({"source_url": url, "pages": list(cached_pages.values())}))
        partial.replace(page_cache)
        pages.append(
            {"url": next_url, "sha256": hashlib.sha256(content).hexdigest(), "response": page}
        )
        next_url = page.get("links", {}).get("next")
    result = {
        "source_url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "data": records,
        "pages": pages,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    return result
