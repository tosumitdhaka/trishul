/* ============================================
   Settings Service - LocalStorage Management
   ============================================ */

class SettingsService {
    constructor() {
        this.storageKey = 'mib_tool_settings';
        this.defaults = {
            // Display Settings
            theme: 'light',
            tablePageSize: 50,
            tableMaxResults: 1000,
            dateFormat: 'YYYY-MM-DD HH:mm:ss',

            // Parser Settings
            parserDeduplicate: true,
            parserDedupStrategy: 'smart',
            parserAutoDetect: true,

            // Database Settings
            dbDefaultImportMode: 'replace',
            dbAutoCreateIndexes: true,

            // Export Settings
            exportDefaultFormat: 'csv',
            exportIncludeHeaders: true,
            exportCompression: 'none',

            // Jobs Settings
            jobsAutoRefresh: true,
            jobsRefreshInterval: 5000, // 5 seconds
            jobsKeepHistoryDays: 30,

            // Table Settings
            tableColumns: {}, // Per-view column preferences
            tableFilters: {}, // Saved filters
            tableSortOrder: {}, // Saved sort preferences
        };

        this.settings = this.load();
        this.listeners = [];
        this.backendSettings = null;
    }

    /**
     * Load settings from localStorage
     */
    load() {
        try {
            const stored = localStorage.getItem(this.storageKey);
            if (stored) {
                const parsed = JSON.parse(stored);
                // Merge with defaults to ensure all keys exist
                return { ...this.defaults, ...parsed };
            }
        } catch (error) {
            console.error('Failed to load settings:', error);
        }
        return { ...this.defaults };
    }

    /**
     * Save settings to localStorage
     */
    save() {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(this.settings));
            this.notifyListeners();
            return true;
        } catch (error) {
            console.error('Failed to save settings:', error);
            return false;
        }
    }

    /**
     * Get a setting value
     */
    get(key, defaultValue = null) {
        const keys = key.split('.');
        let value = this.settings;

        for (const k of keys) {
            if (value && typeof value === 'object' && k in value) {
                value = value[k];
            } else {
                return defaultValue !== null ? defaultValue : this.defaults[key];
            }
        }

        return value;
    }

    /**
     * Set a setting value
     */
    set(key, value) {
        const keys = key.split('.');
        let target = this.settings;

        for (let i = 0; i < keys.length - 1; i++) {
            const k = keys[i];
            if (!(k in target) || typeof target[k] !== 'object') {
                target[k] = {};
            }
            target = target[k];
        }

        target[keys[keys.length - 1]] = value;
        this.save();
    }

    /**
     * Get all settings
     */
    getAll() {
        return { ...this.settings };
    }

    /**
     * Update multiple settings at once
     */
    update(updates) {
        Object.keys(updates).forEach((key) => {
            this.set(key, updates[key]);
        });
    }

    /**
     * Reset to defaults
     */
    reset(category = null) {
        if (category) {
            // Reset specific category
            const categoryKeys = Object.keys(this.defaults).filter((key) =>
                key.toLowerCase().startsWith(category.toLowerCase())
            );
            categoryKeys.forEach((key) => {
                this.settings[key] = this.defaults[key];
            });
        } else {
            // Reset all
            this.settings = { ...this.defaults };
        }
        this.save();
    }

    /**
     * Export settings as JSON
     */
    export() {
        return JSON.stringify(this.settings, null, 2);
    }

    /**
     * Import settings from JSON
     */
    import(jsonString) {
        try {
            const imported = JSON.parse(jsonString);
            this.settings = { ...this.defaults, ...imported };
            this.save();
            return true;
        } catch (error) {
            console.error('Failed to import settings:', error);
            return false;
        }
    }

    /**
     * Add change listener
     */
    onChange(callback) {
        this.listeners.push(callback);
        return () => {
            this.listeners = this.listeners.filter((cb) => cb !== callback);
        };
    }

    /**
     * Notify all listeners
     */
    notifyListeners() {
        this.listeners.forEach((callback) => {
            try {
                callback(this.settings);
            } catch (error) {
                console.error('Settings listener error:', error);
            }
        });
    }

    /**
     * Apply theme
     */
    applyTheme() {
        const theme = this.get('theme', 'light');
        document.documentElement.setAttribute('data-theme', theme);
    }

    /**
     * Toggle theme
     */
    toggleTheme() {
        const current = this.get('theme', 'light');
        const newTheme = current === 'light' ? 'dark' : 'light';
        this.set('theme', newTheme);
        this.applyTheme();
        return newTheme;
    }

    /**
     * Get table column preferences
     */
    getTableColumns(viewName) {
        return this.get(`tableColumns.${viewName}`, null);
    }

    /**
     * Save table column preferences
     */
    setTableColumns(viewName, columns) {
        this.set(`tableColumns.${viewName}`, columns);
    }

    /**
     * Get table filters
     */
    getTableFilters(viewName) {
        return this.get(`tableFilters.${viewName}`, []);
    }

    /**
     * Save table filters
     */
    setTableFilters(viewName, filters) {
        this.set(`tableFilters.${viewName}`, filters);
    }

    /**
     * Get table sort order
     */
    getTableSort(viewName) {
        return this.get(`tableSortOrder.${viewName}`, null);
    }

    /**
     * Save table sort order
     */
    setTableSort(viewName, sortOrder) {
        this.set(`tableSortOrder.${viewName}`, sortOrder);
    }

    /**
     * ✅ NEW: Load backend settings from API
     * @returns {Promise<Object|null>} Backend settings or null if failed
     */
    async loadBackendSettings() {
        try {
            // console.log('🔄 Loading backend settings from API...');
            const response = await window.api.getAllSettings();
            
            if (response && response.success && response.settings) {
                this.backendSettings = response.settings;
                // console.log('✅ Backend settings loaded:', this.backendSettings);
                return this.backendSettings;
            } else {
                console.warn('⚠️ Invalid backend settings response:', response);
                return null;
            }
        } catch (error) {
            console.error('❌ Failed to load backend settings:', error);
            return null;
        }
    }

    /**
     * ✅ NEW: Get backend setting (nested path support)
     * @param {string} path - Dot-separated path (e.g., 'ui.data_table.max_height_px')
     * @param {*} defaultValue - Default value if not found
     * @returns {*} Setting value or default
     */
    getBackend(path, defaultValue = null) {
        if (!this.backendSettings) {
            console.warn('⚠️ Backend settings not loaded yet, returning default');
            return defaultValue;
        }
        
        const keys = path.split('.');
        let value = this.backendSettings;
        
        for (const key of keys) {
            if (value && typeof value === 'object' && key in value) {
                value = value[key];
            } else {
                return defaultValue;
            }
        }
        
        return value;
    }

    /**
     * ✅ NEW: Check if backend settings are loaded
     * @returns {boolean} True if loaded
     */
    isBackendLoaded() {
        return this.backendSettings !== null;
    }


}

// Create global instance
window.settings = new SettingsService();

// Apply theme on load
window.settings.applyTheme();
