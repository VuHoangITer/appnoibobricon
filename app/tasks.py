from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Task, TaskAssignment, User, Notification, TaskComment
from app.decorators import role_required
from datetime import datetime, timedelta
from sqlalchemy import or_, and_
from app.utils import vn_to_utc, utc_to_vn, vn_now

bp = Blueprint('tasks', __name__)


# ============================================
# HELPER FUNCTIONS - COMMENT UNREAD TRACKING
# ============================================

def get_task_unread_comment_count(task_id, user_id):
    """
    Đếm số comment chưa đọc của user trong task
    (KHÔNG bao gồm comment do chính user viết)
    Returns: int
    """
    from app.models import TaskComment, TaskCommentRead

    # Lấy tất cả comment IDs của task, LOẠI TRỪ comment do chính user viết
    all_comment_ids = db.session.query(TaskComment.id).filter(
        TaskComment.task_id == task_id,
        TaskComment.user_id != user_id  # ← THÊM DÒNG NÀY
    ).all()
    all_comment_ids = [c[0] for c in all_comment_ids]

    if not all_comment_ids:
        return 0

    # Lấy comment IDs đã đọc
    read_comment_ids = db.session.query(TaskCommentRead.comment_id).filter(
        TaskCommentRead.user_id == user_id,
        TaskCommentRead.comment_id.in_(all_comment_ids)
    ).all()
    read_comment_ids = [c[0] for c in read_comment_ids]

    # Trả về số comment chưa đọc
    unread_count = len(all_comment_ids) - len(read_comment_ids)
    return unread_count


def mark_task_comments_as_read(task_id, user_id):
    """
    Đánh dấu TẤT CẢ comments của task là đã đọc bởi user
    """
    from app.models import TaskComment, TaskCommentRead

    # Lấy tất cả comment IDs của task
    all_comments = TaskComment.query.filter_by(task_id=task_id).all()

    for comment in all_comments:
        # Check xem đã đánh dấu chưa
        existing = TaskCommentRead.query.filter_by(
            user_id=user_id,
            comment_id=comment.id
        ).first()

        # Nếu chưa có thì tạo mới
        if not existing:
            read_record = TaskCommentRead(
                task_id=task_id,
                user_id=user_id,
                comment_id=comment.id
            )
            db.session.add(read_record)

    try:
        db.session.commit()
    except:
        db.session.rollback()

@bp.route('/dashboard')
@login_required
def dashboard():
    now = datetime.utcnow()

    # Lấy filter parameters
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    assigned_user = request.args.get('assigned_user', '')
    chart_date_from = request.args.get('chart_date_from', '')
    chart_date_to = request.args.get('chart_date_to', '')

    # Statistics for director and manager
    if current_user.role in ['director', 'manager']:
        # Base query for stats
        stats_query = Task.query

        # Apply date filters for stats
        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                date_from_utc = vn_to_utc(date_from_dt)
                stats_query = stats_query.filter(Task.created_at >= date_from_utc)
            except:
                pass

        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
                date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
                date_to_utc = vn_to_utc(date_to_dt)
                stats_query = stats_query.filter(Task.created_at <= date_to_utc)
            except:
                pass

        # Apply assigned user filter for stats
        if assigned_user:
            task_ids = [a.task_id for a in TaskAssignment.query.filter_by(
                user_id=int(assigned_user),
                accepted=True
            ).all()]
            stats_query = stats_query.filter(Task.id.in_(task_ids))

        # Calculate statistics with filters
        total_tasks = stats_query.count()
        pending = stats_query.filter_by(status='PENDING').count()
        in_progress = stats_query.filter_by(status='IN_PROGRESS').count()
        done = stats_query.filter_by(status='DONE').count()

        # Count badges for each status
        pending_urgent = stats_query.filter_by(status='PENDING', is_urgent=True).count()
        pending_important = stats_query.filter_by(status='PENDING', is_important=True).count()
        pending_recurring = stats_query.filter_by(status='PENDING', is_recurring=True).count()

        in_progress_urgent = stats_query.filter_by(status='IN_PROGRESS', is_urgent=True).count()
        in_progress_important = stats_query.filter_by(status='IN_PROGRESS', is_important=True).count()
        in_progress_recurring = stats_query.filter_by(status='IN_PROGRESS', is_recurring=True).count()

        done_urgent = stats_query.filter_by(status='DONE', is_urgent=True).count()
        done_important = stats_query.filter_by(status='DONE', is_important=True).count()
        done_recurring = stats_query.filter_by(status='DONE', is_recurring=True).count()

        total_urgent = stats_query.filter_by(is_urgent=True).count()
        total_important = stats_query.filter_by(is_important=True).count()
        total_recurring = stats_query.filter_by(is_recurring=True).count()

        # ===== ĐẾM NHIỆM VỤ QUÁ HẠN (chỉ count, không query all) =====
        overdue_query = Task.query.filter(
            Task.due_date < now,
            Task.status.in_(['PENDING', 'IN_PROGRESS'])
        )

        # Apply filters
        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                date_from_utc = vn_to_utc(date_from_dt)
                overdue_query = overdue_query.filter(Task.due_date >= date_from_utc)
            except:
                pass

        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
                date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
                date_to_utc = vn_to_utc(date_to_dt)
                overdue_query = overdue_query.filter(Task.due_date <= date_to_utc)
            except:
                pass

        if assigned_user:
            task_ids = [a.task_id for a in TaskAssignment.query.filter_by(
                user_id=int(assigned_user),
                accepted=True
            ).all()]
            overdue_query = overdue_query.filter(Task.id.in_(task_ids))

        overdue_count = overdue_query.count()  # CHỈ COUNT, KHÔNG QUERY ALL
        # ===== END =====

        # Get all users for filter dropdown
        all_users = User.query.filter_by(is_active=True).order_by(User.full_name).all()

        # ===== DỮ LIỆU CHO BIỂU ĐỒ =====

        # 1. PIE CHART DATA - Phân bổ trạng thái
        pie_chart_data = {
            'labels': ['Chưa làm', 'Đang làm', 'Hoàn thành'],
            'data': [pending, in_progress, done],
            'colors': ['#ffc107', '#0dcaf0', '#198754']
        }

        # 2. BAR CHART DATA - Hiệu suất nhân viên
        bar_chart_data = {'labels': [], 'done_on_time': [], 'done_overdue': [], 'overdue': []}

        # Lấy danh sách nhân viên có nhiệm vụ
        users_with_tasks = User.query.filter(
            User.is_active == True,
            User.role.in_(['hr', 'accountant', 'manager'])
        ).all()

        for user in users_with_tasks:
            # Lấy tất cả nhiệm vụ của user này
            user_assignments = TaskAssignment.query.filter_by(
                user_id=user.id,
                accepted=True
            ).all()
            user_task_ids = [a.task_id for a in user_assignments]

            if not user_task_ids:
                continue

            user_tasks_query = stats_query.filter(Task.id.in_(user_task_ids))

            # Đếm số nhiệm vụ theo loại
            done_on_time = user_tasks_query.filter_by(
                status='DONE',
                completed_overdue=False
            ).count()

            done_late = user_tasks_query.filter_by(
                status='DONE',
                completed_overdue=True
            ).count()

            overdue = user_tasks_query.filter(
                Task.due_date < now,
                Task.status.in_(['PENDING', 'IN_PROGRESS'])
            ).count()

            # Chỉ thêm nếu user có ít nhất 1 nhiệm vụ
            if done_on_time > 0 or done_late > 0 or overdue > 0:
                bar_chart_data['labels'].append(user.full_name)
                bar_chart_data['done_on_time'].append(done_on_time)
                bar_chart_data['done_overdue'].append(done_late)
                bar_chart_data['overdue'].append(overdue)

        # 3. LINE CHART DATA - Xu hướng theo khoảng thời gian tùy chọn
        line_chart_data = {
            'labels': [],
            'completed_on_time': [],
            'completed_overdue': [],
            'overdue': [],
            'created': []
        }

        # Xác định khoảng thời gian
        if chart_date_from and chart_date_to:
            try:
                start_date = datetime.strptime(chart_date_from, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
                end_date = datetime.strptime(chart_date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)

                if (end_date - start_date).days > 90:
                    end_date = start_date + timedelta(days=90)
                    flash('Chỉ hiển thị tối đa 90 ngày. Đã điều chỉnh khoảng thời gian.', 'warning')
            except:
                end_date = datetime.utcnow().replace(hour=23, minute=59, second=59)
                start_date = end_date - timedelta(days=29)
        else:
            end_date = datetime.utcnow().replace(hour=23, minute=59, second=59)
            start_date = end_date - timedelta(days=29)

        total_days = (end_date - start_date).days + 1

        # Lấy dữ liệu từng ngày
        for i in range(total_days):
            day = start_date + timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0)
            day_end = day.replace(hour=23, minute=59, second=59)

            line_chart_data['labels'].append(day.strftime('%d/%m'))

            # Hoàn thành ĐÚNG HẠN trong ngày
            completed_on_time = stats_query.filter(
                Task.status == 'DONE',
                Task.completed_overdue == False,
                Task.updated_at >= day_start,
                Task.updated_at <= day_end
            ).count()
            line_chart_data['completed_on_time'].append(completed_on_time)

            # Hoàn thành QUÁ HẠN trong ngày
            completed_late = stats_query.filter(
                Task.status == 'DONE',
                Task.completed_overdue == True,
                Task.updated_at >= day_start,
                Task.updated_at <= day_end
            ).count()
            line_chart_data['completed_overdue'].append(completed_late)

            # Nhiệm vụ quá hạn tính đến cuối ngày (chưa hoàn thành)
            overdue_count_day = stats_query.filter(
                Task.due_date < day_end,
                Task.status.in_(['PENDING', 'IN_PROGRESS'])
            ).count()
            line_chart_data['overdue'].append(overdue_count_day)

            # Nhiệm vụ tạo mới trong ngày
            created_count = stats_query.filter(
                Task.created_at >= day_start,
                Task.created_at <= day_end
            ).count()
            line_chart_data['created'].append(created_count)

        return render_template('dashboard.html',
                               total_tasks=total_tasks,
                               pending=pending,
                               in_progress=in_progress,
                               done=done,
                               # Badge counts
                               total_urgent=total_urgent,
                               total_important=total_important,
                               total_recurring=total_recurring,
                               pending_urgent=pending_urgent,
                               pending_important=pending_important,
                               pending_recurring=pending_recurring,
                               in_progress_urgent=in_progress_urgent,
                               in_progress_important=in_progress_important,
                               in_progress_recurring=in_progress_recurring,
                               done_urgent=done_urgent,
                               done_important=done_important,
                               done_recurring=done_recurring,
                               all_users=all_users,
                               date_from=date_from,
                               date_to=date_to,
                               assigned_user=assigned_user,
                               pie_chart_data=pie_chart_data,
                               bar_chart_data=bar_chart_data,
                               line_chart_data=line_chart_data,
                               chart_date_from=chart_date_from,
                               chart_date_to=chart_date_to
                               )
    else:
        # ===== ACCOUNTANT/HR: Tasks của họ =====
        my_assignments = TaskAssignment.query.filter_by(
            user_id=current_user.id,
            accepted=True
        ).all()
        my_task_ids = [a.task_id for a in my_assignments]

        # Tính toán statistics cho HR/Accountant
        my_tasks_query = Task.query.filter(Task.id.in_(my_task_ids))

        # Apply date filters
        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                date_from_utc = vn_to_utc(date_from_dt)
                my_tasks_query = my_tasks_query.filter(Task.created_at >= date_from_utc)
            except:
                pass

        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
                date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
                date_to_utc = vn_to_utc(date_to_dt)
                my_tasks_query = my_tasks_query.filter(Task.created_at <= date_to_utc)
            except:
                pass

        # Statistics
        total_tasks = my_tasks_query.count()
        pending = my_tasks_query.filter_by(status='PENDING').count()
        in_progress = my_tasks_query.filter_by(status='IN_PROGRESS').count()
        done = my_tasks_query.filter_by(status='DONE').count()

        # Badge counts
        pending_urgent = my_tasks_query.filter_by(status='PENDING', is_urgent=True).count()
        pending_important = my_tasks_query.filter_by(status='PENDING', is_important=True).count()
        pending_recurring = my_tasks_query.filter_by(status='PENDING', is_recurring=True).count()

        in_progress_urgent = my_tasks_query.filter_by(status='IN_PROGRESS', is_urgent=True).count()
        in_progress_important = my_tasks_query.filter_by(status='IN_PROGRESS', is_important=True).count()
        in_progress_recurring = my_tasks_query.filter_by(status='IN_PROGRESS', is_recurring=True).count()

        done_urgent = my_tasks_query.filter_by(status='DONE', is_urgent=True).count()
        done_important = my_tasks_query.filter_by(status='DONE', is_important=True).count()
        done_recurring = my_tasks_query.filter_by(status='DONE', is_recurring=True).count()

        total_urgent = my_tasks_query.filter_by(is_urgent=True).count()
        total_important = my_tasks_query.filter_by(is_important=True).count()
        total_recurring = my_tasks_query.filter_by(is_recurring=True).count()

        # ===== ĐẾM NHIỆM VỤ QUÁ HẠN của user này (chỉ count) =====
        overdue_query = Task.query.filter(
            Task.id.in_(my_task_ids),
            Task.due_date < now,
            Task.status.in_(['PENDING', 'IN_PROGRESS'])
        )

        # Apply date filters
        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                date_from_utc = vn_to_utc(date_from_dt)
                overdue_query = overdue_query.filter(Task.due_date >= date_from_utc)
            except:
                pass

        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
                date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
                date_to_utc = vn_to_utc(date_to_dt)
                overdue_query = overdue_query.filter(Task.due_date <= date_to_utc)
            except:
                pass

        overdue_count = overdue_query.count()  # CHỈ COUNT, KHÔNG QUERY ALL

        return render_template('dashboard.html',
                               # Stats cho HR/Accountant
                               total_tasks=total_tasks,
                               pending=pending,
                               in_progress=in_progress,
                               done=done,
                               total_urgent=total_urgent,
                               total_important=total_important,
                               total_recurring=total_recurring,
                               pending_urgent=pending_urgent,
                               pending_important=pending_important,
                               pending_recurring=pending_recurring,
                               in_progress_urgent=in_progress_urgent,
                               in_progress_important=in_progress_important,
                               in_progress_recurring=in_progress_recurring,
                               done_urgent=done_urgent,
                               done_important=done_important,
                               done_recurring=done_recurring,
                               date_from=date_from,
                               date_to=date_to)


@bp.route('/')
@bp.route('/status/<status>')
@login_required
def list_tasks(status=None):
    # Lấy status từ URL parameter hoặc query string
    if status is None:
        status = request.args.get('status', '')

    # Validate status nếu có
    valid_statuses = ['PENDING', 'IN_PROGRESS', 'DONE']
    if status and status not in valid_statuses:
        flash('Trạng thái không hợp lệ.', 'danger')
        return redirect(url_for('tasks.list_tasks'))

    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    assigned_user = request.args.get('assigned_user', '')
    tag_filter = request.args.get('tag', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20

    if current_user.role in ['director', 'manager']:
        query = Task.query

        if status:
            query = query.filter_by(status=status)

        # Date filters
        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                date_from_utc = vn_to_utc(date_from_dt)
                query = query.filter(Task.due_date >= date_from_utc)
            except:
                pass

        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
                date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
                date_to_utc = vn_to_utc(date_to_dt)
                query = query.filter(Task.due_date <= date_to_utc)
            except:
                pass

        # Filter by assigned user
        if assigned_user:
            task_ids = [a.task_id for a in TaskAssignment.query.filter_by(
                user_id=int(assigned_user),
                accepted=True
            ).all()]
            query = query.filter(Task.id.in_(task_ids))

        # Filter theo tags
        if tag_filter == 'urgent':
            query = query.filter_by(is_urgent=True)
        elif tag_filter == 'important':
            query = query.filter_by(is_important=True)
        elif tag_filter == 'recurring':
            query = query.filter_by(is_recurring=True)

        pagination = query.order_by(Task.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        tasks = pagination.items

        all_users = User.query.filter_by(is_active=True).order_by(User.full_name).all()
    else:
        # Only see assigned tasks
        accepted_assignments = TaskAssignment.query.filter_by(
            user_id=current_user.id,
            accepted=True
        ).all()
        assigned_task_ids = [a.task_id for a in accepted_assignments]

        query = Task.query.filter(
            or_(
                Task.id.in_(assigned_task_ids),
                Task.creator_id == current_user.id
            )
        )

        if status:
            query = query.filter_by(status=status)

        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                date_from_utc = vn_to_utc(date_from_dt)
                query = query.filter(Task.due_date >= date_from_utc)
            except:
                pass

        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
                date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
                date_to_utc = vn_to_utc(date_to_dt)
                query = query.filter(Task.due_date <= date_to_utc)
            except:
                pass

        # Filter theo tags
        if tag_filter == 'urgent':
            query = query.filter_by(is_urgent=True)
        elif tag_filter == 'important':
            query = query.filter_by(is_important=True)
        elif tag_filter == 'recurring':
            query = query.filter_by(is_recurring=True)

        pagination = query.order_by(Task.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        tasks = pagination.items
        all_users = None

    status_names = {
        'PENDING': 'Chưa Làm',
        'IN_PROGRESS': 'Đang Làm',
        'DONE': 'Hoàn thành',
        '': 'Tất cả nhiệm vụ'
    }
    status_name = status_names.get(status, 'Tất cả nhiệm vụ')

    return render_template('tasks.html',
                           tasks=tasks,
                           pagination=pagination,
                           status_filter=status or '',
                           status_name=status_name,
                           date_from=date_from,
                           date_to=date_to,
                           assigned_user=assigned_user,
                           tag_filter=tag_filter,
                           all_users=all_users)


@bp.route('/<int:task_id>')
@login_required
def task_detail(task_id):
    task = Task.query.get(task_id)

    if not task:
        flash('Nhiệm vụ này này đã bị xóa hoặc không tồn tại.', 'warning')
        return redirect(url_for('tasks.dashboard'))

    # Check permission
    if current_user.role not in ['director', 'manager']:
        # Check if user is assigned or creator
        assignment = TaskAssignment.query.filter_by(
            task_id=task_id,
            user_id=current_user.id
        ).first()

        if not assignment and task.creator_id != current_user.id:
            flash('Bạn không có quyền xem tnhiệm vụ này.', 'danger')
            return redirect(url_for('tasks.list_tasks'))

    # Get assignment for current user
    user_assignment = TaskAssignment.query.filter_by(
        task_id=task_id,
        user_id=current_user.id
    ).first()

    # Mark as seen
    if user_assignment and not user_assignment.seen:
        user_assignment.seen = True
        db.session.commit()

    mark_task_comments_as_read(task_id, current_user.id)

    # Get all assignments
    assignments = TaskAssignment.query.filter_by(task_id=task_id).all()

    sorted_comments = TaskComment.query.filter_by(task_id=task_id).order_by(TaskComment.created_at.asc()).all()

    return render_template('task_detail.html',
                           task=task,
                           user_assignment=user_assignment,
                           assignments=assignments,
                           sorted_comments=sorted_comments)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_task():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        due_date_str = request.form.get('due_date')
        assign_type = request.form.get('assign_type')
        assign_to_user_id = request.form.get('assign_to_user')
        assign_to_group = request.form.get('assign_to_group')
        assign_to_multiple = request.form.getlist('assign_to_multiple[]')  # ← MỚI: Lấy nhiều người
        is_urgent = request.form.get('is_urgent') == 'on'
        is_important = request.form.get('is_important') == 'on'
        is_recurring = request.form.get('is_recurring') == 'on'
        recurrence_enabled = request.form.get('recurrence_enabled') == 'on'
        recurrence_interval_days = int(request.form.get('recurrence_interval_days', 7))

        # Validate
        if not title:
            flash('Tiêu đề không được để trống.', 'danger')
            return redirect(url_for('tasks.create_task'))

        # Parse due date with time
        due_date = None
        if due_date_str:
            try:
                vn_datetime = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
                due_date = vn_to_utc(vn_datetime)
            except:
                try:
                    vn_datetime = datetime.strptime(due_date_str, '%Y-%m-%d')
                    due_date = vn_to_utc(vn_datetime)
                except:
                    flash('Định dạng ngày giờ không hợp lệ.', 'danger')
                    return redirect(url_for('tasks.create_task'))

        # Create task
        task = Task(
            title=title,
            description=description,
            creator_id=current_user.id,
            due_date=due_date,
            status='PENDING',
            is_urgent=is_urgent,
            is_important=is_important,
            is_recurring=is_recurring,
            recurrence_enabled=recurrence_enabled if current_user.can_assign_tasks() else False,
            recurrence_interval_days=recurrence_interval_days if recurrence_enabled else None,
            last_recurrence_date=datetime.utcnow() if recurrence_enabled else None
        )
        db.session.add(task)
        db.session.flush()

        # Handle assignments
        if assign_type == 'self':
            assignment = TaskAssignment(
                task_id=task.id,
                user_id=current_user.id,
                assigned_by=current_user.id,
                accepted=True,
                accepted_at=datetime.utcnow()
            )
            db.session.add(assignment)

        elif assign_type == 'user' and assign_to_user_id:
            if current_user.can_assign_tasks():
                user_id = int(assign_to_user_id)
                assignment = TaskAssignment(
                    task_id=task.id,
                    user_id=user_id,
                    assigned_by=current_user.id,
                    accepted=True,
                    accepted_at=datetime.utcnow()
                )
                db.session.add(assignment)

                notif = Notification(
                    user_id=user_id,
                    type='task_assigned',
                    title='Nhiệm vụ mới được giao',
                    body=f'{current_user.full_name} đã giao nhiệm vụ {title} cho bạn.',
                    link=f'/tasks/{task.id}'
                )
                db.session.add(notif)
            else:
                flash('Bạn không có quyền giao nhiệm vụ cho người khác.', 'danger')
                db.session.rollback()
                return redirect(url_for('tasks.list_tasks'))

        elif assign_type == 'group' and assign_to_group:
            if current_user.can_assign_tasks():
                users_in_group = User.query.filter_by(role=assign_to_group, is_active=True).all()

                for user in users_in_group:
                    assignment = TaskAssignment(
                        task_id=task.id,
                        user_id=user.id,
                        assigned_by=current_user.id,
                        assigned_group=assign_to_group,
                        accepted=True,
                        seen=False
                    )
                    db.session.add(assignment)

                    notif = Notification(
                        user_id=user.id,
                        type='task_assigned',
                        title='Nhiệm vụ mới cho nhóm',
                        body=f'{current_user.full_name} đã giao nhiệm vụ {title} cho nhóm. Vui lòng liên hệ các thành viên trong nhóm để thảo luận và làm việc.',
                        link=f'/tasks/{task.id}'
                    )
                    db.session.add(notif)
            else:
                flash('Bạn không có quyền giao nhiệm vụ cho nhóm.', 'danger')
                db.session.rollback()
                return redirect(url_for('tasks.list_tasks'))

        # ========== MỚI: GIAO CHO NHIỀU NGƯỜI TÙY CHỌN ==========
        elif assign_type == 'multiple' and assign_to_multiple:
            if current_user.can_assign_tasks():
                if len(assign_to_multiple) == 0:
                    flash('Vui lòng chọn ít nhất 1 người.', 'warning')
                    db.session.rollback()
                    return redirect(url_for('tasks.create_task'))

                # Giao cho từng người được chọn
                for user_id_str in assign_to_multiple:
                    user_id = int(user_id_str)

                    assignment = TaskAssignment(
                        task_id=task.id,
                        user_id=user_id,
                        assigned_by=current_user.id,
                        accepted=True,
                        accepted_at=datetime.utcnow(),
                        seen=False
                    )
                    db.session.add(assignment)

                    # Gửi notification cho từng người
                    notif = Notification(
                        user_id=user_id,
                        type='task_assigned',
                        title='Nhiệm vụ mới được giao',
                        body=f'{current_user.full_name} đã giao nhiệm vụ "{title}" cho bạn.',
                        link=f'/tasks/{task.id}'
                    )
                    db.session.add(notif)

                flash(f'Đã giao nhiệm vụ cho {len(assign_to_multiple)} người.', 'success')
            else:
                flash('Bạn không có quyền giao nhiệm vụ cho nhiều người.', 'danger')
                db.session.rollback()
                return redirect(url_for('tasks.list_tasks'))
        # ========== END MỚI ==========

        db.session.commit()
        flash('Tạo nhiệm vụ thành công.', 'success')
        return redirect(url_for('tasks.task_detail', task_id=task.id))

    # GET request
    users = []
    if current_user.can_assign_tasks():
        users = User.query.filter(User.is_active == True).order_by(User.full_name).all()

    return render_template('create_task.html', users=users)


#  Route để cập nhật tags
@bp.route('/<int:task_id>/update-tags', methods=['POST'])
@login_required
@role_required(['director', 'manager'])
def update_tags(task_id):
    """Cập nhật tags cho task - chỉ Director/Manager"""
    task = Task.query.get_or_404(task_id)

    task.is_urgent = request.form.get('is_urgent') == 'on'
    task.is_important = request.form.get('is_important') == 'on'
    task.is_recurring = request.form.get('is_recurring') == 'on'
    task.updated_at = datetime.utcnow()

    db.session.commit()
    flash('Cập nhật thẻ thành công.', 'success')
    return redirect(url_for('tasks.task_detail', task_id=task_id))


@bp.route('/<int:task_id>/accept', methods=['POST'])
@login_required
def accept_task(task_id):
    """Accept a group-assigned task"""
    assignment = TaskAssignment.query.filter_by(
        task_id=task_id,
        user_id=current_user.id
    ).first_or_404()

    if assignment.accepted:
        flash('Bạn đã chấp nhận nhiệm vụ này rồi.', 'info')
        return redirect(url_for('tasks.task_detail', task_id=task_id))

    assignment.accepted = True
    assignment.accepted_at = datetime.utcnow()
    db.session.commit()

    flash('Bạn đã chấp nhận nhiệm vụ thành công.', 'success')
    return redirect(url_for('tasks.task_detail', task_id=task_id))


@bp.route('/<int:task_id>/reject', methods=['POST'])
@login_required
def reject_task(task_id):
    """Reject a group-assigned task"""
    assignment = TaskAssignment.query.filter_by(
        task_id=task_id,
        user_id=current_user.id
    ).first_or_404()

    if assignment.accepted:
        flash('Bạn đã chấp nhận nhiệm vụ này, không thể từ chối.', 'danger')
        return redirect(url_for('tasks.task_detail', task_id=task_id))

    db.session.delete(assignment)
    db.session.commit()

    return redirect(url_for('tasks.list_tasks'))


@bp.route('/<int:task_id>/update-status', methods=['POST'])
@login_required
def update_status(task_id):
    task = Task.query.get_or_404(task_id)
    new_status = request.form.get('status')
    completion_note = request.form.get('completion_note', '')
    old_status = task.status

    if new_status not in ['PENDING', 'IN_PROGRESS', 'DONE', 'CANCELLED']:
        flash('Trạng thái không hợp lệ.', 'danger')
        return redirect(url_for('tasks.task_detail', task_id=task_id))

    now = datetime.utcnow()
    is_overdue = task.due_date and task.due_date < now and task.status in ['PENDING', 'IN_PROGRESS']

    # Check permission
    if current_user.role in ['director', 'manager']:
        pass
    else:
        assignment = TaskAssignment.query.filter_by(
            task_id=task_id,
            user_id=current_user.id,
            accepted=True
        ).first()

        if not assignment and task.creator_id != current_user.id:
            flash('Bạn không có quyền cập nhật nhiệm vụ này.', 'danger')
            return redirect(url_for('tasks.task_detail', task_id=task_id))

        if old_status == 'DONE':
            flash('Nhiệm vụ đã hoàn thành và bị khóa. Chỉ Giám đốc hoặc Trưởng phòng mới có thể cập nhật trạng thái.',
                  'danger')
            return redirect(url_for('tasks.task_detail', task_id=task_id))

    # ===== XỬ LÝ KHI CHUYỂN SANG DONE =====
    if new_status == 'DONE' and old_status != 'DONE':
        # Tính thời gian
        completion_time = None
        if task.created_at:
            time_delta = now - task.created_at
            completion_time = int(time_delta.total_seconds() / 60)

        # Set flag quá hạn
        if is_overdue:
            task.completed_overdue = True
            flash('⚠️ Nhiệm vụ đã hoàn thành nhưng QUÁ HẠN!', 'warning')
        else:
            task.completed_overdue = False
            flash('✅ Nhiệm vụ đã hoàn thành ĐÚNG HẠN!', 'success')

        # TẠO BÁO CÁO
        from app.models import TaskCompletionReport

        completion_report = TaskCompletionReport(
            task_id=task.id,
            completed_by=current_user.id,
            completion_note=completion_note if completion_note else None,
            completed_at=now,
            was_overdue=task.completed_overdue,
            completion_time=completion_time
        )
        db.session.add(completion_report)

        # ===== LOGIC MỚI: TỰ ĐỘNG ĐÁNH GIÁ =====
        creator = task.creator

        # TRƯỜNG HỢP 1: Giám đốc hoàn thành nhiệm vụ do Trưởng phòng giao
        # => Tự động đánh giá TỐT
        if current_user.role == 'director' and creator.role == 'manager':
            task.performance_rating = 'good'
            task.rated_by = creator.id  # Người giao việc (manager) đánh giá
            task.rated_at = now

            flash('✅ Nhiệm vụ được tự động đánh giá TỐT vì Giám đốc hoàn thành!', 'success')

            # Gửi thông báo cho Manager
            notif = Notification(
                user_id=creator.id,
                type='task_completed',
                title='Thông báo',
                body=f'Giám đốc {current_user.full_name} đã hoàn thành nhiệm vụ "{task.title}" ',
                link=f'/tasks/{task.id}'
            )
            db.session.add(notif)

        # TRƯỜNG HỢP 2: Trưởng phòng hoàn thành nhiệm vụ do Giám đốc giao
        # => GỬI THÔNG BÁO CHO GIÁM ĐỐC để đánh giá
        elif current_user.role == 'manager' and creator.role == 'director':
            # Gửi thông báo cho Giám đốc
            notif_title = '⚠️ Nhiệm vụ hoàn thành QUÁ HẠN' if task.completed_overdue else '✅ Nhiệm vụ hoàn thành ĐÚNG HẠN'
            notif_body = f'Trưởng phòng {current_user.full_name} đã hoàn thành: {task.title}'
            if completion_note:
                notif_body += f'\n Với báo cáo: {completion_note}'

            creator_notif = Notification(
                user_id=creator.id,
                type='task_completed',
                title=notif_title,
                body=notif_body,
                link=f'/tasks/{task.id}'
            )
            db.session.add(creator_notif)

            # Thông báo nhắc đánh giá
            rating_reminder = Notification(
                user_id=creator.id,
                type='task_needs_rating',
                title='🌟 Cần đánh giá hiệu suất',
                body=f'Nhiệm vụ "{task.title}" đã hoàn thành bởi Trưởng phòng {current_user.full_name}. Vui lòng đánh giá hiệu suất!',
                link=f'/tasks/{task.id}'
            )
            db.session.add(rating_reminder)

        # TRƯỜNG HỢP 3: Các trường hợp khác (HR, Accountant, etc.)
        else:
            # Logic cũ - gửi thông báo cho người giao việc
            if task.completed_overdue:
                notif_title = '⚠️ Nhiệm vụ hoàn thành QUÁ HẠN'
            else:
                notif_title = '✅ Nhiệm vụ hoàn thành ĐÚNG HẠN'

            notif_body = f'{current_user.full_name} đã hoàn thành: {task.title}'
            if completion_note:
                notif_body += f'\n----- Ghi chú: {completion_note}'

            # Gửi cho người giao việc (nếu không phải chính mình)
            if creator.id != current_user.id:
                creator_notif = Notification(
                    user_id=creator.id,
                    type='task_completed',
                    title=notif_title,
                    body=notif_body,
                    link=f'/tasks/{task.id}'
                )
                db.session.add(creator_notif)

                # Nhắc đánh giá
                rating_reminder = Notification(
                    user_id=creator.id,
                    type='task_needs_rating',
                    title='🌟 Cần đánh giá hiệu suất',
                    body=f'Nhiệm vụ "{task.title}" đã hoàn thành bởi {current_user.full_name}. Vui lòng đánh giá hiệu suất!',
                    link=f'/tasks/{task.id}'
                )
                db.session.add(rating_reminder)

            # Gửi cho director/manager khác (nếu có)
            managers = User.query.filter(
                User.role.in_(['director', 'manager']),
                User.is_active == True,
                User.id != current_user.id,
                User.id != creator.id
            ).all()

            for manager in managers:
                manager_notif = Notification(
                    user_id=manager.id,
                    type='task_completed',
                    title=notif_title,
                    body=notif_body,
                    link=f'/tasks/{task.id}'
                )
                db.session.add(manager_notif)

    elif old_status == 'DONE' and new_status != 'DONE':
        task.completed_overdue = False
        # Xóa đánh giá tự động nếu mở lại task
        task.performance_rating = None
        task.rated_by = None
        task.rated_at = None
        flash('Đã mở lại nhiệm vụ.', 'info')

    # Update status
    task.status = new_status
    task.updated_at = datetime.utcnow()
    db.session.commit()

    if new_status != 'DONE' and old_status != new_status:
        flash('Cập nhật trạng thái thành công.', 'success')

    return redirect(url_for('tasks.task_detail', task_id=task_id))


@bp.route('/bulk-delete', methods=['POST'])
@login_required
@role_required(['director', 'manager'])
def bulk_delete_tasks():
    """Xóa nhiều tasks cùng lúc - chỉ dành cho Director/Manager"""
    task_ids = request.form.getlist('task_ids[]')

    if not task_ids:
        flash('Vui lòng chọn ít nhất một nhiệm vụ để xóa.', 'warning')
        return redirect(url_for('tasks.list_tasks'))

    try:
        # Convert to integers
        task_ids = [int(id) for id in task_ids]

        # QUAN TRỌNG: Thứ tự xóa phải đúng!
        # 1. Xóa TaskCompletionReport trước (vì có FK đến tasks)
        from app.models import TaskCompletionReport
        TaskCompletionReport.query.filter(
            TaskCompletionReport.task_id.in_(task_ids)
        ).delete(synchronize_session=False)

        # 2. Xóa TaskAssignment
        TaskAssignment.query.filter(
            TaskAssignment.task_id.in_(task_ids)
        ).delete(synchronize_session=False)

        # 3. Xóa Notifications liên quan
        for task_id in task_ids:
            Notification.query.filter(
                Notification.link == f'/tasks/{task_id}'
            ).delete(synchronize_session=False)

        # 4. Cuối cùng xóa Tasks
        deleted_count = Task.query.filter(
            Task.id.in_(task_ids)
        ).delete(synchronize_session=False)

        db.session.commit()

        flash(f'Đã xóa thành công {deleted_count} nhiệm vụ.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Có lỗi xảy ra khi xóa: {str(e)}', 'danger')

    return redirect(url_for('tasks.list_tasks'))


@bp.route('/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)

    if current_user.role not in ['director', 'manager'] and task.creator_id != current_user.id:
        flash('Bạn không có quyền xóa nhiệm vụ này.', 'danger')
        return redirect(url_for('tasks.task_detail', task_id=task_id))

    try:
        # Xóa tất cả assignments liên quan trước
        TaskAssignment.query.filter_by(task_id=task_id).delete()

        # Xóa notifications liên quan đến task này
        Notification.query.filter(Notification.link == f'/tasks/{task_id}').delete()

        # Sau đó xóa task
        db.session.delete(task)
        db.session.commit()

        flash('Đã xóa thành công.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Có lỗi xảy ra khi xóa: {str(e)}', 'danger')
        return redirect(url_for('tasks.task_detail', task_id=task_id))

    return redirect(url_for('tasks.list_tasks'))


@bp.route('/<int:task_id>/rate', methods=['POST'])
@login_required
@role_required(['director', 'manager'])
def rate_task(task_id):
    """Đánh giá nhiệm vụ - chỉ Director/Manager và task phải DONE"""
    task = Task.query.get_or_404(task_id)

    # Kiểm tra task đã hoàn thành chưa
    if task.status != 'DONE':
        flash('Chỉ có thể đánh giá nhiệm vụ đã hoàn thành.', 'warning')
        return redirect(url_for('tasks.task_detail', task_id=task_id))

    rating = request.form.get('rating')

    if rating not in ['good', 'bad']:
        flash('Đánh giá không hợp lệ.', 'danger')
        return redirect(url_for('tasks.task_detail', task_id=task_id))

    # Cập nhật đánh giá
    task.performance_rating = rating
    task.rated_by = current_user.id
    task.rated_at = datetime.utcnow()

    db.session.commit()

    # Gửi thông báo cho người làm task
    assigned_users = TaskAssignment.query.filter_by(
        task_id=task_id,
        accepted=True
    ).all()

    rating_text = "TỐT 👍" if rating == 'good' else "CẦN CẢI THIỆN 👎"

    for assignment in assigned_users:
        notif = Notification(
            user_id=assignment.user_id,
            type='task_rated',
            title=f'Đánh giá nhiệm vụ của bạn',
            body=f'{current_user.full_name} đã đánh giá nhiệm vụ "{task.title}" là {rating_text}',
            link=f'/tasks/{task.id}'
        )
        db.session.add(notif)

    db.session.commit()

    flash(f'Đã đánh giá nhiệm vụ: {rating_text}', 'success')
    return redirect(url_for('tasks.task_detail', task_id=task_id))


# ============================================
#  KANBAN BOARD ROUTES
# ============================================

@bp.route('/kanban')
@login_required
def kanban():
    """Kanban Board - Hiển thị tasks theo dạng cột"""
    # Get filters
    assigned_user = request.args.get('assigned_user', '')
    tag_filter = request.args.get('tag', '')
    search = request.args.get('search', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    now = datetime.utcnow()

    # Base query theo role
    if current_user.role in ['director', 'manager']:
        query = Task.query
    else:
        # HR/Accountant: only their tasks
        accepted_assignments = TaskAssignment.query.filter_by(
            user_id=current_user.id,
            accepted=True
        ).all()
        assigned_task_ids = [a.task_id for a in accepted_assignments]
        query = Task.query.filter(
            or_(
                Task.id.in_(assigned_task_ids),
                Task.creator_id == current_user.id
            )
        )

    # Apply date filters
    if date_from:
        try:
            date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
            from app.utils import vn_to_utc
            date_from_utc = vn_to_utc(date_from_dt)
            query = query.filter(Task.created_at >= date_from_utc)
        except:
            pass

    if date_to:
        try:
            date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
            date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
            from app.utils import vn_to_utc
            date_to_utc = vn_to_utc(date_to_dt)
            query = query.filter(Task.created_at <= date_to_utc)
        except:
            pass

    # Apply filters
    if assigned_user:
        task_ids = [a.task_id for a in TaskAssignment.query.filter_by(
            user_id=int(assigned_user),
            accepted=True
        ).all()]
        query = query.filter(Task.id.in_(task_ids))

    if tag_filter == 'urgent':
        query = query.filter_by(is_urgent=True)
    elif tag_filter == 'important':
        query = query.filter_by(is_important=True)
    elif tag_filter == 'recurring':
        query = query.filter_by(is_recurring=True)

    if search:
        query = query.filter(Task.title.ilike(f'%{search}%'))

    # Get all tasks
    all_tasks = query.all()

    # Custom sort function
    def sort_tasks(task):
        # Priority 1: Quá hạn (cao nhất)
        is_overdue = task.due_date and task.due_date < now and task.status != 'DONE'

        # Return tuple for sorting (False comes before True, so negate for priority)
        return (
            not is_overdue,  # Quá hạn lên đầu
            not task.is_urgent,  # Khẩn cấp thứ 2
            not task.is_important,  # Quan trọng thứ 3
            not task.is_recurring,  # Lặp lại thứ 4
            task.created_at.timestamp() * -1  # Mới nhất lên đầu (negate để reverse)
        )

    def sort_done_tasks(task):
        """DONE tasks: Sắp xếp theo ngày hoàn thành (updated_at), mới nhất lên đầu"""
        return task.updated_at.timestamp() * -1

    # Phân loại tasks theo status và sắp xếp
    pending_tasks = sorted([t for t in all_tasks if t.status == 'PENDING'], key=sort_tasks)
    in_progress_tasks = sorted([t for t in all_tasks if t.status == 'IN_PROGRESS'], key=sort_tasks)
    done_tasks = sorted([t for t in all_tasks if t.status == 'DONE'], key=sort_done_tasks)

    # Get all users for filter
    all_users = None
    if current_user.role in ['director', 'manager']:
        all_users = User.query.filter_by(is_active=True).order_by(User.full_name).all()

    return render_template('kanban.html',
                           pending_tasks=pending_tasks,
                           in_progress_tasks=in_progress_tasks,
                           done_tasks=done_tasks,
                           all_users=all_users,
                           assigned_user=assigned_user,
                           tag_filter=tag_filter,
                           search=search,
                           date_from=date_from,
                           date_to=date_to,
                           now=now)


@bp.route('/priority-detail')
@login_required
def priority_detail():
    """
    Trang chi tiết công việc theo loại ưu tiên
    Params:
    - assigned_user: ID người được giao
    - tag: urgent/important/recurring
    - status: DONE (cho hoàn thành)
    - date_from, date_to: filter theo ngày (optional)
    """
    assigned_user_id = request.args.get('assigned_user', type=int)
    tag = request.args.get('tag', '')
    status = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    if not assigned_user_id:
        flash('Thiếu thông tin người dùng.', 'danger')
        return redirect(url_for('hub.workflow_hub'))

    # Lấy thông tin user
    user = User.query.get_or_404(assigned_user_id)

    # Base query
    query = db.session.query(Task).join(
        TaskAssignment, Task.id == TaskAssignment.task_id
    ).filter(
        TaskAssignment.user_id == assigned_user_id,
        TaskAssignment.accepted == True
    )

    # Apply filters
    if date_from:
        try:
            date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
            date_from_utc = vn_to_utc(date_from_dt)
            query = query.filter(Task.created_at >= date_from_utc)
        except:
            pass

    if date_to:
        try:
            date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
            date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
            date_to_utc = vn_to_utc(date_to_dt)
            query = query.filter(Task.created_at <= date_to_utc)
        except:
            pass

    # Xác định loại và filter
    priority_type = ''
    priority_icon = ''
    priority_color = ''

    if tag == 'urgent':
        query = query.filter(Task.is_urgent == True, Task.status != 'DONE')
        priority_type = 'KHẨN CẤP'
        priority_icon = '🔴'
        priority_color = 'danger'
    elif tag == 'important':
        query = query.filter(Task.is_important == True, Task.status != 'DONE')
        priority_type = 'QUAN TRỌNG'
        priority_icon = '⭐'
        priority_color = 'warning'
    elif tag == 'recurring':
        query = query.filter(Task.is_recurring == True, Task.status != 'DONE')
        priority_type = 'LẶP LẠI'
        priority_icon = '🔁'
        priority_color = 'info'
    elif status == 'DONE':
        query = query.filter(Task.status == 'DONE')
        priority_type = 'HOÀN THÀNH'
        priority_icon = '✅'
        priority_color = 'success'
    else:
        flash('Loại công việc không hợp lệ.', 'danger')
        return redirect(url_for('hub.workflow_hub'))

    if status == 'DONE':
        all_tasks = query.order_by(Task.updated_at.desc()).all()
    else:
        from sqlalchemy import case, func

        priority_order = case(
            (Task.due_date.is_(None), 3),  # Không có hạn → xuống dưới cùng
            (Task.due_date < func.now(), 1),  # QUÁ HẠN → lên đầu
            else_=2  # CÒN HẠN
        )

        all_tasks = query.order_by(
            priority_order.asc(),  # 1 → 2 → 3
            Task.due_date.asc().nulls_last()  # Trong cùng nhóm: hạn gần nhất trước, nulls xuống dưới
        ).all()

    # Đếm còn hạn và quá hạn
    now = datetime.utcnow()
    on_time_count = 0
    overdue_count = 0

    for task in all_tasks:
        if task.due_date:
            task.vn_due_date = utc_to_vn(task.due_date)

        # Đếm on-time và overdue
        if task.status != 'DONE' and task.due_date:
            if task.due_date >= now:
                on_time_count += 1
            else:
                overdue_count += 1

    # ✅ TÍNH UNREAD COMMENT COUNT CHO MỖI TASK
    for task in all_tasks:
        task.unread_comment_count = get_task_unread_comment_count(task.id, current_user.id)

    return render_template('priority_detail.html',
                           user=user,
                           tasks=all_tasks,
                           priority_type=priority_type,
                           priority_icon=priority_icon,
                           priority_color=priority_color,
                           on_time_count=on_time_count,
                           overdue_count=overdue_count,
                           tag=tag,
                           status=status)


@bp.route('/<int:task_id>/quick-update-status', methods=['POST'])
@login_required
def quick_update_status(task_id):
    """
    API cập nhật nhanh trạng thái task (cho nút Bắt đầu/Hoàn thành)
    """
    task = Task.query.get_or_404(task_id)
    new_status = request.json.get('status')

    if new_status not in ['IN_PROGRESS', 'DONE']:
        return jsonify({'success': False, 'error': 'Trạng thái không hợp lệ'}), 400

    # Check permission
    assignment = TaskAssignment.query.filter_by(
        task_id=task_id,
        user_id=current_user.id,
        accepted=True
    ).first()

    if not assignment and current_user.role not in ['director', 'manager']:
        return jsonify({'success': False, 'error': 'Không có quyền'}), 403

    now = datetime.utcnow()
    old_status = task.status

    # Update status
    if new_status == 'DONE' and old_status != 'DONE':
        is_overdue = task.due_date and task.due_date < now
        task.completed_overdue = is_overdue

        # Tính completion time
        completion_time = None
        if task.created_at:
            time_delta = now - task.created_at
            completion_time = int(time_delta.total_seconds() / 60)

        # Tạo báo cáo
        from app.models import TaskCompletionReport
        completion_report = TaskCompletionReport(
            task_id=task.id,
            completed_by=current_user.id,
            completion_note=None,
            completed_at=now,
            was_overdue=is_overdue,
            completion_time=completion_time
        )
        db.session.add(completion_report)

        # Logic đánh giá tự động (giống như route update_status)
        creator = task.creator
        if current_user.role == 'director' and creator.role == 'manager':
            task.performance_rating = 'good'
            task.rated_by = creator.id
            task.rated_at = now
        elif current_user.role == 'manager' and creator.role == 'director':
            # Gửi thông báo
            notif = Notification(
                user_id=creator.id,
                type='task_completed',
                title='✅ Nhiệm vụ hoàn thành',
                body=f'Trưởng phòng {current_user.full_name} đã hoàn thành: {task.title}',
                link=f'/tasks/{task.id}'
            )
            db.session.add(notif)

    task.status = new_status
    task.updated_at = now
    db.session.commit()

    return jsonify({
        'success': True,
        'new_status': new_status,
        'message': 'Cập nhật thành công'
    })

import os
from werkzeug.utils import secure_filename
from flask import send_from_directory

# Config upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'zip', 'rar'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_type(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
        return 'image'
    elif ext in ['pdf']:
        return 'pdf'
    elif ext in ['doc', 'docx']:
        return 'document'
    elif ext in ['xls', 'xlsx']:
        return 'spreadsheet'
    elif ext in ['zip', 'rar']:
        return 'archive'
    else:
        return 'other'


# ============================================
# TASK ATTACHMENTS
# ============================================

@bp.route('/<int:task_id>/upload-attachment', methods=['POST'])
@login_required
def upload_attachment(task_id):
    """Upload file đính kèm vào task"""
    task = Task.query.get_or_404(task_id)

    # Check permission
    assignment = TaskAssignment.query.filter_by(
        task_id=task_id,
        user_id=current_user.id,
        accepted=True
    ).first()

    if not assignment and current_user.role not in ['director', 'manager']:
        return jsonify({'success': False, 'error': 'Không có quyền'}), 403

    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Không có file'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'success': False, 'error': 'Chưa chọn file'}), 400

    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Loại file không được phép'}), 400

    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    if file_size > MAX_FILE_SIZE:
        return jsonify({'success': False, 'error': 'File quá lớn (tối đa 10MB)'}), 400

    try:
        # Save file
        filename = secure_filename(file.filename)
        unique_filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{filename}"

        upload_folder = os.path.join(current_app.root_path, 'uploads', 'task_attachments')
        os.makedirs(upload_folder, exist_ok=True)

        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)

        # Save to database
        from app.models import TaskAttachment
        attachment = TaskAttachment(
            task_id=task_id,
            uploaded_by=current_user.id,
            filename=unique_filename,
            original_filename=filename,
            file_path=file_path,
            file_size=file_size,
            file_type=get_file_type(filename)
        )
        db.session.add(attachment)
        db.session.commit()

        return jsonify({
            'success': True,
            'attachment': {
                'id': attachment.id,
                'filename': attachment.original_filename,
                'file_type': attachment.file_type,
                'file_size': attachment.file_size,
                'uploaded_by': current_user.full_name,
                'uploaded_at': attachment.uploaded_at.isoformat()
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:task_id>/attachments/<int:attachment_id>/download')
@login_required
def download_attachment(task_id, attachment_id):
    """Download file đính kèm"""
    from app.models import TaskAttachment
    attachment = TaskAttachment.query.get_or_404(attachment_id)

    if attachment.task_id != task_id:
        flash('File không tồn tại', 'danger')
        return redirect(url_for('tasks.task_detail', task_id=task_id))

    # Check permission
    task = Task.query.get_or_404(task_id)
    assignment = TaskAssignment.query.filter_by(
        task_id=task_id,
        user_id=current_user.id,
        accepted=True
    ).first()

    if not assignment and task.creator_id != current_user.id and current_user.role not in ['director', 'manager']:
        flash('Bạn không có quyền tải file này', 'danger')
        return redirect(url_for('tasks.task_detail', task_id=task_id))

    directory = os.path.dirname(attachment.file_path)
    return send_from_directory(directory, attachment.filename, as_attachment=True,
                               download_name=attachment.original_filename)


@bp.route('/<int:task_id>/attachments/<int:attachment_id>/delete', methods=['POST'])
@login_required
def delete_attachment(task_id, attachment_id):
    """Xóa file đính kèm"""
    from app.models import TaskAttachment
    attachment = TaskAttachment.query.get_or_404(attachment_id)

    # Only uploader or director/manager can delete
    if attachment.uploaded_by != current_user.id and current_user.role not in ['director', 'manager']:
        return jsonify({'success': False, 'error': 'Không có quyền xóa'}), 403

    try:
        # Delete physical file
        if os.path.exists(attachment.file_path):
            os.remove(attachment.file_path)

        # Delete from database
        db.session.delete(attachment)
        db.session.commit()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# TASK COMMENTS (REAL-TIME)
# ============================================

@bp.route('/<int:task_id>/comments', methods=['GET'])
@login_required
def get_comments(task_id):
    """Lấy danh sách comments (for AJAX)"""
    task = Task.query.get_or_404(task_id)

    # Check permission
    assignment = TaskAssignment.query.filter_by(
        task_id=task_id,
        user_id=current_user.id,
        accepted=True
    ).first()

    if not assignment and task.creator_id != current_user.id and current_user.role not in ['director', 'manager']:
        return jsonify({'success': False, 'error': 'Không có quyền'}), 403

    from app.models import TaskComment
    from app.utils import utc_to_vn

    comments = TaskComment.query.filter_by(task_id=task_id).order_by(TaskComment.created_at.asc()).all()

    comments_data = []
    for comment in comments:
        vn_time = utc_to_vn(comment.created_at)
        comments_data.append({
            'id': comment.id,
            'content': comment.content,
            'created_at': comment.created_at.isoformat(),
            'created_at_display': vn_time.strftime('%d/%m/%Y %H:%M'),
            'user': {
                'id': comment.user_id,
                'full_name': comment.user.full_name,
                'role': comment.user.role,
                'avatar': comment.user.avatar,
                'avatar_letter': comment.user.full_name[0].upper()
            },
            'can_delete': comment.user_id == current_user.id or current_user.role == 'director'
        })

    return jsonify({
        'success': True,
        'comments': comments_data,
        'total': len(comments_data)
    })


@bp.route('/<int:task_id>/comments', methods=['POST'])
@login_required
def add_comment(task_id):
    """Thêm comment mới"""
    task = Task.query.get_or_404(task_id)

    # Check permission
    assignment = TaskAssignment.query.filter_by(
        task_id=task_id,
        user_id=current_user.id,
        accepted=True
    ).first()

    if not assignment and task.creator_id != current_user.id and current_user.role not in ['director', 'manager']:
        return jsonify({'success': False, 'error': 'Không có quyền'}), 403

    content = request.json.get('content', '').strip()

    if not content:
        return jsonify({'success': False, 'error': 'Nội dung không được để trống'}), 400

    try:
        from app.models import TaskComment
        from app.utils import utc_to_vn

        comment = TaskComment(
            task_id=task_id,
            user_id=current_user.id,
            content=content
        )
        db.session.add(comment)
        db.session.commit()

        # Gửi thông báo cho người liên quan
        # Nếu là nhân viên comment -> gửi cho creator
        if current_user.id != task.creator_id:
            notif = Notification(
                user_id=task.creator_id,
                type='task_comment',
                title=f'💬 Bình luận mới từ {current_user.full_name}',
                body=f'Trong nhiệm vụ: {task.title}',
                link=f'/tasks/{task_id}'
            )
            db.session.add(notif)

        # Nếu là creator comment -> gửi cho assignees
        else:
            assignments = TaskAssignment.query.filter_by(task_id=task_id, accepted=True).all()
            for assignment in assignments:
                if assignment.user_id != current_user.id:
                    notif = Notification(
                        user_id=assignment.user_id,
                        type='task_comment',
                        title=f'💬 Bình luận mới từ {current_user.full_name}',
                        body=f'Trong nhiệm vụ: {task.title}',
                        link=f'/tasks/{task_id}'
                    )
                    db.session.add(notif)

        db.session.commit()

        vn_time = utc_to_vn(comment.created_at)

        return jsonify({
            'success': True,
            'comment': {
                'id': comment.id,
                'content': comment.content,
                'created_at': comment.created_at.isoformat(),
                'created_at_display': vn_time.strftime('%d/%m/%Y %H:%M'),
                'created_at_timestamp': comment.created_at.timestamp(),
                'user': {
                    'id': current_user.id,
                    'full_name': current_user.full_name,
                    'role': current_user.role,
                    'avatar': current_user.avatar,
                    'avatar_letter': current_user.full_name[0].upper()
                },
                'can_delete': True
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:task_id>/comments/<int:comment_id>', methods=['DELETE'])
@login_required
def delete_comment(task_id, comment_id):
    """Xóa comment"""
    from app.models import TaskComment
    comment = TaskComment.query.get_or_404(comment_id)

    if comment.task_id != task_id:
        return jsonify({'success': False, 'error': 'Comment không tồn tại'}), 404

    # Only owner or director can delete
    if comment.user_id != current_user.id and current_user.role != 'director':
        return jsonify({'success': False, 'error': 'Không có quyền xóa'}), 403

    try:
        db.session.delete(comment)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500