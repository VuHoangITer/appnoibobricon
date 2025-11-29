from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app.models import Task, TaskAssignment, Salary, Employee, News, Notification, User
from datetime import datetime, timedelta
from app.utils import utc_to_vn, vn_to_utc
from app import db

bp = Blueprint('hub', __name__, url_prefix='/hub')


# ========================================
def get_team_performance_data(date_from=None, date_to=None):
    """
    Lấy performance data - filter theo role
    Returns: list of dict
    """
    # Xác định users theo role
    if current_user.role == 'director':
        users = User.query.filter_by(is_active=True).all()
    elif current_user.role == 'manager':
        # MANAGER CHỈ THẤY CHÍNH MÌNH VÀ HR
        users = User.query.filter(
            User.is_active == True,
            User.role.in_(['manager', 'hr'])
        ).all()
    else:
        users = [current_user]

    results = []

    for user in users:
        base_query = db.session.query(Task).join(
            TaskAssignment, Task.id == TaskAssignment.task_id
        ).filter(
            TaskAssignment.user_id == user.id
        )

        # Apply date filters
        if date_from:
            try:
                from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                from_utc = vn_to_utc(from_dt)
                base_query = base_query.filter(Task.created_at >= from_utc)
            except ValueError:
                pass

        if date_to:
            try:
                to_dt = datetime.strptime(date_to, '%Y-%m-%d')
                to_dt = to_dt.replace(hour=23, minute=59, second=59)
                to_utc = vn_to_utc(to_dt)
                base_query = base_query.filter(Task.created_at <= to_utc)
            except ValueError:
                pass

        # Count - CHỈ ĐẾM CHƯA HOÀN THÀNH
        urgent_count = base_query.filter(
            Task.is_urgent == True,
            Task.status != 'DONE'
        ).count()

        important_count = base_query.filter(
            Task.is_important == True,
            Task.status != 'DONE'
        ).count()

        recurring_count = base_query.filter(
            Task.is_recurring == True,
            Task.status != 'DONE'
        ).count()

        done_count = base_query.filter(
            Task.status == 'DONE'
        ).count()

        results.append({
            'user_id': user.id,
            'full_name': user.full_name,
            'avatar': user.avatar,
            'urgent_count': urgent_count,
            'important_count': important_count,
            'recurring_count': recurring_count,
            'done_count': done_count
        })

    # Sort by done_count
    results.sort(key=lambda x: x['done_count'], reverse=True)

    # Đánh dấu rank (chỉ dùng cho table display)
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
    else:
        if results:
            results[0]['rank'] = 0

    return results


# ========================================
def get_top_bottom_users_data(date_from=None, date_to=None):
    """
    Lấy top & bottom users từ TOÀN BỘ team ngoại trừ giam doc - KHÔNG filter theo role
    Returns: dict { 'top_user': {...}, 'bottom_user': {...} }
    """
    users = User.query.filter_by(is_active=True).filter(User.role != 'director').all()
    results = []

    for user in users:
        base_query = db.session.query(Task).join(
            TaskAssignment, Task.id == TaskAssignment.task_id
        ).filter(
            TaskAssignment.user_id == user.id
        )

        # Apply date filters
        if date_from:
            try:
                from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                from_utc = vn_to_utc(from_dt)
                base_query = base_query.filter(Task.created_at >= from_utc)
            except ValueError:
                pass

        if date_to:
            try:
                to_dt = datetime.strptime(date_to, '%Y-%m-%d')
                to_dt = to_dt.replace(hour=23, minute=59, second=59)
                to_utc = vn_to_utc(to_dt)
                base_query = base_query.filter(Task.created_at <= to_utc)
            except ValueError:
                pass

        done_count = base_query.filter(Task.status == 'DONE').count()

        results.append({
            'user_id': user.id,
            'full_name': user.full_name,
            'avatar': user.avatar,
            'done_count': done_count
        })

    # Sort by done_count
    results.sort(key=lambda x: x['done_count'], reverse=True)

    response = {}

    if len(results) > 1:
        top = results[0]
        bottom = results[-1]

        # Chỉ trả về nếu có sự khác biệt
        if top['done_count'] > bottom['done_count']:
            response['top_user'] = top
            response['bottom_user'] = bottom
        else:
            response['top_user'] = None
            response['bottom_user'] = None
    elif len(results) == 1:
        # Chỉ có 1 user
        response['top_user'] = results[0]
        response['bottom_user'] = None
    else:
        response['top_user'] = None
        response['bottom_user'] = None

    return response


# ========================================
@bp.route('/')
@login_required
def workflow_hub():
    """Trang Hub - Quy trình công việc tổng quan"""

    now = datetime.utcnow()

    # ========================================
    # CÔNG VIỆC CÁ NHÂN
    # ========================================
    my_assignments = TaskAssignment.query.filter_by(
        user_id=current_user.id,
        accepted=True
    ).all()
    my_task_ids = [a.task_id for a in my_assignments]

    my_pending_tasks = Task.query.filter(
        Task.id.in_(my_task_ids),
        Task.status == 'PENDING'
    ).count()

    my_in_progress = Task.query.filter(
        Task.id.in_(my_task_ids),
        Task.status == 'IN_PROGRESS'
    ).count()

    three_days_later = now + timedelta(days=3)
    my_due_soon = Task.query.filter(
        Task.id.in_(my_task_ids),
        Task.due_date >= now,
        Task.due_date <= three_days_later,
        Task.status.in_(['PENDING', 'IN_PROGRESS'])
    ).count()

    my_overdue = Task.query.filter(
        Task.id.in_(my_task_ids),
        Task.due_date < now,
        Task.status.in_(['PENDING', 'IN_PROGRESS'])
    ).count()

    # ========================================
    # QUẢN LÝ (Director/Manager)
    # ========================================
    tasks_need_rating = 0
    my_tasks_need_rating = 0
    tasks_need_approval = 0  # ✅ KHỞI TẠO BIẾN NGAY TỪ ĐẦU

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

        # ✅ GÁN GIÁ TRỊ CHO tasks_need_approval
        query = Task.query.filter(
            Task.requires_approval == True,
            Task.approved == None  # Chỉ đếm task CHỜ DUYỆT
        )

        # Manager chỉ thấy tasks của HR
        if current_user.role == 'manager':
            query = query.join(User, Task.creator_id == User.id).filter(
                User.role == 'hr'
            )

        tasks_need_approval = query.count()

    # ========================================
    # LƯƠNG (Director/Accountant)
    # ========================================
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

    # ========================================
    # THÔNG BÁO
    # ========================================
    unread_notifications = Notification.query.filter_by(
        user_id=current_user.id,
        read=False
    ).count()

    unconfirmed_news = News.query.filter(
        ~News.confirmations.any(user_id=current_user.id)
    ).count()

    # ========================================
    # QUẢN TRỊ (Director)
    # ========================================
    total_users = 0
    active_users = 0

    if current_user.role == 'director':
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()

    # ✅ Performance table - filter theo role
    initial_performance = get_team_performance_data()

    # ✅ Top & Bottom users - lấy từ toàn bộ team
    initial_top_bottom = get_top_bottom_users_data()

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
                           initial_top_bottom=initial_top_bottom
                           )


# ========================================
# API: REAL-TIME STATS (CHO SSE)
# ========================================
@bp.route('/api/realtime-stats')
@login_required
def get_realtime_stats():
    """API trả về stats real-time cho polling/SSE"""
    try:
        now = datetime.utcnow()

        my_assignments = TaskAssignment.query.filter_by(
            user_id=current_user.id,
            accepted=True
        ).all()
        my_task_ids = [a.task_id for a in my_assignments]

        my_overdue = Task.query.filter(
            Task.id.in_(my_task_ids),
            Task.due_date < now,
            Task.status.in_(['PENDING', 'IN_PROGRESS'])
        ).count()

        three_days_later = now + timedelta(days=3)
        my_due_soon = Task.query.filter(
            Task.id.in_(my_task_ids),
            Task.due_date >= now,
            Task.due_date <= three_days_later,
            Task.status.in_(['PENDING', 'IN_PROGRESS'])
        ).count()

        my_pending_tasks = Task.query.filter(
            Task.id.in_(my_task_ids),
            Task.status == 'PENDING'
        ).count()

        my_in_progress = Task.query.filter(
            Task.id.in_(my_task_ids),
            Task.status == 'IN_PROGRESS'
        ).count()

        unread_notifications = Notification.query.filter_by(
            user_id=current_user.id,
            read=False
        ).count()

        unconfirmed_news = News.query.filter(
            ~News.confirmations.any(user_id=current_user.id)
        ).count()

        # Stats team (cho manager/director)
        team_overdue = 0
        team_pending = 0
        tasks_need_rating = 0
        my_tasks_need_rating = 0

        if current_user.role in ['director', 'manager']:
            team_overdue = Task.query.filter(
                Task.due_date < now,
                Task.status.in_(['PENDING', 'IN_PROGRESS'])
            ).count()

            team_pending = Task.query.filter_by(status='PENDING').count()

            tasks_need_rating = Task.query.filter(
                Task.status == 'DONE',
                Task.performance_rating == None
            ).count()

            my_tasks_need_rating = Task.query.filter(
                Task.creator_id == current_user.id,
                Task.status == 'DONE',
                Task.performance_rating == None
            ).count()

        tasks_need_approval = 0
        if current_user.role in ['director', 'manager']:
            query = Task.query.filter(
                Task.requires_approval == True,
                Task.approved == None
            )

            if current_user.role == 'manager':
                query = query.join(User, Task.creator_id == User.id).filter(
                    User.role == 'hr'
                )

            tasks_need_approval = query.count()

        # Stats lương
        pending_penalties = 0
        pending_advances = 0

        if current_user.role in ['director', 'accountant']:
            from app.models import Penalty, Advance
            pending_penalties = Penalty.query.filter_by(is_deducted=False).count()
            pending_advances = Advance.query.filter_by(is_deducted=False).count()

        work_badge = my_overdue + my_due_soon
        info_badge = unconfirmed_news + unread_notifications
        salary_badge = pending_penalties + pending_advances

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
            'work_badge': work_badge,
            'info_badge': info_badge,
            'salary_badge': salary_badge,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        print(f"❌ Error in get_realtime_stats: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ========================================
# API: TEAM PERFORMANCE (CHO SSE)
# ========================================
@bp.route('/api/team-performance')
@login_required
def get_team_performance():
    """
    API trả về performance của team members - filter theo role
    Dùng cho filters và SSE real-time update
    """
    try:
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')

        results = get_team_performance_data(date_from, date_to)

        return jsonify({
            'success': True,
            'data': results
        })

    except Exception as e:
        print(f"❌ Error in team-performance: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========================================
# API: TOP & BOTTOM USERS (CHO TẤT CẢ ROLES)
# ========================================
@bp.route('/api/top-bottom-users')
@login_required
def get_top_bottom_users():
    """
    Lấy top & bottom users từ TOÀN BỘ team - không filter theo role
    Returns: { top_user: {...}, bottom_user: {...} }
    """
    try:
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')

        response = get_top_bottom_users_data(date_from, date_to)

        return jsonify({
            'success': True,
            'data': response
        })

    except Exception as e:
        print(f"❌ Error in top-bottom-users: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.app_context_processor
def inject_top_bottom_users():
    """
    Tự động inject top_bottom_data vào tất cả template
    Chỉ chạy khi user đã đăng nhập
    """
    from flask_login import current_user

    if current_user.is_authenticated:
        try:
            top_bottom_data = get_top_bottom_users_data()
            return {'top_bottom_data': top_bottom_data}
        except:
            return {'top_bottom_data': None}

    return {'top_bottom_data': None}