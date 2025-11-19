from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from app.models import Task, TaskAssignment, Salary, Employee, News, Notification, User
from datetime import datetime, timedelta
from sqlalchemy import and_, or_
from app.utils import utc_to_vn, vn_now

bp = Blueprint('hub', __name__, url_prefix='/hub')


@bp.route('/')
@login_required
def workflow_hub():
    """Trang Hub - Quy trình công việc tổng quan"""

    now = datetime.utcnow()  #  SỬ DỤNG UTC ĐỂ SO SÁNH VỚI DATABASE
    # ========================================
    #  CÔNG VIỆC HÀNG NGÀY (Cho tất cả roles)
    # ========================================
    my_assignments = TaskAssignment.query.filter_by(
        user_id=current_user.id,
        accepted=True
    ).all()
    my_task_ids = [a.task_id for a in my_assignments]

    # Công việc chờ xử lý của tôi
    my_pending_tasks = Task.query.filter(
        Task.id.in_(my_task_ids),
        Task.status == 'PENDING'
    ).count()

    # Công việc đang làm
    my_in_progress = Task.query.filter(
        Task.id.in_(my_task_ids),
        Task.status == 'IN_PROGRESS'
    ).count()

    # ✅ Công việc sắp đến hạn (trong vòng 3 ngày - SO SÁNH BẰNG UTC)
    three_days_later = now + timedelta(days=3)
    my_due_soon = Task.query.filter(
        Task.id.in_(my_task_ids),
        Task.due_date >= now,  # So sánh UTC với UTC
        Task.due_date <= three_days_later,
        Task.status.in_(['PENDING', 'IN_PROGRESS'])
    ).count()

    # Công việc quá hạn của tôi
    my_overdue = Task.query.filter(
        Task.id.in_(my_task_ids),
        Task.due_date < now,  # So sánh UTC với UTC
        Task.status.in_(['PENDING', 'IN_PROGRESS'])
    ).count()

    # Công việc đã hoàn thành
    my_completed_recent = Task.query.filter(
        Task.id.in_(my_task_ids),
        Task.status == 'DONE'
    ).count()

    # ========================================
    # QUẢN LÝ CÔNG VIỆC (Director/Manager)
    # ========================================
    total_tasks = 0
    tasks_need_rating = 0
    my_tasks_need_rating = 0
    team_overdue = 0
    team_pending = 0

    if current_user.role in ['director', 'manager']:
        # Tổng công việc trong hệ thống
        total_tasks = Task.query.count()

        if current_user.role in ['director', 'manager']:
            # Tổng công việc trong hệ thống
            total_tasks = Task.query.count()

            # ✅ BIẾN 1: Tất cả tasks cần đánh giá trong hệ thống (cho CARD)
            tasks_need_rating = Task.query.filter(
                Task.status == 'DONE',
                Task.performance_rating == None
            ).count()

            # ✅ BIẾN 2: Tasks do MÌNH giao cần đánh giá (cho ICON)
            my_tasks_need_rating = Task.query.filter(
                Task.creator_id == current_user.id,
                Task.status == 'DONE',
                Task.performance_rating == None
            ).count()

        # Công việc quá hạn (toàn hệ thống)
        team_overdue = Task.query.filter(
            Task.due_date < now,  # So sánh UTC với UTC
            Task.status.in_(['PENDING', 'IN_PROGRESS'])
        ).count()

        # Công việc chờ xử lý (toàn hệ thống)
        team_pending = Task.query.filter_by(status='PENDING').count()

    # ========================================
    #  LƯƠNG & TÀI CHÍNH (Director/Accountant)
    # ========================================
    total_salaries = 0
    total_employees = 0
    pending_penalties = 0
    pending_advances = 0

    if current_user.role in ['director', 'accountant']:
        # Tổng bảng lương
        total_salaries = Salary.query.count()

        # Tổng nhân viên active
        total_employees = Employee.query.filter_by(is_active=True).count()

        # Phạt chưa trừ lương
        from app.models import Penalty, Advance
        pending_penalties = Penalty.query.filter_by(is_deducted=False).count()

        # Tạm ứng chưa trừ lương
        pending_advances = Advance.query.filter_by(is_deducted=False).count()

    # ========================================
    # THÔNG BÁO NỘI BỘ (Tất cả)
    # ========================================
    # Thông báo chưa đọc
    unread_notifications = Notification.query.filter_by(
        user_id=current_user.id,
        read=False
    ).count()

    # Tin tức chưa xác nhận đọc (nếu có)
    unconfirmed_news = News.query.filter(
        ~News.confirmations.any(user_id=current_user.id)
    ).count()

    # ========================================
    #  QUẢN TRỊ HỆ THỐNG (Director only)
    # ========================================
    total_users = 0
    active_users = 0

    if current_user.role == 'director':
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()

    #  TÍNH BADGE CHO TAB CÁ NHÂN
    my_work_badge =  my_due_soon + my_overdue

    #  TÍNH BADGE CHO TAB CÔNG VIỆC
    # Đếm số công việc do mình giao cần đánh giá
    tasks_badge = Task.query.filter(
        Task.creator_id == current_user.id,
        Task.status == 'DONE',
        Task.performance_rating == None
    ).count()

    return render_template('hub.html',
                           # Công việc cá nhân
                           my_pending_tasks=my_pending_tasks,
                           my_in_progress=my_in_progress,
                           my_due_soon=my_due_soon,
                           my_overdue=my_overdue,
                           my_completed_recent=my_completed_recent,
                           my_work_badge=my_work_badge,
                           tasks_badge=tasks_badge,
                           # Quản lý công việc
                           total_tasks=total_tasks,
                           tasks_need_rating=tasks_need_rating,
                           my_tasks_need_rating=my_tasks_need_rating,
                           team_overdue=team_overdue,
                           team_pending=team_pending,
                           # Lương & tài chính
                           total_salaries=total_salaries,
                           total_employees=total_employees,
                           pending_penalties=pending_penalties,
                           pending_advances=pending_advances,
                           # Thông báo
                           unread_notifications=unread_notifications,
                           unconfirmed_news=unconfirmed_news,
                           # Quản trị
                           total_users=total_users,
                           active_users=active_users)


# ========================================
#  XEM CÔNG VIỆC CỦA TÔI
# ========================================

@bp.route('/my-tasks/pending')
@login_required
def my_pending_tasks():
    """Xem công việc chưa làm của tôi"""
    from flask import redirect, url_for
    return redirect(url_for('tasks.list_tasks',
                            status='PENDING',
                            assigned_user=current_user.id))


@bp.route('/my-tasks/in-progress')
@login_required
def my_in_progress_tasks():
    """Xem công việc đang làm của tôi"""
    from flask import redirect, url_for
    return redirect(url_for('tasks.list_tasks',
                            status='IN_PROGRESS',
                            assigned_user=current_user.id))


@bp.route('/my-tasks/completed')
@login_required
def my_completed_tasks():
    """Xem tất cả công việc đã hoàn thành của tôi"""
    from flask import redirect, url_for
    return redirect(url_for('tasks.list_tasks',
                            status='DONE',
                            assigned_user=current_user.id))


# ========================================
# ✅ MỚI: API LẤY CÔNG VIỆC SẮP ĐẾN HẠN
# ========================================
@bp.route('/api/my-due-soon-tasks')
@login_required
def get_my_due_soon_tasks():
    """API: Lấy danh sách công việc sắp đến hạn (trong vòng 3 ngày kể từ bây giờ)"""
    try:
        now = datetime.utcnow()  # ✅ SỬ DỤNG UTC ĐỂ SO SÁNH
        three_days_later = now + timedelta(days=3)

        # Lấy danh sách task IDs của user
        my_assignments = TaskAssignment.query.filter_by(
            user_id=current_user.id,
            accepted=True
        ).all()
        my_task_ids = [a.task_id for a in my_assignments]

        # Query các task sắp đến hạn (SO SÁNH UTC VỚI UTC)
        due_soon_tasks = Task.query.filter(
            Task.id.in_(my_task_ids),
            Task.due_date >= now,  # UTC >= UTC
            Task.due_date <= three_days_later,  # UTC <= UTC
            Task.status.in_(['PENDING', 'IN_PROGRESS'])
        ).order_by(Task.due_date.asc()).all()

        tasks_data = []
        for task in due_soon_tasks:
            try:
                creator_name = task.creator.full_name if task.creator else 'Không rõ'

                # ✅ CONVERT UTC SANG VN TIMEZONE ĐỂ HIỂN THỊ
                due_date_vn = utc_to_vn(task.due_date)

                # Tính số ngày còn lại (dùng UTC để tính)
                time_diff = task.due_date - now  # UTC - UTC
                days_left = time_diff.days
                hours_left = time_diff.seconds // 3600

                if days_left < 0:
                    time_left = "Đã quá hạn"
                elif days_left == 0:
                    if hours_left > 0:
                        time_left = f"{hours_left} giờ nữa"
                    else:
                        time_left = "Hôm nay"
                elif days_left == 1:
                    time_left = "1 ngày nữa"
                else:
                    time_left = f"{days_left} ngày nữa"

                priority_label = []
                if task.is_urgent:
                    priority_label.append('Khẩn cấp')
                if task.is_important:
                    priority_label.append('Quan trọng')
                if task.is_recurring:
                    priority_label.append('Lặp lại')

                priority_display = ', '.join(priority_label) if priority_label else 'Bình thường'

                tasks_data.append({
                    'id': task.id,
                    'title': task.title,
                    'due_date': due_date_vn.strftime('%d/%m/%Y %H:%M'),  # ✅ FORMAT THEO GIỜ VN
                    'time_left': time_left,
                    'status': task.status,
                    'creator': creator_name,
                    'priority': priority_display,
                    'is_urgent': task.is_urgent,
                    'is_important': task.is_important,
                    'is_recurring': task.is_recurring
                })
            except Exception as e:
                print(f"Error processing task {task.id}: {str(e)}")
                continue

        return jsonify({'tasks': tasks_data, 'count': len(tasks_data)})

    except Exception as e:
        print(f"Error in get_my_due_soon_tasks: {str(e)}")
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500


# ========================================
# LẤY CÔNG VIỆC QUÁ HẠN CỦA TÔI
# ========================================
@bp.route('/api/my-overdue-tasks')
@login_required
def get_my_overdue_tasks():
    """API: Lấy danh sách công việc quá hạn của chính mình"""
    try:
        now = datetime.utcnow()  # ✅ SỬ DỤNG UTC

        # Lấy danh sách task IDs của user
        my_assignments = TaskAssignment.query.filter_by(
            user_id=current_user.id,
            accepted=True
        ).all()
        my_task_ids = [a.task_id for a in my_assignments]

        # Query các task quá hạn của mình (SO SÁNH UTC)
        overdue_tasks = Task.query.filter(
            Task.id.in_(my_task_ids),
            Task.due_date < now,  # UTC < UTC
            Task.status.in_(['PENDING', 'IN_PROGRESS'])
        ).order_by(Task.due_date.asc()).all()

        tasks_data = []
        for task in overdue_tasks:
            try:
                creator_name = task.creator.full_name if task.creator else 'Không rõ'

                # ✅ CONVERT UTC SANG VN TIMEZONE
                due_date_vn = utc_to_vn(task.due_date)

                priority_label = []
                if task.is_urgent:
                    priority_label.append('Khẩn cấp')
                if task.is_important:
                    priority_label.append('Quan trọng')
                if task.is_recurring:
                    priority_label.append('Lặp lại')

                priority_display = ', '.join(priority_label) if priority_label else 'Bình thường'

                tasks_data.append({
                    'id': task.id,
                    'title': task.title,
                    'due_date': due_date_vn.strftime('%d/%m/%Y %H:%M'),  # ✅ FORMAT THEO GIỜ VN
                    'status': task.status,
                    'creator': creator_name,
                    'priority': priority_display,
                    'is_urgent': task.is_urgent,
                    'is_important': task.is_important,
                    'is_recurring': task.is_recurring
                })
            except Exception as e:
                print(f"Error processing task {task.id}: {str(e)}")
                continue

        return jsonify({'tasks': tasks_data, 'count': len(tasks_data)})

    except Exception as e:
        print(f"Error in get_my_overdue_tasks: {str(e)}")
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500


# ========================================
#  LẤY CÔNG VIỆC QUÁ HẠN TEAM (Director/Manager)
# ========================================
@bp.route('/api/overdue-tasks')
@login_required
def get_overdue_tasks():
    """API: Lấy danh sách công việc quá hạn (cho Director/Manager)"""
    if current_user.role not in ['director', 'manager']:
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        now = datetime.utcnow()  # ✅ SỬ DỤNG UTC
        overdue_tasks = Task.query.filter(
            Task.due_date < now,  # UTC < UTC
            Task.status.in_(['PENDING', 'IN_PROGRESS'])
        ).order_by(Task.due_date.asc()).limit(20).all()

        tasks_data = []
        for task in overdue_tasks:
            try:
                # Lấy người được giao - XỬ LÝ AN TOÀN
                assignments = TaskAssignment.query.filter_by(
                    task_id=task.id,
                    accepted=True
                ).all()

                assignees = []
                for a in assignments:
                    if a.user:  # Kiểm tra user còn tồn tại
                        assignees.append(a.user.full_name)

                creator_name = task.creator.full_name if task.creator else 'Không rõ'

                # ✅ CONVERT UTC SANG VN TIMEZONE
                due_date_vn = utc_to_vn(task.due_date)

                priority_label = []
                if task.is_urgent:
                    priority_label.append('Khẩn cấp')
                if task.is_important:
                    priority_label.append('Quan trọng')
                if task.is_recurring:
                    priority_label.append('Lặp lại')

                priority_display = ', '.join(priority_label) if priority_label else 'Bình thường'

                tasks_data.append({
                    'id': task.id,
                    'title': task.title,
                    'due_date': due_date_vn.strftime('%d/%m/%Y %H:%M'),  # ✅ FORMAT THEO GIỜ VN
                    'status': task.status,
                    'assignees': ', '.join(assignees) if assignees else 'Chưa giao',
                    'creator': creator_name,
                    'priority': priority_display,
                    'is_urgent': task.is_urgent,
                    'is_important': task.is_important,
                    'is_recurring': task.is_recurring
                })
            except Exception as e:
                print(f"Error processing task {task.id}: {str(e)}")
                continue

        return jsonify({'tasks': tasks_data, 'count': len(tasks_data)})

    except Exception as e:
        print(f"Error in get_overdue_tasks: {str(e)}")
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500


@bp.route('/api/unrated-tasks')
@login_required
def get_unrated_tasks():
    """API: Lấy danh sách công việc cần đánh giá (cho Director/Manager)"""
    if current_user.role not in ['director', 'manager']:
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        #  LẤY TẤT CẢ TASK ĐÃ HOÀN THÀNH NHƯNG CHƯA ĐÁNH GIÁ
        unrated_tasks = Task.query.filter(
            Task.status == 'DONE',
            Task.performance_rating == None
        ).order_by(Task.updated_at.desc()).limit(20).all()

        tasks_data = []
        for task in unrated_tasks:
            try:
                # Lấy người thực hiện - XỬ LÝ AN TOÀN
                assignments = TaskAssignment.query.filter_by(
                    task_id=task.id,
                    accepted=True
                ).all()

                assignees = []
                for a in assignments:
                    if a.user:
                        assignees.append(a.user.full_name)

                creator_name = task.creator.full_name if task.creator else 'Không rõ'

                # ✅ CONVERT UTC SANG VN TIMEZONE
                completed_at_vn = utc_to_vn(task.updated_at) if task.updated_at else None

                tasks_data.append({
                    'id': task.id,
                    'title': task.title,
                    'completed_at': completed_at_vn.strftime('%d/%m/%Y %H:%M') if completed_at_vn else 'N/A',
                    'assignees': ', '.join(assignees) if assignees else 'Không rõ',
                    'creator': creator_name
                })
            except Exception as e:
                print(f"Error processing task {task.id}: {str(e)}")
                continue

        return jsonify({'tasks': tasks_data, 'count': len(tasks_data)})

    except Exception as e:
        print(f"Error in get_unrated_tasks: {str(e)}")
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500

# ========================================
# API: CÔNG VIỆC CHƯA LÀM CỦA TÔI
# ========================================
@bp.route('/api/my-pending-tasks-detail')
@login_required
def get_my_pending_tasks_detail():
    """API: Lấy danh sách công việc chưa làm của chính mình"""
    try:
        # Lấy danh sách task IDs của user
        my_assignments = TaskAssignment.query.filter_by(
            user_id=current_user.id,
            accepted=True
        ).all()
        my_task_ids = [a.task_id for a in my_assignments]

        # Query các task chưa làm
        pending_tasks = Task.query.filter(
            Task.id.in_(my_task_ids),
            Task.status == 'PENDING'
        ).order_by(Task.created_at.desc()).all()

        tasks_data = []
        for task in pending_tasks:
            try:
                creator_name = task.creator.full_name if task.creator else 'Không rõ'

                # ✅ CONVERT UTC SANG VN TIMEZONE
                due_date_vn = utc_to_vn(task.due_date) if task.due_date else None
                created_at_vn = utc_to_vn(task.created_at) if task.created_at else None

                priority_label = []
                if task.is_urgent:
                    priority_label.append('Khẩn cấp')
                if task.is_important:
                    priority_label.append('Quan trọng')
                if task.is_recurring:
                    priority_label.append('Lặp lại')

                priority_display = ', '.join(priority_label) if priority_label else 'Bình thường'

                tasks_data.append({
                    'id': task.id,
                    'title': task.title,
                    'due_date': due_date_vn.strftime('%d/%m/%Y %H:%M') if due_date_vn else 'Không có',
                    'created_at': created_at_vn.strftime('%d/%m/%Y %H:%M') if created_at_vn else 'N/A',
                    'creator': creator_name,
                    'priority': priority_display,
                    'is_urgent': task.is_urgent,
                    'is_important': task.is_important,
                    'is_recurring': task.is_recurring
                })
            except Exception as e:
                print(f"Error processing task {task.id}: {str(e)}")
                continue

        return jsonify({'tasks': tasks_data, 'count': len(tasks_data)})

    except Exception as e:
        print(f"Error in get_my_pending_tasks_detail: {str(e)}")
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500


# ========================================
# API: CÔNG VIỆC ĐANG LÀM CỦA TÔI
# ========================================
@bp.route('/api/my-inprogress-tasks-detail')
@login_required
def get_my_inprogress_tasks_detail():
    """API: Lấy danh sách công việc đang làm của chính mình"""
    try:
        # Lấy danh sách task IDs của user
        my_assignments = TaskAssignment.query.filter_by(
            user_id=current_user.id,
            accepted=True
        ).all()
        my_task_ids = [a.task_id for a in my_assignments]

        # Query các task đang làm
        inprogress_tasks = Task.query.filter(
            Task.id.in_(my_task_ids),
            Task.status == 'IN_PROGRESS'
        ).order_by(Task.updated_at.desc()).all()

        tasks_data = []
        for task in inprogress_tasks:
            try:
                creator_name = task.creator.full_name if task.creator else 'Không rõ'

                # ✅ CONVERT UTC SANG VN TIMEZONE
                due_date_vn = utc_to_vn(task.due_date) if task.due_date else None
                updated_at_vn = utc_to_vn(task.updated_at) if task.updated_at else None

                priority_label = []
                if task.is_urgent:
                    priority_label.append('Khẩn cấp')
                if task.is_important:
                    priority_label.append('Quan trọng')
                if task.is_recurring:
                    priority_label.append('Lặp lại')

                priority_display = ', '.join(priority_label) if priority_label else 'Bình thường'

                tasks_data.append({
                    'id': task.id,
                    'title': task.title,
                    'due_date': due_date_vn.strftime('%d/%m/%Y %H:%M') if due_date_vn else 'Không có',
                    'updated_at': updated_at_vn.strftime('%d/%m/%Y %H:%M') if updated_at_vn else 'N/A',
                    'creator': creator_name,
                    'priority': priority_display,
                    'is_urgent': task.is_urgent,
                    'is_important': task.is_important,
                    'is_recurring': task.is_recurring
                })
            except Exception as e:
                print(f"Error processing task {task.id}: {str(e)}")
                continue

        return jsonify({'tasks': tasks_data, 'count': len(tasks_data)})

    except Exception as e:
        print(f"Error in get_my_inprogress_tasks_detail: {str(e)}")
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500

# ========================================
# API: CÔNG VIỆC CHƯA LÀM TEAM (Director/Manager)
# ========================================
@bp.route('/api/team-pending-tasks')
@login_required
def get_team_pending_tasks():
    """API: Lấy danh sách công việc chưa làm của toàn team (cho Director/Manager)"""
    if current_user.role not in ['director', 'manager']:
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        # Query các task chưa làm trong hệ thống
        pending_tasks = Task.query.filter_by(
            status='PENDING'
        ).order_by(Task.created_at.desc()).all()

        tasks_data = []
        for task in pending_tasks:
            try:
                # Lấy người được giao - XỬ LÝ AN TOÀN
                assignments = TaskAssignment.query.filter_by(
                    task_id=task.id,
                    accepted=True
                ).all()

                assignees = []
                for a in assignments:
                    if a.user:  # Kiểm tra user còn tồn tại
                        assignees.append(a.user.full_name)

                creator_name = task.creator.full_name if task.creator else 'Không rõ'

                # ✅ CONVERT UTC SANG VN TIMEZONE
                due_date_vn = utc_to_vn(task.due_date) if task.due_date else None
                created_at_vn = utc_to_vn(task.created_at) if task.created_at else None

                priority_label = []
                if task.is_urgent:
                    priority_label.append('Khẩn cấp')
                if task.is_important:
                    priority_label.append('Quan trọng')
                if task.is_recurring:
                    priority_label.append('Lặp lại')

                priority_display = ', '.join(priority_label) if priority_label else 'Bình thường'

                tasks_data.append({
                    'id': task.id,
                    'title': task.title,
                    'due_date': due_date_vn.strftime('%d/%m/%Y %H:%M') if due_date_vn else 'Không có',
                    'created_at': created_at_vn.strftime('%d/%m/%Y %H:%M') if created_at_vn else 'N/A',
                    'assignees': ', '.join(assignees) if assignees else 'Chưa giao',
                    'creator': creator_name,
                    'priority': priority_display,
                    'is_urgent': task.is_urgent,
                    'is_important': task.is_important,
                    'is_recurring': task.is_recurring
                })
            except Exception as e:
                print(f"Error processing task {task.id}: {str(e)}")
                continue

        return jsonify({'tasks': tasks_data, 'count': len(tasks_data)})

    except Exception as e:
        print(f"Error in get_team_pending_tasks: {str(e)}")
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500