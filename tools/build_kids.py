#!/usr/bin/env python3
"""Build the child-friendly firmware from an unmodified Apple image.

Every change is applied with Image.apply(), which refuses to run unless the
original bytes are exactly what this script expects. A different firmware
therefore fails instead of being silently corrupted.

Addresses are link addresses in the OS image. See docs/firmware-notes.md for
how each one was found.
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
from fwimage import Image  # noqa: E402

SUPPORTED_MD5 = "1cde5b94c5d94073b228760f36744bc6"

# WM8731 headphone register: 0x79 is 0 dB, one step is 1 dB, 0x2f is mute.
CODEC_0DB = 0x79
# Rockbox config of this project also limits to -12 dB.
DEFAULT_LIMIT_DB = 12

# Hauptmenue visibility bits, see the id -> bit switch at 0x684e4.
MENU_PLAYLISTS = 0x8000
MENU_ALBUMS = 0x0004

# Resource "Menu" 9490 (main menu): u32 count, then 40-byte entries.
MAIN_MENU = 0x19db00
MENU_ENTRY_SIZE = 40
ENTRY_CALENDARS = 13  # hidden by the visibility mask
ENTRY_SETTINGS = 16   # not covered by the mask, so it has to be replaced

# German language block.
GERMAN_BLOCK = 0x16d0f4
STRING_RENAMES = {
    0x2605: ("Wiedergabelisten", "Hörspiele"),
    0x25f5: ("Alben", "Musik"),
}

SLIDER_MAX_VIEW = 0x1af018  # max of Cntl 0x333e in View 9783


def ins(word):
    return struct.pack("<I", word)


def ui_volume_for(codec_reg):
    """Smallest slider value (0..0x100) that reaches the register value.

    The OS computes reg = 0x3e + 59 * (ui >> 1) // 121, see 0x14674c.
    """
    for ui in range(0, 0x101, 2):
        if 0x3e + 59 * (ui >> 1) // 121 >= codec_reg:
            return ui
    return 0x100


def patch_volume(img, limit_db):
    reg = CODEC_0DB - limit_db
    if not 0x30 <= reg <= 0x7f:
        raise ValueError("limit out of range")
    ui = ui_volume_for(reg)
    if ui >= 0x100:
        raise ValueError("limit too high for the slider patch")

    # Last clamp before the codec. Nothing can get past this one: no preference,
    # per-track gain or Sound Check reaches the chip without passing here.
    img.apply(0x146774, ins(0xe350007f), ins(0xe3500000 | reg))  # cmp r0,#reg
    img.apply(0x146778, ins(0x83a0007f), ins(0x83a00000 | reg))  # movhi r0,#reg

    # Rescale the slider so a full bar means the limit, without a dead zone.
    img.apply(0x075e40, ins(0xe3500f40), ins(0xe3500000 | ui))   # GetVolume clamp
    img.apply(0x075e44, ins(0x83a00f40), ins(0x83a00000 | ui))
    img.apply(0x0ec094, ins(0xe3a00f40), ins(0xe3a00000 | ui))   # slider model max
    img.apply(SLIDER_MAX_VIEW, ins(0x100), ins(ui))              # slider view max
    return reg, ui


def patch_menu(img):
    # Ignore the stored menu mask: mov r0,#0x8000 / orr r0,r0,#4 / mov pc,lr.
    mask = MENU_PLAYLISTS | MENU_ALBUMS
    img.apply(0x06cfa4, ins(0xe5900000), ins(0xe3a00c80))
    img.apply(0x06cfa8, ins(0xe5900b34), ins(0xe3800004))

    # Settings is always visible, so overwrite it with a hidden entry. Keeping
    # the entry count avoids disturbing anything that indexes this table.
    entry = lambda i: MAIN_MENU + 4 + i * MENU_ENTRY_SIZE
    start = img.payload_range()[0]
    hidden = bytes(img.data[start + entry(ENTRY_CALENDARS):
                            start + entry(ENTRY_CALENDARS) + MENU_ENTRY_SIZE])
    settings = bytes(img.data[start + entry(ENTRY_SETTINGS):
                              start + entry(ENTRY_SETTINGS) + MENU_ENTRY_SIZE])
    if struct.unpack_from("<H", settings, 20)[0] != 0xffbf:
        raise ValueError("main menu entry 16 is not Settings")
    img.apply(entry(ENTRY_SETTINGS), settings, hidden)
    return mask


def string_location(img, block, wanted_id):
    start = img.payload_range()[0] + block
    table_size, type_count = struct.unpack_from("<II", img.data, start + 4)
    for t in range(type_count):
        tag, count, _, offset = struct.unpack_from("<4sIII", img.data, start + 12 + t * 16)
        if tag[::-1] != b"Str ":
            continue
        for i in range(count):
            sid, off, length = struct.unpack_from("<III", img.data, start + offset + i * 12)
            if sid == wanted_id:
                return block + table_size + off, length
    raise KeyError(wanted_id)


def patch_strings(img):
    for sid, (old, new) in STRING_RENAMES.items():
        addr, length = string_location(img, GERMAN_BLOCK, sid)
        old_bytes = old.encode() + b"\0"
        new_bytes = new.encode() + b"\0"
        if len(new_bytes) > len(old_bytes) or len(old_bytes) > length:
            raise ValueError(f"string {sid:#x} does not fit")
        img.apply(addr, old_bytes, new_bytes.ljust(len(old_bytes), b"\0"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("firmware", help="unmodified Firmware-3.2.6.1 or Firmware-6.2.6.1")
    ap.add_argument("-o", "--output-dir", default="build")
    ap.add_argument("--limit-db", type=int, default=DEFAULT_LIMIT_DB,
                    help="maximum headphone level below 0 dB (default %(default)s)")
    args = ap.parse_args()

    img = Image(args.firmware)
    if img.md5 != SUPPORTED_MD5:
        sys.exit(f"unsupported firmware {img.md5}, expected {SUPPORTED_MD5}")

    original = bytes(img.data)
    reg, ui = patch_volume(img, args.limit_db)
    mask = patch_menu(img)
    patch_strings(img)
    img.fix_checksum()

    stored, computed = img.verify()
    if stored != computed:
        sys.exit("checksum mismatch after patching")

    os.makedirs(args.output_dir, exist_ok=True)
    fw_path = os.path.join(args.output_dir, "Firmware-kids")
    ipod_path = os.path.join(args.output_dir, "apple_os.ipod")
    with open(fw_path, "wb") as f:
        f.write(img.data)
    with open(ipod_path, "wb") as f:
        f.write(img.dot_ipod())

    changed = sum(a != b for a, b in zip(original, img.data))
    print(f"limit    -{args.limit_db} dB (codec register {reg:#x}, slider max {ui:#x})")
    print(f"menu     mask {mask:#x}: Hörspiele, Musik, Sie hören")
    print(f"changed  {changed} bytes, checksum {stored:#010x}")
    print(f"output   {fw_path}\n         {ipod_path}")


if __name__ == "__main__":
    main()
