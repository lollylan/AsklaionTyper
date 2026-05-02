import io
import os
import numpy as np
import requests
import soundfile as sf
from faster_whisper import WhisperModel
from openai import OpenAI

from utils import ConfigManager

def create_local_model():
    """
    Create a local model using the faster-whisper library.
    """
    ConfigManager.console_print('Creating local model...')
    local_model_options = ConfigManager.get_config_section('model_options')['local']
    compute_type = local_model_options['compute_type']
    model_path = local_model_options.get('model_path')

    if compute_type == 'int8':
        device = 'cpu'
        ConfigManager.console_print('Using int8 quantization, forcing CPU usage.')
    else:
        device = local_model_options['device']

    try:
        if model_path:
            ConfigManager.console_print(f'Loading model from: {model_path}')
            model = WhisperModel(model_path,
                                 device=device,
                                 compute_type=compute_type,
                                 download_root=None)  # Prevent automatic download
        else:
            model = WhisperModel(local_model_options['model'],
                                 device=device,
                                 compute_type=compute_type)
    except Exception as e:
        ConfigManager.console_print(f'Error initializing WhisperModel: {e}')
        ConfigManager.console_print('Falling back to CPU.')
        model = WhisperModel(model_path or local_model_options['model'],
                             device='cpu',
                             compute_type=compute_type,
                             download_root=None if model_path else None)

    ConfigManager.console_print('Local model created.')

    try:
        ConfigManager.console_print('Warming up model...')
        warmup_audio = np.zeros(16000, dtype=np.float32)
        list(model.transcribe(audio=warmup_audio, language=local_model_options.get('language') or None)[0])
        ConfigManager.console_print('Model warmed up.')
    except Exception as e:
        ConfigManager.console_print(f'Warmup skipped: {e}')

    return model

def transcribe_local(audio_data, local_model=None):
    """
    Transcribe an audio file using a local model.
    """
    if not local_model:
        local_model = create_local_model()
    model_options = ConfigManager.get_config_section('model_options')

    # Convert int16 to float32
    audio_data_float = audio_data.astype(np.float32) / 32768.0

    response = local_model.transcribe(audio=audio_data_float,
                                      language=model_options['common']['language'],
                                      initial_prompt=model_options['common']['initial_prompt'],
                                      condition_on_previous_text=model_options['local']['condition_on_previous_text'],
                                      temperature=model_options['common']['temperature'],
                                      vad_filter=model_options['local']['vad_filter'],)
    return ''.join([segment.text for segment in list(response[0])])

def transcribe_api(audio_data):
    """
    Transcribe an audio file using the OpenAI API.
    """
    model_options = ConfigManager.get_config_section('model_options')
    client = OpenAI(
        api_key=os.getenv('OPENAI_API_KEY') or None,
        base_url=model_options['api']['base_url'] or 'https://api.openai.com/v1'
    )

    # Convert numpy array to WAV file
    byte_io = io.BytesIO()
    sample_rate = ConfigManager.get_config_section('recording_options').get('sample_rate') or 16000
    sf.write(byte_io, audio_data, sample_rate, format='wav')
    byte_io.seek(0)

    response = client.audio.transcriptions.create(
        model=model_options['api']['model'],
        file=('audio.wav', byte_io, 'audio/wav'),
        language=model_options['common']['language'],
        prompt=model_options['common']['initial_prompt'],
        temperature=model_options['common']['temperature'],
    )
    return response.text

def transcribe_asklaion(audio_data):
    """
    Transcribe audio via the Asklaion whisper server (server_GPU_CUDA_Parallel.py).
    Endpoint: POST {base_url}/transcribe, multipart/form-data with file=audio.wav,
    HTTPS with self-signed CA pinned through model_options.api.ca_cert_path.
    """
    api = ConfigManager.get_config_section('model_options')['api']
    base_url = (api.get('base_url') or '').rstrip('/')
    if not base_url:
        raise RuntimeError(
            'Server-URL fehlt. Bitte unter Settings > Model options > '
            'Base url die URL des Asklaion-Servers eintragen '
            '(z. B. https://192.168.178.131:8000).'
        )

    sample_rate = ConfigManager.get_config_section('recording_options').get('sample_rate') or 16000
    buffer = io.BytesIO()
    sf.write(buffer, audio_data, sample_rate, format='WAV', subtype='PCM_16')
    buffer.seek(0)

    ca_cert_path = (api.get('ca_cert_path') or '').strip()
    if ca_cert_path:
        if not os.path.isfile(ca_cert_path):
            raise RuntimeError(
                f'CA-Zertifikat nicht gefunden: {ca_cert_path}\n'
                f'Bitte certs/ca.crt vom Server kopieren und Pfad in den '
                f'Settings korrigieren.'
            )
        verify = ca_cert_path
    else:
        verify = False
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        except Exception:
            pass
        ConfigManager.console_print(
            'WARNUNG: TLS-Verifizierung deaktiviert (kein ca_cert_path gesetzt).')

    response = requests.post(
        f'{base_url}/transcribe',
        files={'file': ('audio.wav', buffer, 'audio/wav')},
        timeout=60,
        verify=verify,
    )
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

def post_process_transcription(transcription):
    """
    Apply post-processing to the transcription.
    """
    transcription = transcription.strip()
    post_processing = ConfigManager.get_config_section('post_processing')
    if post_processing['remove_trailing_period'] and transcription.endswith('.'):
        transcription = transcription[:-1]
    if post_processing['add_trailing_space']:
        transcription += ' '
    if post_processing['remove_capitalization']:
        transcription = transcription.lower()

    return transcription

def transcribe(audio_data, local_model=None):
    """
    Transcribe audio data using one of three backends, depending on config:
    - local faster-whisper (use_api: false)
    - OpenAI-compatible API (use_api: true, api.provider: openai)
    - Asklaion server (use_api: true, api.provider: asklaion)
    """
    if audio_data is None:
        return ''

    if ConfigManager.get_config_value('model_options', 'use_api'):
        provider = ConfigManager.get_config_value('model_options', 'api', 'provider') or 'openai'
        if provider == 'asklaion':
            transcription = transcribe_asklaion(audio_data)
        else:
            transcription = transcribe_api(audio_data)
    else:
        transcription = transcribe_local(audio_data, local_model)

    return post_process_transcription(transcription)

