// ============================================
// SANTA EFFECT - STANDALONE VERSION
// ============================================
const SantaEffect = {
    isShowing: false,
    container: null,

    show(config = {}) {
        if (this.isShowing) {
            console.log('🎅 Santa is already showing');
            return;
        }

        console.log('🎅 Santa Claus is coming to town!');
        this.isShowing = true;

        const message = config.message || 'Chúc Mừng Giáng Sinh! 🎄';

        this.container = document.createElement('div');
        this.container.className = 'santa-container';
        this.container.innerHTML = `
            <div class="santa-message">${message}</div>
            <div class="santa-character">🎅</div>
            <div class="santa-gift">🎁</div>
        `;

        if (config.sparkles !== false) {
            this.addSparkles();
        }

        document.body.appendChild(this.container);

        setTimeout(() => {
            this.hide();
        }, 10000);
    },

    addSparkles() {
        const sparkleCount = 20;

        for (let i = 0; i < sparkleCount; i++) {
            setTimeout(() => {
                const sparkle = document.createElement('div');
                sparkle.className = 'santa-sparkle';

                const x = Math.random() * 150 - 50;
                const y = Math.random() * 150 - 50;
                sparkle.style.left = x + 'px';
                sparkle.style.top = y + 'px';
                sparkle.style.animationDelay = Math.random() * 1 + 's';

                this.container.appendChild(sparkle);

                setTimeout(() => {
                    if (sparkle.parentNode) {
                        sparkle.parentNode.removeChild(sparkle);
                    }
                }, 2000);
            }, i * 100);
        }
    },

    hide() {
        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
            this.container = null;
            this.isShowing = false;
            console.log('🎅 Santa has left the building');
        }
    },

    showOnPageLoad(config = {}) {
        const hasShownToday = sessionStorage.getItem('santa_shown_today');

        if (hasShownToday) {
            console.log('🎅 Santa already appeared today');
            return;
        }

        const delay = config.delay || 1000;

        setTimeout(() => {
            this.show(config);
            sessionStorage.setItem('santa_shown_today', 'true');
        }, delay);
    }
};

window.SantaEffect = SantaEffect;
console.log('🎅 Santa Effect loaded');