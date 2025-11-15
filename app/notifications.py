from flask import Blueprint, render_template, redirect, url_for, jsonify, request
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
    """Đánh dấu 1 thông báo đã đọc"""
    # Check if AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    notif = Notification.query.get_or_404(notif_id)

    if notif.user_id != current_user.id:
        if is_ajax:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        return jsonify({'error': 'Unauthorized'}), 403

    notif.read = True
    db.session.commit()

    if is_ajax:
        # Return updated unread count
        unread = Notification.query.filter_by(
            user_id=current_user.id,
            read=False
        ).count()
        return jsonify({
            'success': True,
            'unread_count': unread
        })

    return jsonify({'success': True})


@bp.route('/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    """Đánh dấu tất cả thông báo đã đọc"""
    # Check if AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    Notification.query.filter_by(
        user_id=current_user.id,
        read=False
    ).update({'read': True})
    db.session.commit()

    if is_ajax:
        return jsonify({
            'success': True,
            'unread_count': 0
        })

    return redirect(url_for('notifications.list_notifications'))


@bp.route('/<int:notif_id>/delete', methods=['POST'])
@login_required
def delete_notification(notif_id):
    """Xóa 1 thông báo"""
    # Check if AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    notif = Notification.query.get_or_404(notif_id)

    if notif.user_id != current_user.id:
        if is_ajax:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        return jsonify({'error': 'Unauthorized'}), 403

    db.session.delete(notif)
    db.session.commit()

    if is_ajax:
        # Return updated counts
        total = Notification.query.filter_by(user_id=current_user.id).count()
        unread = Notification.query.filter_by(
            user_id=current_user.id,
            read=False
        ).count()
        return jsonify({
            'success': True,
            'total_count': total,
            'unread_count': unread
        })

    return redirect(url_for('notifications.list_notifications'))


@bp.route('/delete-all', methods=['POST'])
@login_required
def delete_all_notifications():
    """Xóa tất cả thông báo"""
    # Check if AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    # Get delete type: 'all' or 'read'
    delete_type = request.form.get('type', 'all')

    if delete_type == 'read':
        # Only delete read notifications
        deleted = Notification.query.filter_by(
            user_id=current_user.id,
            read=True
        ).delete()
    else:
        # Delete all notifications
        deleted = Notification.query.filter_by(
            user_id=current_user.id
        ).delete()

    db.session.commit()

    if is_ajax:
        # Return updated counts
        total = Notification.query.filter_by(user_id=current_user.id).count()
        unread = Notification.query.filter_by(
            user_id=current_user.id,
            read=False
        ).count()
        return jsonify({
            'success': True,
            'deleted_count': deleted,
            'total_count': total,
            'unread_count': unread
        })

    return redirect(url_for('notifications.list_notifications'))


@bp.route('/unread-count')
@login_required
def unread_count():
    """API lấy số lượng thông báo chưa đọc"""
    count = Notification.query.filter_by(
        user_id=current_user.id,
        read=False
    ).count()
    return jsonify({'count': count})


@bp.route('/unread-ids')
@login_required
def unread_ids():
    """API lấy danh sách IDs thông báo chưa đọc"""
    notifications = Notification.query.filter_by(
        user_id=current_user.id,
        read=False
    ).order_by(Notification.created_at.desc()).all()

    ids = [notif.id for notif in notifications]

    return jsonify({
        'ids': ids,
        'count': len(ids)
    })


@bp.route('/latest')
@login_required
def latest_notification():
    """API lấy thông báo mới nhất (chưa đọc)"""
    notif = Notification.query.filter_by(
        user_id=current_user.id,
        read=False
    ).order_by(Notification.created_at.desc()).first()

    if notif:
        return jsonify({
            'id': notif.id,
            'title': notif.title,
            'body': notif.body,
            'type': notif.type,
            'link': notif.link,
            'created_at': notif.created_at.isoformat()
        })
    else:
        return jsonify({'title': None}), 404


@bp.route('/latest-all')
@login_required
def latest_all_notifications():
    """API lấy TẤT CẢ thông báo chưa đọc (tối đa 10)"""
    notifs = Notification.query.filter_by(
        user_id=current_user.id,
        read=False
    ).order_by(Notification.created_at.desc()).limit(10).all()

    return jsonify({
        'notifications': [
            {
                'id': notif.id,
                'title': notif.title,
                'body': notif.body,
                'type': notif.type,
                'link': notif.link,
                'created_at': notif.created_at.isoformat()
            } for notif in notifs
        ],
        'count': len(notifs)
    })