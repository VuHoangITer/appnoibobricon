/**
 * Real-time Notification Manager
 * VERSION 5: SSE Optimized + Auto Reconnect + No Duplicates
 * Phù hợp với sse.py optimized
 */

class NotificationManager {
    constructor() {
        this.sound = new NotificationSound();
        this.audioElement = new Audio();
        this.audioElement.preload = 'auto';

        this.settings = this.loadSettings();
        this.lastNotificationCount = 0;
        this.seenNotificationIds = this.loadSeenIds();
        this.processedNotificationIds = new Set();

        this.useSSE = true;
        this.sseConnected = false;

        // Auto-reconnect tracking
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 5000; // 5 seconds

        this.toggleButton = null;
        this.settingsModal = null;

        this.init();
    }

    loadSettings() {
        const defaults = {
            soundEnabled: true,
            ttsEnabled: true,
            ttsSpeed: 1.0,
            readFullContent: true
        };
        try {
            const saved = localStorage.getItem('notification_settings');
            return saved ? { ...defaults, ...JSON.parse(saved) } : defaults;
        } catch (e) {
            return defaults;
        }
    }

    saveSettings() {
        try {
            localStorage.setItem('notification_settings', JSON.stringify(this.settings));
        } catch (e) {
            console.error('Error saving settings:', e);
        }
    }

    loadSeenIds() {
        try {
            const saved = localStorage.getItem('seen_notification_ids');
            if (saved) {
                const ids = JSON.parse(saved);
                // Giới hạn size để tránh localStorage đầy
                if (ids.length > 200) {
                    return new Set(ids.slice(-100));
                }
                return new Set(ids);
            }
        } catch (e) {
            console.error('Error loading seen IDs:', e);
        }
        return new Set();
    }

    saveSeenIds() {
        try {
            let ids = Array.from(this.seenNotificationIds);
            // Giới hạn size
            if (ids.length > 200) {
                ids = ids.slice(-100);
                this.seenNotificationIds = new Set(ids);
            }
            localStorage.setItem('seen_notification_ids', JSON.stringify(ids));
        } catch (e) {
            console.error('Error saving seen IDs:', e);
        }
    }

    init() {
        this.sound.init();
        this.createToggleButton();
        this.createSettingsModal();
        this.startRealtimeUpdates();

        // Cleanup on page unload
        window.addEventListener('beforeunload', () => this.stopRealtimeUpdates());

        // Handle visibility change
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && !this.sseConnected) {
                console.log('📳 Tab visible, reconnecting SSE...');
                this.startRealtimeUpdates();
            }
        });
    }

    createToggleButton() {
        const navbarRight = document.querySelector('.navbar-right');
        if (!navbarRight) return;

        const btn = document.createElement('button');
        btn.className = 'notification-btn notification-settings-btn';
        btn.innerHTML = this.getToggleIcon();
        btn.title = 'Cài đặt thông báo';
        btn.onclick = () => this.openSettings();

        const notifBtn = navbarRight.querySelector('.notification-btn');
        if (notifBtn) {
            navbarRight.insertBefore(btn, notifBtn);
        } else {
            navbarRight.appendChild(btn);
        }
        this.toggleButton = btn;
    }

    getToggleIcon() {
        const { soundEnabled, ttsEnabled } = this.settings;
        if (soundEnabled && ttsEnabled) return '<i class="bi bi-volume-up-fill"></i>';
        if (soundEnabled || ttsEnabled) return '<i class="bi bi-volume-down-fill"></i>';
        return '<i class="bi bi-volume-mute-fill"></i>';
    }

    updateToggleIcon() {
        if (this.toggleButton) {
            this.toggleButton.innerHTML = this.getToggleIcon();
        }
    }

    createSettingsModal() {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = 'notificationSettingsModal';
        modal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title"><i class="bi bi-gear-fill"></i> Cài đặt Thông báo</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="form-check form-switch mb-3">
                            <input class="form-check-input" type="checkbox" id="soundToggle" ${this.settings.soundEnabled ? 'checked' : ''}>
                            <label class="form-check-label" for="soundToggle">
                                <i class="bi bi-bell-fill"></i> Phát âm thanh "ting"
                            </label>
                        </div>
                        <div class="form-check form-switch mb-3">
                            <input class="form-check-input" type="checkbox" id="ttsToggle" ${this.settings.ttsEnabled ? 'checked' : ''}>
                            <label class="form-check-label" for="ttsToggle">
                                <i class="bi bi-megaphone-fill"></i> Đọc tiêu đề thông báo
                            </label>
                        </div>
                        <div class="form-check form-switch mb-3 ms-4">
                            <input class="form-check-input" type="checkbox" id="readFullToggle" ${this.settings.readFullContent ? 'checked' : ''}>
                            <label class="form-check-label" for="readFullToggle">
                                <i class="bi bi-file-text"></i> Đọc cả nội dung chi tiết
                            </label>
                        </div>
                        <hr>
                        <div class="mb-3">
                            <label for="ttsSpeed" class="form-label">
                                Tốc độ đọc: <strong id="ttsSpeedValue">${this.settings.ttsSpeed}x</strong>
                            </label>
                            <input type="range" class="form-range" id="ttsSpeed" min="0.5" max="2" step="0.1" value="${this.settings.ttsSpeed}">
                        </div>
                        <div class="d-grid gap-2">
                            <button type="button" class="btn btn-outline-primary" id="testNotification">
                                <i class="bi bi-play-circle-fill"></i> Nghe thử
                            </button>
                            <button type="button" class="btn btn-outline-secondary btn-sm" id="clearHistory">
                                <i class="bi bi-trash"></i> Nghe lại tất cả
                            </button>
                        </div>
                        <hr>
                        <div class="alert alert-info mb-0">
                            <small>
                                <i class="bi bi-info-circle"></i> Trạng thái:
                                <strong id="connectionStatus">Đang kết nối...</strong>
                            </small>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <small class="text-muted" id="seenCount">Đã ghi nhận: <strong>0</strong> thông báo</small>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        this.settingsModal = new bootstrap.Modal(modal);
        this.attachSettingsListeners();
    }

    attachSettingsListeners() {
        document.getElementById('soundToggle').addEventListener('change', (e) => {
            this.settings.soundEnabled = e.target.checked;
            this.saveSettings();
            this.updateToggleIcon();
        });

        document.getElementById('ttsToggle').addEventListener('change', (e) => {
            this.settings.ttsEnabled = e.target.checked;
            this.saveSettings();
            this.updateToggleIcon();
        });

        document.getElementById('readFullToggle').addEventListener('change', (e) => {
            this.settings.readFullContent = e.target.checked;
            this.saveSettings();
        });

        const speedSlider = document.getElementById('ttsSpeed');
        const speedValue = document.getElementById('ttsSpeedValue');
        speedSlider.addEventListener('input', (e) => {
            const value = parseFloat(e.target.value);
            this.settings.ttsSpeed = value;
            speedValue.textContent = value.toFixed(1) + 'x';
            this.saveSettings();
        });

        document.getElementById('testNotification').addEventListener('click', () => this.testNotification());

        document.getElementById('clearHistory').addEventListener('click', () => {
            if (confirm('Xóa lịch sử? Thông báo cũ sẽ phát lại.')) {
                this.seenNotificationIds.clear();
                this.processedNotificationIds.clear();
                this.saveSeenIds();
                this.updateSeenCount();
                this.showToast('Đã xóa lịch sử', 'success');
            }
        });

        document.getElementById('notificationSettingsModal').addEventListener('shown.bs.modal', () => {
            this.updateSeenCount();
            this.updateConnectionStatus();
        });
    }

    updateSeenCount() {
        const el = document.getElementById('seenCount');
        if (el) el.innerHTML = `Đã ghi nhận: <strong>${this.seenNotificationIds.size}</strong> thông báo`;
    }

    updateConnectionStatus() {
        const el = document.getElementById('connectionStatus');
        if (el) {
            el.innerHTML = this.sseConnected
                ? '<span class="text-success">✅ SSE Real-time</span>'
                : '<span class="text-warning">⚠️ Đang kết nối lại...</span>';
        }
    }

    openSettings() {
        this.settingsModal.show();
    }

    testNotification() {
        if (this.settings.soundEnabled) this.sound.playTing();
        if (this.settings.ttsEnabled) {
            let text = 'Bạn có công việc mới';
            if (this.settings.readFullContent) text += '. Đây là nội dung chi tiết của thông báo.';
            setTimeout(() => this.speak(text), 300);
        }
    }

    async speak(text) {
        if (!this.settings.ttsEnabled || !text) return;
        try {
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
            const response = await fetch('/tts/speak', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ text, speed: this.settings.ttsSpeed })
            });
            if (!response.ok) throw new Error(`TTS error: ${response.status}`);

            const audioBlob = await response.blob();
            const audioUrl = URL.createObjectURL(audioBlob);
            this.audioElement.src = audioUrl;
            this.audioElement.playbackRate = this.settings.ttsSpeed;

            await new Promise((resolve, reject) => {
                this.audioElement.onended = () => { URL.revokeObjectURL(audioUrl); resolve(); };
                this.audioElement.onerror = (e) => { URL.revokeObjectURL(audioUrl); reject(e); };
                this.audioElement.play().catch(reject);
            });
        } catch (error) {
            console.error('TTS Error:', error);
        }
    }

    // ============================================================
    // SSE CONNECTION - AUTO RECONNECT
    // ============================================================
    startRealtimeUpdates() {
        if (typeof window.sseManager === 'undefined') {
            console.warn('⚠️ SSE Manager not loaded, using polling');
            this.startPolling();
            return;
        }

        window.sseManager.connect(
            'notifications',
            '/sse/notifications',
            {
                onOpen: () => {
                    console.log('✅ SSE connected');
                    this.sseConnected = true;
                    this.reconnectAttempts = 0;
                    this.updateConnectionStatus();
                },
                onError: (error, attempts) => {
                    console.error('❌ SSE error:', error);
                    this.sseConnected = false;
                    this.updateConnectionStatus();
                },
                events: {
                    'notification_update': (data) => this.handleNotificationUpdate(data),
                    'new_notification': (data) => this.handleNewNotification(data),
                    'heartbeat': () => console.log('💓 Heartbeat'),
                    'close': (data) => {
                        console.log('🔌 SSE closed, reconnecting...');
                        this.sseConnected = false;
                        // Server yêu cầu reconnect
                        if (data.type === 'reconnect') {
                            setTimeout(() => this.startRealtimeUpdates(), 1000);
                        }
                    }
                }
            },
            {
                url: '/notifications/unread-ids',
                interval: 30000, // 30 giây fallback
                onData: (data) => this.handlePollingData(data)
            }
        );
    }

    stopRealtimeUpdates() {
        if (window.sseManager) window.sseManager.disconnect('notifications');
        this.sseConnected = false;
    }

    startPolling() {
        this.checkNotifications();
        this.pollingInterval = setInterval(() => this.checkNotifications(), 30000);
    }

    async checkNotifications() {
        try {
            const response = await fetch('/notifications/unread-ids');
            if (response.ok) this.handlePollingData(await response.json());
        } catch (e) {
            console.error('Polling error:', e);
        }
    }

    // ============================================================
    // HANDLERS - NO DUPLICATES
    // ============================================================
    handleNotificationUpdate(data) {
        const currentIds = new Set(data.ids || []);
        const newIds = [...currentIds].filter(id => !this.seenNotificationIds.has(id));

        if (newIds.length > 0) {
            newIds.forEach(id => this.seenNotificationIds.add(id));
            this.saveSeenIds();

            // Chỉ trigger sound nếu KHÔNG có SSE connected (tức là từ polling)
            // Vì SSE sẽ gửi new_notification event riêng
            if (!this.sseConnected) {
                this.triggerNotificationAlert(newIds);
            }
        }

        // Cleanup old IDs
        this.seenNotificationIds.forEach(id => {
            if (!currentIds.has(id)) this.seenNotificationIds.delete(id);
        });
        this.saveSeenIds();
        this.lastNotificationCount = currentIds.size;
    }

    handleNewNotification(notifData) {
        if (!notifData.id) return;

        // Kiểm tra đã xử lý chưa
        if (this.processedNotificationIds.has(notifData.id)) {
            console.log('⏭️ Already processed:', notifData.id);
            return;
        }

        // Đánh dấu đã xử lý
        this.processedNotificationIds.add(notifData.id);
        this.seenNotificationIds.add(notifData.id);
        this.saveSeenIds();

        // Giới hạn size
        if (this.processedNotificationIds.size > 100) {
            const arr = Array.from(this.processedNotificationIds);
            this.processedNotificationIds = new Set(arr.slice(-50));
        }

        console.log('🔔 New notification:', notifData.id);

        // Play sound
        if (this.settings.soundEnabled) this.sound.playTing();

        // TTS
        if (this.settings.ttsEnabled) {
            setTimeout(async () => {
                let text = notifData.title || '';
                if (this.settings.readFullContent && notifData.body) {
                    text += '. ' + notifData.body;
                }
                if (text) await this.speak(text);
            }, 300);
        }
    }

    handlePollingData(data) {
        const currentIds = new Set(data.ids || []);
        const newIds = [...currentIds].filter(id =>
            !this.seenNotificationIds.has(id) && !this.processedNotificationIds.has(id)
        );

        if (newIds.length > 0) {
            newIds.forEach(id => {
                this.seenNotificationIds.add(id);
                this.processedNotificationIds.add(id);
            });
            this.saveSeenIds();
            this.triggerNotificationAlert(newIds);
        }

        // Cleanup
        this.seenNotificationIds.forEach(id => {
            if (!currentIds.has(id)) this.seenNotificationIds.delete(id);
        });
        this.saveSeenIds();
    }

    async triggerNotificationAlert(newIds) {
        console.log(`📬 ${newIds.length} new notifications`);

        if (this.settings.soundEnabled) this.sound.playTing();

        if (this.settings.ttsEnabled) {
            setTimeout(() => this.speakLatestNotifications(), 300);
        }
    }

    async speakLatestNotifications() {
        try {
            const response = await fetch('/notifications/latest-all');
            if (!response.ok) throw new Error('API error');

            const data = await response.json();
            const notifications = data.notifications || [];

            for (const notif of notifications) {
                if (this.processedNotificationIds.has(notif.id)) continue;
                this.processedNotificationIds.add(notif.id);

                let text = this.settings.readFullContent
                    ? `${notif.title || ''}. ${notif.body || ''}`.trim()
                    : (notif.title || notif.body || '');

                text = text.replace(/<[^>]*>/g, '').substring(0, 300);
                if (text) await this.speak(text);
            }
        } catch (e) {
            console.error('Error fetching notifications:', e);
            await this.speak('Bạn có thông báo mới');
        }
    }

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} position-fixed`;
        toast.style.cssText = 'top:20px;right:20px;z-index:9999;min-width:250px;';
        toast.innerHTML = `${message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
        document.body.appendChild(toast);
        setTimeout(() => { toast.remove(); }, 3000);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    window.notificationManager = new NotificationManager();
    console.log('✅ Notification Manager v5 - Optimized');
});