/* ============================================
   Dashboard Component - Refactored with Shared Methods
   ============================================ */

class DashboardComponent {
    constructor() {
        this.recentActivity = [];
        this.initialized = false;
        this.monitoringStatus = null;
    }

    async init() {
        if (this.initialized) return;
        
        // Check monitoring status
        await this.checkMonitoringStatus();
        
        this.render();
        this.initialized = true;
    }

    /**
     * Check if monitoring is available
     */
    async checkMonitoringStatus() {
        try {
            const response = await fetch('/api/v1/metrics/prometheus/health');
            this.monitoringStatus = await response.json();
        } catch (error) {
            console.warn('Failed to check monitoring status:', error);
            this.monitoringStatus = {
                available: false,
                enabled: false,
                deployment_type: 'Unknown',
                status: 'error',
                message: 'Failed to check monitoring status'
            };
        }
    }

    // ============================================
    // SHARED RENDERING METHODS
    // ============================================

    /**
     * ✅ NEW: Render a tool card (handles all types)
     * 
     * @param {Object} tool - Tool configuration
     * @param {string} tool.name - Tool name
     * @param {string} tool.icon - SVG icon path
     * @param {string} tool.description - Tool description
     * @param {string} tool.color - Color theme (primary, success, warning, etc.)
     * @param {string} [tool.view] - Internal view name (for navigation)
     * @param {string} [tool.tab] - Sub-tab for view
     * @param {string} [tool.url] - External URL
     * @param {boolean} [tool.external] - Is external link
     * @param {boolean} [tool.disabled] - Is disabled (NA)
     * @param {string} [tool.disabledReason] - Reason for disabled state
     * @returns {string} HTML string
     */
    renderToolCard(tool) {
        // Disabled tool (NA)
        if (tool.disabled) {
            return `
                <div class="tool-card tool-card-disabled" title="${tool.disabledReason || tool.description}">
                    <div class="tool-card-icon" style="background: var(--color-${tool.color}-light); color: var(--color-${tool.color}); opacity: 0.5;">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            ${tool.icon}
                        </svg>
                    </div>
                    <div class="tool-card-content">
                        <h4 class="tool-card-title" style="opacity: 0.6;">
                            ${tool.name}
                            <span style="font-size: 0.7em; color: var(--color-text-secondary);">(NA)</span>
                        </h4>
                        <p class="tool-card-description" style="opacity: 0.6;">${tool.description}</p>
                    </div>
                    <div class="tool-card-arrow" style="opacity: 0.3;">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <line x1="18" y1="6" x2="6" y2="18"/>
                            <line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                    </div>
                </div>
            `;
        }

        // External link
        if (tool.external) {
            return `
                <div class="tool-card" onclick="window.open('${tool.url}', '_blank')">
                    <div class="tool-card-icon" style="background: var(--color-${tool.color}-light); color: var(--color-${tool.color});">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            ${tool.icon}
                        </svg>
                    </div>
                    <div class="tool-card-content">
                        <h4 class="tool-card-title">
                            ${tool.name}
                            <svg style="width: 14px; height: 14px; margin-left: 4px; opacity: 0.6;" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/>
                                <polyline points="15 3 21 3 21 9"/>
                                <line x1="10" y1="14" x2="21" y2="3"/>
                            </svg>
                        </h4>
                        <p class="tool-card-description">${tool.description}</p>
                    </div>
                    <div class="tool-card-arrow">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <polyline points="9 18 15 12 9 6"/>
                        </svg>
                    </div>
                </div>
            `;
        }
        
        // Internal view navigation
        const onClick = tool.tab 
            ? `app.showView('${tool.view}', '${tool.tab}')`
            : `app.showView('${tool.view}')`;

        return `
            <div class="tool-card" onclick="${onClick}">
                <div class="tool-card-icon" style="background: var(--color-${tool.color}-light); color: var(--color-${tool.color});">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        ${tool.icon}
                    </svg>
                </div>
                <div class="tool-card-content">
                    <h4 class="tool-card-title">${tool.name}</h4>
                    <p class="tool-card-description">${tool.description}</p>
                </div>
                <div class="tool-card-arrow">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <polyline points="9 18 15 12 9 6"/>
                    </svg>
                </div>
            </div>
        `;
    }

    /**
     * ✅ NEW: Render a quick action button
     * 
     * @param {Object} action - Action configuration
     * @param {string} action.label - Button label
     * @param {string} action.icon - SVG icon path
     * @param {string} [action.view] - Internal view name
     * @param {string} [action.tab] - Sub-tab for view
     * @param {string} [action.url] - External URL
     * @param {boolean} [action.external] - Is external link
     * @returns {string} HTML string
     */
    renderQuickActionButton(action) {
        let onClick;
        
        if (action.external) {
            onClick = `window.open('${action.url}', '_blank')`;
        } else if (action.tab) {
            onClick = `app.showView('${action.view}', '${action.tab}')`;
        } else {
            onClick = `app.showView('${action.view}')`;
        }

        return `
            <button class="quick-action-btn" onclick="${onClick}">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    ${action.icon}
                </svg>
                <span>${action.label}</span>
                ${action.external ? `
                    <svg style="width: 12px; height: 12px; margin-left: 4px; opacity: 0.6;" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/>
                        <polyline points="15 3 21 3 21 9"/>
                        <line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                ` : ''}
            </button>
        `;
    }

    /**
     * ✅ NEW: Check if a monitoring tool should be shown
     * 
     * @param {string} toolName - Tool name (prometheus, alertmanager, grafana)
     * @returns {Object} { show: boolean, disabled: boolean, reason: string }
     */
    getMonitoringToolStatus(toolName) {
        if (!this.monitoringStatus) {
            return { show: false, disabled: false, reason: 'Status unknown' };
        }

        const available = this.monitoringStatus.available;
        const enabled = this.monitoringStatus.enabled;

        if (available) {
            return { show: true, disabled: false, reason: null };
        } else if (enabled === false) {
            return { 
                show: true, 
                disabled: true, 
                reason: `Not available in ${this.monitoringStatus.deployment_type} mode` 
            };
        } else {
            return { show: false, disabled: false, reason: 'Not configured' };
        }
    }

    // ============================================
    // TOOL DEFINITIONS
    // ============================================

    /**
     * Get FM (Fault Management) tools configuration
     */
    getFMTools() {
        const tools = [
            {
                name: 'Parser',
                icon: `<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>`,
                description: 'Parse and compile SNMP MIB files',
                view: 'parser',
                color: 'primary'
            },
            {
                name: 'Database',
                icon: `<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>`,
                description: 'Query and explore parsed MIB data',
                view: 'database',
                color: 'success'
            },
            {
                name: 'Jobs',
                icon: `<rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/>`,
                description: 'Monitor background parsing jobs',
                view: 'jobs',
                color: 'warning'
            },
            {
                name: 'SNMP Traps',
                icon: `<path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5M2 12l10 5 10-5"/>`,
                description: 'Send and receive SNMP v2c traps',
                view: 'traps',
                tab: 'sender',
                color: 'accent'
            }
        ];

        // ✅ NEW: Add Alertmanager if available (example for future)
        // const alertmanagerStatus = this.getMonitoringToolStatus('alertmanager');
        // if (alertmanagerStatus.show) {
        //     tools.push({
        //         name: 'Alertmanager',
        //         icon: `<path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>`,
        //         description: 'Manage alerts and notifications',
        //         external: true,
        //         url: '/alertmanager',
        //         color: 'danger',
        //         disabled: alertmanagerStatus.disabled,
        //         disabledReason: alertmanagerStatus.reason
        //     });
        // }

        return tools;
    }

    /**
     * Get PM (Performance Management) tools configuration
     */
    getPMTools() {
        const tools = [
            {
                name: 'SNMP Walk',
                icon: `<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>`,
                description: 'Walk SNMP OID trees and collect data',
                view: 'snmp-walk',
                color: 'info'
            },
            {
                name: 'Protobuf Decoder',
                icon: `<rect x="4" y="4" width="16" height="16" rx="2" ry="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/>`,
                description: 'Decode binary protobuf data using schema files',
                view: 'protobuf',
                color: 'info'
            }
        ];

        // ✅ Add Prometheus if available
        const prometheusStatus = this.getMonitoringToolStatus('prometheus');
        if (prometheusStatus.show) {
            tools.push({
                name: 'Prometheus',
                icon: `<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/><circle cx="12" cy="12" r="10"/>`,
                description: 'View metrics and create custom queries',
                external: true,
                url: 'http://192.168.151.114:30090',
                color: 'warning',
                disabled: prometheusStatus.disabled,
                disabledReason: prometheusStatus.reason
            });
        }

        return tools;
    }

    /**
     * Get quick actions configuration
     */
    getQuickActions() {
        const actions = [
            {
                label: 'Parse New MIB',
                icon: `<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/>`,
                view: 'parser'
            },
            {
                label: 'Query Database',
                icon: `<circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>`,
                view: 'database'
            },
            {
                label: 'Send Trap',
                icon: `<line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>`,
                view: 'traps',
                tab: 'sender'
            },
            {
                label: 'SNMP Walk',
                icon: `<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>`,
                view: 'snmp-walk'
            },
            {
                label: 'Decode Protobuf',
                icon: `<rect x="4" y="4" width="16" height="16" rx="2" ry="2"/><rect x="9" y="9" width="6" height="6"/>`,
                view: 'protobuf'
            }
        ];

        // ✅ Add Prometheus if available
        const prometheusStatus = this.getMonitoringToolStatus('prometheus');
        if (prometheusStatus.show && !prometheusStatus.disabled) {
            actions.push({
                label: 'Prometheus',
                icon: `<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>`,
                external: true,
                url: 'http://192.168.151.114:30090'
            });
        }

        return actions;
    }

    // ============================================
    // RENDERING METHODS
    // ============================================

    renderFMTools() {
        return this.getFMTools()
            .map(tool => this.renderToolCard(tool))
            .join('');
    }

    renderPMTools() {
        return this.getPMTools()
            .map(tool => this.renderToolCard(tool))
            .join('');
    }

    renderQuickActions() {
        return this.getQuickActions()
            .map(action => this.renderQuickActionButton(action))
            .join('');
    }

    render() {
        const container = document.getElementById('dashboardContent');
        if (!container) return;

        const appInfo = window.getAppInfo ? window.getAppInfo() : { name: 'Loading...', version: '...' };

        container.innerHTML = `
            <!-- Welcome Section -->
            <div class="dashboard-welcome">
                <h2>Welcome to ${appInfo.name}</h2>
                <p>Comprehensive network management tool for Fault, Configuration, Accounting, Performance, and Security monitoring.</p>
            </div>

            <!-- Tool Categories -->
            <div class="dashboard-section">
                <h3 class="dashboard-section-title">
                    <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                        <path d="M2 17l10 5 10-5M2 12l10 5 10-5"/>
                    </svg>
                    Trap Master (FM Tools)
                </h3>
                <div class="dashboard-tools-grid">
                    ${this.renderFMTools()}
                </div>
            </div>

            <div class="dashboard-section">
                <h3 class="dashboard-section-title">
                    <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                    </svg>
                    Metrics Master (PM Tools)
                </h3>
                <div class="dashboard-tools-grid">
                    ${this.renderPMTools()}
                </div>
            </div>

            <!-- Quick Actions -->
            <div class="dashboard-section">
                <h3 class="dashboard-section-title">
                    <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="8" x2="12" y2="16"/>
                        <line x1="8" y1="12" x2="16" y2="12"/>
                    </svg>
                    Quick Actions
                </h3>
                <div class="dashboard-quick-actions">
                    ${this.renderQuickActions()}
                </div>
            </div>
        `;
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.dashboardComponent = new DashboardComponent();
});
