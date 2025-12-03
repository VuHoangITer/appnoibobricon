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
    """Tự động tạo task lặp lại hàng tuần"""
    with app.app_context():
        from app import db
        from app.models import Task, TaskAssignment, User, Notification
        from datetime import datetime, timedelta

        try:
            now = datetime.utcnow()

            # Tìm các task có bật recurring và đã đến lúc tạo mới
            recurring_tasks = Task.query.filter(
                Task.recurrence_enabled == True,
                Task.is_recurring == True,
                Task.last_recurrence_date.isnot(None)
            ).all()

            created_count = 0

            for original_task in recurring_tasks:
                # Tính ngày tạo task tiếp theo
                next_date = original_task.last_recurrence_date + timedelta(
                    days=original_task.recurrence_interval_days
                )

                # Nếu đã đến lúc tạo task mới
                if now >= next_date:
                    # Tạo task mới
                    new_task = Task(
                        title=original_task.title,
                        description=original_task.description,
                        creator_id=original_task.creator_id,
                        status='PENDING',
                        is_urgent=original_task.is_urgent,
                        is_important=original_task.is_important,
                        is_recurring=original_task.is_recurring,
                        recurrence_enabled=False,  # Task con không tự động lặp
                        parent_task_id=original_task.id,  # Liên kết với task gốc
                    )

                    # Cộng thêm due_date nếu có
                    if original_task.due_date:
                        days_diff = (original_task.due_date - original_task.last_recurrence_date).days
                        new_task.due_date = next_date + timedelta(days=days_diff)

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
                            accepted_at=now
                        )
                        db.session.add(new_assignment)

                        # Gửi thông báo
                        notif = Notification(
                            user_id=orig_assign.user_id,
                            type='task_assigned',
                            title=' Nhiệm vụ lặp lại mới',
                            body=f'Nhiệm vụ "{new_task.title}" đã được tự động giao lại cho bạn.',
                            link=f'/tasks/{new_task.id}'
                        )
                        db.session.add(notif)

                    # Cập nhật last_recurrence_date của task gốc
                    original_task.last_recurrence_date = next_date
                    created_count += 1

            db.session.commit()

            if created_count > 0:
                print(f" [{datetime.now()}] Recurring Tasks: Đã tạo {created_count} nhiệm vụ lặp lại mới")
            else:
                print(f"  [{datetime.now()}] Recurring Tasks: Chưa đến lúc tạo task mới")

        except Exception as e:
            print(f"❌ [{datetime.now()}] Lỗi tạo recurring tasks: {str(e)}")
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