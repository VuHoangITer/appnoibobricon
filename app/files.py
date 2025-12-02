from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, current_app, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from app import db
from app.models import File
from app.decorators import role_required
import os
import uuid

bp = Blueprint('files', __name__)


# ==========================================
# TOKEN FUNCTIONS - Tạo URL tạm thời
# ==========================================

def get_serializer():
    """Tạo serializer để ký token"""
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def generate_file_token(file_id, expires_in=1800):
    """
    Tạo token có thời hạn cho file
    expires_in: thời gian hết hạn (giây), mặc định 30p
    """
    serializer = get_serializer()
    return serializer.dumps({'file_id': file_id}, salt='file-viewer')


def verify_file_token(token, max_age=1800):
    """
    Xác thực token và trả về file_id
    max_age: thời gian tối đa token còn hiệu lực (giây)
    """
    serializer = get_serializer()
    try:
        data = serializer.loads(token, salt='file-viewer', max_age=max_age)
        return data['file_id']
    except (BadSignature, SignatureExpired):
        return None


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def get_file_type(filename):
    """Determine file type based on extension"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

    if ext == 'pdf':
        return 'pdf'
    elif ext in ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp']:
        return 'image'
    elif ext in ['docx', 'doc']:
        return 'word'
    elif ext in ['xlsx', 'xls']:
        return 'excel'
    else:
        return 'unknown'


# ==========================================
# ROUTES
# ==========================================

@bp.route('/')
@login_required
def list_files():
    files = File.query.order_by(File.uploaded_at.desc()).all()
    return render_template('files.html', files=files)


@bp.route('/upload', methods=['GET', 'POST'])
@login_required
@role_required(['director', 'manager'])
def upload_file():
    if request.method == 'POST':
        try:
            if 'file' not in request.files:
                flash('Không có file được chọn.', 'danger')
                return redirect(request.url)

            file = request.files['file']
            description = request.form.get('description', '')

            if file.filename == '':
                flash('Không có file được chọn.', 'danger')
                return redirect(request.url)

            if file and allowed_file(file.filename):
                # Secure filename and add UUID to avoid conflicts
                original_filename = secure_filename(file.filename)
                file_ext = original_filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{uuid.uuid4().hex}.{file_ext}"

                # Tạo folder nếu chưa tồn tại
                os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)

                # Lưu file vào UPLOAD_FOLDER
                filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(filepath)

                # Get file size
                file_size = os.path.getsize(filepath)

                # Save to database
                file_record = File(
                    filename=unique_filename,
                    original_filename=original_filename,
                    path=filepath,
                    uploader_id=current_user.id,
                    description=description,
                    file_size=file_size
                )
                db.session.add(file_record)
                db.session.commit()

                flash('Upload file thành công.', 'success')
                return redirect(url_for('files.list_files'))
            else:
                flash('File không hợp lệ. Chỉ chấp nhận: pdf, docx, xlsx, png, jpg, jpeg', 'danger')
                return redirect(request.url)

        except RequestEntityTooLarge:
            max_size_mb = current_app.config['MAX_CONTENT_LENGTH'] / (1024 * 1024)
            flash(f'File quá lớn! Kích thước tối đa cho phép: {max_size_mb:.0f}MB', 'danger')
            return redirect(request.url)

    return render_template('upload_file.html')


@bp.route('/download/<int:file_id>')
@login_required
def download_file(file_id):
    file = File.query.get_or_404(file_id)

    # Kiểm tra file có tồn tại không
    if not os.path.exists(file.path):
        flash('File không tồn tại trên server.', 'danger')
        return redirect(url_for('files.list_files'))

    try:
        # Lấy thư mục chứa file từ đường dẫn tuyệt đối
        directory = os.path.dirname(file.path)
        filename = os.path.basename(file.path)

        return send_from_directory(
            directory,
            filename,
            as_attachment=True,
            download_name=file.original_filename
        )
    except Exception as e:
        flash(f'Lỗi khi tải file: {str(e)}', 'danger')
        return redirect(url_for('files.list_files'))


@bp.route('/preview/<int:file_id>')
@login_required
def preview_file(file_id):
    """Preview file - show preview page"""
    file = File.query.get_or_404(file_id)
    file_type = get_file_type(file.original_filename)

    # Tạo token có thời hạn 30p
    token = generate_file_token(file.id, expires_in=1800)

    # URL công khai tạm thời (không cần login)
    public_url = url_for('files.view_file_public', token=token, _external=True)

    return render_template('preview_file.html',
                           file=file,
                           file_type=file_type,
                           file_url=public_url)


@bp.route('/view/<int:file_id>')
@login_required
def view_file(file_id):
    """Serve raw file for logged-in users"""
    file = File.query.get_or_404(file_id)

    # Xác định MIME type dựa trên extension
    mime_types = {
        'pdf': 'application/pdf',
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'bmp': 'image/bmp',
        'webp': 'image/webp',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xls': 'application/vnd.ms-excel',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    }

    file_ext = file.original_filename.rsplit('.', 1)[1].lower() if '.' in file.original_filename else ''
    mimetype = mime_types.get(file_ext, 'application/octet-stream')

    # Kiểm tra file có tồn tại không
    if not os.path.exists(file.path):
        abort(404)

    try:
        # Lấy thư mục chứa file từ đường dẫn tuyệt đối
        directory = os.path.dirname(file.path)
        filename = os.path.basename(file.path)

        response = send_from_directory(
            directory,
            filename,
            as_attachment=False,
            mimetype=mimetype
        )

        # Cache trong 1 ngày
        response.headers['Cache-Control'] = 'public, max-age=86400'

        return response
    except Exception as e:
        abort(500)


@bp.route('/public/<token>')
def view_file_public(token):
    """
    Serve file qua signed URL - KHÔNG CẦN LOGIN
    Token hết hạn sau 30p
    Để Google/Microsoft Viewer có thể truy cập
    """
    # Xác thực token (hết hạn sau 30p)
    file_id = verify_file_token(token, max_age=1800)

    if not file_id:
        abort(403)  # Token không hợp lệ hoặc đã hết hạn

    file = File.query.get_or_404(file_id)

    mime_types = {
        'pdf': 'application/pdf',
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'bmp': 'image/bmp',
        'webp': 'image/webp',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xls': 'application/vnd.ms-excel',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    }

    file_ext = file.original_filename.rsplit('.', 1)[1].lower() if '.' in file.original_filename else ''
    mimetype = mime_types.get(file_ext, 'application/octet-stream')

    if not os.path.exists(file.path):
        abort(404)

    try:
        directory = os.path.dirname(file.path)
        filename = os.path.basename(file.path)

        response = send_from_directory(
            directory,
            filename,
            as_attachment=False,
            mimetype=mimetype
        )

        # Cache trong 30p
        response.headers['Cache-Control'] = 'public, max-age=1800'

        # Thêm header CORS để viewer bên ngoài truy cập được
        response.headers['Access-Control-Allow-Origin'] = '*'

        return response
    except Exception as e:
        abort(500)


@bp.route('/<int:file_id>/delete', methods=['POST'])
@login_required
@role_required(['director', 'manager'])
def delete_file(file_id):
    file = File.query.get_or_404(file_id)

    # Only uploader or director can delete
    if current_user.role != 'director' and file.uploader_id != current_user.id:
        flash('Bạn không có quyền xóa file này.', 'danger')
        return redirect(url_for('files.list_files'))

    # Delete physical file
    try:
        if os.path.exists(file.path):
            os.remove(file.path)
    except Exception as e:
        flash(f'Lỗi khi xóa file: {str(e)}', 'danger')
        return redirect(url_for('files.list_files'))

    # Delete from database
    db.session.delete(file)
    db.session.commit()

    flash('Đã xóa file thành công.', 'success')
    return redirect(url_for('files.list_files'))


# Error handler for file too large
@bp.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    max_size_mb = current_app.config['MAX_CONTENT_LENGTH'] / (1024 * 1024)
    flash(f'File quá lớn! Kích thước tối đa cho phép: {max_size_mb:.0f}MB', 'danger')
    return redirect(url_for('files.upload_file'))