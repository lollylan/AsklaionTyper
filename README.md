# <img src="./assets/ww-logo.png" alt="AsklaionTyper Icon" width="25" height="25"> AsklaionTyper

![version](https://img.shields.io/badge/version-1.1.0-blue)
![python](https://img.shields.io/badge/python-3.11-blue)
![platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![license](https://img.shields.io/badge/license-GPL--3.0-green)

<p align="center">
    <img src="./assets/ww-demo-image-02.gif" alt="AsklaionTyper Demo" width="340" height="136">
</p>

**AsklaionTyper** ist eine Diktier-App für Windows, die Sprache vom Mikrofon direkt in das aktive Fenster transkribiert. Egal ob Word, Browser, Mail oder Praxis-Software — Hotkey drücken, sprechen, fertig.

Das Programm basiert auf [WhisperWriter](https://github.com/savbell/whisper-writer) und nutzt [OpenAIs Whisper-Modell](https://openai.com/research/whisper) (lokal über [faster-whisper](https://github.com/SYSTRAN/faster-whisper) oder per API). Der Fork ist auf den deutschen Workflow optimiert — insbesondere für medizinische Diktate.

---

## Inhalt

- [Welche Variante passt zu mir?](#welche-variante-passt-zu-mir)
- [Was muss ich vorher installieren?](#was-muss-ich-vorher-installieren)
- [Variante A: All-in-One (ein Rechner)](#variante-a-all-in-one-ein-rechner)
- [Variante B: Server + Client (Praxis-Setup)](#variante-b-server--client-praxis-setup)
- [Bedienung](#bedienung)
- [Konfiguration](#konfiguration)
- [Troubleshooting](#troubleshooting)
- [Hinter den Kulissen](#hinter-den-kulissen)
- [Roadmap, Credits, Lizenz](#roadmap)

---

## Welche Variante passt zu mir?

| | **Variante A: All-in-One** | **Variante B: Server + Client** |
|---|---|---|
| **Geeignet für** | Einzelplatz mit eigener GPU | Praxis mit zentralem GPU-PC + mehreren Arbeitsplätzen |
| **Wo läuft Whisper?** | Lokal auf demselben Rechner | Auf einem dedizierten Server-PC |
| **Was braucht der Arbeitsplatz?** | NVIDIA-GPU mit ≥ 6 GB VRAM (für `large-v3`) oder CPU-Fallback | Keine GPU nötig — Mikrofon und Netzwerk reichen |
| **Skalierung** | 1 Person | Mehrere Mitarbeiter parallel (z. B. mehrere Sprechzimmer auf einen GPU-Server) |
| **Setup-Aufwand** | Doppelklick auf eine `.bat` | Einmal Server aufsetzen, dann pro Client `start_client.bat` |

**Tipp für die Praxis:** Variante B. Ein Mitarbeiter-PC braucht keine teure GPU, die GPU-Investition lohnt sich nur am zentralen Server.

---

## Was muss ich vorher installieren?

Du brauchst **drei** Dinge auf jedem Rechner, der AsklaionTyper nutzen soll:

### 1. Python 3.11 (Pflicht)

[**Hier herunterladen → Python 3.11.9**](https://www.python.org/downloads/release/python-3119/)

Scrolle auf der Seite nach unten und wähle **„Windows installer (64-bit)"**.

> ⚠️ **Wichtig beim Installieren:** Auf der ersten Seite des Installers das Häkchen **„Add Python to PATH"** anhaken (ganz unten). Sonst findet Windows Python später nicht.

Spätere Python-Versionen (3.12, 3.13) funktionieren oft auch, aber nicht alle Pakete sind dort schon getestet — bleib bei 3.11, dann gibt's am wenigsten Stress.

### 2. Git (für Klonen vom Repo)

[**Hier herunterladen → Git for Windows**](https://git-scm.com/download/win)

Während der Installation kannst du alle Voreinstellungen so lassen, wie sie sind, und einfach durchklicken.

> Falls du kein Git installieren willst: Du kannst stattdessen oben rechts auf dieser GitHub-Seite auf **„Code"** → **„Download ZIP"** klicken und das ZIP irgendwo hin entpacken. Nachteil: keine automatischen Updates per `git pull`.

### 3. Nur falls du die GPU nutzen willst (Variante A oder Server in Variante B)

Du brauchst eine **NVIDIA-Grafikkarte** und **aktuelle NVIDIA-Treiber** ([nvidia.com/drivers](https://www.nvidia.com/Download/index.aspx)).

Die für Whisper benötigten CUDA- und cuDNN-Bibliotheken installiert das Skript automatisch in das Python-venv. Du musst CUDA **nicht** separat als System-Installation einrichten.

---

## Variante A: All-in-One (ein Rechner)

Für: Einzelplatz mit eigener GPU.

### Schritt 1 — Repo klonen

Öffne `Eingabeaufforderung` (Windows-Taste → „cmd" tippen → Enter) und tippe:

```cmd
cd %USERPROFILE%\Documents
git clone https://github.com/lollylan/AsklaionTyper.git
cd AsklaionTyper
```

Falls du die ZIP-Variante nutzt: ZIP entpacken und direkt zu Schritt 2 springen.

### Schritt 2 — Starten

Im Explorer in den Ordner `AsklaionTyper\` wechseln und auf **`start.bat`** doppelklicken.

Beim **ersten Start** passiert das hier automatisch (kann 5-10 Minuten dauern):
1. Eine passende Python-Installation wird gesucht.
2. Ein virtuelles Environment wird in `venv\` angelegt.
3. Alle Pakete werden installiert (inklusive CUDA-Bibliotheken — die sind groß).
4. Die App startet.

Bei späteren Starts geht das in Sekunden — Doppelklick und los.

### Schritt 3 — Erste Konfiguration

Beim allerersten Start öffnet sich das **Settings-Fenster**. Die deutschen Voreinstellungen (`language: de`, `model: large-v3`, `input_method: clipboard`) sind schon richtig gesetzt — du kannst direkt auf **Save** klicken.

Danach erscheint das Hauptfenster, **Start** klicken, fertig. Die App läuft jetzt im Hintergrund (System-Tray rechts unten).

### Schritt 4 — Diktieren

In jedem beliebigen Fenster (Word, Mail, Browser, Karteikarte) den Cursor an die Stelle setzen, wo der Text hinsoll, dann:

- **`Strg + Shift + Leertaste`** drücken
- sprechen
- bei `continuous`-Modus (Standard) hört die App nach einer Sprechpause automatisch auf — der Text wird getippt

Andere Aufnahmemodi → siehe [Bedienung](#bedienung).

---

## Variante B: Server + Client (Praxis-Setup)

Für: Mehrere Arbeitsplätze in einem lokalen Netzwerk, ein zentraler GPU-PC.

**Architektur:**

```
   [PC Sprechzimmer 1]                            ┌────────────────────┐
   start_client.bat ──── HTTPS POST audio ───►   │                    │
                                                  │   GPU-Server-PC    │
   [PC Sprechzimmer 2]                            │  start_server.bat  │
   start_client.bat ──── HTTPS POST audio ───►   │  (Whisper large-v3)│
                                                  │                    │
   [PC Empfang]                                   │   Port 8000        │
   start_client.bat ──── HTTPS POST audio ───►   └────────────────────┘
```

### Teil 1 — Server einrichten (auf dem GPU-PC)

#### Schritt 1.1 — Repo klonen

```cmd
cd %USERPROFILE%\Documents
git clone https://github.com/lollylan/AsklaionTyper.git
cd AsklaionTyper
```

#### Schritt 1.2 — Server starten

Doppelklick auf **`start_server.bat`**. Beim ersten Start:

1. Python-venv wird angelegt.
2. Server-Pakete werden installiert (`fastapi`, `uvicorn`, `cryptography`, `python-multipart`).
3. CUDA-Bibliotheken werden eingerichtet.
4. Ein selbstsigniertes TLS-Zertifikat wird in `certs\` erzeugt (CA + Server-Cert für die aktuelle LAN-IP).
5. Whisper `large-v3` wird in den GPU-VRAM geladen (~3 GB, 20-60 Sek.).
6. Der Server lauscht auf `https://<deine-LAN-IP>:8000`.

Im Konsolenfenster siehst du am Ende:

```
[OK] Server laeuft auf: https://192.168.178.131:8000
[INFO] CA-Zertifikat (einmalig auf jeden Client-PC kopieren): C:\...\certs\ca.crt
```

> Notiere dir die **IP-Adresse** und den **Pfad zur `ca.crt`** — die brauchst du gleich auf den Clients.

**Server am Laufen lassen:** Solange das Konsolenfenster offen ist, läuft der Server. `Strg+C` beendet ihn. Tipp: Verknüpfung von `start_server.bat` in den Autostart-Ordner legen, damit er bei jedem Hochfahren automatisch startet (`Win+R` → `shell:startup` → Verknüpfung dort hinein).

#### Schritt 1.3 — Firewall

Damit andere PCs den Server erreichen, muss in der Windows-Firewall **Port 8000 (TCP) eingehend** freigegeben sein. Beim ersten Start bietet Windows üblicherweise einen Dialog an („Python-Zugriff im privaten Netzwerk zulassen") — auf **Zulassen** klicken.

Falls du den Dialog verpasst hast: `Windows-Sicherheit` → `Firewall- & Netzwerkschutz` → `Erweiterte Einstellungen` → `Eingehende Regeln` → `Neue Regel` → Port → TCP → 8000 → Zulassen.

### Teil 2 — Client einrichten (auf jedem Arbeitsplatz)

#### Schritt 2.1 — `ca.crt` vom Server kopieren

Auf dem Server-PC liegt die Datei `C:\...\AsklaionTyper\certs\ca.crt`. Diese Datei (nur diese eine!) auf jeden Client-PC übertragen — z. B. per USB-Stick, gemeinsamem Netzlaufwerk oder Email.

> **Nur** `ca.crt` kopieren! Niemals `ca.key` oder `server.key` — das sind die privaten Schlüssel und gehören ausschließlich auf den Server.

Auf dem Client legst du die Datei z. B. unter `C:\AsklaionTyper-Cert\ca.crt` ab. Pfad merken.

#### Schritt 2.2 — Repo klonen + Client starten

Auf dem Client-PC:

```cmd
cd %USERPROFILE%\Documents
git clone https://github.com/lollylan/AsklaionTyper.git
cd AsklaionTyper
```

Doppelklick auf **`start_client.bat`**. Beim ersten Start:

1. Python-venv wird angelegt.
2. Pakete werden installiert (deutlich weniger als beim Server, ~1 Minute).
3. Die App startet — gleiche GUI wie All-in-One.

#### Schritt 2.3 — Server-Zugang konfigurieren

Im Hauptfenster auf **Open Settings** klicken (oder Tray-Icon → Open Settings). Im **„Model options"**-Tab:

| Feld | Wert |
|---|---|
| Use api | ✓ (eingeschaltet) |
| Provider | `asklaion` |
| Base url | `https://<server-ip>:8000` (z. B. `https://192.168.178.131:8000`) |
| Ca cert path | Pfad zur kopierten `ca.crt` (z. B. `C:\AsklaionTyper-Cert\ca.crt`) |

**Save** klicken, App startet neu — fertig. Der Client schickt Audio jetzt an den Server, der Text kommt zurück und wird im aktiven Fenster getippt.

> **Wichtig:** Wenn die LAN-IP des Servers sich später ändert (z. B. neuer Router, neuer DHCP-Lease), muss auf dem Server **`certs\` einmal gelöscht und `start_server.bat` neu gestartet** werden — er erzeugt dann ein neues Server-Zertifikat für die neue IP. Die `ca.crt` bleibt gültig und muss nicht erneut auf die Clients verteilt werden.

---

## Bedienung

### Hotkey (Standard)

`Strg + Shift + Leertaste` — anpassbar in den Settings.

### Aufnahmemodi

Im Settings-Fenster unter **Recording options → Recording mode**:

| Modus | Verhalten |
|---|---|
| `continuous` *(Standard, fließendes Diktat)* | Aufnahme stoppt nach Sprechpause, Text wird getippt, Aufnahme läuft sofort weiter. Beenden mit dem Hotkey. |
| `voice_activity_detection` | Aufnahme stoppt nach Sprechpause; **kein** automatischer Neustart. Manuell neu starten. |
| `press_to_toggle` | 1× Hotkey starten, 1× Hotkey beenden. |
| `hold_to_record` | Hotkey halten = aufnehmen, loslassen = transkribieren. |
| `hold_or_double_tap` | Hybrid: kurz halten = Push-to-Talk, doppelt tippen = Kontinuierlich-Modus bis nächster Tap. |

### Tray-Icon

Rechts unten im System-Tray erscheint das AsklaionTyper-Icon. Rechtsklick öffnet das Menü:
- **AsklaionTyper Main Menu** — öffnet Hauptfenster
- **Open Settings** — Konfiguration
- **Exit** — App beenden

---

## Konfiguration

Die Einstellungen werden über das **Settings-Fenster** verwaltet und auf Festplatte gespeichert in:

| Variante | Datei |
|---|---|
| All-in-One (`run.py` / `start.bat`) | `src\config.yaml` |
| Netzwerk-Client (`client.py` / `start_client.bat`) | `client_config.yaml` (im Repo-Root) |

Beide Dateien sind in `.gitignore` und werden **nicht** versioniert (sie können API-Keys oder Server-Pfade enthalten).

Das vollständige Schema mit allen verfügbaren Optionen und ihren Defaults findest du in [`src\config_schema.yaml`](src/config_schema.yaml).

### Wichtigste Optionen für deutsche Diktate

| Bereich | Option | Empfehlung | Wirkung |
|---|---|---|---|
| `model_options.common` | `language` | `de` | Erzwingt deutsches Sprachmodell. |
| `model_options.common` | `initial_prompt` | dt. Beispielsatz | Verbessert Groß-/Kleinschreibung & Zeichensetzung. |
| `model_options.local` | `model` | `large-v3` | Beste Genauigkeit; benötigt GPU mit ≥ 6 GB VRAM. |
| `model_options.local` | `device` | `cuda` / `auto` | GPU-Beschleunigung. |
| `model_options.local` | `compute_type` | `float16` | Schneller auf modernen GPUs. |
| `recording_options` | `recording_mode` | `continuous` | Diktatfluss ohne wiederholtes Drücken. |
| `post_processing` | `input_method` | `clipboard` | Robust für Umlaute auf Windows. |

---

## Troubleshooting

### Allgemein

**„Beim Doppelklick auf `start.bat` schließt sich das Konsolenfenster sofort"**
Wahrscheinlich kein Python in PATH. Re-Installieren mit Häkchen **„Add Python to PATH"**.

**„Umlaute (ä, ö, ü, ß) werden falsch eingefügt"**
Settings → Post processing → `input_method: clipboard` (Standard in diesem Fork).

**„CUDA out of memory" / Modell zu groß**
Auf kleineres Modell wechseln (`medium`, `small`, `base`) oder `compute_type: int8` (erzwingt CPU).

**„DLL-Fehler beim Start"**
cuDNN-Version prüfen — es muss **cuDNN 8** sein, nicht 9. Das Skript installiert die richtige Version automatisch; falls du manuell etwas eingerichtet hast, könnte ein Mismatch vorliegen.

### Server + Client (Variante B)

**„Client kann den Server nicht erreichen / Timeout"**
- Stimmt die IP in `Base url`? IP des Servers checken: am Server-PC `cmd` öffnen, `ipconfig` tippen, „IPv4-Adresse" suchen.
- Firewall am Server: Port 8000 (TCP) eingehend frei?
- Server überhaupt am Laufen? Konsolenfenster auf dem Server-PC sollte „Uvicorn running on https://0.0.0.0:8000" zeigen.

**„CA-Zertifikat-Fehler / certificate verify failed"**
- Stimmt der Pfad in `Ca cert path` auf dem Client?
- IP des Servers geändert? Dann am Server `certs\` löschen, `start_server.bat` neu — der Server generiert ein neues Server-Cert für die neue IP. CA bleibt gültig.

**„Server startet, aber Whisper lädt ewig"**
Beim allerersten Start lädt `faster-whisper` das `large-v3`-Modell von Hugging Face herunter (~3 GB). Das passiert nur einmal, danach ist das Modell im Cache.

**„Port 8000 ist bereits belegt"**
Eine alte Server-Instanz läuft noch. Task-Manager öffnen, alle `python.exe`-Prozesse beenden, dann `start_server.bat` neu.

---

## Hinter den Kulissen

### Wie der All-in-One- und der Netzwerk-Modus zusammenspielen

Beide Varianten teilen sich denselben Code in `src\` (Hotkey-Listener, Audio-Aufnahme, Settings-Fenster, Tray-Icon). Der einzige Unterschied:

- **`run.py`** lädt `src\config.yaml` und nutzt das lokale Whisper-Modell.
- **`client.py`** ist ein schlanker Wrapper, der `src\main.py` mit der Umgebungsvariable `ASKLAIONTYPER_CONFIG=client_config.yaml` startet, sodass eine **separate Config-Datei** verwendet wird, ohne dass die All-in-One-Config überschrieben wird.

In den Settings ist im Bereich **Model options** ein Schalter `provider`:

| Provider | Endpoint | Authentifizierung |
|---|---|---|
| `openai` | `POST {base_url}/audio/transcriptions` (OpenAI-kompatibel) | Bearer-Token |
| `asklaion` | `POST {base_url}/transcribe` (`server_GPU_CUDA_Parallel.py`) | TLS-CA-Pinning |

Damit kannst du den All-in-One-Modus jederzeit auch gegen einen externen OpenAI-Endpoint oder gegen einen LAN-Asklaion-Server fahren — ohne den Client neu zu starten.

### Datei-Übersicht

```
AsklaionTyper\
├── run.py                       # All-in-One-Einstieg
├── client.py                    # Netzwerk-Client-Einstieg (Wrapper)
├── start.bat                    # Bootstrap All-in-One
├── start_client.bat             # Bootstrap Client
├── start_server.bat             # Bootstrap Server
├── server_GPU_CUDA_Parallel.py  # Whisper-HTTPS-Server (FastAPI)
├── security_utils.py            # TLS-Cert-Helper für den Server
├── requirements.txt             # Geteilte Python-Abhängigkeiten
├── certs\                       # vom Server bei Start erzeugt (gitignored, enthält private Keys!)
├── src\
│   ├── main.py                  # Qt-App (Tray, Hauptfenster)
│   ├── transcription.py         # local / openai / asklaion-Provider
│   ├── key_listener.py          # Globaler Hotkey
│   ├── input_simulation.py      # Tippen via pynput / Clipboard
│   ├── config_schema.yaml       # Alle Konfig-Optionen + Defaults
│   └── ui\                      # Settings, Hauptfenster, Status-Pille
└── client_config.yaml           # User-Settings für Client-Modus (gitignored)
```

---

## Roadmap

- [x] Clipboard-Eingabe für Umlaute
- [x] Modell-Warmup nach Laden
- [x] CPU-Fallback bei CUDA-Fehler
- [x] Netzwerk-Server-Modus mit HTTPS und CA-Pinning
- [x] Bootstrap-Skripte für Server und Client
- [ ] Wortersetzungen (z. B. „Punkt" → „.", Diktatkürzel → Ausdrücke)
- [ ] Optionale GPT-Nachbearbeitung für Strukturierung medizinischer Diktate
- [ ] Service-Mode (als Windows-Dienst) für den Server

Detaillierte Änderungshistorie: [CHANGELOG.md](CHANGELOG.md).

## Credits

- [savbell/whisper-writer](https://github.com/savbell/whisper-writer) — das ursprüngliche Projekt, auf dem AsklaionTyper basiert.
- [OpenAI](https://openai.com/) für das Whisper-Modell.
- [Guillaume Klein](https://github.com/guillaumekln) und SYSTRAN für [faster-whisper](https://github.com/SYSTRAN/faster-whisper).

## Lizenz

GNU General Public License v3.0 — siehe [LICENSE](LICENSE).
