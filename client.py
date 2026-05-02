"""
client.py - AsklaionTyper Network Client (thin wrapper).

Verwendet die identische GUI/Hotkey-/Settings-Logik wie das All-in-One-
Skript (run.py / src/main.py). Einziger Unterschied: liest und schreibt
seine Konfiguration in client_config.yaml im Projekt-Root statt in
src/config.yaml. Das All-in-One-Setup bleibt davon vollkommen unberuehrt.

Der Server-Endpoint wird im Settings-Fenster eingetragen:
    Model options > Use api: ON
    Model options > Provider: asklaion
    Model options > Base url: https://<lan-ip>:8000
    Model options > Ca cert path: <pfad zu certs/ca.crt>

Beim ersten Start (keine client_config.yaml vorhanden) oeffnet sich
automatisch das Settings-Fenster, weil src/main.py das so macht, wenn
kein User-Config gefunden wird. Vor dem ersten Save legen wir eine
Vorlage mit den Server-Modus-Defaults an, damit der User nur noch URL
und CA-Cert-Pfad eintragen muss.
"""

import os
import subprocess
import sys

import yaml

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CLIENT_CONFIG = os.path.join(PROJECT_ROOT, 'client_config.yaml')

# Defaults the all-in-one app would otherwise inherit, but pre-set so the
# Settings window opens with the right toggles flipped (use_api on,
# provider=asklaion). User just needs to fill in URL + cert path.
CLIENT_DEFAULTS = {
    'model_options': {
        'use_api': True,
        'api': {
            'provider': 'asklaion',
            'base_url': '',
            'ca_cert_path': '',
        },
    },
    'recording_options': {
        'recording_mode': 'hold_or_double_tap',
    },
    'post_processing': {
        # Robust default for German umlauts on Windows (avoids per-char
        # pynput quirks with multibyte characters).
        'input_method': 'clipboard',
    },
}


def _ensure_client_config_template():
    """Write client_config.yaml with sane server-mode defaults if missing.

    We deliberately do not include base_url or ca_cert_path values, so the
    Settings window the user gets at first launch shows empty fields they
    must fill in. transcribe_asklaion() raises a clear error if base_url
    is still empty after save.
    """
    if os.path.isfile(CLIENT_CONFIG):
        return
    with open(CLIENT_CONFIG, 'w', encoding='utf-8') as f:
        yaml.dump(CLIENT_DEFAULTS, f, default_flow_style=False,
                  allow_unicode=True, sort_keys=False)
    print(f'Vorlage angelegt: {CLIENT_CONFIG}')


def main():
    print('Starting AsklaionTyper Client (network mode)...')
    _ensure_client_config_template()

    # Tell ConfigManager (in src/utils.py) to read/write the client config
    # file instead of src/config.yaml. The all-in-one variant uses the
    # default path and is not affected.
    env = os.environ.copy()
    env['ASKLAIONTYPER_CONFIG'] = CLIENT_CONFIG

    main_script = os.path.join(PROJECT_ROOT, 'src', 'main.py')
    sys.exit(subprocess.call([sys.executable, main_script], env=env))


if __name__ == '__main__':
    main()
