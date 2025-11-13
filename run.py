#!/usr/bin/env python
"""
Run script for Flask application with SocketIO support
Usage: python run.py (development) or gunicorn run:app (production)
"""

from app import create_app, db
from app.websocket import socketio  # THÊM: Import socketio
import os

# Tạo Flask app instance
app = create_app()

# Tạo thư mục uploads khi khởi động (cho cả development và production)
upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
if not os.path.exists(upload_folder):
    os.makedirs(upload_folder)
    print(f"Created upload folder: {upload_folder}")


@app.cli.command()
def init_db():
    """Initialize the database."""
    db.create_all()
    print("Database initialized!")


if __name__ == '__main__':
    # Chỉ chạy development server khi chạy trực tiếp file này
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'

    print("=" * 50)
    print(f"Starting Flask application with SocketIO...")
    print(f"Environment: {os.environ.get('FLASK_ENV', 'production')}")
    print(f"Debug mode: {debug}")
    print(f"Port: {port}")
    print(f"URL: http://localhost:{port}")
    print("=" * 50)

    # THAY ĐỔI: Dùng socketio.run thay vì app.run
    socketio.run(
        app,
        debug=debug,
        host='0.0.0.0',
        port=port,
        allow_unsafe_werkzeug=True
    )