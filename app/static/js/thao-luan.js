// thao-luan.js - Pure JavaScript (NO Jinja2 templates)
// CONFIG sẽ được define trong HTML template

let lastTimestamp = 0;
let knownCommentIds = new Set();
let isFirstPoll = true;

// ============================================
// GLOBAL VARIABLE TO TRACK SELECTED FILES
// ============================================
let selectedFiles = []; // Array to hold File objects

// DOM elements (will be initialized in DOMContentLoaded)
let commentsList;
let commentInput;
let btnAddComment;
let commentsCount;
let commentFileInput;
let filePreview;
let filePreviewName;
let filePreviewSize;
let imagePreview;

// ============================================
// INITIALIZE DOM ELEMENTS
// ============================================
function initializeDOMElements() {
    commentsList = document.getElementById('commentsList');
    commentInput = document.getElementById('commentInput');
    btnAddComment = document.getElementById('btnAddComment');
    commentsCount = document.getElementById('commentsCount');
    commentFileInput = document.getElementById('commentFileInput');
    filePreview = document.getElementById('filePreview');
    filePreviewName = document.getElementById('filePreviewName');
    filePreviewSize = document.getElementById('filePreviewSize');
    imagePreview = document.getElementById('imagePreview');

    // Initialize known comment IDs
    document.querySelectorAll('.comment-item[data-id]').forEach(el => {
        const id = parseInt(el.getAttribute('data-id'));
        knownCommentIds.add(id);
    });
}

// ============================================
// UPDATE ATTACH BUTTON TEXT
// ============================================
function updateAttachButtonText() {
    const attachButtonText = document.getElementById('attachButtonText');
    if (attachButtonText) {
        if (selectedFiles.length > 0) {
            attachButtonText.textContent = 'Thêm file';
        } else {
            attachButtonText.textContent = 'Đính kèm';
        }
    }
}

// ============================================
// FILE INPUT HANDLER
// ============================================
function initFileInput() {
    if (!commentFileInput) return;

    commentFileInput.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);

        if (files.length === 0) return;

        // Validate tất cả files
        for (const file of files) {
            if (!validateFile(file)) {
                // Không clear, chỉ reset input để user chọn lại
                commentFileInput.value = '';
                return;
            }
        }

        // ✅ MERGE VỚI FILES CŨ THAY VÌ REPLACE
        selectedFiles = [...selectedFiles, ...files];

        // Reset input để có thể chọn lại cùng file
        commentFileInput.value = '';

        // ✅ Update text nút đính kèm
        updateAttachButtonText();

        // HIỂN thị preview
        if (selectedFiles.length === 1) {
            const file = selectedFiles[0];
            filePreviewName.textContent = file.name;
            filePreviewSize.textContent = `(${(file.size / 1024).toFixed(1)} KB)`;

            // Preview single image
            if (file.type.startsWith('image/')) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    imagePreview.src = e.target.result;
                    imagePreview.style.display = 'block';
                    document.getElementById('multipleImagePreview').style.display = 'none';
                };
                reader.readAsDataURL(file);
            } else {
                imagePreview.style.display = 'none';
                document.getElementById('multipleImagePreview').style.display = 'none';
            }
        } else {
            // NHIỀU FILES - render grid
            renderMultipleImagePreview();
        }

        filePreview.style.display = 'block';
    });
}

// ============================================
// RENDER MULTIPLE IMAGE PREVIEW VỚI NÚT XÓA
// ============================================
function renderMultipleImagePreview() {
    const multiplePreview = document.getElementById('multipleImagePreview');
    multiplePreview.innerHTML = ''; // Clear previous

    let hasImages = false;

    selectedFiles.forEach((file, index) => {
        if (file.type.startsWith('image/')) {
            hasImages = true;

            const wrapper = document.createElement('div');
            wrapper.className = 'preview-image-wrapper';

            const img = document.createElement('img');
            const reader = new FileReader();
            reader.onload = (e) => {
                img.src = e.target.result;
            };
            reader.readAsDataURL(file);

            const removeBtn = document.createElement('div');
            removeBtn.className = 'preview-remove-btn';
            removeBtn.innerHTML = '<i class="bi bi-x"></i>';
            removeBtn.onclick = () => removeFileAtIndex(index);

            wrapper.appendChild(img);
            wrapper.appendChild(removeBtn);
            multiplePreview.appendChild(wrapper);
        }
    });

    multiplePreview.style.display = hasImages ? 'grid' : 'none';

    // ✅ Update summary với SELECTED FILES thay vì files mới
    const totalSize = selectedFiles.reduce((sum, f) => sum + f.size, 0);
    filePreviewName.textContent = `${selectedFiles.length} files đã chọn`;
    filePreviewSize.textContent = `(${(totalSize / 1024).toFixed(1)} KB)`;

    // Hide single image preview khi có nhiều files
    imagePreview.style.display = 'none';
}

// ============================================
// XÓA FILE TẠI INDEX
// ============================================
function removeFileAtIndex(index) {
    // Remove từ array
    selectedFiles.splice(index, 1);

    if (selectedFiles.length === 0) {
        // Nếu hết files thì clear hết
        clearFileInput();
        return;
    }

    // ✅ Update text nút
    updateAttachButtonText();

    // Re-render preview
    renderMultipleImagePreview();

    // Nếu chỉ còn 1 file thì chuyển sang single preview
    if (selectedFiles.length === 1) {
        const file = selectedFiles[0];
        filePreviewName.textContent = file.name;
        filePreviewSize.textContent = `(${(file.size / 1024).toFixed(1)} KB)`;

        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (e) => {
                imagePreview.src = e.target.result;
                imagePreview.style.display = 'block';
                document.getElementById('multipleImagePreview').style.display = 'none';
            };
            reader.readAsDataURL(file);
        } else {
            imagePreview.style.display = 'none';
            document.getElementById('multipleImagePreview').style.display = 'none';
        }
    }
}

function validateFile(file) {
    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp',
                         'application/pdf', 'application/msword',
                         'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                         'application/vnd.ms-excel',
                         'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         'text/plain'];

    if (!allowedTypes.includes(file.type)) {
        showToast('Loại file không được phép', 'danger');
        return false;
    }

    if (file.size > 10 * 1024 * 1024) {
        showToast('File quá lớn (tối đa 10MB)', 'danger');
        return false;
    }

    return true;
}

function clearFileInput() {
    if (commentFileInput) {
        commentFileInput.value = '';
        selectedFiles = []; // Clear global array
        filePreview.style.display = 'none';
        imagePreview.style.display = 'none';
        document.getElementById('multipleImagePreview').style.display = 'none';
        document.getElementById('multipleImagePreview').innerHTML = '';
        updateAttachButtonText();
    }
}

// ============================================
// REAL-TIME COMMENTS
// ============================================
function startRealtimeComments() {
    console.log('🚀 Starting real-time comments for task', window.CONFIG.TASK_ID);

    if (typeof window.sseManager === 'undefined') {
        console.warn('⚠️ SSE Manager not loaded, using polling fallback');
        startPollingFallback();
        return;
    }

    window.sseManager.connect(
        'task-comments',
        `/sse/tasks/${window.CONFIG.TASK_ID}/comments?last_timestamp=${lastTimestamp}`,
        {
            onOpen: () => {
                console.log('✅ SSE Task Comments connected');
            },
            onError: (error, attempts) => {
                console.error('❌ SSE Task Comments error:', error, 'attempts:', attempts);
            },
            events: {
                'new_comments': (data) => {
                    console.log('[SSE] New comments:', data);
                    handleNewComments(data);
                },
                'comments_sync': (data) => {
                    console.log('[SSE] Comments sync:', data);
                    handleCommentsSync(data);
                },
                'heartbeat': () => {
                    console.log('💓 SSE comments heartbeat');
                }
            }
        },
        {
            url: `/tasks/${window.CONFIG.TASK_ID}/comments?_t=${Date.now()}`,
            interval: 3000,
            onData: (data) => {
                console.log('[POLLING] Fallback data:', data);
                if (data.success && data.comments && data.comments.length > 0) {
                    handleNewComments(data);
                }
            }
        }
    );
}

function startPollingFallback() {
    console.log('🔄 Starting polling fallback (3s interval)');
    pollComments();
    setInterval(pollComments, 3000);
}

async function pollComments() {
    try {
        const response = await fetch(`/tasks/${window.CONFIG.TASK_ID}/comments?_t=${Date.now()}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();

        if (data.success) {
            if (isFirstPoll && data.comments && data.comments.length > 0) {
                let maxTimestamp = lastTimestamp;
                data.comments.forEach(c => {
                    if (c.created_at_timestamp) {
                        maxTimestamp = Math.max(maxTimestamp, c.created_at_timestamp);
                    }
                });
                lastTimestamp = maxTimestamp;
                isFirstPoll = false;
                return;
            }

            isFirstPoll = false;

            const newComments = data.comments.filter(c =>
                !knownCommentIds.has(c.id) && c.created_at_timestamp > lastTimestamp
            );

            if (newComments.length > 0) {
                handleNewComments({ comments: newComments, total_count: data.total });
            }

            const serverIds = new Set(data.comments.map(c => c.id));
            handleCommentsSync({ existing_ids: Array.from(serverIds), total_count: data.total });
        }
    } catch (error) {
        console.error('[POLLING] Error:', error);
    }
}

function handleNewComments(data) {
    console.log('[HANDLER] Processing', data.comments.length, 'new comments');

    data.comments.forEach(comment => {
        if (!knownCommentIds.has(comment.id)) {
            console.log('[HANDLER] Adding new comment ID:', comment.id);
            addCommentToList(comment);
            knownCommentIds.add(comment.id);

            if (comment.created_at_timestamp) {
                lastTimestamp = Math.max(lastTimestamp, comment.created_at_timestamp);
            }
        }
    });

    updateCommentsCount(data.total_count || knownCommentIds.size);
}

function handleCommentsSync(data) {
    const existingIds = new Set(data.existing_ids);

    knownCommentIds.forEach(id => {
        if (!existingIds.has(id)) {
            console.log('[HANDLER] Comment deleted:', id);
            const element = document.querySelector(`.comment-item[data-id="${id}"]`);
            if (element) {
                element.style.transition = 'opacity 0.3s';
                element.style.opacity = '0';

                setTimeout(() => {
                    element.remove();
                    knownCommentIds.delete(id);
                    updateCommentsCount(data.total_count || knownCommentIds.size);
                }, 300);
            } else {
                knownCommentIds.delete(id);
            }
        }
    });
}

function updateCommentsCount(count) {
    if (commentsCount) {
        commentsCount.textContent = `${count} tin nhắn`;
    }
}

function addComment() {
    const content = commentInput.value.trim();
    const hasFiles = selectedFiles.length > 0;

    // ✅ CHỈ CẦN CONTENT HOẶC FILE, KHÔNG CẦN CẢ 2
    if (!content && !hasFiles) {
        showToast('Vui lòng nhập nội dung hoặc đính kèm file', 'warning');
        return;
    }

    btnAddComment.disabled = true;
    btnAddComment.innerHTML = '<i class="bi bi-hourglass-split"></i>'; // ✅ CHỈ ICON

    const formData = new FormData();

    if (content) {
        formData.append('content', content);
    } else {
        // Nếu không có content, gửi một khoảng trắng để backend happy
        formData.append('content', ' ');
    }

    formData.append('csrf_token', window.CONFIG.CSRF_TOKEN);

    // ✅ SỬ DỤNG selectedFiles THAY VÌ commentFileInput.files
    if (selectedFiles.length > 0) {
        for (let i = 0; i < selectedFiles.length; i++) {
            formData.append('file', selectedFiles[i]);
        }
    }

    fetch(`/tasks/${window.CONFIG.TASK_ID}/comments`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': window.CONFIG.CSRF_TOKEN
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            commentInput.value = '';
            clearFileInput();

            addCommentToList(data.comment);
            knownCommentIds.add(data.comment.id);

            if (data.comment.created_at_timestamp) {
                lastTimestamp = Math.max(lastTimestamp, data.comment.created_at_timestamp);
            }

            updateCommentsCount(knownCommentIds.size);
            showToast('Đã gửi tin nhắn', 'success');
        } else {
            showToast(data.error || 'Lỗi gửi tin nhắn', 'danger');
        }
    })
    .catch(error => {
        console.error('❌ Error:', error);
        showToast('Có lỗi xảy ra', 'danger');
    })
    .finally(() => {
        btnAddComment.disabled = false;
        btnAddComment.innerHTML = '<i class="bi bi-send-fill"></i>'; // ✅ CHỈ ICON
    });
}

function toggleCommentTime(commentId) {
    const item = document.querySelector(`.comment-item[data-id="${commentId}"]`);
    if (!item) return;

    const timeElement = item.querySelector('.comment-time');
    if (timeElement) {
        timeElement.classList.toggle('show');
    }
}

// ============================================
// HANDLE COMMENT CLICK - CHỈ TOGGLE KHI KHÔNG PHẢI LINK
// ============================================
function handleCommentClick(event, commentId) {
    // Nếu click vào link (thẻ <a>), không làm gì
    if (event.target.tagName === 'A') {
        return; // Để link tự xử lý
    }

    // Nếu click vào chỗ khác, toggle time
    toggleCommentTime(commentId);
}

function addCommentToList(comment) {
    if (document.querySelector(`.comment-item[data-id="${comment.id}"]`)) {
        return;
    }

    const noComments = document.getElementById('noComments');
    if (noComments) noComments.remove();

    const item = document.createElement('div');
    const isMine = comment.user_id === window.CONFIG.CURRENT_USER_ID;
    item.className = `comment-item ${isMine ? 'mine' : 'other'}`;
    item.dataset.id = comment.id;

    const avatarHTML = comment.user.avatar
        ? `<img src="/profile/avatar/${comment.user.avatar}" alt="">`
        : comment.user.avatar_letter;

    // ✅ MENU 3 CHẤM (chỉ director)
    const menuBtn = (window.CONFIG.CURRENT_USER_ROLE === 'director')
        ? `<button class="comment-menu-btn" onclick="toggleCommentMenu(${comment.id}, event)">
               <i class="bi bi-three-dots"></i>
           </button>
           <div class="comment-dropdown" id="commentMenu${comment.id}">
               <button class="comment-dropdown-item delete" onclick="deleteComment(${comment.id})">
                   <i class="bi bi-trash"></i>
               </button>
           </div>`
        : '';

    // XỬ LÝ NHIỀU FILES
    let attachmentHTML = '';
    if (comment.has_attachment && comment.attachments && comment.attachments.length > 0) {
        attachmentHTML = '<div class="comment-attachment">';

        // NHÓM IMAGES VÀO GRID
        const images = comment.attachments.filter(att => att.file_type === 'image');
        const otherFiles = comment.attachments.filter(att => att.file_type !== 'image');

        // Hiển thị tất cả IMAGES trong grid
        if (images.length > 0) {
            attachmentHTML += '<div class="attachment-images-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; margin-bottom: 10px;">';

            images.forEach(att => {
                attachmentHTML += `
                    <div class="attachment-image-preview">
                        <img src="${att.download_url}"
                             alt="${escapeHtml(att.filename)}"
                             class="img-thumbnail"
                             style="width: 100%; max-height: 200px; object-fit: cover; cursor: pointer; border-radius: 8px;"
                             onclick="openLightbox('${att.download_url}', '${escapeHtml(att.filename)}', ${att.file_size})">
                    </div>
                `;
            });

            attachmentHTML += '</div>';
        }

        // Hiển thị tất cả OTHER FILES (PDF, DOC, EXCEL, etc)
        if (otherFiles.length > 0) {
            otherFiles.forEach(att => {
                const icon = att.file_type === 'pdf' ? 'file-pdf' :
                            att.file_type === 'document' ? 'file-word' :
                            att.file_type === 'spreadsheet' ? 'file-excel' :
                            'file-earmark';

                // ===== NẾU LÀ WORD/EXCEL → PREVIEW (chuyển trang) =====
                // ===== NẾU LÀ FILE KHÁC → DOWNLOAD (mở tab mới) =====
                const fileUrl = (att.file_type === 'document' || att.file_type === 'spreadsheet')
                    ? `/tasks/${window.CONFIG.TASK_ID}/comments/${comment.id}/attachments/${att.id}/preview`
                    : att.download_url;

                const targetAttr = (att.file_type === 'document' || att.file_type === 'spreadsheet')
                    ? '' // KHÔNG mở tab mới cho Word/Excel
                    : 'target="_blank"'; // Mở tab mới cho PDF/file khác

                attachmentHTML += `
                    <div class="attachment-info mt-2">
                        <div>
                            <a href="${fileUrl}" class="btn btn-sm btn-outline-primary" ${targetAttr}>
                                <i class="bi bi-${icon}"></i>
                                ${escapeHtml(att.filename)}
                            </a>
                        </div>
                        <small class="text-muted">(${(att.file_size / 1024).toFixed(1)} KB)</small>
                    </div>
                `;
            });
        }

        attachmentHTML += '</div>';
    }

    item.innerHTML = `
        <div class="comment-avatar">${avatarHTML}</div>
        <div class="comment-content">
            ${menuBtn}
            <div class="comment-header">
                <div>
                    <span class="comment-author">${escapeHtml(comment.user.full_name)}</span>
                </div>
                <div class="d-flex align-items-center gap-2">
                    <span class="comment-time">${comment.created_at_display}</span>
                </div>
            </div>
            <div class="comment-text" onclick="handleCommentClick(event, ${comment.id})">${linkifyText(comment.content)}</div>
            ${attachmentHTML}
        </div>
    `;

    commentsList.appendChild(item);
    commentsList.scrollTop = commentsList.scrollHeight;
    initLongPressListeners();
}

function deleteComment(commentId) {
    // Đóng menu trước khi xóa
    const menu = document.getElementById(`commentMenu${commentId}`);
    if (menu) {
        menu.classList.remove('show');
    }

    fetch(`/tasks/${window.CONFIG.TASK_ID}/comments/${commentId}`, {
        method: 'DELETE',
        headers: {
            'X-CSRFToken': window.CONFIG.CSRF_TOKEN
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const item = document.querySelector(`.comment-item[data-id="${commentId}"]`);
            if (item) {
                item.style.transition = 'opacity 0.3s';
                item.style.opacity = '0';

                setTimeout(() => {
                    item.remove();
                    knownCommentIds.delete(commentId);
                    updateCommentsCount(knownCommentIds.size);
                }, 300);
            }
            showToast('Đã xóa tin nhắn', 'success');
        } else {
            showToast(data.error || 'Lỗi xóa tin nhắn', 'danger');
        }
    })
    .catch(error => {
        console.error('Error deleting comment:', error);
        showToast('Có lỗi xảy ra', 'danger');
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} position-fixed top-0 end-0 m-3`;
    toast.style.zIndex = '9999';
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// ============================================
// CLEANUP
// ============================================
window.addEventListener('beforeunload', () => {
    console.log('🚪 Discussion page unloading - disconnecting SSE');
    if (window.sseManager) {
        window.sseManager.disconnect('task-comments');
    }
});

window.addEventListener('pagehide', () => {
    console.log('🚪 Discussion page hiding - disconnecting SSE');
    if (window.sseManager) {
        window.sseManager.disconnect('task-comments');
    }
});

// ============================================
// LONG PRESS TO DELETE (MOBILE)
// ============================================
let longPressTimer = null;
let longPressCommentId = null;
let isScrolling = false;
let scrollTimeout = null;

function initLongPressListeners() {
    const isMobile = window.matchMedia('(max-width: 768px)').matches;

    if (!isMobile) return; // Chỉ áp dụng cho mobile

    // ===== CHỈ DIRECTOR MỚI CÓ LONG-PRESS DELETE =====
    if (window.CONFIG.CURRENT_USER_ROLE !== 'director') {
        return; // Không phải director thì không setup long-press
    }

    // QUAN TRỌNG: Xóa tất cả listeners cũ trước khi gắn mới
    document.querySelectorAll('.comment-item').forEach(item => {
        // Clone node để xóa tất cả event listeners
        const newItem = item.cloneNode(true);
        item.parentNode.replaceChild(newItem, item);
    });

    // Detect scrolling
    const commentsList = document.getElementById('commentsList');
    if (commentsList) {
        commentsList.addEventListener('scroll', () => {
            isScrolling = true;

            // Clear timer nếu đang scroll
            if (longPressTimer) {
                clearTimeout(longPressTimer);
                longPressTimer = null;
            }

            // Reset scroll state sau 150ms
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                isScrolling = false;
            }, 150);
        }, { passive: true });
    }

    // Gắn listeners MỚI - DIRECTOR CÓ THỂ XÓA TẤT CẢ COMMENTS
    document.querySelectorAll('.comment-item').forEach(item => {
        const commentId = parseInt(item.dataset.id);
        let touchStartY = 0;
        let hasMoved = false;

        // Touch start
        const handleTouchStart = (e) => {
            // Không làm gì nếu đang scroll
            if (isScrolling) return;

            touchStartY = e.touches[0].clientY;
            hasMoved = false;
            longPressCommentId = commentId;
            item.classList.add('long-pressing');

            longPressTimer = setTimeout(() => {
                // Chỉ show modal nếu KHÔNG di chuyển và KHÔNG scroll
                if (!hasMoved && !isScrolling) {
                    showDeleteModal(commentId);
                }
                item.classList.remove('long-pressing');
                longPressTimer = null;
            }, 500);
        };

        // Touch move - detect scroll
        const handleTouchMove = (e) => {
            const touchY = e.touches[0].clientY;
            const deltaY = Math.abs(touchY - touchStartY);

            // Nếu di chuyển > 10px thì coi như scroll
            if (deltaY > 10) {
                hasMoved = true;
                isScrolling = true;
            }

            if (longPressTimer && (hasMoved || isScrolling)) {
                clearTimeout(longPressTimer);
                longPressTimer = null;
                item.classList.remove('long-pressing');
            }
        };

        // Touch end
        const handleTouchEnd = () => {
            if (longPressTimer) {
                clearTimeout(longPressTimer);
                longPressTimer = null;
            }
            item.classList.remove('long-pressing');

            // Reset hasMoved sau 100ms
            setTimeout(() => {
                hasMoved = false;
            }, 100);
        };

        // Touch cancel
        const handleTouchCancel = () => {
            if (longPressTimer) {
                clearTimeout(longPressTimer);
                longPressTimer = null;
            }
            item.classList.remove('long-pressing');
            hasMoved = false;
        };

        // Gắn events với passive: false để có thể preventDefault nếu cần
        item.addEventListener('touchstart', handleTouchStart, { passive: true });
        item.addEventListener('touchmove', handleTouchMove, { passive: true });
        item.addEventListener('touchend', handleTouchEnd, { passive: true });
        item.addEventListener('touchcancel', handleTouchCancel, { passive: true });
    });
}

function showDeleteModal(commentId) {
    // Remove existing modal if any
    const existingModal = document.getElementById('deleteModal');
    if (existingModal) {
        existingModal.remove();
    }

    // Create modal
    const modal = document.createElement('div');
    modal.id = 'deleteModal';
    modal.className = 'delete-modal';
    modal.innerHTML = `
        <div class="delete-modal-content">
            <div class="delete-modal-header">
                <i class="bi bi-trash3"></i>
                <h3 class="delete-modal-title">Xóa tin nhắn?</h3>
            </div>
            <div class="delete-modal-actions">
                <button class="delete-modal-btn delete-modal-btn-cancel" onclick="closeDeleteModal()">
                    Hủy
                </button>
                <button class="delete-modal-btn delete-modal-btn-delete" onclick="confirmDeleteComment(${commentId})">
                    Xóa
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    // Show with animation
    setTimeout(() => {
        modal.classList.add('show');
    }, 10);

    // Close on backdrop click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeDeleteModal();
        }
    });
}

function closeDeleteModal() {
    const modal = document.getElementById('deleteModal');
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => {
            modal.remove();
        }, 200);
    }
}

function confirmDeleteComment(commentId) {
    closeDeleteModal();
    deleteComment(commentId);
}

// ============================================
// IMAGE LIGHTBOX FUNCTIONS
// ============================================
function openLightbox(imageUrl, filename, fileSize) {
    const overlay = document.getElementById('imageLightbox');
    const img = document.getElementById('lightboxImage');
    const info = document.getElementById('lightboxInfo');
    const downloadBtn = document.getElementById('lightboxDownload');

    overlay.classList.add('show');
    document.body.style.overflow = 'hidden';

    img.src = imageUrl;
    info.textContent = `${filename} • ${(fileSize / 1024).toFixed(1)} KB`;

    downloadBtn.onclick = (e) => {
        e.stopPropagation();
        window.open(imageUrl, '_blank');
    };
}

function closeLightbox() {
    document.getElementById('imageLightbox').classList.remove('show');
    document.body.style.overflow = '';
}

// ============================================
// COMMENT MENU FUNCTIONS (3 DOTS - DESKTOP ONLY)
// ============================================

// Toggle comment menu dropdown
function toggleCommentMenu(commentId, event) {
    event.stopPropagation();

    const menu = document.getElementById(`commentMenu${commentId}`);

    // Đóng tất cả menu khác
    document.querySelectorAll('.comment-dropdown').forEach(m => {
        if (m.id !== `commentMenu${commentId}`) {
            m.classList.remove('show');
        }
    });

    // Toggle menu hiện tại
    menu.classList.toggle('show');
}

// Đóng menu khi click ra ngoài
document.addEventListener('click', function(event) {
    if (!event.target.closest('.comment-menu-btn') && !event.target.closest('.comment-dropdown')) {
        document.querySelectorAll('.comment-dropdown').forEach(menu => {
            menu.classList.remove('show');
        });
    }
});

// ============================================
// INIT
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Task Discussion Page Loaded');

    // Initialize DOM elements first
    initializeDOMElements();

    // Initialize file input handler
    initFileInput();

    // Start real-time comments
    startRealtimeComments();

    // Initialize long press listeners
    initLongPressListeners();

    // Setup event listeners
    if (commentInput) {
        commentInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                addComment();
            }
        });
    }

    const commentForm = document.getElementById('commentForm');
    if (commentForm) {
        commentForm.addEventListener('submit', (e) => {
            e.preventDefault();
            addComment();
        });
    }

    // Lightbox events
    const lightbox = document.getElementById('imageLightbox');
    if (lightbox) {
        lightbox.addEventListener('click', function(e) {
            if (e.target === this) closeLightbox();
        });
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeLightbox();
    });

    // Auto scroll to bottom
    if (commentsList) {
        commentsList.scrollTop = commentsList.scrollHeight;
    }

    // Init dropdown menu items
    document.querySelectorAll('.comment-dropdown-item').forEach(item => {
        item.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    });
});

// ============================================
// DRAG & DROP FILE UPLOAD
// ============================================
function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    const commentsList = document.getElementById('commentsList');
    commentsList.classList.add('drag-over');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();

    // Only remove if leaving the comments-body itself
    const commentsList = document.getElementById('commentsList');
    const rect = commentsList.getBoundingClientRect();

    if (
        e.clientX <= rect.left ||
        e.clientX >= rect.right ||
        e.clientY <= rect.top ||
        e.clientY >= rect.bottom
    ) {
        commentsList.classList.remove('drag-over');
    }
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();

    const commentsList = document.getElementById('commentsList');
    commentsList.classList.remove('drag-over');

    const files = e.dataTransfer.files;

    if (files.length === 0) {
        return;
    }

    // Validate files
    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp',
                          'application/pdf',
                          'application/msword',
                          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                          'application/vnd.ms-excel',
                          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                          'text/plain'];

    const maxSize = 10 * 1024 * 1024; // 10MB

    for (let file of files) {
        if (!allowedTypes.includes(file.type)) {
            showToast(`❌ File "${file.name}" không được phép`, 'danger');
            return;
        }

        if (file.size > maxSize) {
            showToast(`❌ File "${file.name}" quá lớn (max 10MB)`, 'danger');
            return;
        }
    }

    // Set files to input
    const fileInput = document.getElementById('commentFileInput');
    fileInput.files = files;

    // Trigger change event to show preview
    const changeEvent = new Event('change', { bubbles: true });
    fileInput.dispatchEvent(changeEvent);

    showToast(`✅ Đã chọn ${files.length} file`, 'success');
}

// ============================================
// AUTO-LINKIFY COMMENT TEXT
// ============================================
function linkifyText(text) {
    // URL regex pattern
    const urlPattern = /(https?:\/\/[^\s]+)/g;

    return text.replace(urlPattern, function(url) {
        // Remove trailing punctuation
        let cleanUrl = url.replace(/[.,;:!?]+$/, '');
        return `<a href="${cleanUrl}" target="_blank" rel="noopener noreferrer">${cleanUrl}</a>`;
    });
}

// ============================================
// PWA EXTERNAL LINK HANDLER
// ============================================
// Detect if running in PWA mode
const isPWA = window.matchMedia('(display-mode: standalone)').matches ||
              window.navigator.standalone === true;

if (isPWA) {
    // Intercept all external links
    document.addEventListener('click', function(e) {
        const link = e.target.closest('a');

        if (link && link.hostname !== window.location.hostname) {
            e.preventDefault();

            // Open in system browser
            if (window.navigator && window.navigator.share) {
                // For mobile PWA - open in default browser
                window.open(link.href, '_blank');
            } else {
                // For desktop PWA
                window.open(link.href, '_blank', 'noopener,noreferrer');
            }
        }
    });
}