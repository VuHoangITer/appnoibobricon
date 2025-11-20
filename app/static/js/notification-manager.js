/**
 * Real-time Notification Manager
 * Quản lý thông báo real-time với âm thanh và text-to-speech
 * VERSION 2: Dùng backend TTS API (chất lượng cao)
 */

class NotificationManager {
    constructor() {
        // Sound instance
        this.sound = new NotificationSound();

        // Audio element cho TTS
        this.audioElement = new Audio();
        this.audioElement.preload = 'auto';

        // Settings (load từ localStorage)
        this.settings = this.loadSettings();

        // Tracking
        this.lastNotificationCount = 0;
        this.seenNotificationIds = this.loadSeenIds(); // THÊM: Load từ localStorage
        this.pollingInterval = null;
        this.pollingDelay = 20000;

        // UI Elements
        this.toggleButton = null;
        this.settingsModal = null;

        this.init();
    }

    /**
     * Load settings từ localStorage
     */
    loadSettings() {
        const defaults = {
            soundEnabled: true,
            ttsEnabled: true,
            ttsSpeed: 1.0,
            readFullContent: true  // THÊM MỚI: Đọc cả nội dung (true) hay chỉ tiêu đề (false)
        };

        try {
            const saved = localStorage.getItem('notification_settings');
            return saved ? { ...defaults, ...JSON.parse(saved) } : defaults;
        } catch (e) {
            return defaults;
        }
    }

    /**
     * Save settings vào localStorage
     */
    saveSettings() {
        try {
            localStorage.setItem('notification_settings', JSON.stringify(this.settings));
        } catch (e) {
            console.error('Error saving settings:', e);
        }
    }

    /**
     * Load seen notification IDs từ localStorage
     */
    loadSeenIds() {
        try {
            const saved = localStorage.getItem('seen_notification_ids');
            if (saved) {
                const ids = JSON.parse(saved);
                console.log('✅ Loaded seen IDs từ localStorage:', ids);
                return new Set(ids);
            }
        } catch (e) {
            console.error('Error loading seen IDs:', e);
        }
        return new Set();
    }

    /**
     * Save seen notification IDs vào localStorage
     */
    saveSeenIds() {
        try {
            const ids = Array.from(this.seenNotificationIds);
            localStorage.setItem('seen_notification_ids', JSON.stringify(ids));
            console.log('💾 Saved seen IDs:', ids);
        } catch (e) {
            console.error('Error saving seen IDs:', e);
        }
    }

    /**
     * Khởi tạo
     */
    init() {
        // Khởi tạo sound
        this.sound.init();

        // Tạo UI
        this.createToggleButton();
        this.createSettingsModal();

        // Bắt đầu polling
        this.startPolling();

        // Cleanup khi tắt trang
        window.addEventListener('beforeunload', () => this.stopPolling());
    }

    /**
     * Tạo nút toggle ở navbar
     */
    createToggleButton() {
        const navbarRight = document.querySelector('.navbar-right');
        if (!navbarRight) return;

        // Tạo button
        const btn = document.createElement('button');
        btn.className = 'notification-btn notification-settings-btn';
        btn.innerHTML = this.getToggleIcon();
        btn.title = 'Cài đặt thông báo';
        btn.onclick = () => this.openSettings();

        // Thêm vào navbar (trước nút notification)
        const notifBtn = navbarRight.querySelector('.notification-btn');
        if (notifBtn) {
            navbarRight.insertBefore(btn, notifBtn);
        } else {
            navbarRight.appendChild(btn);
        }

        this.toggleButton = btn;
    }

    /**
     * Icon cho nút toggle (thay đổi theo trạng thái)
     */
    getToggleIcon() {
        const { soundEnabled, ttsEnabled } = this.settings;

        if (soundEnabled && ttsEnabled) {
            return '<i class="bi bi-volume-up-fill"></i>';
        } else if (soundEnabled || ttsEnabled) {
            return '<i class="bi bi-volume-down-fill"></i>';
        } else {
            return '<i class="bi bi-volume-mute-fill"></i>';
        }
    }

    /**
     * Update icon của nút toggle
     */
    updateToggleIcon() {
        if (this.toggleButton) {
            this.toggleButton.innerHTML = this.getToggleIcon();
        }
    }

    /**
     * Tạo modal cài đặt
     */
    createSettingsModal() {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = 'notificationSettingsModal';
        modal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="bi bi-gear-fill"></i> Cài đặt Thông báo
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <!-- Âm thanh "ting" -->
                        <div class="form-check form-switch mb-3">
                            <input class="form-check-input" type="checkbox" id="soundToggle" ${this.settings.soundEnabled ? 'checked' : ''}>
                            <label class="form-check-label" for="soundToggle">
                                <i class="bi bi-bell-fill"></i> Phát âm thanh "ting"
                            </label>
                        </div>

                        <!-- Text-to-Speech -->
                        <div class="form-check form-switch mb-3">
                            <input class="form-check-input" type="checkbox" id="ttsToggle" ${this.settings.ttsEnabled ? 'checked' : ''}>
                            <label class="form-check-label" for="ttsToggle">
                                <i class="bi bi-megaphone-fill"></i> Đọc tiêu đề thông báo
                            </label>
                        </div>

                        <!-- THÊM MỚI: Đọc cả nội dung -->
                        <div class="form-check form-switch mb-3 ms-4">
                            <input class="form-check-input" type="checkbox" id="readFullToggle" ${this.settings.readFullContent ? 'checked' : ''}>
                            <label class="form-check-label" for="readFullToggle">
                                <i class="bi bi-file-text"></i> Đọc cả nội dung chi tiết
                            </label>
                            <small class="text-muted d-block">Đọc cả tiêu đề lẫn nội dung thông báo</small>
                        </div>

                        <hr>

                        <!-- TTS Speed -->
                        <div class="mb-3">
                            <label for="ttsSpeed" class="form-label">
                                Tốc độ đọc: <strong id="ttsSpeedValue">${this.settings.ttsSpeed}x</strong>
                            </label>
                            <input type="range" class="form-range" id="ttsSpeed"
                                   min="0.5" max="2" step="0.1" value="${this.settings.ttsSpeed}">
                        </div>

                        <!-- Test button -->
                        <div class="d-grid gap-2">
                            <button type="button" class="btn btn-outline-primary" id="testNotification">
                                <i class="bi bi-play-circle-fill"></i> Nghe thử
                            </button>
                            <button type="button" class="btn btn-outline-secondary btn-sm" id="clearHistory">
                                <i class="bi bi-trash"></i> Nghe lại
                            </button>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <small class="text-muted">
                            <i class="bi bi-info-circle"></i> Sử dụng Google TTS chất lượng cao
                        </small>
                        <small class="text-muted ms-3" id="seenCount">
                            Đã ghi nhận: <strong>0</strong> thông báo
                        </small>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        this.settingsModal = new bootstrap.Modal(modal);

        // Event listeners
        this.attachSettingsListeners();
    }

    /**
     * Gắn event listeners cho settings modal
     */
    attachSettingsListeners() {
        // Sound toggle
        document.getElementById('soundToggle').addEventListener('change', (e) => {
            this.settings.soundEnabled = e.target.checked;
            this.saveSettings();
            this.updateToggleIcon();
        });

        // TTS toggle
        document.getElementById('ttsToggle').addEventListener('change', (e) => {
            this.settings.ttsEnabled = e.target.checked;
            this.saveSettings();
            this.updateToggleIcon();
        });

        // THÊM MỚI: Read full content toggle
        document.getElementById('readFullToggle').addEventListener('change', (e) => {
            this.settings.readFullContent = e.target.checked;
            this.saveSettings();
        });

        // TTS speed
        const speedSlider = document.getElementById('ttsSpeed');
        const speedValue = document.getElementById('ttsSpeedValue');
        speedSlider.addEventListener('input', (e) => {
            const value = parseFloat(e.target.value);
            this.settings.ttsSpeed = value;
            speedValue.textContent = value.toFixed(1) + 'x';
            this.saveSettings();
        });

        // Test button
        document.getElementById('testNotification').addEventListener('click', () => {
            this.testNotification();
        });

        // Clear history button
        document.getElementById('clearHistory').addEventListener('click', () => {
            if (confirm('Bạn muốn nghe lại? Thông báo cũ sẽ phát lại lần nữa.')) {
                this.seenNotificationIds.clear();
                this.saveSeenIds();
                this.updateSeenCount();
                this.showToast('Đã xóa lịch sử thông báo cũ', 'success');
            }
        });

        // Update seen count when modal opens
        document.getElementById('notificationSettingsModal').addEventListener('shown.bs.modal', () => {
            this.updateSeenCount();
        });
    }

    /**
     * Update số lượng thông báo đã seen trong modal
     */
    updateSeenCount() {
        const countEl = document.getElementById('seenCount');
        if (countEl) {
            const count = this.seenNotificationIds.size;
            countEl.innerHTML = `Đã ghi nhận: <strong>${count}</strong> thông báo`;
        }
    }

    /**
     * Mở modal settings
     */
    openSettings() {
        this.settingsModal.show();
    }

    /**
     * Test notification
     */
    testNotification() {
        const testTitle = 'Bạn có công việc mới từ Vũ Văn Hoàng';
        const testBody = 'Vũ Văn Hoàng đã giao cho bạn nhiệm vụ mát-xa cho Hoàng';

        if (this.settings.soundEnabled) {
            this.sound.playTing();
        }

        if (this.settings.ttsEnabled) {
            setTimeout(() => {
                // Test với setting hiện tại
                let textToTest = testTitle;
                if (this.settings.readFullContent) {
                    textToTest += '. ' + testBody;
                }
                this.speak(textToTest);
            }, 300);
        }
    }

/**
 * Text-to-Speech: Đọc tiêu đề BẰNG BACKEND API
 */
async speak(text) {
    if (!this.settings.ttsEnabled || !text) {
        console.log('⏸️ TTS disabled hoặc không có text');
        return;
    }

    try {
        console.log('🗣️ Gọi TTS API:', text);

        // Lấy CSRF token
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

        // Gọi backend API
        const response = await fetch('/tts/speak', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                text: text,
                speed: this.settings.ttsSpeed
            })
        });

        if (!response.ok) {
            throw new Error(`TTS API error: ${response.status}`);
        }

        // Nhận audio blob
        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);

        console.log('✅ TTS audio nhận được, đang phát...');

        // Phát audio VÀ ĐỢI PHÁT XONG
        this.audioElement.src = audioUrl;
        this.audioElement.playbackRate = this.settings.ttsSpeed;

        // QUAN TRỌNG: Đợi audio phát xong bằng Promise
        await new Promise((resolve, reject) => {
            this.audioElement.onended = () => {
                console.log('⏹️ TTS phát xong');
                URL.revokeObjectURL(audioUrl);
                resolve();
            };

            this.audioElement.onerror = (error) => {
                console.error('❌ Audio playback error:', error);
                URL.revokeObjectURL(audioUrl);
                reject(error);
            };

            this.audioElement.play().catch(reject);
        });

        console.log('🔊 Đã phát xong TTS');

    } catch (error) {
        console.error('❌ TTS Error:', error);

        // Fallback: hiện toast thông báo
        this.showToast('Không thể phát âm thanh thông báo', 'warning');
    }
}

    /**
     * Bắt đầu polling
     */
    startPolling() {
        // Poll ngay lập tức
        this.checkNotifications();

        // Sau đó poll định kỳ
        this.pollingInterval = setInterval(() => {
            this.checkNotifications();
        }, this.pollingDelay);
    }

    /**
     * Dừng polling
     */
    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }

    /**
     * Kiểm tra thông báo mới
     */
    async checkNotifications() {
        try {
            // Thử gọi API mới (unread-ids)
            let response = await fetch('/notifications/unread-ids');

            if (response.ok) {
                // API MỚI: Track bằng IDs (CHỐNG ĐỌC LẠI)
                const data = await response.json();

                const currentIds = new Set(data.ids || []);
                const currentCount = currentIds.size;

                // Tìm IDs MỚI (có trong currentIds nhưng không có trong seenNotificationIds)
                const newIds = [...currentIds].filter(id => !this.seenNotificationIds.has(id));

                if (newIds.length > 0) {
                    console.log(`📬 ${newIds.length} thông báo MỚI (IDs: ${newIds.join(', ')})`);

                    // Thêm IDs mới vào seen list
                    newIds.forEach(id => this.seenNotificationIds.add(id));

                    // LƯU VÀO LOCALSTORAGE
                    this.saveSeenIds();

                    // Trigger notification (chỉ khi thật sự có thông báo MỚI)
                    this.onNewNotification(newIds.length);
                }

                // Cleanup: Xóa IDs đã đọc khỏi seenNotificationIds
                this.seenNotificationIds.forEach(id => {
                    if (!currentIds.has(id)) {
                        this.seenNotificationIds.delete(id);
                    }
                });

                // LƯU LẠI SAU KHI CLEANUP
                this.saveSeenIds();

                this.lastNotificationCount = currentCount;

            } else {
                // FALLBACK: API cũ (dùng count) - có thể bị đọc lại
                console.warn('⚠️ /unread-ids not available, using fallback (count)');

                response = await fetch('/notifications/unread-count');
                const data = await response.json();
                const currentCount = data.count || 0;

                // Nếu có thông báo mới (tăng lên)
                if (currentCount > this.lastNotificationCount) {
                    const newNotifs = currentCount - this.lastNotificationCount;
                    this.onNewNotification(newNotifs);
                }

                this.lastNotificationCount = currentCount;
            }

        } catch (error) {
            console.error('Error checking notifications:', error);
        }
    }

    /**
     * Xử lý khi có thông báo mới
     */
    async onNewNotification(count) {
        console.log(`📬 ${count} thông báo mới!`);

        // Phát âm thanh
        if (this.settings.soundEnabled) {
            this.sound.playTing();
        }

        // Đọc thông báo
        if (this.settings.ttsEnabled) {
            // Delay một chút để âm thanh phát xong
            setTimeout(async () => {
                await this.speakLatestNotification();
            }, 300);
        }
    }

/**
 * Lấy và đọc TẤT CẢ thông báo mới
 */
async speakLatestNotification() {
    try {
        // Gọi API lấy TẤT CẢ thông báo chưa đọc
        const response = await fetch('/notifications/latest-all');

        if (!response.ok) {
            throw new Error('API error');
        }

        const data = await response.json();
        const notifications = data.notifications || [];

        console.log(`📢 Có ${notifications.length} thông báo cần đọc`);
        console.log('📋 FULL DATA:', data);

        if (notifications.length === 0) {
            console.log('⚠️ Không có thông báo nào');
            return;
        }

        // Đọc TỪNG thông báo (tuần tự)
        for (let i = 0; i < notifications.length; i++) {
            const notif = notifications[i];
            let textToSpeak = '';

            console.log(`\n📖 === Đang đọc thông báo ${i + 1}/${notifications.length} ===`);
            console.log('📋 RAW notification:', notif);
            console.log('📋 Title:', notif.title);
            console.log('📋 Body:', notif.body);
            console.log('📋 readFullContent setting:', this.settings.readFullContent);

            // Kiểm tra setting: Đọc full hay chỉ title?
            if (this.settings.readFullContent) {
                // ĐỌC CẢ TITLE VÀ BODY
                if (notif.title) {
                    textToSpeak = notif.title;
                }

                if (notif.body) {
                    if (textToSpeak) {
                        textToSpeak += '. ' + notif.body;
                    } else {
                        textToSpeak = notif.body;
                    }
                }

                console.log('✅ Chế độ: Đọc TOÀN BỘ (title + body)');
            } else {
                // CHỈ ĐỌC TITLE
                textToSpeak = notif.title || notif.body || '';
                console.log('✅ Chế độ: Chỉ đọc TIÊU ĐỀ');
            }

            console.log('📝 Text trước khi làm sạch:', textToSpeak);

            // Làm sạch text
            textToSpeak = textToSpeak.replace(/<[^>]*>/g, ''); // Xóa HTML
            textToSpeak = textToSpeak.trim();

            // Giới hạn độ dài (tránh đọc quá dài)
            const maxLength = this.settings.readFullContent ? 300 : 150;
            if (textToSpeak.length > maxLength) {
                textToSpeak = textToSpeak.substring(0, maxLength) + '...';
                console.log('⚠️ Text quá dài, đã cắt bớt');
            }

            console.log('🗣️ Text SAU khi làm sạch:', textToSpeak);
            console.log('📏 Độ dài:', textToSpeak.length, 'ký tự');

            // Đọc thông báo này
            if (textToSpeak) {
                await this.speak(textToSpeak);

                // Delay giữa các thông báo
                if (i < notifications.length - 1) {
                    console.log('⏳ Delay 0.2s trước khi đọc thông báo tiếp theo...');
                    await new Promise(resolve => setTimeout(resolve, 200));
                }
            } else {
                console.log('⚠️ Không có text để đọc!');
            }
        }

        console.log('\n✅ Đã đọc xong tất cả thông báo\n');

    } catch (error) {
        console.error('❌ Error fetching notifications:', error);

        // Fallback: đọc thông báo chung
        const fallbackText = `Bạn có thông báo mới`;
        console.log('📢 Fallback - đọc:', fallbackText);
        await this.speak(fallbackText);
    }
}

    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} alert-dismissible fade show`;
        toast.style.position = 'fixed';
        toast.style.top = '20px';
        toast.style.right = '20px';
        toast.style.zIndex = '9999';
        toast.style.minWidth = '300px';
        toast.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
}

// Khởi động khi DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.notificationManager = new NotificationManager();
    console.log('✅ Notification Manager initialized (Backend TTS)');
});