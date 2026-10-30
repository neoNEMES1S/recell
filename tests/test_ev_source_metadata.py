"""OSF inventory pagination must stay on the declared metadata service."""

import json

import pytest

from second_life_battery.data import osf as module


def test_listing_preserves_all_pages_and_pins_source(tmp_path, monkeypatch):
    url = "https://api.osf.io/v2/example/?page%5Bsize%5D=100"
    next_url = url + "&page=2"
    payloads = {
        url: {"data": [{"id": "a"}], "links": {"next": next_url}},
        next_url: {"data": [{"id": "b"}], "links": {"next": None}},
    }
    seen = []

    def fetch(target):
        seen.append(target)
        return json.dumps(payloads[target]).encode()

    monkeypatch.setattr(module, "fetch_page", fetch)
    output = tmp_path / "listing.json"
    result = module.inspect_listing(url, output)
    assert [row["id"] for row in result["data"]] == ["a", "b"]
    assert len(result["pages"]) == 2
    assert module.inspect_listing(url, output) == result
    assert seen == [url, next_url]
    with pytest.raises(ValueError, match="different source"):
        module.inspect_listing(next_url, output)


@pytest.mark.parametrize(
    "destination", ["https://example.com/", "https://api.osf.io/v2/example/?page%5Bsize%5D=100"]
)
def test_redirected_or_repeated_pagination_rejected(tmp_path, monkeypatch, destination):
    payload = {"data": [], "links": {"next": destination}}
    monkeypatch.setattr(module, "fetch_page", lambda *a, **k: json.dumps(payload).encode())
    with pytest.raises(ValueError):
        module.inspect_listing(
            "https://api.osf.io/v2/example/?page%5Bsize%5D=100", tmp_path / "listing.json"
        )
    assert not (tmp_path / "listing.json").exists()


def test_transient_metadata_timeout_is_retried(tmp_path, monkeypatch):
    calls = []

    def fetch(*args, **kwargs):
        calls.append(args)
        if len(calls) < 3:
            raise TimeoutError("temporary service delay")
        return json.dumps({"data": [], "links": {"next": None}}).encode()

    monkeypatch.setattr(module, "fetch_page", fetch)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    assert (
        module.inspect_listing(
            "https://api.osf.io/v2/example/?page%5Bsize%5D=100", tmp_path / "list.json"
        )["data"]
        == []
    )
    assert len(calls) == 3


def test_interrupted_pagination_resumes_verified_pages(tmp_path, monkeypatch):
    url = "https://api.osf.io/v2/example/?page%5Bsize%5D=100"
    second = url + "&page=2"
    output = tmp_path / "listing.json"
    calls = []

    def interrupted(target):
        calls.append(target)
        if target == second:
            raise TimeoutError("interrupted")
        return json.dumps({"data": [{"id": "a"}], "links": {"next": second}}).encode()

    monkeypatch.setattr(module, "fetch_page", interrupted)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    with pytest.raises(TimeoutError):
        module.inspect_listing(url, output)
    assert not output.exists()
    assert calls.count(url) == 1
    calls.clear()

    def finish(target):
        calls.append(target)
        return json.dumps({"data": [{"id": "b"}], "links": {"next": None}}).encode()

    monkeypatch.setattr(module, "fetch_page", finish)
    result = module.inspect_listing(url, output)
    assert calls == [second]
    assert [row["id"] for row in result["data"]] == ["a", "b"]
