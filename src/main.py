import os
import sys
import time
from audioplayer import AudioPlayer
from pynput.keyboard import Controller
from PyQt5.QtCore import QObject, QProcess, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QMessageBox

from key_listener import KeyListener
from result_thread import ResultThread
from ui.main_window import MainWindow
from ui.settings_window import SettingsWindow
from ui.status_window import StatusWindow
from transcription import create_local_model
from input_simulation import InputSimulator
from utils import ConfigManager


class AsklaionTyperApp(QObject):
    def __init__(self):
        """
        Initialize the application, opening settings window if no configuration file is found.
        """
        super().__init__()
        self.app = QApplication(sys.argv)
        self.app.setWindowIcon(QIcon(os.path.join('assets', 'ww-logo.png')))

        ConfigManager.initialize()

        self.settings_window = SettingsWindow()
        self.settings_window.settings_closed.connect(self.on_settings_closed)
        self.settings_window.settings_saved.connect(self.restart_app)

        if ConfigManager.config_file_exists():
            self.initialize_components()
        else:
            print('No valid configuration file found. Opening settings window...')
            self.settings_window.show()

    def initialize_components(self):
        """
        Initialize the components of the application.
        """
        self.input_simulator = InputSimulator()

        self.key_listener = KeyListener()
        self.key_listener.add_callback("on_activate", self.on_activation)
        self.key_listener.add_callback("on_deactivate", self.on_deactivation)

        model_options = ConfigManager.get_config_section('model_options')
        model_path = model_options.get('local', {}).get('model_path')
        self.local_model = create_local_model() if not model_options.get('use_api') else None

        self.result_thread = None
        self.stopping_continuous = False

        # State for hold_or_double_tap mode
        self._hd_state = 'idle'  # 'idle' | 'hold' | 'tap_armed' | 'toggle'
        self._hd_press_time = 0.0
        self._hd_tap_timer = QTimer(self)
        self._hd_tap_timer.setSingleShot(True)
        self._hd_tap_timer.timeout.connect(self._on_double_tap_window_expired)

        self.main_window = MainWindow()
        self.main_window.openSettings.connect(self.settings_window.show)
        self.main_window.startListening.connect(self.key_listener.start)
        self.main_window.closeApp.connect(self.exit_app)

        if not ConfigManager.get_config_value('misc', 'hide_status_window'):
            self.status_window = StatusWindow()

        self.create_tray_icon()

        # If a config exists, the user has already done the initial setup —
        # start the key listener silently and live in the system tray.
        # Otherwise, show the main window so the user can press "Start".
        if ConfigManager.config_file_exists():
            self.key_listener.start()
            self.tray_icon.showMessage(
                'AsklaionTyper',
                'Läuft im Hintergrund. Strg+Shift+Leertaste zum Diktieren.',
                QSystemTrayIcon.Information,
                3000,
            )
        else:
            self.main_window.show()

    def create_tray_icon(self):
        """
        Create the system tray icon and its context menu.
        """
        self.tray_icon = QSystemTrayIcon(QIcon(os.path.join('assets', 'ww-logo.png')), self.app)

        tray_menu = QMenu()

        show_action = QAction('AsklaionTyper Main Menu', self.app)
        show_action.triggered.connect(self.main_window.show)
        tray_menu.addAction(show_action)

        settings_action = QAction('Open Settings', self.app)
        settings_action.triggered.connect(self.settings_window.show)
        tray_menu.addAction(settings_action)

        exit_action = QAction('Exit', self.app)
        exit_action.triggered.connect(self.exit_app)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def cleanup(self):
        if self.key_listener:
            self.key_listener.stop()
        if self.input_simulator:
            self.input_simulator.cleanup()

    def exit_app(self):
        """
        Exit the application.
        """
        self.cleanup()
        QApplication.quit()

    def restart_app(self):
        """Restart the application to apply the new settings."""
        self.cleanup()
        QApplication.quit()
        QProcess.startDetached(sys.executable, sys.argv)

    def on_settings_closed(self):
        """
        If settings is closed without saving on first run, initialize the components with default values.
        """
        if not os.path.exists(os.path.join('src', 'config.yaml')):
            QMessageBox.information(
                self.settings_window,
                'Using Default Values',
                'Settings closed without saving. Default values are being used.'
            )
            self.initialize_components()

    def on_activation(self):
        """
        Called when the activation key combination is pressed.
        """
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
        """
        Called when the activation key combination is released.
        """
        recording_mode = ConfigManager.get_config_value('recording_options', 'recording_mode')

        if recording_mode == 'hold_or_double_tap':
            self._on_deactivation_hybrid()
            return

        if recording_mode == 'hold_to_record':
            if self.result_thread and self.result_thread.isRunning():
                self.result_thread.stop_recording()

    # ------------------------------------------------------------------
    # hold_or_double_tap state machine
    # ------------------------------------------------------------------
    # State diagram:
    #   idle      --press--> hold (recording starts)
    #   hold      --release after >= hold_threshold--> idle (transcribe)
    #   hold      --release before  hold_threshold-->  tap_armed (timer running)
    #   tap_armed --press within window--> toggle
    #   tap_armed --timer expires--> idle (transcribe; treat short tap as hold)
    #   toggle    --press--> idle (transcribe)
    #   toggle    --release--> ignored

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
        # When state is 'hold' a press without a release shouldn't happen on
        # a sane key listener; treat as no-op.

    def _on_deactivation_hybrid(self):
        if self._hd_state != 'hold':
            return  # only the first release after a press matters

        held_for = time.monotonic() - self._hd_press_time
        hold_threshold_s = (ConfigManager.get_config_value(
            'recording_options', 'hold_threshold_ms') or 350) / 1000.0

        if held_for >= hold_threshold_s:
            # Genuine hold: stop and transcribe immediately.
            self._hd_state = 'idle'
            if self.result_thread and self.result_thread.isRunning():
                self.result_thread.stop_recording()
        else:
            # Short tap: keep recording, wait for a possible second tap.
            self._hd_state = 'tap_armed'
            window_ms = ConfigManager.get_config_value(
                'recording_options', 'double_tap_window_ms') or 450
            self._hd_tap_timer.start(int(window_ms))

    def _on_double_tap_window_expired(self):
        if self._hd_state != 'tap_armed':
            return
        # No second tap arrived. Treat as a short hold and transcribe.
        self._hd_state = 'idle'
        if self.result_thread and self.result_thread.isRunning():
            self.result_thread.stop_recording()

    def start_result_thread(self):
        """
        Start the result thread to record audio and transcribe it.
        """
        if self.result_thread and self.result_thread.isRunning():
            return

        self.result_thread = ResultThread(self.local_model)
        if not ConfigManager.get_config_value('misc', 'hide_status_window'):
            self.result_thread.statusSignal.connect(self.status_window.updateStatus)
            self.result_thread.audioLevelSignal.connect(self.status_window.setAudioLevel)
            self.status_window.closeSignal.connect(self.stop_result_thread)
        self.result_thread.resultSignal.connect(self.on_transcription_complete)
        self.result_thread.start()

    def stop_result_thread(self):
        """
        Stop the result thread.
        """
        if self.result_thread and self.result_thread.isRunning():
            self.result_thread.stop()

    def on_transcription_complete(self, result):
        """
        When the transcription is complete, type the result and start listening for the activation key again.
        """
        self.input_simulator.typewrite(result)

        if ConfigManager.get_config_value('misc', 'noise_on_completion'):
            AudioPlayer(os.path.join('assets', 'beep.wav')).play(block=True)

        if ConfigManager.get_config_value('recording_options', 'recording_mode') == 'continuous':
            if self.stopping_continuous:
                self.stopping_continuous = False
                self.key_listener.start()
            else:
                self.start_result_thread()
        else:
            self.key_listener.start()

    def run(self):
        """
        Start the application.
        """
        sys.exit(self.app.exec_())


if __name__ == '__main__':
    app = AsklaionTyperApp()
    app.run()
