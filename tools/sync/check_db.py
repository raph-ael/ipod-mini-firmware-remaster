#!/usr/bin/env python3
"""Check an iTunesDB against the rules of the firmware parser at 0xb095c."""
import struct
import sys

PREFIX = ":iPod_Control:Music:"
MAX_RELATIVE_PATH = 35


def main():
    data = open(sys.argv[1], "rb").read()
    errors = []

    def need(condition, message):
        if not condition:
            errors.append(message)

    tag, header, total, unk, version, children = struct.unpack_from("<4sIIIII", data, 0)
    need(tag == b"mhbd", "file does not start with mhbd")
    need(total == len(data), f"mhbd length {total} is not the file size {len(data)}")
    need(unk <= 1, f"mhbd field 0x0c is {unk}, the parser rejects values above 1")
    need(children > 0, "no child data sets")
    print(f"mhbd version {version:#x}, {children} data sets, {len(data)} bytes")

    offset = header
    tracks = 0
    audiobooks = 0
    playlists_seen = False
    for _ in range(children):
        tag, header, total, kind = struct.unpack_from("<4sIII", data, offset)
        need(tag == b"mhsd", f"expected mhsd at {offset:#x}")
        print(f"  mhsd type {kind}, {total} bytes")
        if kind == 1:
            pos = offset + header
            _, lt_header, count = struct.unpack_from("<4sII", data, pos)
            pos += lt_header
            for _ in range(count):
                t_tag, t_header, t_total, mhods = struct.unpack_from("<4sIII", data, pos)
                need(t_tag == b"mhit", f"expected mhit at {pos:#x}")
                need(t_header >= 0xf4, f"mhit header {t_header:#x} is too small")
                visible = struct.unpack_from("<I", data, pos + 0x14)[0]
                need(visible == 1, f"track at {pos:#x} is not visible")
                bookmark_flag = data[pos + 0xa6]
                audiobooks += bookmark_flag != 0
                sub = pos + t_header
                path = None
                for _ in range(mhods):
                    m_tag, m_header, m_total, m_type = struct.unpack_from("<4sIII", data, sub)
                    need(m_tag == b"mhod", f"expected mhod at {sub:#x}")
                    if m_type == 2:
                        length = struct.unpack_from("<I", data, sub + 28)[0]
                        path = data[sub + 40:sub + 40 + length].decode("utf-16-le")
                    sub += m_total
                need(path is not None, f"track at {pos:#x} has no path")
                if path:
                    need(path.startswith(PREFIX), f"bad path prefix: {path}")
                    need(len(path) - len(PREFIX) <= MAX_RELATIVE_PATH, f"path too long: {path}")
                    need(path.isascii(), f"path is not ASCII: {path}")
                tracks += 1
                pos += t_total
        if kind in (2, 3) and not playlists_seen:
            playlists_seen = True
            pos = offset + header
            _, lp_header, count = struct.unpack_from("<4sII", data, pos)
            pos += lp_header
            for i in range(count):
                p_tag, p_header, p_total, mhods, items = struct.unpack_from("<4sIIII", data, pos)
                need(p_tag == b"mhyp", f"expected mhyp at {pos:#x}")
                master = data[pos + 0x14]
                need((i == 0) == bool(master), "the master playlist must come first")
                print(f"    playlist {i}: {items} tracks, master={master}")
                pos += p_total
        offset += total

    print(f"{tracks} tracks, {audiobooks} with remember flag")
    for error in errors:
        print("ERROR", error)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
