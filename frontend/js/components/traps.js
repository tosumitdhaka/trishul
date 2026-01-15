/* ============================================
   SNMP Traps Component - Compact Table Design
   ============================================ */

class TrapsComponent {
    constructor() {
        // Active tab
        this.activeTab = 'sender';

        // Sender state
        this.notifications = [];
        this.selectedNotification = null;
        this.notificationObjects = [];
        this.varbindValues = {};
        this.additionalVarbinds = [];
        this.templates = [];
        this.sentHistory = [];
        this.targetConfig = {
            host: '127.0.0.1',
            port: 1162,
            community: 'public',
            version: 'v2c'
        };

        // Receiver state
        this.receiverStatus = { running: false, port: 1162, bind_address: '0.0.0.0' };
        this.receivedTraps = [];
        this.autoRefresh = true;
        this.refreshInterval = 5000;
        this.autoRefreshTimer = null;
        this.filters = { sourceIp: '', trapOid: '', trapName: '' };

        // Debounce timers
        this.notificationSearchTimer = null;
        this.varbindSearchTimer = null;

        this.init();
    }

    init() {
        this.render();
        this.loadTemplates();
    }

    /**
     * Switch tab - Called from sidebar or programmatically
     */
    switchTab(tab) {
        this.activeTab = tab;

        // Render content based on tab
        if (tab === 'sender') {
            this.renderSender();
        } else if (tab === 'receiver') {
            this.renderReceiver();
            this.loadReceiverStatus();
            this.loadReceivedTraps();
            if (this.autoRefresh) {
                this.startAutoRefresh();
            }
        }
    }

    /**
     * Initial render - Shows sender by default
     */
    render() {
        const container = document.getElementById('trapsContent');
        if (!container) return;

        container.innerHTML = '';
        
        // Render based on active tab
        if (this.activeTab === 'sender') {
            this.renderSender();
        } else {
            this.renderReceiver();
        }
    }


    // ============================================
    // SENDER TAB
    // ============================================

    renderSender() {
        const container = document.getElementById('trapsContent');
        if (!container) return;

        container.innerHTML = `
            <!-- Target Config -->
            <div class="sender-top-row">
                <!-- Target Configuration -->
                <section class="trap-section-compact" style="flex: 1;">
                    <div class="section-header-inline">
                        <h3>Target Configuration</h3>
                    </div>
                    <div class="config-form-compact">
                        <label>Host: <input type="text" id="targetHost" class="form-input-inline" value="${this.targetConfig.host}" placeholder="192.168.1.100"></label>
                        <label>Port: <input type="number" id="targetPort" class="form-input-inline" value="${this.targetConfig.port}" placeholder="1162"></label>
                        <label>Community: <input type="text" id="targetCommunity" class="form-input-inline" value="${this.targetConfig.community}" placeholder="public"></label>
                        <label>Version: 
                            <select id="targetVersion" class="form-select-inline">
                                <option value="v2c" selected>SNMP v2c</option>
                            </select>
                        </label>
                    </div>
                </section>

            </div>

            <!-- Select Notification (rest remains same) -->
            <section class="trap-section-compact" id="selectNotificationSection">
                <div class="section-header-inline">
                    <h3>Select Notification</h3>
                </div>

                <div class="search-box-compact">
                    <svg class="search-icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <circle cx="11" cy="11" r="8"/>
                        <path d="m21 21-4.35-4.35"/>
                    </svg>
                    <input 
                        type="text" 
                        id="notificationSearch" 
                        class="search-input-compact" 
                        placeholder="Search notifications... (e.g., linkDown, coldStart)"
                    />
                </div>

                <div id="notificationsList" class="table-container-compact"></div>
            </section>

            <!-- Rest of the sections remain same -->
            <!-- Selected Notification Details -->
            <section class="trap-section-compact" id="selectedNotificationSection" style="display: none;">
                <div class="section-header-inline">
                    <h3>Selected Notification</h3>
                    <button class="btn btn-sm btn-secondary" onclick="trapsComponent.clearSelection()">
                        Clear Selection
                    </button>
                </div>
                <div id="notificationDetails"></div>
            </section>

            <!-- Actions -->
            <section class="trap-section-compact" id="actionsSection" style="display: none;">
                <div class="actions-row">
                    <button class="btn btn-secondary" id="saveTemplateBtn">
                        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/>
                        </svg>
                        Save Template
                    </button>
                    <button class="btn btn-secondary" id="loadTemplateBtn">
                        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
                        </svg>
                        Load Template
                    </button>
                    <button class="btn btn-primary btn-lg" id="sendTrapBtn">
                        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <line x1="22" y1="2" x2="11" y2="13"/>
                            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                        </svg>
                        Send Trap
                    </button>
                </div>
            </section>

            <!-- Sent History -->
            <section class="trap-section-compact">
                <div class="section-header-inline">
                    <h3>Sent History (Last 10)</h3>
                    <button class="btn btn-sm btn-secondary" onclick="trapsComponent.loadSentHistory()">
                        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <polyline points="23 4 23 10 17 10"/>
                            <path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/>
                        </svg>
                        Refresh
                    </button>
                </div>
                <div id="sentHistoryList" class="table-container-compact"></div>
            </section>
        `;

        this.setupSenderEventListeners();
        this.loadNotifications();
        this.loadSentHistory();
    }


    setupSenderEventListeners() {
        // Target config inputs
        const targetHost = document.getElementById('targetHost');
        const targetPort = document.getElementById('targetPort');
        const targetCommunity = document.getElementById('targetCommunity');

        if (targetHost) targetHost.addEventListener('input', (e) => this.targetConfig.host = e.target.value);
        if (targetPort) targetPort.addEventListener('input', (e) => this.targetConfig.port = parseInt(e.target.value));
        if (targetCommunity) targetCommunity.addEventListener('input', (e) => this.targetConfig.community = e.target.value);

        // Notification search (500ms debounce)
        const notificationSearch = document.getElementById('notificationSearch');
        if (notificationSearch) {
            notificationSearch.addEventListener('input', (e) => {
                clearTimeout(this.notificationSearchTimer);
                this.notificationSearchTimer = setTimeout(() => {
                    this.searchNotifications(e.target.value);
                }, 500);
            });
        }

        // Send trap button
        const sendTrapBtn = document.getElementById('sendTrapBtn');
        if (sendTrapBtn) {
            sendTrapBtn.addEventListener('click', () => this.sendTrap());
        }

        // Save template button
        const saveTemplateBtn = document.getElementById('saveTemplateBtn');
        if (saveTemplateBtn) {
            saveTemplateBtn.addEventListener('click', () => this.showSaveTemplateModal());
        }

        // Load template button
        const loadTemplateBtn = document.getElementById('loadTemplateBtn');
        if (loadTemplateBtn) {
            loadTemplateBtn.addEventListener('click', () => this.showLoadTemplateModal());
        }
    }

    async loadNotifications(search = '') {
        try {
            const params = { limit: 20, offset: 0 }; // Changed from 10 to 20
            if (search) params.search = search;

            const response = await api.get('/trap-builder/notifications', params);

            if (response.success) {
                this.notifications = response.notifications || [];
                this.renderNotificationsList();
            }
        } catch (error) {
            console.error('Failed to load notifications:', error);
        }
    }

    async searchNotifications(query) {
        if (!query || query.trim().length < 2) {
            this.loadNotifications();
            return;
        }
        this.loadNotifications(query.trim());
    }

    renderNotificationsList() {
        const container = document.getElementById('notificationsList');
        if (!container) return;

        if (this.notifications.length === 0) {
            container.innerHTML = `
                <div class="empty-state-compact">
                    <p>No notifications found. Try a different search term.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <table class="data-table-compact">
                <thead>
                    <tr>
                        <th style="width: 40px;"></th>
                        <th>Name</th>
                        <th>OID</th>
                        <th>Description</th>
                        <th style="width: 60px; text-align: center;">Objects</th>
                        <th style="width: 100px; text-align: center;">Action</th>
                    </tr>
                </thead>
                <tbody>
                    ${this.notifications.map(notif => `
                        <tr class="table-row-hover">
                            <td style="text-align: center;">📌</td>
                            <td><strong>${notif.name}</strong></td>
                            <td><code class="oid-compact">${notif.oid}</code></td>
                            <td>
                                <span class="text-truncate" title="${this.escapeHtml(notif.description || 'No description')}">
                                    ${this.truncateText(notif.description || 'No description', 50)}
                                </span>
                            </td>
                            <td style="text-align: center;">
                                <span class="badge-compact">${notif.objects_count || 0}</span>
                            </td>
                            <td style="text-align: right;">
                                <button class="btn btn-sm btn-primary" onclick="trapsComponent.selectNotification('${notif.name}')">
                                    Select
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    async selectNotification(name) {
        try {
            window.showLoading('Loading notification details...');

            const response = await api.get(`/trap-builder/notifications/${name}`);

            if (!response.success) {
                throw new Error('Failed to load notification');
            }

            this.selectedNotification = response.notification;

            // Load objects
            const objectsResponse = await api.get(`/trap-builder/notifications/${name}/objects`);

            if (objectsResponse.success) {
                this.notificationObjects = objectsResponse.objects || [];
            }

            // Initialize varbind values
            this.varbindValues = {};
            this.notificationObjects.forEach(obj => {
                this.varbindValues[obj.name] = '';
            });

            // Reset additional varbinds
            this.additionalVarbinds = [];

            window.hideLoading();
            notify.success(`Selected: ${name}`);

            this.renderNotificationDetails();
            this.updateSenderUI();

        } catch (error) {
            window.hideLoading();
            console.error('Failed to select notification:', error);
            notify.error(`Failed to load notification: ${error.message}`);
        }
    }

    clearSelection() {
        this.selectedNotification = null;
        this.notificationObjects = [];
        this.varbindValues = {};
        this.additionalVarbinds = [];
        this.updateSenderUI();
        notify.info('Selection cleared');
    }

    renderNotificationDetails() {
        const container = document.getElementById('notificationDetails');
        if (!container || !this.selectedNotification) return;

        container.innerHTML = `
            <div class="notification-info-compact">
                <div><strong>OID:</strong> <code>${this.selectedNotification.oid}</code></div>
                <div><strong>Module:</strong> ${this.selectedNotification.module || 'Unknown'}</div>
                <div><strong>Description:</strong> ${this.selectedNotification.description || 'No description'}</div>
            </div>

            ${this.notificationObjects.length > 0 ? `
                <div style="margin-top: var(--spacing-md);">
                    <h4 class="subsection-title">Required Varbinds (${this.notificationObjects.length})</h4>
                    <table class="data-table-compact">
                        <thead>
                            <tr>
                                <th>Object Name (OID)</th>
                                <th style="width: 120px;">Type</th>
                                <th style="width: 120px;">Sample</th>
                                <th style="width: 200px; text-align: right;">Value</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${this.notificationObjects.map((obj, index) => this.renderVarbindRow(obj, index)).join('')}
                        </tbody>
                    </table>
                </div>
            ` : ''}

            <div style="margin-top: var(--spacing-md);">
                <h4 class="subsection-title">Additional Varbinds (Optional)</h4>
                <div class="search-box-compact" style="margin-bottom: var(--spacing-sm);">
                    <svg class="search-icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <circle cx="11" cy="11" r="8"/>
                        <path d="m21 21-4.35-4.35"/>
                    </svg>
                    <input 
                        type="text" 
                        id="varbindSearch" 
                        class="search-input-compact" 
                        placeholder="Search objects to add... (e.g., sysUpTime, sysDescr)"
                    />
                </div>
                <div id="varbindSearchResults"></div>
                <div id="additionalVarbindsList"></div>
            </div>
        `;

        // Setup varbind search
        const varbindSearch = document.getElementById('varbindSearch');
        if (varbindSearch) {
            varbindSearch.addEventListener('input', (e) => {
                clearTimeout(this.varbindSearchTimer);
                this.varbindSearchTimer = setTimeout(() => {
                    this.searchVarbinds(e.target.value);
                }, 500);
            });
        }

        // ✅ ADD EVENT LISTENERS FOR VARBIND INPUTS
        this.notificationObjects.forEach((obj, index) => {
            const input = document.getElementById(`varbind_${index}`);
            if (input) {
                input.addEventListener('input', (e) => {
                    this.varbindValues[obj.name] = e.target.value;
                });
                input.addEventListener('change', (e) => {
                    this.varbindValues[obj.name] = e.target.value;
                });
            }
        });
    }

    renderVarbindRow(obj, index) {
        const hasEnums = obj.enumerations && Object.keys(obj.enumerations).length > 0;
        const sampleValue = hasEnums ? Object.keys(obj.enumerations)[0] + '(' + obj.enumerations[Object.keys(obj.enumerations)[0]] + ')' : (obj.default_value || '');

        return `
            <tr>
                <td>
                    <strong>${obj.name}</strong><br>
                    <code class="oid-compact">${obj.oid}</code>
                </td>
                <td><span class="type-badge">${obj.syntax || 'Unknown'}</span></td>
                <td><span class="sample-value">${sampleValue}</span></td>
                <td style="text-align: right;">
                    ${hasEnums ? `
                        <select class="form-select-compact" id="varbind_${index}" data-varbind-name="${obj.name}">
                            <option value="">Select...</option>
                            ${Object.entries(obj.enumerations).map(([label, value]) => `
                                <option value="${value}">${label}(${value})</option>
                            `).join('')}
                        </select>
                    ` : `
                        <input 
                            type="text" 
                            class="form-input-compact" 
                            id="varbind_${index}"
                            data-varbind-name="${obj.name}"
                            placeholder="Enter value..."
                        />
                    `}
                </td>
            </tr>
        `;
    }

    async searchVarbinds(query) {
        if (!query || query.trim().length < 2) {
            document.getElementById('varbindSearchResults').innerHTML = '';
            return;
        }

        try {
            // Use 'q' parameter instead of 'search'
            const response = await api.get('/trap-builder/varbinds/search', {
                q: query.trim(), // Changed from 'search' to 'q'
                limit: 10
            });

            if (response.success) {
                // Response has 'varbinds' field, not 'objects'
                this.renderVarbindSearchResults(response.varbinds || []);
            }
        } catch (error) {
            console.error('Varbind search failed:', error);
            document.getElementById('varbindSearchResults').innerHTML = '';
        }
    }


    renderVarbindSearchResults(objects) {
        const container = document.getElementById('varbindSearchResults');
        if (!container) return;

        if (objects.length === 0) {
            container.innerHTML = '';
            return;
        }

        container.innerHTML = `
            <table class="data-table-compact" style="margin-bottom: var(--spacing-sm);">
                <thead>
                    <tr>
                        <th>Object Name (OID)</th>
                        <th style="width: 120px;">Type</th>
                        <th style="width: 80px; text-align: right;">Action</th>
                    </tr>
                </thead>
                <tbody>
                    ${objects.map(obj => `
                        <tr class="table-row-hover">
                            <td>
                                <strong>${obj.name}</strong><br>
                                <code class="oid-compact">${obj.oid}</code>
                            </td>
                            <td><span class="type-badge">${obj.syntax || 'Unknown'}</span></td>
                            <td style="text-align: right;">
                                <button class="btn btn-sm btn-primary" onclick="trapsComponent.addAdditionalVarbind('${obj.name}', '${obj.oid}', '${obj.syntax}')">
                                    Add
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    addAdditionalVarbind(name, oid, syntax) {
        // Check if already added
        if (this.additionalVarbinds.find(v => v.oid === oid)) {
            notify.warning('Varbind already added');
            return;
        }

        this.additionalVarbinds.push({ name, oid, syntax, value: '' });
        this.renderAdditionalVarbindsList();
        notify.success(`Added: ${name}`);

        // Clear search
        const searchInput = document.getElementById('varbindSearch');
        if (searchInput) searchInput.value = '';
        document.getElementById('varbindSearchResults').innerHTML = '';
    }

    renderAdditionalVarbindsList() {
        const container = document.getElementById('additionalVarbindsList');
        if (!container) return;

        if (this.additionalVarbinds.length === 0) {
            container.innerHTML = '';
            return;
        }

        container.innerHTML = `
            <table class="data-table-compact">
                <thead>
                    <tr>
                        <th>Object Name (OID)</th>
                        <th style="width: 120px;">Type</th>
                        <th style="width: 120px;">Sample</th>
                        <th style="width: 200px; text-align: right;">Value</th>
                        <th style="width: 60px;"></th>
                    </tr>
                </thead>
                <tbody>
                    ${this.additionalVarbinds.map((varbind, index) => `
                        <tr>
                            <td>
                                <strong>${varbind.name}</strong><br>
                                <code class="oid-compact">${varbind.oid}</code>
                            </td>
                            <td><span class="type-badge">${varbind.syntax}</span></td>
                            <td><span class="sample-value">-</span></td>
                            <td style="text-align: right;">
                                <input 
                                    type="text" 
                                    class="form-input-compact" 
                                    id="additional_varbind_${index}"
                                    placeholder="Enter value..."
                                    value="${varbind.value}"
                                />
                            </td>
                            <td style="text-align: center;">
                                <button class="btn btn-sm btn-danger" onclick="trapsComponent.removeAdditionalVarbind(${index})" title="Remove">
                                    ✕
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        // ✅ ADD EVENT LISTENERS FOR ADDITIONAL VARBIND INPUTS
        this.additionalVarbinds.forEach((varbind, index) => {
            const input = document.getElementById(`additional_varbind_${index}`);
            if (input) {
                input.addEventListener('input', (e) => {
                    this.additionalVarbinds[index].value = e.target.value;
                });
            }
        });
    }

    updateAdditionalVarbindValue(index, value) {
        if (this.additionalVarbinds[index]) {
            this.additionalVarbinds[index].value = value;
        }
    }

    removeAdditionalVarbind(index) {
        this.additionalVarbinds.splice(index, 1);
        this.renderAdditionalVarbindsList();
        notify.info('Varbind removed');
    }

    async sendTrap() {
        if (!this.selectedNotification) {
            notify.error('Please select a notification first');
            return;
        }

        // Validate target config
        if (!this.targetConfig.host || !this.targetConfig.port) {
            notify.error('Please configure target host and port');
            return;
        }

        // Build varbind values - collect from inputs
        const varbindValues = {};

        // Collect required varbinds from inputs
        this.notificationObjects.forEach((obj, index) => {
            const input = document.getElementById(`varbind_${index}`);
            if (input) {
                varbindValues[obj.name] = input.value || '';
            } else {
                varbindValues[obj.name] = this.varbindValues[obj.name] || '';
            }
        });

        // Add additional varbinds
        this.additionalVarbinds.forEach(varbind => {
            varbindValues[varbind.name] = varbind.value || '';
        });

        console.log('Sending trap with varbinds:', varbindValues);

        try {
            window.showLoading('Sending trap...');

            const response = await api.post('/traps/send-by-name', {
                notification_name: this.selectedNotification.name,
                target_host: this.targetConfig.host,
                target_port: this.targetConfig.port,
                community: this.targetConfig.community,
                varbind_values: varbindValues
            });

            window.hideLoading();

            if (response.success) {
                notify.success(`✅ Trap sent successfully to ${this.targetConfig.host}:${this.targetConfig.port}`);
                this.loadSentHistory();
            } else {
                throw new Error(response.message || 'Failed to send trap');
            }

        } catch (error) {
            window.hideLoading();
            console.error('Send trap failed:', error);
            notify.error(`Failed to send trap: ${error.message}`);
        }
    }


    async loadSentHistory() {
        try {
            const response = await api.get('/traps/sent', { limit: 10, offset: 0 });

            if (response.success) {
                this.sentHistory = response.traps || [];
                this.renderSentHistory();
            }
        } catch (error) {
            console.error('Failed to load sent history:', error);
        }
    }

    renderSentHistory() {
        const container = document.getElementById('sentHistoryList');
        if (!container) return;

        if (this.sentHistory.length === 0) {
            container.innerHTML = `
                <div class="empty-state-compact">
                    <p>No traps sent yet</p>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <table class="data-table-compact">
                <thead>
                    <tr>
                        <th style="width: 50px; text-align: center;">Status</th>
                        <th>Trap Name</th>
                        <th>Description</th>
                        <th style="width: 150px;">Target</th>
                        <th style="width: 80px; text-align: center;">Varbinds</th>
                        <th style="width: 120px;">Sent At</th>
                        <th style="width: 100px; text-align: right;">Action</th>
                    </tr>
                </thead>
                <tbody>
                    ${this.sentHistory.map(trap => {
                        const isSuccess = trap.status === 'success' || trap.status === 'sent';
                        const varbinds = trap.varbinds ? (typeof trap.varbinds === 'string' ? JSON.parse(trap.varbinds) : trap.varbinds) : [];
                        
                        // Get description from first varbind or use trap name
                        let description = 'No description';
                        if (varbinds.length > 0 && varbinds[0].description) {
                            description = varbinds[0].description;
                        }
                        
                        return `
                            <tr class="table-row-hover">
                                <td style="text-align: center; font-size: var(--font-size-lg);">
                                    ${isSuccess ? '✅' : '❌'}
                                </td>
                                <td><strong>${trap.trap_name || trap.trap_oid || 'Unknown'}</strong></td>
                                <td>
                                    <span class="text-truncate" title="${this.escapeHtml(description)}">
                                        ${this.truncateText(description, 50)}
                                    </span>
                                </td>
                                <td>${trap.target_host}:${trap.target_port}</td>
                                <td style="text-align: center;">
                                    <span class="badge-compact">${varbinds.length}</span>
                                </td>
                                <td>${this.formatRelativeTime(trap.sent_at)}</td>
                                <td style="text-align: right;">
                                    <button class="btn btn-sm btn-secondary" onclick="trapsComponent.showSentTrapDetails(${trap.id})">
                                        Details
                                    </button>
                                </td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        `;
    }



    showSentTrapDetails(trapId) {
        const trap = this.sentHistory.find(t => t.id === trapId);
        if (!trap) {
            notify.error('Trap not found');
            return;
        }

        const varbinds = trap.varbinds ? (typeof trap.varbinds === 'string' ? JSON.parse(trap.varbinds) : trap.varbinds) : [];
        const isSuccess = trap.status === 'success' || trap.status === 'sent';

        const content = `
            <div class="trap-details-modal">
                <div class="detail-grid-modal">
                    <div class="detail-item-modal">
                        <span class="detail-label-modal">Status:</span>
                        <span class="detail-value-modal">
                            ${isSuccess ? '✅ Sent Successfully' : '❌ Failed'}
                        </span>
                    </div>
                    <div class="detail-item-modal">
                        <span class="detail-label-modal">Trap Name:</span>
                        <span class="detail-value-modal"><strong>${trap.trap_name || 'Unknown'}</strong></span>
                    </div>
                    <div class="detail-item-modal">
                        <span class="detail-label-modal">Trap OID:</span>
                        <span class="detail-value-modal"><code>${trap.trap_oid}</code></span>
                    </div>
                    <div class="detail-item-modal">
                        <span class="detail-label-modal">Target:</span>
                        <span class="detail-value-modal">${trap.target_host}:${trap.target_port}</span>
                    </div>
                    <div class="detail-item-modal">
                        <span class="detail-label-modal">Community:</span>
                        <span class="detail-value-modal">${trap.community || 'public'}</span>
                    </div>
                    <div class="detail-item-modal">
                        <span class="detail-label-modal">SNMP Version:</span>
                        <span class="detail-value-modal">${trap.snmp_version || 'v2c'}</span>
                    </div>
                    <div class="detail-item-modal">
                        <span class="detail-label-modal">Sent At:</span>
                        <span class="detail-value-modal">${this.formatDateTime(trap.sent_at)}</span>
                    </div>
                    ${trap.error_message ? `
                        <div class="detail-item-modal" style="grid-column: 1 / -1;">
                            <span class="detail-label-modal">Error:</span>
                            <span class="detail-value-modal" style="color: var(--color-danger);">${trap.error_message}</span>
                        </div>
                    ` : ''}
                </div>

                ${varbinds.length > 0 ? `
                    <div style="margin-top: var(--spacing-lg);">
                        <h4 class="subsection-title">Varbinds Sent (${varbinds.length})</h4>
                        <table class="data-table-compact">
                            <thead>
                                <tr>
                                    <th>Name (OID)</th>
                                    <th style="width: 120px;">Type</th>
                                    <th>Value</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${varbinds.map(vb => `
                                    <tr>
                                        <td>
                                            <strong>${vb.name || 'Unknown'}</strong><br>
                                            <code class="oid-compact">${vb.oid}</code>
                                        </td>
                                        <td><span class="type-badge">${vb.syntax || vb.type || 'Unknown'}</span></td>
                                        <td>${vb.value}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                ` : ''}
            </div>
        `;

        modal.show({
            title: 'Sent Trap Details',
            content: content,
            size: 'large',
            buttons: [
                {
                    text: 'Copy JSON',
                    class: 'btn-secondary',
                    onClick: () => {
                        navigator.clipboard.writeText(JSON.stringify(trap, null, 2));
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


    async loadTemplates() {
        try {
            const response = await api.get('/traps/templates');
            if (response.success) {
                this.templates = response.templates || [];
            }
        } catch (error) {
            console.error('Failed to load templates:', error);
        }
    }

    async showSaveTemplateModal() {
        if (!this.selectedNotification) {
            notify.error('Please select a notification first');
            return;
        }

        const name = await modal.prompt({
            title: 'Save Template',
            message: 'Enter template name:',
            placeholder: 'My Trap Template',
            confirmText: 'Save',
            cancelText: 'Cancel'
        });

        if (!name) return;

        try {
            window.showLoading('Saving template...');

            const varbinds = [];

            // Supported types
            const supportedTypes = [
                'Integer32', 'INTEGER', 'Counter32', 'Counter64', 'Gauge32',
                'TimeTicks', 'IpAddress', 'OctetString', 'ObjectIdentifier',
                'Opaque', 'Unsigned32', 'DisplayString'
            ];

            // Add required varbinds (convert unsupported to OctetString)
            this.notificationObjects.forEach(obj => {
                let syntax = obj.syntax || 'OctetString';
                
                // Convert unsupported types to OctetString
                if (!supportedTypes.includes(syntax)) {
                    console.warn(`Converting unsupported type ${syntax} to OctetString for ${obj.name}`);
                    syntax = 'OctetString';
                }

                varbinds.push({
                    oid: obj.oid,
                    type: syntax,
                    value: this.varbindValues[obj.name] || ''
                });
            });

            // Add additional varbinds
            this.additionalVarbinds.forEach(varbind => {
                let syntax = varbind.syntax || 'OctetString';
                
                if (!supportedTypes.includes(syntax)) {
                    console.warn(`Converting unsupported type ${syntax} to OctetString for ${varbind.name}`);
                    syntax = 'OctetString';
                }

                varbinds.push({
                    oid: varbind.oid,
                    type: syntax,
                    value: varbind.value
                });
            });

            const response = await api.post('/traps/templates', {
                name: name,
                trap_oid: this.selectedNotification.oid,
                varbinds: varbinds,
                community: this.targetConfig.community
            });

            window.hideLoading();

            if (response.success) {
                notify.success(`Template saved successfully (${varbinds.length} varbinds)`);
                this.loadTemplates();
            } else {
                throw new Error(response.message || 'Failed to save template');
            }

        } catch (error) {
            window.hideLoading();
            console.error('Save template failed:', error);
            notify.error(`Failed to save template: ${error.message}`);
        }
    }

    async showLoadTemplateModal() {
        if (this.templates.length === 0) {
            notify.info('No templates available');
            return;
        }

        const content = `
            <div class="template-list">
                ${this.templates.map(template => `
                    <div class="template-item" onclick="trapsComponent.loadTemplate(${template.id})">
                        <div>
                            <div class="template-name">${template.name}</div>
                            <div class="template-oid">${template.trap_oid}</div>
                        </div>
                        <svg class="template-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <polyline points="9 18 15 12 9 6"/>
                        </svg>
                    </div>
                `).join('')}
            </div>
        `;

        modal.show({
            title: 'Load Template',
            content: content,
            size: 'medium',
            buttons: [
                {
                    text: 'Cancel',
                    class: 'btn-secondary',
                    onClick: () => modal.close()
                }
            ]
        });
    }

    async loadTemplate(templateId) {
        modal.close();

        try {
            window.showLoading('Loading template...');

            // Get template details
            const template = this.templates.find(t => t.id === templateId);
            if (!template) {
                throw new Error('Template not found');
            }

            // Parse varbinds
            const varbinds = typeof template.varbinds === 'string' 
                ? JSON.parse(template.varbinds) 
                : template.varbinds;

            // Search for notification by OID
            const searchResponse = await api.get('/trap-builder/notifications', {
                search: template.trap_oid,
                limit: 20
            });

            if (!searchResponse.success || !searchResponse.notifications || searchResponse.notifications.length === 0) {
                throw new Error(`Notification with OID ${template.trap_oid} not found. Please sync tables first.`);
            }

            // Find exact match by OID
            const notification = searchResponse.notifications.find(n => n.oid === template.trap_oid);
            
            if (!notification) {
                throw new Error(`Notification with OID ${template.trap_oid} not found in search results.`);
            }

            // Select the notification
            await this.selectNotification(notification.name);

            // Wait for notification to load
            await new Promise(resolve => setTimeout(resolve, 500));

            // Fill varbind values
            varbinds.forEach(vb => {
                // Find matching object by OID
                const obj = this.notificationObjects.find(o => o.oid === vb.oid);
                if (obj) {
                    this.varbindValues[obj.name] = vb.value;
                    
                    // Update UI input
                    const inputs = document.querySelectorAll(`[oninput*="updateVarbindValue"]`);
                    inputs.forEach(input => {
                        if (input.getAttribute('oninput').includes(`'${obj.name}'`)) {
                            input.value = vb.value;
                        }
                    });
                }
            });

            // Update target config
            if (template.community) {
                this.targetConfig.community = template.community;
                const communityInput = document.getElementById('targetCommunity');
                if (communityInput) {
                    communityInput.value = template.community;
                }
            }

            window.hideLoading();
            notify.success(`Template "${template.name}" loaded successfully`);

        } catch (error) {
            window.hideLoading();
            console.error('Load template failed:', error);
            notify.error(`Failed to load template: ${error.message}`);
        }
    }



    updateSenderUI() {
        const selectSection = document.getElementById('selectNotificationSection');
        const selectedSection = document.getElementById('selectedNotificationSection');
        const actionsSection = document.getElementById('actionsSection');

        if (selectSection) {
            selectSection.style.display = this.selectedNotification ? 'none' : 'block';
        }
        if (selectedSection) {
            selectedSection.style.display = this.selectedNotification ? 'block' : 'none';
        }
        if (actionsSection) {
            actionsSection.style.display = this.selectedNotification ? 'block' : 'none';
        }
    }

    // ============================================
    // RECEIVER TAB
    // ============================================

    renderReceiver() {
        const container = document.getElementById('trapsContent');
        if (!container) return;

        container.innerHTML = `
            <!-- Receiver Configuration -->
            <section class="trap-section-compact">
                <div class="section-header-inline">
                    <h3>Receiver Configuration</h3>
                </div>

                <div class="receiver-config-row">
                    <div class="receiver-config-inputs">
                        <label>Port: <input type="number" id="receiverPort" class="form-input-inline" value="1162" style="width: 80px;"></label>
                        <label>Bind: <input type="text" id="receiverBind" class="form-input-inline" value="0.0.0.0" style="width: 120px;"></label>
                        <label>Community: <input type="text" id="receiverCommunity" class="form-input-inline" value="public"></label>
                    </div>
                    <div class="receiver-status-row">
                        <div id="receiverStatus" class="receiver-status-inline"></div>
                        <button class="btn btn-primary" id="startReceiverBtn">
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <polygon points="5 3 19 12 5 21 5 3"/>
                            </svg>
                            Start
                        </button>
                        <button class="btn btn-danger" id="stopReceiverBtn" style="display: none;">
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <rect x="6" y="4" width="4" height="16"/>
                                <rect x="14" y="4" width="4" height="16"/>
                            </svg>
                            Stop
                        </button>
                    </div>
                </div>
            </section>

            <!-- Received Traps -->
            <section class="trap-section-compact">
                <div class="section-header-inline">
                    <h3>Received Traps <span id="receivedTrapsCount" class="badge-compact">0</span></h3>
                    <div class="receiver-controls-inline">
                        <label class="checkbox-label-inline">
                            <input type="checkbox" id="autoRefreshToggle" checked>
                            <span>Auto</span>
                        </label>
                        <select id="refreshIntervalSelect" class="form-select-inline">
                            <option value="5000">5s</option>
                            <option value="10000" selected>10s</option>
                            <option value="15000">15s</option>
                            <option value="30000">30s</option>
                            <option value="60000">60s</option>
                        </select>
                        <button class="btn btn-sm btn-secondary" id="refreshNowBtn" title="Refresh Now">
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <polyline points="23 4 23 10 17 10"/>
                                <path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/>
                            </svg>
                        </button>
                        <button class="btn btn-sm btn-secondary" id="exportTrapsBtn" title="Export">
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                                <polyline points="7 10 12 15 17 10"/>
                                <line x1="12" y1="15" x2="12" y2="3"/>
                            </svg>
                        </button>
                        <button class="btn btn-sm btn-danger" id="clearHistoryBtn" title="Clear History">
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <polyline points="3 6 5 6 21 6"/>
                                <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                            </svg>
                        </button>
                    </div>
                </div>

                <div class="filters-row">
                    <input type="text" id="filterSourceIp" class="form-input-inline" placeholder="Filter by Source IP..." style="width: 180px;">
                    <input type="text" id="filterTrapOid" class="form-input-inline" placeholder="Filter by Trap OID..." style="width: 180px;">
                    <input type="text" id="filterTrapName" class="form-input-inline" placeholder="Filter by Trap Name..." style="width: 180px;">
                </div>

                <div id="receivedTrapsList" class="table-container-compact"></div>
            </section>
        `;

        this.setupReceiverEventListeners();
    }

    setupReceiverEventListeners() {
        // Start/Stop buttons
        const startBtn = document.getElementById('startReceiverBtn');
        const stopBtn = document.getElementById('stopReceiverBtn');

        if (startBtn) startBtn.addEventListener('click', () => this.startReceiver());
        if (stopBtn) stopBtn.addEventListener('click', () => this.stopReceiver());

        // Auto-refresh toggle
        const autoRefreshToggle = document.getElementById('autoRefreshToggle');
        if (autoRefreshToggle) {
            autoRefreshToggle.addEventListener('change', (e) => {
                this.autoRefresh = e.target.checked;
                if (this.autoRefresh) {
                    this.startAutoRefresh();
                } else {
                    this.stopAutoRefresh();
                }
            });
        }

        // Refresh interval
        const refreshIntervalSelect = document.getElementById('refreshIntervalSelect');
        if (refreshIntervalSelect) {
            refreshIntervalSelect.addEventListener('change', (e) => {
                this.refreshInterval = parseInt(e.target.value);
                if (this.autoRefresh) {
                    this.stopAutoRefresh();
                    this.startAutoRefresh();
                }
            });
        }

        // Refresh now
        const refreshNowBtn = document.getElementById('refreshNowBtn');
        if (refreshNowBtn) {
            refreshNowBtn.addEventListener('click', () => this.loadReceivedTraps());
        }

        // Filters
        const filterSourceIp = document.getElementById('filterSourceIp');
        const filterTrapOid = document.getElementById('filterTrapOid');

        if (filterSourceIp) {
            filterSourceIp.addEventListener('input', (e) => {
                this.filters.sourceIp = e.target.value;
                this.renderReceivedTraps();
            });
        }

        if (filterTrapOid) {
            filterTrapOid.addEventListener('input', (e) => {
                this.filters.trapOid = e.target.value;
                this.renderReceivedTraps();
            });
        }

        const filterTrapName = document.getElementById('filterTrapName');
        if (filterTrapName) {
            filterTrapName.addEventListener('input', (e) => {
                this.filters.trapName = e.target.value;
                this.renderReceivedTraps();
            });
        }

        // Export
        const exportBtn = document.getElementById('exportTrapsBtn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportTraps());
        }

        // Clear history
        const clearBtn = document.getElementById('clearHistoryBtn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearReceivedHistory());
        }
    }


    async loadReceiverStatus() {
        try {
            const response = await api.get('/traps/receiver/status');

            // Handle different response structures
            if (response) {
                if (response.success !== undefined) {
                    // Response has success field
                    this.receiverStatus = {
                        running: response.running || false,
                        port: response.port || 1162,
                        bind_address: response.bind_address || '0.0.0.0',
                        community: response.community || 'public'
                    };
                } else if (response.status) {
                    // Response has nested status
                    this.receiverStatus = response.status;
                } else {
                    // Response is the status itself
                    this.receiverStatus = response;
                }
                
                this.renderReceiverStatus();
            }
        } catch (error) {
            console.error('Failed to load receiver status:', error);
            // Set default status on error
            this.receiverStatus = { running: false, port: 1162, bind_address: '0.0.0.0' };
            this.renderReceiverStatus();
        }
    }


    renderReceiverStatus() {
        const container = document.getElementById('receiverStatus');
        if (!container) return;

        const isRunning = this.receiverStatus.running;

        container.innerHTML = `
            <div class="status-dot-inline ${isRunning ? 'running' : 'stopped'}"></div>
            <span class="status-text-inline">
                ${isRunning 
                    ? `Running (${this.receiverStatus.bind_address}:${this.receiverStatus.port})`
                    : 'Stopped'
                }
            </span>
        `;

        // Toggle buttons
        const startBtn = document.getElementById('startReceiverBtn');
        const stopBtn = document.getElementById('stopReceiverBtn');

        if (startBtn) startBtn.style.display = isRunning ? 'none' : 'inline-flex';
        if (stopBtn) stopBtn.style.display = isRunning ? 'inline-flex' : 'none';
    }

    async startReceiver() {
        const port = parseInt(document.getElementById('receiverPort').value);
        const bindAddress = document.getElementById('receiverBind').value;
        const community = document.getElementById('receiverCommunity').value;

        try {
            window.showLoading('Starting receiver...');

            const response = await api.post('/traps/receiver/start', {
                port: port,
                bind_address: bindAddress,
                community: community
            });

            window.hideLoading();

            // Check if response has success field
            if (response && response.success) {
                notify.success('✅ Receiver started successfully');
                
                // Update status immediately
                this.receiverStatus = {
                    running: true,
                    port: response.port || port,
                    bind_address: response.bind_address || bindAddress,
                    community: community
                };
                
                this.renderReceiverStatus();
                this.loadReceivedTraps();
                
                if (this.autoRefresh) {
                    this.startAutoRefresh();
                }
            } else {
                throw new Error(response.message || 'Failed to start receiver');
            }

        } catch (error) {
            window.hideLoading();
            console.error('Start receiver failed:', error);
            notify.error(`Failed to start receiver: ${error.message}`);
        }
    }


    async stopReceiver() {
        try {
            window.showLoading('Stopping receiver...');

            const response = await api.post('/traps/receiver/stop');

            window.hideLoading();

            if (response.success) {
                notify.success('⏸️ Receiver stopped');
                this.loadReceiverStatus();
                this.stopAutoRefresh();
            } else {
                throw new Error(response.message || 'Failed to stop receiver');
            }

        } catch (error) {
            window.hideLoading();
            console.error('Stop receiver failed:', error);
            notify.error(`Failed to stop receiver: ${error.message}`);
        }
    }

    async loadReceivedTraps() {
        try {
            const response = await api.get('/traps/received', { limit: 50, offset: 0 });

            if (response.success) {
                this.receivedTraps = response.traps || [];
                this.renderReceivedTraps();
            }
        } catch (error) {
            console.error('Failed to load received traps:', error);
        }
    }

    renderReceivedTraps() {
        const container = document.getElementById('receivedTrapsList');
        const countBadge = document.getElementById('receivedTrapsCount');

        if (!container) return;

        // Apply filters
        let filteredTraps = this.receivedTraps;

        if (this.filters.sourceIp) {
            filteredTraps = filteredTraps.filter(trap => 
                trap.source_ip.includes(this.filters.sourceIp)
            );
        }

        if (this.filters.trapOid) {
            filteredTraps = filteredTraps.filter(trap => 
                trap.trap_oid.includes(this.filters.trapOid)
            );
        }

        if (this.filters.trapName) {
            filteredTraps = filteredTraps.filter(trap => 
                (trap.trap_name || '').toLowerCase().includes(this.filters.trapName.toLowerCase())
            );
        }

        if (countBadge) {
            countBadge.textContent = filteredTraps.length;
        }

        if (filteredTraps.length === 0) {
            container.innerHTML = `
                <div class="empty-state-compact">
                    <p>No traps received yet</p>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <table class="data-table-compact">
                <thead>
                    <tr>
                        <th>Trap Name</th>
                        <th>Description</th>
                        <th style="width: 150px; text-align: center">Source IP</th>
                        <th style="width: 80px; text-align: center;">Varbinds</th>
                        <th style="width: 150px; text-align: center">Received</th>
                        <th style="width: 100px; text-align: center;">Action</th>
                    </tr>
                </thead>
                <tbody>
                    ${filteredTraps.map(trap => `
                        <tr class="table-row-hover">
                            <td><strong>${trap.trap_name || 'Unknown'}</strong></td>
                            <td>
                                <span class="text-truncate" title="${this.escapeHtml(trap.trap_description || 'No description')}">
                                    ${this.truncateText(trap.trap_description || 'No description', 60)}
                                </span>
                            </td>
                            <td>${trap.source_ip}:${trap.source_port}</td>
                            <td style="text-align: center;">
                                <span class="badge-compact">${(trap.varbinds || []).length}</span>
                            </td>
                            <td>${this.formatRelativeTime(trap.received_at)}</td>
                            <td style="text-align: right;">
                                <button class="btn btn-sm btn-secondary" onclick="trapsComponent.showReceivedTrapDetails(${trap.id})">
                                    Details
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    showReceivedTrapDetails(trapId) {
        const trap = this.receivedTraps.find(t => t.id === trapId);
        if (!trap) {
            notify.error('Trap not found');
            return;
        }

        const varbinds = trap.varbinds || [];

        const content = `
            <div class="trap-details-modal">
                <div class="detail-grid-modal">
                    <div class="detail-item-modal">
                        <span class="detail-label-modal">Trap Name:</span>
                        <span class="detail-value-modal"><strong>${trap.trap_name || 'Unknown'}</strong></span>
                    </div>
                    <div class="detail-item-modal">
                        <span class="detail-label-modal">OID:</span>
                        <span class="detail-value-modal"><code>${trap.trap_oid}</code></span>
                    </div>
                    <div class="detail-item-modal">
                        <span class="detail-label-modal">Module:</span>
                        <span class="detail-value-modal">${trap.trap_description || 'Unknown'}</span>
                    </div>
                    <div class="detail-item-modal">
                        <span class="detail-label-modal">Source:</span>
                        <span class="detail-value-modal">${trap.source_ip}:${trap.source_port}</span>
                    </div>
                    <div class="detail-item-modal">
                        <span class="detail-label-modal">Received:</span>
                        <span class="detail-value-modal">${this.formatDateTime(trap.received_at)}</span>
                    </div>
                    <div class="detail-item-modal">
                        <span class="detail-label-modal">Community:</span>
                        <span class="detail-value-modal">${trap.community || 'public'}</span>
                    </div>
                    <div class="detail-item-modal">
                        <span class="detail-label-modal">SNMP Version:</span>
                        <span class="detail-value-modal">${trap.snmp_version || 'v2c'}</span>
                    </div>
                </div>

                ${varbinds.length > 0 ? `
                    <div style="margin-top: var(--spacing-lg);">
                        <h4 class="subsection-title">Varbinds (${varbinds.length})</h4>
                        <table class="data-table-compact">
                            <thead>
                                <tr>
                                    <th>Name (OID)</th>
                                    <th style="width: 120px;">Type</th>
                                    <th>Value</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${varbinds.map(vb => `
                                    <tr>
                                        <td>
                                            <strong>${vb.name || vb.oid}</strong><br>
                                            <code class="oid-compact">${vb.oid}</code>
                                        </td>
                                        <td><span class="type-badge">${vb.type || 'Unknown'}</span></td>
                                        <td>${vb.value}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                ` : `
                    <div style="margin-top: var(--spacing-lg); text-align: center; color: var(--color-text-secondary);">
                        No additional varbinds
                    </div>
                `}
            </div>
        `;

        modal.show({
            title: 'Received Trap Details',
            content: content,
            size: 'large',
            buttons: [
                {
                    text: 'Copy JSON',
                    class: 'btn-secondary',
                    onClick: () => {
                        navigator.clipboard.writeText(JSON.stringify(trap, null, 2));
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

    async exportTraps() {
        if (this.receivedTraps.length === 0) {
            notify.warning('No traps to export');
            return;
        }

        try {
            // Create JSON export
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-').split('T')[0];
            const filename = `received_traps_${timestamp}.json`;

            // Export full trap data
            const exportData = this.receivedTraps.map(trap => ({
                id: trap.id,
                source_ip: trap.source_ip,
                source_port: trap.source_port,
                trap_oid: trap.trap_oid,
                trap_name: trap.trap_name,
                trap_description: trap.trap_description,
                enterprise_oid: trap.enterprise_oid,
                timestamp: trap.timestamp,
                varbinds: trap.varbinds || [],
                snmp_version: trap.snmp_version,
                community: trap.community,
                raw_data: trap.raw_data,
                received_at: trap.received_at
            }));

            // Create blob and download
            const json = JSON.stringify(exportData, null, 2);
            const blob = new Blob([json], { type: 'application/json' });
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = filename;
            link.click();
            window.URL.revokeObjectURL(url);

            notify.success(`Exported ${exportData.length} traps to ${filename}`);

        } catch (error) {
            console.error('Export failed:', error);
            notify.error(`Export failed: ${error.message}`);
        }
    }

    async exportFromDatabase(tableName, database = 'traps') {
        try {
            await window.exportService.export({
                source: 'table',
                name: tableName,
                database: database,
                format: 'csv',
                filename: `${tableName}_${new Date().toISOString().split('T')[0]}.csv`
            });
        } catch (error) {
            console.error('Export failed:', error);
            notify.error(`Export failed: ${error.message}`);
        }
    }


    async clearReceivedHistory() {
        const confirmed = await modal.confirm({
            title: 'Clear History',
            message: 'Are you sure you want to clear all received traps? This action cannot be undone.',
            confirmText: 'Clear All',
            cancelText: 'Cancel',
            danger: true
        });

        if (!confirmed) return;

        try {
            window.showLoading('Clearing history...');

            const response = await api.delete('/traps/received');

            window.hideLoading();

            if (response.success) {
                notify.success('History cleared');
                this.receivedTraps = [];
                this.renderReceivedTraps();
            } else {
                throw new Error(response.message || 'Failed to clear history');
            }

        } catch (error) {
            window.hideLoading();
            console.error('Clear history failed:', error);
            notify.error(`Failed to clear history: ${error.message}`);
        }
    }

    startAutoRefresh() {
        this.stopAutoRefresh();
        this.autoRefreshTimer = setInterval(() => {
            this.loadReceivedTraps();
        }, this.refreshInterval);
    }

    stopAutoRefresh() {
        if (this.autoRefreshTimer) {
            clearInterval(this.autoRefreshTimer);
            this.autoRefreshTimer = null;
        }
    }

    // ============================================
    // UTILITIES
    // ============================================

    formatRelativeTime(timestamp) {
        if (!timestamp) return 'Unknown';
        
        const now = new Date();
        const then = new Date(timestamp);
        const diffMs = now - then;
        const diffSec = Math.floor(diffMs / 1000);
        const diffMin = Math.floor(diffSec / 60);
        const diffHour = Math.floor(diffMin / 60);
        const diffDay = Math.floor(diffHour / 24);

        if (diffSec < 60) return `${diffSec}s ago`;
        if (diffMin < 60) return `${diffMin}m ago`;
        if (diffHour < 24) return `${diffHour}h ago`;
        return `${diffDay}d ago`;
    }

    formatDateTime(timestamp) {
        if (!timestamp) return 'Unknown';
        const date = new Date(timestamp);
        return date.toLocaleString();
    }

    truncateText(text, maxLength) {
        if (!text) return '';
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    destroy() {
        this.stopAutoRefresh();
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.trapsComponent = new TrapsComponent();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.trapsComponent) {
        window.trapsComponent.destroy();
    }
});
