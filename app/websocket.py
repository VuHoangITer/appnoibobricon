"""
WebSocket handler for real-time features
"""
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import request

socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')


@socketio.on('connect')
def handle_connect():
    """Client kết nối"""
    print(f'✅ Client connected: {request.sid}')


@socketio.on('disconnect')
def handle_disconnect():
    """Client ngắt kết nối"""
    print(f'❌ Client disconnected: {request.sid}')


@socketio.on('join_news')
def handle_join_news(data):
    """Client join vào room của bài đăng cụ thể"""
    news_id = data.get('news_id')
    room = f'news_{news_id}'
    join_room(room)
    print(f'👥 Client {request.sid} joined {room}')
    emit('joined', {'news_id': news_id})


@socketio.on('leave_news')
def handle_leave_news(data):
    """Client rời room"""
    news_id = data.get('news_id')
    room = f'news_{news_id}'
    leave_room(room)
    print(f'👋 Client {request.sid} left {room}')


def broadcast_comment_added(news_id, comment_data):
    """Broadcast comment mới đến tất cả clients trong room"""
    socketio.emit('comment_added', comment_data, room=f'news_{news_id}')
    print(f'📢 Broadcast comment_added to news_{news_id}')


def broadcast_comment_deleted(news_id, comment_id):
    """Broadcast comment bị xóa"""
    socketio.emit('comment_deleted', {'comment_id': comment_id}, room=f'news_{news_id}')
    print(f'📢 Broadcast comment_deleted to news_{news_id}')