"""
Server-Sent Events (SSE) Blueprint - OPTIMIZED VERSION
Real-time updates cho notifications, dashboard stats, và news comments
Tối ưu cho nhiều users đồng thời (50-100+ users với 2 CPU, 3GB RAM)
"""

from flask import Blueprint, Response, stream_with_context, request, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from app.models import (
    Notification, Task, TaskAssignment, News, NewsComment,
    Penalty, Advance, User
)
from app import db
import json
import time
import hashlib

bp = Blueprint('sse', __name__, url_prefix='/sse')

# ============================================================
# SSE CONFIGURATION - TỐI ƯU CHO NHIỀU USERS
# ============================================================
SSE_RETRY_TIMEOUT = 30000       # 30 seconds (client reconnect)
SSE_HEARTBEAT_INTERVAL = 45     # Heartbeat mỗi 45 giây
SSE_MAX_DURATION = 180          # 3 phút thì reconnect (giảm từ 5 phút)

# Poll intervals - TĂNG LÊN để giảm tải
NOTIFICATION_POLL_INTERVAL = 5   # 5 giây (thay vì 3)
DASHBOARD_POLL_INTERVAL = 15     # 15 giây (thay vì 2!)
COMMENTS_POLL_INTERVAL = 3       # 3 giây (comments cần nhanh)


def format_sse(data: str, event: str = None, retry: int = None) -> str:
    """Format data as SSE message"""
    msg = ''
    if event:
        msg += f'event: {event}\n'
    if retry:
        msg += f'retry: {retry}\n'
    for line in data.split('\n'):
        msg += f'data: {line}\n'
    msg += '\n'
    return msg


def hash_dict(d: dict, exclude_keys: list = None) -> str:
    """Tạo hash từ dict để so sánh nhanh"""
    if exclude_keys is None:
        exclude_keys = ['timestamp']

    filtered = {k: v for k, v in d.items() if k not in exclude_keys}
    return hashlib.md5(json.dumps(filtered, sort_keys=True).encode()).hexdigest()


# ============================================================
# NOTIFICATIONS STREAM - TỐI ƯU
# ============================================================
@bp.route('/notifications')
@login_required
def notifications_stream():
    """
    SSE stream cho notifications
    CHỈ GỬI KHI CÓ THAY ĐỔI
    """
    user_id = current_user.id  # Cache user_id

    def generate():
        last_check = datetime.utcnow()
        last_hash = None
        last_heartbeat = time.time()
        start_time = time.time()

        try:
            yield format_sse('', retry=SSE_RETRY_TIMEOUT)

            # Initial data
            initial_data = get_notification_data_fast(user_id)
            last_hash = hash_dict(initial_data)
            yield format_sse(json.dumps(initial_data), event='notification_update')

            while True:
                # Connection timeout
                if time.time() - start_time > SSE_MAX_DURATION:
                    yield format_sse(
                        json.dumps({'type': 'reconnect', 'message': 'Please reconnect'}),
                        event='close'
                    )
                    break

                try:
                    time.sleep(NOTIFICATION_POLL_INTERVAL)
                    now = datetime.utcnow()

                    # 1. Check thông báo MỚI (quan trọng nhất)
                    new_notifs = get_new_notifications_fast(user_id, last_check)

                    if new_notifs:
                        for notif in new_notifs:
                            yield format_sse(json.dumps(notif), event='new_notification')
                        last_check = now

                    # 2. Check count thay đổi (mỗi 10 giây)
                    if int(time.time()) % 10 < NOTIFICATION_POLL_INTERVAL:
                        current_data = get_notification_data_fast(user_id)
                        current_hash = hash_dict(current_data)

                        if current_hash != last_hash:
                            last_hash = current_hash
                            yield format_sse(json.dumps(current_data), event='notification_update')

                    # 3. Heartbeat
                    if time.time() - last_heartbeat >= SSE_HEARTBEAT_INTERVAL:
                        last_heartbeat = time.time()
                        yield format_sse(
                            json.dumps({'type': 'heartbeat'}),
                            event='heartbeat'
                        )

                except Exception as e:
                    current_app.logger.error(f"SSE notification error: {e}")
                    time.sleep(2)

        except GeneratorExit:
            pass

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
            'Content-Type': 'text/event-stream'
        }
    )


# ============================================================
# DASHBOARD STATS STREAM - TỐI ƯU MẠNH
# ============================================================
@bp.route('/dashboard-stats')
@login_required
def dashboard_stats_stream():
    """
    SSE stream cho dashboard stats
    CHỈ GỬI KHI CÓ THAY ĐỔI - Poll mỗi 15 giây
    """
    user_id = current_user.id
    user_role = current_user.role

    def generate():
        last_hash = None
        last_heartbeat = time.time()
        start_time = time.time()

        try:
            yield format_sse('', retry=SSE_RETRY_TIMEOUT)

            # Initial data
            initial_data = get_dashboard_stats_fast(user_id, user_role)
            last_hash = hash_dict(initial_data)
            yield format_sse(json.dumps(initial_data), event='stats_update')

            while True:
                if time.time() - start_time > SSE_MAX_DURATION:
                    yield format_sse(
                        json.dumps({'type': 'reconnect'}),
                        event='close'
                    )
                    break

                try:
                    time.sleep(DASHBOARD_POLL_INTERVAL)

                    # Chỉ query khi cần
                    stats = get_dashboard_stats_fast(user_id, user_role)
                    current_hash = hash_dict(stats)

                    # CHỈ GỬI KHI CÓ THAY ĐỔI
                    if current_hash != last_hash:
                        last_hash = current_hash
                        yield format_sse(json.dumps(stats), event='stats_update')

                    # Heartbeat
                    if time.time() - last_heartbeat >= SSE_HEARTBEAT_INTERVAL:
                        last_heartbeat = time.time()
                        yield format_sse(
                            json.dumps({'type': 'heartbeat'}),
                            event='heartbeat'
                        )

                except Exception as e:
                    current_app.logger.error(f"SSE stats error: {e}")
                    time.sleep(2)

        except GeneratorExit:
            pass

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
            'Content-Type': 'text/event-stream'
        }
    )


# ============================================================
# NEWS COMMENTS STREAM - TỐI ƯU
# ============================================================
@bp.route('/news/<int:news_id>/comments')
@login_required
def news_comments_stream(news_id):
    """
    SSE stream cho news comments
    CHỈ GỬI KHI CÓ COMMENT MỚI HOẶC XÓA
    """
    user_id = current_user.id
    user_role = current_user.role

    def generate():
        from app.utils import utc_to_vn

        last_timestamp = request.args.get('last_timestamp', type=float, default=0)
        if last_timestamp > 0:
            last_check = datetime.fromtimestamp(last_timestamp)
        else:
            last_check = datetime.utcnow() - timedelta(seconds=1)

        last_comment_ids = set()
        last_heartbeat = time.time()
        start_time = time.time()

        try:
            yield format_sse('', retry=SSE_RETRY_TIMEOUT)

            # Initial: lấy danh sách comment IDs hiện tại
            current_comments = NewsComment.query.filter_by(news_id=news_id).all()
            last_comment_ids = {c.id for c in current_comments}

            while True:
                if time.time() - start_time > SSE_MAX_DURATION:
                    yield format_sse(json.dumps({'type': 'reconnect'}), event='close')
                    break

                try:
                    time.sleep(COMMENTS_POLL_INTERVAL)
                    now = datetime.utcnow()

                    # 1. Check comments MỚI
                    new_comments = NewsComment.query.filter(
                        NewsComment.news_id == news_id,
                        NewsComment.created_at > last_check
                    ).order_by(NewsComment.created_at.asc()).all()

                    if new_comments:
                        comments_data = []
                        for comment in new_comments:
                            if comment.id not in last_comment_ids:
                                vn_time = utc_to_vn(comment.created_at)
                                comments_data.append({
                                    'id': comment.id,
                                    'content': comment.content,
                                    'created_at': comment.created_at.isoformat(),
                                    'created_at_timestamp': comment.created_at.timestamp(),
                                    'created_at_display': vn_time.strftime('%d/%m/%Y %H:%M'),
                                    'user': {
                                        'id': comment.user_id,
                                        'full_name': comment.user.full_name,
                                        'role': comment.user.role,
                                        'avatar_letter': comment.user.full_name[0].upper()
                                    },
                                    'can_delete': comment.user_id == user_id or user_role == 'director'
                                })
                                last_comment_ids.add(comment.id)

                        if comments_data:
                            yield format_sse(
                                json.dumps({
                                    'comments': comments_data,
                                    'total_count': len(last_comment_ids)
                                }),
                                event='new_comments'
                            )
                        last_check = now

                    # 2. Check comments bị XÓA (mỗi 10 giây)
                    if int(time.time()) % 10 < COMMENTS_POLL_INTERVAL:
                        current_ids = {c.id for c in NewsComment.query.filter_by(news_id=news_id).all()}
                        deleted_ids = last_comment_ids - current_ids

                        if deleted_ids:
                            last_comment_ids = current_ids
                            yield format_sse(
                                json.dumps({
                                    'existing_ids': list(current_ids),
                                    'deleted_ids': list(deleted_ids),
                                    'total_count': len(current_ids)
                                }),
                                event='comments_sync'
                            )

                    # 3. Heartbeat
                    if time.time() - last_heartbeat >= SSE_HEARTBEAT_INTERVAL:
                        last_heartbeat = time.time()
                        yield format_sse(json.dumps({'type': 'heartbeat'}), event='heartbeat')

                except Exception as e:
                    current_app.logger.error(f"SSE comments error: {e}")
                    time.sleep(2)

        except GeneratorExit:
            pass

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
            'Content-Type': 'text/event-stream'
        }
    )


# ============================================================
# OPTIMIZED HELPER FUNCTIONS - QUERY TỐI ƯU
# ============================================================

def get_notification_data_fast(user_id: int) -> dict:
    """Lấy notification data - TỐI ƯU với single query"""
    # Chỉ lấy IDs và count, không load full objects
    result = db.session.query(Notification.id).filter(
        Notification.user_id == user_id,
        Notification.read == False
    ).order_by(Notification.created_at.desc()).all()

    ids = [r[0] for r in result]

    return {
        'count': len(ids),
        'ids': ids,
        'timestamp': datetime.utcnow().isoformat()
    }


def get_new_notifications_fast(user_id: int, since: datetime) -> list:
    """Lấy thông báo mới từ timestamp - TỐI ƯU"""
    notifications = Notification.query.filter(
        Notification.user_id == user_id,
        Notification.created_at > since,
        Notification.read == False
    ).order_by(Notification.created_at.desc()).limit(5).all()

    return [
        {
            'id': n.id,
            'title': n.title,
            'body': n.body,
            'type': n.type,
            'link': n.link,
            'created_at': n.created_at.isoformat()
        }
        for n in notifications
    ]


def get_dashboard_stats_fast(user_id: int, user_role: str) -> dict:
    """Lấy dashboard stats - TỐI ƯU với ít queries hơn"""
    now = datetime.utcnow()
    three_days_later = now + timedelta(days=3)

    # 1. Lấy task IDs của user (single query)
    my_task_ids = [
        a.task_id for a in
        TaskAssignment.query.filter_by(user_id=user_id, accepted=True)
        .with_entities(TaskAssignment.task_id).all()
    ]

    # 2. Batch query cho personal stats
    my_overdue = 0
    my_due_soon = 0
    my_pending = 0
    my_in_progress = 0

    if my_task_ids:
        # Single query với CASE WHEN để đếm nhiều điều kiện
        from sqlalchemy import case, func

        stats = db.session.query(
            func.sum(case((
                (Task.due_date < now) & (Task.status.in_(['PENDING', 'IN_PROGRESS'])),
                1
            ), else_=0)).label('overdue'),
            func.sum(case((
                (Task.due_date >= now) & (Task.due_date <= three_days_later) &
                (Task.status.in_(['PENDING', 'IN_PROGRESS'])),
                1
            ), else_=0)).label('due_soon'),
            func.sum(case((Task.status == 'PENDING', 1), else_=0)).label('pending'),
            func.sum(case((Task.status == 'IN_PROGRESS', 1), else_=0)).label('in_progress')
        ).filter(Task.id.in_(my_task_ids)).first()

        if stats:
            my_overdue = stats.overdue or 0
            my_due_soon = stats.due_soon or 0
            my_pending = stats.pending or 0
            my_in_progress = stats.in_progress or 0

    # 3. Notification counts (optimized)
    unread_notifications = db.session.query(func.count(Notification.id)).filter(
        Notification.user_id == user_id,
        Notification.read == False
    ).scalar() or 0

    # 4. Unconfirmed news (optimized)
    from sqlalchemy import not_, exists
    from app.models import NewsConfirmation

    unconfirmed_news = db.session.query(func.count(News.id)).filter(
        ~exists().where(
            (NewsConfirmation.news_id == News.id) &
            (NewsConfirmation.user_id == user_id)
        )
    ).scalar() or 0

    # 5. Team stats (chỉ cho Director/Manager)
    team_overdue = 0
    team_pending = 0
    tasks_need_rating = 0
    my_tasks_need_rating = 0

    if user_role in ['director', 'manager']:
        from sqlalchemy import func

        team_stats = db.session.query(
            func.sum(case((
                (Task.due_date < now) & (Task.status.in_(['PENDING', 'IN_PROGRESS'])),
                1
            ), else_=0)).label('overdue'),
            func.sum(case((Task.status == 'PENDING', 1), else_=0)).label('pending'),
            func.sum(case((
                (Task.status == 'DONE') & (Task.performance_rating == None),
                1
            ), else_=0)).label('need_rating')
        ).first()

        if team_stats:
            team_overdue = team_stats.overdue or 0
            team_pending = team_stats.pending or 0
            tasks_need_rating = team_stats.need_rating or 0

        # Tasks do mình giao cần đánh giá
        my_tasks_need_rating = db.session.query(func.count(Task.id)).filter(
            Task.creator_id == user_id,
            Task.status == 'DONE',
            Task.performance_rating == None
        ).scalar() or 0

    # 6. Salary stats (Director/Accountant)
    pending_penalties = 0
    pending_advances = 0

    if user_role in ['director', 'accountant']:
        pending_penalties = db.session.query(func.count(Penalty.id)).filter(
            Penalty.is_deducted == False
        ).scalar() or 0

        pending_advances = db.session.query(func.count(Advance.id)).filter(
            Advance.is_deducted == False
        ).scalar() or 0

    # Calculate badges
    work_badge = my_overdue + my_due_soon
    info_badge = unconfirmed_news + unread_notifications
    salary_badge = pending_penalties + pending_advances

    return {
        'my_overdue': my_overdue,
        'my_due_soon': my_due_soon,
        'my_pending_tasks': my_pending,
        'my_in_progress': my_in_progress,
        'unread_notifications': unread_notifications,
        'unconfirmed_news': unconfirmed_news,
        'team_overdue': team_overdue,
        'team_pending': team_pending,
        'tasks_need_rating': tasks_need_rating,
        'my_tasks_need_rating': my_tasks_need_rating,
        'pending_penalties': pending_penalties,
        'pending_advances': pending_advances,
        'work_badge': work_badge,
        'info_badge': info_badge,
        'salary_badge': salary_badge,
        'timestamp': datetime.utcnow().isoformat()
    }