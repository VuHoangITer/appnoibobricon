// ============================================
// CSRF TOKEN - SAFE GETTER
// ============================================
function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (!meta) {
        console.error('CSRF token meta tag not found');
        return '';
    }
    return meta.content;
}

// ============================================
// HÀM HỖ TRỢ: XỬ LÝ RESPONSE JSON AN TOÀN
// ============================================
async function handleResponse(response) {
    // Lấy text trước để debug
    const text = await response.text();
    console.log('Response status:', response.status);
    console.log('Response text:', text);

    // Kiểm tra response có OK không (status 200-299)
    if (!response.ok) {
        // Thử parse JSON để lấy error message
        try {
            const errorData = JSON.parse(text);
            throw new Error(errorData.error || errorData.message || `Lỗi ${response.status}: ${response.statusText}`);
        } catch (e) {
            // Nếu không parse được JSON, hiển thị raw text
            throw new Error(`Lỗi ${response.status}: ${text || response.statusText}`);
        }
    }

    // Parse JSON response nếu OK
    try {
        return JSON.parse(text);
    } catch (e) {
        throw new Error('Server không trả về JSON hợp lệ: ' + text);
    }
}

// ========================================
// COUNTDOWN TIMER
// ========================================
function startCountdowns() {
    const countdownElements = document.querySelectorAll('.task-countdown');

    countdownElements.forEach(element => {
        const dueDate = new Date(element.dataset.dueDate);
        const timerDisplay = element.querySelector('.countdown-timer');

        function updateCountdown() {
            const now = new Date();
            const diff = dueDate - now;

            // ===== XỬ LÝ KHI QUÁ HẠN: HIỂN THỊ THỜI GIAN ÂM =====
            if (diff <= 0) {
                const overdueDiff = Math.abs(diff);

                const days = Math.floor(overdueDiff / (1000 * 60 * 60 * 24));
                const hours = Math.floor((overdueDiff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                const minutes = Math.floor((overdueDiff % (1000 * 60 * 60)) / (1000 * 60));
                const seconds = Math.floor((overdueDiff % (1000 * 60)) / 1000);

                let timeString = '-';
                if (days > 0) {
                    timeString += `${days}d:${String(hours).padStart(2, '0')}h:${String(minutes).padStart(2, '0')}m:${String(seconds).padStart(2, '0')}s`;
                } else {
                    timeString += `${String(hours).padStart(2, '0')}h:${String(minutes).padStart(2, '0')}m:${String(seconds).padStart(2, '0')}s`;
                }

                timerDisplay.textContent = timeString;
                timerDisplay.classList.add('overdue');
                element.style.background = '#f8d7da';
                element.style.borderColor = '#f5c2c7';
                return;
            }

            // ===== XỬ LÝ KHI CÒN HẠN: HIỂN THỊ BÌNH THƯỜNG =====
            const days = Math.floor(diff / (1000 * 60 * 60 * 24));
            const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((diff % (1000 * 60)) / 1000);

            let timeString = '';
            if (days > 0) {
                timeString = `${days}d:${String(hours).padStart(2, '0')}h:${String(minutes).padStart(2, '0')}m:${String(seconds).padStart(2, '0')}s`;
            } else {
                timeString = `${String(hours).padStart(2, '0')}h:${String(minutes).padStart(2, '0')}m:${String(seconds).padStart(2, '0')}s`;
            }

            timerDisplay.textContent = timeString;
        }

        updateCountdown();
        setInterval(updateCountdown, 1000);
    });
}

// ============================================================
// FILTER THEO TIN NHẮN CHƯA ĐỌC
// ============================================================
let unreadFilterActive = false;

function toggleUnreadFilter() {
    const summary = document.getElementById('unreadSummary');
    const cards = document.querySelectorAll('.task-card');

    unreadFilterActive = !unreadFilterActive;

    if (unreadFilterActive) {
        summary.classList.add('active');
        currentFilter = null;
        document.querySelectorAll('[data-filter]').forEach(btn => {
            btn.classList.remove('active');
        });

        cards.forEach(card => {
            if (card.dataset.hasUnread === 'true') {
                card.style.display = 'flex';
            } else {
                card.style.display = 'none';
            }
        });
    } else {
        summary.classList.remove('active');
        cards.forEach(card => {
            card.style.display = 'flex';
        });
    }
}

// ========================================
// FILTER TASKS
// ========================================
let currentFilter = null;

function toggleFilter(filterType) {
    if (unreadFilterActive) {
        unreadFilterActive = false;
        const summary = document.getElementById('unreadSummary');
        if (summary) {
            summary.classList.remove('active');
        }
    }

    const buttons = document.querySelectorAll('[data-filter]');
    const cards = document.querySelectorAll('.task-card');

    if (currentFilter === filterType) {
        currentFilter = null;
        buttons.forEach(btn => btn.classList.remove('active'));
        cards.forEach(card => card.style.display = 'flex');
    } else {
        currentFilter = filterType;

        buttons.forEach(btn => {
            if (btn.dataset.filter === filterType) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        cards.forEach(card => {
            const header = card.querySelector('.task-card-header');
            const cardRating = card.dataset.rating;
            let shouldShow = false;

            if (filterType === 'overdue') {
                shouldShow = header.classList.contains('overdue');
            } else if (filterType === 'on-time') {
                shouldShow = header.classList.contains('on-time');
            } else if (filterType === 'rated-good') {
                shouldShow = (cardRating === 'good');
            } else if (filterType === 'rated-bad') {
                shouldShow = (cardRating === 'bad');
            }

            card.style.display = shouldShow ? 'flex' : 'none';
        });
    }
}

// ========================================
// QUICK UPDATE STATUS - ĐÃ SỬA LỖI
// ========================================
async function quickUpdateStatus(taskId, newStatus) {
    const btn = event.target.closest('button');
    const originalHTML = btn.innerHTML;

    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Đang xử lý...';

    try {
        const response = await fetch(`/tasks/${taskId}/quick-update-status`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({ status: newStatus })
        });

        const data = await handleResponse(response);

        if (data.success) {
            location.reload();
        } else {
            alert('Lỗi: ' + (data.error || 'Không thể cập nhật'));
            btn.disabled = false;
            btn.innerHTML = originalHTML;
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Có lỗi xảy ra: ' + error.message + '\nVui lòng kiểm tra console để biết thêm chi tiết.');
        btn.disabled = false;
        btn.innerHTML = originalHTML;
    }
}

// ========================================
// QUICK RATE TASK - ĐÃ SỬA LỖI
// ========================================
async function quickRateTask(taskId, rating) {
    try {
        const response = await fetch(`/tasks/${taskId}/quick-rate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({ rating: rating })
        });

        const data = await handleResponse(response);

        if (data.success) {
            location.reload();
        } else {
            alert('Lỗi: ' + (data.error || 'Không thể đánh giá'));
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Có lỗi xảy ra: ' + error.message);
    }
}

// ========================================
// RATING MODAL
// ========================================
let currentRatingTaskId = null;

function showRatingModal(taskId) {
    currentRatingTaskId = taskId;
    const modal = document.getElementById('ratingModal');
    modal.classList.add('show');
    document.body.style.overflow = 'hidden';
}

function closeRatingModal() {
    const modal = document.getElementById('ratingModal');
    modal.classList.remove('show');
    document.body.style.overflow = '';
    currentRatingTaskId = null;
}

function selectRating(rating) {
    if (!currentRatingTaskId) return;

    quickRateTask(currentRatingTaskId, rating);
    closeRatingModal();
}

// ============================================
// CHECKLIST FUNCTIONS - ĐÃ SỬA LỖI
// ============================================
let currentChecklistTaskId = null;

function showChecklistModal(taskId, event) {
    if (event) {
        event.stopPropagation();
    }

    currentChecklistTaskId = taskId;
    const modal = document.getElementById('checklistModal');

    // Load checklist items
    loadChecklistItems(taskId);

    modal.classList.add('show');
    document.body.style.overflow = 'hidden';
}

function closeChecklistModal() {
    const modal = document.getElementById('checklistModal');
    modal.classList.remove('show');
    document.body.style.overflow = '';
    currentChecklistTaskId = null;
}

async function loadChecklistItems(taskId) {
    const container = document.getElementById('checklistModalBody');
    container.innerHTML = '<div style="text-align: center; padding: 20px;"><i class="bi bi-hourglass-split"></i> Đang tải...</div>';

    try {
        const response = await fetch(`/tasks/${taskId}/checklists`);
        const data = await handleResponse(response);

        if (data.success) {
            renderChecklistItems(data.checklists, data.can_manage);
        } else {
            container.innerHTML = '<div style="text-align: center; padding: 20px; color: #dc3545;">Không thể tải checklist</div>';
        }
    } catch (error) {
        console.error('Error:', error);
        container.innerHTML = `<div style="text-align: center; padding: 20px; color: #dc3545;">Có lỗi xảy ra: ${error.message}</div>`;
    }
}

function renderChecklistItems(checklists, canManage) {
    const container = document.getElementById('checklistModalBody');

    if (!checklists || checklists.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 40px; color: #6c757d;">
                <i class="bi bi-inbox" style="font-size: 3rem;"></i>
                <p style="margin-top: 10px;">Nhiệm vụ này chưa có checklist</p>
            </div>
        `;
        return;
    }

    const itemsHTML = checklists.map(item => {
        let statusBadge = '';
        let actionButtons = '';
        let rejectionHTML = '';

        // Status badge
        if (item.status === 'APPROVED') {
            statusBadge = '<span class="checklist-item-status approved"><i class="bi bi-check-circle-fill"></i> Đã duyệt</span>';
        } else if (item.status === 'WAITING_APPROVAL') {
            statusBadge = '<span class="checklist-item-status waiting_approval"><i class="bi bi-clock-fill"></i> Chờ duyệt</span>';
        } else if (item.status === 'REJECTED') {
            statusBadge = '<span class="checklist-item-status rejected"><i class="bi bi-x-circle-fill"></i> Từ chối</span>';
            if (item.rejection_reason) {
                rejectionHTML = `
                    <div class="checklist-item-rejection">
                        <strong>Lý do từ chối:</strong>
                        ${item.rejection_reason}
                    </div>
                `;
            }
        } else {
            statusBadge = '<span class="checklist-item-status pending"><i class="bi bi-circle"></i> Chưa làm</span>';
        }

        // Action buttons
        if (item.status === 'PENDING' && item.can_complete) {
            actionButtons = `
                <div class="checklist-item-actions">
                    <button class="checklist-action-btn btn-complete"
                            onclick="completeChecklistItem(${item.id})">
                        <i class="bi bi-check-lg"></i>
                        Hoàn thành
                    </button>
                </div>
            `;
        } else if (item.status === 'WAITING_APPROVAL' && canManage) {
            actionButtons = `
                <div class="checklist-item-actions">
                    <button class="checklist-action-btn btn-approve"
                            onclick="approveChecklistItem(${item.id}, 'approve')">
                        <i class="bi bi-check-lg"></i>
                        Duyệt
                    </button>
                    <button class="checklist-action-btn btn-reject"
                            onclick="rejectChecklistItem(${item.id})">
                        <i class="bi bi-x-lg"></i>
                        Từ chối
                    </button>
                </div>
            `;
        } else if (item.status === 'REJECTED' && item.can_complete) {
            actionButtons = `
                <div class="checklist-item-actions">
                    <button class="checklist-action-btn btn-reset"
                            onclick="resetChecklistItem(${item.id})">
                        <i class="bi bi-arrow-counterclockwise"></i>
                        Làm lại
                    </button>
                </div>
            `;
        }

        return `
            <div class="checklist-item ${item.status.toLowerCase()}" data-checklist-id="${item.id}">
                <div class="checklist-item-header">
                    <div class="checklist-item-content">
                        <div class="checklist-item-title">${item.title}</div>
                        ${item.description ? `<div class="checklist-item-description">${item.description}</div>` : ''}
                    </div>
                    ${statusBadge}
                </div>
                ${rejectionHTML}
                ${actionButtons}
            </div>
        `;
    }).join('');

    container.innerHTML = `<div class="checklist-items">${itemsHTML}</div>`;
}

async function completeChecklistItem(checklistId) {
    const btn = event.target.closest('button');
    const originalHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Đang xử lý...';

    try {
        const response = await fetch(`/tasks/${currentChecklistTaskId}/checklist/complete`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({ checklist_id: checklistId })
        });

        const data = await handleResponse(response);

        if (data.success) {
            loadChecklistItems(currentChecklistTaskId);
            setTimeout(() => location.reload(), 1000);
        } else {
            alert('Lỗi: ' + (data.error || 'Không thể xử lý'));
            btn.disabled = false;
            btn.innerHTML = originalHTML;
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Có lỗi xảy ra: ' + error.message);
        btn.disabled = false;
        btn.innerHTML = originalHTML;
    }
}

async function approveChecklistItem(checklistId, action) {
    const btn = event.target.closest('button');
    const originalHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Đang xử lý...';

    try {
        const response = await fetch(`/tasks/${currentChecklistTaskId}/checklist/approve`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                checklist_id: checklistId,
                action: action
            })
        });

        const data = await handleResponse(response);

        if (data.success) {
            loadChecklistItems(currentChecklistTaskId);
            setTimeout(() => location.reload(), 1000);
        } else {
            alert('Lỗi: ' + (data.error || 'Không thể xử lý'));
            btn.disabled = false;
            btn.innerHTML = originalHTML;
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Có lỗi xảy ra: ' + error.message);
        btn.disabled = false;
        btn.innerHTML = originalHTML;
    }
}

async function rejectChecklistItem(checklistId) {
    const reason = prompt('Nhập lý do từ chối (tùy chọn):');

    if (reason === null) return;

    const btn = event.target.closest('button');
    const originalHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Đang xử lý...';

    try {
        const response = await fetch(`/tasks/${currentChecklistTaskId}/checklist/approve`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                checklist_id: checklistId,
                action: 'reject',
                rejection_reason: reason || ''
            })
        });

        const data = await handleResponse(response);

        if (data.success) {
            loadChecklistItems(currentChecklistTaskId);
            setTimeout(() => location.reload(), 1000);
        } else {
            alert('Lỗi: ' + (data.error || 'Không thể xử lý'));
            btn.disabled = false;
            btn.innerHTML = originalHTML;
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Có lỗi xảy ra: ' + error.message);
        btn.disabled = false;
        btn.innerHTML = originalHTML;
    }
}

async function resetChecklistItem(checklistId) {
    if (!confirm('Bạn muốn làm lại checklist này?')) return;

    const btn = event.target.closest('button');
    const originalHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Đang xử lý...';

    try {
        const response = await fetch(`/tasks/${currentChecklistTaskId}/checklist/reset`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({ checklist_id: checklistId })
        });

        const data = await handleResponse(response);

        if (data.success) {
            loadChecklistItems(currentChecklistTaskId);
        } else {
            alert('Lỗi: ' + (data.error || 'Không thể xử lý'));
            btn.disabled = false;
            btn.innerHTML = originalHTML;
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Có lỗi xảy ra: ' + error.message);
        btn.disabled = false;
        btn.innerHTML = originalHTML;
    }
}

// ========================================
// EVENT LISTENERS
// ========================================
document.addEventListener('click', function(e) {
    // Close rating modal khi click bên ngoài
    const ratingModal = document.getElementById('ratingModal');
    if (e.target === ratingModal) {
        closeRatingModal();
    }

    // Close checklist modal khi click bên ngoài
    const checklistModal = document.getElementById('checklistModal');
    if (e.target === checklistModal) {
        closeChecklistModal();
    }
});

// ========================================
// INIT
// ========================================
document.addEventListener('DOMContentLoaded', function() {
    startCountdowns();
});