#!/usr/bin/env python3
"""
Erfasst die freien Stellplaetze im Parkhaus Maastrichter Strasse (Koeln)
und haengt einen Messwert an daten/belegung_maastrichter.csv an.

Quelle 1: Offene Daten Koeln, Parkhausbelegung (JSON, Lizenz DL-DE-Zero-2.0)
Quelle 2 (Rueckfall): koeln.de, Parkhausseite Maastrichter Strasse
          (zeigt dieselben Daten aus dem Parkleitsystem an)
Nur Python-Standardbibliothek, keine Installation noetig.
"""
import csv
import json
import re
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Berlin")
CSV_DATEI = Path(__file__).parent / "daten" / "belegung_maastrichter.csv"
FELDER = ["abruf_zeit", "stand_quelle", "frei", "tendenz", "quelle", "status"]
MAX_ALTER = timedelta(hours=2)  # aeltere Quellstaende gelten als veraltet

URL_JSON = "https://www.stadt-koeln.de/externe-dienste/open-data/parking-ts.php"
URL_HTML = "https://www.koeln.de/apps/parken/parkhaus/maastrichter_strasse"
USER_AGENT = "Mozilla/5.0 (Datenerhebung Masterthesis TH Koeln, 15-Minuten-Takt)"


def holen(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as antwort:
        return antwort.read().decode("utf-8", errors="replace")


def zeit_lesen(text: str) -> datetime:
    for muster in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M"):
        try:
            return datetime.strptime(text.strip(), muster).replace(tzinfo=TZ)
        except ValueError:
            pass
    raise ValueError(f"Zeitstempel nicht lesbar: {text!r}")


def aus_json() -> dict:
    daten = json.loads(holen(URL_JSON))

    def suche(obj):
        if isinstance(obj, dict):
            klein = {str(k).lower(): v for k, v in obj.items()}
            if "maastricht" in str(klein.get("parkhaus", "")).lower():
                return klein
            obj = list(obj.values())
        if isinstance(obj, list):
            for wert in obj:
                treffer = suche(wert)
                if treffer:
                    return treffer
        return None

    eintrag = suche(daten)
    if not eintrag:
        raise ValueError("Maastrichter Strasse nicht im JSON gefunden")
    frei = int(eintrag.get("kapazitaet"))
    if frei < 0:
        raise ValueError("Quelle meldet -1 (keine Daten)")
    stand = zeit_lesen(str(eintrag.get("timestamp", "")))
    return {"stand": stand, "frei": frei,
            "tendenz": eintrag.get("tendenz", ""), "quelle": "offenedaten-koeln JSON"}


def aus_html() -> dict:
    text = re.sub(r"<[^>]+>", " ", holen(URL_HTML))
    text = re.sub(r"\s+", " ", text)
    frei = re.search(r"Aktuell frei:\s*(\d+)", text)
    stand = re.search(r"Stand vom\s*(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})", text)
    tendenz = re.search(r"Tendenz\s+([A-Za-zäöüÄÖÜß]+)", text)
    if not (frei and stand):
        raise ValueError("Werte auf koeln.de nicht gefunden (Seitenaufbau geaendert?)")
    return {"stand": zeit_lesen(stand.group(1)), "frei": int(frei.group(1)),
            "tendenz": tendenz.group(1) if tendenz else "", "quelle": "koeln.de"}


def main() -> None:
    jetzt = datetime.now(TZ)
    zeile = {"abruf_zeit": jetzt.strftime("%Y-%m-%d %H:%M")}
    fehler = []
    for abruf in (aus_json, aus_html):
        try:
            erg = abruf()
            if jetzt - erg["stand"] > MAX_ALTER:
                raise ValueError(f"Stand veraltet ({erg['stand']:%Y-%m-%d %H:%M})")
            zeile.update(stand_quelle=erg["stand"].strftime("%Y-%m-%d %H:%M"),
                         frei=erg["frei"], tendenz=erg["tendenz"],
                         quelle=erg["quelle"], status="ok")
            break
        except Exception as ex:  # naechste Quelle versuchen
            fehler.append(f"{abruf.__name__}: {ex}")
    else:
        zeile["status"] = ("fehler: " + " | ".join(fehler))[:300]

    CSV_DATEI.parent.mkdir(parents=True, exist_ok=True)
    neu = not CSV_DATEI.exists()
    with CSV_DATEI.open("a", newline="", encoding="utf-8") as f:
        schreiber = csv.DictWriter(f, fieldnames=FELDER)
        if neu:
            schreiber.writeheader()
        schreiber.writerow({k: zeile.get(k, "") for k in FELDER})
    print(zeile)


if __name__ == "__main__":
    main()
