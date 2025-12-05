"""
Scheduler để tự động xóa link hết hạn
SỬA: Chỉ chạy trong 1 worker duy nhất để tránh duplicate jobs
"""

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import os


def cleanup_expired_links(app):
    """Tự động xóa các link đã hết hạn"""
    with app.app_context():
        from app import db
        from app.models import SalaryShareLink

        try:
            now = datetime.utcnow()

            # Xóa các link hết hạn
            deleted = SalaryShareLink.query.filter(
                SalaryShareLink.expires_at < now
            ).delete(synchronize_session=False)

            # Xóa luôn các link hết lượt xem
            links_out_of_views = SalaryShareLink.query.filter(
                SalaryShareLink.max_views.isnot(None),
                SalaryShareLink.view_count >= SalaryShareLink.max_views,
                SalaryShareLink.is_active == True
            ).all()

            deactivated = 0
            for link in links_out_of_views:
                db.session.delete(link)
                deactivated += 1

            db.session.commit()

            if deleted > 0 or deactivated > 0:
                print(f" [{datetime.now()}] Cleanup: Đã xóa {deleted} link hết hạn, {deactivated} link hết lượt xem")
            else:
                print(f" [{datetime.now()}] Cleanup: Không có link nào cần xóa")

        except Exception as e:
            print(f" [{datetime.now()}] Lỗi khi cleanup: {str(e)}")
            db.session.rollback()


def create_recurring_tasks(app):
    """
    Tự động tạo task lặp lại
    - Hỗ trợ 2 mode: 'interval' (theo khoảng cách) và 'weekly' (theo ngày trong tuần)
    - Chạy mỗi giờ để đảm bảo không bỏ sót
    """
    with app.app_context():
        from app import db
        from app.models import Task, TaskAssignment, User, Notification
        from datetime import datetime, timedelta
        from app.utils import vn_now, utc_to_vn, vn_to_utc

        try:
            # ===== LẤY THỜI GIAN HIỆN TẠI (GIỜ VN) =====
            now_utc = datetime.utcnow()
            now_vn = vn_now()  # Datetime object theo giờ VN
            today_vn_date = now_vn.date()
            today_weekday = now_vn.weekday()  # 0=Monday, 6=Sunday

            # ===== CHUYỂN ĐỔI WEEKDAY SANG FORMAT UI =====
            # Python: 0=Mon, 1=Tue, ..., 6=Sun
            # UI:     1=T2,  2=T3,  ..., 6=T7, 0=CN
            weekday_map = {
                0: '1',  # Monday    → Thứ 2
                1: '2',  # Tuesday   → Thứ 3
                2: '3',  # Wednesday → Thứ 4
                3: '4',  # Thursday  → Thứ 5
                4: '5',  # Friday    → Thứ 6
                5: '6',  # Saturday  → Thứ 7
                6: '0'  # Sunday    → Chủ nhật
            }
            today_weekday_str = weekday_map[today_weekday]

            # ===== TÌM TẤT CẢ TASK CÓ BẬT RECURRING =====
            recurring_tasks = Task.query.filter(
                Task.recurrence_enabled == True,
                Task.is_recurring == True,
                Task.last_recurrence_date.isnot(None)
            ).all()

            created_count = 0
            skipped_count = 0

            for original_task in recurring_tasks:
                should_create = False
                next_due_date = None

                # ===== CHUYỂN last_recurrence_date SANG GIỜ VN =====
                last_recurrence_vn = utc_to_vn(original_task.last_recurrence_date)
                last_recurrence_date = last_recurrence_vn.date()

                # ===== KIỂM TRA ĐÃ TẠO TASK HÔM NAY CHƯA =====
                if last_recurrence_date >= today_vn_date:
                    skipped_count += 1
                    continue  # Đã tạo task hôm nay rồi, bỏ qua

                # ===== MODE 1: INTERVAL (LOGIC CŨ) =====
                if original_task.recurrence_type == 'interval':
                    if not original_task.recurrence_interval_days:
                        continue

                    # Tính ngày tạo task tiếp theo
                    next_date_vn = last_recurrence_vn + timedelta(days=original_task.recurrence_interval_days)

                    # Nếu đã đến lúc tạo task mới
                    if now_vn >= next_date_vn:
                        should_create = True

                        # Tính due_date mới (nếu có)
                        if original_task.due_date:
                            original_due_vn = utc_to_vn(original_task.due_date)
                            time_diff = original_due_vn - last_recurrence_vn
                            next_due_date_vn = next_date_vn + time_diff
                            next_due_date = vn_to_utc(next_due_date_vn)

                # ===== MODE 2: WEEKLY (LOGIC MỚI) =====
                elif original_task.recurrence_type == 'weekly':
                    if not original_task.recurrence_weekdays:
                        continue

                    # Lấy danh sách ngày cần tạo task
                    weekdays_list = original_task.recurrence_weekdays.split(',')  # ['1', '3', '5']

                    # Kiểm tra hôm nay có phải ngày cần tạo task không
                    if today_weekday_str in weekdays_list:
                        should_create = True

                        # Tính due_date mới (nếu có)
                        if original_task.due_date:
                            original_due_vn = utc_to_vn(original_task.due_date)
                            # Giữ nguyên giờ từ task gốc, chỉ đổi ngày
                            next_due_date_vn = now_vn.replace(
                                hour=original_due_vn.hour,
                                minute=original_due_vn.minute,
                                second=original_due_vn.second,
                                microsecond=0
                            )
                            next_due_date = vn_to_utc(next_due_date_vn)

                # ===== TẠO TASK MỚI =====
                if should_create:
                    new_task = Task(
                        title=original_task.title,
                        description=original_task.description,
                        creator_id=original_task.creator_id,
                        due_date=next_due_date,
                        status='PENDING',
                        is_urgent=original_task.is_urgent,
                        is_important=original_task.is_important,
                        is_recurring=original_task.is_recurring,
                        recurrence_enabled=False,  # Task con không tự động lặp
                        parent_task_id=original_task.id,
                    )

                    db.session.add(new_task)
                    db.session.flush()

                    # Sao chép assignments từ task gốc
                    original_assignments = TaskAssignment.query.filter_by(
                        task_id=original_task.id,
                        accepted=True
                    ).all()

                    for orig_assign in original_assignments:
                        new_assignment = TaskAssignment(
                            task_id=new_task.id,
                            user_id=orig_assign.user_id,
                            assigned_by=orig_assign.assigned_by,
                            assigned_group=orig_assign.assigned_group,
                            accepted=True,
                            accepted_at=now_utc
                        )
                        db.session.add(new_assignment)

                        # Gửi thông báo
                        notif = Notification(
                            user_id=orig_assign.user_id,
                            type='task_assigned',
                            title='🔁 Nhiệm vụ lặp lại mới',
                            body=f'Nhiệm vụ "{new_task.title}" đã được tự động giao lại cho bạn.',
                            link=f'/tasks/{new_task.id}'
                        )
                        db.session.add(notif)

                    # ===== CẬP NHẬT last_recurrence_date =====
                    original_task.last_recurrence_date = now_utc
                    created_count += 1

            db.session.commit()

            if created_count > 0:
                print(f"✅ [{datetime.now()}] Recurring Tasks: Đã tạo {created_count} nhiệm vụ lặp lại mới")
            else:
                print(f"ℹ️  [{datetime.now()}] Recurring Tasks: Không có task nào cần tạo (skipped: {skipped_count})")

        except Exception as e:
            print(f"❌ [{datetime.now()}] Lỗi tạo recurring tasks: {str(e)}")
            import traceback
            traceback.print_exc()
            db.session.rollback()


def start_scheduler(app):
    """Khởi động scheduler"""
    worker_id = os.environ.get('GUNICORN_WORKER_ID', '0')

    if worker_id != '0':
        print(f" Worker {worker_id}: Bỏ qua scheduler")
        return None

    scheduler = BackgroundScheduler()

    # Job 1: Cleanup links (giữ nguyên)
    scheduler.add_job(
        func=lambda: cleanup_expired_links(app),
        trigger="interval",
        hours=1,
        id='cleanup_expired_links',
        name='Cleanup expired salary share links',
        replace_existing=True
    )

    # Job 2: THÊM MỚI - Tạo recurring tasks (mỗi ngày lúc 6h sáng)
    scheduler.add_job(
        func=lambda: create_recurring_tasks(app),
        trigger="cron",
        hour=6,
        minute=0,
        id='create_recurring_tasks',
        name='Create recurring tasks',
        replace_existing=True
    )

    # Chạy ngay lần đầu
    scheduler.add_job(
        func=lambda: cleanup_expired_links(app),
        trigger="date",
        run_date=datetime.now(),
        id='cleanup_on_start'
    )

    scheduler.start()
    print(f" Worker 0: Scheduler đã khởi động")
    print(f"   - Cleanup links: Mỗi 1 giờ")
    print(f"   - Recurring tasks: Mỗi ngày 6:00 AM")

    return scheduler