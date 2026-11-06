# Notizen zur Firmware 1.4.1 (iPod mini)

Alle Adressen sind Link-Adressen im OS-Image. Die Angaben gelten nur für die
Datei mit md5 `1cde5b94c5d94073b228760f36744bc6`, also `Firmware-3.2.6.1` und
das bytegleiche `Firmware-6.2.6.1`.

## Image-Format

| Offset in der Datei | Inhalt |
| --- | --- |
| `0x0100` | Magic `]ih[`, Verzeichnis-Offset, Formatversion 3 |
| `0x4200` | Image-Verzeichnis, 40 Byte pro Eintrag |
| `0x4400` | `devOffset` von `osos`, ein Sektor ohne Bedeutung fürs Laden |
| `0x4600` | erstes Byte des OS, wird nach `0x10000000` geladen |

Die Prüfsumme im Verzeichnis ist die Bytesumme des OS, mod 2^32. Sie stimmt für
die Images der Familien 3, 6 und 7 sowie für einen Dump von einem echten Gerät.
Eine Signatur gibt es auf diesem Pfad nicht. `ipodpatcher` nutzt das auch.

Das OS ist auf Adresse 0 gelinkt, der DRAM wird dorthin gemappt. ARM-Code liegt
in `0–0x160000` und ab `0x320000`, dazwischen Daten.

## UI-Ressourcen

Der Container bei `0x19260c` enthält die Typen `BMap`, `LDTm`, `Menu`, `Str `,
`TCmd`, `Type` und `View`. Aufbau: Version, Tabellengröße, Anzahl Typen, dann pro
Typ Tag, Anzahl, Reserviert, Offset der Eintragstabelle. Einträge sind
`(id, offset, länge)`, IDs sind vorzeichenbehaftet, die Daten beginnen bei
`Container + Tabellengröße`.

Die Sprachen liegen in gleich aufgebauten Blöcken, Basistabelle bei `0x318074`.
Deutsch ist `0x16d0f4`. `TCmd` ist Bytecode für eine kleine VM, die die UI-Logik
ausführt. `tools/dump_resources.py` listet alle Menüs.

## Hauptmenü

Menü 9490 hat 21 Einträge. Sichtbar ist ein Eintrag, wenn sein Bit in der Maske
gesetzt ist. Die Abbildung ID → Bit steht bei `0x684e4`, der Werkszustand ist
`0x81201` (Musik, Extras, Backlight, Shuffle). Die Maske liegt im Einstellungsfeld
`0xb34`, gelesen wird sie über `0x6cfa4`. Direkt greifen nur das Laden und
Speichern der Preferences darauf zu.

"Einstellungen" und "Sie hören" haben kein Bit und lassen sich nicht ausblenden.
Das Bytecode-Skript blendet Einträge über ihre ID aus und trifft dabei offenbar nur
den ersten Treffer: Eine Kopie von "Kalender" an der Stelle von "Einstellungen" blieb
am Gerät sichtbar. Der Build entfernt den Eintrag deshalb aus der Tabelle.

## Lautstärke

1. Der Slider ist `Cntl 0x333e` in View 9783, Bereich `0..0x100`.
2. Die Einstellung ist `0x27d4` im Namensraum `0x2780`. Beim Lesen klemmt
   `0x75e1c` auf `0x100`.
3. `0xa3cf4` übernimmt Wert und Balance, `0xa2690` rechnet die Track-Anpassung ein
   und kappt auf `0x200`.
4. `0xd5278` übergibt `Wert >> 1`, maximal `0x7f`.
5. Ab `0x14673c` entsteht das Register des Codecs:
   `reg = 0x3e + 59 * v / 121 + trim`, Mute ist `0x2f`, geklemmt auf `0x7f`.

Beim WM8731 ist `0x79` genau 0 dB und jede Stufe 1 dB. Die Skala ist also
dB-linear. Von den 20 direkten Aufrufen der Codec-Schreibfunktion `0x157128`
schreibt nur `0x1467d0` einen variablen Wert in dieses Register, zwei weitere
schreiben feste Stummwerte. Die Klemme bei `0x146774` greift daher immer.

## Titel und iTunesDB

Der Parser beginnt bei `0xb095c`. Er verlangt, dass die Gesamtlänge im `mhbd`-Header
der Dateigröße entspricht. Von `mhsd` Typ 2 und 3 liest er nur den ersten.

`0xa6608` speichert den Dateipfad eines Titels: Er überspringt die ersten 20 Zeichen,
ohne sie zu prüfen, und übernimmt vom Rest höchstens 35 Byte. `0xd5650` setzt beim
Öffnen wieder `iPod_Control\Music\` davor. Titel müssen also unter diesem Ordner liegen.

Byte `0xA6` im `mhit`-Header wird beim Parsen gelesen. `0xa25c4` behandelt einen Titel
mit gesetztem Flag wie eine `.m4b`-Datei.

## Rockbox als sichere Testumgebung

Der Rockbox-Bootloader lädt bei Hold oder Menu zuerst `/.rockbox/apple_os.ipod`.
Das erlaubt Tests, ohne die Firmware-Partition zu ändern. Die Datei besteht aus
Prüfsumme (big endian, `modelnum + Bytesumme`), Modellname und OS. Für den mini 1G
gilt `mini` und 9, für den mini 2G wären es `mn2g` und 11.

## Reproduzieren

`tools/ghidra/ExportAll.java` exportiert Listing und Dekompilat. Import als Raw
Binary, ARM v4t, Basis 0, der OS-Teil beginnt bei Datei-Offset `0x4600`.
