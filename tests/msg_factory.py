"""
Generate valid Outlook .msg files for testing.

Builds the OLE2/CFBF (Compound File Binary Format) container from scratch,
writing the MAPI property streams that extract_msg expects. No external
dependencies beyond the standard library.

Reference: MS-OXMSG specification
https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-oxmsg/
"""

import math
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# MAPI property type and ID constants
# ---------------------------------------------------------------------------

PT_LONG = 0x0003
PT_SYSTIME = 0x0040
PT_UNICODE = 0x001F
PT_BINARY = 0x0102

PID_MESSAGE_CLASS = 0x001A
PID_SUBJECT = 0x0037
PID_CLIENT_SUBMIT_TIME = 0x0039
PID_SENDER_NAME = 0x0C1A
PID_SENDER_EMAIL = 0x0C1F
PID_DISPLAY_CC = 0x0E03
PID_DISPLAY_TO = 0x0E04
PID_MESSAGE_DELIVERY = 0x0E06
PID_BODY = 0x1000
PID_HTML = 0x1013
PID_INTERNET_MESSAGE_ID = 0x1035
PID_STORE_SUPPORT_MASK = 0x340D

PROP_FLAGS = 0x06  # READABLE | WRITABLE
STORE_UNICODE_OK = 0x00040000

# CFBF constants
SECTOR_SIZE = 512
MINI_SECTOR_SIZE = 64
MINI_STREAM_CUTOFF = 0x1000
DIR_ENTRY_SIZE = 128
ENDOFCHAIN = 0xFFFFFFFE
FREESECT = 0xFFFFFFFF
FAT_SECT = 0xFFFFFFFD

# Windows FILETIME epoch
_FILETIME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# MAPI property helpers
# ---------------------------------------------------------------------------

def _prop_tag(prop_id: int, prop_type: int) -> int:
    return (prop_id << 16) | prop_type


def _stream_name(prop_id: int, prop_type: int) -> str:
    return f"__substg1.0_{_prop_tag(prop_id, prop_type):08X}"


def _to_filetime(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int((dt - _FILETIME_EPOCH).total_seconds() * 10_000_000)


def _fixed_entry(prop_id: int, prop_type: int, value: bytes) -> bytes:
    tag = _prop_tag(prop_id, prop_type)
    return struct.pack("<II", tag, PROP_FLAGS) + value.ljust(8, b"\x00")[:8]


def _variable_entry(prop_id: int, prop_type: int, data: bytes) -> bytes:
    tag = _prop_tag(prop_id, prop_type)
    size = len(data) + (2 if prop_type == PT_UNICODE else 0)
    return struct.pack("<IIII", tag, PROP_FLAGS, size, 0)


# ---------------------------------------------------------------------------
# Build logical streams for a message
# ---------------------------------------------------------------------------

def _build_streams(
    *,
    subject: str,
    body: str,
    sender_name: str,
    sender_email: str,
    to: str,
    cc: str,
    message_id: str,
    date: datetime,
    html_body: Optional[bytes],
) -> dict[str, bytes]:
    """Return {stream_name: data} for the .msg OLE2 container."""
    streams: dict[str, bytes] = {}
    entries: list[bytes] = []

    # -- fixed-length properties (stored inside __properties_version1.0) --
    ft = _to_filetime(date)
    entries.append(_fixed_entry(PID_STORE_SUPPORT_MASK, PT_LONG, struct.pack("<I", STORE_UNICODE_OK)))
    entries.append(_fixed_entry(PID_CLIENT_SUBMIT_TIME, PT_SYSTIME, struct.pack("<Q", ft)))
    entries.append(_fixed_entry(PID_MESSAGE_DELIVERY, PT_SYSTIME, struct.pack("<Q", ft)))

    # -- variable-length properties (each gets its own stream) --
    def _add_unicode(pid: int, value: str) -> None:
        if not value:
            return  # skip empty — zero-length OLE streams confuse extract_msg
        encoded = value.encode("utf-16-le")
        streams[_stream_name(pid, PT_UNICODE)] = encoded
        entries.append(_variable_entry(pid, PT_UNICODE, encoded))

    _add_unicode(PID_MESSAGE_CLASS, "IPM.Note")
    _add_unicode(PID_SUBJECT, subject)
    _add_unicode(PID_BODY, body)
    _add_unicode(PID_SENDER_NAME, sender_name)
    _add_unicode(PID_SENDER_EMAIL, sender_email)
    _add_unicode(PID_DISPLAY_TO, to)
    _add_unicode(PID_DISPLAY_CC, cc)
    _add_unicode(PID_INTERNET_MESSAGE_ID, message_id)

    if html_body:
        name = _stream_name(PID_HTML, PT_BINARY)
        streams[name] = html_body
        entries.append(_variable_entry(PID_HTML, PT_BINARY, html_body))

    # 32-byte top-level header + property entries
    header = struct.pack("<QIIIIQ", 0, 0, 0, 0, 0, 0)
    streams["__properties_version1.0"] = header + b"".join(entries)
    return streams


# ---------------------------------------------------------------------------
# CFBF writer — the minimum viable OLE2 container
# ---------------------------------------------------------------------------

def _pad(data: bytes, boundary: int = SECTOR_SIZE) -> bytes:
    r = len(data) % boundary
    return data + b"\x00" * (boundary - r) if r else data


def _dir_entry(
    name: str,
    etype: int,
    start: int = ENDOFCHAIN,
    size: int = 0,
    child: int = 0xFFFFFFFF,
    left: int = 0xFFFFFFFF,
    right: int = 0xFFFFFFFF,
) -> bytes:
    raw = bytearray(128)
    encoded = name.encode("utf-16-le")[:62]
    raw[: len(encoded)] = encoded
    struct.pack_into("<H", raw, 64, min(len(encoded) + 2, 64))
    raw[66] = etype
    raw[67] = 1  # black
    struct.pack_into("<I", raw, 68, left)
    struct.pack_into("<I", raw, 72, right)
    struct.pack_into("<I", raw, 76, child)
    struct.pack_into("<I", raw, 116, start)
    struct.pack_into("<Q", raw, 120, size)
    return bytes(raw)


def _write_cfbf(path: str, streams: dict[str, bytes]) -> None:
    """Pack *streams* into a valid CFBF (OLE2) file at *path*."""
    names = sorted(streams.keys())

    # Separate mini (<4 KiB) vs regular streams
    mini, regular = {}, {}
    for n in names:
        (mini if len(streams[n]) < MINI_STREAM_CUTOFF else regular)[n] = streams[n]

    # Build mini-stream container (all mini data concatenated, 64-byte aligned)
    mini_blob = b""
    mini_offsets: dict[str, int] = {}
    for n in names:
        if n in mini:
            mini_offsets[n] = len(mini_blob)
            mini_blob += mini[n].ljust(
                math.ceil(len(mini[n]) / MINI_SECTOR_SIZE) * MINI_SECTOR_SIZE, b"\x00"
            )

    total_mini_sectors = len(mini_blob) // MINI_SECTOR_SIZE
    mini_container_sects = math.ceil(len(mini_blob) / SECTOR_SIZE) if mini_blob else 0
    mini_fat_sects = math.ceil(total_mini_sectors * 4 / SECTOR_SIZE) if total_mini_sectors else 0

    reg_sects_map: dict[str, int] = {}
    total_reg_sects = 0
    for n in names:
        if n in regular:
            s = math.ceil(len(regular[n]) / SECTOR_SIZE)
            reg_sects_map[n] = s
            total_reg_sects += s

    dir_sects = math.ceil((1 + len(names)) * DIR_ENTRY_SIZE / SECTOR_SIZE)

    # Iteratively determine FAT size
    data_sects = dir_sects + mini_container_sects + mini_fat_sects + total_reg_sects
    ents_per_fat = SECTOR_SIZE // 4
    fat_sects = 1
    for _ in range(5):
        fat_sects = max(1, math.ceil((fat_sects + data_sects) / ents_per_fat))

    total = fat_sects + data_sects

    # Assign sector IDs
    cur = fat_sects
    dir_start = cur;         cur += dir_sects
    mc_start = cur if mini_container_sects else ENDOFCHAIN;  cur += mini_container_sects
    mf_start = cur if mini_fat_sects else ENDOFCHAIN;        cur += mini_fat_sects

    reg_starts: dict[str, int] = {}
    for n in names:
        if n in regular:
            reg_starts[n] = cur
            cur += reg_sects_map[n]

    # Build FAT
    fat = [FREESECT] * (fat_sects * ents_per_fat)
    for i in range(fat_sects):
        fat[i] = FAT_SECT

    def _chain(start: int, count: int) -> None:
        for i in range(count):
            fat[start + i] = start + i + 1 if i + 1 < count else ENDOFCHAIN

    _chain(dir_start, dir_sects)
    if mini_container_sects:
        _chain(mc_start, mini_container_sects)
    if mini_fat_sects:
        _chain(mf_start, mini_fat_sects)
    for n in names:
        if n in regular:
            _chain(reg_starts[n], reg_sects_map[n])

    fat_bytes = b"".join(struct.pack("<I", e) for e in fat[:total])
    fat_bytes = fat_bytes.ljust(fat_sects * SECTOR_SIZE, b"\xff")

    # Build mini-FAT
    mfat_bytes = b""
    if total_mini_sectors:
        mfat: list[int] = []
        for n in names:
            if n in mini:
                ns = math.ceil(len(mini[n]) / MINI_SECTOR_SIZE)
                for j in range(ns):
                    mfat.append(len(mfat) + 1 if j + 1 < ns else ENDOFCHAIN)
        mfat_bytes = b"".join(struct.pack("<I", e) for e in mfat)
        mfat_bytes = mfat_bytes.ljust(mini_fat_sects * SECTOR_SIZE, b"\xff")

    # Build directory — balanced binary tree
    def _build_tree(lst: list[str], out: list[dict]) -> int:
        if not lst:
            return 0xFFFFFFFF
        mid = len(lst) // 2
        n = lst[mid]
        idx = len(out) + 1  # +1 for Root
        out.append({"name": n, "left": 0xFFFFFFFF, "right": 0xFFFFFFFF})
        pos = len(out) - 1
        out[pos]["left"] = _build_tree(lst[:mid], out)
        out[pos]["right"] = _build_tree(lst[mid + 1:], out)
        return idx

    tree: list[dict] = []
    root_child = _build_tree(names, tree) if names else 0xFFFFFFFF

    dir_bytes = _dir_entry("Root Entry", 5, mc_start, len(mini_blob), root_child)
    for t in tree:
        n = t["name"]
        if n in mini:
            s_start = mini_offsets[n] // MINI_SECTOR_SIZE
        elif n in regular:
            s_start = reg_starts[n]
        else:
            s_start = ENDOFCHAIN
        dir_bytes += _dir_entry(n, 2, s_start, len(streams[n]), left=t["left"], right=t["right"])
    dir_bytes = dir_bytes.ljust(dir_sects * SECTOR_SIZE, b"\x00")

    # Build header
    hdr = bytearray(512)
    hdr[0:8] = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
    struct.pack_into("<H", hdr, 24, 0x003E)
    struct.pack_into("<H", hdr, 26, 0x0003)
    struct.pack_into("<H", hdr, 28, 0xFFFE)
    struct.pack_into("<H", hdr, 30, 9)
    struct.pack_into("<H", hdr, 32, 6)
    struct.pack_into("<I", hdr, 44, fat_sects)
    struct.pack_into("<I", hdr, 48, dir_start)
    struct.pack_into("<I", hdr, 56, MINI_STREAM_CUTOFF)
    struct.pack_into("<I", hdr, 60, mf_start if mini_fat_sects else ENDOFCHAIN)
    struct.pack_into("<I", hdr, 64, mini_fat_sects)
    struct.pack_into("<I", hdr, 68, ENDOFCHAIN)
    struct.pack_into("<I", hdr, 72, 0)
    for i in range(109):
        struct.pack_into("<I", hdr, 76 + i * 4, i if i < fat_sects else FREESECT)

    with open(path, "wb") as f:
        f.write(bytes(hdr))
        f.write(fat_bytes)
        f.write(dir_bytes)
        if mini_container_sects:
            f.write(_pad(mini_blob))
        if mini_fat_sects:
            f.write(mfat_bytes)
        for n in names:
            if n in regular:
                f.write(_pad(regular[n]))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def make_msg(
    path: str | Path,
    *,
    message_id: str = "<test@example.com>",
    subject: str = "Test Subject",
    body: str = "Hello, this is a test email.",
    sender_name: str = "Sender",
    sender_email: str = "sender@example.com",
    to: str = "inbox@company.com",
    cc: str = "",
    date: Optional[datetime] = None,
    html_body: Optional[bytes] = None,
) -> Path:
    """
    Create a valid Outlook .msg file at *path*.

    The generated file is parseable by ``extract_msg.Message``.
    Returns the Path to the created file.
    """
    if date is None:
        date = datetime(2026, 2, 17, 10, 0, 0, tzinfo=timezone.utc)

    streams = _build_streams(
        subject=subject,
        body=body,
        sender_name=sender_name,
        sender_email=sender_email,
        to=to,
        cc=cc,
        message_id=message_id,
        date=date,
        html_body=html_body,
    )
    p = Path(path)
    _write_cfbf(str(p), streams)
    return p
