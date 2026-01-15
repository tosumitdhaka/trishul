/* ============================================
   Main Application - With Sidebar Navigation
   ============================================ */

class MIBToolApp {
    constructor() {
        this.currentView = 'dashboard';
        this.sidebarCollapsed = false;
        this.appInfo = { name: 'Loading...', version: '...' };
        this.init();
    }

    /**
     * Initialize application
     */
    init() {
        console.log('🚀 Initializing...');

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.onReady());
        } else {
            this.onReady();
        }
    }

    /**
     * DOM ready handler
     */
    async onReady() {
        console.log('✅ DOM Ready');

        // ✅ CRITICAL: Setup global helpers FIRST
        this.setupGlobalHelpers();

        // ✅ NEW: Load app info from backend
        await this.loadAppInfo();

        // ✅ Load backend settings
        await window.settings.loadBackendSettings();
        
        if (window.settings.isBackendLoaded()) {
            // console.log('✅ Backend settings loaded successfully');
        } else {
            console.warn('⚠️ Backend settings failed to load, using defaults');
        }

        // Initialize core features
        this.setupSidebarNavigation();
        this.setupTheme();
        this.setupHealth();
        this.setupMobileMenu();

        // Show initial view
        this.showView(this.currentView);

        // Check API health
        this.checkHealth();

        console.log(`✅ ${this.appInfo.name} v${this.appInfo.version} is ready...`);
    }

    /**
     * ✅ UPDATED: Load app info from backend
     */
    async loadAppInfo() {
        try {
            const health = await api.healthCheck();
            
            if (health && health.service && health.version) {
                this.appInfo = {
                    name: health.service,
                    version: health.version
                };
                
                // Update page title
                document.title = `${this.appInfo.name} v${this.appInfo.version}`;
                
                // ✅ NEW: Update sidebar title
                const sidebarTitle = document.getElementById('sidebarTitle');
                if (sidebarTitle) {
                    sidebarTitle.textContent = this.appInfo.name;
                }
                
                // ✅ NEW: Update logo alt text
                const sidebarLogo = document.getElementById('sidebarLogo');
                if (sidebarLogo) {
                    sidebarLogo.alt = `${this.appInfo.name} Logo`;
                }
                
                // Update console banner
                console.log(
                    `%c ${this.appInfo.name} v${this.appInfo.version} `,
                    'background: #2563eb; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;'
                );
            }
        } catch (error) {
            console.warn('⚠️ Failed to load app info, using defaults:', error);
            this.appInfo = { name: 'Trishul', version: '1.3.0' };
            document.title = `${this.appInfo.name} v${this.appInfo.version}`;
            
            // Update sidebar with defaults
            const sidebarTitle = document.getElementById('sidebarTitle');
            if (sidebarTitle) {
                sidebarTitle.textContent = this.appInfo.name;
            }
        }
    }


    /**
     * Setup sidebar navigation
     */
    setupSidebarNavigation() {
        // Sidebar item clicks
        document.querySelectorAll('.sidebar-item, .sidebar-subitem').forEach((item) => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const view = item.dataset.view;
                const tab = item.dataset.tab;
                
                if (view) {
                    this.showView(view, tab);
                }
            });
        });

        // ✅ Auto-expand on parent click
        document.querySelectorAll('.sidebar-item-expandable').forEach((item) => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                
                const view = item.dataset.view;
                const parentItem = item.closest('.sidebar-parent-item');
                const submenu = parentItem?.querySelector('.sidebar-submenu');
                
                // ✅ Auto-expand submenu
                if (submenu && !submenu.classList.contains('show')) {
                    item.classList.add('expanded');
                    submenu.classList.add('show');
                }
                
                // Navigate to default tab (sender)
                if (view) {
                    this.showView(view, 'sender');
                }
            });
        });

        // Expand icon click (toggle)
        document.querySelectorAll('.sidebar-expand-icon').forEach((icon) => {
            icon.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                const item = icon.closest('.sidebar-item-expandable');
                const parentItem = item.closest('.sidebar-parent-item');
                const submenu = parentItem?.querySelector('.sidebar-submenu');
                
                if (item && submenu) {
                    item.classList.toggle('expanded');
                    submenu.classList.toggle('show');
                }
            });
        });

        // Sidebar toggle
        const sidebarToggle = document.getElementById('sidebarToggle');
        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', () => {
                this.toggleSidebar();
            });
        }

        // Add tooltips to sidebar items for collapsed state
        document.querySelectorAll('.sidebar-item').forEach((item) => {
            const text = item.querySelector('.sidebar-text');
            if (text) {
                item.setAttribute('data-tooltip', text.textContent);
            }
        });
    }

    /**
     * Toggle sidebar collapsed state
     */
    toggleSidebar() {
        const sidebar = document.getElementById('appSidebar');
        if (sidebar) {
            sidebar.classList.toggle('collapsed');
            this.sidebarCollapsed = !this.sidebarCollapsed;
            
            // Save preference
            localStorage.setItem('sidebarCollapsed', this.sidebarCollapsed);
        }
    }

    /**
     * Setup mobile menu
     */
    setupMobileMenu() {
        const mobileToggle = document.getElementById('mobileMenuToggle');
        const sidebar = document.getElementById('appSidebar');
        
        if (mobileToggle && sidebar) {
            mobileToggle.addEventListener('click', () => {
                sidebar.classList.toggle('mobile-open');
                
                // Add/remove overlay
                let overlay = document.querySelector('.sidebar-overlay');
                if (!overlay) {
                    overlay = document.createElement('div');
                    overlay.className = 'sidebar-overlay';
                    document.body.appendChild(overlay);
                    
                    overlay.addEventListener('click', () => {
                        sidebar.classList.remove('mobile-open');
                        overlay.classList.remove('show');
                    });
                }
                
                overlay.classList.toggle('show');
            });
        }

        // Close mobile menu when clicking sidebar items
        document.querySelectorAll('.sidebar-item, .sidebar-subitem').forEach((item) => {
            item.addEventListener('click', () => {
                if (window.innerWidth <= 768) {
                    sidebar?.classList.remove('mobile-open');
                    document.querySelector('.sidebar-overlay')?.classList.remove('show');
                }
            });
        });
    }

    /**
     * Show view
     */
    showView(viewName, subTab = null) {
        // Update sidebar active state
        document.querySelectorAll('.sidebar-item, .sidebar-subitem').forEach((item) => {
            const itemView = item.dataset.view;
            const itemTab = item.dataset.tab;
            
            // For items with tabs (like Traps sub-items)
            if (itemTab) {
                const isActive = itemView === viewName && itemTab === subTab;
                item.classList.toggle('active', isActive);
            } 
            // For parent items (like Traps main item)
            else if (item.classList.contains('sidebar-item-expandable')) {
                const isActive = itemView === viewName;
                item.classList.toggle('active', isActive);
            }
            // For regular items
            else {
                const isActive = itemView === viewName && !subTab;
                item.classList.toggle('active', isActive);
            }
        });

        // Update views
        document.querySelectorAll('.view').forEach((view) => {
            // Convert view name to match ID format (e.g., 'snmp-walk' → 'snmpWalkView')
            const viewId = viewName.replace(/-([a-z])/g, (g) => g[1].toUpperCase()) + 'View';
            view.classList.toggle('active', view.id === viewId);
        });


        // Update page title
        const pageTitle = document.getElementById('pageTitle');
        if (pageTitle) {
            pageTitle.textContent = this.getViewTitle(viewName);
        }

        this.currentView = viewName;

        // Trigger view-specific actions
        this.onViewChange(viewName, subTab);

        // Update URL hash
        history.pushState({ view: viewName, tab: subTab }, '', `#${viewName}${subTab ? `/${subTab}` : ''}`);
    }

    /**
     * Get view title
     */
    getViewTitle(viewName) {
        const titles = {
            dashboard: 'Dashboard',
            parser: 'MIB Parser',
            database: 'Database Explorer',
            jobs: 'Background Jobs',
            traps: 'SNMP Traps',
            'snmp-walk': 'SNMP Walk',   
            protobuf: 'Protobuf Decoder',
            settings: 'Settings'
        };
        return titles[viewName] || this.appInfo.name;  // ✅ CHANGED: Use app name as fallback
    }

    /**
     * Handle view change
     */
    onViewChange(viewName, subTab = null) {
        switch (viewName) {
            case 'dashboard':
                // ✅ NEW: Initialize dashboard when viewed
                if (window.dashboardComponent) {
                    window.dashboardComponent.init();
                }
                break;

            case 'database':
                if (window.databaseComponent) {
                    window.databaseComponent.init();
                }
                break;

            case 'jobs':
                if (window.jobsComponent) {
                    window.jobsComponent.loadJobs();
                }
                break;

            case 'parser':
                break;

            case 'traps':
                // ✅ Handle traps sub-tabs from sidebar
                if (window.trapsComponent) {
                    const tab = subTab || 'sender'; // Default to sender
                    window.trapsComponent.switchTab(tab);
                }
                break;

            case 'snmp-walk':
                if (window.snmpWalkComponent) {
                    window.snmpWalkComponent.switchTab(subTab);
                }
                break;

            case 'protobuf':
                break;

            case 'settings':
                if (window.settingsComponent) {
                    window.settingsComponent.init();
                    window.settingsComponent.render();
                }
                break;
        }
    }

    /**
     * Setup theme
     */
    setupTheme() {
        const themeToggle = document.getElementById('themeToggle');
        if (!themeToggle) return;

        themeToggle.addEventListener('click', () => {
            const newTheme = window.settings.toggleTheme();
            this.updateThemeIcon(newTheme);
        });

        // Set initial icon
        const currentTheme = window.settings.get('theme', 'light');
        this.updateThemeIcon(currentTheme);
    }

    /**
     * Update theme icon
     */
    updateThemeIcon(theme) {
        const icon = document.querySelector('#themeToggle .icon');
        if (!icon) return;

        if (theme === 'dark') {
            // Sun icon (for switching to light)
            icon.innerHTML = `
                <circle cx="12" cy="12" r="5"/>
                <line x1="12" y1="1" x2="12" y2="3"/>
                <line x1="12" y1="21" x2="12" y2="23"/>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                <line x1="1" y1="12" x2="3" y2="12"/>
                <line x1="21" y1="12" x2="23" y2="12"/>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
            `;
        } else {
            // Moon icon (for switching to dark)
            icon.innerHTML = `<path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>`;
        }
    }

    /**
     * Setup health status
     */
    setupHealth() {
        const healthStatus = document.getElementById('healthStatus');
        if (!healthStatus) return;

        // Check health every 30 seconds
        setInterval(() => this.checkHealth(), 30000);

        // Show health details on click
        healthStatus.addEventListener('click', () => {
            this.showHealthDetails();
        });
    }

    /**
     * Check API health
     */
    async checkHealth() {
        const healthStatus = document.getElementById('healthStatus');
        if (!healthStatus) return;

        const statusDot = healthStatus.querySelector('.status-dot');

        try {
            const health = await api.healthCheck();

            if (health.status === 'healthy') {
                statusDot.className = 'status-dot';
                healthStatus.title = 'System Status: Healthy';
            } else if (health.status === 'degraded' || health.status === 'warning') {
                statusDot.className = 'status-dot warning';
                healthStatus.title = 'System Status: Degraded';
            } else {
                statusDot.className = 'status-dot error'; // Red
                healthStatus.title = 'System Status: Error';
            }
        } catch (error) {
            statusDot.className = 'status-dot error';
            healthStatus.title = 'System Status: Offline';
            console.error('Health check failed:', error);
        }
    }

    /**
     * Show health details modal
     */
    async showHealthDetails() {
        try {
            const health = await api.healthCheck();

            const content = `
                <div style="display: grid; gap: var(--spacing-md);">
                    <div class="stat-card" style="text-align: center;">
                        <div class="stat-value" style="color: ${health.status === 'healthy' ? 'var(--color-success)' : 'var(--color-warning)'};">
                            ${health.status === 'healthy' ? '✓' : '⚠'}
                        </div>
                        <div class="stat-label">Status: ${health.status}</div>
                    </div>
                    
                    <div>
                        <label style="font-size: 0.75rem; color: var(--color-text-secondary); display: block; margin-bottom: var(--spacing-xs);">
                            Service
                        </label>
                        <div style="color: var(--color-text);">
                            ${health.service || this.appInfo.name}
                        </div>
                    </div>
                    
                    <div>
                        <label style="font-size: 0.75rem; color: var(--color-text-secondary); display: block; margin-bottom: var(--spacing-xs);">
                            Version
                        </label>
                        <div style="color: var(--color-text);">
                            ${health.version || this.appInfo.version}
                        </div>
                    </div>
                    
                    <div>
                        <label style="font-size: 0.75rem; color: var(--color-text-secondary); display: block; margin-bottom: var(--spacing-xs);">
                            Timestamp
                        </label>
                        <div style="color: var(--color-text);">
                            ${Utils.formatDateTime(health.timestamp)}
                        </div>
                    </div>
                    
                    ${health.databases ? `
                        <div>
                            <label style="font-size: 0.75rem; color: var(--color-text-secondary); display: block; margin-bottom: var(--spacing-xs);">
                                Database Status
                            </label>
                            <div style="color: var(--color-text);">
                                ${health.database_status === 'healthy' ? '✅ All databases healthy' : '⚠️ Some databases degraded'}
                            </div>
                        </div>
                    ` : ''}
                </div>
            `;

            modal.show({
                title: 'System Health',
                content: content,
                size: 'medium',
                buttons: [
                    {
                        text: 'Close',
                        class: 'btn-primary',
                        onClick: () => modal.close(),
                    },
                ],
            });
        } catch (error) {
            notify.error(`Failed to get health status: ${error.message}`);
        }
    }

    /**
     * Setup global helpers
     */
    setupGlobalHelpers() {

        // ✅ NEW: Global app info getter
        window.getAppInfo = () => {
            return this.appInfo;
        };
        
        // Loading overlay
        window.showLoading = (message = 'Loading...') => {
            const overlay = document.getElementById('loadingOverlay');
            const text = document.getElementById('loadingText');
            if (overlay) {
                overlay.style.display = 'flex';
                if (text) text.textContent = message;
            }
        };

        window.hideLoading = () => {
            const overlay = document.getElementById('loadingOverlay');
            if (overlay) {
                overlay.style.display = 'none';
            }
        };

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + K for search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                const searchInput = document.querySelector(
                    '.search-input:not([style*="display: none"])'
                );
                if (searchInput) {
                    searchInput.focus();
                }
            }

            // ESC to close modals
            if (e.key === 'Escape') {
                if (window.modal && window.modal.currentModal) {
                    window.modal.close();
                }
            }

            // Ctrl/Cmd + B to toggle sidebar
            if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
                e.preventDefault();
                this.toggleSidebar();
            }
        });

        // Handle browser back/forward
        window.addEventListener('popstate', (e) => {
            if (e.state && e.state.view) {
                this.showView(e.state.view, e.state.tab);
            }
        });

        // Restore view from URL hash
        const hash = window.location.hash.slice(1);
        if (hash) {
            const [view, tab] = hash.split('/');
            if (['dashboard', 'parser', 'database', 'jobs', 'traps', 'snmp-walk', 'protobuf', 'settings'].includes(view)) {
                this.currentView = view;
            }
        }

        // Restore sidebar collapsed state
        const savedCollapsed = localStorage.getItem('sidebarCollapsed');
        if (savedCollapsed === 'true') {
            const sidebar = document.getElementById('appSidebar');
            if (sidebar) {
                sidebar.classList.add('collapsed');
                this.sidebarCollapsed = true;
            }
        }
    }

    /**
     * Show error page
     */
    showError(title, message) {
        const content = `
            <div style="text-align: center; padding: var(--spacing-xl);">
                <svg style="width: 64px; height: 64px; color: var(--color-danger); margin-bottom: var(--spacing-lg);" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="15" y1="9" x2="9" y2="15"/>
                    <line x1="9" y1="9" x2="15" y2="15"/>
                </svg>
                <h2 style="margin: 0 0 var(--spacing-md) 0; color: var(--color-text);">${title}</h2>
                <p style="color: var(--color-text-secondary); margin: 0;">${message}</p>
            </div>
        `;

        modal.show({
            title: 'Error',
            content: content,
            size: 'medium',
            buttons: [
                {
                    text: 'Close',
                    class: 'btn-primary',
                    onClick: () => modal.close(),
                },
            ],
        });
    }

    /**
     * Get current view
     */
    getCurrentView() {
        return this.currentView;
    }

    /**
     * Refresh current view
     */
    refreshCurrentView() {
        this.onViewChange(this.currentView);
    }
}

// Initialize app
window.app = new MIBToolApp();

// Global error handler
window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);

    if (event.error && event.error.message && event.error.message.includes('critical')) {
        window.app.showError('Application Error', event.error.message);
    }
});

// Global unhandled promise rejection handler
window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);

    if (event.reason && event.reason.message && event.reason.message.includes('critical')) {
        window.app.showError('Promise Error', event.reason.message);
    }
});

