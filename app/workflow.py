from flask import Blueprint, render_template, abort, request
from flask_login import login_required, current_user
from app import db
from app.models import Task, TaskAssignment, User
from sqlalchemy import and_, or_
from datetime import datetime

bp = Blueprint('workflow', __name__)


def get_workflow_data():
    """
    Lấy dữ liệu số lượng tasks giữa từng user cụ thể

    Logic:
    - creator->assignee: Số tasks đang giao (PENDING, IN_PROGRESS)
    - assignee->creator: Số tasks hoàn thành chưa đánh giá (DONE, rating=None)

    Returns: dict với key là 'from_id->to_id' và value là {'active': số_đang_giao, 'needs_rating': số_cần_đánh_giá}
    """
    workflow_counts = {}

    # ===== CHIỀU 1: Tasks đang giao (PENDING, IN_PROGRESS) =====
    active_tasks = Task.query.filter(
        Task.status.in_(['PENDING', 'IN_PROGRESS'])
    ).all()

    for task in active_tasks:
        creator_id = task.creator_id

        # Lấy người được giao đã accept
        accepted_assignments = TaskAssignment.query.filter_by(
            task_id=task.id,
            accepted=True
        ).all()

        for assignment in accepted_assignments:
            assignee_id = assignment.user_id

            # Key: creator->assignee (chiều giao việc)
            key = f"{creator_id}->{assignee_id}"
            if key not in workflow_counts:
                workflow_counts[key] = {'active': 0, 'needs_rating': 0}
            workflow_counts[key]['active'] += 1

    # ===== CHIỀU 2: Tasks hoàn thành chưa đánh giá (DONE, rating=None) =====
    done_tasks = Task.query.filter(
        Task.status == 'DONE',
        Task.performance_rating == None  # Chưa đánh giá
    ).all()

    for task in done_tasks:
        creator_id = task.creator_id  # Người giao việc (Sếp)

        # Lấy người đã làm xong
        accepted_assignments = TaskAssignment.query.filter_by(
            task_id=task.id,
            accepted=True
        ).all()

        for assignment in accepted_assignments:
            assignee_id = assignment.user_id  # Người làm việc (NV)

            # Key NGƯỢC LẠI: assignee->creator (chiều báo cáo hoàn thành)
            reverse_key = f"{assignee_id}->{creator_id}"
            if reverse_key not in workflow_counts:
                workflow_counts[reverse_key] = {'active': 0, 'needs_rating': 0}
            workflow_counts[reverse_key]['needs_rating'] += 1

    return workflow_counts


def can_view_tasks(from_user_id, to_user_id):
    """
    Kiểm tra user hiện tại có quyền xem tasks giữa 2 user cụ thể không

    Logic:
    - Director: Xem tất cả
    - Manager: Xem tasks họ tham gia (creator hoặc assignee)
    - Accountant/HR: CHỈ xem tasks họ là creator HOẶC assignee
    """
    if current_user.role == 'director':
        # Director xem tất cả
        return True

    elif current_user.role == 'manager':
        # Manager xem tasks họ giao hoặc nhận
        if from_user_id == current_user.id or to_user_id == current_user.id:
            return True
        return False

    elif current_user.role in ['accountant', 'hr']:
        # Accountant/HR CHỈ xem tasks liên quan trực tiếp đến họ
        if from_user_id == current_user.id or to_user_id == current_user.id:
            return True
        return False

    return False


@bp.route('/')
@login_required
def workflow_diagram():
    """Hiển thị ma trận workflow"""

    # Lấy dữ liệu đếm theo user_id
    workflow_counts = get_workflow_data()

    # Lấy tất cả users active
    all_users = User.query.filter_by(is_active=True).order_by(
        # Sắp xếp theo role rồi tên
        db.case(
            (User.role == 'director', 1),
            (User.role == 'manager', 2),
            (User.role == 'accountant', 3),
            (User.role == 'hr', 4),
            else_=5
        ),
        User.full_name
    ).all()

    # Role names cho display
    role_names = {
        'director': 'GĐ',
        'manager': 'TP',
        'accountant': 'KT',
        'hr': 'NV'
    }

    # Tạo workflow data dict với thông tin can_view
    workflow_data = {}
    total_tasks = 0
    active_connections = 0

    for from_user in all_users:
        for to_user in all_users:
            if from_user.id == to_user.id:
                continue

            key = f"{from_user.id}->{to_user.id}"

            # ===== SỬA: Lấy cả active và needs_rating =====
            if key in workflow_counts:
                counts = workflow_counts[key]
                total_count = counts['active'] + counts['needs_rating']

                if total_count > 0:
                    can_view = can_view_tasks(from_user.id, to_user.id)
                    workflow_data[key] = {
                        'count': total_count,
                        'active': counts['active'],
                        'needs_rating': counts['needs_rating'],
                        'can_view': can_view,
                        'from_name': from_user.full_name,
                        'to_name': to_user.full_name
                    }
                    total_tasks += total_count
                    active_connections += 1

    return render_template('workflow.html',
                           all_users=all_users,
                           workflow_data=workflow_data,
                           role_names=role_names,
                           total_tasks=total_tasks,
                           active_connections=active_connections,
                           total_users=len(all_users))


@bp.route('/<int:from_user_id>/<int:to_user_id>')
@login_required
def workflow_user_tasks(from_user_id, to_user_id):
    """
    Hiển thị danh sách tasks giữa 2 user cụ thể

    ===== LOGIC MỚI: HIỂN THỊ CẢ 2 LOẠI =====
    - Tasks đang giao (PENDING, IN_PROGRESS) do from_user giao cho to_user
    - Tasks cần đánh giá (DONE, chưa rate) do to_user giao cho from_user (và from_user đã làm xong)

    Args:
        from_user_id: User ID người giao/người làm
        to_user_id: User ID người nhận/người cần đánh giá
    """

    # Get users
    from_user = User.query.get_or_404(from_user_id)
    to_user = User.query.get_or_404(to_user_id)

    # Kiểm tra quyền xem
    if not can_view_tasks(from_user_id, to_user_id):
        abort(403)

    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # ===== LOGIC MỚI: LẤY CẢ 2 LOẠI TASKS =====

    # 1. Tasks ĐANG GIAO: from_user giao cho to_user (PENDING, IN_PROGRESS)
    assigned_task_ids = [a.task_id for a in TaskAssignment.query.filter_by(
        user_id=to_user_id,
        accepted=True
    ).all()]

    active_tasks_query = Task.query.filter(
        Task.creator_id == from_user_id,
        Task.id.in_(assigned_task_ids),
        Task.status.in_(['PENDING', 'IN_PROGRESS'])
    )

    # 2. Tasks CẦN ĐÁNH GIÁ: to_user giao cho from_user, from_user đã DONE chưa rate
    done_task_ids = [a.task_id for a in TaskAssignment.query.filter_by(
        user_id=from_user_id,  # from_user là người làm
        accepted=True
    ).all()]

    needs_rating_query = Task.query.filter(
        Task.creator_id == to_user_id,  # to_user là người giao việc
        Task.id.in_(done_task_ids),
        Task.status == 'DONE',
        Task.performance_rating == None
    )

    # ===== KẾT HỢP 2 QUERY BẰNG UNION =====
    from sqlalchemy import union_all

    # Lấy tất cả tasks từ cả 2 query
    combined_query = active_tasks_query.union(needs_rating_query)

    # Pagination
    pagination = combined_query.order_by(Task.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    tasks = pagination.items

    # ===== XÁC ĐỊNH WORKFLOW_TYPE CHO TỪNG TASK =====
    active_task_ids_set = set([t.id for t in active_tasks_query.all()])
    needs_rating_task_ids_set = set([t.id for t in needs_rating_query.all()])

    for task in tasks:
        task.needs_my_rating = False
        task.is_active_assignment = False

        # Đánh dấu tasks đang giao
        if task.id in active_task_ids_set:
            task.is_active_assignment = True

        # Đánh dấu tasks cần đánh giá
        if task.id in needs_rating_task_ids_set:
            if task.status == 'DONE' and not task.performance_rating:
                # Người xem là to_user và là người cần đánh giá
                if to_user_id == current_user.id:
                    task.needs_my_rating = True

    # Đếm số lượng từng loại
    active_count = active_tasks_query.count()
    needs_rating_count = needs_rating_query.count()

    # Role names
    role_names = {
        'director': 'Giám Đốc',
        'manager': 'Trưởng Phòng',
        'accountant': 'Kế Toán',
        'hr': 'Nhân Viên'
    }

    return render_template('workflow_tasks.html',
                           tasks=tasks,
                           pagination=pagination,
                           from_role=from_user.role,
                           to_role=to_user.role,
                           from_role_name=from_user.full_name,
                           to_role_name=to_user.full_name,
                           from_user_id=from_user_id,
                           to_user_id=to_user_id,
                           active_count=active_count,
                           needs_rating_count=needs_rating_count,
                           workflow_type='mixed')  # Mixed type


@bp.route('/<from_role>/<to_role>')
@login_required
def workflow_tasks(from_role, to_role):
    """
    Hiển thị danh sách tasks giữa 2 role (legacy route - giữ lại cho tương thích)

    Args:
        from_role: Role người tạo task
        to_role: Role người được giao task
    """

    # Validate roles
    valid_roles = ['director', 'manager', 'accountant', 'hr']
    if from_role not in valid_roles or to_role not in valid_roles:
        abort(404)

    # Kiểm tra quyền xem
    if not can_view_tasks(from_role, to_role):
        abort(403)

    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # Query tasks
    # Lấy users theo role
    creators = User.query.filter_by(role=from_role, is_active=True).all()
    assignees = User.query.filter_by(role=to_role, is_active=True).all()

    creator_ids = [u.id for u in creators]
    assignee_ids = [u.id for u in assignees]

    # Lấy task_ids từ assignments
    accepted_assignments = TaskAssignment.query.filter(
        TaskAssignment.user_id.in_(assignee_ids),
        TaskAssignment.accepted == True
    ).all()

    task_ids = [a.task_id for a in accepted_assignments]

    # Query tasks
    query = Task.query.filter(
        Task.creator_id.in_(creator_ids),
        Task.id.in_(task_ids),
        Task.status.in_(['PENDING', 'IN_PROGRESS'])
    )

    # Pagination
    pagination = query.order_by(Task.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    tasks = pagination.items

    # Role names for display
    role_names = {
        'director': 'Giám Đốc',
        'manager': 'Trưởng Phòng',
        'accountant': 'Kế Toán',
        'hr': 'Nhân Viên'
    }

    return render_template('workflow_tasks.html',
                           tasks=tasks,
                           pagination=pagination,
                           from_role=from_role,
                           to_role=to_role,
                           from_role_name=role_names[from_role],
                           to_role_name=role_names[to_role])