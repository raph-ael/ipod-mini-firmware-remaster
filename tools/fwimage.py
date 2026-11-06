#!/usr/bin/env python3
"""Read, patch and rebuild iPod mini 1G/2G firmware images (version-3 layout).

Layout, verified against Firmware-3.2.6.1 / Firmware-6.2.6.1 (build 1.4.1):

  0x0000  ASCII banner, 0x100: "]ih[" magic, directory offset, format version
  0x4200  image directory, 40 bytes per entry
  0x4400  'osos' devOffset; the payload starts one sector later (0x4600)

The boot ROM validates the OS with a plain 32-bit sum of the payload bytes,
stored in the directory entry. There is no signature on this path.
"""
import argparse
import hashlib
import struct
import sys

DIR_OFFSET = 0x4200
ENTRY_SIZE = 40
SECTOR = 0x200

# md5 of the only input this tool has been verified against.
KNOWN_FIRMWARE = {
    "1cde5b94c5d94073b228760f36744bc6": "iPod mini 1G/2G, build 1.4.1 (updater family 3 and 6)",
}


class Image:
    def __init__(self, path):
        self.data = bytearray(open(path, "rb").read())
        self.md5 = hashlib.md5(self.data).hexdigest()

    def entry(self, tag):
        """Return (directory offset, devOffset, length, checksum) for an image tag."""
        for i in range(8):
            off = DIR_OFFSET + i * ENTRY_SIZE
            if bytes(self.data[off + 4:off + 8]) == tag[::-1]:
                dev_off, length = struct.unpack_from("<II", self.data, off + 12)
                checksum = struct.unpack_from("<I", self.data, off + 28)[0]
                return off, dev_off, length, checksum
        raise KeyError(tag)

    def payload_range(self, tag=b"osos"):
        _, dev_off, length, _ = self.entry(tag)
        start = dev_off + SECTOR
        return start, start + length

    def os_payload(self):
        start, end = self.payload_range()
        return bytes(self.data[start:end])

    def verify(self):
        off, _, _, stored = self.entry(b"osos")
        computed = sum(self.os_payload()) & 0xFFFFFFFF
        return stored, computed

    def apply(self, addr, expected, replacement):
        """Patch the OS at link address `addr`, refusing to run on unexpected bytes."""
        if len(expected) != len(replacement):
            raise ValueError("patches must keep the length")
        start, end = self.payload_range()
        pos = start + addr
        if pos + len(expected) > end:
            raise ValueError(f"patch at {addr:#x} is outside the OS image")
        found = bytes(self.data[pos:pos + len(expected)])
        if found != expected:
            raise ValueError(f"patch at {addr:#x}: found {found.hex()}, expected {expected.hex()}")
        self.data[pos:pos + len(replacement)] = replacement

    def fix_checksum(self):
        off = self.entry(b"osos")[0]
        struct.pack_into("<I", self.data, off + 28, sum(self.os_payload()) & 0xFFFFFFFF)

    def dot_ipod(self, model_name=b"mini", model_num=9):
        """Serialise the OS as a Rockbox `.ipod` file (header + raw payload).

        The Rockbox bootloader loads this from /.rockbox/apple_os.ipod, which is
        how a build can be tested without touching the firmware partition.
        """
        payload = self.os_payload()
        checksum = (model_num + sum(payload)) & 0xFFFFFFFF
        return struct.pack(">I", checksum) + model_name + payload


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("firmware")
    args = ap.parse_args()
    img = Image(args.firmware)
    stored, computed = img.verify()
    print(f"md5      {img.md5} ({KNOWN_FIRMWARE.get(img.md5, 'UNKNOWN - not verified')})")
    print(f"checksum stored {stored:#010x} computed {computed:#010x} "
          f"{'OK' if stored == computed else 'MISMATCH'}")
    sys.exit(0 if stored == computed else 1)


if __name__ == "__main__":
    main()
