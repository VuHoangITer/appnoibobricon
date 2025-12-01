// ============================================
// SEASONAL EFFECTS ENGINE - SNOW + SANTA ONLY
// ============================================

const SeasonalEffects = {
    container: null,
    activeEffect: 'none',
    config: {},
    intervals: {},
    elements: [],
    currentPage: 'hub',

    // ========================================
    // INITIALIZATION
    // ========================================
    async init() {
        console.log('🎨 Initializing Seasonal Effects...');

        this.detectCurrentPage();
        console.log('📍 Current page:', this.currentPage);

        this.container = document.getElementById('seasonalEffects');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'seasonalEffects';
            document.body.prepend(this.container);
            console.log('✅ Created seasonalEffects container');
        } else {
            console.log('✅ Found existing seasonalEffects container');
        }

        await this.loadConfig();

        // Chỉ auto-start snowfall và santa
        ['snowfall', 'santa'].forEach(effectName => {
            const effectConfig = this.config.effects[effectName];
            if (effectConfig && effectConfig.active) {
                if (this.shouldShowEffect(effectName)) {
                    console.log('🎯 Auto-starting effect:', effectName);
                    this.startEffect(effectName);
                } else {
                    console.log('⏭️ Skipping effect:', effectName, '(not for this page)');
                }
            }
        });

        console.log('✅ Seasonal Effects initialized');
    },

    // ========================================
    // DETECT CURRENT PAGE
    // ========================================
    detectCurrentPage() {
        const path = window.location.pathname;

        if (path.includes('/hub')) {
            this.currentPage = 'hub';
        } else if (path.includes('/tasks')) {
            this.currentPage = 'tasks';
        } else if (path.includes('/files')) {
            this.currentPage = 'files';
        } else if (path.includes('/notes')) {
            this.currentPage = 'notes';
        } else if (path.includes('/salaries')) {
            this.currentPage = 'salaries';
        } else if (path.includes('/news')) {
            this.currentPage = 'news';
        } else if (path.includes('/performance')) {
            this.currentPage = 'performance';
        } else if (path.includes('/employees')) {
            this.currentPage = 'employees';
        } else {
            this.currentPage = 'hub';
        }
    },

    // ========================================
    // CHECK SHOULD SHOW EFFECT
    // ========================================
    shouldShowEffect(effectName) {
        const effectConfig = this.config.effects[effectName];
        if (!effectConfig) return false;

        const pages = effectConfig.pages || ['all'];

        if (pages.includes('all')) {
            return true;
        }

        return pages.includes(this.currentPage);
    },

    // ========================================
    // CONFIG MANAGEMENT
    // ========================================
    async loadConfig() {
        try {
            console.log('🔄 Loading config from server...');
            const response = await fetch('/seasonal-effects/api/get-config');

            if (!response.ok) {
                console.warn(`⚠️ Server returned ${response.status}, using default config`);
                this.setDefaultConfig();
                return;
            }

            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                console.warn('⚠️ Server returned non-JSON response, using default config');
                this.setDefaultConfig();
                return;
            }

            const data = await response.json();

            if (data.success && data.config) {
                this.config = data.config;
                console.log('✅ Loaded config from server:', this.config);
            } else {
                console.log('⚠️ No config from server, using default');
                this.setDefaultConfig();
            }
        } catch (e) {
            console.warn('⚠️ Failed to load config from server, using default:', e.message);
            this.setDefaultConfig();
        }
    },

    setDefaultConfig() {
        this.config = {
            effects: {
                snowfall: {
                    active: false,
                    duration: 0,
                    intensity: 50,
                    speed: 'medium',
                    pages: ['all']
                },
                santa: {
                    active: false,
                    message: 'Chúc Mừng Giáng Sinh! 🎄',
                    delay: 1000,
                    sparkles: true,
                    pages: ['all']
                }
            }
        };
    },

    async saveConfig() {
        try {
            console.log('💾 Saving config:', this.config);

            const response = await fetch('/seasonal-effects/api/save-config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(this.config)
            });

            if (response.status === 403 || response.status === 401) {
                console.warn('⚠️ No permission to save config (only director can save)');
                return false;
            }

            if (!response.ok) {
                console.error(`❌ Server returned ${response.status}`);
                return false;
            }

            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                console.error('❌ Server returned non-JSON response');
                return false;
            }

            const data = await response.json();

            if (data.success) {
                console.log('✅ Config saved to server');
                return true;
            } else {
                console.error('❌ Failed to save config:', data.error);
                return false;
            }
        } catch (e) {
            console.error('❌ Failed to save config:', e);
            return false;
        }
    },

    // ========================================
    // EFFECT CONTROL
    // ========================================
    startEffect(effectName, customConfig = null) {
        console.log(`🎯 Starting effect: ${effectName}`);

        this.stopEffect(effectName);

        const effectConfig = customConfig || (this.config.effects && this.config.effects[effectName]);
        if (!effectConfig) {
            console.error('Effect config not found:', effectName);
            if (!this.config.effects) {
                this.config.effects = {};
            }
            this.config.effects[effectName] = { active: false, duration: 0, pages: ['all'] };
            return;
        }

        console.log('Config:', effectConfig);

        if (this.effects[effectName]) {
            try {
                this.effects[effectName].start.call(this, effectConfig);

                if (!this.config.effects[effectName]) {
                    this.config.effects[effectName] = {};
                }
                this.config.effects[effectName].active = true;

                if (!customConfig && window.IS_SEASONAL_SETTINGS_PAGE) {
                    this.saveConfig();
                }

                console.log('✅ Effect started successfully');

                // Auto stop sau duration (KHÔNG ÁP DỤNG CHO SANTA)
                if (effectName !== 'santa' && effectConfig.duration && effectConfig.duration > 0) {
                    setTimeout(() => {
                        this.stopEffect(effectName);
                        console.log(`⏱️ ${effectName} stopped after ${effectConfig.duration}s`);
                    }, effectConfig.duration * 1000);
                }
            } catch (e) {
                console.error('Error starting effect:', e);
            }
        } else {
            console.error('Effect not found:', effectName);
        }
    },

    stopEffect(effectName) {
        console.log(`🛑 Stopping effect: ${effectName}`);

        if (this.intervals[effectName]) {
            clearInterval(this.intervals[effectName]);
            delete this.intervals[effectName];
        }

        const elementsToRemove = this.elements.filter(el =>
            el && el.className && el.className.includes(effectName)
        );

        elementsToRemove.forEach(el => {
            if (el && el.parentNode) {
                el.parentNode.removeChild(el);
            }
        });

        this.elements = this.elements.filter(el =>
            !elementsToRemove.includes(el)
        );

        if (this.config.effects && this.config.effects[effectName]) {
            this.config.effects[effectName].active = false;
            if (window.IS_SEASONAL_SETTINGS_PAGE) {
                this.saveConfig();
            }
        }
    },

    stopAllEffects() {
        console.log('🛑 Stopping all effects');

        Object.keys(this.intervals).forEach(key => {
            clearInterval(this.intervals[key]);
        });
        this.intervals = {};

        this.elements.forEach(el => {
            if (el && el.parentNode) {
                el.parentNode.removeChild(el);
            }
        });
        this.elements = [];

        if (this.container) {
            this.container.innerHTML = '';
        }

        Object.keys(this.config.effects).forEach(key => {
            this.config.effects[key].active = false;
        });

        if (window.IS_SEASONAL_SETTINGS_PAGE) {
            this.saveConfig();
        }
    },

    // ========================================
    // EFFECTS IMPLEMENTATIONS
    // ========================================
    effects: {
        // ====================================
        // SNOWFALL
        // ====================================
        snowfall: {
            start(config) {
                console.log('❄️ Starting snowfall with config:', config);
                const self = SeasonalEffects;

                const intensity = config.intensity || 50;
                const speed = config.speed || 'medium';

                const speedMap = {
                    slow: { min: 15, max: 25 },
                    medium: { min: 8, max: 15 },
                    fast: { min: 5, max: 10 }
                };

                const snowflakes = ['❄', '❅', '❆'];

                const createSnowflake = () => {
                    const snowflake = document.createElement('div');
                    snowflake.className = 'snowflake';
                    snowflake.textContent = snowflakes[Math.floor(Math.random() * snowflakes.length)];
                    snowflake.style.left = Math.random() * 100 + '%';
                    snowflake.style.fontSize = (Math.random() * 1.5 + 0.5) + 'em';
                    snowflake.style.animationDuration = (Math.random() * (speedMap[speed].max - speedMap[speed].min) + speedMap[speed].min) + 's';
                    snowflake.style.animationDelay = '0s';

                    self.container.appendChild(snowflake);
                    self.elements.push(snowflake);

                    const duration = parseFloat(snowflake.style.animationDuration) * 1000;
                    setTimeout(() => {
                        if (snowflake.parentNode) {
                            snowflake.parentNode.removeChild(snowflake);
                            const index = self.elements.indexOf(snowflake);
                            if (index > -1) self.elements.splice(index, 1);
                        }
                    }, duration);
                };

                const spawnRate = Math.max(50, 500 - intensity * 4);
                self.intervals.snowfall = setInterval(createSnowflake, spawnRate);

                const initialCount = Math.floor(intensity * 0.5);
                for (let i = 0; i < initialCount; i++) {
                    setTimeout(createSnowflake, i * 50);
                }
            }
        },

        // ====================================
        // SANTA CLAUS
        // ====================================
        santa: {
            start(config) {
                console.log('🎅 Starting Santa effect with config:', config);

                if (window.SantaEffect) {
                    window.SantaEffect.showOnPageLoad({
                        message: config.message || 'Chúc Mừng Giáng Sinh! 🎄',
                        delay: config.delay || 1000,
                        sparkles: config.sparkles !== false
                    });
                } else {
                    console.error('SantaEffect not loaded');
                }
            }
        }
    }
};

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        SeasonalEffects.init();
    });
} else {
    SeasonalEffects.init();
}

window.SeasonalEffects = SeasonalEffects;

console.log('🎨 Seasonal Effects script loaded');