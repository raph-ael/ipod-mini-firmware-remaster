# iPod mini Firmware Remaster

Patcht die Apple-Firmware 1.4.1 des iPod mini zu einer kinderfreundlichen Version.
Das Repo enthält nur eigene Werkzeuge. **Apple-Firmware gehört nicht hierher**, sie
muss aus einem eigenen Restore-Image kommen.

## Was der Build ändert

| Bereich | Änderung |
| --- | --- |
| Lautstärke | Hartes Limit bei −12 dB im letzten Schritt vor dem Codec, voller Balken entspricht dem Limit |
| Hauptmenü | Nur noch Hörspiele, Musik und Sie hören |
| Einstellungen | Nicht mehr erreichbar, damit auch kein Zurücksetzen und keine Sprachumstellung |
| Texte | „Wiedergabelisten" wird zu „Hörspiele", „Alben" wird zu „Musik" |

Insgesamt ändern sich 46 Byte. Der Build bricht ab, wenn die Firmware nicht exakt
die erwartete Datei ist.

## Status

Statisch geprüft, **noch nicht auf einem Gerät getestet**. Lautstärkekurve,
Menüfilter und Bootverhalten stammen aus der Analyse, nicht aus einer Messung.

Offen:

- Test auf dem Gerät
- Erzeugen einer `iTunesDB` aus den vorhandenen MP3s, ohne die zeigt das OS keine Titel
- Weiterhören an der letzten Stelle für Hörspiele

## Bauen

```sh
python3 tools/build_kids.py /pfad/zu/Firmware-3.2.6.1 -o build
```

Das ergibt `build/apple_os.ipod` zum Testen und `build/Firmware-kids` für die
Firmware-Partition. Mit `--limit-db 18` lässt sich das Limit ändern.

## Sicher testen

Auf einem Gerät mit Rockbox-Bootloader ändert dieser Test die Firmware-Partition nicht:

1. `build/apple_os.ipod` nach `/.rockbox/apple_os.ipod` kopieren.
2. Hold einschalten und den iPod starten. Das lädt die gepatchte Firmware.
3. Ohne Hold startet weiter Rockbox. Zum Rückbau die Datei löschen.

`Firmware-kids` erst auf die Firmware-Partition schreiben, wenn dieser Test
durchgelaufen ist. Eine dort abstürzende Firmware erfordert unter Umständen, den
iPod zu öffnen und die Karte im Lesegerät zurückzuschreiben.

## Falls nur Rockbox zuverlässig starten soll

Der Rockbox-Bootloader startet Apple OS, wenn beim Einschalten Hold aktiv ist oder
Menu gedrückt wird. Das lässt sich ohne Firmware-Änderung abstellen:

1. `/.rockbox/rockbox.ipod` nach `/.rockbox/apple_os.ipod` kopieren.
2. In `/.rockbox/config.cfg` die Zeile `clear settings on hold: off` ergänzen.

Punkt 2 ist nötig, weil Rockbox sonst bei aktivem Hold seine Einstellungen zurücksetzt.

## Werkzeuge

- `tools/fwimage.py`: Image lesen, prüfen, patchen
- `tools/build_kids.py`: alle Patches anwenden
- `tools/dump_resources.py`: Menüs und Strings auflisten
- `tools/ghidra/ExportAll.java`: Ghidra-Export
- `docs/firmware-notes.md`: Format und Fundstellen
