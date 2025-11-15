"""
Text-to-Speech Service using Google Cloud TTS or gTTS
CHẤT LƯỢNG CAO - Giống Google Dịch 100%
"""

from flask import Blueprint, jsonify, send_file, request
from flask_login import login_required, current_user
import os
import tempfile
import hashlib
from pathlib import Path

# TÙY CHỌN: Dùng gTTS (miễn phí, không cần API key) hoặc Google Cloud TTS (trả phí, tốt hơn)
TTS_METHOD = os.environ.get('TTS_METHOD', 'gtts')  # 'gtts' hoặc 'google_cloud'

if TTS_METHOD == 'google_cloud':
    try:
        from google.cloud import texttospeech

        GOOGLE_CLOUD_AVAILABLE = True
    except ImportError:
        GOOGLE_CLOUD_AVAILABLE = False
        TTS_METHOD = 'gtts'  # Fallback
else:
    GOOGLE_CLOUD_AVAILABLE = False

try:
    from gtts import gTTS

    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

bp = Blueprint('tts', __name__)

# Cache directory
CACHE_DIR = Path(tempfile.gettempdir()) / 'tts_cache'
CACHE_DIR.mkdir(exist_ok=True)


def get_cache_filename(text, speed=1.0):
    """Tạo filename cache dựa trên text và speed"""
    key = f"{text}_{speed}".encode('utf-8')
    hash_key = hashlib.md5(key).hexdigest()
    return CACHE_DIR / f"{hash_key}.mp3"


def generate_tts_gtts(text, speed=1.0):
    """
    Generate TTS using gTTS (Google Text-to-Speech - FREE)

    Ưu điểm:
    - MIỄN PHÍ 100%
    - Chất lượng tốt (dùng Google TTS API)
    - Không cần API key

    Nhược điểm:
    - Cần internet
    - Không điều chỉnh được speed (sẽ xử lý bằng frontend)
    """
    if not GTTS_AVAILABLE:
        raise Exception("gTTS not installed. Run: pip install gTTS")

    cache_file = get_cache_filename(text, speed)

    # Check cache
    if cache_file.exists():
        print(f"✅ TTS Cache hit: {text[:30]}...")
        return cache_file

    print(f"🔊 Generating TTS with gTTS: {text[:30]}...")

    try:
        # Generate speech
        tts = gTTS(text=text, lang='vi', slow=False)

        # Save to cache
        tts.save(str(cache_file))

        print(f"✅ TTS generated successfully")
        return cache_file

    except Exception as e:
        print(f"❌ Error generating TTS: {e}")
        raise


def generate_tts_google_cloud(text, speed=1.0):
    """
    Generate TTS using Google Cloud Text-to-Speech API (PAID)

    Ưu điểm:
    - CHẤT LƯỢNG CỰC CAO
    - Điều chỉnh được speed, pitch, voice
    - Nhiều giọng đọc

    Nhược điểm:
    - CẦN TRẢ PHÍ (nhưng rẻ: $4/1 triệu ký tự)
    - Cần setup API key
    """
    if not GOOGLE_CLOUD_AVAILABLE:
        raise Exception("Google Cloud TTS not available. Run: pip install google-cloud-texttospeech")

    cache_file = get_cache_filename(text, speed)

    # Check cache
    if cache_file.exists():
        print(f"✅ TTS Cache hit: {text[:30]}...")
        return cache_file

    print(f"🔊 Generating TTS with Google Cloud: {text[:30]}...")

    try:
        client = texttospeech.TextToSpeechClient()

        synthesis_input = texttospeech.SynthesisInput(text=text)

        # Voice config - dùng giọng WaveNet (chất lượng cao)
        voice = texttospeech.VoiceSelectionParams(
            language_code="vi-VN",
            name="vi-VN-Wavenet-A",  # Giọng nữ, chất lượng cao
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speed,
            pitch=0.0,
            volume_gain_db=0.0
        )

        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        # Save to cache
        with open(cache_file, 'wb') as out:
            out.write(response.audio_content)

        print(f"✅ TTS generated successfully")
        return cache_file

    except Exception as e:
        print(f"❌ Error generating TTS: {e}")
        raise


@bp.route('/speak', methods=['POST'])
@login_required
def speak():
    """
    API endpoint to generate speech from text

    Request JSON:
    {
        "text": "Bạn có công việc mới",
        "speed": 1.0
    }

    Response: MP3 audio file
    """
    data = request.get_json()

    if not data or 'text' not in data:
        return jsonify({'error': 'Missing text parameter'}), 400

    text = data['text'].strip()
    speed = float(data.get('speed', 1.0))

    if not text:
        return jsonify({'error': 'Empty text'}), 400

    # Giới hạn độ dài text (tránh abuse)
    if len(text) > 500:
        return jsonify({'error': 'Text too long (max 500 characters)'}), 400

    try:
        # Generate TTS
        if TTS_METHOD == 'google_cloud' and GOOGLE_CLOUD_AVAILABLE:
            audio_file = generate_tts_google_cloud(text, speed)
        elif GTTS_AVAILABLE:
            audio_file = generate_tts_gtts(text, speed)
        else:
            return jsonify({'error': 'No TTS service available'}), 500

        # Return audio file
        return send_file(
            audio_file,
            mimetype='audio/mpeg',
            as_attachment=False,
            download_name='speech.mp3'
        )

    except Exception as e:
        print(f"❌ TTS Error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@bp.route('/test', methods=['GET'])
@login_required
def test():
    """Test endpoint"""
    return jsonify({
        'tts_method': TTS_METHOD,
        'gtts_available': GTTS_AVAILABLE,
        'google_cloud_available': GOOGLE_CLOUD_AVAILABLE,
        'cache_dir': str(CACHE_DIR),
        'cache_files': len(list(CACHE_DIR.glob('*.mp3')))
    })


@bp.route('/clear-cache', methods=['POST'])
@login_required
def clear_cache():
    """Clear TTS cache (admin only)"""
    if current_user.role != 'director':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        count = 0
        for f in CACHE_DIR.glob('*.mp3'):
            f.unlink()
            count += 1

        return jsonify({
            'success': True,
            'deleted_files': count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500