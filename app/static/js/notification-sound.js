/**
 * Notification Sound Generator
 * Tạo âm thanh "ting" giống chuông thật bằng Web Audio API
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
     * Phát âm thanh "ting" notification - Bell Classic
     * Nhiều harmonics giống chuông thật
     */
    playTing() {
        if (!this.enabled) return;

        try {
            this.init();

            const ctx = this.audioContext;
            const now = ctx.currentTime;

            // Master gain
            const masterGain = ctx.createGain();
            masterGain.connect(ctx.destination);

            // Tạo nhiều harmonics giống chuông thật
            const harmonics = [
                { freq: 1200, gain: 0.6 },  // Fundamental (cao hơn để giống "ting")
                { freq: 2400, gain: 0.3 },  // Overtone 1
                { freq: 3600, gain: 0.15 }, // Overtone 2
                { freq: 4800, gain: 0.08 }  // Overtone 3
            ];

            harmonics.forEach(({ freq, gain: volume }) => {
                const osc = ctx.createOscillator();
                const oscGain = ctx.createGain();

                osc.connect(oscGain);
                oscGain.connect(masterGain);

                // Dùng sine wave cho âm trong trẻo
                osc.type = 'sine';
                osc.frequency.setValueAtTime(freq, now);

                // Envelope tự nhiên: attack nhanh, decay dài giống chuông
                oscGain.gain.setValueAtTime(0, now);
                oscGain.gain.linearRampToValueAtTime(volume, now + 0.005); // Attack cực nhanh
                oscGain.gain.exponentialRampToValueAtTime(0.001, now + 0.8); // Decay dài, tự nhiên

                osc.start(now);
                osc.stop(now + 0.8);
            });

            // Master volume
            masterGain.gain.setValueAtTime(0.4, now);

        } catch (error) {
            console.error('Error playing notification sound:', error);
        }
    }

    /**
     * Phát âm thanh "ting" Version 2: Triangle wave (sắc hơn)
     */
    playTingSharp() {
        if (!this.enabled) return;

        try {
            this.init();

            const ctx = this.audioContext;
            const now = ctx.currentTime;

            const osc = ctx.createOscillator();
            const gain = ctx.createGain();

            osc.connect(gain);
            gain.connect(ctx.destination);

            // Triangle wave cho âm sắc hơn
            osc.type = 'triangle';
            osc.frequency.setValueAtTime(1500, now);

            // Pitch envelope: tăng nhẹ rồi giảm (giống kim loại rung)
            osc.frequency.linearRampToValueAtTime(1600, now + 0.02);
            osc.frequency.exponentialRampToValueAtTime(1500, now + 0.3);

            // Volume envelope
            gain.gain.setValueAtTime(0, now);
            gain.gain.linearRampToValueAtTime(0.3, now + 0.003);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.6);

            osc.start(now);
            osc.stop(now + 0.6);

        } catch (error) {
            console.error('Error playing notification sound:', error);
        }
    }

    /**
     * Phát âm thanh "ting" Version 3: Double hit (giống gõ chuông 2 lần)
     */
    playTingDouble() {
        if (!this.enabled) return;

        try {
            this.init();

            const ctx = this.audioContext;
            const now = ctx.currentTime;

            // Hit 1
            this.createTingHit(now);

            // Hit 2 (nhẹ hơn, sau 0.08s)
            this.createTingHit(now + 0.08, 0.5);

        } catch (error) {
            console.error('Error playing notification sound:', error);
        }
    }

    /**
     * Helper: Tạo 1 hit "ting"
     */
    createTingHit(startTime, volumeMultiplier = 1) {
        const ctx = this.audioContext;
        const masterGain = ctx.createGain();
        masterGain.connect(ctx.destination);

        const harmonics = [
            { freq: 1400, gain: 0.5 * volumeMultiplier },
            { freq: 2800, gain: 0.25 * volumeMultiplier },
            { freq: 4200, gain: 0.12 * volumeMultiplier }
        ];

        harmonics.forEach(({ freq, gain: volume }) => {
            const osc = ctx.createOscillator();
            const oscGain = ctx.createGain();

            osc.connect(oscGain);
            oscGain.connect(masterGain);

            osc.type = 'sine';
            osc.frequency.setValueAtTime(freq, startTime);

            oscGain.gain.setValueAtTime(0, startTime);
            oscGain.gain.linearRampToValueAtTime(volume, startTime + 0.003);
            oscGain.gain.exponentialRampToValueAtTime(0.001, startTime + 0.4);

            osc.start(startTime);
            osc.stop(startTime + 0.4);
        });

        masterGain.gain.setValueAtTime(0.4, startTime);
    }

    /**
     * Phát âm thanh "ting" Version 4: Marimba-like (ấm áp hơn)
     */
    playTingWarm() {
        if (!this.enabled) return;

        try {
            this.init();

            const ctx = this.audioContext;
            const now = ctx.currentTime;

            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            const filter = ctx.createBiquadFilter();

            osc.connect(filter);
            filter.connect(gain);
            gain.connect(ctx.destination);

            // Sine wave với filter
            osc.type = 'sine';
            osc.frequency.setValueAtTime(880, now); // A5 note

            // Lowpass filter để âm ấm hơn
            filter.type = 'lowpass';
            filter.frequency.setValueAtTime(3000, now);
            filter.Q.setValueAtTime(1, now);

            // Envelope
            gain.gain.setValueAtTime(0, now);
            gain.gain.linearRampToValueAtTime(0.35, now + 0.005);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.7);

            osc.start(now);
            osc.stop(now + 0.7);

        } catch (error) {
            console.error('Error playing notification sound:', error);
        }
    }

    /**
     * Phát âm thanh "ting" Version 5: Glass/Crystal (trong trẻo nhất)
     */
    playTingCrystal() {
        if (!this.enabled) return;

        try {
            this.init();

            const ctx = this.audioContext;
            const now = ctx.currentTime;

            const masterGain = ctx.createGain();
            masterGain.connect(ctx.destination);

            // Tần số cao, nhiều harmonics
            const harmonics = [
                { freq: 2000, gain: 0.4, decay: 0.6 },
                { freq: 4000, gain: 0.3, decay: 0.5 },
                { freq: 6000, gain: 0.2, decay: 0.4 },
                { freq: 8000, gain: 0.1, decay: 0.3 }
            ];

            harmonics.forEach(({ freq, gain: volume, decay }) => {
                const osc = ctx.createOscillator();
                const oscGain = ctx.createGain();

                osc.connect(oscGain);
                oscGain.connect(masterGain);

                osc.type = 'sine';
                osc.frequency.setValueAtTime(freq, now);

                // Decay khác nhau cho mỗi harmonic
                oscGain.gain.setValueAtTime(0, now);
                oscGain.gain.linearRampToValueAtTime(volume, now + 0.002);
                oscGain.gain.exponentialRampToValueAtTime(0.001, now + decay);

                osc.start(now);
                osc.stop(now + decay);
            });

            masterGain.gain.setValueAtTime(0.3, now);

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