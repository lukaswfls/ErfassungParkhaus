#!/usr/bin/env python3
"""
Wertet daten/belegung_maastrichter.csv aus.
Ergebnis: auswertung/auswertung_maastrichter.xlsx und zwei Diagramme (PNG).

Methodik:
- Doppelte Quellstaende (gleicher Zeitstempel der Quelle) werden entfernt.
- Messwerte werden zu Stundenmitteln zusammengefasst. Das gleicht unregelmaessige
  Abrufabstaende aus; jede Stunde geht mit gleichem Gewicht in den Wochenmittelwert ein.
- Auslastung = (Bezugskapazitaet - frei) / Bezugskapazitaet.
"""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Setzung: Das Parkleitsystem zaehlt vermutlich nur die Kurzparkerplaetze
# (koeln.de: 684 gesamt / 450 Kurzparker). Vom Verfasser zu pruefen.
KAPAZITAET = 450

BASIS = Path(__file__).parent
ZIEL = BASIS / "auswertung"
ZIEL.mkdir(exist_ok=True)
TAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

roh = pd.read_csv(BASIS / "daten" / "belegung_maastrichter.csv")
ok = roh[roh["status"] == "ok"].copy()
ok["zeit"] = pd.to_datetime(ok["stand_quelle"])
ok = ok.drop_duplicates("zeit").sort_values("zeit")
ok["belegt"] = KAPAZITAET - ok["frei"]
ok["auslastung_pct"] = ok["belegt"] / KAPAZITAET * 100

std = ok.set_index("zeit")[["frei", "belegt", "auslastung_pct"]].resample("1h").mean().dropna()
std["wochentag"] = [TAGE[d] for d in std.index.dayofweek]
std["stunde"] = std.index.hour

kennwerte = pd.DataFrame({
    "Kennwert": [
        "Erhebungszeitraum von", "Erhebungszeitraum bis", "Abrufe gesamt",
        "Abrufe mit Fehler", "verwertbare Messwerte", "Stunden mit Daten",
        "Bezugskapazitaet (Setzung)", "Mittlere Auslastung [%]",
        "Median Auslastung [%]", "Minimum Auslastung [%]", "Maximum Auslastung [%]",
        "Mittlere Auslastung Mo-Fr 8-20 Uhr [%]", "Mittlere Auslastung Sa 8-20 Uhr [%]",
        "Mittlere Auslastung 22-6 Uhr [%]",
    ],
    "Wert": [
        ok["zeit"].min(), ok["zeit"].max(), len(roh),
        int((roh["status"] != "ok").sum()), len(ok), len(std), KAPAZITAET,
        round(std["auslastung_pct"].mean(), 1), round(std["auslastung_pct"].median(), 1),
        round(std["auslastung_pct"].min(), 1), round(std["auslastung_pct"].max(), 1),
        round(std[(std.index.dayofweek < 5) & std["stunde"].between(8, 19)]["auslastung_pct"].mean(), 1),
        round(std[(std.index.dayofweek == 5) & std["stunde"].between(8, 19)]["auslastung_pct"].mean(), 1),
        round(std[(std["stunde"] >= 22) | (std["stunde"] < 6)]["auslastung_pct"].mean(), 1),
    ],
})

nach_tag = std.groupby("wochentag")["auslastung_pct"].agg(["mean", "min", "max", "count"]).reindex(TAGE).round(1)
profil = std.pivot_table(index="stunde", columns="wochentag", values="auslastung_pct").reindex(columns=TAGE).round(1)

with pd.ExcelWriter(ZIEL / "auswertung_maastrichter.xlsx") as xl:
    kennwerte.to_excel(xl, sheet_name="Kennwerte", index=False)
    nach_tag.to_excel(xl, sheet_name="nach Wochentag")
    profil.to_excel(xl, sheet_name="Tagesgang")
    std.to_excel(xl, sheet_name="Stundenmittel")
    roh.to_excel(xl, sheet_name="Rohdaten", index=False)

fig, ax = plt.subplots(figsize=(12, 4))
ax.plot(std.index, std["auslastung_pct"], lw=1)
ax.axhline(std["auslastung_pct"].mean(), ls="--", lw=1, label="Mittelwert")
ax.set_ylabel(f"Auslastung [%] (Bezug {KAPAZITAET} Stellplaetze)")
ax.set_ylim(0, 100); ax.legend(); ax.grid(alpha=.3)
ax.set_title("Parkhaus Maastrichter Strasse, Stundenmittel")
fig.tight_layout(); fig.savefig(ZIEL / "verlauf.png", dpi=200)

fig, ax = plt.subplots(figsize=(10, 4))
profil.plot(ax=ax, lw=1)
ax.set_xlabel("Uhrzeit"); ax.set_ylabel("Auslastung [%]"); ax.set_ylim(0, 100)
ax.set_xticks(range(0, 24, 2)); ax.grid(alpha=.3)
ax.set_title("Tagesgang nach Wochentag")
fig.tight_layout(); fig.savefig(ZIEL / "tagesgang.png", dpi=200)

print(kennwerte.to_string(index=False))
