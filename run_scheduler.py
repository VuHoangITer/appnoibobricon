#!/usr/bin/env python
"""
Scheduler Service - Chạy riêng biệt với Flask app
Nhiệm vụ: Tự động xóa link chia sẻ lương đã hết hạn mỗi 1 giờ
"""

from app import create_app
from app.scheduler import cleanup_expired_links
import signal
import sys
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime

# Flag để graceful shutdown
should_exit = False


def signal_handler(sig, frame):
    """Xử lý tín hiệu dừng (Ctrl+C hoặc systemctl stop)"""
    global should_exit
    print("\n Nhận tín hiệu dừng scheduler...")
    should_exit = True
    sys.exit(0)


# Đăng ký signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Tạo Flask app
app = create_app()

# Banner
print("=" * 70)
print("Company Workflow - Scheduler Service")
print("=" * 70)
print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Cleanup job: Every 1 hour")
print(f"Target: Expired salary share links")
print(f"Press Ctrl+C to stop gracefully")
print("=" * 70)

# Tạo BlockingScheduler (khác với BackgroundScheduler)
scheduler = BlockingScheduler()

# Thêm job: chạy mỗi 1 giờ
scheduler.add_job(
    func=lambda: cleanup_expired_links(app),
    trigger="interval",
    hours=1,
    id='cleanup_expired_links',
    name='Cleanup expired salary share links',
    replace_existing=True,
    max_instances=1  # Chỉ cho phép 1 instance chạy cùng lúc
)

# Chạy cleanup ngay lần đầu tiên
print("\nRunning initial cleanup...")
cleanup_expired_links(app)

# Khởi động scheduler
try:
    print("\nScheduler is now running!")
    print("Next cleanup: in 1 hour")
    print("-" * 70)
    scheduler.start()
except (KeyboardInterrupt, SystemExit):
    print("\nStopping scheduler...")
    scheduler.shutdown(wait=True)
    print("Scheduler stopped gracefully.")
    sys.exit(0)

# Thêm vào cuối file
from app.scheduler import create_recurring_tasks

# Thêm job mới
scheduler.add_job(
    func=lambda: create_recurring_tasks(app),
    trigger="cron",
    hour=6,
    minute=0,
    id='create_recurring_tasks',
    name='Create recurring tasks daily at 6 AM',
    replace_existing=True,
    max_instances=1
)

print(f"Recurring Tasks job: Every day at 6:00 AM")