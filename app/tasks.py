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

        # ===== THÔNG BÁO THÔNG MINH =====
        # Tính toán hiệu suất
        completion_rate = (done / total_tasks * 100) if total_tasks > 0 else 0
        overdue_rate = (overdue_count / total_tasks * 100) if total_tasks > 0 else 0

        # Đếm nhiệm vụ chưa đánh giá (DONE nhưng chưa rate)
        unrated_tasks = stats_query.filter_by(status='DONE', performance_rating=None).count()

        # Tính nhiệm vụ hoàn thành quá hạn
        done_overdue_count = stats_query.filter_by(status='DONE', completed_overdue=True).count()

        # Tính nhiệm vụ bị đánh giá kém
        bad_rating_count = stats_query.filter_by(status='DONE', performance_rating='bad').count()
        good_rating_count = stats_query.filter_by(status='DONE', performance_rating='good').count()

        # Quality Score: % nhiệm vụ hoàn thành ĐÚNG HẠN và KHÔNG BỊ ĐÁNH GIÁ KÉM
        quality_done = done - done_overdue_count - bad_rating_count
        on_time_rate = (quality_done / done * 100) if done > 0 else 0

        # Rating rate: % đã được đánh giá trong số đã hoàn thành
        rated_count = good_rating_count + bad_rating_count
        rating_rate = (rated_count / done * 100) if done > 0 else 0

        # Logic thông báo cho DIRECTOR
        if current_user.role == 'director':
            # ĐIỀU KIỆN 1: KHẨN CẤP - Quá nhiều quá hạn hoặc chất lượng quá thấp
            if overdue_rate >= 30 or (done > 0 and on_time_rate < 30):
                notification = {
                    'type': 'danger',
                    'icon': 'bi-exclamation-triangle-fill',
                    'title': 'KHẨN CẤP - Cần Can Thiệp Ngay!',
                    'message': f'Có {overdue_count} quá hạn ({overdue_rate:.0f}%), {bad_rating_count} đánh giá kém. Chất lượng công việc đang sụt giảm nghiêm trọng!',
                    'stats': {
                        'completion': completion_rate,
                        'overdue': overdue_count,
                        'unrated': unrated_tasks,
                        'on_time_rate': on_time_rate,
                        'bad_rating': bad_rating_count,
                        'done_overdue': done_overdue_count
                    }
                }
            # ĐIỀU KIỆN 2: CẢNH BÁO - Nhiều task quá hạn hoặc chưa đánh giá
            elif overdue_count >= 10 or unrated_tasks >= 10 or bad_rating_count >= 5:
                notification = {
                    'type': 'warning',
                    'icon': 'bi-exclamation-circle-fill',
                    'title': 'Cảnh Báo - Cần Giám Sát',
                    'message': f'Có {overdue_count} quá hạn, {unrated_tasks} chưa đánh giá, {bad_rating_count} đánh giá kém. Đội Ngũ đang gặp khó khăn!',
                    'stats': {
                        'completion': completion_rate,
                        'overdue': overdue_count,
                        'unrated': unrated_tasks,
                        'on_time_rate': on_time_rate,
                        'bad_rating': bad_rating_count
                    }
                }
            # ĐIỀU KIỆN 3: XUẤT SẮC - Hoàn thành cao + chất lượng cao + ít quá hạn
            elif completion_rate >= 70 and on_time_rate >= 70 and overdue_count <= 3:
                notification = {
                    'type': 'success',
                    'icon': 'bi-trophy-fill',
                    'title': 'Hoạt Động Xuất Sắc!',
                    'message': f'Tuyệt vời! {done}/{total_tasks} hoàn thành ({completion_rate:.0f}%), {on_time_rate:.0f}% đúng hạn. Đội Ngũ đang làm việc hiệu quả!',
                    'stats': {
                        'completion': completion_rate,
                        'overdue': overdue_count,
                        'unrated': unrated_tasks,
                        'on_time_rate': on_time_rate,
                        'good_rating': good_rating_count
                    }
                }
            # ĐIỀU KIỆN 4: TỐT - Hoàn thành khá, chất lượng ổn
            elif completion_rate >= 50 and on_time_rate >= 50:
                notification = {
                    'type': 'info',
                    'icon': 'bi-graph-up-arrow',
                    'title': 'Hoạt Động Tốt',
                    'message': f'{done}/{total_tasks} hoàn thành ({completion_rate:.0f}%), {on_time_rate:.0f}% đúng hạn. Có {unrated_tasks} cần đánh giá.',
                    'stats': {
                        'completion': completion_rate,
                        'overdue': overdue_count,
                        'unrated': unrated_tasks,
                        'on_time_rate': on_time_rate
                    }
                }
            # ĐIỀU KIỆN 5: DEFAULT
            else:
                notification = {
                    'type': 'info',
                    'icon': 'bi-clipboard-data',
                    'title': 'Giám Sát Tiến Độ',
                    'message': f'{done}/{total_tasks} hoàn thành ({completion_rate:.0f}%). Có {overdue_count} quá hạn, {unrated_tasks} chưa đánh giá.',
                    'stats': {
                        'completion': completion_rate,
                        'overdue': overdue_count,
                        'unrated': unrated_tasks,
                        'on_time_rate': on_time_rate
                    }
                }

        # Logic thông báo cho MANAGER
        else:  # manager
            # ĐIỀU KIỆN 1: KHẨN CẤP - Đội Ngũ có vấn đề nghiêm trọng
            if overdue_count >= 15 or (done > 0 and on_time_rate < 40):
                notification = {
                    'type': 'danger',
                    'icon': 'bi-exclamation-triangle-fill',
                    'title': 'Khẩn Cấp - Cần Hỗ Trợ Ngay!',
                    'message': f'Có {overdue_count} quá hạn, {bad_rating_count} đánh giá kém. Chất lượng: {on_time_rate:.0f}%. Cần can thiệp!',
                    'stats': {
                        'completion': completion_rate,
                        'overdue': overdue_count,
                        'unrated': unrated_tasks,
                        'team_done': done,
                        'on_time_rate': on_time_rate,
                        'bad_rating': bad_rating_count
                    }
                }
            # ĐIỀU KIỆN 2: CẢNH BÁO - Nhiều task cần xử lý
            elif overdue_count >= 8 or unrated_tasks >= 8 or bad_rating_count >= 4:
                notification = {
                    'type': 'warning',
                    'icon': 'bi-exclamation-circle-fill',
                    'title': 'Cảnh Báo - Cần Theo Dõi Sát',
                    'message': f'Có {overdue_count} quá hạn, {unrated_tasks} chưa đánh giá, {bad_rating_count} đánh giá kém. Hãy hỗ trợ nhân viên!',
                    'stats': {
                        'completion': completion_rate,
                        'overdue': overdue_count,
                        'unrated': unrated_tasks,
                        'team_done': done,
                        'bad_rating': bad_rating_count
                    }
                }
            # ĐIỀU KIỆN 3: XUẤT SẮC - Đội Ngũ làm việc tốt
            elif completion_rate >= 65 and on_time_rate >= 65 and overdue_count <= 3:
                notification = {
                    'type': 'success',
                    'icon': 'bi-emoji-smile-fill',
                    'title': 'Hoạt Động Xuất Sắc!',
                    'message': f'Tuyệt vời! Có {done}/{total_tasks} hoàn thành ({completion_rate:.0f}%), {on_time_rate:.0f}% đúng hạn!',
                    'stats': {
                        'completion': completion_rate,
                        'overdue': overdue_count,
                        'unrated': unrated_tasks,
                        'team_done': done,
                        'on_time_rate': on_time_rate,
                        'good_rating': good_rating_count
                    }
                }
            # ĐIỀU KIỆN 4: TỐT
            elif completion_rate >= 50 and on_time_rate >= 50:
                notification = {
                    'type': 'info',
                    'icon': 'bi-clipboard-check',
                    'title': 'Hoạt Động Tốt',
                    'message': f'Có {done}/{total_tasks} hoàn thành ({completion_rate:.0f}%), {on_time_rate:.0f}% đúng hạn. {unrated_tasks} cần đánh giá.',
                    'stats': {
                        'completion': completion_rate,
                        'overdue': overdue_count,
                        'unrated': unrated_tasks,
                        'team_done': done,
                        'on_time_rate': on_time_rate
                    }
                }
            # ĐIỀU KIỆN 5: DEFAULT
            else:
                notification = {
                    'type': 'info',
                    'icon': 'bi-clipboard-data',
                    'title': 'Quản Lý',
                    'message': f'Có {done}/{total_tasks} hoàn thành ({completion_rate:.0f}%). {unrated_tasks} cần đánh giá, {overdue_count} quá hạn.',
                    'stats': {
                        'completion': completion_rate,
                        'overdue': overdue_count,
                        'unrated': unrated_tasks,
                        'team_done': done
                    }
                }

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
                               notification=notification,
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

        # ===== THÔNG BÁO THÔNG MINH CHO HR/ACCOUNTANT =====
        completion_rate = (done / total_tasks * 100) if total_tasks > 0 else 0
        active_tasks = pending + in_progress

        # Tính nhiệm vụ hoàn thành quá hạn
        done_overdue_count = my_tasks_query.filter_by(status='DONE', completed_overdue=True).count()

        # Tính nhiệm vụ bị đánh giá kém
        bad_rating_count = my_tasks_query.filter_by(status='DONE', performance_rating='bad').count()

        # Tính điểm chất lượng (Quality Score)
        good_rating_count = my_tasks_query.filter_by(status='DONE', performance_rating='good').count()
        on_time_done = done - done_overdue_count

        # Quality rate: % nhiệm vụ hoàn thành ĐÚNG HẠN và KHÔNG BỊ ĐÁNH GIÁ KÉM
        quality_done = done - done_overdue_count - bad_rating_count
        quality_rate = (quality_done / done * 100) if done > 0 else 0

        # LOGIC MỚI - ƯU TIÊN CHẤT LƯỢNG
        if total_tasks == 0:
            notification = {
                'type': 'secondary',
                'icon': 'bi-inbox',
                'title': 'Chưa Có Nhiệm Vụ',
                'message': 'Bạn chưa có nhiệm vụ nào. Hãy liên hệ Giám đốc/Trưởng phòng để nhận công việc.',
                'stats': {
                    'completion': 0,
                    'overdue': 0,
                    'active': 0
                }
            }
        # ĐIỀU KIỆN 1: Có quá nhiều quá hạn hoặc đánh giá kém
        elif overdue_count >= 5 or bad_rating_count >= 3:
            notification = {
                'type': 'danger',
                'icon': 'bi-exclamation-triangle-fill',
                'title': 'Báo Động - Hiệu Suất Kém!',
                'message': f'Bạn có {overdue_count} quá hạn, {bad_rating_count} bị đánh giá kém. Cần cải thiện ngay!',
                'stats': {
                    'completion': completion_rate,
                    'overdue': overdue_count,
                    'active': active_tasks,
                    'done_overdue': done_overdue_count,
                    'bad_rating': bad_rating_count
                }
            }
        # ĐIỀU KIỆN 2: Hoàn thành nhiều nhưng chất lượng thấp
        elif completion_rate >= 70 and (done_overdue_count >= 2 or bad_rating_count >= 2):
            notification = {
                'type': 'warning',
                'icon': 'bi-exclamation-circle-fill',
                'title': 'Cần Cải Thiện Chất Lượng',
                'message': f'Bạn hoàn thành {done}/{total_tasks} nhiệm vụ nhưng có {done_overdue_count} quá hạn và {bad_rating_count} đánh giá kém. Hãy chú ý!',
                'stats': {
                    'completion': completion_rate,
                    'overdue': overdue_count,
                    'active': active_tasks,
                    'done_overdue': done_overdue_count,
                    'bad_rating': bad_rating_count,
                    'quality': quality_rate
                }
            }

        # ĐIỀU KIỆN 3: Có task quá hạn đang chờ
        elif overdue_count >= 3 or (overdue_count >= 1 and completion_rate < 50):
            notification = {
                'type': 'warning',
                'icon': 'bi-clock-fill',
                'title': 'Cần Cố Gắng Hơn',
                'message': f'Bạn có {overdue_count} quá hạn, {pending} chưa làm và {in_progress} đang làm. Hãy tập trung!',
                'stats': {
                    'completion': completion_rate,
                    'overdue': overdue_count,
                    'active': active_tasks,
                    'done_overdue': done_overdue_count
                }
            }
        # ĐIỀU KIỆN 4: XUẤT SẮC - Hoàn thành cao + chất lượng cao
        elif completion_rate >= 80 and quality_rate >= 70 and overdue_count == 0:
            notification = {
                'type': 'success',
                'icon': 'bi-trophy-fill',
                'title': 'Xuất Sắc!',
                'message': f'Tuyệt vời! Bạn đã hoàn thành {done}/{total_tasks} nhiệm vụ ({completion_rate:.0f}%) với chất lượng cao ({quality_rate:.0f}% đúng hạn)! Tiếp tục phát huy!',
                'stats': {
                    'completion': completion_rate,
                    'overdue': overdue_count,
                    'active': active_tasks,
                    'done_overdue': done_overdue_count,
                    'quality': quality_rate,
                    'good_rating': good_rating_count
                }
            }
        # ĐIỀU KIỆN 5: Làm tốt - hoàn thành khá + chất lượng tốt
        elif completion_rate >= 50 and quality_rate >= 60:
            notification = {
                'type': 'info',
                'icon': 'bi-hand-thumbs-up-fill',
                'title': 'Làm Tốt Lắm!',
                'message': f'Bạn đã hoàn thành {done}/{total_tasks} nhiệm vụ ({completion_rate:.0f}%). Còn {active_tasks} đang chờ.',
                'stats': {
                    'completion': completion_rate,
                    'overdue': overdue_count,
                    'active': active_tasks,
                    'done_overdue': done_overdue_count,
                    'quality': quality_rate
                }
            }
        # ĐIỀU KIỆN 6: Default
        else:
            notification = {
                'type': 'info',
                'icon': 'bi-clipboard-data',
                'title': 'Theo Dõi Tiến Độ',
                'message': f'Bạn có {active_tasks} nhiệm vụ đang xử lý. Hãy hoàn thành đúng hạn để đạt hiệu suất cao!',
                'stats': {
                    'completion': completion_rate,
                    'overdue': overdue_count,
                    'active': active_tasks,
                    'done_overdue': done_overdue_count
                }
            }

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
                               date_to=date_to,
                               notification=notification)


# Route để xem chi tiết tasks theo status
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
        'PENDING': 'Chưa Làm',
        'IN_PROGRESS': 'Đang Làm',
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
            is_urgent=is_urgent,
            is_important=is_important,
            is_recurring=is_recurring
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
                title='✅ Giám đốc đã hoàn thành nhiệm vụ',
                body=f'Giám đốc {current_user.full_name} đã hoàn thành nhiệm vụ "{task.title}" (Tự động đánh giá: TỐT)',
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