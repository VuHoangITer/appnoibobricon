from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from app import db
from app.models import User, Task, TaskAssignment
from app.decorators import role_required
from datetime import datetime

bp = Blueprint('performance', __name__)


@bp.route('/')
@login_required
@role_required(['director', 'manager'])
def performance_review():
    """Trang đánh giá hiệu suất - chỉ Director/Manager"""

    # Get filter params
    selected_user_id = request.args.get('user_id', type=int)
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    status_filter = request.args.get('status', 'DONE')  # Mặc định xem DONE
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # Lấy danh sách nhân viên để chọn
    all_users = User.query.filter_by(is_active=True).order_by(User.full_name).all()

    # Nếu chưa chọn user, hiển thị trang chọn
    if not selected_user_id:
        return render_template('performance_review.html',
                               all_users=all_users,
                               selected_user=None,
                               tasks=None,
                               pagination=None,
                               stats=None)

    # Lấy thông tin user được chọn
    selected_user = User.query.get_or_404(selected_user_id)

    # Base query: Lấy tasks của user này
    assignments = TaskAssignment.query.filter_by(
        user_id=selected_user_id,
        accepted=True
    ).all()
    task_ids = [a.task_id for a in assignments]

    query = Task.query.filter(Task.id.in_(task_ids))

    # Apply status filter
    if status_filter:
        query = query.filter_by(status=status_filter)

    # Apply date filters
    if date_from:
        try:
            from app.utils import vn_to_utc
            date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
            date_from_utc = vn_to_utc(date_from_dt)
            query = query.filter(Task.created_at >= date_from_utc)
        except:
            pass

    if date_to:
        try:
            from app.utils import vn_to_utc
            date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
            date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
            date_to_utc = vn_to_utc(date_to_dt)
            query = query.filter(Task.created_at <= date_to_utc)
        except:
            pass

    # Pagination
    pagination = query.order_by(Task.updated_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    tasks = pagination.items

    # ===== TÍNH TOÁN STATISTICS =====
    all_user_tasks = Task.query.filter(Task.id.in_(task_ids))

    # Apply date filters to stats
    if date_from:
        try:
            date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
            from app.utils import vn_to_utc
            date_from_utc = vn_to_utc(date_from_dt)
            all_user_tasks = all_user_tasks.filter(Task.created_at >= date_from_utc)
        except:
            pass

    if date_to:
        try:
            date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
            date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
            from app.utils import vn_to_utc
            date_to_utc = vn_to_utc(date_to_dt)
            all_user_tasks = all_user_tasks.filter(Task.created_at <= date_to_utc)
        except:
            pass

    total_tasks = all_user_tasks.count()
    done_tasks = all_user_tasks.filter_by(status='DONE').count()
    in_progress = all_user_tasks.filter_by(status='IN_PROGRESS').count()
    pending = all_user_tasks.filter_by(status='PENDING').count()

    # Đếm theo rating
    good_rating = all_user_tasks.filter_by(status='DONE', performance_rating='good').count()
    bad_rating = all_user_tasks.filter_by(status='DONE', performance_rating='bad').count()
    unrated = all_user_tasks.filter_by(status='DONE', performance_rating=None).count()

    # Đếm hoàn thành đúng hạn / quá hạn
    done_on_time = all_user_tasks.filter_by(status='DONE', completed_overdue=False).count()
    done_overdue = all_user_tasks.filter_by(status='DONE', completed_overdue=True).count()

    # Đếm đang quá hạn
    now = datetime.utcnow()
    current_overdue = all_user_tasks.filter(
        Task.due_date < now,
        Task.status.in_(['PENDING', 'IN_PROGRESS'])
    ).count()

    # Tính % completion
    completion_rate = (done_tasks / total_tasks * 100) if total_tasks > 0 else 0

    # Tính % on-time (trong số đã hoàn thành)
    on_time_rate = (done_on_time / done_tasks * 100) if done_tasks > 0 else 0

    # Tính % good rating (trong số đã hoàn thành)
    good_rating_rate = (good_rating / done_tasks * 100) if done_tasks > 0 else 0

    # Tính % rating coverage (đã được đánh giá / tổng số DONE)
    rating_coverage = ((good_rating + bad_rating) / done_tasks * 100) if done_tasks > 0 else 0

    stats = {
        'total_tasks': total_tasks,
        'done_tasks': done_tasks,
        'in_progress': in_progress,
        'pending': pending,
        'good_rating': good_rating,
        'bad_rating': bad_rating,
        'unrated': unrated,
        'done_on_time': done_on_time,
        'done_overdue': done_overdue,
        'current_overdue': current_overdue,
        'completion_rate': round(completion_rate, 1),
        'on_time_rate': round(on_time_rate, 1),
        'good_rating_rate': round(good_rating_rate, 1),
        'rating_coverage': round(rating_coverage, 1)
    }

    return render_template('performance_review.html',
                           all_users=all_users,
                           selected_user=selected_user,
                           tasks=tasks,
                           pagination=pagination,
                           stats=stats,
                           date_from=date_from,
                           date_to=date_to,
                           status_filter=status_filter)


# ===== ROUTE MỚI: XEM TẤT CẢ NHIỆM VỤ CHƯA ĐÁNH GIÁ =====
@bp.route('/unrated-tasks')
@login_required
@role_required(['director', 'manager'])
def unrated_tasks():
    """Xem tất cả nhiệm vụ chưa đánh giá - chỉ Director/Manager"""

    # Get filters
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    assigned_user = request.args.get('assigned_user', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # Base query: Tất cả tasks DONE nhưng chưa được đánh giá
    query = Task.query.filter_by(
        status='DONE',
        performance_rating=None
    )

    # Apply date filters (theo ngày hoàn thành - updated_at)
    if date_from:
        try:
            from app.utils import vn_to_utc
            date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
            date_from_utc = vn_to_utc(date_from_dt)
            query = query.filter(Task.updated_at >= date_from_utc)
        except:
            pass

    if date_to:
        try:
            from app.utils import vn_to_utc
            date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
            date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
            date_to_utc = vn_to_utc(date_to_dt)
            query = query.filter(Task.updated_at <= date_to_utc)
        except:
            pass

    # Apply assigned user filter
    if assigned_user:
        task_ids = [a.task_id for a in TaskAssignment.query.filter_by(
            user_id=int(assigned_user),
            accepted=True
        ).all()]
        query = query.filter(Task.id.in_(task_ids))

    # Order: Ưu tiên quá hạn lên đầu, sau đó theo thời gian hoàn thành
    query = query.order_by(
        Task.completed_overdue.desc(),  # Quá hạn lên đầu
        Task.updated_at.desc()  # Mới nhất lên đầu
    )

    # Pagination
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    tasks = pagination.items

    # Statistics
    total_unrated = query.count()
    unrated_overdue = query.filter_by(completed_overdue=True).count()
    unrated_on_time = query.filter_by(completed_overdue=False).count()

    # Get all users for filter
    all_users = User.query.filter_by(is_active=True).order_by(User.full_name).all()

    return render_template('unrated_tasks.html',
                           tasks=tasks,
                           pagination=pagination,
                           total_unrated=total_unrated,
                           unrated_overdue=unrated_overdue,
                           unrated_on_time=unrated_on_time,
                           all_users=all_users,
                           date_from=date_from,
                           date_to=date_to,
                           assigned_user=assigned_user)