/**
 * SSE Manager v2 - Optimized for Many Users
 * Auto-reconnect + Smart fallback + Resource efficient
 */

class SSEManager {
    constructor() {
        this.connections = new Map();
        this.reconnectAttempts = new Map();
        this.reconnectTimers = new Map();
        this.pollingFallbacks = new Map();

        // Configuration
        this.maxReconnectAttempts = 3;
        this.baseReconnectDelay = 3000;     // ✅ 3 giây
        this.maxReconnectDelay = 60000;     // ✅ 60 giây
        this.maxConnections = 3;            //  Giới hạn 3 SSE/user

        this.sseSupported = typeof EventSource !== 'undefined';

        console.log('🚀 SSE Manager v2 initialized', { sseSupported: this.sseSupported });
    }

    /* Connect to SSE endpoint with auto-reconnect*/
    connect(name, url, callbacks, fallbackConfig = null) {
        // check connection limit
        if (this.connections.size >= this.maxConnections && !this.connections.has(name)) {
            console.warn(` Max ${this.maxConnections} SSE connections, using polling for ${name}`);
            if (fallbackConfig) {
                this.startPollingFallback(name, fallbackConfig);
            }
            return;
        }

        if (!this.sseSupported) {
            console.warn(` SSE not supported, using polling for ${name}`);
            this.startPollingFallback(name, fallbackConfig);
            return;
        }

        // Clear any pending reconnect
        this.clearReconnectTimer(name);

        // Close existing connection
        if (this.connections.has(name)) {
            this.disconnect(name, false); // Don't clear attempts
        }

        console.log(`📡 Connecting SSE: ${name}`);

        try {
            const eventSource = new EventSource(url);
            let isConnected = false;

            eventSource.onopen = () => {
                console.log(`✅ SSE connected: ${name}`);
                isConnected = true;
                this.reconnectAttempts.set(name, 0);
                this.stopPollingFallback(name);
                if (callbacks.onOpen) callbacks.onOpen();
            };

            eventSource.onerror = (error) => {
                const attempts = this.reconnectAttempts.get(name) || 0;
                console.error(`❌ SSE error: ${name}, attempts: ${attempts}`);

                if (callbacks.onError) callbacks.onError(error, attempts);

                // EventSource auto-reconnects, but we track attempts
                if (eventSource.readyState === EventSource.CLOSED) {
                    this.handleDisconnect(name, callbacks, fallbackConfig);
                }
            };

            // Register event handlers
            if (callbacks.events) {
                for (const [eventName, handler] of Object.entries(callbacks.events)) {
                    eventSource.addEventListener(eventName, (e) => {
                        try {
                            const data = JSON.parse(e.data);

                            // Handle server-initiated close/reconnect
                            if (data.type === 'reconnect' || data.type === 'timeout') {
                                console.log(`🔄 Server requested reconnect for ${name}`);
                                eventSource.close();
                                this.scheduleReconnect(name, url, callbacks, fallbackConfig, 1000);
                                return;
                            }

                            handler(data, e);
                        } catch (err) {
                            console.error(`Error parsing SSE ${eventName}:`, err);
                        }
                    });
                }
            }

            eventSource.onmessage = (e) => {
                if (callbacks.onMessage) {
                    try {
                        callbacks.onMessage(JSON.parse(e.data), e);
                    } catch (err) {
                        console.error('Error parsing SSE message:', err);
                    }
                }
            };

            this.connections.set(name, {
                eventSource,
                callbacks,
                fallbackConfig,
                url,
                connectedAt: Date.now()
            });

        } catch (error) {
            console.error(`Failed to create SSE for ${name}:`, error);
            if (fallbackConfig) this.startPollingFallback(name, fallbackConfig);
        }
    }

    /**
     * Handle disconnection with exponential backoff
     */
    handleDisconnect(name, callbacks, fallbackConfig) {
        const attempts = (this.reconnectAttempts.get(name) || 0) + 1;
        this.reconnectAttempts.set(name, attempts);

        if (attempts <= this.maxReconnectAttempts) {
            // Exponential backoff: 2s, 4s, 8s, 16s, 30s
            const delay = Math.min(
                this.baseReconnectDelay * Math.pow(2, attempts - 1),
                this.maxReconnectDelay
            );
            console.log(`🔄 Reconnecting ${name} in ${delay}ms (attempt ${attempts}/${this.maxReconnectAttempts})`);

            const conn = this.connections.get(name);
            if (conn) {
                this.scheduleReconnect(name, conn.url, callbacks, fallbackConfig, delay);
            }
        } else {
            console.warn(`⚠️ Max reconnect attempts for ${name}, switching to polling`);
            this.connections.delete(name);
            if (fallbackConfig) this.startPollingFallback(name, fallbackConfig);
        }
    }

    /**
     * Schedule a reconnect attempt
     */
    scheduleReconnect(name, url, callbacks, fallbackConfig, delay) {
        this.clearReconnectTimer(name);

        const timer = setTimeout(() => {
            this.connect(name, url, callbacks, fallbackConfig);
        }, delay);

        this.reconnectTimers.set(name, timer);
    }

    /**
     * Clear reconnect timer
     */
    clearReconnectTimer(name) {
        const timer = this.reconnectTimers.get(name);
        if (timer) {
            clearTimeout(timer);
            this.reconnectTimers.delete(name);
        }
    }

    /**
     * Disconnect from SSE
     */
    disconnect(name, clearAttempts = true) {
        this.clearReconnectTimer(name);

        const conn = this.connections.get(name);
        if (conn) {
            console.log(`🔌 Disconnecting SSE: ${name}`);
            conn.eventSource.close();
            this.connections.delete(name);
        }

        this.stopPollingFallback(name);
        if (clearAttempts) this.reconnectAttempts.delete(name);
    }

    /**
     * Disconnect all
     */
    disconnectAll() {
        console.log('🔌 Disconnecting all SSE');
        for (const name of this.connections.keys()) {
            this.disconnect(name);
        }
    }

    /**
     * Start polling fallback
     */
    startPollingFallback(name, config) {
        if (!config) return;

        this.stopPollingFallback(name);
        console.log(`🔄 Starting polling for ${name} (${config.interval}ms)`);

        const poll = async () => {
            try {
                const response = await fetch(config.url);
                if (response.ok && config.onData) {
                    config.onData(await response.json());
                }
            } catch (e) {
                console.error(`Polling error for ${name}:`, e);
            }
        };

        poll(); // Initial
        const intervalId = setInterval(poll, config.interval);
        this.pollingFallbacks.set(name, intervalId);
    }

    /**
     * Stop polling fallback
     */
    stopPollingFallback(name) {
        const id = this.pollingFallbacks.get(name);
        if (id) {
            clearInterval(id);
            this.pollingFallbacks.delete(name);
        }
    }

    /**
     * Check connection status
     */
    isConnected(name) {
        const conn = this.connections.get(name);
        return conn && conn.eventSource.readyState === EventSource.OPEN;
    }

    /**
     * Get status info
     */
    getStatus(name) {
        const conn = this.connections.get(name);
        if (!conn) {
            return {
                connected: false,
                type: this.pollingFallbacks.has(name) ? 'polling' : 'disconnected',
                reconnectAttempts: this.reconnectAttempts.get(name) || 0
            };
        }
        return {
            connected: conn.eventSource.readyState === EventSource.OPEN,
            type: 'sse',
            connectedAt: conn.connectedAt,
            reconnectAttempts: this.reconnectAttempts.get(name) || 0
        };
    }
}

// Global instance
window.sseManager = new SSEManager();

// Cleanup on unload
window.addEventListener('beforeunload', () => {
    window.sseManager.disconnectAll();
});

// Handle visibility - reconnect when tab becomes visible
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        console.log('📴 Tab hidden');
    } else {
        console.log('📳 Tab visible');
        // Check and reconnect any closed connections
        for (const [name, conn] of window.sseManager.connections) {
            if (conn.eventSource.readyState === EventSource.CLOSED) {
                console.log(`🔄 Reconnecting ${name} after tab visible`);
                window.sseManager.connect(name, conn.url, conn.callbacks, conn.fallbackConfig);
            }
        }
    }
});