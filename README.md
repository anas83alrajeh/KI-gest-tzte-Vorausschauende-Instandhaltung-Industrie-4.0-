# 🏭 Industrie 4.0: KI-gestützte Vorausschauende Instandhaltung (Predictive Maintenance)

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Machine Learning](https://img.shields.io/badge/Machine_Learning-Isolation_Forest-orange.svg)
![Power BI](https://img.shields.io/badge/Power_BI-Streaming_API-yellow.svg)
![Status](https://img.shields.io/badge/Status-PoC_Completed-brightgreen.svg)

## 📌 Projektübersicht
Dieses Projekt ist ein **Proof of Concept (PoC)** für ein modernes Industrie 4.0-System. Es kombiniert Edge Computing, Unsupervised Machine Learning und Echtzeit-Datenvisualisierung, um Maschinenausfälle vorherzusagen, bevor sie passieren. 

Das System simuliert Maschinendaten in Echtzeit, analysiert diese lokal via KI, streamt die Ergebnisse live in ein **Power BI Dashboard** und generiert vollautomatisch **ERP-Wartungstickets**, um Produktionsausfälle (Downtimes) zu minimieren.

---

## 🏗️ Systemarchitektur

Das Projekt folgt dem Paradigma des **Edge Computings**. Die KI-Inferenz findet direkt an der Datenquelle statt, um Latenzen zu vermeiden und Bandbreite zu sparen.

```mermaid
graph TD
    A[Maschinen-Simulator / Edge] -->|Sensordaten: Temp, Vibration, RPM| B(KI-Modell: Isolation Forest)
    B -->|Bewertung: Normal / Anomalie| C{Entscheidungslogik}
    C -->|Echtzeit-Payload JSON| D[Power BI Live-Dashboard]
    C -->|Flankenerkennung: Anomalie detektiert| E[Automatisierung]
    E -->|Generiert| F[ERP-Wartungsticket]
    E -->|Schreibt| G[protokoll.log & tickets.jsonl]
