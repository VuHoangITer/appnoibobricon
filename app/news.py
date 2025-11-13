from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models import News, NewsComment, NewsConfirmation, User, Notification
from app.decorators import role_required
from datetime import datetime
import os
import uuid

bp = Blueprint('news', __name__)

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_image_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


@bp.route('/')
@login_required
def list_news():
    """Danh sách tất cả bài đăng tin tức"""
    page = request.args.get('page', 1, type=int)
    per_page = 10

    pagination = News.query.order_by(News.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    news_posts = pagination.items

    return render_template('news/list.html',
                           news_posts=news_posts,
                           pagination=pagination)


# ============ API ROUTE - PHẢI ĐẶT TRƯỚC /<int:news_id> ============
@bp.route('/<int:news_id>/comments/latest')
@login_required
def get_latest_comments(news_id):
    """API để lấy comments mới nhất (dùng cho polling)"""
    from app.utils import utc_to_vn

    try:
        news = News.query.get_or_404(news_id)

        # Lấy timestamp từ query parameter
        last_timestamp = request.args.get('last_timestamp', type=float, default=0)

        print(f"[DEBUG] API called - news_id={news_id}, last_timestamp={last_timestamp}")

        # Convert timestamp về datetime
        if last_timestamp > 0:
            last_datetime = datetime.fromtimestamp(last_timestamp)
            # Lấy comments mới hơn last_datetime
            comments = NewsComment.query.filter(
                NewsComment.news_id == news_id,
                NewsComment.created_at > last_datetime
            ).order_by(NewsComment.created_at.asc()).all()
            print(f"[DEBUG] Found {len(comments)} new comments after {last_datetime}")
        else:
            # Lần đầu tiên, lấy tất cả
            comments = NewsComment.query.filter_by(
                news_id=news_id
            ).order_by(NewsComment.created_at.desc()).all()
            print(f"[DEBUG] Initial load, found {len(comments)} total comments")

        # Format comments thành JSON
        comments_data = []
        for comment in comments:
            # Convert UTC to Vietnam time for display
            vn_time = utc_to_vn(comment.created_at)

            comments_data.append({
                'id': comment.id,
                'content': comment.content,
                'created_at': comment.created_at.isoformat(),
                'created_at_timestamp': comment.created_at.timestamp(),
                'created_at_display': vn_time.strftime('%d/%m/%Y %H:%M'),
                'user': {
                    'id': comment.user_id,
                    'full_name': comment.user.full_name,
                    'role': comment.user.role,
                    'avatar_letter': comment.user.full_name[0].upper()
                },
                'can_delete': comment.user_id == current_user.id or current_user.role == 'director'
            })

        total_count = NewsComment.query.filter_by(news_id=news_id).count()

        response_data = {
            'success': True,
            'comments': comments_data,
            'total_count': total_count,
            'server_time': datetime.utcnow().isoformat()
        }

        print(f"[DEBUG] Returning {len(comments_data)} comments, total={total_count}")

        return jsonify(response_data)

    except Exception as e:
        print(f"[ERROR] get_latest_comments: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/<int:news_id>')
@login_required
def news_detail(news_id):
    """Chi tiết bài đăng"""
    news = News.query.get_or_404(news_id)
    comments = news.comments.order_by(NewsComment.created_at.desc()).all()

    # Kiểm tra user đã confirm chưa
    is_confirmed = news.is_confirmed_by(current_user.id)

    # Lấy danh sách người đã confirm
    confirmations = news.confirmations.all()

    return render_template('news/detail.html',
                           news=news,
                           comments=comments,
                           is_confirmed=is_confirmed,
                           confirmations=confirmations)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required(['director', 'manager'])
def create_news():
    """Tạo bài đăng mới - chỉ Director/Manager"""
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')

        if not title or not content:
            flash('Vui lòng nhập đầy đủ tiêu đề và nội dung.', 'danger')
            return redirect(url_for('news.create_news'))

        # Xử lý upload ảnh
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_image_file(file.filename):
                # Tạo tên file unique
                original_filename = secure_filename(file.filename)
                file_ext = original_filename.rsplit('.', 1)[1].lower()
                unique_filename = f"news_{uuid.uuid4().hex}.{file_ext}"

                # Tạo thư mục news_images nếu chưa có
                news_images_folder = os.path.join(current_app.root_path, 'uploads', 'news_images')
                if not os.path.exists(news_images_folder):
                    os.makedirs(news_images_folder)

                filepath = os.path.join(news_images_folder, unique_filename)
                file.save(filepath)
                image_filename = unique_filename

        # Tạo bài đăng
        news = News(
            title=title,
            content=content,
            author_id=current_user.id,
            image_filename=image_filename
        )
        db.session.add(news)
        db.session.commit()

        # Gửi thông báo cho tất cả users
        all_users = User.query.filter(User.id != current_user.id, User.is_active == True).all()
        for user in all_users:
            notif = Notification(
                user_id=user.id,
                type='news_posted',
                title='Tin tức mới',
                body=f'{current_user.full_name} đã đăng tin tức: {title}',
                link=f'/news/{news.id}'
            )
            db.session.add(notif)

        db.session.commit()

        flash('Đăng tin tức thành công!', 'success')
        return redirect(url_for('news.news_detail', news_id=news.id))

    return render_template('news/create.html')


@bp.route('/<int:news_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_news(news_id):
    """Chỉnh sửa bài đăng - chỉ tác giả hoặc Director"""
    news = News.query.get_or_404(news_id)

    # Kiểm tra quyền
    if news.author_id != current_user.id and current_user.role != 'director':
        flash('Bạn không có quyền chỉnh sửa bài đăng này.', 'danger')
        return redirect(url_for('news.news_detail', news_id=news_id))

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        delete_image = request.form.get('delete_image', '0')

        if not title or not content:
            flash('Vui lòng nhập đầy đủ tiêu đề và nội dung.', 'danger')
            return redirect(url_for('news.edit_news', news_id=news_id))

        news.title = title
        news.content = content
        news.updated_at = datetime.utcnow()

        # Xử lý xóa ảnh hiện tại nếu được yêu cầu
        if delete_image == '1' and news.image_filename:
            old_image_path = os.path.join(
                current_app.root_path, 'uploads', 'news_images', news.image_filename
            )
            if os.path.exists(old_image_path):
                try:
                    os.remove(old_image_path)
                    print(f"[DEBUG] Đã xóa ảnh theo yêu cầu: {old_image_path}")
                except Exception as e:
                    print(f"[LỖI] Xóa ảnh theo yêu cầu thất bại: {e}")
            else:
                print(f"[CẢNH BÁO] Không tìm thấy ảnh để xóa: {old_image_path}")
            news.image_filename = None

        # Xử lý upload ảnh mới
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_image_file(file.filename):
                # Xóa ảnh cũ nếu có (khi upload ảnh mới)
                if news.image_filename:
                    old_image_path = os.path.join(
                        current_app.root_path, 'uploads', 'news_images', news.image_filename
                    )
                    if os.path.exists(old_image_path):
                        try:
                            os.remove(old_image_path)
                            print(f"[DEBUG] Đã xóa ảnh cũ: {old_image_path}")
                        except Exception as e:
                            print(f"[LỖI] Xóa ảnh cũ thất bại: {e}")

                # Lưu ảnh mới
                original_filename = secure_filename(file.filename)
                file_ext = original_filename.rsplit('.', 1)[1].lower()
                unique_filename = f"news_{uuid.uuid4().hex}.{file_ext}"

                news_images_folder = os.path.join(current_app.root_path, 'uploads', 'news_images')
                if not os.path.exists(news_images_folder):
                    os.makedirs(news_images_folder)

                filepath = os.path.join(news_images_folder, unique_filename)
                file.save(filepath)
                news.image_filename = unique_filename

        db.session.commit()
        flash('Cập nhật tin tức thành công!', 'success')
        return redirect(url_for('news.news_detail', news_id=news_id))

    return render_template('news/edit.html', news=news)


@bp.route('/<int:news_id>/delete', methods=['POST'])
@login_required
def delete_news(news_id):
    """Xóa bài đăng - chỉ tác giả hoặc Director"""
    news = News.query.get_or_404(news_id)

    # Kiểm tra quyền
    if news.author_id != current_user.id and current_user.role != 'director':
        flash('Bạn không có quyền xóa bài đăng này.', 'danger')
        return redirect(url_for('news.news_detail', news_id=news_id))

    # Xóa ảnh nếu có
    if news.image_filename:
        image_path = os.path.join(
            current_app.root_path, 'uploads', 'news_images', news.image_filename
        )
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
                print(f"[DEBUG] Đã xóa ảnh: {image_path}")
            except Exception as e:
                print(f"[LỖI] Không xóa được ảnh: {e}")
        else:
            print(f"[CẢNH BÁO] Không tìm thấy ảnh: {image_path}")

    # Xóa thông báo liên quan
    Notification.query.filter(Notification.link == f'/news/{news_id}').delete()

    db.session.delete(news)
    db.session.commit()

    flash('Đã xóa tin tức thành công.', 'success')
    return redirect(url_for('news.list_news'))


@bp.route('/<int:news_id>/comment', methods=['POST'])
@login_required
def add_comment(news_id):
    """Thêm bình luận"""
    from app.utils import utc_to_vn

    # Check if it's an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    news = News.query.get_or_404(news_id)
    content = request.form.get('content')

    if not content or not content.strip():
        if is_ajax:
            return jsonify({
                'success': False,
                'error': 'Nội dung bình luận không được để trống.'
            }), 400
        flash('Nội dung bình luận không được để trống.', 'danger')
        return redirect(url_for('news.news_detail', news_id=news_id))

    comment = NewsComment(
        news_id=news_id,
        user_id=current_user.id,
        content=content.strip()
    )
    db.session.add(comment)
    db.session.commit()

    print(f"[DEBUG] New comment added: id={comment.id}, created_at={comment.created_at}")

    # Gửi thông báo cho tác giả bài viết (nếu không phải chính họ comment)
    if news.author_id != current_user.id:
        notif = Notification(
            user_id=news.author_id,
            type='news_comment',
            title='Bình luận mới',
            body=f'{current_user.full_name} đã bình luận vào bài viết: {news.title}',
            link=f'/news/{news.id}'
        )
        db.session.add(notif)
        db.session.commit()

    # If AJAX request, return JSON
    if is_ajax:
        vn_time = utc_to_vn(comment.created_at)
        return jsonify({
            'success': True,
            'comment': {
                'id': comment.id,
                'content': comment.content,
                'created_at': comment.created_at.isoformat(),
                'created_at_timestamp': comment.created_at.timestamp(),
                'created_at_display': vn_time.strftime('%d/%m/%Y %H:%M'),
                'user': {
                    'id': comment.user_id,
                    'full_name': comment.user.full_name,
                    'role': comment.user.role,
                    'avatar_letter': comment.user.full_name[0].upper()
                },
                'can_delete': True  # User just created it
            }
        })

    flash('Đã thêm bình luận.', 'success')
    return redirect(url_for('news.news_detail', news_id=news_id))


@bp.route('/comment/<int:comment_id>/delete', methods=['POST', 'DELETE'])
@login_required
def delete_comment(comment_id):
    """Xóa bình luận - chỉ người tạo hoặc Director"""
    # Check if it's an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    comment = NewsComment.query.get_or_404(comment_id)
    news_id = comment.news_id

    # Kiểm tra quyền
    if comment.user_id != current_user.id and current_user.role != 'director':
        if is_ajax:
            return jsonify({
                'success': False,
                'error': 'Bạn không có quyền xóa bình luận này.'
            }), 403
        flash('Bạn không có quyền xóa bình luận này.', 'danger')
        return redirect(url_for('news.news_detail', news_id=news_id))

    db.session.delete(comment)
    db.session.commit()

    print(f"[DEBUG] Comment deleted: id={comment_id}")

    # If AJAX request, return JSON
    if is_ajax:
        return jsonify({
            'success': True,
            'comment_id': comment_id
        })

    flash('Đã xóa bình luận.', 'success')
    return redirect(url_for('news.news_detail', news_id=news_id))


@bp.route('/<int:news_id>/confirm', methods=['POST'])
@login_required
def confirm_read(news_id):
    """Xác nhận đã đọc tin tức"""
    news = News.query.get_or_404(news_id)

    # Kiểm tra đã confirm chưa
    existing = NewsConfirmation.query.filter_by(
        news_id=news_id,
        user_id=current_user.id
    ).first()

    if existing:
        flash('Bạn đã xác nhận đọc tin tức này rồi.', 'info')
    else:
        confirmation = NewsConfirmation(
            news_id=news_id,
            user_id=current_user.id
        )
        db.session.add(confirmation)
        db.session.commit()
        flash('Đã xác nhận đọc tin tức.', 'success')

    return redirect(url_for('news.news_detail', news_id=news_id))


@bp.route('/<int:news_id>/image')
@login_required
def get_news_image(news_id):
    """Lấy ảnh của bài đăng"""
    from flask import send_from_directory
    news = News.query.get_or_404(news_id)

    if not news.image_filename:
        return "No image", 404

    news_images_folder = os.path.join(current_app.root_path, 'uploads', 'news_images')
    return send_from_directory(news_images_folder, news.image_filename)


@bp.route('/<int:news_id>/comments/deleted')
@login_required
def get_deleted_comments(news_id):
    """API để lấy danh sách comment IDs đã bị xóa (cho realtime sync)"""
    # Lấy danh sách comment IDs hiện tại
    current_comment_ids = [c.id for c in NewsComment.query.filter_by(news_id=news_id).all()]

    return jsonify({
        'success': True,
        'existing_ids': current_comment_ids,
        'total_count': len(current_comment_ids)
    })