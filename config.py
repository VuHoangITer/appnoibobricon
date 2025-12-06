import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-this'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 5,
        'pool_timeout': 30,
        'connect_args': {
            'connect_timeout': 10,
        }
    }

    basedir = os.path.abspath(os.path.dirname(__file__))
    _upload_folder_env = os.environ.get('UPLOAD_FOLDER')
    if _upload_folder_env and os.path.isabs(_upload_folder_env):
        UPLOAD_FOLDER = _upload_folder_env
    else:
        UPLOAD_FOLDER = os.path.join(basedir, 'app', 'uploads')

    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_FILE_SIZE', 15728640))
    ALLOWED_EXTENSIONS = set(os.environ.get('ALLOWED_EXTENSIONS', 'pdf,docx,xlsx,png,jpg,jpeg').split(','))
    WTF_CSRF_ENABLED = True
    VERSION = '2.5.6'

    #  AI Summary - Groq
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY') or 'your-groq-api-key-here'
    AI_TIMEOUT = 10