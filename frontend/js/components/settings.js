/**
 * Settings Component - Schema-Driven (Redesigned)
 * Reads SETTINGS_SCHEMA and renders UI with new grouping structure
 */

class SettingsComponent {
    constructor() {
        this.schema = window.SETTINGS_SCHEMA;  // From settings-schema.js
        this.settingsData = null;  // API response data
        this.activeSection = null;
        this.hasUnsavedChanges = false;
        this.pendingUpdates = [];
    }

    /**
     * Initialize component
     */
    async init() {
        try {
            this.renderLoadingState();
            await this.loadSettings();
            
            // Set default active section (first section key)
            if (!this.activeSection && this.schema) {
                const firstSectionKey = Object.keys(this.schema)[0];
                this.activeSection = firstSectionKey;
            }
            
            this.render();
        } catch (error) {
            console.error('❌ Settings initialization failed:', error);
            this.renderErrorState(error);
        }
    }

    /**
     * Render loading state
     */
    renderLoadingState() {
        const container = document.getElementById('settingsContent');
        if (!container) return;

        container.innerHTML = `
            <div class="settings-container">
                <div class="loading-state">
                    <div class="spinner"></div>
                    <p>Loading settings...</p>
                </div>
            </div>
        `;
    }

    /**
     * Render error state
     */
    renderErrorState(error) {
        const container = document.getElementById('settingsContent');
        if (!container) return;

        container.innerHTML = `
            <div class="settings-container">
                <div class="settings-notice settings-notice-danger">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="8" x2="12" y2="12"/>
                        <line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                    <span>Failed to load settings: ${error.message}</span>
                </div>
                <button class="btn btn-primary" onclick="window.settingsComponent.init()">
                    <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <polyline points="23 4 23 10 17 10"/>
                        <path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/>
                    </svg>
                    Retry
                </button>
            </div>
        `;
    }

    /**
     * Load settings from backend
     */
    async loadSettings() {
        try {
            window.showLoading('Loading settings...');
            
            const response = await api.getAllSettings();
            
            if (response && response.success && response.settings) {
                this.settingsData = response.settings;
            } else {
                throw new Error('Invalid response format');
            }
            
            window.hideLoading();
            
        } catch (error) {
            window.hideLoading();
            console.error('❌ Failed to load settings:', error);
            throw error;
        }
    }

    /**
     * Get value from settings data by path (supports nested paths)
     */
    getValueByPath(path) {
        const keys = path.split('.');
        let value = this.settingsData;
        
        for (const key of keys) {
            if (value && typeof value === 'object' && key in value) {
                value = value[key];
            } else {
                return null;
            }
        }
        
        return value;
    }

    /**
     * Render settings UI
     */
    render() {
        const container = document.getElementById('settingsContent');
        if (!container) return;

        if (!this.settingsData) {
            this.renderLoadingState();
            return;
        }

        container.innerHTML = `
            <div class="settings-container">
                <!-- Header -->
                <div class="settings-header">
                    <div class="settings-header-left">
                        <h2>Settings</h2>
                        <p class="settings-subtitle">Configure application settings</p>
                    </div>
                    <div class="settings-header-actions">
                        <button class="btn btn-secondary" id="reloadConfigBtn" title="Reload from file">
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0118.8-4.3M22 12.5a10 10 0 01-18.8 4.2"/>
                            </svg>
                            Reload Config
                        </button>
                        
                        <button class="btn btn-secondary" id="manageBackupsBtn" title="Manage backups">
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                                <polyline points="17 8 12 3 7 8"/>
                                <line x1="12" y1="3" x2="12" y2="15"/>
                            </svg>
                            Backups
                        </button>
                        
                        <button class="btn btn-primary" id="saveSettingsBtn" ${!this.hasUnsavedChanges ? 'disabled' : ''}>
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/>
                                <polyline points="17 21 17 13 7 13 7 21"/>
                                <polyline points="7 3 7 8 15 8"/>
                            </svg>
                            Save Changes
                        </button>
                    </div>
                </div>

                <!-- Settings Layout -->
                <div class="settings-layout">
                    <!-- Sidebar -->
                    <div class="settings-sidebar">
                        ${this.renderSidebar()}
                    </div>

                    <!-- Content -->
                    <div class="settings-content">
                        ${this.renderActiveSection()}
                    </div>
                </div>
            </div>
        `;
        
        this.setupEventListeners();
    }

    /**
     * Render sidebar tabs
     */
    renderSidebar() {
        if (!this.schema) return '';

        return Object.entries(this.schema).map(([sectionKey, section]) => `
            <button class="settings-tab ${this.activeSection === sectionKey ? 'active' : ''}" 
                    data-section="${sectionKey}">
                <span class="tab-icon">${section.icon}</span>
                <span class="tab-label">${section.label}</span>
            </button>
        `).join('');
    }

    /**
     * Render active section
     */
    renderActiveSection() {
        if (!this.schema || !this.activeSection) {
            return '<p>Section not found</p>';
        }

        const section = this.schema[this.activeSection];
        
        if (!section) {
            return '<p>Section not found</p>';
        }

        return `
            <div class="settings-section">
                <div class="section-header-inline">
                    <h3>${section.icon} ${section.label}</h3>
                </div>
                <p class="section-description">${section.description}</p>

                <div class="settings-form">
                    ${this.renderSubsections(section.sections)}
                </div>
            </div>
        `;
    }

    /**
     * Render subsections
     */
    renderSubsections(subsections) {
        if (!subsections) return '';

        return Object.entries(subsections).map(([subsectionKey, subsection]) => `
            <div class="settings-subsection">
                <div class="subsection-header">
                    <h4>${subsection.label}</h4>
                    <p class="subsection-description">${subsection.description}</p>
                </div>
                <div class="subsection-fields">
                    ${this.renderFields(subsection.fields)}
                </div>
            </div>
        `).join('');
    }

    /**
     * Render fields
     */
    renderFields(fields) {
        if (!fields || Object.keys(fields).length === 0) {
            return '<p class="form-help">No configurable settings in this section.</p>';
        }

        return Object.entries(fields).map(([fieldPath, field]) => {
            // Check conditional rendering
            if (field.showIf && !this.shouldShowField(field.showIf)) {
                return '';
            }
            
            return this.renderField(fieldPath, field);
        }).join('');
    }

    /**
     * Check if field should be shown based on condition
     */
    shouldShowField(condition) {
        const { field, value } = condition;
        const currentValue = this.getValueByPath(field);
        return currentValue === value;
    }

    /**
     * Render individual field
     */
    renderField(fieldPath, field) {
        const fieldId = `field_${fieldPath.replace(/\./g, '_')}`;
        const value = this.getValueByPath(fieldPath);
        const isReadonly = field.readonly || false;
        const isRequired = field.required || false;

        let inputHtml = '';
        
        switch (field.type) {
            case 'boolean':
                inputHtml = `
                    <label class="form-label">
                        <input type="checkbox" 
                               id="${fieldId}" 
                               data-path="${fieldPath}" 
                               ${value ? 'checked' : ''} 
                               ${isReadonly ? 'disabled' : ''}>
                        ${field.label}
                        ${isRequired ? '<span class="required">*</span>' : ''}
                    </label>
                `;
                break;
            
            case 'number':
                inputHtml = `
                    <label class="form-label">
                        ${field.label}
                        ${isRequired ? '<span class="required">*</span>' : ''}
                    </label>
                    <input type="number" 
                           id="${fieldId}" 
                           class="form-control" 
                           value="${value !== null && value !== undefined ? value : (field.default || '')}" 
                           data-path="${fieldPath}" 
                           ${field.validation?.min !== undefined ? `min="${field.validation.min}"` : ''}
                           ${field.validation?.max !== undefined ? `max="${field.validation.max}"` : ''}
                           step="any"
                           ${isReadonly ? 'readonly' : ''}>
                `;
                break;
            
            case 'text':
                inputHtml = `
                    <label class="form-label">
                        ${field.label}
                        ${isRequired ? '<span class="required">*</span>' : ''}
                    </label>
                    <input type="text" 
                           id="${fieldId}" 
                           class="form-control" 
                           value="${value !== null && value !== undefined ? value : (field.default || '')}" 
                           data-path="${fieldPath}"
                           placeholder="${field.placeholder || ''}"
                           ${isReadonly ? 'readonly' : ''}>
                `;
                break;
            
            case 'select':
                const options = field.options || [];
                const currentValue = value !== undefined ? value : field.default;
                inputHtml = `
                    <label class="form-label">
                        ${field.label}
                        ${isRequired ? '<span class="required">*</span>' : ''}
                    </label>
                    <select id="${fieldId}" 
                            class="form-control" 
                            data-path="${fieldPath}"
                            ${isReadonly ? 'disabled' : ''}>
                        ${options.map(opt => `
                            <option value="${opt}" ${currentValue === opt ? 'selected' : ''}>
                                ${opt}
                            </option>
                        `).join('')}
                    </select>
                `;
                break;
            
            case 'array':
                const arrayValue = Array.isArray(value) ? value : (field.default || []);
                const arrayStr = arrayValue.join(', ');
                inputHtml = `
                    <label class="form-label">
                        ${field.label}
                        ${isRequired ? '<span class="required">*</span>' : ''}
                    </label>
                    <input type="text" 
                           id="${fieldId}" 
                           class="form-control" 
                           value="${arrayStr}" 
                           data-path="${fieldPath}" 
                           data-array="true"
                           data-array-type="${field.arrayType || 'text'}"
                           placeholder="${field.placeholder || 'Comma-separated values'}"
                           ${isReadonly ? 'readonly' : ''}>
                `;
                break;
            
            default:
                inputHtml = `
                    <label class="form-label">
                        ${field.label}
                        ${isRequired ? '<span class="required">*</span>' : ''}
                    </label>
                    <input type="text" 
                           id="${fieldId}" 
                           class="form-control" 
                           value="${value || field.default || ''}" 
                           data-path="${fieldPath}"
                           ${isReadonly ? 'readonly' : ''}>
                `;
        }

        return `
            <div class="form-group ${isReadonly ? 'readonly' : ''}" data-field="${fieldPath}">
                ${inputHtml}
                ${field.description ? `<p class="form-help">${field.description}</p>` : ''}
                ${field.help ? `<p class="form-help-extra" title="${field.help}">ℹ️ ${field.help}</p>` : ''}
                ${field.warning ? `<div class="field-warning">⚠️ ${field.warning}</div>` : ''}
            </div>
        `;
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        const container = document.getElementById('settingsContent');
        if (!container) return;

        // Remove old listeners
        if (this._boundClickHandler) {
            container.removeEventListener('click', this._boundClickHandler);
        }
        if (this._boundChangeHandler) {
            container.removeEventListener('change', this._boundChangeHandler);
        }
        if (this._boundInputHandler) {
            container.removeEventListener('input', this._boundInputHandler);
        }

        // Attach new listeners
        this._boundClickHandler = this._handleClick.bind(this);
        this._boundChangeHandler = this._handleChange.bind(this);
        this._boundInputHandler = this._handleInput.bind(this);

        container.addEventListener('click', this._boundClickHandler);
        container.addEventListener('change', this._boundChangeHandler);
        container.addEventListener('input', this._boundInputHandler);
    }

    /**
     * Handle clicks
     */
    _handleClick(e) {
        const target = e.target.closest('button');
        if (!target) return;

        // Section switching
        if (target.classList.contains('settings-tab')) {
            const sectionKey = target.dataset.section;
            if (sectionKey) this.switchSection(sectionKey);
            return;
        }

        // Save button
        if (target.id === 'saveSettingsBtn') {
            this.saveSettings();
            return;
        }

        // Reload button
        if (target.id === 'reloadConfigBtn') {
            this.reloadConfig();
            return;
        }

        // Manage backups button
        if (target.id === 'manageBackupsBtn') {
            this.manageBackups();
            return;
        }
    }

    /**
     * Handle changes (for checkboxes and selects)
     */
    _handleChange(e) {
        const target = e.target;

        // Only handle fields with data-path
        if (!target.dataset.path) return;

        this._updateFieldValue(target);
    }

    /**
     * Handle input (for text and number fields)
     */
    _handleInput(e) {
        const target = e.target;

        // Only handle fields with data-path
        if (!target.dataset.path) return;

        // Debounce for text inputs
        if (target.type === 'text' || target.type === 'number') {
            clearTimeout(this._inputDebounce);
            this._inputDebounce = setTimeout(() => {
                this._updateFieldValue(target);
            }, 500);
        }
    }

    /**
     * Update field value
     */
    _updateFieldValue(target) {
        const path = target.dataset.path;
        let value;

        if (target.type === 'checkbox') {
            value = target.checked;
        } else if (target.type === 'number') {
            value = parseFloat(target.value);
        } else if (target.dataset.array === 'true') {
            // Parse comma-separated array
            const arrayType = target.dataset.arrayType || 'text';
            value = target.value.split(',').map(v => v.trim()).filter(v => v);
            
            // Convert to numbers if needed
            if (arrayType === 'number') {
                value = value.map(v => parseFloat(v)).filter(v => !isNaN(v));
            }
        } else {
            value = target.value;
        }

        // Track change
        const existingIndex = this.pendingUpdates.findIndex(u => u.path === path);
        if (existingIndex >= 0) {
            this.pendingUpdates[existingIndex].value = value;
        } else {
            this.pendingUpdates.push({ path, value });
        }

        console.log(`📝 Changed ${path} =`, value);

        this.hasUnsavedChanges = true;
        this._enableSaveButton();

        // Check if this field affects conditional fields
        if (this._hasConditionalDependents(path)) {
            this.render(); // Re-render to show/hide dependent fields
        }
    }

    /**
     * Check if field has conditional dependents
     */
    _hasConditionalDependents(fieldPath) {
        if (!this.schema) return false;

        for (const section of Object.values(this.schema)) {
            for (const subsection of Object.values(section.sections)) {
                for (const field of Object.values(subsection.fields)) {
                    if (field.showIf && field.showIf.field === fieldPath) {
                        return true;
                    }
                }
            }
        }
        return false;
    }

    /**
     * Enable save button
     */
    _enableSaveButton() {
        const saveBtn = document.getElementById('saveSettingsBtn');
        if (saveBtn) saveBtn.disabled = false;
    }

    /**
     * Switch section
     */
    switchSection(sectionKey) {
        this.activeSection = sectionKey;

        // Update active tab button
        document.querySelectorAll('.settings-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.section === sectionKey);
        });

        // Update content
        const content = document.querySelector('.settings-content');
        if (content) {
            content.innerHTML = this.renderActiveSection();
        }
    }

    /**
     * Save settings
     */
    async saveSettings() {
        if (this.pendingUpdates.length === 0) {
            notify.info('No changes to save');
            return;
        }

        try {
            window.showLoading('Saving settings...');

            console.log(`💾 Saving ${this.pendingUpdates.length} updates...`, this.pendingUpdates);
            
            const response = await api.updateSettings(this.pendingUpdates);

            window.hideLoading();

            if (response && response.success) {
                notify.success(response.restart_message || '✅ Settings saved successfully!');
                this.pendingUpdates = [];
                this.hasUnsavedChanges = false;
                
                const saveBtn = document.getElementById('saveSettingsBtn');
                if (saveBtn) saveBtn.disabled = true;

                // Reload settings to show updated values
                await this.loadSettings();
                this.render();
            }

        } catch (error) {
            window.hideLoading();
            console.error('Failed to save settings:', error);
            notify.error(`Failed to save settings: ${error.message}`);
        }
    }

    /**
     * Reload config
     */
    async reloadConfig() {
        const confirmed = await modal.confirm({
            title: 'Reload Configuration',
            message: 'Reload configuration from config.yaml file? Any manual edits will be applied.',
            confirmText: 'Reload',
            cancelText: 'Cancel'
        });

        if (!confirmed) return;

        try {
            window.showLoading('Reloading configuration...');

            const response = await fetch(`${api.baseURL}/settings/reload`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Accept: 'application/json'
                },
            });

            const result = await response.json();

            window.hideLoading();

            if (result.success) {
                notify.success('✅ Configuration reloaded!');
                await this.loadSettings();
                this.render();
            }

        } catch (error) {
            window.hideLoading();
            notify.error(`Failed to reload: ${error.message}`);
        }
    }

    /**
     * Manage backups
     */
    async manageBackups() {
        try {
            window.showLoading('Loading backups...');

            const response = await api.listBackups();

            window.hideLoading();

            if (response && response.success) {
                const backupsHtml = response.backups.length > 0
                    ? response.backups.map(backup => `
                        <div class="backup-item">
                            <div class="backup-info">
                                <strong>${backup.filename}</strong>
                                <p style="font-size: 0.875rem; color: var(--color-text-secondary); margin: 0;">
                                    ${new Date(backup.modified).toLocaleString()} • ${(backup.size / 1024).toFixed(2)} KB
                                </p>
                            </div>
                            <button class="btn btn-sm btn-primary" onclick="window.settingsComponent.restoreBackup('${backup.filename}')">
                                Restore
                            </button>
                        </div>
                    `).join('')
                    : '<p style="color: var(--color-text-secondary); text-align: center; padding: var(--spacing-lg);">No backups available</p>';

                modal.show({
                    title: 'Configuration Backups',
                    content: `
                        <div style="display: flex; flex-direction: column; gap: var(--spacing-sm); max-height: 500px; overflow-y: auto;">
                            ${backupsHtml}
                        </div>
                    `,
                    size: 'medium',
                    buttons: [
                        {
                            text: 'Close',
                            class: 'btn-secondary',
                            onClick: () => modal.close()
                        }
                    ]
                });
            }

        } catch (error) {
            window.hideLoading();
            notify.error(`Failed to load backups: ${error.message}`);
        }
    }

    /**
     * Restore backup
     */
    async restoreBackup(backupName) {
        modal.close();

        const confirmed = await modal.confirm({
            title: 'Restore Backup',
            message: `Restore configuration from ${backupName}? Current config will be overwritten.`,
            confirmText: 'Restore',
            cancelText: 'Cancel',
            danger: true
        });

        if (!confirmed) return;

        try {
            window.showLoading('Restoring backup...');

            const response = await api.restoreBackup(backupName);

            window.hideLoading();

            if (response && response.success) {
                notify.success('✅ Backup restored successfully!');
                await this.loadSettings();
                this.render();
            }

        } catch (error) {
            window.hideLoading();
            notify.error(`Failed to restore backup: ${error.message}`);
        }
    }
}

// Create global instance
window.settingsComponent = new SettingsComponent();
