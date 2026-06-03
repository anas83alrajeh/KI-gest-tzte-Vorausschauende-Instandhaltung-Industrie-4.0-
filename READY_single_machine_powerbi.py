"""
======================================================================
 PROJEKT: Vorausschauende Instandhaltung & Automatisierung (PoC)
 COMPLETE PRODUCTION-READY SYSTEM
 Einzelmaschine mit Power BI API - READY TO RUN
======================================================================
 ⚠️  SECURITY WARNING / تحذير أمني
 هذا الملف يحتوي على Power BI API Key. لا تشاركه علناً أو على GitHub.
 This file contains a Power BI API secret. Do NOT share publicly.
 Treat this file like a password.
======================================================================
"""

import os
import time
import json
import random
import signal
import sys
import threading
from datetime import datetime, timezone
from collections import deque

import requests
import numpy as np
from sklearn.ensemble import IsolationForest

# ======================================================================
# 1) KONFIGURATION — POWER BI READY
# ======================================================================
# ✅ Power BI Push URL — READY TO USE
POWER_BI_PUSH_URL = "https://api.powerbi.com/beta/8fcf4cd9-2fe4-4571-8431-b17c3f29efb3/datasets/036b76c8-e7a8-4f97-8fef-64eadaef5ec5/rows?experience=power-bi&key=QzIhrwylJCO8YdqoMsPJKbgEZSaA2Uq%2FZ8ntZw%2B34X4tgL7UL2SVN%2FEXTqnLCaWWJyWPOFtuOoRjYEPrgYhi5w%3D%3D"

SEND_INTERVAL_SEC = 1.0
MACHINE_ID = "MOTOR-A1"
STANDORT = "Werk Stuttgart, Halle 3"
REQUEST_TIMEOUT = 5
MAX_RETRIES = 3

LOG_DATEI = "protokoll.log"
TICKET_DATEI = "tickets.jsonl"

TRAINING_SAMPLES = 500
CONTAMINATION = 0.02
SMOOTHING_WINDOW = 5
ALARM_THRESHOLD = 0.6
TICKET_COOLDOWN_SEC = 30

SENSOR_PROFILES = {
    "NORMAL": {
        "temperatur": {"mittel": 65.0, "streuung": 2.5},
        "vibration":  {"mittel": 2.0,  "streuung": 0.4},
        "drehzahl":   {"mittel": 1480, "streuung": 15},
    },
    "ANOMALIE": {
        "temperatur": {"mittel": 95.0, "streuung": 6.0},
        "vibration":  {"mittel": 7.5,  "streuung": 1.5},
        "drehzahl":   {"mittel": 1300, "streuung": 60},
    },
}
FEATURE_ORDER = ("temperatur", "vibration", "drehzahl")
SOLLWERTE = {"temperatur": 65.0, "vibration": 2.0, "drehzahl": 1480}

# ======================================================================
# 2) GLOBALER ZUSTAND
# ======================================================================
class SimulatorState:
    def __init__(self):
        self.modus = "NORMAL"
        self.laeuft = True
        self.degradation = 0.0

    def toggle(self):
        self.modus = "ANOMALIE" if self.modus == "NORMAL" else "NORMAL"
        print(f"\n>>> Modus gewechselt zu: {self.modus} <<<\n")

state = SimulatorState()

# ======================================================================
# 3) DATENGENERIERUNG
# ======================================================================
def _wert_aus_profil(profil_key: str, sensor: str) -> float:
    p = SENSOR_PROFILES[profil_key][sensor]
    return random.gauss(p["mittel"], p["streuung"])

def generiere_messpaket() -> dict:
    ziel = 1.0 if state.modus == "ANOMALIE" else 0.0
    state.degradation += (ziel - state.degradation) * 0.15

    paket = {}
    for sensor in FEATURE_ORDER:
        normal_wert = _wert_aus_profil("NORMAL", sensor)
        anomalie_wert = _wert_aus_profil("ANOMALIE", sensor)
        wert = normal_wert + (anomalie_wert - normal_wert) * state.degradation
        paket[sensor] = round(wert, 2)

    paket["zeitstempel"] = datetime.now(timezone.utc).isoformat()
    paket["maschine_id"] = MACHINE_ID
    paket["standort"] = STANDORT
    return paket

# ======================================================================
# 4) KI-MODELL
# ======================================================================
class AnomalieDetektor:
    def __init__(self):
        self.model = IsolationForest(
            n_estimators=100, contamination=CONTAMINATION, random_state=42
        )
        self.trainiert = False
        self.fenster = deque(maxlen=SMOOTHING_WINDOW)

    def trainieren(self):
        print(f"[KI] Training laeuft ... ({TRAINING_SAMPLES} Normal-Samples)")
        X = [[_wert_aus_profil("NORMAL", s) for s in FEATURE_ORDER]
             for _ in range(TRAINING_SAMPLES)]
        self.model.fit(np.array(X))
        self.trainiert = True
        print("[KI] Training abgeschlossen. Modell ist bereit.\n")

    def bewerten(self, paket: dict) -> dict:
        if not self.trainiert:
            self.trainieren()
        features = np.array([[paket[s] for s in FEATURE_ORDER]])
        einzel_pred = int(self.model.predict(features)[0])
        score = float(self.model.decision_function(features)[0])
        self.fenster.append(1 if einzel_pred == -1 else 0)
        anteil = sum(self.fenster) / len(self.fenster)
        return {
            "ki_status": "GEFAHR" if anteil >= ALARM_THRESHOLD else "NORMAL",
            "anomalie_score": round(score, 4),
            "anomalie_punkt": "Anomalie" if einzel_pred == -1 else "OK",
            "anomalie_anteil": round(anteil, 2),
        }

detektor = AnomalieDetektor()

# ======================================================================
# 5) WARTUNGSMANAGER
# ======================================================================
class WartungsManager:
    def __init__(self):
        self.war_in_gefahr = False
        self.letztes_ticket_ts = 0.0
        self.ticket_zaehler = 0

    @staticmethod
    def _handlungsempfehlung(paket: dict) -> str:
        empfehlungen = []
        if paket["temperatur"] > SOLLWERTE["temperatur"] * 1.20:
            empfehlungen.append("Ueberhitzung -> Kuehlung & Schmierung pruefen")
        if paket["vibration"] > SOLLWERTE["vibration"] * 1.50:
            empfehlungen.append("Starke Vibration -> Lager / Ausrichtung pruefen")
        if abs(paket["drehzahl"] - SOLLWERTE["drehzahl"]) > 80:
            empfehlungen.append("Instabile Drehzahl -> Antrieb / Last pruefen")
        return " | ".join(empfehlungen) if empfehlungen else "Allgemeine Inspektion empfohlen"

    @staticmethod
    def _prioritaet(paket: dict) -> str:
        score = paket.get("anomalie_score", 0.0)
        if score < -0.15:
            return "KRITISCH (P1)"
        if score < -0.05:
            return "HOCH (P2)"
        return "MITTEL (P3)"

    def pruefen_und_reagieren(self, paket: dict):
        ist_gefahr = (paket["ki_status"] == "GEFAHR")
        jetzt = time.time()
        neue_stoerung = ist_gefahr and not self.war_in_gefahr
        cooldown_ok = (jetzt - self.letztes_ticket_ts) > TICKET_COOLDOWN_SEC
        if neue_stoerung and cooldown_ok:
            self._ticket_erstellen(paket)
            self.letztes_ticket_ts = jetzt
        self.war_in_gefahr = ist_gefahr

    def _ticket_erstellen(self, paket: dict):
        self.ticket_zaehler += 1
        jetzt = datetime.now()
        ticket_id = f"WT-{jetzt.strftime('%Y%m%d')}-{self.ticket_zaehler:04d}"
        ticket = {
            "ticket_id": ticket_id,
            "erstellt_am": jetzt.isoformat(),
            "maschine_id": paket["maschine_id"],
            "standort": paket.get("standort", "-"),
            "status": "OFFEN",
            "prioritaet": self._prioritaet(paket),
            "fehlerbeschreibung": "KI hat drohenden Maschinenausfall erkannt",
            "handlungsempfehlung": self._handlungsempfehlung(paket),
            "messwerte": {
                "temperatur": paket["temperatur"],
                "vibration": paket["vibration"],
                "drehzahl": paket["drehzahl"],
                "anomalie_score": paket["anomalie_score"],
            },
        }
        self._erp_konsole(ticket)
        self._protokoll_schreiben(ticket)

    @staticmethod
    def _erp_konsole(ticket: dict):
        print("\n" + "#" * 64)
        print("#  >>> AUTOMATISCHES WARTUNGSTICKET ERSTELLT <<<")
        print("#" * 64)
        print(f"#  Ticket-ID      : {ticket['ticket_id']}")
        print(f"#  Erstellt am    : {ticket['erstellt_am']}")
        print(f"#  Maschine       : {ticket['maschine_id']}  ({ticket['standort']})")
        print(f"#  Prioritaet     : {ticket['prioritaet']}")
        print(f"#  Beschreibung   : {ticket['fehlerbeschreibung']}")
        print(f"#  Empfehlung     : {ticket['handlungsempfehlung']}")
        m = ticket["messwerte"]
        print(f"#  Messwerte      : T={m['temperatur']} C | V={m['vibration']} mm/s | RPM={m['drehzahl']} | Score={m['anomalie_score']}")
        print("#" * 64 + "\n")

    @staticmethod
    def _protokoll_schreiben(ticket: dict):
        zeile = (f"[{ticket['erstellt_am']}] {ticket['ticket_id']} | {ticket['prioritaet']} | "
                 f"{ticket['maschine_id']} | T={ticket['messwerte']['temperatur']}C "
                 f"V={ticket['messwerte']['vibration']}mm/s | {ticket['handlungsempfehlung']}\n")
        with open(LOG_DATEI, "a", encoding="utf-8") as f:
            f.write(zeile)
        with open(TICKET_DATEI, "a", encoding="utf-8") as f:
            f.write(json.dumps(ticket, ensure_ascii=False) + "\n")
        print(f"[PROTOKOLL] Eintrag gespeichert -> {LOG_DATEI}")

manager = WartungsManager()

# ======================================================================
# 6) DATENVERSAND AN POWER BI
# ======================================================================
# Nur diese 9 Felder existieren im Power BI Dataset.
# 'standort' wird intern fuer Tickets genutzt, aber NICHT gesendet.
POWERBI_FELDER = (
    "zeitstempel", "temperatur", "vibration", "drehzahl", "maschine_id",
    "ki_status", "anomalie_score", "anomalie_punkt", "anomalie_anteil",
)

def sende_an_powerbi(paket: dict) -> bool:
    # Paket auf die im Dataset definierten Spalten filtern (kein 'standort'!)
    sende_paket = {k: paket[k] for k in POWERBI_FELDER if k in paket}
    payload = json.dumps([sende_paket])
    headers = {"Content-Type": "application/json"}
    for versuch in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(POWER_BI_PUSH_URL, data=payload,
                                 headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                return True
            # Diagnose: zeige den Grund vom Power BI Server
            grund = resp.text[:200] if resp.text else "(keine Details)"
            print(f"[WARN] Power BI Status {resp.status_code} "
                  f"(Versuch {versuch}/{MAX_RETRIES}) | Grund: {grund}")
        except requests.exceptions.RequestException as e:
            print(f"[FEHLER] Netzwerk: {e} (Versuch {versuch}/{MAX_RETRIES})")
        time.sleep(0.5 * versuch)
    return False

# ======================================================================
# 7) TASTATUR-STEUERUNG (Windows-robust + arabische Ziffern)
# ======================================================================
def _verarbeite(eingabe: str):
    eingabe = eingabe.strip().lower()
    if eingabe == "q":
        state.laeuft = False
        print("\n>>> Beenden angefordert ... <<<")
    else:
        state.toggle()

def keyboard_listener():
    if sys.platform == "win32":
        import msvcrt
        while state.laeuft:
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\r", "\n", "\x00", "\xe0"):
                    continue
                _verarbeite(ch)
            else:
                time.sleep(0.05)
    else:
        while state.laeuft:
            zeile = sys.stdin.readline()
            if not zeile:
                break
            _verarbeite(zeile)

# ======================================================================
# 8) HAUPTSCHLEIFE
# ======================================================================
def hauptschleife():
    print("=" * 70)
    print(" PRODUKTIONS-SYSTEM: Einzelmaschine + KI + Power BI + Automatisierung")
    print(" Maschine:", MACHINE_ID)
    print("=" * 70)
    print(" Steuerung (Taste druecken, unter Windows OHNE ENTER):")
    print("   beliebige Taste = NORMAL<->ANOMALIE   |   q = Beenden")
    print(" Power BI: VERBUNDEN ✅")
    # Diagnose: welche Dataset-ID ist geladen?
    try:
        _ds_id = POWER_BI_PUSH_URL.split("/datasets/")[1].split("/")[0]
        print(f" Dataset-ID: {_ds_id}")
    except Exception:
        print(" Dataset-ID: (konnte nicht gelesen werden)")
    print("-" * 70)

    detektor.trainieren()
    t = threading.Thread(target=keyboard_listener, daemon=True)
    t.start()

    while state.laeuft:
        paket = generiere_messpaket()
        paket.update(detektor.bewerten(paket))
        manager.pruefen_und_reagieren(paket)
        gesendet = sende_an_powerbi(paket)

        ziel = "[✅ PowerBI]" if gesendet else "[❌ lokal]"
        warnung = "  !!! GEFAHR !!!" if paket["ki_status"] == "GEFAHR" else ""
        print(f"{ziel} {paket['zeitstempel']} | T={paket['temperatur']:6.2f} | "
              f"V={paket['vibration']:5.2f} | RPM={paket['drehzahl']:7.2f} | "
              f"KI={paket['ki_status']:6s} (Score={paket['anomalie_score']:7.4f}){warnung}")

        time.sleep(SEND_INTERVAL_SEC)

    print(f"\nSimulator gestoppt. {manager.ticket_zaehler} Ticket(s) erstellt.")
    print(f"Protokoll: {os.path.abspath(LOG_DATEI)}")

def signal_handler(sig, frame):
    state.laeuft = False
    print("\n>>> Strg+C erkannt, beende ... <<<")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    hauptschleife()
