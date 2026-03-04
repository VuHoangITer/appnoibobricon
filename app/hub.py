from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app.models import Task, TaskAssignment, Salary, Employee, News, Notification, User
from datetime import datetime, timedelta
from app.utils import utc_to_vn, vn_to_utc
from app import db
from sqlalchemy import func, case

bp = Blueprint('hub', __name__, url_prefix='/hub')


# ========================================
# CACHE ĐƠN GIẢN TRONG BỘ NHỚ
# ========================================
import time as _time

_cache_store = {}
_cache_ttl_store = {}

def _cache_get(key):
    if key in _cache_store:
        if _time.time() - _cache_ttl_store.get(key, 0) < 30:  # TTL 30 giây
            return _cache_store[key]
    return None

def _cache_set(key, value):
    _cache_store[key] = value
    _cache_ttl_store[key] = _time.time()


# ========================================
# PERFORMANCE DATA - TỐI ƯU: 1 QUERY TỔNG HỢP thay vì N*4 queries
# ========================================
def get_team_performance_data(date_from=None, date_to=None):
    """
    Lấy performance data - dùng GROUP BY thay vì loop từng user
    Từ N*4 queries → 1 query duy nhất
    """
    # Xác định users theo role
    if current_user.role == 'director':
        users = User.query.filter_by(is_active=True).all()
    elif current_user.role == 'manager':
        users = User.query.filter(
            User.is_active == True,
            User.role.in_(['manager', 'hr'])
        ).all()
    else:
        users = [current_user]

    if not users:
        return []

    user_ids = [u.id for u in users]
    user_map = {u.id: u for u in users}

    # === 1 QUERY DUY NHẤT với GROUP BY + CASE ===
    query = db.session.query(
        TaskAssignment.user_id,
        func.count(
            case((
                (Task.is_urgent == True) & (Task.status != 'DONE'),
                Task.id
            ))
        ).label('urgent_count'),
        func.count(
            case((
                (Task.is_important == True) & (Task.status != 'DONE'),
                Task.id
            ))
        ).label('important_count'),
        func.count(
            case((
                (Task.is_recurring == True) & (Task.status != 'DONE'),
                Task.id
            ))
        ).label('recurring_count'),
        func.count(
            case((
                Task.status == 'DONE',
                Task.id
            ))
        ).label('done_count'),
    ).join(
        Task, Task.id == TaskAssignment.task_id
    ).filter(
        TaskAssignment.user_id.in_(user_ids)
    )

    # Apply date filters
    if date_from:
        try:
            from_dt = datetime.strptime(date_from, '%Y-%m-%d')
            from_utc = vn_to_utc(from_dt)
            query = query.filter(Task.created_at >= from_utc)
        except ValueError:
            pass

    if date_to:
        try:
            to_dt = datetime.strptime(date_to, '%Y-%m-%d')
            to_dt = to_dt.replace(hour=23, minute=59, second=59)
            to_utc = vn_to_utc(to_dt)
            query = query.filter(Task.created_at <= to_utc)
        except ValueError:
            pass

    query = query.group_by(TaskAssignment.user_id)
    rows = query.all()

    # Map kết quả
    counts_map = {row.user_id: row for row in rows}

    results = []
    for user in users:
        row = counts_map.get(user.id)
        results.append({
            'user_id': user.id,
            'full_name': user.full_name,
            'avatar': user.avatar,
            'urgent_count': row.urgent_count if row else 0,
            'important_count': row.important_count if row else 0,
            'recurring_count': row.recurring_count if row else 0,
            'done_count': row.done_count if row else 0,
        })

    # Sort by done_count
    results.sort(key=lambda x: x['done_count'], reverse=True)

    # Đánh rank
    if len(results) > 1:
        max_done = results[0]['done_count']
        min_done = results[-1]['done_count']
        for r in results:
            if r['done_count'] == max_done and max_done > min_done:
                r['rank'] = 1
            elif r['done_count'] == min_done and max_done > min_done:
                r['rank'] = -1
            else:
                r['rank'] = 0
    elif results:
        results[0]['rank'] = 0

    return results


# ========================================
# TOP/BOTTOM USERS - TỐI ƯU: 1 QUERY thay vì N queries
# ========================================
def get_top_bottom_users_data(date_from=None, date_to=None):
    """
    Lấy top & bottom users - 1 query GROUP BY thay vì loop
    """
    users = User.query.filter(
        User.is_active == True,
        User.role != 'director'
    ).all()

    if not users:
        return {'top_user': None, 'bottom_user': None}

    user_ids = [u.id for u in users]
    user_map = {u.id: u for u in users}

    # 1 query duy nhất
    query = db.session.query(
        TaskAssignment.user_id,
        func.count(
            case((Task.status == 'DONE', Task.id))
        ).label('done_count'),
    ).join(
        Task, Task.id == TaskAssignment.task_id
    ).filter(
        TaskAssignment.user_id.in_(user_ids)
    )

    if date_from:
        try:
            from_dt = datetime.strptime(date_from, '%Y-%m-%d')
            from_utc = vn_to_utc(from_dt)
            query = query.filter(Task.created_at >= from_utc)
        except ValueError:
            pass

    if date_to:
        try:
            to_dt = datetime.strptime(date_to, '%Y-%m-%d')
            to_dt = to_dt.replace(hour=23, minute=59, second=59)
            to_utc = vn_to_utc(to_dt)
            query = query.filter(Task.created_at <= to_utc)
        except ValueError:
            pass

    query = query.group_by(TaskAssignment.user_id)
    rows = query.all()

    if not rows:
        return {'top_user': None, 'bottom_user': None}

    rows_sorted = sorted(rows, key=lambda r: r.done_count, reverse=True)
    top_row = rows_sorted[0]
    bottom_row = rows_sorted[-1]

    if top_row.done_count == bottom_row.done_count:
        return {'top_user': None, 'bottom_user': None}

    def user_to_dict(row):
        u = user_map.get(row.user_id)
        if not u:
            return None
        return {
            'user_id': u.id,
            'full_name': u.full_name,
            'avatar': u.avatar,
            'done_count': row.done_count,
        }

    return {
        'top_user': user_to_dict(top_row),
        'bottom_user': user_to_dict(bottom_row),
    }


# ========================================
# HUB ROUTE
# ========================================
@bp.route('/')
@login_required
def workflow_hub():
    now = datetime.utcnow()

    # Công việc cá nhân - dùng subquery thay vì load all assignments
    my_task_ids_subq = db.session.query(TaskAssignment.task_id).filter(
        TaskAssignment.user_id == current_user.id,
        TaskAssignment.accepted == True
    ).subquery()

    my_pending_tasks = Task.query.filter(
        Task.id.in_(my_task_ids_subq),
        Task.status == 'PENDING'
    ).count()

    my_in_progress = Task.query.filter(
        Task.id.in_(my_task_ids_subq),
        Task.status == 'IN_PROGRESS'
    ).count()

    three_days_later = now + timedelta(days=3)
    my_due_soon = Task.query.filter(
        Task.id.in_(my_task_ids_subq),
        Task.due_date >= now,
        Task.due_date <= three_days_later,
        Task.status.in_(['PENDING', 'IN_PROGRESS'])
    ).count()

    my_overdue = Task.query.filter(
        Task.id.in_(my_task_ids_subq),
        Task.due_date < now,
        Task.status.in_(['PENDING', 'IN_PROGRESS'])
    ).count()

    # Quản lý
    tasks_need_rating = 0
    my_tasks_need_rating = 0
    tasks_need_approval = 0

    if current_user.role in ['director', 'manager']:
        tasks_need_rating = Task.query.filter(
            Task.status == 'DONE',
            Task.performance_rating == None
        ).count()

        my_tasks_need_rating = Task.query.filter(
            Task.creator_id == current_user.id,
            Task.status == 'DONE',
            Task.performance_rating == None
        ).count()

        query = Task.query.filter(
            Task.requires_approval == True,
            Task.approved == None
        )
        if current_user.role == 'manager':
            query = query.join(User, Task.creator_id == User.id).filter(
                User.role == 'hr'
            )
        tasks_need_approval = query.count()

    # Lương
    total_salaries = 0
    total_employees = 0
    pending_penalties = 0
    pending_advances = 0

    if current_user.role in ['director', 'accountant']:
        total_salaries = Salary.query.count()
        total_employees = Employee.query.filter_by(is_active=True).count()
        from app.models import Penalty, Advance
        pending_penalties = Penalty.query.filter_by(is_deducted=False).count()
        pending_advances = Advance.query.filter_by(is_deducted=False).count()

    # Thông báo - dùng scalar count thay vì load objects
    unread_notifications = db.session.query(func.count(Notification.id)).filter(
        Notification.user_id == current_user.id,
        Notification.read == False
    ).scalar() or 0

    unconfirmed_news = db.session.query(func.count(News.id)).filter(
        ~News.confirmations.any(user_id=current_user.id)
    ).scalar() or 0

    # Admin
    total_users = 0
    active_users = 0
    if current_user.role == 'director':
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()

    # Performance
    initial_performance = get_team_performance_data()
    initial_top_bottom = get_top_bottom_users_data()

    from app.models import MarqueeConfig
    marquee_config = MarqueeConfig.get_config()

    return render_template('hub.html',
                           my_pending_tasks=my_pending_tasks,
                           my_in_progress=my_in_progress,
                           my_due_soon=my_due_soon,
                           my_overdue=my_overdue,
                           tasks_need_rating=tasks_need_rating,
                           my_tasks_need_rating=my_tasks_need_rating,
                           tasks_need_approval=tasks_need_approval,
                           total_salaries=total_salaries,
                           total_employees=total_employees,
                           pending_penalties=pending_penalties,
                           pending_advances=pending_advances,
                           unread_notifications=unread_notifications,
                           unconfirmed_news=unconfirmed_news,
                           total_users=total_users,
                           active_users=active_users,
                           initial_performance=initial_performance,
                           initial_top_bottom=initial_top_bottom,
                           marquee_config=marquee_config)


# ========================================
# API: REAL-TIME STATS - TỐI ƯU với scalar counts
# ========================================
@bp.route('/api/realtime-stats')
@login_required
def get_realtime_stats():
    try:
        now = datetime.utcnow()

        # Dùng subquery thay vì load all assignments
        my_task_ids_subq = db.session.query(TaskAssignment.task_id).filter(
            TaskAssignment.user_id == current_user.id,
            TaskAssignment.accepted == True
        ).subquery()

        my_overdue = db.session.query(func.count(Task.id)).filter(
            Task.id.in_(my_task_ids_subq),
            Task.due_date < now,
            Task.status.in_(['PENDING', 'IN_PROGRESS'])
        ).scalar() or 0

        three_days_later = now + timedelta(days=3)
        my_due_soon = db.session.query(func.count(Task.id)).filter(
            Task.id.in_(my_task_ids_subq),
            Task.due_date >= now,
            Task.due_date <= three_days_later,
            Task.status.in_(['PENDING', 'IN_PROGRESS'])
        ).scalar() or 0

        my_pending_tasks = db.session.query(func.count(Task.id)).filter(
            Task.id.in_(my_task_ids_subq),
            Task.status == 'PENDING'
        ).scalar() or 0

        my_in_progress = db.session.query(func.count(Task.id)).filter(
            Task.id.in_(my_task_ids_subq),
            Task.status == 'IN_PROGRESS'
        ).scalar() or 0

        unread_notifications = db.session.query(func.count(Notification.id)).filter(
            Notification.user_id == current_user.id,
            Notification.read == False
        ).scalar() or 0

        unconfirmed_news = db.session.query(func.count(News.id)).filter(
            ~News.confirmations.any(user_id=current_user.id)
        ).scalar() or 0

        # Manager/Director stats
        team_overdue = 0
        team_pending = 0
        tasks_need_rating = 0
        my_tasks_need_rating = 0
        tasks_need_approval = 0

        if current_user.role in ['director', 'manager']:
            team_overdue = db.session.query(func.count(Task.id)).filter(
                Task.due_date < now,
                Task.status.in_(['PENDING', 'IN_PROGRESS'])
            ).scalar() or 0

            team_pending = db.session.query(func.count(Task.id)).filter(
                Task.status == 'PENDING'
            ).scalar() or 0

            tasks_need_rating = db.session.query(func.count(Task.id)).filter(
                Task.status == 'DONE',
                Task.performance_rating == None
            ).scalar() or 0

            my_tasks_need_rating = db.session.query(func.count(Task.id)).filter(
                Task.creator_id == current_user.id,
                Task.status == 'DONE',
                Task.performance_rating == None
            ).scalar() or 0

            approval_query = Task.query.filter(
                Task.requires_approval == True,
                Task.approved == None
            )
            if current_user.role == 'manager':
                approval_query = approval_query.join(User, Task.creator_id == User.id).filter(
                    User.role == 'hr'
                )
            tasks_need_approval = approval_query.count()

        # Lương
        pending_penalties = 0
        pending_advances = 0
        if current_user.role in ['director', 'accountant']:
            from app.models import Penalty, Advance
            pending_penalties = db.session.query(func.count(Penalty.id)).filter(
                Penalty.is_deducted == False
            ).scalar() or 0
            pending_advances = db.session.query(func.count(Advance.id)).filter(
                Advance.is_deducted == False
            ).scalar() or 0

        return jsonify({
            'my_overdue': my_overdue,
            'my_due_soon': my_due_soon,
            'my_pending_tasks': my_pending_tasks,
            'my_in_progress': my_in_progress,
            'unread_notifications': unread_notifications,
            'unconfirmed_news': unconfirmed_news,
            'team_overdue': team_overdue,
            'team_pending': team_pending,
            'tasks_need_rating': tasks_need_rating,
            'my_tasks_need_rating': my_tasks_need_rating,
            'tasks_need_approval': tasks_need_approval,
            'pending_penalties': pending_penalties,
            'pending_advances': pending_advances,
            'work_badge': my_overdue + my_due_soon,
            'info_badge': unconfirmed_news + unread_notifications,
            'salary_badge': pending_penalties + pending_advances,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        print(f"❌ Error in get_realtime_stats: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ========================================
# API: TEAM PERFORMANCE
# ========================================
@bp.route('/api/team-performance')
@login_required
def get_team_performance():
    try:
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        results = get_team_performance_data(date_from, date_to)
        return jsonify({'success': True, 'data': results})
    except Exception as e:
        print(f"❌ Error in team-performance: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========================================
# API: TOP & BOTTOM USERS
# ========================================
@bp.route('/api/top-bottom-users')
@login_required
def get_top_bottom_users():
    try:
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        response = get_top_bottom_users_data(date_from, date_to)
        return jsonify({'success': True, 'data': response})
    except Exception as e:
        print(f"❌ Error in top-bottom-users: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========================================
# ĐÃ XÓA: inject_top_bottom_users()
# Hàm này chạy DB query trên MỌI request → gây lag toàn app
# Nếu cần dùng top_bottom_data trong template khác, hãy truyền trực tiếp
# từ route đó thay vì dùng context_processor
# ========================================