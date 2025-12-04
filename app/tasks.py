from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app, send_from_directory, abort
from flask_login import login_required, current_user
from app import db
from app.models import Task, TaskAssignment, User, Notification, TaskComment
from app.decorators import role_required
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, case, func
from app.utils import vn_to_utc, utc_to_vn, vn_now
from werkzeug.exceptions import abort
from app.ai_service import summarize_description

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

    # Statistics for director and manager
    if current_user.role in ['director', 'manager']:
        # ===== ✅ TỐI ƯU: SỬ DỤNG 1 QUERY DUY NHẤT CHO TẤT CẢ STATS =====
        from sqlalchemy import func, case

        # Base query with filters
        base_conditions = []

        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                date_from_utc = vn_to_utc(date_from_dt)
                base_conditions.append(Task.created_at >= date_from_utc)
            except:
                pass

        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
                date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
                date_to_utc = vn_to_utc(date_to_dt)
                base_conditions.append(Task.created_at <= date_to_utc)
            except:
                pass

        # Apply assigned user filter
        if assigned_user:
            task_ids = [a.task_id for a in TaskAssignment.query.filter_by(
                user_id=int(assigned_user),
                accepted=True
            ).all()]
            base_conditions.append(Task.id.in_(task_ids))

        # ✅ 1 QUERY DUY NHẤT để lấy tất cả statistics
        stats = db.session.query(
            func.count(Task.id).label('total_tasks'),
            func.sum(case((Task.status == 'PENDING', 1), else_=0)).label('pending'),
            func.sum(case((Task.status == 'IN_PROGRESS', 1), else_=0)).label('in_progress'),
            func.sum(case((Task.status == 'DONE', 1), else_=0)).label('done'),
            # Badge counts - PENDING (✅ SỬA CÚ PHÁP: dùng AND)
            func.sum(case(((Task.status == 'PENDING') & (Task.is_urgent == True), 1), else_=0)).label('pending_urgent'),
            func.sum(case(((Task.status == 'PENDING') & (Task.is_important == True), 1), else_=0)).label(
                'pending_important'),
            func.sum(case(((Task.status == 'PENDING') & (Task.is_recurring == True), 1), else_=0)).label(
                'pending_recurring'),
            # Badge counts - IN_PROGRESS
            func.sum(case(((Task.status == 'IN_PROGRESS') & (Task.is_urgent == True), 1), else_=0)).label(
                'in_progress_urgent'),
            func.sum(case(((Task.status == 'IN_PROGRESS') & (Task.is_important == True), 1), else_=0)).label(
                'in_progress_important'),
            func.sum(case(((Task.status == 'IN_PROGRESS') & (Task.is_recurring == True), 1), else_=0)).label(
                'in_progress_recurring'),
            # Badge counts - DONE
            func.sum(case(((Task.status == 'DONE') & (Task.is_urgent == True), 1), else_=0)).label('done_urgent'),
            func.sum(case(((Task.status == 'DONE') & (Task.is_important == True), 1), else_=0)).label('done_important'),
            func.sum(case(((Task.status == 'DONE') & (Task.is_recurring == True), 1), else_=0)).label('done_recurring'),
            # Badge counts - TOTAL
            func.sum(case((Task.is_urgent == True, 1), else_=0)).label('total_urgent'),
            func.sum(case((Task.is_important == True, 1), else_=0)).label('total_important'),
            func.sum(case((Task.is_recurring == True, 1), else_=0)).label('total_recurring'),
        )

        # Apply filters
        if base_conditions:
            stats = stats.filter(*base_conditions)

        stats = stats.first()

        # Extract values
        total_tasks = stats.total_tasks or 0
        pending = stats.pending or 0
        in_progress = stats.in_progress or 0
        done = stats.done or 0
        pending_urgent = stats.pending_urgent or 0
        pending_important = stats.pending_important or 0
        pending_recurring = stats.pending_recurring or 0
        in_progress_urgent = stats.in_progress_urgent or 0
        in_progress_important = stats.in_progress_important or 0
        in_progress_recurring = stats.in_progress_recurring or 0
        done_urgent = stats.done_urgent or 0
        done_important = stats.done_important or 0
        done_recurring = stats.done_recurring or 0
        total_urgent = stats.total_urgent or 0
        total_important = stats.total_important or 0
        total_recurring = stats.total_recurring or 0

        # Get all users for filter dropdown
        all_users = User.query.filter_by(is_active=True).order_by(User.full_name).all()

        return render_template('dashboard.html',
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

        # ✅ TỐI ƯU: 1 QUERY cho tất cả stats
        from sqlalchemy import func, case

        base_conditions = [Task.id.in_(my_task_ids)]

        # Apply date filters
        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                date_from_utc = vn_to_utc(date_from_dt)
                base_conditions.append(Task.created_at >= date_from_utc)
            except:
                pass

        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
                date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
                date_to_utc = vn_to_utc(date_to_dt)
                base_conditions.append(Task.created_at <= date_to_utc)
            except:
                pass

        # ✅ 1 QUERY DUY NHẤT (✅ SỬA CÚ PHÁP: dùng &)
        stats = db.session.query(
            func.count(Task.id).label('total_tasks'),
            func.sum(case((Task.status == 'PENDING', 1), else_=0)).label('pending'),
            func.sum(case((Task.status == 'IN_PROGRESS', 1), else_=0)).label('in_progress'),
            func.sum(case((Task.status == 'DONE', 1), else_=0)).label('done'),
            func.sum(case(((Task.status == 'PENDING') & (Task.is_urgent == True), 1), else_=0)).label('pending_urgent'),
            func.sum(case(((Task.status == 'PENDING') & (Task.is_important == True), 1), else_=0)).label(
                'pending_important'),
            func.sum(case(((Task.status == 'PENDING') & (Task.is_recurring == True), 1), else_=0)).label(
                'pending_recurring'),
            func.sum(case(((Task.status == 'IN_PROGRESS') & (Task.is_urgent == True), 1), else_=0)).label(
                'in_progress_urgent'),
            func.sum(case(((Task.status == 'IN_PROGRESS') & (Task.is_important == True), 1), else_=0)).label(
                'in_progress_important'),
            func.sum(case(((Task.status == 'IN_PROGRESS') & (Task.is_recurring == True), 1), else_=0)).label(
                'in_progress_recurring'),
            func.sum(case(((Task.status == 'DONE') & (Task.is_urgent == True), 1), else_=0)).label('done_urgent'),
            func.sum(case(((Task.status == 'DONE') & (Task.is_important == True), 1), else_=0)).label('done_important'),
            func.sum(case(((Task.status == 'DONE') & (Task.is_recurring == True), 1), else_=0)).label('done_recurring'),
            func.sum(case((Task.is_urgent == True, 1), else_=0)).label('total_urgent'),
            func.sum(case((Task.is_important == True, 1), else_=0)).label('total_important'),
            func.sum(case((Task.is_recurring == True, 1), else_=0)).label('total_recurring'),
        ).filter(*base_conditions).first()

        total_tasks = stats.total_tasks or 0
        pending = stats.pending or 0
        in_progress = stats.in_progress or 0
        done = stats.done or 0
        pending_urgent = stats.pending_urgent or 0
        pending_important = stats.pending_important or 0
        pending_recurring = stats.pending_recurring or 0
        in_progress_urgent = stats.in_progress_urgent or 0
        in_progress_important = stats.in_progress_important or 0
        in_progress_recurring = stats.in_progress_recurring or 0
        done_urgent = stats.done_urgent or 0
        done_important = stats.done_important or 0
        done_recurring = stats.done_recurring or 0
        total_urgent = stats.total_urgent or 0
        total_important = stats.total_important or 0
        total_recurring = stats.total_recurring or 0

        return render_template('dashboard.html',
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
    per_page = 10

    # ===== ✅ IMPORT EAGER LOADING =====
    from sqlalchemy.orm import joinedload

    if current_user.role in ['director', 'manager']:
        # ===== ✅ EAGER LOAD CHỈ CREATOR =====
        query = Task.query.options(
            joinedload(Task.creator)  # Chỉ load creator
        )

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

        # ===== ✅ BATCH LOAD ASSIGNMENTS CHO TẤT CẢ TASKS =====
        if tasks:
            task_ids = [task.id for task in tasks]

            # Load tất cả assignments + users trong 1 query
            from sqlalchemy.orm import joinedload
            all_assignments = db.session.query(TaskAssignment).options(
                joinedload(TaskAssignment.user)
            ).filter(
                TaskAssignment.task_id.in_(task_ids)
            ).all()

            # Tạo dictionary: task_id -> list of assignments
            assignments_by_task = {}
            for assignment in all_assignments:
                if assignment.task_id not in assignments_by_task:
                    assignments_by_task[assignment.task_id] = []
                assignments_by_task[assignment.task_id].append(assignment)

            # Gán vào tasks
            for task in tasks:
                task._cached_assignments = assignments_by_task.get(task.id, [])

        all_users = User.query.filter_by(is_active=True).order_by(User.full_name).all()
    else:
        # Only see assigned tasks
        accepted_assignments = TaskAssignment.query.filter_by(
            user_id=current_user.id,
            accepted=True
        ).all()
        assigned_task_ids = [a.task_id for a in accepted_assignments]

        # ===== ✅ EAGER LOAD CHỈ CREATOR =====
        query = Task.query.options(
            joinedload(Task.creator)
        ).filter(
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

        # ===== ✅ BATCH LOAD ASSIGNMENTS =====
        if tasks:
            task_ids = [task.id for task in tasks]

            all_assignments = db.session.query(TaskAssignment).options(
                joinedload(TaskAssignment.user)
            ).filter(
                TaskAssignment.task_id.in_(task_ids)
            ).all()

            assignments_by_task = {}
            for assignment in all_assignments:
                if assignment.task_id not in assignments_by_task:
                    assignments_by_task[assignment.task_id] = []
                assignments_by_task[assignment.task_id].append(assignment)

            for task in tasks:
                task._cached_assignments = assignments_by_task.get(task.id, [])

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

    task.unread_comment_count = get_task_unread_comment_count(task_id, current_user.id)

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
        assign_to_multiple = request.form.getlist('assign_to_multiple[]')

        # ===== TAGS: Cho phép TẤT CẢ user gắn tags =====
        is_urgent = request.form.get('is_urgent') == 'on'
        is_important = request.form.get('is_important') == 'on'
        is_recurring = request.form.get('is_recurring') == 'on'

        # Recurrence: CHỈ Director/Manager
        recurrence_enabled = False
        recurrence_interval_days = 7
        if current_user.can_assign_tasks():
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

        # =====  KIỂM TRA CẦN PHÊ DUYỆT =====
        # Chỉ task tự giao cho mình MỚI cần phê duyệt
        requires_approval = False

        if assign_type == 'self':  # Nếu user tự giao cho mình
            # HR, Accountant, Manager tự tạo task => cần duyệt
            if current_user.role in ['hr', 'accountant', 'manager']:
                requires_approval = True
        # Director tự tạo task => KHÔNG cần duyệt
        # Task được cấp trên giao => KHÔNG cần duyệt
        # ===== KẾT THÚC KIỂM TRA =====

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
            requires_approval=requires_approval,  # Đánh dấu cần duyệt
            approved=None if requires_approval else True,  # None = chờ duyệt, True = không cần duyệt
            recurrence_enabled=recurrence_enabled if current_user.can_assign_tasks() else False,
            recurrence_interval_days=recurrence_interval_days if recurrence_enabled else None,
            last_recurrence_date=datetime.utcnow() if recurrence_enabled else None
        )
        db.session.add(task)
        db.session.flush()

        # =====  BIẾN ĐỂ KIỂM TRA ĐÃ FLASH MESSAGE CHƯA =====
        has_flashed = False

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

            # =====  GỬI THÔNG BÁO CHO NGƯỜI PHÊ DUYỆT =====
            if requires_approval:  # Nếu task cần phê duyệt
                approvers = []  # Danh sách người được quyền duyệt

                # ===== XÁC ĐỊNH AI ĐƯỢC QUYỀN DUYỆT =====
                if current_user.role == 'hr':
                    # HR tự tạo => Manager HOẶC Director duyệt
                    approvers = User.query.filter(
                        User.role.in_(['manager', 'director']),
                        User.is_active == True
                    ).all()

                elif current_user.role == 'accountant':
                    # Accountant tự tạo => CHỈ Director duyệt
                    approvers = User.query.filter(
                        User.role == 'director',
                        User.is_active == True
                    ).all()

                elif current_user.role == 'manager':
                    # Manager tự tạo => CHỈ Director duyệt
                    approvers = User.query.filter(
                        User.role == 'director',
                        User.is_active == True
                    ).all()

                # ===== GỬI THÔNG BÁO CHO TẤT CẢ NGƯỜI DUYỆT =====
                for approver in approvers:
                    notif = Notification(
                        user_id=approver.id,
                        type='task_approval_request',
                        title='🔔 Yêu cầu phê duyệt công việc',
                        body=f'{current_user.full_name} đã tạo công việc "{title}" và cần phê duyệt.',
                        link=f'/tasks/{task.id}'
                    )
                    db.session.add(notif)

                # Flash message cho user biết đang chờ duyệt
                flash('Công việc đã được tạo và đang chờ phê duyệt.', 'info')
                has_flashed = True

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

        elif assign_type == 'multiple' and assign_to_multiple:
            if current_user.can_assign_tasks():
                if len(assign_to_multiple) == 0:
                    flash('Vui lòng chọn ít nhất 1 người.', 'warning')
                    db.session.rollback()
                    return redirect(url_for('tasks.create_task'))

                # ===== KIỂM TRA CÓ TẠO TASK RIÊNG HAY KHÔNG =====
                create_separate = request.form.get('create_separate_tasks') == 'on'

                if create_separate:
                    # ===== TẠO TASK RIÊNG CHO TỪNG NGƯỜI =====
                    created_tasks = []

                    for user_id_str in assign_to_multiple:
                        user_id = int(user_id_str)
                        assigned_user = User.query.get(user_id)

                        if not assigned_user:
                            continue

                        # Tạo tiêu đề mới: "Tiêu đề gốc - Tên người"
                        new_title = f"{title} - {assigned_user.full_name}"

                        # Tạo task riêng
                        separate_task = Task(
                            title=new_title,
                            description=description,
                            creator_id=current_user.id,
                            due_date=due_date,
                            status='PENDING',
                            is_urgent=is_urgent,
                            is_important=is_important,
                            is_recurring=is_recurring,
                            requires_approval=False,  # Task giao từ trên xuống không cần duyệt
                            approved=True,
                            recurrence_enabled=recurrence_enabled if current_user.can_assign_tasks() else False,
                            recurrence_interval_days=recurrence_interval_days if recurrence_enabled else None,
                            last_recurrence_date=datetime.utcnow() if recurrence_enabled else None
                        )
                        db.session.add(separate_task)
                        db.session.flush()

                        # Tạo assignment
                        assignment = TaskAssignment(
                            task_id=separate_task.id,
                            user_id=user_id,
                            assigned_by=current_user.id,
                            accepted=True,
                            accepted_at=datetime.utcnow(),
                            seen=False
                        )
                        db.session.add(assignment)

                        # Gửi notification
                        notif = Notification(
                            user_id=user_id,
                            type='task_assigned',
                            title='Nhiệm vụ mới được giao',
                            body=f'{current_user.full_name} đã giao nhiệm vụ "{new_title}" cho bạn.',
                            link=f'/tasks/{separate_task.id}'
                        )
                        db.session.add(notif)

                        created_tasks.append(separate_task)

                    db.session.commit()

                    flash(f'✅ Đã tạo {len(created_tasks)} nhiệm vụ riêng cho từng người.', 'success')
                    has_flashed = True

                    # Redirect về danh sách tasks thay vì 1 task cụ thể
                    return redirect(url_for('tasks.list_tasks'))

                else:
                    # ===== TẠO 1 TASK CHUNG (LOGIC CŨ) =====
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
                    has_flashed = True

            else:
                flash('Bạn không có quyền giao nhiệm vụ cho nhiều người.', 'danger')
                db.session.rollback()
                return redirect(url_for('tasks.list_tasks'))

        # =====  COMMIT DATABASE =====
        db.session.commit()

        # =====  FLASH MESSAGE NẾU CHƯA FLASH =====
        if not has_flashed:
            flash('Tạo nhiệm vụ thành công.', 'success')

        return redirect(url_for('tasks.task_detail', task_id=task.id))

    # GET request
    users = []
    if current_user.can_assign_tasks():
        users = User.query.filter(User.is_active == True).order_by(User.full_name).all()

    return render_template('create_task.html', users=users)


@bp.route('/api/summarize-description', methods=['POST'])
@login_required
def api_summarize_description():
    """
    API để tóm tắt mô tả công việc bằng AI

    Request JSON:
        {
            "description": "Văn bản dài cần tóm tắt..."
        }

    Response JSON:
        {
            "success": true,
            "summary": "Bản tóm tắt ngắn gọn",
            "original_word_count": 120,
            "summary_word_count": 45,
            "elapsed": 2.3
        }
    """
    try:
        data = request.get_json()
        description = data.get('description', '').strip()

        if not description:
            return jsonify({
                'success': False,
                'error': 'Không có nội dung để tóm tắt'
            }), 400

        # Kiểm tra độ dài tối thiểu
        word_count = len(description.split())

        if word_count < 30:
            return jsonify({
                'success': False,
                'error': 'Mô tả quá ngắn (dưới 30 từ), không cần tóm tắt'
            }), 400

        # ✅ GỌI AI SERVICE
        result = summarize_description(description, max_words=50)

        if result['success']:
            summary_word_count = len(result['summary'].split())

            return jsonify({
                'success': True,
                'summary': result['summary'],
                'original_word_count': word_count,
                'summary_word_count': summary_word_count,
                'elapsed': result.get('elapsed', 0)
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500

    except Exception as e:
        print(f"[ERROR] AI Summary API: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Lỗi server. Vui lòng thử lại.'
        }), 500

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

    # =====  CHECK PHÊ DUYỆT =====
    # Nếu task cần phê duyệt và chưa được duyệt => KHÔNG cho phép thay đổi status
    if task.requires_approval and task.approved is None:
        # ===== CHỈ DIRECTOR mới được bypass =====
        # Manager tự giao việc cho mình VẪN PHẢI chờ Director duyệt
        # HR/Accountant phải chờ Manager/Director duyệt
        if current_user.role != 'director':
            flash('❌ Công việc chưa được phê duyệt. Vui lòng chờ phê duyệt trước khi bắt đầu.', 'warning')
            return redirect(url_for('tasks.task_detail', task_id=task_id))

    # Nếu task bị TỪ CHỐI => KHÔNG cho phép thay đổi (đã bị cancel rồi)
    if task.requires_approval and task.approved is False:
        flash('❌ Công việc đã bị từ chối. Không thể thay đổi trạng thái.', 'danger')
        return redirect(url_for('tasks.task_detail', task_id=task_id))

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

        #  XÓA FILE ĐÍNH KÈM COMMENT TRƯỚC
        from app.models import TaskComment
        comments_with_files = TaskComment.query.filter(
            TaskComment.task_id.in_(task_ids),
            TaskComment.has_attachment == True
        ).all()

        for comment in comments_with_files:
            if comment.attachment_file_path and os.path.exists(comment.attachment_file_path):
                try:
                    os.remove(comment.attachment_file_path)
                    print(f" Deleted file: {comment.attachment_file_path}")
                except Exception as e:
                    print(f" Could not delete file: {e}")

        # QUAN TRỌNG: Thứ tự xóa phải đúng!
        # 1. Xóa TaskCompletionReport trước (vì có FK đến tasks)
        from app.models import TaskCompletionReport
        TaskCompletionReport.query.filter(
            TaskCompletionReport.task_id.in_(task_ids)
        ).delete(synchronize_session=False)

        # 2. Xóa TaskComment
        TaskComment.query.filter(
            TaskComment.task_id.in_(task_ids)
        ).delete(synchronize_session=False)

        # 3. Xóa TaskAssignment
        TaskAssignment.query.filter(
            TaskAssignment.task_id.in_(task_ids)
        ).delete(synchronize_session=False)

        # 4. Xóa Notifications liên quan
        for task_id in task_ids:
            Notification.query.filter(
                Notification.link == f'/tasks/{task_id}'
            ).delete(synchronize_session=False)

        # 5. Cuối cùng xóa Tasks
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
#  TASK APPROVAL
# ============================================

@bp.route('/<int:task_id>/approve-self-task', methods=['POST'])
@login_required
@role_required(['director', 'manager'])
def approve_self_task(task_id):
    """
    Phê duyệt công việc tự tạo

    Logic:
    - Director: Duyệt được TẤT CẢ
    - Manager: CHỈ duyệt được task của HR
    """
    task = Task.query.get_or_404(task_id)

    # ===== KIỂM TRA CƠ BẢN =====
    if not task.requires_approval:
        return jsonify({'success': False, 'error': 'Công việc này không cần phê duyệt'}), 400

    if task.approved is not None:
        return jsonify({'success': False, 'error': 'Công việc đã được xử lý rồi'}), 400

    # ===== KIỂM TRA QUYỀN PHÊ DUYỆT =====
    can_approve = False

    if current_user.role == 'director':
        # Director duyệt được tất cả
        can_approve = True
    elif current_user.role == 'manager':
        # Manager CHỈ duyệt được task của HR
        if task.creator.role == 'hr':
            can_approve = True

    if not can_approve:
        return jsonify({'success': False, 'error': 'Bạn không có quyền phê duyệt công việc này'}), 403


    # ===== CẬP NHẬT TRẠNG THÁI PHÊ DUYỆT =====
    task.approved = True
    task.approved_by = current_user.id
    task.approved_at = datetime.utcnow()


    # ===== GỬI THÔNG BÁO CHO NGƯỜI TẠO TASK =====
    notif = Notification(
        user_id=task.creator_id,
        type='task_approved',
        title='✅ Công việc đã được phê duyệt',
        body=f'{current_user.full_name} đã phê duyệt công việc "{task.title}"',
        link=f'/tasks/{task.id}'
    )
    db.session.add(notif)

    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Đã phê duyệt công việc'
    })


@bp.route('/<int:task_id>/reject-self-task', methods=['POST'])
@login_required
@role_required(['director', 'manager'])
def reject_self_task(task_id):
    """
    Từ chối công việc tự tạo

    Logic tương tự approve_self_task
    """
    task = Task.query.get_or_404(task_id)

    # ===== KIỂM TRA CƠ BẢN =====
    if not task.requires_approval:
        return jsonify({'success': False, 'error': 'Công việc này không cần phê duyệt'}), 400

    if task.approved is not None:
        return jsonify({'success': False, 'error': 'Công việc đã được xử lý rồi'}), 400

    # ===== KIỂM TRA QUYỀN TỪ CHỐI =====
    can_reject = False

    if current_user.role == 'director':
        can_reject = True
    elif current_user.role == 'manager':
        if task.creator.role == 'hr':
            can_reject = True

    if not can_reject:
        return jsonify({'success': False, 'error': 'Bạn không có quyền từ chối công việc này'}), 403

    # ===== CẬP NHẬT TRẠNG THÁI TỪ CHỐI =====
    task.approved = False
    task.approved_by = current_user.id
    task.approved_at = datetime.utcnow()
    task.status = 'CANCELLED'  # Đổi status thành CANCELLED

    # ===== GỬI THÔNG BÁO CHO NGƯỜI TẠO TASK =====
    notif = Notification(
        user_id=task.creator_id,
        type='task_rejected',
        title='❌ Công việc không được phê duyệt',
        body=f'{current_user.full_name} đã từ chối công việc "{task.title}".',
        link=f'/tasks/{task.id}'
    )
    db.session.add(notif)

    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Đã từ chối công việc'
    })


@bp.route('/pending-approvals')
@login_required
@role_required(['director', 'manager'])
def pending_approvals():
    """
    Trang danh sách công việc chờ phê duyệt

    Logic:
    - Director: Thấy TẤT CẢ tasks chờ duyệt
    - Manager: CHỈ thấy tasks của HR chờ duyệt
    """
    # Base query: Lấy tasks cần phê duyệt và đang chờ
    query = Task.query.filter(
        Task.requires_approval == True,
        Task.approved == None  # None = chờ duyệt
    ).join(
        User, Task.creator_id == User.id  # Join để lấy thông tin người tạo
    )

    # Manager chỉ thấy tasks của HR
    if current_user.role == 'manager':
        query = query.filter(User.role == 'hr')

    # Sắp xếp: Task cũ nhất lên đầu (chờ lâu nhất)
    tasks = query.order_by(Task.created_at.asc()).all()

    return render_template('pending_approvals.html',
                           tasks=tasks,
                           total_count=len(tasks))

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

    # ===== ✅ IMPORT EAGER LOADING =====
    from sqlalchemy.orm import joinedload
    from sqlalchemy import case, func

    # Base query theo role
    if current_user.role in ['director', 'manager']:
        # ===== ✅ EAGER LOAD CREATOR =====
        query = Task.query.options(
            joinedload(Task.creator)
        )
    else:
        # HR/Accountant: only their tasks
        accepted_assignments = TaskAssignment.query.filter_by(
            user_id=current_user.id,
            accepted=True
        ).all()
        assigned_task_ids = [a.task_id for a in accepted_assignments]
        query = Task.query.options(
            joinedload(Task.creator)
        ).filter(
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

    # ===== ✅ TỐI ƯU: SORT BẰNG SQL THAY VÌ PYTHON =====
    # Sort priority cho PENDING và IN_PROGRESS
    priority_order = case(
        (Task.due_date < func.now(), 1),  # Overdue first
        (Task.is_urgent == True, 2),
        (Task.is_important == True, 3),
        (Task.is_recurring == True, 4),
        else_=5
    )

    # Query cho từng status với sorting SQL
    pending_tasks = query.filter(Task.status == 'PENDING').order_by(
        priority_order.asc(),
        Task.created_at.desc()
    ).all()

    in_progress_tasks = query.filter(Task.status == 'IN_PROGRESS').order_by(
        priority_order.asc(),
        Task.created_at.desc()
    ).all()

    done_tasks = query.filter(Task.status == 'DONE').order_by(
        Task.updated_at.desc()
    ).all()

    # ===== ✅ BATCH LOAD ASSIGNMENTS CHO TẤT CẢ TASKS =====
    all_tasks = pending_tasks + in_progress_tasks + done_tasks

    if all_tasks:
        task_ids = [task.id for task in all_tasks]

        # Load tất cả assignments + users trong 1 query
        all_assignments = db.session.query(TaskAssignment).options(
            joinedload(TaskAssignment.user)
        ).filter(
            TaskAssignment.task_id.in_(task_ids)
        ).all()

        # Tạo dictionary: task_id -> list of assignments
        assignments_by_task = {}
        for assignment in all_assignments:
            if assignment.task_id not in assignments_by_task:
                assignments_by_task[assignment.task_id] = []
            assignments_by_task[assignment.task_id].append(assignment)

        # Gán vào tasks
        for task in all_tasks:
            task._cached_assignments = assignments_by_task.get(task.id, [])

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

# ============================================
#  Priority ROUTES
# ============================================
@bp.route('/priority-detail')
@login_required
def priority_detail():
    """
    Trang chi tiết công việc theo loại ưu tiên - OPTIMIZED
    """
    assigned_user_id = request.args.get('assigned_user', type=int)
    tag = request.args.get('tag', '')
    status = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    page = request.args.get('page', 1, type=int)
    per_page = 6

    if not assigned_user_id:
        flash('Thiếu thông tin người dùng.', 'danger')
        return redirect(url_for('hub.workflow_hub'))

    user = User.query.get_or_404(assigned_user_id)

    from sqlalchemy.orm import joinedload
    from sqlalchemy import case, func
    from app.models import TaskComment, TaskCommentRead

    # ===== BASE QUERY =====
    base_query = db.session.query(Task).options(
        joinedload(Task.creator)
    ).join(
        TaskAssignment, Task.id == TaskAssignment.task_id
    ).filter(
        TaskAssignment.user_id == assigned_user_id,
        TaskAssignment.accepted == True
    )

    # Apply date filters
    if date_from:
        try:
            date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
            date_from_utc = vn_to_utc(date_from_dt)
            base_query = base_query.filter(Task.created_at >= date_from_utc)
        except:
            pass

    if date_to:
        try:
            date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
            date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
            date_to_utc = vn_to_utc(date_to_dt)
            base_query = base_query.filter(Task.created_at <= date_to_utc)
        except:
            pass

    # Xác định loại và filter
    priority_type = ''
    priority_icon = ''

    if tag == 'urgent':
        base_query = base_query.filter(Task.is_urgent == True, Task.status != 'DONE')
        priority_type = 'KHẨN CẤP'
        priority_icon = '🔥'
    elif tag == 'important':
        base_query = base_query.filter(Task.is_important == True, Task.status != 'DONE')
        priority_type = 'QUAN TRỌNG'
        priority_icon = '⭐'
    elif tag == 'recurring':
        base_query = base_query.filter(Task.is_recurring == True, Task.status != 'DONE')
        priority_type = 'LẶP LẠI'
        priority_icon = '🔁'
    elif status == 'DONE':
        base_query = base_query.filter(Task.status == 'DONE')
        priority_type = 'HOÀN THÀNH'
        priority_icon = '✅'
    else:
        flash('Loại công việc không hợp lệ.', 'danger')
        return redirect(url_for('hub.workflow_hub'))

    # ===== ✅ ĐẾM TỔNG TIN NHẮN CHƯA ĐỌC TRƯỚC KHI PHÂN TRANG =====
    all_task_ids = [t.id for t in base_query.all()]

    total_unread_messages = 0
    tasks_with_unread = 0

    if all_task_ids:
        # Tổng comment (trừ comment của chính user)
        total_comments_subq = db.session.query(
            TaskComment.task_id,
            func.count(TaskComment.id).label('total')
        ).filter(
            TaskComment.task_id.in_(all_task_ids),
            TaskComment.user_id != current_user.id
        ).group_by(TaskComment.task_id).subquery()

        # Comment đã đọc
        read_comments_subq = db.session.query(
            TaskCommentRead.task_id,
            func.count(TaskCommentRead.comment_id).label('read')
        ).filter(
            TaskCommentRead.task_id.in_(all_task_ids),
            TaskCommentRead.user_id == current_user.id
        ).group_by(TaskCommentRead.task_id).subquery()

        # Tính tổng unread
        results = db.session.query(
            (func.coalesce(total_comments_subq.c.total, 0) -
             func.coalesce(read_comments_subq.c.read, 0)).label('unread')
        ).select_from(total_comments_subq).outerjoin(
            read_comments_subq,
            total_comments_subq.c.task_id == read_comments_subq.c.task_id
        ).all()

        for (unread,) in results:
            if unread > 0:
                total_unread_messages += unread
                tasks_with_unread += 1

    # ===== ĐẾM TỔNG SỐ (TỐI ƯU) =====
    now = datetime.utcnow()

    if status == 'DONE':
        on_time_count = base_query.filter(Task.completed_overdue == False).count()
        overdue_count = base_query.filter(Task.completed_overdue == True).count()
    else:
        on_time_count = base_query.filter(Task.due_date >= now).count()
        overdue_count = base_query.filter(Task.due_date < now).count()

    # ===== SORTING =====
    if status == 'DONE':
        base_query = base_query.order_by(Task.updated_at.desc())
    else:
        priority_order = case(
            (Task.due_date.is_(None), 3),
            (Task.due_date < func.now(), 1),
            else_=2
        )
        base_query = base_query.order_by(
            priority_order.asc(),
            Task.due_date.asc().nullslast()
        )

    # ===== PAGINATION =====
    pagination = base_query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    tasks = pagination.items
    task_ids = [task.id for task in tasks]

    # ===== BATCH LOAD UNREAD COUNTS CHỈ CHO TRANG HIỆN TẠI =====
    unread_counts = {}

    if task_ids:
        total_comments_subq = db.session.query(
            TaskComment.task_id,
            func.count(TaskComment.id).label('total')
        ).filter(
            TaskComment.task_id.in_(task_ids),
            TaskComment.user_id != current_user.id
        ).group_by(TaskComment.task_id).subquery()

        read_comments_subq = db.session.query(
            TaskCommentRead.task_id,
            func.count(TaskCommentRead.comment_id).label('read')
        ).filter(
            TaskCommentRead.task_id.in_(task_ids),
            TaskCommentRead.user_id == current_user.id
        ).group_by(TaskCommentRead.task_id).subquery()

        results = db.session.query(
            total_comments_subq.c.task_id,
            (func.coalesce(total_comments_subq.c.total, 0) -
             func.coalesce(read_comments_subq.c.read, 0)).label('unread')
        ).outerjoin(
            read_comments_subq,
            total_comments_subq.c.task_id == read_comments_subq.c.task_id
        ).all()

        unread_counts = {task_id: max(0, unread) for task_id, unread in results}

    # ===== BATCH LOAD ASSIGNMENTS =====
    if task_ids:
        all_assignments = db.session.query(TaskAssignment).options(
            joinedload(TaskAssignment.user)
        ).filter(
            TaskAssignment.task_id.in_(task_ids),
            TaskAssignment.accepted == True
        ).all()

        assignments_by_task = {}
        for assignment in all_assignments:
            if assignment.task_id not in assignments_by_task:
                assignments_by_task[assignment.task_id] = []
            assignments_by_task[assignment.task_id].append(assignment)

        for task in tasks:
            task._cached_assignments = assignments_by_task.get(task.id, [])

    # ===== GÁN DATA CHO TASKS =====
    for task in tasks:
        if task.due_date:
            task.vn_due_date = utc_to_vn(task.due_date)
        task.unread_comment_count = unread_counts.get(task.id, 0)

    return render_template('priority_detail.html',
                           user=user,
                           tasks=tasks,
                           pagination=pagination,
                           priority_type=priority_type,
                           priority_icon=priority_icon,
                           on_time_count=on_time_count,
                           overdue_count=overdue_count,
                           tag=tag,
                           status=status,
                           total_unread_messages=total_unread_messages,
                           tasks_with_unread=tasks_with_unread)


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

    # ===== CHECK PHÊ DUYỆT =====
    # Nếu task cần phê duyệt và chưa được duyệt => KHÔNG cho phép
    if task.requires_approval and task.approved is None:
        # CHỈ DIRECTOR mới được bypass
        if current_user.role != 'director':
            return jsonify({
                'success': False,
                'error': 'Công việc chưa được phê duyệt. Vui lòng chờ phê duyệt.'
            }), 403

    # Nếu task bị TỪ CHỐI => KHÔNG cho phép
    if task.requires_approval and task.approved is False:
        return jsonify({
            'success': False,
            'error': 'Công việc đã bị từ chối.'
        }), 403

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
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif','webp', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'zip', 'rar'}
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
        comment_dict = {
            'id': comment.id,
            'user_id': comment.user_id,
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
            'can_delete': current_user.role == 'director',
            'has_attachment': comment.has_attachment
        }

        # Thêm thông tin file nếu có
        if comment.has_attachment:
            comment_dict['attachment'] = {
                'filename': comment.attachment_original_filename,
                'file_type': comment.attachment_file_type,
                'file_size': comment.attachment_file_size,
                'download_url': url_for('tasks.download_comment_attachment',
                                       task_id=task_id,
                                       comment_id=comment.id)
            }

        comments_data.append(comment_dict)

    return jsonify({
        'success': True,
        'comments': comments_data,
        'total': len(comments_data)
    })


@bp.route('/<int:task_id>/comments', methods=['POST'])
@login_required
def add_comment(task_id):
    """Thêm comment mới (có thể kèm file)"""
    task = Task.query.get_or_404(task_id)

    # Check permission
    assignment = TaskAssignment.query.filter_by(
        task_id=task_id,
        user_id=current_user.id,
        accepted=True
    ).first()

    if not assignment and task.creator_id != current_user.id and current_user.role not in ['director', 'manager']:
        return jsonify({'success': False, 'error': 'Không có quyền'}), 403

    # Lấy nội dung từ form (vì có file upload)
    content = request.form.get('content', '').strip()

    has_files = 'file' in request.files and request.files.getlist('file')

    if not content and not has_files:
        return jsonify({
            'success': False,
            'error': 'Vui lòng nhập nội dung hoặc đính kèm file'
        }), 400

    if not content and has_files:
        content = '[Đã gửi file đính kèm]'

    try:
        from app.models import TaskComment, TaskCommentAttachment
        from app.utils import utc_to_vn

        comment = TaskComment(
            task_id=task_id,
            user_id=current_user.id,
            content=content
        )

        # =====  XỬ LÝ NHIỀU FILE =====
        uploaded_files = []

        if 'file' in request.files:
            files = request.files.getlist('file')  # Lấy nhiều files

            now_utc = datetime.utcnow()
            month_folder = now_utc.strftime('%Y_%m')  # Format: 2024_12

            upload_folder = os.path.join(
                current_app.root_path,
                'uploads',
                f'comment_attachments_{month_folder}'
            )
            os.makedirs(upload_folder, exist_ok=True)

            for file in files:
                if file and file.filename != '':
                    if not allowed_file(file.filename):
                        return jsonify({'success': False, 'error': f'File {file.filename} không được phép'}), 400

                    # Check file size
                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)

                    if file_size > MAX_FILE_SIZE:
                        return jsonify({'success': False, 'error': f'File {file.filename} quá lớn (max 10MB)'}), 400

                    # Save file
                    filename = secure_filename(file.filename)
                    unique_filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{filename}"

                    file_path = os.path.join(upload_folder, unique_filename)
                    file.save(file_path)

                    uploaded_files.append({
                        'filename': unique_filename,
                        'original_filename': filename,
                        'file_path': file_path,
                        'file_size': file_size,
                        'file_type': get_file_type(filename)
                    })

        # Đánh dấu comment có attachment (tương thích ngược)
        if uploaded_files:
            comment.has_attachment = True
            # Giữ nguyên field cũ cho file đầu tiên (backward compatibility)
            first_file = uploaded_files[0]
            comment.attachment_filename = first_file['filename']
            comment.attachment_original_filename = first_file['original_filename']
            comment.attachment_file_path = first_file['file_path']
            comment.attachment_file_size = first_file['file_size']
            comment.attachment_file_type = first_file['file_type']

        db.session.add(comment)
        db.session.flush()

        #Tạo records trong bảng attachments
        attachment_objects = []
        for file_info in uploaded_files:
            attachment = TaskCommentAttachment(
                comment_id=comment.id,
                filename=file_info['filename'],
                original_filename=file_info['original_filename'],
                file_path=file_info['file_path'],
                file_size=file_info['file_size'],
                file_type=file_info['file_type']
            )
            db.session.add(attachment)
            attachment_objects.append(attachment)

        # ===== GỬI THÔNG BÁO =====
        notification_recipients = set()

        if current_user.id != task.creator_id:
            notification_recipients.add(task.creator_id)

        assignments = TaskAssignment.query.filter_by(task_id=task_id, accepted=True).all()
        for assignment in assignments:
            if assignment.user_id != current_user.id:
                notification_recipients.add(assignment.user_id)

        for recipient_id in notification_recipients:
            existing_notif = Notification.query.filter_by(
                user_id=recipient_id,
                type='task_comment',
                link=f'/tasks/{task_id}/discussion',
                read=False  # ← CHỈ TÌM NOTIFICATION CHƯA ĐỌC
            ).order_by(Notification.created_at.desc()).first()

            if existing_notif:
                # Đếm comments sau notification
                unread_count = TaskComment.query.filter(
                    TaskComment.task_id == task_id,
                    TaskComment.created_at > existing_notif.created_at
                ).count()

                existing_notif.title = f'💬 {unread_count} tin nhắn mới trong nhiệm vụ {task.title}'
                existing_notif.body = f'{current_user.full_name} đã bình luận'
                existing_notif.read = False
            else:
                notif = Notification(
                    user_id=recipient_id,
                    type='task_comment',
                    title=f'💬 Tin nhắn mới trong nhiệm vụ {task.title}',
                    body=f'{current_user.full_name} đã bình luận',
                    link=f'/tasks/{task_id}/discussion'
                )
                db.session.add(notif)

        db.session.commit()

        vn_time = utc_to_vn(comment.created_at)

        # Tạo response với DANH SÁCH attachments
        comment_data = {
            'id': comment.id,
            'user_id': current_user.id,
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
            'can_delete': True,
            'has_attachment': comment.has_attachment,
            'attachments': []
        }

        # Thêm thông tin TẤT CẢ files
        if comment.has_attachment:
            for att in attachment_objects:
                comment_data['attachments'].append({
                    'id': att.id,
                    'filename': att.original_filename,
                    'file_type': att.file_type,
                    'file_size': att.file_size,
                    'download_url': url_for('tasks.download_comment_attachment',
                                            task_id=task_id,
                                            comment_id=comment.id,
                                            attachment_id=att.id)
                })

        return jsonify({
            'success': True,
            'comment': comment_data
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error adding comment: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:task_id>/comments/<int:comment_id>', methods=['DELETE'])
@login_required
def delete_comment(task_id, comment_id):
    """Xóa comment (và TẤT CẢ file đính kèm)"""
    from app.models import TaskComment, TaskCommentAttachment

    comment = TaskComment.query.get_or_404(comment_id)

    if comment.task_id != task_id:
        return jsonify({'success': False, 'error': 'Comment không tồn tại'}), 404

    # Only  director can delete
    if current_user.role != 'director':
        return jsonify({'success': False, 'error': 'Không có quyền xóa tin nhắn'}), 403

    try:
        # ===== XÓA TẤT CẢ FILES =====

        # 1. Xóa file cũ (backward compatibility)
        if comment.has_attachment and comment.attachment_file_path:
            try:
                if os.path.exists(comment.attachment_file_path):
                    os.remove(comment.attachment_file_path)
                    print(f"✅ Deleted old file: {comment.attachment_file_path}")
            except Exception as e:
                print(f"⚠️ Could not delete old file: {e}")

        # 2. Xóa TẤT CẢ files trong bảng attachments
        attachments = TaskCommentAttachment.query.filter_by(comment_id=comment_id).all()

        for attachment in attachments:
            try:
                if os.path.exists(attachment.file_path):
                    os.remove(attachment.file_path)
                    print(f"✅ Deleted attachment file: {attachment.file_path}")
            except Exception as e:
                print(f"⚠️ Could not delete attachment file: {e}")

            # Xóa record trong database
            db.session.delete(attachment)

        # 3. Xóa comment trong database (cascade sẽ tự động xóa attachments)
        db.session.delete(comment)
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error deleting comment: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:task_id>/comments/<int:comment_id>/attachments/<int:attachment_id>/download')
@login_required
def download_comment_attachment(task_id, comment_id, attachment_id):
    """Download 1 file cụ thể từ comment"""
    from app.models import TaskComment, TaskCommentAttachment

    #  Handle fallback cho attachment_id=0 (dữ liệu cũ)
    if attachment_id == 0:
        comment = TaskComment.query.get_or_404(comment_id)
        if comment.task_id != task_id:
            flash('File không tồn tại', 'danger')
            return redirect(url_for('tasks.task_detail', task_id=task_id))

        if not comment.has_attachment or not comment.attachment_file_path:
            flash('Không có file đính kèm', 'danger')
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

        directory = os.path.dirname(comment.attachment_file_path)
        return send_from_directory(directory, comment.attachment_filename, as_attachment=True,
                                   download_name=comment.attachment_original_filename)

    # ✅ XỬ LÝ BÌNH THƯỜNG cho dữ liệu mới
    attachment = TaskCommentAttachment.query.get_or_404(attachment_id)

    if attachment.comment_id != comment_id:
        flash('File không tồn tại', 'danger')
        return redirect(url_for('tasks.task_detail', task_id=task_id))

    comment = attachment.comment
    if comment.task_id != task_id:
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


@bp.route('/<int:task_id>/comments/<int:comment_id>/attachments/<int:attachment_id>/preview')
@login_required
def preview_comment_attachment(task_id, comment_id, attachment_id):
    """Preview file Word/Excel từ comment attachment"""
    from app.models import TaskComment, TaskCommentAttachment
    from app.files import generate_file_token

    attachment = TaskCommentAttachment.query.get_or_404(attachment_id)

    if attachment.comment_id != comment_id:
        flash('File không tồn tại', 'danger')
        return redirect(url_for('tasks.task_discussion', task_id=task_id))

    comment = attachment.comment
    if comment.task_id != task_id:
        flash('File không tồn tại', 'danger')
        return redirect(url_for('tasks.task_discussion', task_id=task_id))

    task = Task.query.get_or_404(task_id)
    assignment = TaskAssignment.query.filter_by(
        task_id=task_id,
        user_id=current_user.id,
        accepted=True
    ).first()

    if not assignment and task.creator_id != current_user.id and current_user.role not in ['director', 'manager']:
        flash('Bạn không có quyền xem file này', 'danger')
        return redirect(url_for('tasks.task_discussion', task_id=task_id))

    # Tạo token
    token = generate_file_token(f"comment_{comment_id}_{attachment_id}", expires_in=1800)

    # URL công khai
    file_url = url_for('tasks.view_comment_attachment_public', token=token, _external=True)

    return render_template('preview_comment_file.html',
                           task=task,
                           attachment=attachment,
                           file_url=file_url,
                           file_type=attachment.file_type)

@bp.route('/<int:task_id>/quick-rate', methods=['POST'])
@login_required
@role_required(['director', 'manager'])
def quick_rate_task(task_id):
    """
    API đánh giá nhanh task (cho nút đánh giá trên priority_detail)
    """
    task = Task.query.get_or_404(task_id)

    # Kiểm tra task đã hoàn thành chưa
    if task.status != 'DONE':
        return jsonify({'success': False, 'error': 'Chỉ có thể đánh giá nhiệm vụ đã hoàn thành'}), 400

    rating = request.json.get('rating')

    if rating not in ['good', 'bad']:
        return jsonify({'success': False, 'error': 'Đánh giá không hợp lệ'}), 400

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

    return jsonify({
        'success': True,
        'rating': rating,
        'message': f'Đã đánh giá: {rating_text}'
    })

@bp.route('/<int:task_id>/discussion')
@login_required
def task_discussion(task_id):
    """Trang thảo luận riêng cho task"""
    task = Task.query.get_or_404(task_id)

    # Check permission
    if current_user.role not in ['director', 'manager']:
        assignment = TaskAssignment.query.filter_by(
            task_id=task_id,
            user_id=current_user.id
        ).first()

        if not assignment and task.creator_id != current_user.id:
            flash('Bạn không có quyền xem nhiệm vụ này.', 'danger')
            return redirect(url_for('tasks.list_tasks'))

    # Get assignment for current user
    user_assignment = TaskAssignment.query.filter_by(
        task_id=task_id,
        user_id=current_user.id
    ).first()

    # Mark comments as read when entering discussion page
    mark_task_comments_as_read(task_id, current_user.id)

    # Get all assignments (for showing participants)
    assignments = TaskAssignment.query.filter_by(task_id=task_id).all()

    # Get initial comments
    sorted_comments = TaskComment.query.filter_by(task_id=task_id).order_by(TaskComment.created_at.asc()).all()

    # ===== PRIORITY INFO =====
    priority_icon = ''
    priority_text = ''
    priority_class = ''

    if task.is_urgent:
        priority_icon = '🔥'
        priority_text = 'KHẨN CẤP'
        priority_class = 'urgent'
    elif task.is_important:
        priority_icon = '⭐'
        priority_text = 'QUAN TRỌNG'
        priority_class = 'important'
    elif task.is_recurring:
        priority_icon = '🔁'
        priority_text = 'LẶP LẠI'
        priority_class = 'recurring'

    return render_template('task_discussion.html',
                           task=task,
                           user_assignment=user_assignment,
                           assignments=assignments,
                           sorted_comments=sorted_comments,
                           priority_icon=priority_icon,
                           priority_text=priority_text,
                           priority_class=priority_class)


@bp.route('/comment-attachments/public/<token>')
def view_comment_attachment_public(token):
    """Serve comment attachment qua signed URL - KHÔNG CẦN LOGIN"""
    from app.files import verify_file_token
    from app.models import TaskCommentAttachment

    data = verify_file_token(token, max_age=1800)
    if not data:
        abort(403)

    try:
        parts = data.split('_')
        comment_id = int(parts[1])
        attachment_id = int(parts[2])
    except:
        abort(403)

    attachment = TaskCommentAttachment.query.get_or_404(attachment_id)
    if attachment.comment_id != comment_id:
        abort(403)

    mime_types = {
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'pdf': 'application/pdf',
    }

    file_ext = attachment.original_filename.rsplit('.', 1)[1].lower() if '.' in attachment.original_filename else ''
    mimetype = mime_types.get(file_ext, 'application/octet-stream')

    if not os.path.exists(attachment.file_path):
        abort(404)

    directory = os.path.dirname(attachment.file_path)
    filename = os.path.basename(attachment.file_path)

    response = send_from_directory(directory, filename, as_attachment=False, mimetype=mimetype)
    response.headers['Cache-Control'] = 'public, max-age=1800'
    response.headers['Access-Control-Allow-Origin'] = '*'

    return response


@bp.route('/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    """
    Chỉnh sửa task
    - Director: Chỉnh sửa TẤT CẢ nhiệm vụ
    - Manager: Chỉnh sửa nhiều loại nhiệm vụ:
        + Task do HR tạo
        + Task do chính Manager tạo
        + Task được giao cho HR (KHÔNG bao gồm kế toán)
    - HR/Accountant: Không có quyền
    """
    task = Task.query.get_or_404(task_id)

    # ===== KIỂM TRA QUYỀN =====
    can_edit = False

    if current_user.role == 'director':
        # Director chỉnh sửa được tất cả
        can_edit = True

    elif current_user.role == 'manager':
        # 1. Task do HR tạo
        if task.creator.role == 'hr':
            can_edit = True

        # 2. Task do chính Manager tạo
        elif task.creator_id == current_user.id:
            can_edit = True

        # 3. Task được giao cho HR (CHỈ HR, không bao gồm kế toán)
        else:
            for assignment in task.assignments:
                if assignment.user.role == 'hr':
                    can_edit = True
                    break

    if not can_edit:
        flash('Bạn không có quyền chỉnh sửa nhiệm vụ này.', 'danger')
        return redirect(url_for('tasks.task_detail', task_id=task_id))

    # ===== XỬ LÝ POST REQUEST =====
    if request.method == 'POST':
        # Cập nhật mô tả
        task.description = request.form.get('description')

        # Cập nhật due_date
        due_date_str = request.form.get('due_date')
        if due_date_str:
            try:
                vn_datetime = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
                task.due_date = vn_to_utc(vn_datetime)
            except:
                try:
                    vn_datetime = datetime.strptime(due_date_str, '%Y-%m-%d')
                    task.due_date = vn_to_utc(vn_datetime)
                except:
                    flash('Định dạng ngày giờ không hợp lệ.', 'danger')
                    return redirect(url_for('tasks.edit_task', task_id=task_id))
        else:
            task.due_date = None

        # Cập nhật recurrence
        task.recurrence_enabled = request.form.get('recurrence_enabled') == 'on'
        if task.recurrence_enabled:
            task.recurrence_interval_days = int(request.form.get('recurrence_interval_days', 7))
        else:
            task.recurrence_interval_days = None

        task.updated_at = datetime.utcnow()

        try:
            db.session.commit()
            flash('✅ Cập nhật nhiệm vụ thành công!', 'success')
            return redirect(url_for('tasks.task_detail', task_id=task_id))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Lỗi: {str(e)}', 'danger')
            return redirect(url_for('tasks.edit_task', task_id=task_id))

    # ===== XỬ LÝ GET REQUEST =====
    vn_due_date = None
    if task.due_date:
        vn_due_date = utc_to_vn(task.due_date).strftime('%Y-%m-%dT%H:%M')

    return render_template('edit_task.html',
                           task=task,
                           vn_due_date=vn_due_date)