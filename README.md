# Nerva Scooter per Home Assistant

Integrazione locale tramite Bluetooth Low Energy (BLE) per scooter elettrici **Nerva** (EXE, EXE II, Cargo, LIFT).

> **Disclaimer:** Questo e' un progetto indipendente sviluppato a scopo di interoperabilita' personale. Non e' affiliato, approvato o supportato in alcun modo da Nerva.

## Funzionalita'
Monitora in locale (senza cloud) i principali parametri dello scooter:
* Stato della batteria (SoC %%) e salute (SoH %%)
* Autonomia stimata (km) e contachilometri totale
* Temperatura di batteria, motore e centralina
* Velocita', potenza istantanea e consumo medio
* Codici di diagnostica (disabilitati di default)

## Installazione tramite HACS
1. Apri **HACS** in Home Assistant.
2. Clicca sui tre puntini in alto a destra e seleziona **Repository personalizzati** (*Custom repositories*).
3. Incolla l'URL `https://github.com` e scegli la categoria **Integrazione** (*Integration*).
4. Clicca su **Aggiungi**, cerca **Nerva Scooter** e installalo.
5. Riavvia Home Assistant.

## Configurazione
1. Vai su **Impostazioni** -> **Dispositivi e servizi** -> **Aggiungi integrazione**.
2. Cerca **Nerva Scooter**.
3. Seleziona il dispositivo Bluetooth rilevato, inserisci il numero di telaio (**VIN** a 17 caratteri), scegli il modello e (opzionalmente) la password di 8 caratteri dell'app Nerva.
