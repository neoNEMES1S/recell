"""A partial ZIP download must retain exact range, release and member integrity."""

import importlib.util
import io
import struct
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

spec = importlib.util.spec_from_file_location(
    "acquire_iblend", Path(__file__).resolve().parents[1] / "scripts/acquire_iblend.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_range_must_match_release_and_requested_bytes():
    header = 'HTTP/1.1 206 Partial Content\r\nContent-Range: bytes 10-19/100\r\nETag: "pinned"\r\n'
    module.check_range(header, 10, 19, 100, "pinned")
    with pytest.raises(ValueError, match="exact requested"):
        module.check_range(header, 0, 9, 100, "pinned")
    with pytest.raises(ValueError, match="ETag"):
        module.check_range(header, 10, 19, 100, "changed")


def test_selected_member_crc_and_name_are_verified(tmp_path):
    stream = io.BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("energy_dataset/Readme.txt", "timestamp is UNIX; power is watts")
    data = stream.getvalue()
    with ZipFile(io.BytesIO(data)) as archive:
        info = archive.getinfo("energy_dataset/Readme.txt")
    row = {"name": info.filename, "bytes": info.file_size, "crc32": info.CRC}
    fields = struct.unpack("<4s5H3I2H", data[:30])
    start = 30 + fields[-2] + fields[-1]
    compressed = tmp_path / "compressed.bin"
    compressed.write_bytes(data[start : start + info.compress_size])
    result = module.extract_member(tmp_path, row, data[:4096], compressed)
    assert (tmp_path / "Readme.txt").read_text() == "timestamp is UNIX; power is watts"
    assert result["upstream_member_crc32"] == info.CRC
    with pytest.raises(ValueError, match="size/CRC"):
        module.extract_member(tmp_path, {**row, "crc32": 0}, data[:4096], compressed)
    with pytest.raises(ValueError, match="central directory"):
        module.extract_member(tmp_path, {**row, "name": "other.txt"}, data[:4096], compressed)
