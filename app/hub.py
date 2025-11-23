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

    now = datetime.utcnow()  # SỬ DỤNG UTC ĐỂ SO SÁNH VỚI DATABASE

    # ========================================
    # CÔNG VIỆC HÀNG NGÀY (Cho tất cả roles)
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

    # Công việc sắp đến hạn (trong vòng 3 ngày)
    three_days_later = now + timedelta(days=3)
    my_due_soon = Task.query.filter(
        Task.id.in_(my_task_ids),
        Task.due_date >= now,
        Task.due_date <= three_days_later,
        Task.status.in_(['PENDING', 'IN_PROGRESS'])
    ).count()

    # Công việc quá hạn của tôi
    my_overdue = Task.query.filter(
        Task.id.in_(my_task_ids),
        Task.due_date < now,
        Task.status.in_(['PENDING', 'IN_PROGRESS'])
    ).count()

    # Công việc đã hoàn thành
    my_completed_recent = Task.query.filter(
        Task.id.in_(my_task_ids),
        Task.status == 'DONE'
    ).count()

    # ========================================
    # TÍNH TOÁN METRICS CHO THÔNG BÁO CÁ NHÂN
    # ========================================
    total_my_tasks = len(my_task_ids)

    # Completion rate
    my_completion_rate = (my_completed_recent / total_my_tasks * 100) if total_my_tasks > 0 else 0

    # Số công việc hoàn thành nhưng quá hạn
    my_done_overdue_count = Task.query.filter(
        Task.id.in_(my_task_ids),
        Task.status == 'DONE',
        Task.completed_overdue == True
    ).count()

    # Số công việc bị đánh giá kém
    my_bad_rating_count = Task.query.filter(
        Task.id.in_(my_task_ids),
        Task.status == 'DONE',
        Task.performance_rating == 'bad'
    ).count()

    # Số công việc được đánh giá tốt
    my_good_rating_count = Task.query.filter(
        Task.id.in_(my_task_ids),
        Task.status == 'DONE',
        Task.performance_rating == 'good'
    ).count()

    # Quality rate: % hoàn thành đúng hạn + không bị đánh giá kém
    quality_done = my_completed_recent - my_done_overdue_count - my_bad_rating_count
    my_quality_rate = (quality_done / my_completed_recent * 100) if my_completed_recent > 0 else 0

    # ========================================
    # LOGIC THÔNG BÁO CÁ NHÂN
    # ========================================
    personal_notification = None

    if total_my_tasks == 0:
        # Chưa có công việc
        personal_notification = {
            'type': 'secondary',
            'icon': 'bi-inbox',
            'title': 'Chưa Có Nhiệm Vụ',
            'message': 'Bạn chưa có nhiệm vụ nào. Hãy liên hệ Giám đốc/Trưởng phòng để nhận công việc.',
            'stats': {
                'total': 0,
                'completed': 0,
                'overdue': 0
            }
        }
    elif my_overdue >= 5 or my_bad_rating_count >= 3 or (my_overdue >= 3 and my_completion_rate < 30):
        # KHẨN CẤP
        personal_notification = {
            'type': 'danger',
            'icon': 'bi-exclamation-triangle-fill',
            'title': '🚨 KHẨN CẤP ',
            'message': f'Bạn có <strong>{my_overdue} công việc quá hạn</strong>, <strong>{my_bad_rating_count} việc bị đánh giá kém</strong>. Hãy ưu tiên xử lý các công việc này ngay!',
            'stats': {
                'total': total_my_tasks,
                'completed': my_completed_recent,
                'overdue': my_overdue,
                'bad_rating': my_bad_rating_count,
                'completion_rate': my_completion_rate
            }
        }
    elif my_overdue >= 3 or my_due_soon >= 5 or (my_done_overdue_count >= 3 and my_completion_rate >= 50):
        # CẢNH BÁO
        personal_notification = {
            'type': 'warning',
            'icon': 'bi-exclamation-circle-fill',
            'title': '⚠️ Chú Ý ',
            'message': f'Bạn có <strong>{my_overdue} việc quá hạn</strong>, <strong>{my_due_soon} việc sắp đến hạn</strong> trong 3 ngày tới và <strong>{my_done_overdue_count} nhiệm vụ hoàn thành nhưng bị quá hạn!</strong> CẦN TẬP TRUNG ',
            'stats': {
                'total': total_my_tasks,
                'completed': my_completed_recent,
                'overdue': my_overdue,
                'due_soon': my_due_soon,
                'completion_rate': my_completion_rate
            }
        }
    elif my_completion_rate >= 80 and my_quality_rate >= 70 and my_overdue == 0:
        # XUẤT SẮC
        personal_notification = {
            'type': 'success',
            'icon': 'bi-trophy-fill',
            'title': '🏆 Xuất Sắc - Tiếp Tục Phát Huy!',
            'message': f'Tuyệt vời! Bạn đã hoàn thành <strong>{my_completed_recent}/{total_my_tasks} việc ({my_completion_rate:.0f}%)</strong>, <strong>{my_quality_rate:.0f}%</strong> đúng hạn với chất lượng tốt. Tiếp tục duy trì nhé!',
            'stats': {
                'total': total_my_tasks,
                'completed': my_completed_recent,
                'overdue': my_overdue,
                'quality_rate': my_quality_rate,
                'good_rating': my_good_rating_count,
                'completion_rate': my_completion_rate
            }
        }
    elif my_completion_rate >= 50 and my_quality_rate >= 60:
        # TỐT
        personal_notification = {
            'type': 'info',
            'icon': 'bi-hand-thumbs-up-fill',
            'title': '👍 Làm Tốt ',
            'message': f'Bạn đã hoàn thành <strong>{my_completed_recent}/{total_my_tasks} việc ({my_completion_rate:.0f}%)</strong>, <strong>{my_quality_rate:.0f}%</strong> đúng hạn. Còn <strong>{my_pending_tasks} việc chưa làm</strong>, <strong>{my_in_progress} việc đang làm</strong>. Cố gắng thêm!',
            'stats': {
                'total': total_my_tasks,
                'completed': my_completed_recent,
                'pending': my_pending_tasks,
                'in_progress': my_in_progress,
                'overdue': my_overdue,
                'quality_rate': my_quality_rate,
                'completion_rate': my_completion_rate
            }
        }
    else:
        # BÌNH THƯỜNG
        personal_notification = {
            'type': 'secondary',
            'icon': 'bi-clipboard-data',
            'title': '📊 Theo Dõi Tiến Độ',
            'message': f'Bạn có <strong>{my_in_progress} việc đang làm</strong>, <strong>{my_pending_tasks} việc chưa làm</strong>, <strong>{my_overdue} việc quá hạn</strong>. Hãy hoàn thành đúng hạn để đạt hiệu suất cao!',
            'stats': {
                'total': total_my_tasks,
                'completed': my_completed_recent,
                'pending': my_pending_tasks,
                'in_progress': my_in_progress,
                'overdue': my_overdue,
                'completion_rate': my_completion_rate
            }
        }

    # ========================================
    # QUẢN LÝ CÔNG VIỆC (Director/Manager)
    # ========================================
    total_tasks = 0
    tasks_need_rating = 0
    my_tasks_need_rating = 0
    team_overdue = 0
    team_pending = 0
    company_notification = None

    if current_user.role in ['director', 'manager']:
        # Tổng công việc trong hệ thống
        total_tasks = Task.query.count()

        # Tasks cần đánh giá
        tasks_need_rating = Task.query.filter(
            Task.status == 'DONE',
            Task.performance_rating == None
        ).count()

        # Tasks do MÌNH giao cần đánh giá
        my_tasks_need_rating = Task.query.filter(
            Task.creator_id == current_user.id,
            Task.status == 'DONE',
            Task.performance_rating == None
        ).count()

        # Công việc quá hạn (toàn hệ thống)
        team_overdue = Task.query.filter(
            Task.due_date < now,
            Task.status.in_(['PENDING', 'IN_PROGRESS'])
        ).count()

        # Công việc chờ xử lý (toàn hệ thống)
        team_pending = Task.query.filter_by(status='PENDING').count()

        # Công việc đang làm
        team_in_progress = Task.query.filter_by(status='IN_PROGRESS').count()

        # Công việc đã hoàn thành
        team_completed = Task.query.filter_by(status='DONE').count()

        # ========================================
        # TÍNH TOÁN METRICS CHỈ CHO DIRECTOR
        # ========================================
        if current_user.role == 'director':
            # Completion rate
            company_completion_rate = (team_completed / total_tasks * 100) if total_tasks > 0 else 0

            # Overdue rate
            company_overdue_rate = (team_overdue / total_tasks * 100) if total_tasks > 0 else 0

            # Số công việc hoàn thành nhưng quá hạn
            company_done_overdue = Task.query.filter_by(
                status='DONE',
                completed_overdue=True
            ).count()

            # Số công việc bị đánh giá kém
            company_bad_rating = Task.query.filter_by(
                status='DONE',
                performance_rating='bad'
            ).count()

            # Số công việc được đánh giá tốt
            company_good_rating = Task.query.filter_by(
                status='DONE',
                performance_rating='good'
            ).count()

            # On-time rate: % hoàn thành đúng hạn + không bị đánh giá kém
            quality_completed = team_completed - company_done_overdue - company_bad_rating
            company_on_time_rate = (quality_completed / team_completed * 100) if team_completed > 0 else 0

            # ========================================
            # LOGIC THÔNG BÁO CÔNG TY (CHỈ DIRECTOR)
            # ========================================
            if total_tasks == 0:
                company_notification = {
                    'type': 'secondary',
                    'icon': 'bi-building',
                    'title': 'Chưa Có Dữ Liệu',
                    'message': 'Công ty chưa có công việc nào trong hệ thống.',
                    'stats': {}
                }
            elif company_overdue_rate >= 30 or company_on_time_rate < 30 or company_bad_rating >= 10:
                # KHẨN CẤP
                company_notification = {
                    'type': 'danger',
                    'icon': 'bi-exclamation-triangle-fill',
                    'title': '🚨 KHẨN CẤP - Cần Can Thiệp Ngay!',
                    'message': f'Công ty có <strong>{team_overdue} việc quá hạn ({company_overdue_rate:.0f}%)</strong>, <strong>{company_bad_rating} việc đánh giá kém</strong>. Chất lượng đang sụt giảm nghiêm trọng. Cần họp khẩn với các phòng ban!',
                    'stats': {
                        'total': total_tasks,
                        'completed': team_completed,
                        'overdue': team_overdue,
                        'overdue_rate': company_overdue_rate,
                        'bad_rating': company_bad_rating,
                        'on_time_rate': company_on_time_rate,
                        'completion_rate': company_completion_rate
                    }
                }
            elif team_overdue >= 15 or tasks_need_rating >= 15 or company_bad_rating >= 5 or company_overdue_rate >= 20:
                # CẢNH BÁO
                company_notification = {
                    'type': 'warning',
                    'icon': 'bi-exclamation-circle-fill',
                    'title': '⚠️ Cảnh Báo - Cần Giám Sát!',
                    'message': f'Có <strong>{team_overdue} việc quá hạn</strong>, <strong>{tasks_need_rating} việc cần đánh giá</strong>, <strong>{company_bad_rating} việc đánh giá kém</strong>. Một số bộ phận đang gặp khó khăn, cần họp với trưởng phòng!',
                    'stats': {
                        'total': total_tasks,
                        'completed': team_completed,
                        'overdue': team_overdue,
                        'need_rating': tasks_need_rating,
                        'bad_rating': company_bad_rating,
                        'overdue_rate': company_overdue_rate,
                        'completion_rate': company_completion_rate
                    }
                }
            elif company_completion_rate >= 70 and company_on_time_rate >= 70 and team_overdue <= 5:
                # XUẤT SẮC
                company_notification = {
                    'type': 'success',
                    'icon': 'bi-trophy-fill',
                    'title': '🏆 Xuất Sắc - Hoạt Động Rất Tốt!',
                    'message': f'Công ty hoàn thành <strong>{team_completed}/{total_tasks} việc ({company_completion_rate:.0f}%)</strong>, <strong>{company_on_time_rate:.0f}%</strong> đúng hạn với chất lượng cao. Toàn thể nhân viên đang làm việc hiệu quả!',
                    'stats': {
                        'total': total_tasks,
                        'completed': team_completed,
                        'overdue': team_overdue,
                        'on_time_rate': company_on_time_rate,
                        'good_rating': company_good_rating,
                        'completion_rate': company_completion_rate
                    }
                }
            elif company_completion_rate >= 50 and company_on_time_rate >= 50:
                # TỐT
                company_notification = {
                    'type': 'info',
                    'icon': 'bi-hand-thumbs-up-fill',
                    'title': '👍 Hoạt Động Tốt - Ổn Định',
                    'message': f'Công ty hoàn thành <strong>{team_completed}/{total_tasks} việc ({company_completion_rate:.0f}%)</strong>, <strong>{company_on_time_rate:.0f}%</strong> đúng hạn. Có <strong>{team_overdue} việc quá hạn</strong>, <strong>{tasks_need_rating} việc cần đánh giá</strong>.',
                    'stats': {
                        'total': total_tasks,
                        'completed': team_completed,
                        'overdue': team_overdue,
                        'need_rating': tasks_need_rating,
                        'on_time_rate': company_on_time_rate,
                        'completion_rate': company_completion_rate
                    }
                }
            else:
                # BÌNH THƯỜNG
                company_notification = {
                    'type': 'secondary',
                    'icon': 'bi-clipboard-data',
                    'title': '📊 Giám Sát Tiến Độ',
                    'message': f'Công ty có <strong>{team_completed}/{total_tasks} việc hoàn thành ({company_completion_rate:.0f}%)</strong>. Có <strong>{team_overdue} việc quá hạn</strong>, <strong>{tasks_need_rating} việc cần đánh giá</strong>. Tiếp tục theo dõi!',
                    'stats': {
                        'total': total_tasks,
                        'completed': team_completed,
                        'overdue': team_overdue,
                        'need_rating': tasks_need_rating,
                        'completion_rate': company_completion_rate
                    }
                }

    # ========================================
    # LƯƠNG & TÀI CHÍNH (Director/Accountant)
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
    # THÔNG BÁO NỘI BỘ
    # ========================================
    unread_notifications = Notification.query.filter_by(
        user_id=current_user.id,
        read=False
    ).count()

    unconfirmed_news = News.query.filter(
        ~News.confirmations.any(user_id=current_user.id)
    ).count()

    # ========================================
    # QUẢN TRỊ HỆ THỐNG (Director only)
    # ========================================
    total_users = 0
    active_users = 0

    if current_user.role == 'director':
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()

    # TÍNH BADGE
    my_work_badge = my_due_soon + my_overdue

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
                           # Thông báo cá nhân
                           personal_notification=personal_notification,
                           # Quản lý công việc
                           total_tasks=total_tasks,
                           tasks_need_rating=tasks_need_rating,
                           my_tasks_need_rating=my_tasks_need_rating,
                           team_overdue=team_overdue,
                           team_pending=team_pending,
                           # Thông báo công ty (chỉ Director)
                           company_notification=company_notification,
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


# ========================================
# API: REAL-TIME STATS (POLLING)
# ========================================
@bp.route('/api/realtime-stats')
@login_required
def get_realtime_stats():
    """API trả về stats real-time cho polling"""
    try:
        now = datetime.utcnow()

        # Lấy task IDs của user
        my_assignments = TaskAssignment.query.filter_by(
            user_id=current_user.id,
            accepted=True
        ).all()
        my_task_ids = [a.task_id for a in my_assignments]

        # Đếm các chỉ số cá nhân
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

        # Thông báo
        unread_notifications = Notification.query.filter_by(
            user_id=current_user.id,
            read=False
        ).count()

        unconfirmed_news = News.query.filter(
            ~News.confirmations.any(user_id=current_user.id)
        ).count()

        # Stats cho Director/Manager
        team_overdue = 0
        team_pending = 0
        tasks_need_rating = 0

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

        # Tính badges
        work_badge = my_overdue + my_due_soon
        info_badge = unconfirmed_news + unread_notifications

        # Stats cho Lương (Director/Accountant)
        pending_penalties = 0
        pending_advances = 0

        if current_user.role in ['director', 'accountant']:
            from app.models import Penalty, Advance
            pending_penalties = Penalty.query.filter_by(is_deducted=False).count()
            pending_advances = Advance.query.filter_by(is_deducted=False).count()

        salary_badge = pending_penalties + pending_advances

        return jsonify({
            # Công việc cá nhân
            'my_overdue': my_overdue,
            'my_due_soon': my_due_soon,
            'my_pending_tasks': my_pending_tasks,
            'my_in_progress': my_in_progress,

            # Thông báo
            'unread_notifications': unread_notifications,
            'unconfirmed_news': unconfirmed_news,

            # Stats team (Director/Manager)
            'team_overdue': team_overdue,
            'team_pending': team_pending,
            'tasks_need_rating': tasks_need_rating,

            # Stats lương
            'pending_penalties': pending_penalties,
            'pending_advances': pending_advances,

            # Badges
            'work_badge': work_badge,
            'info_badge': info_badge,
            'salary_badge': salary_badge,

            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        print(f"❌ Error in get_realtime_stats: {str(e)}")
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500