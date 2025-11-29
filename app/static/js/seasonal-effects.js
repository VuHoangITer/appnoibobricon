// ============================================
// SEASONAL EFFECTS ENGINE - WITH PAGES SUPPORT
// ============================================

const SeasonalEffects = {
    container: null,
    activeEffect: 'none',
    config: {},
    intervals: {},
    elements: [],
    currentPage: 'hub', // Trang hiện tại

    // ========================================
    // INITIALIZATION
    // ========================================
    async init() {
        console.log('🎨 Initializing Seasonal Effects...');

        // Xác định trang hiện tại
        this.detectCurrentPage();
        console.log('📍 Current page:', this.currentPage);

        // Create container
        this.container = document.getElementById('seasonalEffects');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'seasonalEffects';
            document.body.prepend(this.container);
            console.log('✅ Created seasonalEffects container');
        } else {
            console.log('✅ Found existing seasonalEffects container');
        }

        // Load config from server (async)
        await this.loadConfig();

        // Start all active effects nếu trang hiện tại hỗ trợ
        Object.keys(this.config.effects).forEach(effectName => {
            const effectConfig = this.config.effects[effectName];
            if (effectConfig.active) {
                // Kiểm tra xem effect có nên hiển thị trên trang này không
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
            this.currentPage = 'hub'; // Mặc định
        }
    },

    // ========================================
    // CHECK SHOULD SHOW EFFECT
    // ========================================
    shouldShowEffect(effectName) {
        const effectConfig = this.config.effects[effectName];
        if (!effectConfig) return false;

        const pages = effectConfig.pages || ['all'];

        // Nếu có 'all' thì hiển thị trên tất cả trang
        if (pages.includes('all')) {
            return true;
        }

        // Kiểm tra trang hiện tại có trong list không
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
                fireworks: {
                    active: false,
                    duration: 0,
                    frequency: 1500,
                    intensity: 50,
                    colors: ['#ff0000', '#ffd700', '#00ff00', '#0000ff', '#ff00ff'],
                    pages: ['all']
                },
                noel: {
                    active: false,
                    duration: 0,
                    intensity: 50,
                    pages: ['all']
                },
                tet: {
                    active: false,
                    duration: 0,
                    intensity: 50,
                    pages: ['all']
                },
                flags: {
                    active: false,
                    duration: 0,
                    intensity: 50,
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
                const text = await response.text();
                console.error('Response:', text.substring(0, 200));
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

        // Stop this effect if already running
        this.stopEffect(effectName);

        // Get config
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

        // Start the effect
        if (this.effects[effectName]) {
            try {
                this.effects[effectName].start.call(this, effectConfig);

                // Ensure effect exists in config before setting active
                if (!this.config.effects[effectName]) {
                    this.config.effects[effectName] = {};
                }
                this.config.effects[effectName].active = true;

                // Only save to server if:
                // 1. Not a preview (customConfig)
                // 2. User is on settings page (director only)
                if (!customConfig && window.IS_SEASONAL_SETTINGS_PAGE) {
                    this.saveConfig();
                }

                console.log('✅ Effect started successfully');

                // Auto stop after duration if set (KHÔNG ÁP DỤNG CHO SANTA)
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

        // Stop intervals for this effect
        if (this.intervals[effectName]) {
            clearInterval(this.intervals[effectName]);
            delete this.intervals[effectName];
        }

        // Remove elements for this effect
        const elementsToRemove = this.elements.filter(el =>
            el && el.className && el.className.includes(effectName)
        );

        elementsToRemove.forEach(el => {
            if (el && el.parentNode) {
                el.parentNode.removeChild(el);
            }
        });

        // Update elements array
        this.elements = this.elements.filter(el =>
            !elementsToRemove.includes(el)
        );

        // Update config - check if effect exists first
        if (this.config.effects && this.config.effects[effectName]) {
            this.config.effects[effectName].active = false;
            // Only save if on settings page (director only)
            if (window.IS_SEASONAL_SETTINGS_PAGE) {
                this.saveConfig();
            }
        }
    },

    stopAllEffects() {
        console.log('🛑 Stopping all effects');

        // Stop all intervals
        Object.keys(this.intervals).forEach(key => {
            clearInterval(this.intervals[key]);
        });
        this.intervals = {};

        // Remove all elements
        this.elements.forEach(el => {
            if (el && el.parentNode) {
                el.parentNode.removeChild(el);
            }
        });
        this.elements = [];

        // Clear container
        if (this.container) {
            this.container.innerHTML = '';
        }

        // Update config
        Object.keys(this.config.effects).forEach(key => {
            this.config.effects[key].active = false;
        });

        // Only save if on settings page (director only)
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
        // FIREWORKS
        // ====================================
        fireworks: {
            start(config) {
                console.log('🎆 Starting fireworks with config:', config);
                const self = SeasonalEffects;

                const frequency = config.frequency || 1500;
                const intensity = config.intensity || 50;
                const colors = config.colors || ['#ff0000', '#ffd700', '#00ff00', '#0000ff'];

                const launchFirework = () => {
                    const x = Math.random() * 80 + 10;
                    const y = Math.random() * 30 + 20;
                    const color = colors[Math.floor(Math.random() * colors.length)];

                    // Particle count dựa vào intensity
                    const particleCount = Math.floor((intensity / 50) * 20) + 10;

                    for (let i = 0; i < particleCount; i++) {
                        const particle = document.createElement('div');
                        particle.className = 'firework-particle';
                        particle.style.left = x + '%';
                        particle.style.top = y + '%';
                        particle.style.background = color;

                        const angle = (Math.PI * 2 * Math.random());
                        const velocity = Math.random() * 100 + 50;
                        const tx = Math.cos(angle) * velocity;
                        const ty = Math.sin(angle) * velocity;

                        particle.style.setProperty('--tx', tx + 'px');
                        particle.style.setProperty('--ty', ty + 'px');

                        self.container.appendChild(particle);
                        self.elements.push(particle);

                        setTimeout(() => {
                            if (particle.parentNode) {
                                particle.parentNode.removeChild(particle);
                                const index = self.elements.indexOf(particle);
                                if (index > -1) self.elements.splice(index, 1);
                            }
                        }, 1000);
                    }
                };

                launchFirework();
                self.intervals.fireworks = setInterval(launchFirework, frequency);
            }
        },

        // ====================================
        // NOEL
        // ====================================
        noel: {
            start(config) {
                console.log('🎄 Starting noel with config:', config);
                const self = SeasonalEffects;

                const intensity = config.intensity || 50;
                const symbols = ['🎄', '🎁'];

                const createElement = () => {
                    const element = document.createElement('div');
                    element.className = 'noel';
                    element.textContent = symbols[Math.floor(Math.random() * symbols.length)];
                    element.style.left = Math.random() * 100 + '%';
                    element.style.fontSize = (Math.random() * 1 + 1.5) + 'em';
                    element.style.animationDuration = (Math.random() * 5 + 8) + 's';
                    element.style.animationDelay = '0s';

                    self.container.appendChild(element);
                    self.elements.push(element);

                    const duration = parseFloat(element.style.animationDuration) * 1000;
                    setTimeout(() => {
                        if (element.parentNode) {
                            element.parentNode.removeChild(element);
                            const index = self.elements.indexOf(element);
                            if (index > -1) self.elements.splice(index, 1);
                        }
                    }, duration);
                };

                // Spawn rate dựa vào intensity
                const spawnRate = Math.max(200, 600 - intensity * 4);
                self.intervals.noel = setInterval(createElement, spawnRate);

                // Initial count dựa vào intensity
                const initialCount = Math.floor(intensity * 0.2);
                for (let i = 0; i < initialCount; i++) {
                    setTimeout(createElement, i * 200);
                }
            }
        },

        // ====================================
        // TẾT
        // ====================================
        tet: {
            start(config) {
                console.log('🧧 Starting tet with config:', config);
                const self = SeasonalEffects;

                const intensity = config.intensity || 50;
                const images = [
                    '/static/images/200-dong.png',
                    '/static/images/500-dong.png'
                ];

                const createElement = () => {
                    const element = document.createElement('div');
                    element.className = 'tet';

                    const img = document.createElement('img');
                    img.src = images[Math.floor(Math.random() * images.length)];
                    img.alt = 'Tiền Tết';
                    img.style.pointerEvents = 'none';

                    element.appendChild(img);
                    element.style.left = Math.random() * 100 + '%';
                    element.style.animationDuration = (Math.random() * 4 + 7) + 's';
                    element.style.animationDelay = '0s';

                    self.container.appendChild(element);
                    self.elements.push(element);

                    const duration = parseFloat(element.style.animationDuration) * 1000;
                    setTimeout(() => {
                        if (element.parentNode) {
                            element.parentNode.removeChild(element);
                            const index = self.elements.indexOf(element);
                            if (index > -1) self.elements.splice(index, 1);
                        }
                    }, duration);
                };

                // Spawn rate dựa vào intensity
                const spawnRate = Math.max(180, 580 - intensity * 4);
                self.intervals.tet = setInterval(createElement, spawnRate);

                // Initial count dựa vào intensity
                const initialCount = Math.floor(intensity * 0.24);
                for (let i = 0; i < initialCount; i++) {
                    setTimeout(createElement, i * 180);
                }
            }
        },

        // ====================================
        // FLAGS
        // ====================================
        flags: {
            start(config) {
                console.log('🇻🇳 Starting flags with config:', config);
                const self = SeasonalEffects;

                const intensity = config.intensity || 50;

                const createFlag = () => {
                    const flag = document.createElement('div');
                    flag.className = 'flag';

                    const img = document.createElement('img');
                    img.src = '/static/images/flag-vn.png';
                    img.alt = 'Cờ Việt Nam';
                    img.style.width = '40px';
                    img.style.height = 'auto';
                    img.style.pointerEvents = 'none';

                    flag.appendChild(img);
                    flag.style.left = Math.random() * 100 + '%';
                    flag.style.animationDuration = (Math.random() * 4 + 6) + 's';
                    flag.style.animationDelay = '0s';

                    self.container.appendChild(flag);
                    self.elements.push(flag);

                    const duration = parseFloat(flag.style.animationDuration) * 1000;
                    setTimeout(() => {
                        if (flag.parentNode) {
                            flag.parentNode.removeChild(flag);
                            const index = self.elements.indexOf(flag);
                            if (index > -1) self.elements.splice(index, 1);
                        }
                    }, duration);
                };

                // Spawn rate dựa vào intensity
                const spawnRate = Math.max(250, 650 - intensity * 4);
                self.intervals.flags = setInterval(createFlag, spawnRate);

                // Initial count dựa vào intensity
                const initialCount = Math.floor(intensity * 0.16);
                for (let i = 0; i < initialCount; i++) {
                    setTimeout(createFlag, i * 250);
                }
            }
        },

        // ====================================
        // SANTA CLAUS - ÔNG GIÀ NOEL
        // ====================================
        santa: {
            start(config) {
                console.log('🎅 Starting Santa effect with config:', config);

                // Hiển thị ông già Noel
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

// Expose globally
window.SeasonalEffects = SeasonalEffects;

console.log('🎨 Seasonal Effects script loaded');