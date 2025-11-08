from flask import Blueprint, render_template, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Notification

bp = Blueprint('notifications', __name__)


@bp.route('/')
@login_required
def list_notifications():
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).all()
    return render_template('notifications.html', notifications=notifications)


@bp.route('/<int:notif_id>/mark-read', methods=['POST'])
@login_required
def mark_read(notif_id):
    notif = Notification.query.get_or_404(notif_id)

    if notif.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    notif.read = True
    db.session.commit()

    return jsonify({'success': True})


@bp.route('/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter_by(
        user_id=current_user.id,
        read=False
    ).update({'read': True})
    db.session.commit()

    return redirect(url_for('notifications.list_notifications'))


@bp.route('/<int:notif_id>/delete', methods=['POST'])
@login_required
def delete_notification(notif_id):
    notif = Notification.query.get_or_404(notif_id)

    if notif.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    db.session.delete(notif)
    db.session.commit()

    return redirect(url_for('notifications.list_notifications'))


@bp.route('/unread-count')
@login_required
def unread_count():
    count = Notification.query.filter_by(
        user_id=current_user.id,
        read=False
    ).count()
    return jsonify({'count': count})