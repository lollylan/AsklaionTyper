import importlib.util
import os
import subprocess
import sys


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
REQUIREMENTS_FILE = os.path.join(PROJECT_ROOT, 'requirements.txt')

# Maps the import name (left) we test for to the pip package name (right)
# that satisfies it. Used both for fast detection of missing packages and for
# a targeted pip install when the full requirements.txt is unavailable.
REQUIRED_PACKAGES = {
    'PyQt5': 'PyQt5',
    'faster_whisper': 'faster-whisper',
    'openai': 'openai',
    'pynput': 'pynput',
    'pyperclip': 'pyperclip',
    'audioplayer': 'audioplayer',
    'dotenv': 'python-dotenv',
    'sounddevice': 'sounddevice',
    'soundfile': 'soundfile',
    'numpy': 'numpy',
    'yaml': 'PyYAML',
    'webrtcvad': 'webrtcvad-wheels',
}


def _missing_imports():
    return [mod for mod in REQUIRED_PACKAGES if importlib.util.find_spec(mod) is None]


def _pip_install(args):
    cmd = [sys.executable, '-m', 'pip', 'install', *args]
    print('  $ ' + ' '.join(cmd))
    subprocess.check_call(cmd)


def ensure_dependencies():
    missing = _missing_imports()
    if not missing:
        return

    print(f'Fehlende Abhängigkeiten erkannt: {", ".join(missing)}')
    print('Installiere fehlende Pakete...')

    if os.path.exists(REQUIREMENTS_FILE):
        try:
            _pip_install(['-r', REQUIREMENTS_FILE])
        except subprocess.CalledProcessError as exc:
            print(f'pip install -r requirements.txt fehlgeschlagen: {exc}')
            print('Versuche, fehlende Pakete einzeln zu installieren...')
            _pip_install([REQUIRED_PACKAGES[m] for m in missing])
    else:
        _pip_install([REQUIRED_PACKAGES[m] for m in missing])

    still_missing = _missing_imports()
    if still_missing:
        print(
            'Folgende Pakete konnten nicht installiert werden: '
            + ', '.join(still_missing)
        )
        sys.exit(1)
    print('Alle Abhängigkeiten installiert.')


def main():
    ensure_dependencies()

    from dotenv import load_dotenv

    print('Starting AsklaionTyper...')
    load_dotenv()
    main_script = os.path.join(PROJECT_ROOT, 'src', 'main.py')
    sys.exit(subprocess.call([sys.executable, main_script]))


if __name__ == '__main__':
    main()
