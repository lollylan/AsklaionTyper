"""
client.py - AsklaionTyper Network Client.

Eigenstaendige Client-Variante: nimmt Audio lokal auf (mit Hotkey, VAD,
allen Aufnahme-Modi) und schickt es zur Transkription an einen entfernten
Whisper-Server. Lokale GPU- und faster-whisper-Modelle werden nicht benoetigt.

Spricht das Asklaion-Server-Protokoll (server_GPU_CUDA_Parallel.py):
    POST {base_url}/transcribe
mit multipart/form-data (file=audio.wav) ueber HTTPS mit selbstsigniertem
CA. Response: {"text": "...", "language": "...", "probability": ...}.

Die UI-/Hotkey-/Eingabe-Module aus src/ werden unveraendert wiederverwendet:
- src/key_listener.py
- src/input_simulation.py
- src/utils.py (ConfigManager)
- src/ui/status_window.py

Konfiguration: client_config.yaml im Projekt-Root (wird beim ersten Start
mit Defaults angelegt).
"""

import io
import math
import os
import sys
import time
import traceback
from collections import deque
from threading import Event

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(PROJECT_ROOT, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import numpy as np
import requests
import sounddevice as sd
import soundfile as sf
import webrtcvad
import yaml
from PyQt5.QtCore import QMutex, QObject, QProcess, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (QAction, QApplication, QMenu, QMessageBox,
                             QSystemTrayIcon)

from input_simulation import InputSimulator
from key_listener import KeyListener
from utils import ConfigManager

try:
    from ui.status_window import StatusWindow
    HAS_STATUS_WINDOW = True
except Exception:
    HAS_STATUS_WINDOW = False


CLIENT_CONFIG_PATH = os.path.join(PROJECT_ROOT, 'client_config.yaml')

DEFAULT_CLIENT_CONFIG = {
    'model_options': {
        # Forced True at runtime, kept here for transparency.
        'use_api': True,
        'common': {
            # Server hat aktuell language='de' fest verdrahtet, daher hier
            # nur informativ.
            'language': 'de',
            'temperature': 0.0,
            'initial_prompt': None,
        },
        'api': {
            # Asklaion-Server laeuft per Default auf https://<server-ip>:8000
            'base_url': 'https://127.0.0.1:8000',
            # Pfad zum CA-Zertifikat (certs/ca.crt vom Server). Leer lassen,
            # um TLS-Verifizierung temporaer abzuschalten (NICHT empfohlen).
            'ca_cert_path': '',
            'timeout_s': 60,
        },
    },
    'recording_options': {
        'activation_key': 'ctrl+shift+space',
        'input_backend': 'auto',
        'recording_mode': 'hold_or_double_tap',
        'hold_threshold_ms': 350,
        'double_tap_window_ms': 450,
        'sound_device': None,
        'sample_rate': 16000,
        'silence_duration': 900,
        'min_duration': 100,
    },
    'post_processing': {
        'writing_key_press_delay': 0.005,
        'remove_trailing_period': False,
        'add_trailing_space': True,
        'remove_capitalization': False,
        'input_method': 'clipboard',
    },
    'misc': {
        'print_to_terminal': True,
        'hide_status_window': False,
        'noise_on_completion': False,
    },
}


# ---------------------------------------------------------------------------
# Remote transcription
# ---------------------------------------------------------------------------

def transcribe_remote(audio_data: np.ndarray, sample_rate: int) -> str:
    """Send int16 PCM audio to the Asklaion whisper server (POST /transcribe)."""
    api = ConfigManager.get_config_section('model_options')['api']

    base_url = (api.get('base_url') or '').rstrip('/')
    if not base_url:
        raise RuntimeError('model_options.api.base_url ist leer. '
                           'Bitte client_config.yaml anpassen.')

    url = f'{base_url}/transcribe'
    timeout_s = api.get('timeout_s') or 60

    # TLS verification: prefer pinning to the server's CA cert.
    ca_cert_path = (api.get('ca_cert_path') or '').strip()
    if ca_cert_path:
        if not os.path.isfile(ca_cert_path):
            raise RuntimeError(
                f'CA-Zertifikat nicht gefunden: {ca_cert_path}\n'
                f'Bitte certs/ca.crt vom Server kopieren oder Pfad korrigieren.'
            )
        verify = ca_cert_path
    else:
        # Self-signed cert without pinning - emit a one-time warning.
        verify = False
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        except Exception:
            pass
        ConfigManager.console_print(
            'WARNUNG: TLS-Verifizierung deaktiviert (kein ca_cert_path gesetzt).')

    buffer = io.BytesIO()
    sf.write(buffer, audio_data, sample_rate, format='WAV', subtype='PCM_16')
    buffer.seek(0)

    files = {'file': ('audio.wav', buffer, 'audio/wav')}

    response = requests.post(url, files=files, timeout=timeout_s, verify=verify)
    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError:
        return response.text.strip()

    if isinstance(payload, dict):
        if 'error' in payload:
            raise RuntimeError(f'Server meldet Fehler: {payload["error"]}')
        for key in ('text', 'transcription', 'transcript'):
            if key in payload:
                return str(payload[key])
    return str(payload)


def post_process(transcription: str) -> str:
    transcription = transcription.strip()
    pp = ConfigManager.get_config_section('post_processing')
    if pp.get('remove_trailing_period') and transcription.endswith('.'):
        transcription = transcription[:-1]
    if pp.get('add_trailing_space'):
        transcription += ' '
    if pp.get('remove_capitalization'):
        transcription = transcription.lower()
    return transcription


# ---------------------------------------------------------------------------
# Recording + remote-transcription thread (mirrors src/result_thread.py)
# ---------------------------------------------------------------------------

class RemoteResultThread(QThread):
    statusSignal = pyqtSignal(str)
    resultSignal = pyqtSignal(str)
    audioLevelSignal = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.is_recording = False
        self.is_running = True
        self.sample_rate = None
        self.mutex = QMutex()

    def stop_recording(self):
        self.mutex.lock()
        self.is_recording = False
        self.mutex.unlock()

    def stop(self):
        self.mutex.lock()
        self.is_running = False
        self.mutex.unlock()
        self.statusSignal.emit('idle')
        self.wait()

    def run(self):
        try:
            if not self.is_running:
                return

            self.mutex.lock()
            self.is_recording = True
            self.mutex.unlock()

            self.statusSignal.emit('recording')
            ConfigManager.console_print('Recording...')
            audio_data = self._record_audio()

            if not self.is_running or audio_data is None:
                self.statusSignal.emit('idle')
                return

            self.statusSignal.emit('transcribing')
            ConfigManager.console_print('Sending to server...')

            t0 = time.time()
            try:
                raw = transcribe_remote(audio_data, self.sample_rate)
            except requests.RequestException as exc:
                ConfigManager.console_print(f'Server-Fehler: {exc}')
                self.statusSignal.emit('error')
                self.resultSignal.emit('')
                return
            elapsed = time.time() - t0

            result = post_process(raw)
            ConfigManager.console_print(
                f'Transcription completed in {elapsed:.2f}s: {result!r}')

            if not self.is_running:
                return

            self.statusSignal.emit('idle')
            self.resultSignal.emit(result)

        except Exception:
            traceback.print_exc()
            self.statusSignal.emit('error')
            self.resultSignal.emit('')
        finally:
            self.stop_recording()

    def _record_audio(self):
        recording_options = ConfigManager.get_config_section('recording_options')
        self.sample_rate = recording_options.get('sample_rate') or 16000
        frame_duration_ms = 30
        frame_size = int(self.sample_rate * (frame_duration_ms / 1000.0))
        silence_duration_ms = recording_options.get('silence_duration') or 900
        silence_frames = int(silence_duration_ms / frame_duration_ms)
        initial_frames_to_skip = int(0.15 * self.sample_rate / frame_size)

        recording_mode = recording_options.get('recording_mode') or 'continuous'
        vad = None
        speech_detected = False
        silent_frame_count = 0
        if recording_mode in ('voice_activity_detection', 'continuous'):
            vad = webrtcvad.Vad(2)

        audio_buffer = deque(maxlen=frame_size)
        recording = []
        data_ready = Event()

        def audio_callback(indata, frames, time_info, status):
            if status:
                ConfigManager.console_print(f'Audio callback status: {status}')
            audio_buffer.extend(indata[:, 0])
            data_ready.set()

        with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype='int16',
                            blocksize=frame_size,
                            device=recording_options.get('sound_device'),
                            callback=audio_callback):
            while self.is_running and self.is_recording:
                data_ready.wait()
                data_ready.clear()

                if len(audio_buffer) < frame_size:
                    continue

                frame = np.array(list(audio_buffer), dtype=np.int16)
                audio_buffer.clear()
                recording.extend(frame)

                rms = float(np.sqrt(np.mean((frame.astype(np.float32) / 32768.0) ** 2)))
                if rms > 0:
                    db = 20.0 * math.log10(max(rms, 1e-6))
                    level = (db + 55.0) / 45.0
                    self.audioLevelSignal.emit(max(0.0, min(1.0, level)))
                else:
                    self.audioLevelSignal.emit(0.0)

                if initial_frames_to_skip > 0:
                    initial_frames_to_skip -= 1
                    continue

                if vad:
                    if vad.is_speech(frame.tobytes(), self.sample_rate):
                        silent_frame_count = 0
                        if not speech_detected:
                            ConfigManager.console_print('Speech detected.')
                            speech_detected = True
                    else:
                        silent_frame_count += 1
                    if speech_detected and silent_frame_count > silence_frames:
                        break

        audio_data = np.array(recording, dtype=np.int16)
        duration = len(audio_data) / self.sample_rate
        ConfigManager.console_print(
            f'Recording finished. Size: {audio_data.size} samples, '
            f'Duration: {duration:.2f}s')

        min_duration_ms = recording_options.get('min_duration') or 100
        if (duration * 1000) < min_duration_ms:
            ConfigManager.console_print('Discarded due to being too short.')
            return None
        return audio_data


# ---------------------------------------------------------------------------
# Application (tray-only, mirrors hotkey state machine from src/main.py)
# ---------------------------------------------------------------------------

def _ensure_client_config():
    """Create client_config.yaml on first run with sane defaults."""
    if os.path.isfile(CLIENT_CONFIG_PATH):
        return False
    with open(CLIENT_CONFIG_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(DEFAULT_CLIENT_CONFIG, f, default_flow_style=False,
                  allow_unicode=True, sort_keys=False)
    print(f'Konfigurationsdatei angelegt: {CLIENT_CONFIG_PATH}')
    print('Bitte vor dem naechsten Start anpassen, insbesondere:')
    print('  model_options.api.base_url      (z. B. https://192.168.1.10:8000)')
    print('  model_options.api.ca_cert_path  (Pfad zur certs/ca.crt vom Server)')
    return True


class AsklaionTyperClient(QObject):
    def __init__(self):
        super().__init__()
        self.app = QApplication(sys.argv)

        icon_path = os.path.join(PROJECT_ROOT, 'assets', 'ww-logo.png')
        if os.path.isfile(icon_path):
            self.app.setWindowIcon(QIcon(icon_path))

        # Initialise ConfigManager with the project's existing schema, then
        # overlay the client-specific config on top.
        ConfigManager.initialize()
        ConfigManager._instance.load_user_config(CLIENT_CONFIG_PATH)
        # Force API mode regardless of what is in the file - we are a client.
        ConfigManager.set_config_value(True, 'model_options', 'use_api')

        self._validate_server_config()

        self.input_simulator = InputSimulator()

        self.key_listener = KeyListener()
        self.key_listener.add_callback('on_activate', self.on_activation)
        self.key_listener.add_callback('on_deactivate', self.on_deactivation)

        self.result_thread = None
        self.stopping_continuous = False

        # hold_or_double_tap state machine (identical to src/main.py)
        self._hd_state = 'idle'
        self._hd_press_time = 0.0
        self._hd_tap_timer = QTimer(self)
        self._hd_tap_timer.setSingleShot(True)
        self._hd_tap_timer.timeout.connect(self._on_double_tap_window_expired)

        self.status_window = None
        if HAS_STATUS_WINDOW and not ConfigManager.get_config_value('misc', 'hide_status_window'):
            self.status_window = StatusWindow()

        self.create_tray_icon()
        self.key_listener.start()

        api = ConfigManager.get_config_section('model_options')['api']
        activation_key = ConfigManager.get_config_value('recording_options', 'activation_key')
        self.tray_icon.showMessage(
            'AsklaionTyper Client',
            f'Verbindet zu {api.get("base_url")}\n{activation_key} zum Diktieren.',
            QSystemTrayIcon.Information,
            3500,
        )

    # ---------------- Setup helpers ----------------

    def _validate_server_config(self):
        api = ConfigManager.get_config_section('model_options')['api']
        base_url = (api.get('base_url') or '').strip()
        if not base_url:
            QMessageBox.critical(
                None,
                'AsklaionTyper Client',
                f'Server-URL fehlt.\n\nBitte {CLIENT_CONFIG_PATH} bearbeiten und '
                f'unter model_options.api.base_url die URL des Whisper-Servers '
                f'eintragen (z. B. https://192.168.1.10:8000).'
            )
            sys.exit(1)

    def create_tray_icon(self):
        icon_path = os.path.join(PROJECT_ROOT, 'assets', 'ww-logo.png')
        icon = QIcon(icon_path) if os.path.isfile(icon_path) else QIcon()
        self.tray_icon = QSystemTrayIcon(icon, self.app)

        menu = QMenu()

        api = ConfigManager.get_config_section('model_options')['api']
        info_action = QAction(f'Server: {api.get("base_url")}', self.app)
        info_action.setEnabled(False)
        menu.addAction(info_action)

        menu.addSeparator()

        edit_action = QAction('Edit client_config.yaml', self.app)
        edit_action.triggered.connect(self._open_config_file)
        menu.addAction(edit_action)

        restart_action = QAction('Restart Client', self.app)
        restart_action.triggered.connect(self.restart_app)
        menu.addAction(restart_action)

        menu.addSeparator()

        exit_action = QAction('Exit', self.app)
        exit_action.triggered.connect(self.exit_app)
        menu.addAction(exit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def _open_config_file(self):
        if sys.platform == 'win32':
            os.startfile(CLIENT_CONFIG_PATH)  # noqa: SIM115
        elif sys.platform == 'darwin':
            QProcess.startDetached('open', [CLIENT_CONFIG_PATH])
        else:
            QProcess.startDetached('xdg-open', [CLIENT_CONFIG_PATH])

    # ---------------- Lifecycle ----------------

    def cleanup(self):
        if getattr(self, 'key_listener', None):
            self.key_listener.stop()
        if getattr(self, 'input_simulator', None):
            self.input_simulator.cleanup()

    def exit_app(self):
        self.cleanup()
        QApplication.quit()

    def restart_app(self):
        self.cleanup()
        QApplication.quit()
        QProcess.startDetached(sys.executable, sys.argv)

    # ---------------- Hotkey handling (1:1 from src/main.py) ----------------

    def on_activation(self):
        recording_mode = ConfigManager.get_config_value('recording_options', 'recording_mode')

        if recording_mode == 'hold_or_double_tap':
            self._on_activation_hybrid()
            return

        if self.result_thread and self.result_thread.isRunning():
            if recording_mode == 'press_to_toggle':
                self.result_thread.stop_recording()
            elif recording_mode == 'continuous':
                self.stopping_continuous = True
                self.result_thread.stop_recording()
            return

        self.start_result_thread()

    def on_deactivation(self):
        recording_mode = ConfigManager.get_config_value('recording_options', 'recording_mode')

        if recording_mode == 'hold_or_double_tap':
            self._on_deactivation_hybrid()
            return

        if recording_mode == 'hold_to_record':
            if self.result_thread and self.result_thread.isRunning():
                self.result_thread.stop_recording()

    def _on_activation_hybrid(self):
        if self._hd_state == 'idle':
            self._hd_press_time = time.monotonic()
            self._hd_state = 'hold'
            self.start_result_thread()
        elif self._hd_state == 'tap_armed':
            self._hd_tap_timer.stop()
            self._hd_state = 'toggle'
        elif self._hd_state == 'toggle':
            self._hd_state = 'idle'
            if self.result_thread and self.result_thread.isRunning():
                self.result_thread.stop_recording()

    def _on_deactivation_hybrid(self):
        if self._hd_state != 'hold':
            return
        held_for = time.monotonic() - self._hd_press_time
        hold_threshold_s = (ConfigManager.get_config_value(
            'recording_options', 'hold_threshold_ms') or 350) / 1000.0
        if held_for >= hold_threshold_s:
            self._hd_state = 'idle'
            if self.result_thread and self.result_thread.isRunning():
                self.result_thread.stop_recording()
        else:
            self._hd_state = 'tap_armed'
            window_ms = ConfigManager.get_config_value(
                'recording_options', 'double_tap_window_ms') or 450
            self._hd_tap_timer.start(int(window_ms))

    def _on_double_tap_window_expired(self):
        if self._hd_state != 'tap_armed':
            return
        self._hd_state = 'idle'
        if self.result_thread and self.result_thread.isRunning():
            self.result_thread.stop_recording()

    # ---------------- Result thread ----------------

    def start_result_thread(self):
        if self.result_thread and self.result_thread.isRunning():
            return

        self.result_thread = RemoteResultThread()
        if self.status_window is not None:
            self.result_thread.statusSignal.connect(self.status_window.updateStatus)
            self.result_thread.audioLevelSignal.connect(self.status_window.setAudioLevel)
            self.status_window.closeSignal.connect(self.stop_result_thread)
        self.result_thread.resultSignal.connect(self.on_transcription_complete)
        self.result_thread.start()

    def stop_result_thread(self):
        if self.result_thread and self.result_thread.isRunning():
            self.result_thread.stop()

    def on_transcription_complete(self, result):
        if result:
            self.input_simulator.typewrite(result)

        if ConfigManager.get_config_value('misc', 'noise_on_completion'):
            try:
                from audioplayer import AudioPlayer
                AudioPlayer(os.path.join(PROJECT_ROOT, 'assets', 'beep.wav')).play(block=True)
            except Exception:
                pass

        if ConfigManager.get_config_value('recording_options', 'recording_mode') == 'continuous':
            if self.stopping_continuous:
                self.stopping_continuous = False
                self.key_listener.start()
            else:
                self.start_result_thread()
        else:
            self.key_listener.start()

    def run(self):
        sys.exit(self.app.exec_())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print('Starting AsklaionTyper Client...')
    if _ensure_client_config():
        # First run: config was just created. Let user edit it before starting.
        print('Beim naechsten Start verbindet sich der Client zum Server.')
        return

    client = AsklaionTyperClient()
    client.run()


if __name__ == '__main__':
    main()
