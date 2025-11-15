/**
 * Notification Sound Generator
 * Tạo âm thanh "ting" chuyên nghiệp bằng Web Audio API
 */

class NotificationSound {
    constructor() {
        this.audioContext = null;
        this.enabled = true;
    }

    /**
     * Khởi tạo Audio Context (cần user interaction)
     */
    init() {
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }
    }

    /**
     * Phát âm thanh "ting" notification
     */
    playTing() {
        if (!this.enabled) return;

        try {
            this.init();

            const ctx = this.audioContext;
            const now = ctx.currentTime;

            // Tạo oscillator cho âm thanh ting
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();

            // Kết nối: oscillator -> gain -> destination
            osc.connect(gain);
            gain.connect(ctx.destination);

            // Cấu hình âm thanh: tần số cao, ngắn, rõ ràng
            osc.type = 'sine';
            osc.frequency.setValueAtTime(800, now); // Tần số chính
            osc.frequency.exponentialRampToValueAtTime(1200, now + 0.05); // Tăng nhanh
            osc.frequency.exponentialRampToValueAtTime(800, now + 0.1); // Giảm về

            // Envelope: attack-decay nhanh
            gain.gain.setValueAtTime(0, now);
            gain.gain.linearRampToValueAtTime(0.3, now + 0.01); // Attack
            gain.gain.exponentialRampToValueAtTime(0.01, now + 0.2); // Decay

            // Phát âm
            osc.start(now);
            osc.stop(now + 0.2);

        } catch (error) {
            console.error('Error playing notification sound:', error);
        }
    }

    /**
     * Bật/tắt âm thanh
     */
    setEnabled(enabled) {
        this.enabled = enabled;
    }
}

// Export global instance
window.NotificationSound = NotificationSound;