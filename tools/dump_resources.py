#!/usr/bin/env python3
"""List the UI resources of an iPod mini firmware image.

The OS keeps its menus, views and strings as data in one resource container.
This prints them in readable form, which is how the patch targets were found.
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
from fwimage import Image  # noqa: E402

BASE_CONTAINER = 0x19260c
MENU_ENTRY_SIZE = 40


def signed(value):
    return value - (1 << 32) if value >= 1 << 31 else value


def read_container(data, base):
    table_size, type_count = struct.unpack_from("<II", data, base + 4)
    resources = {}
    for t in range(type_count):
        tag, count, _, offset = struct.unpack_from("<4sIII", data, base + 12 + t * 16)
        entries = []
        for i in range(count):
            rid, off, length = struct.unpack_from("<III", data, base + offset + i * 12)
            entries.append((signed(rid), base + table_size + off, length))
        resources[tag[::-1].decode("latin1")] = entries
    return resources


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("firmware")
    args = ap.parse_args()

    data = Image(args.firmware).os_payload()
    res = read_container(data, BASE_CONTAINER)
    print({tag: len(entries) for tag, entries in res.items()})

    strings = {}
    for rid, addr, length in res["Str "]:
        strings[rid] = data[addr:addr + length].split(b"\0")[0].decode("utf8", "replace")

    def text(sid):
        return strings.get(sid - 65536 if sid >= 32768 else sid, "?")

    for rid, addr, _ in res["Menu"]:
        count = struct.unpack_from("<I", data, addr)[0]
        print(f"\nMenu {rid} at {addr:#x}, {count} entries")
        for i in range(count):
            f = struct.unpack_from("<10I", data, addr + 4 + i * MENU_ENTRY_SIZE)
            sid = f[5] & 0xffff
            print(f"  [{i:2}] {text(sid)!r:24} text={sid:#06x} script={f[3]:#06x} "
                  f"accessory={f[6]:#06x}/{f[7]:#06x}")


if __name__ == "__main__":
    main()
