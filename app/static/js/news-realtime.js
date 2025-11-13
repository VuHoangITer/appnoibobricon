/**
 * Real-time comments using Socket.IO
 */

// Lấy news_id từ URL
const newsId = window.location.pathname.split('/')[2];
const currentUserId = parseInt(document.body.dataset.userId || '0');
const currentUserRole = document.body.dataset.userRole || '';

// Kết nối Socket.IO
const socket = io({
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionAttempts: 5
});

// Event: Kết nối thành công
socket.on('connect', function() {
    console.log('✅ Connected to server');
    // Join vào room của bài đăng này
    socket.emit('join_news', { news_id: newsId });
});

// Event: Join room thành công
socket.on('joined', function(data) {
    console.log('👥 Joined news room:', data.news_id);
});

// Event: Mất kết nối
socket.on('disconnect', function() {
    console.log('❌ Disconnected from server');
});

// Event: Lỗi kết nối
socket.on('connect_error', function(error) {
    console.error('⚠️ Connection error:', error);
});

// ========== LISTEN REAL-TIME EVENTS ==========

// Event: Comment mới được thêm
socket.on('comment_added', function(data) {
    console.log('📢 New comment received:', data);
    addCommentToDOM(data);
});

// Event: Comment bị xóa
socket.on('comment_deleted', function(data) {
    console.log('📢 Comment deleted:', data.comment_id);
    removeCommentFromDOM(data.comment_id);
});

// ========== DOM MANIPULATION ==========

/**
 * Thêm comment vào DOM
 */
function addCommentToDOM(commentData) {
    const commentsList = document.querySelector('.comments-list');
    const noCommentsMsg = document.querySelector('.text-center.news-mb-2');

    // Xóa message "Chưa có bình luận" nếu có
    if (noCommentsMsg) {
        noCommentsMsg.remove();
    }

    // Kiểm tra xem comment đã tồn tại chưa (tránh duplicate)
    if (document.getElementById(`comment-${commentData.id}`)) {
        console.log('Comment already exists, skipping...');
        return;
    }

    // Tạo HTML cho comment mới
    const canDelete = commentData.user_id === currentUserId || currentUserRole === 'director';
    const deleteButton = canDelete ? `
        <form method="POST"
              action="/news/comment/${commentData.id}/delete"
              onsubmit="return handleDeleteComment(event, ${commentData.id});"
              style="display: inline;">
            <input type="hidden" name="csrf_token" value="${getCSRFToken()}"/>
            <button type="submit" class="btn btn-link text-danger news-p-0" style="font-size: 0.85rem;">
                <i class="bi bi-trash"></i>
            </button>
        </form>
    ` : '';

    const commentHTML = `
        <div class="news-comment" id="comment-${commentData.id}">
            <div class="d-flex gap-2">
                <div class="news-avatar small">
                    ${commentData.author_initial}
                </div>
                <div class="flex-grow-1">
                    <div class="news-comment-bubble">
                        <div class="d-flex justify-content-between align-items-start news-mb-1">
                            <div>
                                <strong style="font-size: 0.85rem;">${commentData.author_name}</strong>
                                <span class="news-badge" style="font-size: 0.65rem; margin-left: 0.25rem;">
                                    ${getRoleVN(commentData.author_role)}
                                </span>
                            </div>
                            ${deleteButton}
                        </div>
                        <p class="news-comment-content">${escapeHtml(commentData.content)}</p>
                    </div>
                    <small style="color: var(--news-text-muted); font-size: 0.7rem; margin-left: 0.5rem;">
                        <i class="bi bi-clock"></i> ${commentData.created_at}
                    </small>
                </div>
            </div>
        </div>
    `;

    // Tạo element từ HTML
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = commentHTML.trim();
    const commentElement = tempDiv.firstChild;

    // Thêm vào đầu danh sách comments
    if (commentsList) {
        commentsList.insertBefore(commentElement, commentsList.firstChild);
    } else {
        // Tạo comments-list mới nếu chưa có
        const newCommentsList = document.createElement('div');
        newCommentsList.className = 'comments-list';
        newCommentsList.appendChild(commentElement);

        const cardBody = document.querySelector('.news-card-body');
        cardBody.appendChild(newCommentsList);
    }

    // Animation: fade in
    commentElement.style.opacity = '0';
    setTimeout(() => {
        commentElement.style.transition = 'opacity 0.3s ease-in';
        commentElement.style.opacity = '1';
    }, 10);

    // Cập nhật counter
    updateCommentCount(1);
}

/**
 * Xóa comment khỏi DOM
 */
function removeCommentFromDOM(commentId) {
    const commentElement = document.getElementById(`comment-${commentId}`);
    if (commentElement) {
        // Animation: fade out
        commentElement.style.transition = 'opacity 0.3s ease-out';
        commentElement.style.opacity = '0';

        setTimeout(() => {
            commentElement.remove();

            // Kiểm tra nếu không còn comment nào
            const commentsList = document.querySelector('.comments-list');
            if (commentsList && commentsList.children.length === 0) {
                const noCommentsMsg = `
                    <p class="text-center news-mb-2" style="color: var(--news-text-muted); font-size: 0.85rem;">
                        Chưa có bình luận nào. Hãy là người đầu tiên!
                    </p>
                `;
                commentsList.insertAdjacentHTML('afterend', noCommentsMsg);
                commentsList.remove();
            }

            // Cập nhật counter
            updateCommentCount(-1);
        }, 300);
    }
}

// ========== FORM HANDLERS ==========

/**
 * Xử lý submit form thêm comment
 */
function handleAddComment(event) {
    event.preventDefault();

    const form = event.target;
    const formData = new FormData(form);
    const submitButton = form.querySelector('button[type="submit"]');
    const textarea = form.querySelector('textarea[name="content"]');

    // Disable button để tránh spam
    submitButton.disabled = true;
    submitButton.innerHTML = '<i class="bi bi-hourglass-split"></i> Đang gửi...';

    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Clear textarea
            textarea.value = '';
            console.log('✅ Comment added successfully');
        } else {
            alert('Lỗi: ' + (data.error || 'Không thể thêm bình luận'));
        }
    })
    .catch(error => {
        console.error('❌ Error adding comment:', error);
        alert('Có lỗi xảy ra khi gửi bình luận');
    })
    .finally(() => {
        // Re-enable button
        submitButton.disabled = false;
        submitButton.innerHTML = '<i class="bi bi-send"></i> Gửi';
    });

    return false;
}

/**
 * Xử lý xóa comment
 */
function handleDeleteComment(event, commentId) {
    event.preventDefault();

    if (!confirm('Xóa bình luận này?')) {
        return false;
    }

    const form = event.target;
    const formData = new FormData(form);

    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('✅ Comment deleted successfully');
            // WebSocket sẽ tự động xóa comment khỏi DOM
        } else {
            alert('Lỗi: ' + (data.error || 'Không thể xóa bình luận'));
        }
    })
    .catch(error => {
        console.error('❌ Error deleting comment:', error);
        alert('Có lỗi xảy ra khi xóa bình luận');
    });

    return false;
}

// ========== UTILITY FUNCTIONS ==========

/**
 * Lấy CSRF token từ form
 */
function getCSRFToken() {
    const tokenInput = document.querySelector('input[name="csrf_token"]');
    return tokenInput ? tokenInput.value : '';
}

/**
 * Escape HTML để tránh XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Convert role sang tiếng Việt
 */
function getRoleVN(role) {
    const roleMap = {
        'director': 'Giám đốc',
        'manager': 'Trưởng phòng',
        'accountant': 'Kế toán',
        'hr': 'Nhân viên'
    };
    return roleMap[role] || role;
}

/**
 * Cập nhật số lượng comments trong header
 */
function updateCommentCount(delta) {
    const header = document.querySelector('.news-card-header h6');
    if (header) {
        const match = header.textContent.match(/\((\d+)\)/);
        if (match) {
            const currentCount = parseInt(match[1]);
            const newCount = Math.max(0, currentCount + delta);
            header.textContent = header.textContent.replace(/\(\d+\)/, `(${newCount})`);
        }
    }
}

// ========== INIT ==========

// Gắn event handler cho form add comment
document.addEventListener('DOMContentLoaded', function() {
    const addCommentForm = document.querySelector('form[action*="/comment"]');
    if (addCommentForm) {
        addCommentForm.onsubmit = handleAddComment;
    }

    console.log('🚀 Real-time comments initialized');
});

// Cleanup khi rời khỏi trang
window.addEventListener('beforeunload', function() {
    if (socket.connected) {
        socket.emit('leave_news', { news_id: newsId });
        socket.disconnect();
    }
});