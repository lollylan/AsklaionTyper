"""Generate the AsklaionTyper logo via kie.ai (Nano Banana Pro).

Reads KIE_API_KEY from .env (gitignored). Replaces assets/ww-logo.png and
assets/ww-logo.ico with a freshly generated 1:1 squircle icon.

Run with the project's venv:
    venv\\Scripts\\python.exe scripts\\generate_logo_kie.py
"""

import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv
from PIL import Image


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(PROJECT_ROOT, 'assets')
PNG_PATH = os.path.join(ASSETS_DIR, 'ww-logo.png')
ICO_PATH = os.path.join(ASSETS_DIR, 'ww-logo.ico')

CREATE_URL = 'https://api.kie.ai/api/v1/jobs/createTask'
POLL_URL = 'https://api.kie.ai/api/v1/jobs/recordInfo'

MODEL = 'nano-banana-pro'

PROMPT = (
    'A premium, modern mobile app icon for a voice-to-text dictation app '
    'named "AsklaionTyper". Squircle (iOS-style rounded square) shape filling '
    'the entire canvas. Background: a deep, sophisticated dark navy-blue '
    'gradient — bright cobalt-blue at the top fading into near-black at the '
    'bottom — with a soft, glossy inner glow at the top edge for depth. In '
    'the centre, a single, large, bold capital letter "A" rendered in a '
    'clean, geometric sans-serif typeface (Inter Black, SF Pro Display Bold, '
    'or similar) in pure white. Just below the letter "A", three small '
    'rounded vertical bars (audio level indicator), light-blue colour '
    '(#9CC7FF), of varying heights — short, tall, short — perfectly centred. '
    'Crisp clean edges, professional, native macOS / iOS app-icon look, no '
    'text, no shadows outside the icon, no rim, no bezel — just the icon '
    'itself, perfectly framed, 1:1 square composition, ultra high quality.'
)


def _post(url, payload, key):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode('utf-8'))


def _get(url, key):
    req = urllib.request.Request(
        url,
        headers={'Authorization': f'Bearer {key}'},
        method='GET',
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))


def generate_via_kie(key):
    print('Submitting generation task to kie.ai (model: nano-banana-pro) ...')
    create = _post(
        CREATE_URL,
        {
            'model': MODEL,
            'input': {
                'prompt': PROMPT,
                'image_input': [],
                'aspect_ratio': '1:1',
                'resolution': '2K',
                'output_format': 'png',
            },
        },
        key,
    )
    if create.get('code') != 200:
        raise RuntimeError(f'createTask failed: {create}')
    task_id = create['data']['taskId']
    print(f'  taskId: {task_id}')

    deadline = time.time() + 300  # 5 min hard timeout
    while True:
        if time.time() > deadline:
            raise TimeoutError('Generation took longer than 5 minutes.')
        time.sleep(3)
        detail = _get(f'{POLL_URL}?taskId={task_id}', key)
        if detail.get('code') != 200:
            raise RuntimeError(f'recordInfo failed: {detail}')
        data = detail['data']
        state = data.get('state')
        print(f'  state: {state}')
        if state == 'success':
            result = json.loads(data['resultJson'])
            urls = result.get('resultUrls', [])
            if not urls:
                raise RuntimeError(f'No resultUrls in {result}')
            return urls[0]
        if state in ('fail', 'failed', 'error'):
            raise RuntimeError(data.get('failMsg', 'unknown failure'))


def download(url):
    print(f'Downloading {url} ...')
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/124.0 Safari/537.36',
            'Accept': 'image/png,image/*,*/*;q=0.8',
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def save_assets(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
    print(f'  source image: {img.size[0]}x{img.size[1]} {img.mode}')

    img.save(PNG_PATH, 'PNG')
    print(f'  wrote {PNG_PATH}')

    sizes = [256, 128, 64, 48, 32, 24, 16]
    icons = [img.resize((s, s), Image.LANCZOS) for s in sizes]
    icons[0].save(ICO_PATH, format='ICO', sizes=[(s, s) for s in sizes])
    print(f'  wrote {ICO_PATH}  (sizes: {sizes})')


def main():
    load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
    key = os.environ.get('KIE_API_KEY', '').strip().strip("'\"")
    if not key:
        print('ERROR: KIE_API_KEY not set in .env', file=sys.stderr)
        sys.exit(1)

    try:
        url = generate_via_kie(key)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f'HTTP error {e.code}: {body}', file=sys.stderr)
        sys.exit(2)

    raw = download(url)
    save_assets(raw)
    print('Done.')


if __name__ == '__main__':
    main()
