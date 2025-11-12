import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-this'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ===== THÊM: DATABASE CONNECTION POOL SETTINGS =====
    # Quan trọng để tránh lỗi "SSL SYSCALL error: EOF detected"
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,  # Số connection tối đa trong pool
        'pool_recycle': 3600,  # Recycle connection sau 1 giờ
        'pool_pre_ping': True,  # Kiểm tra connection trước khi dùng
        'max_overflow': 5,  # Số connection tạm thời thêm
        'pool_timeout': 30,  # Timeout khi chờ connection
        'connect_args': {
            'connect_timeout': 10,  # Timeout khi kết nối
        }
    }
    # ===== END =====

    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_FILE_SIZE', 15728640))
    ALLOWED_EXTENSIONS = set(os.environ.get('ALLOWED_EXTENSIONS', 'pdf,docx,xlsx,png,jpg,jpeg').split(','))
    WTF_CSRF_ENABLED = True