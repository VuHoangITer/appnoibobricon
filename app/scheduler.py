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
                print(f"✅ [{datetime.now()}] Cleanup: Đã xóa {deleted} link hết hạn, {deactivated} link hết lượt xem")
            else:
                print(f"ℹ️  [{datetime.now()}] Cleanup: Không có link nào cần xóa")

        except Exception as e:
            print(f"❌ [{datetime.now()}] Lỗi khi cleanup: {str(e)}")
            db.session.rollback()


def start_scheduler(app):
    """
    Khởi động scheduler - CHỈ CHẠY TRONG 1 WORKER DUY NHẤT
    """
    # ===== THÊM: Kiểm tra chỉ chạy trong worker đầu tiên =====
    worker_id = os.environ.get('GUNICORN_WORKER_ID', '0')

    # Nếu không phải worker đầu tiên, không khởi động scheduler
    if worker_id != '0':
        print(f"ℹ️  Worker {worker_id}: Bỏ qua scheduler (chỉ chạy ở worker 0)")
        return None
    # ===== END =====

    scheduler = BackgroundScheduler()

    # Chạy cleanup mỗi 1 giờ
    scheduler.add_job(
        func=lambda: cleanup_expired_links(app),
        trigger="interval",
        hours=1,
        id='cleanup_expired_links',
        name='Cleanup expired salary share links',
        replace_existing=True
    )

    # Chạy ngay lần đầu khi start
    scheduler.add_job(
        func=lambda: cleanup_expired_links(app),
        trigger="date",
        run_date=datetime.now(),
        id='cleanup_on_start',
        name='Initial cleanup'
    )

    scheduler.start()
    print(f"✅ Worker 0: Scheduler đã khởi động - tự động xóa link hết hạn mỗi 1 giờ")

    return scheduler