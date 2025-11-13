from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Task, TaskAssignment, User, Notification
from app.decorators import role_required
from datetime import datetime, timedelta
from sqlalchemy import or_, and_
from app.utils import vn_to_utc, vn_now

bp = Blueprint('tasks', __name__)


@bp.route('/dashboard')
@login_required
def dashboard():
    now = datetime.utcnow()

    # Lấy filter parameters
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    assigned_user = request.args.get('assigned_user', '')

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

        # ===== Tasks được gán cho Director/Manager (tasks cá nhân) =====
        my_assignments = TaskAssignment.query.filter_by(
            user_id=current_user.id,
            accepted=True
        ).all()
        my_personal_tasks = [a.task for a in my_assignments if a.task.status != 'DONE']
        # ===== END =====

        # ===== NHIỆM VỤ QUÁ HẠN (cho toàn bộ hệ thống) =====
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

        overdue_tasks = overdue_query.order_by(Task.due_date).all()
        # ===== END =====

        # ===== TẤT CẢ tasks sắp đến hạn (KHÔNG BAO GỒM quá hạn) =====
        thirty_days = now + timedelta(days=30)

        upcoming_query = Task.query.filter(
            Task.due_date <= thirty_days,
            Task.due_date >= now,
            Task.status.in_(['PENDING', 'IN_PROGRESS'])
        )

        # Apply filters
        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                date_from_utc = vn_to_utc(date_from_dt)
                upcoming_query = upcoming_query.filter(Task.due_date >= date_from_utc)
            except:
                pass

        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
                date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
                date_to_utc = vn_to_utc(date_to_dt)
                upcoming_query = upcoming_query.filter(Task.due_date <= date_to_utc)
            except:
                pass

        if assigned_user:
            task_ids = [a.task_id for a in TaskAssignment.query.filter_by(
                user_id=int(assigned_user),
                accepted=True
            ).all()]
            upcoming_query = upcoming_query.filter(Task.id.in_(task_ids))

        upcoming = upcoming_query.order_by(Task.due_date).limit(10).all()
        # ===== END =====

        # Recent activities - Tất cả tasks
        recent_query = Task.query

        # Apply filters for recent tasks
        if date_from or date_to:
            if date_from:
                try:
                    date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                    date_from_utc = vn_to_utc(date_from_dt)
                    recent_query = recent_query.filter(Task.created_at >= date_from_utc)
                except:
                    pass

            if date_to:
                try:
                    date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
                    date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
                    date_to_utc = vn_to_utc(date_to_dt)
                    recent_query = recent_query.filter(Task.created_at <= date_to_utc)
                except:
                    pass

        if assigned_user:
            task_ids = [a.task_id for a in TaskAssignment.query.filter_by(
                user_id=int(assigned_user),
                accepted=True
            ).all()]
            recent_query = recent_query.filter(Task.id.in_(task_ids))

        recent_tasks = recent_query.order_by(Task.updated_at.desc()).limit(10).all()

        # Get all users for filter dropdown
        all_users = User.query.filter_by(is_active=True).order_by(User.full_name).all()

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
                               my_personal_tasks=my_personal_tasks,
                               overdue_tasks=overdue_tasks,
                               upcoming=upcoming,
                               recent_tasks=recent_tasks,
                               all_users=all_users,
                               date_from=date_from,
                               date_to=date_to,
                               assigned_user=assigned_user)
    else:
        # ===== ACCOUNTANT/HR: Tasks của họ =====
        my_assignments = TaskAssignment.query.filter_by(
            user_id=current_user.id,
            accepted=True
        ).all()
        my_task_ids = [a.task_id for a in my_assignments]

        # THÊM MỚI: Tính toán statistics cho HR/Accountant
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

        my_tasks = [a.task for a in my_assignments if a.task.status != 'DONE']

        # Tasks created by user
        created_tasks = Task.query.filter_by(creator_id=current_user.id).all()

        # Pending group assignments
        pending_assignments = TaskAssignment.query.filter_by(
            user_id=current_user.id,
            accepted=False
        ).all()

        # ===== NHIỆM VỤ QUÁ HẠN của user này =====
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

        overdue_tasks = overdue_query.order_by(Task.due_date).all()

        # ===== Tasks sắp đến hạn của chính họ (KHÔNG BAO GỒM quá hạn) =====
        seven_days = now + timedelta(days=7)

        upcoming_query = Task.query.filter(
            Task.id.in_(my_task_ids),
            Task.due_date <= seven_days,
            Task.due_date >= now,
            Task.status.in_(['PENDING', 'IN_PROGRESS'])
        )

        # Apply date filters
        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                date_from_utc = vn_to_utc(date_from_dt)
                upcoming_query = upcoming_query.filter(Task.due_date >= date_from_utc)
            except:
                pass

        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
                date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
                date_to_utc = vn_to_utc(date_to_dt)
                upcoming_query = upcoming_query.filter(Task.due_date <= date_to_utc)
            except:
                pass

        upcoming = upcoming_query.order_by(Task.due_date).limit(10).all()

        from app.models import Note
        recent_notes = Note.query.filter_by(user_id=current_user.id).order_by(
            Note.updated_at.desc()
        ).limit(5).all()

        return render_template('dashboard.html',
                               # THÊM stats cho HR/Accountant
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
                               # Existing data
                               my_tasks=my_tasks,
                               created_tasks=created_tasks,
                               pending_assignments=pending_assignments,
                               overdue_tasks=overdue_tasks,
                               upcoming=upcoming,
                               recent_notes=recent_notes,
                               date_from=date_from,
                               date_to=date_to)


# THÊM MỚI: Route để xem chi tiết tasks theo status
@bp.route('/by-status/<status>')
@login_required
def tasks_by_status(status):
    """Hiển thị danh sách tasks theo status với filter"""
    # Validate status
    valid_statuses = ['ALL', 'PENDING', 'IN_PROGRESS', 'DONE']
    if status not in valid_statuses:
        flash('Trạng thái không hợp lệ.', 'danger')
        return redirect(url_for('tasks.dashboard'))

    # Get filters from query params
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    assigned_user = request.args.get('assigned_user', '')
    tag_filter = request.args.get('tag', '')  # urgent, important, recurring
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # Base query
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

    # Apply status filter
    if status != 'ALL':
        query = query.filter_by(status=status)

    # Apply date filters
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

    # Apply assigned user filter
    if assigned_user:
        task_ids = [a.task_id for a in TaskAssignment.query.filter_by(
            user_id=int(assigned_user),
            accepted=True
        ).all()]
        query = query.filter(Task.id.in_(task_ids))

    # Apply tag filters
    if tag_filter == 'urgent':
        query = query.filter_by(is_urgent=True)
    elif tag_filter == 'important':
        query = query.filter_by(is_important=True)
    elif tag_filter == 'recurring':
        query = query.filter_by(is_recurring=True)

    # Pagination
    pagination = query.order_by(Task.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    tasks = pagination.items

    # Get all users for filter dropdown
    all_users = None
    if current_user.role in ['director', 'manager']:
        all_users = User.query.filter_by(is_active=True).order_by(User.full_name).all()

    # Status name for display
    status_names = {
        'ALL': 'Tất cả nhiệm vụ',
        'PENDING': 'Chờ xử lý',
        'IN_PROGRESS': 'Đang thực hiện',
        'DONE': 'Hoàn thành'
    }

    return render_template('tasks_by_status.html',
                           tasks=tasks,
                           pagination=pagination,
                           status=status,
                           status_name=status_names[status],
                           date_from=date_from,
                           date_to=date_to,
                           assigned_user=assigned_user,
                           tag_filter=tag_filter,
                           all_users=all_users)


@bp.route('/')
@login_required
def list_tasks():
    status_filter = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    assigned_user = request.args.get('assigned_user', '')
    tag_filter = request.args.get('tag', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20

    if current_user.role in ['director', 'manager']:
        query = Task.query

        if status_filter:
            query = query.filter_by(status=status_filter)

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

        if status_filter:
            query = query.filter_by(status=status_filter)

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

    return render_template('tasks.html',
                           tasks=tasks,
                           pagination=pagination,
                           status_filter=status_filter,
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

    # Get all assignments
    assignments = TaskAssignment.query.filter_by(task_id=task_id).all()

    return render_template('task_detail.html',
                           task=task,
                           user_assignment=user_assignment,
                           assignments=assignments)


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

        # THÊM MỚI: Lấy giá trị của 3 thẻ tags
        is_urgent = request.form.get('is_urgent') == 'on'
        is_important = request.form.get('is_important') == 'on'
        is_recurring = request.form.get('is_recurring') == 'on'

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
            is_urgent=is_urgent,  # THÊM MỚI
            is_important=is_important,  # THÊM MỚI
            is_recurring=is_recurring  # THÊM MỚI
        )
        db.session.add(task)
        db.session.flush()

        # Handle assignments (giữ nguyên code cũ)
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
                        accepted=False,
                        seen=False
                    )
                    db.session.add(assignment)

                    notif = Notification(
                        user_id=user.id,
                        type='task_assigned',
                        title='Nhiệm vụ mới cho nhóm',
                        body=f'{current_user.full_name} đã giao nhiệm vụ {title} cho nhóm. Vui lòng chấp nhận.',
                        link=f'/tasks/{task.id}'
                    )
                    db.session.add(notif)
            else:
                flash('Bạn không có quyền giao nhiệm vụ cho nhóm.', 'danger')
                db.session.rollback()
                return redirect(url_for('tasks.list_tasks'))

        db.session.commit()
        flash('Tạo nhiệm vụ thành công.', 'success')
        return redirect(url_for('tasks.task_detail', task_id=task.id))

    # GET request
    users = []
    if current_user.can_assign_tasks():
        users = User.query.filter(User.is_active == True).all()

    return render_template('create_task.html', users=users)


# THÊM MỚI: Route để cập nhật tags
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

    flash('Giỡn mặt à ?', 'success')
    return redirect(url_for('tasks.list_tasks'))


@bp.route('/<int:task_id>/update-status', methods=['POST'])
@login_required
def update_status(task_id):
    task = Task.query.get_or_404(task_id)
    new_status = request.form.get('status')
    old_status = task.status

    if new_status not in ['PENDING', 'IN_PROGRESS', 'DONE', 'CANCELLED']:
        flash('Trạng thái không hợp lệ.', 'danger')
        return redirect(url_for('tasks.task_detail', task_id=task_id))

    # Check if task is overdue
    now = datetime.utcnow()
    is_overdue = task.due_date and task.due_date < now and task.status in ['PENDING', 'IN_PROGRESS']

    # Check permission
    if current_user.role in ['director', 'manager']:
        # Director/Manager có thể cập nhật mọi task
        pass
    else:
        # HR/Accountant
        assignment = TaskAssignment.query.filter_by(
            task_id=task_id,
            user_id=current_user.id,
            accepted=True
        ).first()

        if not assignment and task.creator_id != current_user.id:
            flash('Bạn không có quyền cập nhật nhiệm vụ này.', 'danger')
            return redirect(url_for('tasks.task_detail', task_id=task_id))

        # KIỂM TRA: Nếu task đã DONE, HR/Accountant không thể thay đổi
        if old_status == 'DONE':
            flash('Nhiệm vụ đã hoàn thành và bị khóa. Chỉ Giám đốc hoặc Trưởng phòng mới có thể cập nhật trạng thái.',
                  'danger')
            return redirect(url_for('tasks.task_detail', task_id=task_id))

    # LOGIC MỚI: Kiểm tra nếu chuyển sang DONE khi đang quá hạn
    if new_status == 'DONE' and is_overdue:
        task.completed_overdue = True
        flash('⚠️ Nhiệm vụ đã hoàn thành nhưng QUÁ HẠN!', 'warning')
    elif new_status == 'DONE':
        task.completed_overdue = False

    # Nếu chuyển từ DONE sang trạng thái khác, reset flag
    if old_status == 'DONE' and new_status != 'DONE':
        task.completed_overdue = False

    # Update status
    task.status = new_status
    task.updated_at = datetime.utcnow()
    db.session.commit()

    # Gửi thông báo khi hoàn thành
    if current_user.role in ['hr', 'accountant'] and new_status == 'DONE' and old_status != 'DONE':
        directors_and_managers = User.query.filter(
            User.role.in_(['director', 'manager']),
            User.is_active == True
        ).all()

        # Thông báo có thêm thông tin quá hạn
        completion_msg = f'{current_user.full_name} ({current_user.role.upper()}) đã hoàn thành nhiệm vụ: {task.title}'
        if task.completed_overdue:
            completion_msg += ' (⚠️ HOÀN THÀNH QUÁ HẠN)'

        for recipient in directors_and_managers:
            notif = Notification(
                user_id=recipient.id,
                type='task_completed',
                title='Nhiệm vụ đã hoàn thành' + (' - QUÁ HẠN' if task.completed_overdue else ''),
                body=completion_msg,
                link=f'/tasks/{task.id}'
            )
            db.session.add(notif)

        db.session.commit()

    if not task.completed_overdue:
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

        # Xóa tất cả task assignments liên quan trước
        TaskAssignment.query.filter(TaskAssignment.task_id.in_(task_ids)).delete(synchronize_session=False)

        # Xóa tất cả notifications liên quan (nếu có link đến tasks)
        # Lưu ý: Chỉ xóa notifications có link đến tasks đang xóa
        for task_id in task_ids:
            Notification.query.filter(Notification.link == f'/tasks/{task_id}').delete(synchronize_session=False)

        # Sau đó xóa tasks
        deleted_count = Task.query.filter(Task.id.in_(task_ids)).delete(synchronize_session=False)
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
            title=f'Đánh giá nhiệm vụ: {rating_text}',
            body=f'{current_user.full_name} đã đánh giá nhiệm vụ "{task.title}" là {rating_text}',
            link=f'/tasks/{task.id}'
        )
        db.session.add(notif)

    db.session.commit()

    flash(f'Đã đánh giá nhiệm vụ: {rating_text}', 'success')
    return redirect(url_for('tasks.task_detail', task_id=task_id))