/* ============================================
   SNMP Walk Component
   ============================================ */

class SnmpWalkComponent {
    constructor() {
        // Active tab
        this.activeTab = localStorage.getItem('snmpWalkLastTab') || 'execute';
        
        // State
        this.devices = [];
        this.configs = [];
        this.results = [];
        this.stats = null;
        
        // Execute tab state
        this.selectedDevice = null;
        this.selectedConfig = null;
        this.configMode = 'predefined'; // 'predefined' or 'custom'
        this.customOid = '';
        this.customWalkType = 'custom';
        this.resolveOids = true;
        this.lastExecutionResult = null;
        
        // Results tab state
        this.resultsFilters = {
            device_id: null,
            config_id: null,
            oid_filter: '',
            resolved_only: false
        };
        this.resultsPage = 1;
        this.resultsLimit = 100;
        this.resultsTotal = 0;
        
        // Search/filter state
        this.deviceSearchQuery = '';
        this.configSearchQuery = '';
        this.deviceFilterEnabled = 'all'; // 'all', 'enabled', 'disabled'
        this.configFilterEnabled = 'all';
        
        this.init();
    }

    init() {
        this.render();
        this.loadInitialData();
    }

    async loadInitialData() {
        // Load based on active tab
        if (this.activeTab === 'devices') {
            await this.loadDevices();
        } else if (this.activeTab === 'configs') {
            await this.loadConfigs();
        } else if (this.activeTab === 'execute') {
            await this.loadDevices();
            await this.loadConfigs();
        } else if (this.activeTab === 'results') {
            await this.loadResults();
        } else if (this.activeTab === 'stats') {
            await this.loadStats();
        }
    }

    /**
     * Switch tab
     */
    switchTab(tab) {
        if (!tab) {
            tab = this.activeTab;
        }

        this.activeTab = tab;

        // Save to localStorage
        localStorage.setItem('snmpWalkLastTab', tab);
        
        // Update tab button active states
        document.querySelectorAll('.snmp-walk-tab').forEach(tabBtn => {
            tabBtn.classList.toggle('active', tabBtn.dataset.tab === tab);
        });
        
        this.renderTabContent();
        this.loadInitialData();
    }

    /**
     * Main render
     */
    render() {
        const container = document.getElementById('snmpWalkContent');
        if (!container) return;

        container.innerHTML = `
            <!-- Tab Navigation -->
            <div class="snmp-walk-tabs">
                <button class="snmp-walk-tab ${this.activeTab === 'devices' ? 'active' : ''}" data-tab="devices">
                    <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" style="width: 16px; height: 16px;">
                        <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
                        <line x1="8" y1="21" x2="16" y2="21"/>
                        <line x1="12" y1="17" x2="12" y2="21"/>
                    </svg>
                    Devices
                </button>
                <button class="snmp-walk-tab ${this.activeTab === 'configs' ? 'active' : ''}" data-tab="configs">
                    <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" style="width: 16px; height: 16px;">
                        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    Configs
                </button>
                <button class="snmp-walk-tab ${this.activeTab === 'execute' ? 'active' : ''}" data-tab="execute">
                    <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" style="width: 16px; height: 16px;">
                        <polygon points="5 3 19 12 5 21 5 3"/>
                    </svg>
                    Execute
                </button>
                <button class="snmp-walk-tab ${this.activeTab === 'results' ? 'active' : ''}" data-tab="results">
                    <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" style="width: 16px; height: 16px;">
                        <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                    </svg>
                    Results
                </button>
                <button class="snmp-walk-tab ${this.activeTab === 'stats' ? 'active' : ''}" data-tab="stats">
                    <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" style="width: 16px; height: 16px;">
                        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                    </svg>
                    Statistics
                </button>
            </div>

            <!-- Tab Content -->
            <div id="snmpWalkTabContent"></div>
        `;

        this.setupTabListeners();
        this.renderTabContent();
    }

    setupTabListeners() {
        document.querySelectorAll('.snmp-walk-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                const tabName = e.currentTarget.dataset.tab;
                this.switchTab(tabName);
                
                // Update tab active state
                document.querySelectorAll('.snmp-walk-tab').forEach(t => t.classList.remove('active'));
                e.currentTarget.classList.add('active');
            });
        });
    }

    renderTabContent() {
        const container = document.getElementById('snmpWalkTabContent');
        if (!container) return;

        switch (this.activeTab) {
            case 'devices':
                this.renderDevicesTab();
                break;
            case 'configs':
                this.renderConfigsTab();
                break;
            case 'execute':
                this.renderExecuteTab();
                break;
            case 'results':
                this.renderResultsTab();
                break;
            case 'stats':
                this.renderStatsTab();
                break;
        }
    }

    // ============================================
    // DEVICES TAB
    // ============================================

    renderDevicesTab() {
        const container = document.getElementById('snmpWalkTabContent');
        if (!container) return;

        container.innerHTML = `
            <div class="snmp-walk-section">
                <div class="snmp-walk-section-header">
                    <h3 class="snmp-walk-section-title">SNMP Devices (${this.devices.length})</h3>
                    <div style="display: flex; gap: var(--spacing-sm);">
                        <button class="btn btn-sm btn-primary" id="addDeviceBtn">
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <line x1="12" y1="5" x2="12" y2="19"/>
                                <line x1="5" y1="12" x2="19" y2="12"/>
                            </svg>
                            Add Device
                        </button>
                        <button class="btn btn-sm btn-secondary" id="refreshDevicesBtn">
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <polyline points="23 4 23 10 17 10"/>
                                <path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/>
                            </svg>
                            Refresh
                        </button>
                    </div>
                </div>

                <!-- Search and Filters -->
                <div style="display: flex; gap: var(--spacing-sm); margin-bottom: var(--spacing-md);">
                    <div class="snmp-walk-search-box" style="flex: 1;">
                        <svg class="snmp-walk-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <circle cx="11" cy="11" r="8"/>
                            <path d="m21 21-4.35-4.35"/>
                        </svg>
                        <input 
                            type="text" 
                            class="snmp-walk-search-input" 
                            id="deviceSearchInput"
                            placeholder="Search devices..."
                            value="${this.deviceSearchQuery}"
                        />
                    </div>
                    <select class="form-select" id="deviceFilterEnabled" style="width: 150px;">
                        <option value="all" ${this.deviceFilterEnabled === 'all' ? 'selected' : ''}>All Devices</option>
                        <option value="enabled" ${this.deviceFilterEnabled === 'enabled' ? 'selected' : ''}>Enabled Only</option>
                        <option value="disabled" ${this.deviceFilterEnabled === 'disabled' ? 'selected' : ''}>Disabled Only</option>
                    </select>
                </div>

                <!-- Devices Table -->
                <div id="devicesTableContainer"></div>
            </div>
        `;

        this.renderDevicesTable();
        this.setupDevicesEventListeners();
    }

    renderDevicesTable() {
        const container = document.getElementById('devicesTableContainer');
        if (!container) return;

        // Filter devices
        let filteredDevices = this.devices;

        if (this.deviceSearchQuery) {
            const query = this.deviceSearchQuery.toLowerCase();
            filteredDevices = filteredDevices.filter(d => 
                d.name.toLowerCase().includes(query) ||
                d.ip_address.includes(query) ||
                (d.device_type || '').toLowerCase().includes(query)
            );
        }

        if (this.deviceFilterEnabled === 'enabled') {
            filteredDevices = filteredDevices.filter(d => d.enabled);
        } else if (this.deviceFilterEnabled === 'disabled') {
            filteredDevices = filteredDevices.filter(d => !d.enabled);
        }

        if (filteredDevices.length === 0) {
            container.innerHTML = `
                <div class="snmp-walk-empty">
                    <svg class="snmp-walk-empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
                        <line x1="8" y1="21" x2="16" y2="21"/>
                        <line x1="12" y1="17" x2="12" y2="21"/>
                    </svg>
                    <div class="snmp-walk-empty-title">No devices found</div>
                    <div class="snmp-walk-empty-text">Add your first SNMP device to get started</div>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div class="snmp-walk-table-container">
                <table class="snmp-walk-table">
                    <thead>
                        <tr>
                            <th style="width: 50px; text-align: center;">Status</th>
                            <th>Name</th>
                            <th>IP Address</th>
                            <th>Port</th>
                            <th>Type</th>
                            <th>Location</th>
                            <th style="width: 200px; text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${filteredDevices.map(device => `
                            <tr>
                                <td style="text-align: center;">
                                    <span class="snmp-walk-status ${device.enabled ? 'enabled' : 'disabled'}">
                                        ${device.enabled ? '✅' : '❌'}
                                    </span>
                                </td>
                                <td><strong>${this.escapeHtml(device.name)}</strong></td>
                                <td><code>${this.escapeHtml(device.ip_address)}</code></td>
                                <td>${device.snmp_port || 161}</td>
                                <td>${this.escapeHtml(device.device_type || 'N/A')}</td>
                                <td>${this.escapeHtml(device.location || 'N/A')}</td>
                                <td style="text-align: right;">
                                    <div style="display: flex; gap: var(--spacing-xs); justify-content: flex-end;">
                                        <button class="btn btn-sm btn-secondary" onclick="snmpWalkComponent.editDevice(${device.id})" title="Edit">
                                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                                <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                                                <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                                            </svg>
                                            Edit
                                        </button>
                                        <button class="btn btn-sm ${device.enabled ? 'btn-warning' : 'btn-success'}" onclick="snmpWalkComponent.toggleDevice(${device.id})" title="${device.enabled ? 'Disable' : 'Enable'}">
                                            ${device.enabled ? 'Disable' : 'Enable'}
                                        </button>
                                        <button class="btn btn-sm btn-danger" onclick="snmpWalkComponent.deleteDevice(${device.id})" title="Delete">
                                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                                <polyline points="3 6 5 6 21 6"/>
                                                <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                                            </svg>
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    setupDevicesEventListeners() {
        const addBtn = document.getElementById('addDeviceBtn');
        const refreshBtn = document.getElementById('refreshDevicesBtn');
        const searchInput = document.getElementById('deviceSearchInput');
        const filterSelect = document.getElementById('deviceFilterEnabled');

        if (addBtn) {
            addBtn.addEventListener('click', () => this.showAddDeviceModal());
        }

        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadDevices());
        }

        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.deviceSearchQuery = e.target.value;
                this.renderDevicesTable();
            });
        }

        if (filterSelect) {
            filterSelect.addEventListener('change', (e) => {
                this.deviceFilterEnabled = e.target.value;
                this.renderDevicesTable();
            });
        }
    }

    async loadDevices() {
        try {
            const response = await api.get('/snmp-walk/devices', {
                enabled_only: false,
                limit: 1000,
                offset: 0
            });

            if (response && Array.isArray(response)) {
                this.devices = response;
            } else {
                this.devices = [];
            }

            if (this.activeTab === 'devices') {
                this.renderDevicesTable();
            }
        } catch (error) {
            console.error('Failed to load devices:', error);
            notify.error(`Failed to load devices: ${error.message}`);
        }
    }

    showAddDeviceModal() {
        this.showDeviceModal(null);
    }

    editDevice(deviceId) {
        const device = this.devices.find(d => d.id === deviceId);
        if (!device) {
            notify.error('Device not found');
            return;
        }
        this.showDeviceModal(device);
    }

    showDeviceModal(device = null) {
        const isEdit = device !== null;
        const title = isEdit ? 'Edit Device' : 'Add Device';

        const content = `
            <div style="display: flex; flex-direction: column; gap: var(--spacing-md);">
                <div class="form-group">
                    <label for="deviceName">Name *</label>
                    <input type="text" id="deviceName" class="form-input" placeholder="e.g., core-router-mumbai" value="${device ? this.escapeHtml(device.name) : ''}" required />
                </div>

                <div class="form-group">
                    <label for="deviceIp">IP Address *</label>
                    <input type="text" id="deviceIp" class="form-input" placeholder="192.168.1.1" value="${device ? this.escapeHtml(device.ip_address) : ''}" required />
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--spacing-md);">
                    <div class="form-group">
                        <label for="devicePort">SNMP Port</label>
                        <input type="number" id="devicePort" class="form-input" placeholder="161" value="${device ? device.snmp_port : 161}" />
                    </div>

                    <div class="form-group">
                        <label for="deviceCommunity">Community</label>
                        <input type="text" id="deviceCommunity" class="form-input" placeholder="public" value="${device ? this.escapeHtml(device.snmp_community) : 'public'}" />
                    </div>
                </div>

                <div class="form-group">
                    <label for="deviceType">Device Type (optional)</label>
                    <input type="text" id="deviceType" class="form-input" placeholder="Router, Switch, Firewall..." value="${device ? this.escapeHtml(device.device_type || '') : ''}" />
                </div>

                <div class="form-group">
                    <label for="deviceVendor">Vendor (optional)</label>
                    <input type="text" id="deviceVendor" class="form-input" placeholder="Cisco, Juniper..." value="${device ? this.escapeHtml(device.vendor || '') : ''}" />
                </div>

                <div class="form-group">
                    <label for="deviceLocation">Location (optional)</label>
                    <input type="text" id="deviceLocation" class="form-input" placeholder="Mumbai Data Center" value="${device ? this.escapeHtml(device.location || '') : ''}" />
                </div>

                <div class="form-group">
                    <label for="deviceContact">Contact (optional)</label>
                    <input type="text" id="deviceContact" class="form-input" placeholder="admin@example.com" value="${device ? this.escapeHtml(device.contact || '') : ''}" />
                </div>

                <div class="form-group">
                    <label for="deviceDescription">Description (optional)</label>
                    <textarea id="deviceDescription" class="form-textarea" rows="3" placeholder="Additional notes...">${device ? this.escapeHtml(device.description || '') : ''}</textarea>
                </div>

                <div class="form-group">
                    <label class="checkbox-label">
                        <input type="checkbox" id="deviceEnabled" ${device ? (device.enabled ? 'checked' : '') : 'checked'} />
                        <span>Enabled</span>
                    </label>
                </div>
            </div>
        `;

        modal.show({
            title: title,
            content: content,
            size: 'medium',
            buttons: [
                {
                    text: 'Cancel',
                    class: 'btn-secondary',
                    onClick: () => modal.close()
                },
                {
                    text: isEdit ? 'Update' : 'Create',
                    class: 'btn-primary',
                    onClick: async () => {
                        const name = document.getElementById('deviceName').value.trim();
                        const ip = document.getElementById('deviceIp').value.trim();
                        const port = parseInt(document.getElementById('devicePort').value) || 161;
                        const community = document.getElementById('deviceCommunity').value.trim() || 'public';
                        const deviceType = document.getElementById('deviceType').value.trim();
                        const vendor = document.getElementById('deviceVendor').value.trim();
                        const location = document.getElementById('deviceLocation').value.trim();
                        const contact = document.getElementById('deviceContact').value.trim();
                        const description = document.getElementById('deviceDescription').value.trim();
                        const enabled = document.getElementById('deviceEnabled').checked;

                        if (!name || !ip) {
                            notify.error('Name and IP Address are required');
                            return;
                        }

                        modal.close();

                        if (isEdit) {
                            await this.updateDevice(device.id, {
                                name, ip_address: ip, snmp_port: port, snmp_community: community,
                                device_type: deviceType, vendor, location, contact, description, enabled
                            });
                        } else {
                            await this.createDevice({
                                name, ip_address: ip, snmp_port: port, snmp_community: community,
                                device_type: deviceType, vendor, location, contact, description, enabled
                            });
                        }
                    }
                }
            ]
        });

        // Focus first input
        setTimeout(() => {
            const input = document.getElementById('deviceName');
            if (input) input.focus();
        }, 100);
    }

    async createDevice(data) {
        try {
            window.showLoading('Creating device...');
            const response = await api.post('/snmp-walk/devices', data);
            window.hideLoading();

            if (response && response.success) {
                notify.success(`Device '${data.name}' created successfully`);
                await this.loadDevices();
            } else {
                throw new Error(response.message || 'Failed to create device');
            }
        } catch (error) {
            window.hideLoading();
            console.error('Create device failed:', error);
            notify.error(`Failed to create device: ${error.message}`);
        }
    }

    async updateDevice(deviceId, data) {
        try {
            window.showLoading('Updating device...');
            const response = await api.put(`/snmp-walk/devices/${deviceId}`, data);
            window.hideLoading();

            if (response && response.success) {
                notify.success('Device updated successfully');
                await this.loadDevices();
            } else {
                throw new Error(response.message || 'Failed to update device');
            }
        } catch (error) {
            window.hideLoading();
            console.error('Update device failed:', error);
            notify.error(`Failed to update device: ${error.message}`);
        }
    }

    async toggleDevice(deviceId) {
        const device = this.devices.find(d => d.id === deviceId);
        if (!device) return;

        await this.updateDevice(deviceId, { enabled: !device.enabled });
    }

    async deleteDevice(deviceId) {
        const device = this.devices.find(d => d.id === deviceId);
        if (!device) return;

        const confirmed = await modal.confirm({
            title: 'Delete Device',
            message: `Are you sure you want to delete device '${device.name}'? This will also delete all walk results for this device.`,
            confirmText: 'Delete',
            cancelText: 'Cancel',
            danger: true
        });

        if (!confirmed) return;

        try {
            window.showLoading('Deleting device...');
            const response = await api.delete(`/snmp-walk/devices/${deviceId}`);
            window.hideLoading();

            if (response && response.success) {
                notify.success('Device deleted successfully');
                await this.loadDevices();
            } else {
                throw new Error(response.message || 'Failed to delete device');
            }
        } catch (error) {
            window.hideLoading();
            console.error('Delete device failed:', error);
            notify.error(`Failed to delete device: ${error.message}`);
        }
    }

    // ============================================
    // CONFIGS TAB
    // ============================================

    renderConfigsTab() {
        const container = document.getElementById('snmpWalkTabContent');
        if (!container) return;

        container.innerHTML = `
            <div class="snmp-walk-section">
                <div class="snmp-walk-section-header">
                    <h3 class="snmp-walk-section-title">Walk Configurations (${this.configs.length})</h3>
                    <div style="display: flex; gap: var(--spacing-sm);">
                        <button class="btn btn-sm btn-primary" id="addConfigBtn">
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <line x1="12" y1="5" x2="12" y2="19"/>
                                <line x1="5" y1="12" x2="19" y2="12"/>
                            </svg>
                            Add Config
                        </button>
                        <button class="btn btn-sm btn-secondary" id="refreshConfigsBtn">
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <polyline points="23 4 23 10 17 10"/>
                                <path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/>
                            </svg>
                            Refresh
                        </button>
                    </div>
                </div>

                <!-- Search and Filters -->
                <div style="display: flex; gap: var(--spacing-sm); margin-bottom: var(--spacing-md);">
                    <div class="snmp-walk-search-box" style="flex: 1;">
                        <svg class="snmp-walk-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <circle cx="11" cy="11" r="8"/>
                            <path d="m21 21-4.35-4.35"/>
                        </svg>
                        <input 
                            type="text" 
                            class="snmp-walk-search-input" 
                            id="configSearchInput"
                            placeholder="Search configs..."
                            value="${this.configSearchQuery}"
                        />
                    </div>
                    <select class="form-select" id="configFilterEnabled" style="width: 150px;">
                        <option value="all" ${this.configFilterEnabled === 'all' ? 'selected' : ''}>All Configs</option>
                        <option value="enabled" ${this.configFilterEnabled === 'enabled' ? 'selected' : ''}>Enabled Only</option>
                        <option value="disabled" ${this.configFilterEnabled === 'disabled' ? 'selected' : ''}>Disabled Only</option>
                    </select>
                </div>

                <!-- Configs Table -->
                <div id="configsTableContainer"></div>
            </div>
        `;

        this.renderConfigsTable();
        this.setupConfigsEventListeners();
    }

    renderConfigsTable() {
        const container = document.getElementById('configsTableContainer');
        if (!container) return;

        // Filter configs
        let filteredConfigs = this.configs;

        if (this.configSearchQuery) {
            const query = this.configSearchQuery.toLowerCase();
            filteredConfigs = filteredConfigs.filter(c => 
                c.name.toLowerCase().includes(query) ||
                c.base_oid.includes(query) ||
                (c.walk_type || '').toLowerCase().includes(query)
            );
        }

        if (this.configFilterEnabled === 'enabled') {
            filteredConfigs = filteredConfigs.filter(c => c.enabled);
        } else if (this.configFilterEnabled === 'disabled') {
            filteredConfigs = filteredConfigs.filter(c => !c.enabled);
        }

        if (filteredConfigs.length === 0) {
            container.innerHTML = `
                <div class="snmp-walk-empty">
                    <svg class="snmp-walk-empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <div class="snmp-walk-empty-title">No configurations found</div>
                    <div class="snmp-walk-empty-text">Create your first walk configuration</div>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div class="snmp-walk-table-container">
                <table class="snmp-walk-table">
                    <thead>
                        <tr>
                            <th style="width: 50px; text-align: center;">Status</th>
                            <th>Name</th>
                            <th>Base OID</th>
                            <th>Walk Type</th>
                            <th>Description</th>
                            <th style="width: 200px; text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${filteredConfigs.map(config => `
                            <tr>
                                <td style="text-align: center;">
                                    <span class="snmp-walk-status ${config.enabled ? 'enabled' : 'disabled'}">
                                        ${config.enabled ? '✅' : '❌'}
                                    </span>
                                </td>
                                <td><strong>${this.escapeHtml(config.name)}</strong></td>
                                <td><code>${this.escapeHtml(config.base_oid)}</code></td>
                                <td><span class="badge-compact">${this.escapeHtml(config.walk_type || 'custom')}</span></td>
                                <td>${this.escapeHtml(config.description || 'No description')}</td>
                                <td style="text-align: right;">
                                    <div style="display: flex; gap: var(--spacing-xs); justify-content: flex-end;">
                                        <button class="btn btn-sm btn-secondary" onclick="snmpWalkComponent.editConfig(${config.id})" title="Edit">
                                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                                <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                                                <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                                            </svg>
                                            Edit
                                        </button>
                                        <button class="btn btn-sm ${config.enabled ? 'btn-warning' : 'btn-success'}" onclick="snmpWalkComponent.toggleConfig(${config.id})" title="${config.enabled ? 'Disable' : 'Enable'}">
                                            ${config.enabled ? 'Disable' : 'Enable'}
                                        </button>
                                        <button class="btn btn-sm btn-danger" onclick="snmpWalkComponent.deleteConfig(${config.id})" title="Delete">
                                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                                <polyline points="3 6 5 6 21 6"/>
                                                <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                                            </svg>
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    setupConfigsEventListeners() {
        const addBtn = document.getElementById('addConfigBtn');
        const refreshBtn = document.getElementById('refreshConfigsBtn');
        const searchInput = document.getElementById('configSearchInput');
        const filterSelect = document.getElementById('configFilterEnabled');

        if (addBtn) {
            addBtn.addEventListener('click', () => this.showAddConfigModal());
        }

        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadConfigs());
        }

        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.configSearchQuery = e.target.value;
                this.renderConfigsTable();
            });
        }

        if (filterSelect) {
            filterSelect.addEventListener('change', (e) => {
                this.configFilterEnabled = e.target.value;
                this.renderConfigsTable();
            });
        }
    }

    async loadConfigs() {
        try {
            const response = await api.get('/snmp-walk/configs', {
                enabled_only: false,
                limit: 1000,
                offset: 0
            });

            if (response && Array.isArray(response)) {
                this.configs = response;
            } else {
                this.configs = [];
            }

            if (this.activeTab === 'configs') {
                this.renderConfigsTable();
            }
        } catch (error) {
            console.error('Failed to load configs:', error);
            notify.error(`Failed to load configs: ${error.message}`);
        }
    }

    showAddConfigModal() {
        this.showConfigModal(null);
    }

    editConfig(configId) {
        const config = this.configs.find(c => c.id === configId);
        if (!config) {
            notify.error('Config not found');
            return;
        }
        this.showConfigModal(config);
    }

    showConfigModal(config = null) {
        const isEdit = config !== null;
        const title = isEdit ? 'Edit Walk Configuration' : 'Add Walk Configuration';

        const content = `
            <div style="display: flex; flex-direction: column; gap: var(--spacing-md);">
                <div class="form-group">
                    <label for="configName">Name *</label>
                    <input type="text" id="configName" class="form-input" placeholder="e.g., BGP Peer Monitoring" value="${config ? this.escapeHtml(config.name) : ''}" required />
                </div>

                <div class="form-group">
                    <label for="configBaseOid">Base OID *</label>
                    <input type="text" id="configBaseOid" class="form-input" placeholder="1.3.6.1.2.1.15.3" value="${config ? this.escapeHtml(config.base_oid) : ''}" required />
                </div>

                <div class="form-group">
                    <label for="configWalkType">Walk Type</label>
                    <select id="configWalkType" class="form-select">
                        <option value="system" ${config && config.walk_type === 'system' ? 'selected' : ''}>System</option>
                        <option value="bgp_peers" ${config && config.walk_type === 'bgp_peers' ? 'selected' : ''}>BGP Peers</option>
                        <option value="interfaces" ${config && config.walk_type === 'interfaces' ? 'selected' : ''}>Interfaces</option>
                        <option value="routing" ${config && config.walk_type === 'routing' ? 'selected' : ''}>Routing</option>
                        <option value="memory" ${config && config.walk_type === 'memory' ? 'selected' : ''}>Memory</option>
                        <option value="custom" ${!config || config.walk_type === 'custom' ? 'selected' : ''}>Custom</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="configDescription">Description (optional)</label>
                    <textarea id="configDescription" class="form-textarea" rows="3" placeholder="Monitor BGP peer states and AS numbers...">${config ? this.escapeHtml(config.description || '') : ''}</textarea>
                </div>

                <div class="form-group">
                    <label class="checkbox-label">
                        <input type="checkbox" id="configEnabled" ${config ? (config.enabled ? 'checked' : '') : 'checked'} />
                        <span>Enabled</span>
                    </label>
                </div>
            </div>
        `;

        modal.show({
            title: title,
            content: content,
            size: 'medium',
            buttons: [
                {
                    text: 'Cancel',
                    class: 'btn-secondary',
                    onClick: () => modal.close()
                },
                {
                    text: isEdit ? 'Update' : 'Create',
                    class: 'btn-primary',
                    onClick: async () => {
                        const name = document.getElementById('configName').value.trim();
                        const baseOid = document.getElementById('configBaseOid').value.trim();
                        const walkType = document.getElementById('configWalkType').value;
                        const description = document.getElementById('configDescription').value.trim();
                        const enabled = document.getElementById('configEnabled').checked;

                        if (!name || !baseOid) {
                            notify.error('Name and Base OID are required');
                            return;
                        }

                        modal.close();

                        if (isEdit) {
                            await this.updateConfig(config.id, { name, base_oid: baseOid, walk_type: walkType, description, enabled });
                        } else {
                            await this.createConfig({ name, base_oid: baseOid, walk_type: walkType, description, enabled });
                        }
                    }
                }
            ]
        });

        // Focus first input
        setTimeout(() => {
            const input = document.getElementById('configName');
            if (input) input.focus();
        }, 100);
    }

    async createConfig(data) {
        try {
            window.showLoading('Creating config...');
            const response = await api.post('/snmp-walk/configs', data);
            window.hideLoading();

            if (response && response.success) {
                notify.success(`Config '${data.name}' created successfully`);
                await this.loadConfigs();
            } else {
                throw new Error(response.message || 'Failed to create config');
            }
        } catch (error) {
            window.hideLoading();
            console.error('Create config failed:', error);
            notify.error(`Failed to create config: ${error.message}`);
        }
    }

    async updateConfig(configId, data) {
        try {
            window.showLoading('Updating config...');
            const response = await api.put(`/snmp-walk/configs/${configId}`, data);
            window.hideLoading();

            if (response && response.success) {
                notify.success('Config updated successfully');
                await this.loadConfigs();
            } else {
                throw new Error(response.message || 'Failed to update config');
            }
        } catch (error) {
            window.hideLoading();
            console.error('Update config failed:', error);
            notify.error(`Failed to update config: ${error.message}`);
        }
    }

    async toggleConfig(configId) {
        const config = this.configs.find(c => c.id === configId);
        if (!config) return;

        await this.updateConfig(configId, { enabled: !config.enabled });
    }

    async deleteConfig(configId) {
        const config = this.configs.find(c => c.id === configId);
        if (!config) return;

        const confirmed = await modal.confirm({
            title: 'Delete Configuration',
            message: `Are you sure you want to delete config '${config.name}'?`,
            confirmText: 'Delete',
            cancelText: 'Cancel',
            danger: true
        });

        if (!confirmed) return;

        try {
            window.showLoading('Deleting config...');
            const response = await api.delete(`/snmp-walk/configs/${configId}`);
            window.hideLoading();

            if (response && response.success) {
                notify.success('Config deleted successfully');
                await this.loadConfigs();
            } else {
                throw new Error(response.message || 'Failed to delete config');
            }
        } catch (error) {
            window.hideLoading();
            console.error('Delete config failed:', error);
            notify.error(`Failed to delete config: ${error.message}`);
        }
    }

    // ============================================
    // EXECUTE TAB
    // ============================================

    renderExecuteTab() {
        const container = document.getElementById('snmpWalkTabContent');
        if (!container) return;

        const enabledDevices = this.devices.filter(d => d.enabled);
        const enabledConfigs = this.configs.filter(c => c.enabled);

        container.innerHTML = `
            <!-- Step 1: Select Device -->
            <div class="snmp-walk-execute-step">
                <div class="snmp-walk-step-header">
                    <div class="snmp-walk-step-number">1</div>
                    <h3 class="snmp-walk-step-title">Select Device</h3>
                </div>

                <div class="snmp-walk-selection">
                    <select class="form-select" id="executeDeviceSelect">
                        <option value="">Choose device...</option>
                        ${enabledDevices.map(d => `
                            <option value="${d.id}" ${this.selectedDevice && this.selectedDevice.id === d.id ? 'selected' : ''}>
                                ${this.escapeHtml(d.name)} (${this.escapeHtml(d.ip_address)})
                            </option>
                        `).join('')}
                    </select>

                    ${this.selectedDevice ? `
                        <div class="snmp-walk-selection-info">
                            <svg style="width: 16px; height: 16px;" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <circle cx="12" cy="12" r="10"/>
                                <line x1="12" y1="16" x2="12" y2="12"/>
                                <line x1="12" y1="8" x2="12.01" y2="8"/>
                            </svg>
                            <span>
                                ${this.escapeHtml(this.selectedDevice.ip_address)}:${this.selectedDevice.snmp_port || 161} 
                                ${this.selectedDevice.device_type ? `(${this.escapeHtml(this.selectedDevice.device_type)})` : ''}
                            </span>
                        </div>
                    ` : ''}
                </div>
            </div>

            <!-- Step 2: Select Walk Config -->
            <div class="snmp-walk-execute-step" id="executeStep2" style="${this.selectedDevice ? '' : 'display: none;'}">
                <div class="snmp-walk-step-header">
                    <div class="snmp-walk-step-number">2</div>
                    <h3 class="snmp-walk-step-title">Select Walk Configuration</h3>
                </div>

                <div class="snmp-walk-radio-group">
                    <!-- Predefined Config -->
                    <div class="snmp-walk-radio-option ${this.configMode === 'predefined' ? 'selected' : ''}" id="radioPredefined">
                        <label class="snmp-walk-radio-label">
                            <input type="radio" name="configMode" value="predefined" ${this.configMode === 'predefined' ? 'checked' : ''} />
                            <span>Use Predefined Configuration</span>
                        </label>
                        <div class="snmp-walk-radio-content">
                            <select class="form-select" id="executeConfigSelect">
                                <option value="">Choose configuration...</option>
                                ${enabledConfigs.map(c => `
                                    <option value="${c.id}" ${this.selectedConfig && this.selectedConfig.id === c.id ? 'selected' : ''}>
                                        ${this.escapeHtml(c.name)} (${this.escapeHtml(c.base_oid)})
                                    </option>
                                `).join('')}
                            </select>
                            ${this.selectedConfig ? `
                                <div class="snmp-walk-selection-info" style="margin-top: var(--spacing-sm);">
                                    <svg style="width: 16px; height: 16px;" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                        <circle cx="12" cy="12" r="10"/>
                                        <line x1="12" y1="16" x2="12" y2="12"/>
                                        <line x1="12" y1="8" x2="12.01" y2="8"/>
                                    </svg>
                                    <span>Base OID: ${this.escapeHtml(this.selectedConfig.base_oid)} | Type: ${this.escapeHtml(this.selectedConfig.walk_type)}</span>
                                </div>
                            ` : ''}
                        </div>
                    </div>

                    <!-- Custom OID -->
                    <div class="snmp-walk-radio-option ${this.configMode === 'custom' ? 'selected' : ''}" id="radioCustom">
                        <label class="snmp-walk-radio-label">
                            <input type="radio" name="configMode" value="custom" ${this.configMode === 'custom' ? 'checked' : ''} />
                            <span>Custom OID</span>
                        </label>
                        <div class="snmp-walk-radio-content">
                            <div class="form-group">
                                <label>Base OID</label>
                                <div class="snmp-walk-oid-input-group">
                                    <input type="text" class="form-input" id="customOidInput" placeholder="1.3.6.1.2.1.1" value="${this.customOid}" />
                                    <button class="btn btn-secondary" id="lookupOidBtn" title="Lookup OID">
                                        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                            <circle cx="11" cy="11" r="8"/>
                                            <path d="m21 21-4.35-4.35"/>
                                        </svg>
                                        Lookup
                                    </button>
                                    <button class="btn btn-secondary" id="browseOidsBtn" title="Browse OIDs">
                                        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                            <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>
                                        </svg>
                                        Browse
                                    </button>
                                </div>
                                <div id="oidLookupResult"></div>
                            </div>

                            <div class="form-group">
                                <label>Walk Type</label>
                                <select class="form-select" id="customWalkTypeSelect">
                                    <option value="system">System</option>
                                    <option value="bgp_peers">BGP Peers</option>
                                    <option value="interfaces">Interfaces</option>
                                    <option value="routing">Routing</option>
                                    <option value="memory">Memory</option>
                                    <option value="custom" selected>Custom</option>
                                </select>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Step 3: Options -->
            <div class="snmp-walk-execute-step" id="executeStep3" style="${this.selectedDevice && (this.selectedConfig || this.customOid) ? '' : 'display: none;'}">
                <div class="snmp-walk-step-header">
                    <div class="snmp-walk-step-number">3</div>
                    <h3 class="snmp-walk-step-title">Options</h3>
                </div>

                <label class="checkbox-label">
                    <input type="checkbox" id="resolveOidsCheckbox" ${this.resolveOids ? 'checked' : ''} />
                    <span>Resolve OIDs (lookup names from trap_master_data)</span>
                </label>
            </div>

            <!-- Execute Button -->
            <div style="display: flex; justify-content: flex-end; margin-top: var(--spacing-lg);">
                <button class="btn btn-primary btn-lg" id="executeWalkBtn" ${this.canExecute() ? '' : 'disabled'}>
                    <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <polygon points="5 3 19 12 5 21 5 3"/>
                    </svg>
                    Execute Walk
                </button>
            </div>

            <!-- Execution Results Preview -->
            <div id="executionResultsContainer"></div>
        `;

        this.setupExecuteEventListeners();
    }

    setupExecuteEventListeners() {
        // Device select
        const deviceSelect = document.getElementById('executeDeviceSelect');
        if (deviceSelect) {
            deviceSelect.addEventListener('change', (e) => {
                const deviceId = parseInt(e.target.value);
                this.selectedDevice = this.devices.find(d => d.id === deviceId) || null;
                this.renderExecuteTab();
            });
        }

        // Config mode radio
        document.querySelectorAll('input[name="configMode"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.configMode = e.target.value;
                
                // Update radio option styling
                document.getElementById('radioPredefined').classList.toggle('selected', this.configMode === 'predefined');
                document.getElementById('radioCustom').classList.toggle('selected', this.configMode === 'custom');
                
                this.renderExecuteTab();
            });
        });

        // Config select
        const configSelect = document.getElementById('executeConfigSelect');
        if (configSelect) {
            configSelect.addEventListener('change', (e) => {
                const configId = parseInt(e.target.value);
                this.selectedConfig = this.configs.find(c => c.id === configId) || null;
                this.renderExecuteTab();
            });
        }

        // Custom OID input
        const customOidInput = document.getElementById('customOidInput');
        if (customOidInput) {
            customOidInput.addEventListener('input', (e) => {
                this.customOid = e.target.value.trim();
                this.renderExecuteTab();
            });
        }

        // Custom walk type
        const customWalkTypeSelect = document.getElementById('customWalkTypeSelect');
        if (customWalkTypeSelect) {
            customWalkTypeSelect.addEventListener('change', (e) => {
                this.customWalkType = e.target.value;
            });
        }

        // Resolve OIDs checkbox
        const resolveCheckbox = document.getElementById('resolveOidsCheckbox');
        if (resolveCheckbox) {
            resolveCheckbox.addEventListener('change', (e) => {
                this.resolveOids = e.target.checked;
            });
        }

        // Lookup OID button
        const lookupBtn = document.getElementById('lookupOidBtn');
        if (lookupBtn) {
            lookupBtn.addEventListener('click', () => this.lookupOid());
        }

        // Browse OIDs button
        const browseBtn = document.getElementById('browseOidsBtn');
        if (browseBtn) {
            browseBtn.addEventListener('click', () => this.showOidBrowserModal());
        }

        // Execute button
        const executeBtn = document.getElementById('executeWalkBtn');
        if (executeBtn) {
            executeBtn.addEventListener('click', () => this.executeWalk());
        }
    }

    canExecute() {
        if (!this.selectedDevice) return false;
        
        if (this.configMode === 'predefined') {
            return this.selectedConfig !== null;
        } else {
            return this.customOid.length > 0;
        }
    }

    async lookupOid() {
        const oid = this.customOid.trim();
        if (!oid) {
            notify.warning('Please enter an OID first');
            return;
        }

        try {
            const response = await api.get(`/snmp-walk/oid-resolver/resolve/${encodeURIComponent(oid)}`);
            
            const resultContainer = document.getElementById('oidLookupResult');
            if (!resultContainer) return;

            if (response && response.success && response.result) {
                const result = response.result;
                resultContainer.innerHTML = `
                    <div class="snmp-walk-oid-result">
                        <div class="snmp-walk-oid-result-title">✅ ${this.escapeHtml(result.name)}</div>
                        <div class="snmp-walk-oid-result-meta">
                            ${this.escapeHtml(result.description || 'No description')} | 
                            Type: ${this.escapeHtml(result.type)} | 
                            Module: ${this.escapeHtml(result.module)}
                        </div>
                    </div>
                `;
            } else {
                resultContainer.innerHTML = `
                    <div class="snmp-walk-oid-result error">
                        <div class="snmp-walk-oid-result-title">❌ OID not found</div>
                        <div class="snmp-walk-oid-result-meta">OID '${this.escapeHtml(oid)}' not found in trap_master_data</div>
                    </div>
                `;
            }
        } catch (error) {
            console.error('OID lookup failed:', error);
            notify.error(`Lookup failed: ${error.message}`);
        }
    }

    showOidBrowserModal() {
        const content = `
            <div style="display: flex; flex-direction: column; gap: var(--spacing-md);">
                <div class="snmp-walk-search-box">
                    <svg class="snmp-walk-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <circle cx="11" cy="11" r="8"/>
                        <path d="m21 21-4.35-4.35"/>
                    </svg>
                    <input 
                        type="text" 
                        class="snmp-walk-search-input" 
                        id="oidBrowserSearch"
                        placeholder="Search OIDs (e.g., bgp, system, interface)..."
                    />
                </div>

                <div id="oidBrowserResults" class="snmp-walk-oid-search-results">
                    <div style="text-align: center; padding: var(--spacing-xl); color: var(--color-text-secondary);">
                        Enter a search term to find OIDs
                    </div>
                </div>
            </div>
        `;

        modal.show({
            title: 'Browse OIDs',
            content: content,
            size: 'large',
            buttons: [
                {
                    text: 'Close',
                    class: 'btn-secondary',
                    onClick: () => modal.close()
                }
            ]
        });

        // Setup search
        setTimeout(() => {
            const searchInput = document.getElementById('oidBrowserSearch');
            if (searchInput) {
                let searchTimer = null;
                searchInput.addEventListener('input', (e) => {
                    clearTimeout(searchTimer);
                    searchTimer = setTimeout(() => {
                        this.searchOids(e.target.value.trim());
                    }, 500);
                });
                searchInput.focus();
            }
        }, 100);
    }

    async searchOids(query) {
        if (!query || query.length < 2) {
            const resultsContainer = document.getElementById('oidBrowserResults');
            if (resultsContainer) {
                resultsContainer.innerHTML = `
                    <div style="text-align: center; padding: var(--spacing-xl); color: var(--color-text-secondary);">
                        Enter at least 2 characters to search
                    </div>
                `;
            }
            return;
        }

        try {
            const response = await api.get('/snmp-walk/oid-resolver/search', {
                search: query,
                limit: 50
            });

            const resultsContainer = document.getElementById('oidBrowserResults');
            if (!resultsContainer) return;

            if (response && response.success && response.results && response.results.length > 0) {
                resultsContainer.innerHTML = response.results.map(oid => `
                    <div class="snmp-walk-oid-search-item">
                        <div class="snmp-walk-oid-search-info">
                            <div class="snmp-walk-oid-search-name">${this.escapeHtml(oid.name)}</div>
                            <div class="snmp-walk-oid-search-oid">
                                <code>${this.escapeHtml(oid.oid)}</code> | 
                                ${this.escapeHtml(oid.module)} | 
                                ${this.escapeHtml(oid.type)}
                            </div>
                        </div>
                        <button class="btn btn-sm btn-primary" onclick="snmpWalkComponent.selectOidFromBrowser('${this.escapeHtml(oid.oid)}')">
                            Use
                        </button>
                    </div>
                `).join('');
            } else {
                resultsContainer.innerHTML = `
                    <div style="text-align: center; padding: var(--spacing-xl); color: var(--color-text-secondary);">
                        No OIDs found matching "${this.escapeHtml(query)}"
                    </div>
                `;
            }
        } catch (error) {
            console.error('OID search failed:', error);
            notify.error(`Search failed: ${error.message}`);
        }
    }

    selectOidFromBrowser(oid) {
        this.customOid = oid;
        modal.close();
        this.renderExecuteTab();
        notify.success(`OID selected: ${oid}`);
    }

    async executeWalk() {
        if (!this.canExecute()) {
            notify.error('Please select device and configuration');
            return;
        }

        try {
            window.showLoading('Executing SNMP walk...');

            const payload = {
                device_id: this.selectedDevice.id,
                resolve_oids: this.resolveOids
            };

            if (this.configMode === 'predefined') {
                payload.config_id = this.selectedConfig.id;
            } else {
                payload.base_oid = this.customOid;
                payload.walk_type = this.customWalkType;
            }

            const response = await api.post('/snmp-walk/execute', payload);
            window.hideLoading();

            if (response && response.success) {
                this.lastExecutionResult = response;
                notify.success(`✅ Walk completed: ${response.results_count} OIDs retrieved`);
                this.renderExecutionResults(response);
            } else {
                throw new Error(response.error || 'Walk execution failed');
            }
        } catch (error) {
            window.hideLoading();
            console.error('Walk execution failed:', error);
            notify.error(`Execution failed: ${error.message}`);
            
            // Show error in results
            this.renderExecutionError(error.message);
        }
    }

    renderExecutionResults(result) {
        const container = document.getElementById('executionResultsContainer');
        if (!container) return;

        const previewResults = result.results ? result.results.slice(0, 100) : [];

        container.innerHTML = `
            <div class="snmp-walk-result-preview" style="margin-top: var(--spacing-lg);">
                <div class="snmp-walk-result-header">
                    <div class="snmp-walk-result-icon">✅</div>
                    <div>
                        <div class="snmp-walk-result-title">Walk Completed Successfully</div>
                    </div>
                </div>

                <div class="snmp-walk-result-stats">
                    <div class="snmp-walk-result-stat">
                        <div class="snmp-walk-result-stat-label">Device</div>
                        <div class="snmp-walk-result-stat-value">${this.escapeHtml(result.device_name)}</div>
                    </div>
                    <div class="snmp-walk-result-stat">
                        <div class="snmp-walk-result-stat-label">IP Address</div>
                        <div class="snmp-walk-result-stat-value">${this.escapeHtml(result.device_ip)}</div>
                    </div>
                    <div class="snmp-walk-result-stat">
                        <div class="snmp-walk-result-stat-label">Base OID</div>
                        <div class="snmp-walk-result-stat-value"><code>${this.escapeHtml(result.base_oid)}</code></div>
                    </div>
                    <div class="snmp-walk-result-stat">
                        <div class="snmp-walk-result-stat-label">Results</div>
                        <div class="snmp-walk-result-stat-value">${result.results_count} OIDs</div>
                    </div>
                    <div class="snmp-walk-result-stat">
                        <div class="snmp-walk-result-stat-label">Resolved</div>
                        <div class="snmp-walk-result-stat-value">${result.resolved_count} (${((result.resolved_count / result.results_count) * 100).toFixed(1)}%)</div>
                    </div>
                    <div class="snmp-walk-result-stat">
                        <div class="snmp-walk-result-stat-label">Duration</div>
                        <div class="snmp-walk-result-stat-value">${result.duration.toFixed(2)}s</div>
                    </div>
                </div>

                <div style="margin-bottom: var(--spacing-md);">
                    <button class="btn btn-primary" onclick="snmpWalkComponent.switchTab('results')">
                        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                        </svg>
                        View Full Results in Results Tab
                    </button>
                </div>

                ${previewResults.length > 0 ? `
                    <div>
                        <h4 style="margin-bottom: var(--spacing-sm);">Preview (First ${previewResults.length} rows)</h4>
                        <div class="snmp-walk-table-container">
                            <table class="snmp-walk-table">
                                <thead>
                                    <tr>
                                        <th>OID</th>
                                        <th>Name</th>
                                        <th>Value</th>
                                        <th>Type</th>
                                        <th style="width: 50px; text-align: center;">✓</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${previewResults.map(r => `
                                        <tr>
                                            <td><code style="font-size: var(--font-size-xs);">${this.escapeHtml(r.oid)}</code></td>
                                            <td>${r.resolved ? `<strong>${this.escapeHtml(r.oid_name)}</strong>` : '<em>Unresolved</em>'}</td>
                                            <td>${this.escapeHtml(r.value)}</td>
                                            <td><span class="badge-compact">${this.escapeHtml(r.value_type)}</span></td>
                                            <td style="text-align: center;">${r.resolved ? '✅' : '❌'}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>
                ` : ''}
            </div>
        `;

        // Scroll to results
        setTimeout(() => {
            container.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
    }

    renderExecutionError(errorMessage) {
        const container = document.getElementById('executionResultsContainer');
        if (!container) return;

        container.innerHTML = `
            <div class="snmp-walk-result-preview error" style="margin-top: var(--spacing-lg);">
                <div class="snmp-walk-result-header">
                    <div class="snmp-walk-result-icon">❌</div>
                    <div>
                        <div class="snmp-walk-result-title">Walk Failed</div>
                    </div>
                </div>
                <div style="padding: var(--spacing-md); background: var(--color-danger-bg); border-radius: var(--radius-md);">
                    <strong>Error:</strong> ${this.escapeHtml(errorMessage)}
                </div>
            </div>
        `;
    }

    // ============================================
    // RESULTS TAB
    // ============================================

    renderResultsTab() {
        const container = document.getElementById('snmpWalkTabContent');
        if (!container) return;

        container.innerHTML = `
            <div class="snmp-walk-section">
                <div class="snmp-walk-section-header">
                    <h3 class="snmp-walk-section-title">Walk Results</h3>
                    <div style="display: flex; gap: var(--spacing-sm);">
                        <button class="btn btn-sm btn-secondary" id="exportResultsBtn">
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                                <polyline points="7 10 12 15 17 10"/>
                                <line x1="12" y1="15" x2="12" y2="3"/>
                            </svg>
                            Export
                        </button>
                        <button class="btn btn-sm btn-danger" id="clearResultsBtn">
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <polyline points="3 6 5 6 21 6"/>
                                <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                            </svg>
                            Clear Old
                        </button>
                        <button class="btn btn-sm btn-secondary" id="refreshResultsBtn">
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <polyline points="23 4 23 10 17 10"/>
                                <path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/>
                            </svg>
                            Refresh
                        </button>
                    </div>
                </div>

                <!-- Filters -->
                <div class="snmp-walk-filters">
                    <div class="snmp-walk-filter-group">
                        <label class="snmp-walk-filter-label">Device</label>
                        <select class="form-select" id="resultsFilterDevice">
                            <option value="">All Devices</option>
                            ${this.devices.map(d => `
                                <option value="${d.id}" ${this.resultsFilters.device_id === d.id ? 'selected' : ''}>
                                    ${this.escapeHtml(d.name)}
                                </option>
                            `).join('')}
                        </select>
                    </div>

                    <div class="snmp-walk-filter-group">
                        <label class="snmp-walk-filter-label">Config</label>
                        <select class="form-select" id="resultsFilterConfig">
                            <option value="">All Configs</option>
                            ${this.configs.map(c => `
                                <option value="${c.id}" ${this.resultsFilters.config_id === c.id ? 'selected' : ''}>
                                    ${this.escapeHtml(c.name)}
                                </option>
                            `).join('')}
                        </select>
                    </div>

                    <div class="snmp-walk-filter-group">
                        <label class="snmp-walk-filter-label">OID Search</label>
                        <input 
                            type="text" 
                            class="form-input" 
                            id="resultsFilterOid" 
                            placeholder="Search OID or name..."
                            value="${this.resultsFilters.oid_filter}"
                        />
                    </div>

                    <div class="snmp-walk-filter-group">
                        <label class="snmp-walk-filter-label">&nbsp;</label>
                        <label class="checkbox-label">
                            <input type="checkbox" id="resultsFilterResolved" ${this.resultsFilters.resolved_only ? 'checked' : ''} />
                            <span>Resolved Only</span>
                        </label>
                    </div>

                    <div class="snmp-walk-filter-actions">
                        <button class="btn btn-primary" id="applyFiltersBtn">Apply</button>
                        <button class="btn btn-secondary" id="clearFiltersBtn">Clear</button>
                    </div>
                </div>

                <!-- Results Table -->
                <div id="resultsTableContainer"></div>

                <!-- Pagination -->
                <div id="resultsPaginationContainer"></div>
            </div>
        `;

        this.renderResultsTable();
        this.setupResultsEventListeners();
    }

    renderResultsTable() {
        const container = document.getElementById('resultsTableContainer');
        if (!container) return;

        if (this.results.length === 0) {
            container.innerHTML = `
                <div class="snmp-walk-empty">
                    <svg class="snmp-walk-empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                    </svg>
                    <div class="snmp-walk-empty-title">No results found</div>
                    <div class="snmp-walk-empty-text">Execute a walk to see results here</div>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div class="snmp-walk-table-container">
                <table class="snmp-walk-table">
                    <thead>
                        <tr>
                            <th>Device</th>
                            <th>OID</th>
                            <th>Name</th>
                            <th>Value</th>
                            <th>Type</th>
                            <th>Collected</th>
                            <th style="width: 100px; text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${this.results.map(result => `
                            <tr>
                                <td><strong>${this.escapeHtml(result.device_name)}</strong></td>
                                <td><code style="font-size: var(--font-size-xs);">${this.escapeHtml(result.oid)}</code></td>
                                <td>${result.resolved ? `<strong>${this.escapeHtml(result.oid_name)}</strong>` : '<em>Unresolved</em>'}</td>
                                <td>${this.escapeHtml(result.value)}</td>
                                <td><span class="badge-compact">${this.escapeHtml(result.value_type)}</span></td>
                                <td>${Utils.formatRelativeTime(result.collected_at)}</td>
                                <td style="text-align: right;">
                                    <button class="btn btn-sm btn-secondary" onclick="snmpWalkComponent.showResultDetails(${result.id})" title="View Details">
                                        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                            <circle cx="12" cy="12" r="3"/>
                                        </svg>
                                    </button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;

        this.renderResultsPagination();
    }

    renderResultsPagination() {
        const container = document.getElementById('resultsPaginationContainer');
        if (!container) return;

        const totalPages = Math.ceil(this.resultsTotal / this.resultsLimit);
        const startRecord = (this.resultsPage - 1) * this.resultsLimit + 1;
        const endRecord = Math.min(this.resultsPage * this.resultsLimit, this.resultsTotal);

        if (this.resultsTotal === 0) {
            container.innerHTML = '';
            return;
        }

        container.innerHTML = `
            <div class="snmp-walk-pagination">
                <div class="snmp-walk-pagination-info">
                    Showing ${startRecord}-${endRecord} of ${this.resultsTotal} results
                </div>
                <div class="snmp-walk-pagination-controls">
                    <button class="snmp-walk-pagination-btn" ${this.resultsPage === 1 ? 'disabled' : ''} onclick="snmpWalkComponent.goToResultsPage(1)">
                        First
                    </button>
                    <button class="snmp-walk-pagination-btn" ${this.resultsPage === 1 ? 'disabled' : ''} onclick="snmpWalkComponent.goToResultsPage(${this.resultsPage - 1})">
                        ◀ Prev
                    </button>
                    ${this.renderPageNumbers(totalPages)}
                    <button class="snmp-walk-pagination-btn" ${this.resultsPage === totalPages ? 'disabled' : ''} onclick="snmpWalkComponent.goToResultsPage(${this.resultsPage + 1})">
                        Next ▶
                    </button>
                    <button class="snmp-walk-pagination-btn" ${this.resultsPage === totalPages ? 'disabled' : ''} onclick="snmpWalkComponent.goToResultsPage(${totalPages})">
                        Last
                    </button>
                </div>
            </div>
        `;
    }

    renderPageNumbers(totalPages) {
        const maxVisible = 5;
        let pages = [];

        if (totalPages <= maxVisible) {
            pages = Array.from({ length: totalPages }, (_, i) => i + 1);
        } else {
            const start = Math.max(1, this.resultsPage - 2);
            const end = Math.min(totalPages, this.resultsPage + 2);
            pages = Array.from({ length: end - start + 1 }, (_, i) => start + i);
        }

        return pages.map(page => `
            <button class="snmp-walk-pagination-btn ${page === this.resultsPage ? 'active' : ''}" onclick="snmpWalkComponent.goToResultsPage(${page})">
                ${page}
            </button>
        `).join('');
    }

    goToResultsPage(page) {
        this.resultsPage = page;
        this.loadResults();
    }

    setupResultsEventListeners() {
        const exportBtn = document.getElementById('exportResultsBtn');
        const clearBtn = document.getElementById('clearResultsBtn');
        const refreshBtn = document.getElementById('refreshResultsBtn');
        const applyFiltersBtn = document.getElementById('applyFiltersBtn');
        const clearFiltersBtn = document.getElementById('clearFiltersBtn');

        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportResults());
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearOldResults());
        }

        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadResults());
        }

        if (applyFiltersBtn) {
            applyFiltersBtn.addEventListener('click', () => {
                this.applyResultsFilters();
            });
        }

        if (clearFiltersBtn) {
            clearFiltersBtn.addEventListener('click', () => {
                this.clearResultsFilters();
            });
        }
    }

    applyResultsFilters() {
        const deviceSelect = document.getElementById('resultsFilterDevice');
        const configSelect = document.getElementById('resultsFilterConfig');
        const oidInput = document.getElementById('resultsFilterOid');
        const resolvedCheckbox = document.getElementById('resultsFilterResolved');

        this.resultsFilters = {
            device_id: deviceSelect ? (deviceSelect.value ? parseInt(deviceSelect.value) : null) : null,
            config_id: configSelect ? (configSelect.value ? parseInt(configSelect.value) : null) : null,
            oid_filter: oidInput ? oidInput.value.trim() : '',
            resolved_only: resolvedCheckbox ? resolvedCheckbox.checked : false
        };

        this.resultsPage = 1;
        this.loadResults();
    }

    clearResultsFilters() {
        this.resultsFilters = {
            device_id: null,
            config_id: null,
            oid_filter: '',
            resolved_only: false
        };
        this.resultsPage = 1;
        this.renderResultsTab();
        this.loadResults();
    }

    async loadResults() {
        try {
            const params = {
                limit: this.resultsLimit,
                offset: (this.resultsPage - 1) * this.resultsLimit,
                sort_by: 'collected_at',
                sort_order: 'desc'
            };

            if (this.resultsFilters.device_id) {
                params.device_id = this.resultsFilters.device_id;
            }

            if (this.resultsFilters.config_id) {
                params.config_id = this.resultsFilters.config_id;
            }

            if (this.resultsFilters.oid_filter) {
                params.oid_filter = this.resultsFilters.oid_filter;
            }

            if (this.resultsFilters.resolved_only) {
                params.resolved_only = true;
            }

            const response = await api.post('/snmp-walk/results/query', params);

            if (response && response.success) {
                this.results = response.results || [];
                this.resultsTotal = response.total || 0;
            } else {
                this.results = [];
                this.resultsTotal = 0;
            }

            if (this.activeTab === 'results') {
                this.renderResultsTable();
            }
        } catch (error) {
            console.error('Failed to load results:', error);
            notify.error(`Failed to load results: ${error.message}`);
        }
    }

    showResultDetails(resultId) {
        const result = this.results.find(r => r.id === resultId);
        if (!result) {
            notify.error('Result not found');
            return;
        }

        const content = `
            <div style="display: flex; flex-direction: column; gap: var(--spacing-md);">
                <div style="display: grid; grid-template-columns: 150px 1fr; gap: var(--spacing-sm); font-size: var(--font-size-sm);">
                    <div style="font-weight: var(--font-weight-semibold); color: var(--color-text-secondary);">Device:</div>
                    <div>${this.escapeHtml(result.device_name)}</div>

                    <div style="font-weight: var(--font-weight-semibold); color: var(--color-text-secondary);">IP Address:</div>
                    <div>${this.escapeHtml(result.device_ip)}</div>

                    <div style="font-weight: var(--font-weight-semibold); color: var(--color-text-secondary);">Config:</div>
                    <div>${this.escapeHtml(result.config_name || 'Custom')}</div>

                    <div style="font-weight: var(--font-weight-semibold); color: var(--color-text-secondary);">Base OID:</div>
                    <div><code>${this.escapeHtml(result.base_oid)}</code></div>

                    <div style="font-weight: var(--font-weight-semibold); color: var(--color-text-secondary);">Walk Type:</div>
                    <div>${this.escapeHtml(result.walk_type || 'custom')}</div>

                    <div style="border-top: 1px solid var(--color-border); padding-top: var(--spacing-sm); grid-column: 1 / -1;"></div>

                    <div style="font-weight: var(--font-weight-semibold); color: var(--color-text-secondary);">OID:</div>
                    <div><code>${this.escapeHtml(result.oid)}</code></div>

                    ${result.oid_index ? `
                        <div style="font-weight: var(--font-weight-semibold); color: var(--color-text-secondary);">OID Index:</div>
                        <div><code>${this.escapeHtml(result.oid_index)}</code></div>
                    ` : ''}

                    ${result.resolved ? `
                        <div style="font-weight: var(--font-weight-semibold); color: var(--color-text-secondary);">OID Name:</div>
                        <div><strong>${this.escapeHtml(result.oid_name)}</strong></div>

                        ${result.oid_description ? `
                            <div style="font-weight: var(--font-weight-semibold); color: var(--color-text-secondary);">Description:</div>
                            <div>${this.escapeHtml(result.oid_description)}</div>
                        ` : ''}

                        ${result.oid_syntax ? `
                            <div style="font-weight: var(--font-weight-semibold); color: var(--color-text-secondary);">Syntax:</div>
                            <div>${this.escapeHtml(result.oid_syntax)}</div>
                        ` : ''}

                        ${result.oid_module ? `
                            <div style="font-weight: var(--font-weight-semibold); color: var(--color-text-secondary);">Module:</div>
                            <div>${this.escapeHtml(result.oid_module)}</div>
                        ` : ''}
                    ` : `
                        <div style="font-weight: var(--font-weight-semibold); color: var(--color-text-secondary);">Status:</div>
                        <div><em style="color: var(--color-warning);">Unresolved</em></div>
                    `}

                    <div style="border-top: 1px solid var(--color-border); padding-top: var(--spacing-sm); grid-column: 1 / -1;"></div>

                    <div style="font-weight: var(--font-weight-semibold); color: var(--color-text-secondary);">Value:</div>
                    <div><strong>${this.escapeHtml(result.value)}</strong></div>

                    <div style="font-weight: var(--font-weight-semibold); color: var(--color-text-secondary);">Value Type:</div>
                    <div><span class="badge-compact">${this.escapeHtml(result.value_type)}</span></div>

                    <div style="border-top: 1px solid var(--color-border); padding-top: var(--spacing-sm); grid-column: 1 / -1;"></div>

                    <div style="font-weight: var(--font-weight-semibold); color: var(--color-text-secondary);">Collected:</div>
                    <div>${Utils.formatDateTime(result.collected_at)}</div>

                    ${result.job_id ? `
                        <div style="font-weight: var(--font-weight-semibold); color: var(--color-text-secondary);">Job ID:</div>
                        <div><code>${this.escapeHtml(result.job_id)}</code></div>
                    ` : ''}
                </div>
            </div>
        `;

        modal.show({
            title: 'Walk Result Details',
            content: content,
            size: 'medium',
            buttons: [
                {
                    text: 'Copy JSON',
                    class: 'btn-secondary',
                    onClick: () => {
                        navigator.clipboard.writeText(JSON.stringify(result, null, 2));
                        notify.success('Copied to clipboard');
                    }
                },
                {
                    text: 'Close',
                    class: 'btn-primary',
                    onClick: () => modal.close()
                }
            ]
        });
    }

    async exportResults() {
        if (this.results.length === 0) {
            notify.warning('No results to export');
            return;
        }

        try {
            window.showLoading('Exporting results...');

            // Build query params
            const params = {
                limit: this.resultsTotal, // Export all matching results
                offset: 0,
                sort_by: 'collected_at',
                sort_order: 'desc'
            };

            if (this.resultsFilters.device_id) params.device_id = this.resultsFilters.device_id;
            if (this.resultsFilters.config_id) params.config_id = this.resultsFilters.config_id;
            if (this.resultsFilters.oid_filter) params.oid_filter = this.resultsFilters.oid_filter;
            if (this.resultsFilters.resolved_only) params.resolved_only = true;

            const response = await api.post('/snmp-walk/results/query', params);

            window.hideLoading();

            if (response && response.success && response.results) {
                const timestamp = new Date().toISOString().split('T')[0];
                const filename = `snmp_walk_results_${timestamp}.json`;
                
                const json = JSON.stringify(response.results, null, 2);
                const blob = new Blob([json], { type: 'application/json' });
                const url = window.URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = filename;
                link.click();
                window.URL.revokeObjectURL(url);

                notify.success(`Exported ${response.results.length} results to ${filename}`);
            } else {
                throw new Error('Failed to export results');
            }
        } catch (error) {
            window.hideLoading();
            console.error('Export failed:', error);
            notify.error(`Export failed: ${error.message}`);
        }
    }

    async clearOldResults() {
        const confirmed = await modal.confirm({
            title: 'Clear Old Results',
            message: 'Delete results older than 30 days? This action cannot be undone.',
            confirmText: 'Clear',
            cancelText: 'Cancel',
            danger: true
        });

        if (!confirmed) return;

        try {
            window.showLoading('Clearing old results...');
            const response = await api.delete('/snmp-walk/results/clear', {
                older_than_days: 30
            });
            window.hideLoading();

            if (response && response.success) {
                notify.success(`Cleared ${response.deleted_count} old results`);
                await this.loadResults();
            } else {
                throw new Error(response.message || 'Failed to clear results');
            }
        } catch (error) {
            window.hideLoading();
            console.error('Clear results failed:', error);
            notify.error(`Failed to clear results: ${error.message}`);
        }
    }

    // ============================================
    // STATS TAB
    // ============================================

    renderStatsTab() {
        const container = document.getElementById('snmpWalkTabContent');
        if (!container) return;

        container.innerHTML = `
            <div class="snmp-walk-section">
                <div class="snmp-walk-section-header">
                    <h3 class="snmp-walk-section-title">Statistics</h3>
                    <button class="btn btn-sm btn-secondary" id="refreshStatsBtn">
                        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <polyline points="23 4 23 10 17 10"/>
                            <path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/>
                        </svg>
                        Refresh
                    </button>
                </div>

                <div id="statsContainer"></div>
            </div>
        `;

        this.renderStats();
        this.setupStatsEventListeners();
    }

    renderStats() {
        const container = document.getElementById('statsContainer');
        if (!container) return;

        if (!this.stats) {
            container.innerHTML = `
                <div style="text-align: center; padding: var(--spacing-xl); color: var(--color-text-secondary);">
                    Loading statistics...
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <!-- Overview Stats -->
            <div class="snmp-walk-stats-grid">
                <div class="snmp-walk-stat-card">
                    <div class="snmp-walk-stat-value">${this.stats.total_devices || 0}</div>
                    <div class="snmp-walk-stat-label">Total Devices</div>
                </div>
                <div class="snmp-walk-stat-card">
                    <div class="snmp-walk-stat-value">${this.stats.enabled_devices || 0}</div>
                    <div class="snmp-walk-stat-label">Enabled Devices</div>
                </div>
                <div class="snmp-walk-stat-card">
                    <div class="snmp-walk-stat-value">${this.stats.total_configs || 0}</div>
                    <div class="snmp-walk-stat-label">Total Configs</div>
                </div>
                <div class="snmp-walk-stat-card">
                    <div class="snmp-walk-stat-value">${this.stats.enabled_configs || 0}</div>
                    <div class="snmp-walk-stat-label">Enabled Configs</div>
                </div>
                <div class="snmp-walk-stat-card">
                    <div class="snmp-walk-stat-value">${Utils.formatNumber(this.stats.total_results || 0)}</div>
                    <div class="snmp-walk-stat-label">Total Results</div>
                </div>
                <div class="snmp-walk-stat-card">
                    <div class="snmp-walk-stat-value">${Utils.formatNumber(this.stats.resolved_results || 0)}</div>
                    <div class="snmp-walk-stat-label">Resolved Results</div>
                </div>
                <div class="snmp-walk-stat-card">
                    <div class="snmp-walk-stat-value">${this.stats.resolution_percentage ? this.stats.resolution_percentage.toFixed(1) : '0.0'}%</div>
                    <div class="snmp-walk-stat-label">Resolution Rate</div>
                </div>
                <div class="snmp-walk-stat-card">
                    <div class="snmp-walk-stat-value">${this.stats.last_walk_time ? Utils.formatRelativeTime(this.stats.last_walk_time) : 'Never'}</div>
                    <div class="snmp-walk-stat-label">Last Walk</div>
                </div>
            </div>
        `;
    }

    setupStatsEventListeners() {
        const refreshBtn = document.getElementById('refreshStatsBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadStats());
        }
    }

    async loadStats() {
        try {
            const response = await api.get('/snmp-walk/stats');

            if (response) {
                this.stats = response;
            } else {
                this.stats = null;
            }

            if (this.activeTab === 'stats') {
                this.renderStats();
            }
        } catch (error) {
            console.error('Failed to load stats:', error);
            notify.error(`Failed to load stats: ${error.message}`);
        }
    }

    // ============================================
    // UTILITIES
    // ============================================

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // console.log('🔧 Initializing SnmpWalkComponent...');
    window.snmpWalkComponent = new SnmpWalkComponent();
    // console.log('✅ SnmpWalkComponent initialized:', window.snmpWalkComponent);
});

