from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Note
from datetime import datetime

bp = Blueprint('notes', __name__)


@bp.route('/')
@login_required
def list_notes():
    notes = Note.query.filter_by(
        user_id=current_user.id
    ).order_by(Note.updated_at.desc()).all()
    return render_template('notes.html', notes=notes)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_note():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')

        if not title:
            flash('Tiêu đề không được để trống.', 'danger')
            return redirect(url_for('notes.create_note'))

        note = Note(
            user_id=current_user.id,
            title=title,
            content=content
        )
        db.session.add(note)
        db.session.commit()

        flash('Tạo ghi chú thành công.', 'success')
        return redirect(url_for('notes.list_notes'))

    return render_template('create_note.html')


@bp.route('/<int:note_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_note(note_id):
    note = Note.query.get_or_404(note_id)

    if note.user_id != current_user.id:
        flash('Bạn không có quyền chỉnh sửa ghi chú này.', 'danger')
        return redirect(url_for('notes.list_notes'))

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')

        if not title:
            flash('Tiêu đề không được để trống.', 'danger')
            return redirect(url_for('notes.edit_note', note_id=note_id))

        note.title = title
        note.content = content
        note.updated_at = datetime.utcnow()
        db.session.commit()

        flash('Cập nhật ghi chú thành công.', 'success')
        return redirect(url_for('notes.list_notes'))

    return render_template('edit_note.html', note=note)


@bp.route('/<int:note_id>/delete', methods=['POST'])
@login_required
def delete_note(note_id):
    note = Note.query.get_or_404(note_id)

    if note.user_id != current_user.id:
        flash('Bạn không có quyền xóa ghi chú này.', 'danger')
        return redirect(url_for('notes.list_notes'))

    db.session.delete(note)
    db.session.commit()

    flash('Đã xóa ghi chú thành công.', 'success')
    return redirect(url_for('notes.list_notes'))