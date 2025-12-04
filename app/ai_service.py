from groq import Groq
from flask import current_app
import time


def summarize_description(long_text, max_words=50):
    """
    Tóm tắt mô tả dài thành bản ngắn gọn bằng Groq AI
    Có timeout để tránh block quá lâu

    Args:
        long_text (str): Văn bản cần tóm tắt
        max_words (int): Số từ tối đa cho bản tóm tắt

    Returns:
        dict: {
            'success': bool,
            'summary': str (nếu thành công),
            'error': str (nếu lỗi)
        }
    """
    try:
        api_key = current_app.config.get('GROQ_API_KEY')
        timeout = current_app.config.get('AI_TIMEOUT', 10)

        if not api_key or api_key == 'your-groq-api-key-here':
            return {
                'success': False,
                'error': 'Chưa cấu hình Groq API key. Vui lòng liên hệ quản trị viên.'
            }

        # ✅ CACHE: Nếu văn bản quá ngắn, không cần tóm tắt
        word_count = len(long_text.split())
        if word_count <= 30:
            return {
                'success': False,
                'error': 'Văn bản quá ngắn, không cần tóm tắt'
            }

        client = Groq(api_key=api_key)

        prompt = f"""Tóm tắt ngắn gọn nội dung sau thành mô tả công việc chuyên nghiệp, KHÔNG QUÁ {max_words} từ tiếng Việt:

{long_text}

Yêu cầu:
- Giữ thông tin quan trọng
- Loại bỏ chi tiết thừa
- Viết ngắn gọn, súc tích
- CHỈ TRẢ VỀ BẢN TÓM TẮT

Tóm tắt:"""

        start_time = time.time()

        # ✅ SỬ DỤNG MODEL MỚI NHẤT (LLAMA 3.3 70B - FREE)
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="llama-3.3-70b-versatile",  # ✅ MODEL MỚI NHẤT
            temperature=0.2,
            max_tokens=250,
            top_p=0.9,
            stream=False,
            timeout=timeout
        )

        elapsed = time.time() - start_time
        summary = chat_completion.choices[0].message.content.strip()

        # Log performance (optional)
        print(f"[AI] Summarized in {elapsed:.2f}s - {word_count} → {len(summary.split())} words")

        return {
            'success': True,
            'summary': summary,
            'elapsed': round(elapsed, 2)
        }

    except Exception as e:
        error_msg = str(e)

        # ✅ XỬ LÝ TIMEOUT
        if 'timeout' in error_msg.lower():
            return {
                'success': False,
                'error': 'AI mất quá nhiều thời gian. Vui lòng thử lại.'
            }

        # ✅ XỬ LÝ RATE LIMIT
        if 'rate limit' in error_msg.lower():
            return {
                'success': False,
                'error': 'Quá nhiều yêu cầu. Vui lòng đợi 1 phút rồi thử lại.'
            }

        # ✅ XỬ LÝ MODEL DEPRECATED
        if 'decommissioned' in error_msg.lower() or 'deprecated' in error_msg.lower():
            return {
                'success': False,
                'error': 'Model AI đã lỗi thời. Vui lòng liên hệ quản trị viên để cập nhật.'
            }

        return {
            'success': False,
            'error': f'Lỗi AI: {error_msg}'
        }