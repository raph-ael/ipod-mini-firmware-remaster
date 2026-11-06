#!/usr/bin/env python3
"""Build the iPod database for the kids firmware.

For now this handles a small sample: selected files are copied below
iPod_Control/Music and everything else stays where it is.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

import mutagen

HERE = os.path.dirname(os.path.abspath(__file__))
KIDSDB = os.path.join(HERE, "kidsdb")
AUDIOBOOKS = "Hörspiele"
MUSIC = "Musik"
GENRE_AUDIOBOOK = "Hörspiel"

# The firmware skips this exact prefix without checking it and keeps only the
# next 35 bytes of the path, see docs/firmware-notes.md.
PATH_PREFIX = ":iPod_Control:Music:"
MAX_RELATIVE_PATH = 35


def clean_tag(text):
    """Undo the underscores left over from file name sanitising."""
    text = re.sub(r"(?<=\w)_s\b", "'s", text)
    text = text.replace("_ ", ", ")
    return re.sub(r"\s+_|_\s+|_$", " ", text).strip()


def audiobook_title(stem):
    """'001 Hexen gibt es doch' -> (1, '001 - Hexen gibt es doch')."""
    m = re.match(r"(\d+)\s+(.+)", stem)
    if m:
        return int(m.group(1)), f"{m.group(1)} - {m.group(2)}"
    m = re.match(r"Band\s+(\d+)", stem)
    return (int(m.group(1)) if m else 0), stem


def describe(path, name, category, folder, ipod_path):
    """One database row. `name` is the original file name, `path` may be a copy."""
    audio = mutagen.File(path, easy=True)
    if audio is None:
        raise ValueError(f"not an audio file: {path}")
    stem = os.path.splitext(name)[0]
    tags = audio.tags or {}
    first = lambda key: tags.get(key, [""])[0]

    if category == AUDIOBOOKS:
        number, title = audiobook_title(stem)
        artist, album, genre, playlist, is_book = folder, "", GENRE_AUDIOBOOK, folder, 1
    else:
        number = int(re.match(r"\d*", first("tracknumber")).group() or 0)
        title = clean_tag(first("title") or stem)
        artist = clean_tag(first("artist"))
        album, genre, playlist, is_book = clean_tag(first("album") or folder), first("genre"), "", 0

    return [ipod_path, title, artist, album, genre, number, 0,
            int(audio.info.length * 1000), int(audio.info.bitrate / 1000),
            audio.info.sample_rate, os.path.getsize(path), is_book, playlist]


def sample(mount, spec):
    """Yield (source, category, folder) for 'Category/Folder:count' entries."""
    for item in spec:
        where, _, count = item.rpartition(":")
        category, folder = where.split("/", 1)
        names = sorted(n for n in os.listdir(os.path.join(mount, where))
                       if n.lower().endswith(".mp3"))
        for name in names[:int(count)]:
            yield os.path.join(mount, where, name), category, folder


def copy_sample(mount, spec):
    target = os.path.join(mount, "iPod_Control", "Music", "F00")
    rows = []
    for index, (source, category, folder) in enumerate(sample(mount, spec), 1):
        relative = f"F00:K{index:04d}.mp3"
        if len(relative) > MAX_RELATIVE_PATH:
            raise ValueError(f"path too long for the firmware: {relative}")
        dest = os.path.join(target, f"K{index:04d}.mp3")
        if not os.path.exists(dest) or os.path.getsize(dest) != os.path.getsize(source):
            shutil.copyfile(source, dest + ".tmp")
            os.replace(dest + ".tmp", dest)
        rows.append(describe(dest, os.path.basename(source), category, folder,
                             PATH_PREFIX + relative))
    return rows


def write_database(mount, rows):
    text = "".join("\t".join(str(v) for v in row) + "\n" for row in rows)
    subprocess.run([KIDSDB, mount], input=text, text=True, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mount")
    ap.add_argument("sample", nargs="+", help="e.g. 'Hörspiele/Bibi Blocksberg:4'")
    args = ap.parse_args()
    if not os.path.isdir(os.path.join(args.mount, "iPod_Control")):
        sys.exit("no iPod_Control folder at this mount point")
    write_database(args.mount, copy_sample(args.mount, args.sample))


if __name__ == "__main__":
    main()
