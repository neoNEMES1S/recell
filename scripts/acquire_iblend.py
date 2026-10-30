"""Acquire only documented non-residential I-BLEND members using verified byte ranges."""

import json
import re
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path

from second_life_battery.data.inventory import sha256_file

URL = "https://ndownloader.figshare.com/files/10797959"


def check_range(headers, start, end, size, etag):
    ranges = re.findall(r"(?im)^content-range:\s*bytes (\d+)-(\d+)/(\d+)\s*$", headers)
    tags = re.findall(r'(?im)^etag:\s*"([^"\r\n]+)"\s*$', headers)
    if not ranges or tuple(map(int, ranges[-1])) != (start, end, size):
        raise ValueError("Provider did not return the exact requested archive range")
    if not tags or tags[-1] != etag:
        raise ValueError("Remote archive ETag differs from the published release checksum")


def get_range(raw, start, end, size, etag):
    cache = raw / "ranges"
    cache.mkdir(exist_ok=True, parents=True)
    path = cache / f"{start}-{end}.bin"
    receipt = path.with_suffix(".receipt.json")
    if path.exists() and receipt.exists():
        pin = json.loads(receipt.read_text())
        if pin["sha256"] != sha256_file(path) or pin["archive_etag"] != etag:
            raise ValueError("Pinned byte range changed")
        return path
    partial = path.with_suffix(".part")
    with tempfile.TemporaryDirectory(prefix="recell-range-") as folder:
        headers = Path(folder) / "headers.txt"
        for attempt in range(3):
            result = subprocess.run(
                [
                    "curl",
                    "--fail",
                    "--location",
                    "--silent",
                    "--show-error",
                    "--connect-timeout",
                    "30",
                    "--max-time",
                    "900",
                    "--range",
                    f"{start}-{end}",
                    "--max-filesize",
                    str(end - start + 1),
                    "--dump-header",
                    str(headers),
                    URL,
                    "--output",
                    str(partial),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                break
            print(
                json.dumps(
                    {
                        "retry_range": [start, end],
                        "attempt": attempt + 1,
                        "curl_exit": result.returncode,
                    }
                ),
                flush=True,
            )
        else:
            raise ConnectionError("Bounded I-BLEND range download failed")
        check_range(headers.read_text(), start, end, size, etag)
    if partial.stat().st_size != end - start + 1:
        raise ValueError("Incomplete I-BLEND byte range")
    partial.replace(path)
    receipt.write_text(
        json.dumps(
            {
                "url": URL,
                "start": start,
                "end": end,
                "archive_bytes": size,
                "archive_etag": etag,
                "sha256": sha256_file(path),
            },
            indent=2,
        )
        + "\n"
    )
    return path


def extract_member(raw, row, header, compressed):
    signature, _, flags, method, _, _, _, _, _, name_len, extra_len = struct.unpack(
        "<4s5H3I2H", header[:30]
    )
    if signature != b"PK\x03\x04" or flags & 1 or method != 8:
        raise ValueError("Unsupported or encrypted ZIP member")
    name = header[30 : 30 + name_len].decode("utf-8")
    if name != row["name"] or 30 + name_len + extra_len > len(header):
        raise ValueError("Local ZIP header differs from pinned central directory")
    destination = raw / Path(name).name
    temporary = destination.with_suffix(destination.suffix + ".part")
    decoder, count, crc = zlib.decompressobj(-15), 0, 0
    with compressed.open("rb") as source, temporary.open("wb") as output:
        for chunk in iter(lambda: source.read(65536), b""):
            data = decoder.decompress(chunk)
            count += len(data)
            if count > row["bytes"] or count > 200 * 1024**2:
                raise ValueError("ZIP member exceeds declared size or acquisition budget")
            crc = zlib.crc32(data, crc)
            output.write(data)
        data = decoder.flush()
        count += len(data)
        crc = zlib.crc32(data, crc)
        output.write(data)
    if not decoder.eof or count != row["bytes"] or crc != row["crc32"]:
        raise ValueError("Selected ZIP member failed size/CRC integrity checks")
    temporary.replace(destination)
    return {
        "member": name,
        "path": str(destination),
        "bytes": count,
        "sha256": sha256_file(destination),
        "upstream_member_crc32": crc,
    }


def acquire(root):
    audit = root / "outputs/india_ci/source_audit"
    raw = root / "data/raw/india_iblend"
    raw.mkdir(parents=True, exist_ok=True)
    metadata_path = audit / "iblend_metadata.json"
    directory_path = audit / "iblend_remote_directory.json"
    metadata, directory = [json.loads(p.read_text()) for p in (metadata_path, directory_path)]
    source = metadata["files"][0]
    if source["download_url"] != URL or source["size"] != directory["source_archive_bytes"]:
        raise ValueError("Pinned I-BLEND release metadata differs")
    size, etag = source["size"], source["computed_md5"]
    results = []
    for name in [
        "energy_dataset/Readme.txt",
        "energy_dataset/acad_build_mains.csv",
        "energy_dataset/data_present_status_buildings.csv",
    ]:
        row = next(r for r in directory["members"] if r["name"] == name)
        if row["compressed_bytes"] > 60 * 1024**2 or row["bytes"] > 200 * 1024**2:
            raise ValueError("Selected member exceeds the acquisition budget")
        start = row["header_offset"]
        header_path = get_range(raw, start, start + 4095, size, etag)
        header = header_path.read_bytes()
        fields = struct.unpack("<4s5H3I2H", header[:30])
        data_start = start + 30 + fields[-2] + fields[-1]
        compressed = get_range(
            raw, data_start, data_start + row["compressed_bytes"] - 1, size, etag
        )
        result = extract_member(raw, row, header, compressed)
        result["compressed_range"] = [data_start, data_start + row["compressed_bytes"] - 1]
        results.append(result)
        (audit / "iblend_selected_receipt.json").write_text(
            json.dumps(
                {
                    "doi": metadata["doi"],
                    "version": metadata["version"],
                    "license": metadata["license"],
                    "metadata_sha256": sha256_file(metadata_path),
                    "directory_sha256": sha256_file(directory_path),
                    "archive_etag": etag,
                    "integrity_basis": (
                        "Exact HTTP 206 ranges, matching published archive ETag, member CRC32 "
                        "and local SHA256; full archive MD5 not recomputed"
                    ),
                    "members": results,
                    "status": "selected_members_acquiring; semantic_audit_pending",
                },
                indent=2,
            )
            + "\n"
        )
        print(json.dumps(result), flush=True)
    receipt = audit / "iblend_selected_receipt.json"
    saved = json.loads(receipt.read_text())
    saved["status"] = "selected_members_verified; semantic_audit_pending"
    receipt.write_text(json.dumps(saved, indent=2) + "\n")
    return results


if __name__ == "__main__":
    acquire(Path(__file__).resolve().parent.parent)
