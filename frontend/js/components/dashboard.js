/* ============================================
   Dashboard Component - Refactored with External Links Section
   ============================================ */

class DashboardComponent {
    constructor() {
        this.recentActivity = [];
        this.initialized = false;
        this.monitoringStatus = null;
        this.externalLinks = null;
    }

    async init() {
        if (this.initialized) return;
        
        // Load external links from config (optional)
        await this.loadExternalLinks();
        
        await this.render();
        this.initialized = true;
    }


    /**
     * ✅ NEW: Load external links from config (OPTIONAL)
     */
    async loadExternalLinks() {
        try {
            const response = await api.getAllSettings();
            
            if (response.success && response.settings && response.settings.external_links) {
                // Filter to only enabled links
                const enabledLinks = {};
                Object.entries(response.settings.external_links).forEach(([key, link]) => {
                    if (link && link.enabled) {
                        enabledLinks[key] = link;
                    }
                });
                
                // Only set if we have enabled links
                if (Object.keys(enabledLinks).length > 0) {
                    this.externalLinks = enabledLinks;
                    console.log('✅ Loaded external links:', Object.keys(this.externalLinks));
                } else {
                    this.externalLinks = null;
                    console.log('ℹ️ No enabled external links');
                }
            } else {
                this.externalLinks = null;
                console.log('ℹ️ No external links configured (standalone deployment)');
            }
        } catch (error) {
            console.warn('Failed to load external links:', error);
            this.externalLinks = null;
        }
    }

    // ============================================
    // SHARED RENDERING METHODS
    // ============================================

    /**
     * Render a tool card (handles all types)
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
     * Render a quick action button
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

    // ============================================
    // TOOL DEFINITIONS
    // ============================================

    /**
     * Get FM (Fault Management) tools configuration
     */
    getFMTools() {
        return [
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
    }

    /**
     * Get PM (Performance Management) tools configuration
     */
    getPMTools() {
        return [
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
    }

    /**
     * ✅ NEW: Get external links as tool cards
     */
    getExternalLinks() {
        if (!this.externalLinks) {
            return [];
        }

        return Object.entries(this.externalLinks).map(([key, link]) => ({
            name: link.label,
            icon: link.icon,
            description: link.description,
            external: true,
            url: link.url,
            color: link.color || 'primary'
        }));
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

    /**
     * ✅ NEW: Render external links section (only if configured)
     */
    renderExternalLinks() {
        const links = this.getExternalLinks();
        
        if (links.length === 0) {
            return ''; // Don't render section if no links
        }

        return `
            <div class="dashboard-section">
                <h3 class="dashboard-section-title">
                    <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/>
                        <polyline points="15 3 21 3 21 9"/>
                        <line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                    External Links
                </h3>
                <div class="dashboard-tools-grid">
                    ${links.map(link => this.renderToolCard(link)).join('')}
                </div>
            </div>
        `;
    }

    renderQuickActions() {
        return this.getQuickActions()
            .map(action => this.renderQuickActionButton(action))
            .join('');
    }

    /**
     * ✅ UPDATED: Main render method with External Links section
     */
    async render() {
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

            <!-- ✅ NEW: External Links Section (only if configured) -->
            ${this.renderExternalLinks()}

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

// Initialize dashboard component
window.dashboardComponent = new DashboardComponent();
