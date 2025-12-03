"""
Scheduler để tự động xóa link hết hạn và tạo recurring tasks
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
                print(f"🧹 [{datetime.now()}] Cleanup: Đã xóa {deleted} link hết hạn, {deactivated} link hết lượt xem")
            else:
                print(f"ℹ️  [{datetime.now()}] Cleanup: Không có link nào cần xóa")

        except Exception as e:
            print(f"❌ [{datetime.now()}] Lỗi khi cleanup: {str(e)}")
            db.session.rollback()


def create_recurring_tasks(app):
    """Tự động tạo task lặp lại - hỗ trợ cả interval và weekly"""
    with app.app_context():
        from app import db
        from app.models import Task, TaskAssignment, User, Notification
        from datetime import datetime, timedelta, time as dt_time
        from app.utils import vn_now, vn_to_utc, utc_to_vn

        try:
            now_utc = datetime.utcnow()
            now_vn = vn_now()  # Lấy giờ Việt Nam

            print(f"⏰ [{now_vn.strftime('%Y-%m-%d %H:%M:%S')}] Checking recurring tasks...")

            # ===== XỬ LÝ 2 LOẠI RECURRING =====

            # ===== 1️⃣ INTERVAL-BASED (cũ - giữ nguyên logic) =====
            interval_tasks = Task.query.filter(
                Task.recurrence_enabled == True,
                Task.recurrence_type == 'interval',
                Task.last_recurrence_date.isnot(None)
            ).all()

            created_interval = 0
            for original_task in interval_tasks:
                next_date = original_task.last_recurrence_date + timedelta(
                    days=original_task.recurrence_interval_days
                )

                if now_utc >= next_date:
                    # Tạo task mới
                    new_task = Task(
                        title=original_task.title,
                        description=original_task.description,
                        creator_id=original_task.creator_id,
                        status='PENDING',
                        is_urgent=original_task.is_urgent,
                        is_important=original_task.is_important,
                        is_recurring=original_task.is_recurring,
                        recurrence_enabled=False,
                        parent_task_id=original_task.id,
                    )

                    if original_task.due_date:
                        days_diff = (original_task.due_date - original_task.last_recurrence_date).days
                        new_task.due_date = next_date + timedelta(days=days_diff)

                    db.session.add(new_task)
                    db.session.flush()

                    # Sao chép assignments
                    _copy_assignments(original_task, new_task, now_utc)

                    original_task.last_recurrence_date = next_date
                    created_interval += 1

            # ===== 2️⃣ WEEKLY-BASED (mới) =====
            weekly_tasks = Task.query.filter(
                Task.recurrence_enabled == True,
                Task.recurrence_type == 'weekly',
                Task.recurrence_weekdays.isnot(None),
                Task.recurrence_time.isnot(None)
            ).all()

            created_weekly = 0
            for original_task in weekly_tasks:
                try:
                    # Parse weekdays: '0,2,4' -> [0, 2, 4]
                    weekdays = [int(d.strip()) for d in original_task.recurrence_weekdays.split(',')]

                    # Lấy thứ hiện tại (Monday=0, Sunday=6)
                    current_weekday = now_vn.weekday()

                    # Kiểm tra hôm nay có trong danh sách không
                    if current_weekday not in weekdays:
                        continue

                    # Kiểm tra giờ
                    task_time = original_task.recurrence_time

                    # Tạo datetime VN cho thời điểm tạo task
                    target_time_vn = now_vn.replace(
                        hour=task_time.hour,
                        minute=task_time.minute,
                        second=0,
                        microsecond=0
                    )

                    # Kiểm tra đã tạo hôm nay chưa
                    last_created_vn = None
                    if original_task.last_recurrence_date:
                        last_created_vn = utc_to_vn(original_task.last_recurrence_date)

                    if last_created_vn and last_created_vn.date() == now_vn.date():
                        continue  # Đã tạo hôm nay rồi

                    # Kiểm tra đã đến giờ chưa
                    if now_vn < target_time_vn:
                        continue  # Chưa đến giờ

                    # ✅ TẠO TASK MỚI
                    new_task = Task(
                        title=original_task.title,
                        description=original_task.description,
                        creator_id=original_task.creator_id,
                        status='PENDING',
                        is_urgent=original_task.is_urgent,
                        is_important=original_task.is_important,
                        is_recurring=original_task.is_recurring,
                        recurrence_enabled=False,  # Task con không tự động lặp
                        parent_task_id=original_task.id,
                    )

                    # Tính due_date: target_time_vn + duration_days
                    due_date_vn = target_time_vn + timedelta(days=original_task.recurrence_duration_days)
                    new_task.due_date = vn_to_utc(due_date_vn)

                    db.session.add(new_task)
                    db.session.flush()

                    # Sao chép assignments
                    _copy_assignments(original_task, new_task, now_utc)

                    # Cập nhật last_recurrence_date
                    original_task.last_recurrence_date = vn_to_utc(now_vn)
                    created_weekly += 1

                    print(f"✅ Created weekly task: '{new_task.title}' (ID: {new_task.id})")

                except Exception as e:
                    print(f"⚠️  Error processing weekly task {original_task.id}: {str(e)}")
                    continue

            db.session.commit()

            if created_interval > 0 or created_weekly > 0:
                print(
                    f"✅ [{now_vn.strftime('%H:%M:%S')}] Created {created_interval} interval tasks, {created_weekly} weekly tasks")
            else:
                print(f"ℹ️  [{now_vn.strftime('%H:%M:%S')}] No tasks to create")

        except Exception as e:
            print(f"❌ [{datetime.now()}] Error creating recurring tasks: {str(e)}")
            import traceback
            traceback.print_exc()
            db.session.rollback()


def _copy_assignments(original_task, new_task, now_utc):
    """Helper: Sao chép assignments từ task gốc sang task mới"""
    from app.models import TaskAssignment, Notification
    from app import db

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


def start_scheduler(app):
    """Khởi động scheduler"""
    worker_id = os.environ.get('GUNICORN_WORKER_ID', '0')

    if worker_id != '0':
        print(f"⏭️  Worker {worker_id}: Bỏ qua scheduler")
        return None

    scheduler = BackgroundScheduler()

    # Job 1: Cleanup links
    scheduler.add_job(
        func=lambda: cleanup_expired_links(app),
        trigger="interval",
        hours=1,
        id='cleanup_expired_links',
        name='Cleanup expired salary share links',
        replace_existing=True
    )

    # Job 2: ✅ TỐI ƯU - Chạy mỗi giờ từ 6h sáng đến 19h tối
    scheduler.add_job(
        func=lambda: create_recurring_tasks(app),
        trigger="cron",
        hour='6-19',  # Chỉ chạy từ 6:00 đến 19:00
        minute=0,  # Chạy đúng phút 00 của mỗi giờ
        id='create_recurring_tasks',
        name='Create recurring tasks (6AM-7PM)',
        replace_existing=True
    )

    # Chạy ngay lần đầu
    scheduler.add_job(
        func=lambda: cleanup_expired_links(app),
        trigger="date",
        run_date=datetime.now(),
        id='cleanup_on_start'
    )

    scheduler.add_job(
        func=lambda: create_recurring_tasks(app),
        trigger="date",
        run_date=datetime.now(),
        id='recurring_on_start'
    )

    scheduler.start()
    print(f"✅ Worker 0: Scheduler started")
    print(f"   - Cleanup links: Every 1 hour")
    print(f"   - Recurring tasks: Hourly (6:00-19:00)")

    return scheduler