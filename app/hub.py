from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app.models import Task, TaskAssignment, Salary, Employee, News, Notification, User
from datetime import datetime, timedelta
from app.utils import utc_to_vn, vn_to_utc
from app import db

bp = Blueprint('hub', __name__, url_prefix='/hub')


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

    return render_template('hub.html',
                           my_pending_tasks=my_pending_tasks,
                           my_in_progress=my_in_progress,
                           my_due_soon=my_due_soon,
                           my_overdue=my_overdue,
                           tasks_need_rating=tasks_need_rating,
                           my_tasks_need_rating=my_tasks_need_rating,
                           total_salaries=total_salaries,
                           total_employees=total_employees,
                           pending_penalties=pending_penalties,
                           pending_advances=pending_advances,
                           unread_notifications=unread_notifications,
                           unconfirmed_news=unconfirmed_news,
                           total_users=total_users,
                           active_users=active_users)


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
    API trả về performance của team members
    Hỗ trợ SSE real-time update
    """
    try:
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')

        # Xác định users theo role
        if current_user.role == 'director':
            users = User.query.filter_by(is_active=True).all()
        elif current_user.role == 'manager':
            # Lấy danh sách task IDs trực tiếp
            created_tasks = db.session.query(Task.id).filter_by(
                creator_id=current_user.id
            ).all()

            created_task_ids = [t[0] for t in created_tasks]

            assigned_user_ids = db.session.query(TaskAssignment.user_id).filter(
                TaskAssignment.task_id.in_(created_task_ids)
            ).distinct().all()

            user_ids = [current_user.id] + [uid[0] for uid in assigned_user_ids]
            users = User.query.filter(
                User.id.in_(user_ids),
                User.is_active == True
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

            # Apply date filter
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

        # Đánh dấu rank
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