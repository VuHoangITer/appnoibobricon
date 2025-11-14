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
    Returns: dict với key là 'creator_id->assignee_id' và value là số lượng
    """
    workflow_counts = {}

    # Lấy tất cả tasks đang active (PENDING, IN_PROGRESS)
    active_tasks = Task.query.filter(
        Task.status.in_(['PENDING', 'IN_PROGRESS'])
    ).all()

    for task in active_tasks:
        creator_id = task.creator_id

        # Lấy tất cả assignments đã accept
        accepted_assignments = TaskAssignment.query.filter_by(
            task_id=task.id,
            accepted=True
        ).all()

        for assignment in accepted_assignments:
            assignee_id = assignment.user_id

            # Tạo key: creator_id->assignee_id
            key = f"{creator_id}->{assignee_id}"
            workflow_counts[key] = workflow_counts.get(key, 0) + 1

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
            count = workflow_counts.get(key, 0)

            if count > 0:
                can_view = can_view_tasks(from_user.id, to_user.id)
                workflow_data[key] = {
                    'count': count,
                    'can_view': can_view,
                    'from_name': from_user.full_name,
                    'to_name': to_user.full_name
                }
                total_tasks += count
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

    Args:
        from_user_id: User ID người tạo task
        to_user_id: User ID người được giao task
    """

    # Get users
    from_user = User.query.get_or_404(from_user_id)
    to_user = User.query.get_or_404(to_user_id)

    # Kiểm tra quyền xem - TRUYỀN USER_ID thay vì ROLE
    if not can_view_tasks(from_user_id, to_user_id):
        abort(403)

    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # Query tasks: creator = from_user, assignee = to_user, accepted = True
    task_ids = [a.task_id for a in TaskAssignment.query.filter_by(
        user_id=to_user_id,
        accepted=True
    ).all()]

    query = Task.query.filter(
        Task.creator_id == from_user_id,
        Task.id.in_(task_ids),
        Task.status.in_(['PENDING', 'IN_PROGRESS'])
    )

    # Pagination
    pagination = query.order_by(Task.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    tasks = pagination.items

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
                           to_user_id=to_user_id)


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