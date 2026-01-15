/* ============================================
   Database Component V3 - WITH SYNC INTEGRATION
   Handles user data tables (mib_tool) + Master Sync
   ============================================ */

class DatabaseComponent {
    constructor() {
        this.tables = [];
        this.currentTable = null;
        this.dataTable = null;
        this.currentPage = 1;
        this.pageSize = 1000;
        this.totalRecords = 0;
        this.expandedTables = new Set();
        this.queryBuilderVisible = false;
        this.eventListeners = [];
        this.initialized = false;
        
        // ✅ NEW: Sync status tracking
        this.syncStatusMap = {};

        this.syncWebsockets = new Map();  // table_name -> WebSocket
        this.syncAllWebsocket = null;
        
        this.setupEventListeners();
    }

    /**
     * Initialize database component (call only when needed)
     */
    async init() {
        if (this.initialized) return;
        
        await this.loadTables();
        this.initialized = true;
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        const addTrackedListener = (element, event, handler) => {
            if (element) {
                element.addEventListener(event, handler);
                this.eventListeners.push({ element, event, handler });
            }
        };

        const importDataBtn = document.getElementById('importDataBtn');
        if (importDataBtn) {
            importDataBtn.addEventListener('click', () => {
                this.showImportModal(null);
            });
        }

        // ✅ NEW: Sync action buttons
        const syncAllBtn = document.getElementById('syncAllTablesBtn');
        addTrackedListener(syncAllBtn, 'click', () => {
            this.syncAllTables();
        });

        const masterStatsBtn = document.getElementById('viewMasterStatsBtn');
        addTrackedListener(masterStatsBtn, 'click', () => {
            this.showMasterStats();
        });

        const refreshBtn = document.getElementById('refreshTablesBtn');
        addTrackedListener(refreshBtn, 'click', () => {
            this.loadTables();
        });

        // SQL Query Runner listeners
        const executeQueryBtn = document.getElementById('executeQueryBtn');
        addTrackedListener(executeQueryBtn, 'click', () => {
            this.executeQuery();
        });

        const clearQueryBtn = document.getElementById('clearQueryBtn');
        addTrackedListener(clearQueryBtn, 'click', () => {
            this.clearQuery();
        });

        const toggleQueryBuilder = document.getElementById('toggleQueryBuilder');
        addTrackedListener(toggleQueryBuilder, 'click', () => {
            this.toggleQueryBuilder();
        });

        const buildQueryBtn = document.getElementById('buildQueryBtn');
        addTrackedListener(buildQueryBtn, 'click', () => {
            this.buildQuery();
        });

        const clearQueryBuilderBtn = document.getElementById('clearQueryBuilderBtn');
        addTrackedListener(clearQueryBuilderBtn, 'click', () => {
            this.clearQueryBuilder();
        });

        const queryInput = document.getElementById('sqlQueryInput');
        if (queryInput) {
            const keyHandler = (e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                    e.preventDefault();
                    this.executeQuery();
                }
            };
            addTrackedListener(queryInput, 'keydown', keyHandler);
        }
    }

    /**
     * Toggle table expansion
     */
    toggleTableExpansion(tableName) {
        if (this.expandedTables.has(tableName)) {
            this.expandedTables.delete(tableName);
        } else {
            this.expandedTables.add(tableName);
        }
        this.displayTables();
    }

    /**
     * ✅ NEW: Load sync status for all tables
     */
    async loadSyncStatus() {
        try {
            const response = await api.get('/trap-sync/sync/tables');
            
            if (response && response.success) {
                this.syncStatusMap = {};
                response.tables.forEach(table => {
                    this.syncStatusMap[table.table_name] = {
                        status: table.sync_status,
                        lastSync: table.last_sync_at,
                        rowsSynced: table.rows_synced,
                        notificationsCount: table.notifications_count
                    };
                });
            }
        } catch (error) {
            console.error('Failed to load sync status:', error);
        }
    }

    /**
     * ✅ UPDATED: Load tables from database + sync status
     */
    async loadTables() {
        try {
            window.showLoading('Loading tables...');
            
            // Load both tables and sync status in parallel
            const [tables, _] = await Promise.all([
                api.database.listTables(),
                this.loadSyncStatus()
            ]);
            
            window.hideLoading();

            this.tables = tables;
            this.displayTables();

            // ✅ NEW: Connect WebSocket for active syncs
            this.connectActiveSyncWebSockets();

            if (tables.length === 0) {
                console.log('No tables found in database');
            }
        } catch (error) {
            window.hideLoading();
            notify.error(`Failed to load tables: ${error.message}`);
            console.error('Load tables error:', error);
        }
    }

    /**
     * ✅ UPDATED: Display tables (list view only, removed card view)
     */
    displayTables() {
        const tablesGrid = document.getElementById('tablesList');
        if (!tablesGrid) return;

        if (this.tables.length === 0) {
            tablesGrid.innerHTML = `
                <div class="empty-state">
                    <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
                        <polyline points="9 22 9 12 15 12 15 22"/>
                    </svg>
                    <p class="empty-message">No tables found</p>
                    <p style="color: var(--color-text-secondary); font-size: 0.875rem; margin-top: var(--spacing-sm);">
                        Parse and save MIB files to create database tables
                    </p>
                </div>
            `;
            return;
        }

        // Always render list view
        tablesGrid.className = 'tables-list';
        tablesGrid.innerHTML = this.tables
            .map((table) => this.renderTableListItem(table))
            .join('');
        
    }

    /**
     * ✅ UPDATED: Render table as list item (with sync status)
     */
    renderTableListItem(table) {
        const isExpanded = this.expandedTables.has(table.name);
        
        // ✅ NEW: Check if this is the master table
        const isMasterTable = table.name === 'trap_master_data';
        
        // Get sync status for this table (skip for master table)
        const syncInfo = !isMasterTable ? this.syncStatusMap[table.name] : null;
        const isSynced = syncInfo && syncInfo.status === 'completed';
        const syncStatus = syncInfo ? syncInfo.status : 'never';
        
        // ✅ UPDATED: Determine badge style (skip for master table)
        let statusBadge = '';
        if (!isMasterTable) {
            if (syncStatus === 'completed') {
                statusBadge = '<span class="badge-compact" style="background: var(--color-success-light); color: var(--color-success);">✓ Synced</span>';
            } else if (syncStatus === 'pending') {
                statusBadge = '<span class="badge-compact" style="background: var(--color-info-light); color: var(--color-info);">⏳ Syncing...</span>';
            } else if (syncStatus === 'failed') {
                statusBadge = '<span class="badge-compact" style="background: var(--color-danger-light); color: var(--color-danger);">✗ Failed</span>';
            } else {
                statusBadge = '<span class="badge-compact" style="background: var(--color-warning-light); color: var(--color-warning);">Not Synced</span>';
            }
        }

        return `
            <div class="table-list-item" data-table="${table.name}">
                <div class="table-list-header">
                    <div class="table-list-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
                        </svg>
                    </div>
                    <div class="table-list-info">
                        <span class="table-list-name">${table.name}</span>
                        <span class="table-list-meta">
                            ${Utils.formatNumber(table.row_count)} rows • ${table.size_mb.toFixed(2)} MB
                            ${syncInfo && syncInfo.lastSync ? ` • Synced ${Utils.formatRelativeTime(syncInfo.lastSync)}` : ''}
                        </span>
                    </div>
                    
                    <!-- ✅ UPDATED: Sync Status Badge (only for non-master tables) -->
                    ${!isMasterTable ? `
                        <div class="table-list-sync-status">
                            ${statusBadge}
                        </div>
                    ` : ''}
                    
                    <div class="table-list-actions">
                        <!-- ✅ UPDATED: Sync button (only for non-master tables, not synced, not pending) -->
                        ${!isMasterTable && !isSynced && syncStatus !== 'pending' ? `
                            <button class="btn btn-sm btn-secondary" onclick="databaseComponent.syncTable('${table.name}'); event.stopPropagation();" title="Sync to Master">
                                <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <polyline points="23 4 23 10 17 10"/>
                                    <path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/>
                                </svg>
                                Sync
                            </button>
                        ` : ''}
                        
                        <button class="btn btn-sm btn-primary" onclick="databaseComponent.loadTableData('${table.name}'); event.stopPropagation();" title="View Data">
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                <circle cx="12" cy="12" r="3"/>
                            </svg>
                            View
                        </button>
                        <button class="btn btn-sm btn-secondary" onclick="databaseComponent.exportTable('${table.name}'); event.stopPropagation();">
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                                <polyline points="7 10 12 15 17 10"/>
                                <line x1="12" y1="15" x2="12" y2="3"/>
                            </svg>
                            Export
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="databaseComponent.deleteTable('${table.name}'); event.stopPropagation();">
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <polyline points="3 6 5 6 21 6"/>
                                <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                            </svg>
                            Delete
                        </button>
                        <button class="btn btn-sm btn-icon table-expand-btn" onclick="databaseComponent.toggleTableExpansion('${table.name}'); event.stopPropagation();" title="${isExpanded ? 'Collapse' : 'Expand'}">
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" style="transform: rotate(${isExpanded ? '180' : '0'}deg); transition: transform 0.3s;">
                                <polyline points="6 9 12 15 18 9"/>
                            </svg>
                        </button>
                    </div>
                </div>
                ${
                    isExpanded
                        ? `
                    <div class="table-list-details">
                        <div class="detail-grid">
                            <div class="detail-item">
                                <span class="detail-label">Table Name</span>
                                <span class="detail-value"><code>${table.name}</code></span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Total Rows</span>
                                <span class="detail-value">${Utils.formatNumber(table.row_count)}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Size</span>
                                <span class="detail-value">${table.size_mb.toFixed(2)} MB</span>
                            </div>
                            
                            ${!isMasterTable && syncInfo ? `
                                <div class="detail-item">
                                    <span class="detail-label">Sync Status</span>
                                    <span class="detail-value">${statusBadge}</span>
                                </div>
                                ${syncInfo.lastSync ? `
                                    <div class="detail-item">
                                        <span class="detail-label">Last Synced</span>
                                        <span class="detail-value">${Utils.formatDateTime(syncInfo.lastSync)}</span>
                                    </div>
                                ` : ''}
                                ${syncInfo.rowsSynced ? `
                                    <div class="detail-item">
                                        <span class="detail-label">Rows Synced</span>
                                        <span class="detail-value">${Utils.formatNumber(syncInfo.rowsSynced)}</span>
                                    </div>
                                ` : ''}
                            ` : ''}
                            
                            ${
                                table.created
                                    ? `
                                <div class="detail-item">
                                    <span class="detail-label">Created</span>
                                    <span class="detail-value">${Utils.formatDateTime(table.created)}</span>
                                </div>
                            `
                                    : ''
                            }
                            ${
                                table.updated
                                    ? `
                                <div class="detail-item">
                                    <span class="detail-label">Last Updated</span>
                                    <span class="detail-value">${Utils.formatDateTime(table.updated)}</span>
                                </div>
                            `
                                    : ''
                            }
                            ${
                                table.columns && table.columns.length > 0
                                    ? `
                                <div class="detail-item">
                                    <span class="detail-label">Columns</span>
                                    <span class="detail-value">${table.columns.length}</span>
                                </div>
                            `
                                    : ''
                            }
                        </div>
                    </div>
                `
                        : ''
                }
            </div>
        `;
    }

    // ============================================
    // SYNC OPERATIONS
    // ============================================
    
    /**
     * Sync single table
     */
    async syncTable(tableName) {
        try {
            this.connectSyncWebSocket(tableName);

            // ✅ Show initial progress bar instead
            this.showSyncProgressBar(tableName, 0, 'Starting sync...');
            
            const response = await api.post('/trap-sync/sync/table', {
                table_name: tableName,
                // strategy: 'append',
                // force_full: false
            });
            
            if (response && response.success) {
                // await this.loadTables();

            } else {
                throw new Error(response.message || 'Sync failed');
            }
        } catch (error) {
            console.error('Sync table failed:', error);
            notify.error(`Sync failed: ${error.message}`);
            this.hideSyncProgressBar(tableName);
            this.disconnectSyncWebSocket(tableName);
        }
    }
    
    /**
     * ✅ UPDATED: Sync all tables with results modal
     */
    async syncAllTables() {
        const confirmed = await modal.confirm({
            title: 'Sync All Tables',
            message: 'This will sync all user MIB tables to the master trap database. Continue?',
            confirmText: 'Sync All',
            cancelText: 'Cancel'
        });

        if (!confirmed) return;

        try {
            this.connectSyncAllWebSocket();
            // notify.info('Starting sync for all tables...');
            
            const response = await api.post('/trap-sync/sync/all', {
                // strategy: 'append'
            });
            
            if (response && response.success) {
                // ✅ Show detailed results in modal
                this.showSyncResults(response);
                
                // Also show quick notification
                const stats = response.overall_stats || {};

                const total_duration = response.total_duration.toFixed(2);

                if (response.tables_skipped > 0){
                    const message = `✅ Synced ${response.tables_synced} tables (${response.tables_skipped} skipped): ${Utils.formatNumber(stats.total_rows_inserted)} inserted, ${Utils.formatNumber(stats.total_rows_updated)} updated, ${Utils.formatNumber(stats.total_rows_skipped)} skipped (${total_duration}s)`
                    notify.success(message);
                } else {
                    const message = `✅ Synced ${response.tables_synced} tables: ${Utils.formatNumber(stats.total_rows_inserted)} inserted, ${Utils.formatNumber(stats.total_rows_updated)} updated, ${Utils.formatNumber(stats.total_rows_)} skipped (${total_duration}s)`
                    notify.success(message);
                }
                
                // await this.loadTables();

            } else {
                throw new Error(response.message || 'Sync failed');
            }
        } catch (error) {
            console.error('Sync all failed:', error);
            notify.error(`Sync failed: ${error.message}`);
            this.disconnectSyncAllWebSocket();
        }
    }

    /**
     * ✅ UPDATED: Show detailed sync results using CSS classes
     */
    showSyncResults(response) {
        const { tables_synced, tables_failed, tables_skipped, overall_stats, results, total_duration } = response;
        
        // Format total duration
        const durationText = total_duration 
            ? `${total_duration.toFixed(2)}s` 
            : results.reduce((sum, r) => sum + (r.duration || 0), 0).toFixed(2) + 's';
        
        // ✅ FIX: results is already an array, not results.stats
        const tableResults = results || [];
        
        // Create detailed results HTML with CSS classes
        const html = `
            <div class="sync-results">
                <div class="sync-summary">
                    <div class="stat">
                        <span class="label">Tables Synced</span>
                        <span class="value">${tables_synced}</span>
                    </div>
                    
                    ${tables_failed > 0 ? `
                    <div class="stat error">
                        <span class="label">Tables Failed</span>
                        <span class="value">${tables_failed}</span>
                    </div>
                    ` : ''}
                    
                    ${tables_skipped > 0 ? `
                    <div class="stat warning">
                        <span class="label">Tables Skipped</span>
                        <span class="value">${tables_skipped}</span>
                    </div>
                    ` : ''}
                    
                    <div class="stat duration">
                        <span class="label">Total Duration</span>
                        <span class="value">${durationText}</span>
                    </div>
                </div>
                
                <div class="sync-stats">
                    <h4>Overall Statistics</h4>
                    <table>
                        <tbody>
                            <tr>
                                <td>Inserted:</td>
                                <td class="stat-inserted">${Utils.formatNumber(overall_stats.total_rows_inserted || 0)}</td>
                            </tr>
                            <tr>
                                <td>Updated:</td>
                                <td class="stat-updated">${Utils.formatNumber(overall_stats.total_rows_updated || 0)}</td>
                            </tr>
                            <tr>
                                <td>Skipped:</td>
                                <td class="stat-skipped">${Utils.formatNumber(overall_stats.total_rows_skipped || 0)}</td>
                            </tr>
                            <tr class="total">
                                <td>Total Processed:</td>
                                <td>${Utils.formatNumber(
                                    (overall_stats.total_rows_inserted || 0) + 
                                    (overall_stats.total_rows_updated || 0) + 
                                    (overall_stats.total_rows_skipped || 0)
                                )}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                
                <details class="sync-details">
                    <summary>Per-Table Results (${tableResults.length} tables)</summary>
                    <div class="results-table-container">
                        <table class="results-table">
                            <thead>
                                <tr>
                                    <th>Table</th>
                                    <th>Inserted</th>
                                    <th>Updated</th>
                                    <th>Skipped</th>
                                    <th>Duration</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${tableResults.map(r => {
                                    const stats = r.stats || r;
                                    const inserted = stats.rows_inserted || 0;
                                    const updated = stats.rows_updated || 0;
                                    const skipped = stats.rows_skipped || 0;
                                    
                                    // ✅ Show different icon for skipped tables
                                    const icon = r.skipped ? '⏭️' : (r.success ? '✅' : '❌');
                                    const reason = r.skipped ? ` (${r.reason})` : '';
                                    
                                    return `
                                        <tr>
                                            <td>${icon} ${r.table_name}${reason}</td>
                                            <td class="stat-inserted">${Utils.formatNumber(inserted)}</td>
                                            <td class="stat-updated">${Utils.formatNumber(updated)}</td>
                                            <td class="stat-skipped">${Utils.formatNumber(skipped)}</td>
                                            <td>${(r.duration || 0).toFixed(2)}s</td>
                                        </tr>
                                    `;
                                }).join('')}
                            </tbody>

                        </table>
                    </div>
                </details>
            </div>
        `;
        
        // Use modal.show() without close button in buttons array
        modal.show({
            title: 'Sync All Results',
            content: html,
            size: 'large',
            buttons: []  // No buttons - use X button to close
        });
    }

    /**
     * Update sync progress in UI (optional)
     */
    updateSyncProgress(tableName, progress) {
        const tableRow = document.querySelector(`[data-table="${tableName}"]`);
        if (!tableRow) return;
        
        let progressIndicator = tableRow.querySelector('.sync-progress-indicator');
        
        if (!progressIndicator) {
            const syncStatusDiv = tableRow.querySelector('.table-list-sync-status');
            if (syncStatusDiv) {
                progressIndicator = document.createElement('div');
                progressIndicator.className = 'sync-progress-indicator';
                progressIndicator.style.cssText = `
                    font-size: 0.75rem;
                    color: var(--color-info);
                    margin-top: 0.25rem;
                `;
                syncStatusDiv.appendChild(progressIndicator);
            }
        }
        
        if (progressIndicator) {
            progressIndicator.textContent = `${Math.round(progress)}%`;
        }
    }

    /**
     * ✅ NEW: Show master table statistics modal
     */
    async showMasterStats() {
        try {
            window.showLoading('Loading master stats...');
            
            const response = await api.get('/trap-sync/master/stats');
            
            window.hideLoading();
            
            if (!response || !response.success) {
                throw new Error('Failed to load master stats');
            }
            
            const stats = response;
            
            const content = `
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--spacing-md);">
                    <div class="stat-card-compact">
                        <div class="stat-value-compact">${Utils.formatNumber(stats.total_notifications)}</div>
                        <div class="stat-label-compact">Notifications</div>
                    </div>
                    <div class="stat-card-compact">
                        <div class="stat-value-compact">${Utils.formatNumber(stats.total_objects)}</div>
                        <div class="stat-label-compact">Objects</div>
                    </div>
                    <div class="stat-card-compact">
                        <div class="stat-value-compact">${stats.modules}</div>
                        <div class="stat-label-compact">Modules</div>
                    </div>
                    <div class="stat-card-compact">
                        <div class="stat-value-compact">${stats.source_tables}</div>
                        <div class="stat-label-compact">Source Tables</div>
                    </div>
                    <div class="stat-card-compact">
                        <div class="stat-value-compact">${Utils.formatNumber(stats.total_rows)}</div>
                        <div class="stat-label-compact">Total Rows</div>
                    </div>
                    <div class="stat-card-compact">
                        <div class="stat-value-compact">${stats.size_mb.toFixed(2)} MB</div>
                        <div class="stat-label-compact">Database Size</div>
                    </div>
                </div>
                
                <div style="margin-top: var(--spacing-lg); padding: var(--spacing-md); background: var(--color-surface); border-radius: var(--radius-md);">
                    <div style="display: grid; grid-template-columns: 150px 1fr; gap: var(--spacing-sm); font-size: var(--font-size-sm);">
                        <div style="color: var(--color-text-secondary);">Created:</div>
                        <div>${Utils.formatDateTime(stats.created)}</div>
                        
                        <div style="color: var(--color-text-secondary);">Last Updated:</div>
                        <div>${Utils.formatDateTime(stats.updated)}</div>
                    </div>
                </div>
            `;
            
            modal.show({
                title: 'Master Table Statistics',
                content: content,
                size: 'medium',
                buttons: [
                    {
                        text: 'Close',
                        class: 'btn-primary',
                        onClick: () => modal.close()
                    }
                ]
            });
            
        } catch (error) {
            window.hideLoading();
            console.error('Failed to load master stats:', error);
            notify.error(`Failed to load stats: ${error.message}`);
        }
    }

    /**
     * Export table (from table list)
     */
    exportTable(tableName) {
        const table = this.tables.find((t) => t.name === tableName);
        const recordCount = table ? table.row_count : 0;

        if (window.exportComponent) {
            window.exportComponent.showExportModal(
                'table',
                tableName,
                recordCount
            );
        } else {
            window.exportService.export({
                source: 'table',
                name: tableName,
                format: 'csv',
            });
        }
    }

    /**
     * Handle export with correct table reference
     */
    handleExport(data) {
        if (!this.currentTable) {
            notify.warning('No table loaded');
            return;
        }

        const backendFilters =
            this.currentTable.filters && this.currentTable.filters.length > 0
                ? window.filterService.convertToBackend(this.currentTable.filters)
                : null;

        const exportCount = this.currentTable.data.length;

        if (window.exportComponent) {
            window.exportComponent.showExportModal(
                'table',
                this.currentTable.name,
                exportCount,
                {
                    database: 'data',
                    filters: backendFilters,
                    columns: this.dataTable?.state?.visibleColumns || [],
                    limit: exportCount
                }
            );
        }
    }

    /**
     * Handle analyze
     */
    async handleAnalyze(data) {
        if (!data || data.length === 0) {
            notify.warning('No data to analyze');
            return;
        }

        await window.analyzerService.analyze(data, {
            source: 'table',
            name: this.currentTable?.name || 'Unknown Table',
            showModal: true,
        });
    }

    /**
     * Delete table (helper method for list view)
     */
    async deleteTable(tableName) {
        const confirmed = await modal.confirmWithInput({
            title: 'Delete Table',
            message: `You are about to permanently delete table <strong>"${tableName}"</strong>. This action cannot be undone.`,
            inputLabel: 'Type DELETE to confirm:',
            expectedValue: 'DELETE',
            confirmText: 'Delete Table',
            cancelText: 'Cancel',
            danger: true,
        });

        if (!confirmed) return;

        try {
            window.showLoading(`Deleting table: ${tableName}...`);
            await api.database.deleteTable(tableName);
            window.hideLoading();
            notify.success(`Table "${tableName}" deleted successfully`);
            this.loadTables();
        } catch (error) {
            window.hideLoading();
            notify.error(`Failed to delete table: ${error.message}`);
            console.error('Delete table error:', error);
        }
    }

    /**
     * Load table data using SQL query
     */
    async loadTableData(tableName, page = 1, filters = []) {
        try {
            window.showLoading(`Loading table: ${tableName}...`);

            const fetchLimit = (this.dataTable ? this.dataTable.state.dbLimit : this.pageSize);
            const offset = (page - 1) * fetchLimit;

            const sql = window.filterService.buildSQLQuery(tableName, filters, {
                columns: ['*'],
                limit: fetchLimit,
                offset: offset,
                orderBy: 'notification_name ASC',
            });

            const whereClause = window.filterService.extractWhereClause(sql);
            const orderByClause = window.filterService.extractOrderBy(sql);

            const result = await api.database.query({
                table: tableName,
                database: 'data',
                columns: ['*'],
                where: whereClause,
                order_by: orderByClause,
                limit: fetchLimit,
                offset: offset,
            });

            window.hideLoading();

            if (!result.success) {
                throw new Error('Failed to load table data');
            }

            this.currentTable = {
                name: tableName,
                data: result.data,
                total: result.total,
                filters: filters,
            };

            this.currentPage = page;
            this.totalRecords = result.total;

            this.displayTableData();

        } catch (error) {
            window.hideLoading();
            notify.error(`Failed to load table: ${error.message}`);
            console.error('Load table data error:', error);
        }
    }

    /**
     * Display table data
     */
    displayTableData() {
        const tablesSection = document.querySelector('.tables-section');
        const tableDataSection = document.getElementById('tableDataSection');

        if (tablesSection) tablesSection.style.display = 'block';
        if (tableDataSection) {
            tableDataSection.style.display = 'block';
            setTimeout(() => {
                tableDataSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 100);
        }

        const tableNameHeader = document.getElementById('currentTableName');
        if (tableNameHeader) {
            tableNameHeader.textContent = this.currentTable.name;
        }

        if (this.dataTable) {
            const existingTableName = this.dataTable.options.tableName;

            if (existingTableName === this.currentTable.name) {
                this.dataTable.setData(this.currentTable.data, this.currentTable.total);
                return;
            } else {
                this.dataTable.destroy();
                this.dataTable = null;
            }
        }

        this.dataTable = new UnifiedDataTable('databaseDataTable', {
            title: `Table: ${this.currentTable.name}`,
            tableName: this.currentTable.name,
            viewName: 'database',
            searchable: true,
            sortable: true,
            filterable: true,
            exportable: true,
            analyzable: true,
            
            onClose: () => {
                this.closeTableData();
            },
            
            onFilterChange: (filters) => {
                console.log('🔄 Filter changed, reloading data');
                this.loadTableData(this.currentTable.name, 1, filters);
            },
            
            onFetchBatch: async (offset, limit, filters) => {
                console.log(`📡 Fetching batch: offset=${offset}, limit=${limit}`);
                
                try {
                    const sql = window.filterService.buildSQLQuery(this.currentTable.name, filters, {
                        columns: ['*'],
                        limit: limit,
                        offset: offset,
                        orderBy: 'notification_name ASC',
                    });
                    
                    const whereClause = window.filterService.extractWhereClause(sql);
                    const orderByClause = window.filterService.extractOrderBy(sql);
                    
                    const result = await api.database.query({
                        table: this.currentTable.name,
                        database: 'data',
                        columns: ['*'],
                        where: whereClause,
                        order_by: orderByClause,
                        limit: limit,
                        offset: offset,
                    });
                    
                    if (result && result.success) {
                        this.currentTable.data = result.data;
                        this.currentTable.total = result.total;
                        
                        return {
                            data: result.data,
                            total: result.total
                        };
                    } else {
                        throw new Error('Failed to fetch batch');
                    }
                } catch (error) {
                    console.error('❌ Fetch batch failed:', error);
                    notify.error(`Failed to load data: ${error.message}`);
                    return {
                        data: [],
                        total: 0
                    };
                }
            },

            onAnalyze: (data) => this.handleAnalyze(data),
            onExport: (data) => this.handleExport(data),
        });

        this.dataTable.context = {
            source: 'table',
            database: 'data',
            tableName: this.currentTable.name,
            jobId: null,
        };

        this.dataTable.setData(this.currentTable.data, this.currentTable.total);
    }

    /**
     * Hide table data section
     */
    closeTableData() {
        const tableDataSection = document.getElementById('tableDataSection');
        if (tableDataSection) {
            tableDataSection.style.display = 'none';
        }

        if (this.dataTable) {
            this.dataTable.destroy();
            this.dataTable = null;
        }

        this.currentTable = null;
        this.currentPage = 1;

        const tablesSection = document.querySelector('.tables-section');
        if (tablesSection) {
            tablesSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    /**
     * Toggle query builder
     */
    toggleQueryBuilder() {
        this.queryBuilderVisible = !this.queryBuilderVisible;
        const container = document.getElementById('queryBuilderContainer');
        const toggleBtn = document.getElementById('toggleQueryBuilder');

        if (container) {
            container.style.display = this.queryBuilderVisible ? 'block' : 'none';
        }

        if (toggleBtn) {
            const icon = toggleBtn.querySelector('.btn-icon');
            if (icon) {
                icon.innerHTML = this.queryBuilderVisible
                    ? '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>'
                    : '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="15" x2="15" y2="15"/>';
            }
        }

        if (this.queryBuilderVisible) {
            this.populateQueryBuilderTables();
        }
    }

    /**
     * Populate query builder table dropdown
     */
    populateQueryBuilderTables() {
        const select = document.getElementById('qbFrom');
        if (!select) return;

        select.innerHTML = '<option value="">Choose table...</option>';

        this.tables.forEach((table) => {
            const option = document.createElement('option');
            option.value = table.name;
            option.textContent = table.name;
            select.appendChild(option);
        });
    }

    /**
     * Execute SQL query using safe backend endpoint
     */
    async executeQuery() {
        const textarea = document.getElementById('sqlQueryInput');
        if (!textarea) return;

        const query = textarea.value.trim();
        if (!query) {
            notify.warning('Please enter a SQL query');
            return;
        }

        try {
            window.showLoading('Validating query...');

            const validation = await api.post('/database/query/validate', { query });

            if (!validation.valid) {
                window.hideLoading();
                notify.error(`Invalid query: ${validation.error}`);
                return;
            }
        } catch (error) {
            window.hideLoading();
            notify.error(`Validation failed: ${error.message}`);
            return;
        }

        const parsed = this.parseQuery(query);
        if (!parsed) {
            window.hideLoading();
            notify.error('Could not parse query. Please check syntax.');
            return;
        }

        try {
            window.showLoading('Executing query...');

            const response = await api.post('/database/query', {
                table: parsed.table,
                columns: parsed.columns || ['*'],
                where: parsed.where || null,
                order_by: parsed.orderBy || null,
                limit: parsed.limit || 1000,
                offset: 0,
            });

            window.hideLoading();

            if (response && response.success) {
                this.displayQueryResults(response.data, response.query, response.total);
                notify.success(`Query executed: ${response.returned} rows returned`);
            } else {
                notify.error('Query execution failed');
            }
        } catch (error) {
            window.hideLoading();
            console.error('Query execution error:', error);
            notify.error(`Query failed: ${error.message}`);
        }
    }

    /**
     * Parse SQL query
     */
    parseQuery(query) {
        try {
            const upperQuery = query.toUpperCase().trim();

            if (!upperQuery.startsWith('SELECT')) {
                notify.error('Only SELECT queries are allowed');
                return null;
            }

            const tableMatch = query.match(/FROM\s+`?(\w+)`?/i);
            if (!tableMatch) {
                return null;
            }
            const table = tableMatch[1];

            const columnsMatch = query.match(/SELECT\s+(.*?)\s+FROM/i);
            const columnsStr = columnsMatch ? columnsMatch[1].trim() : '*';
            const columns =
                columnsStr === '*'
                    ? ['*']
                    : columnsStr.split(',').map((c) => c.trim().replace(/`/g, ''));

            const whereMatch = query.match(/WHERE\s+(.*?)(?:\s+ORDER\s+BY|\s+LIMIT|$)/i);
            const where = whereMatch ? whereMatch[1].trim() : null;

            const orderMatch = query.match(/ORDER\s+BY\s+(.*?)(?:\s+LIMIT|$)/i);
            const orderBy = orderMatch ? orderMatch[1].trim() : null;

            const limitMatch = query.match(/LIMIT\s+(\d+)/i);
            const limit = limitMatch ? parseInt(limitMatch[1]) : 1000;

            return { table, columns, where, orderBy, limit };
        } catch (error) {
            console.error('Query parse error:', error);
            return null;
        }
    }

    /**
     * Display query results
     */
    displayQueryResults(data, query, rowCount) {
        const resultsContainer = document.getElementById('queryResults');
        if (!resultsContainer) return;

        this.currentQueryData = data;

        resultsContainer.style.display = 'block';
        resultsContainer.innerHTML = `
            <div class="query-results-header">
                <h3>Query Results</h3>
                <div class="query-results-info">
                    ${Utils.formatNumber(rowCount)} total rows, showing ${Utils.formatNumber(data.length)}
                </div>
                <div class="query-results-actions">
                    <button class="btn btn-sm btn-secondary" id="copyQueryBtn" title="Copy query to clipboard">
                        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                            <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                        </svg>
                        Copy Query
                    </button>
                </div>
            </div>
            <div class="query-info" style="background: var(--color-background); padding: 0.75rem; border-radius: var(--radius-md); margin-bottom: 1rem; font-family: monospace; font-size: 0.875rem;">
                <strong>Executed Query:</strong><br>
                <code style="color: var(--color-primary);">${Utils.escapeHtml(query)}</code>
            </div>
            <div id="queryResultsTable"></div>
        `;

        if (this.queryResultsTable) {
            this.queryResultsTable.destroy();
        }

        this.queryResultsTable = new UnifiedDataTable('queryResultsTable', {
            title: 'Query Results',
            tableName: 'query_results',
            viewName: 'query_results',
            searchable: true,
            sortable: true,
            filterable: false,
            exportable: true,
            analyzable: true,
            pageSize: 50,
            
            onExport: (data) => {
                if (window.exportComponent) {
                    window.exportComponent.showExportModal(
                        'query',
                        'query_results',
                        this.currentQueryData.length,
                        {
                            database: 'data',
                            data: this.currentQueryData
                        }
                    );
                }
            },
            
            onAnalyze: async (data) => {
                await window.analyzerService.analyze(this.currentQueryData, {
                    source: 'query',
                    name: 'Query Results',
                    showModal: true
                });
            }
        });

        this.queryResultsTable.context = {
            source: 'query',
            database: 'data',
            tableName: 'query_results',
            jobId: null,
        };

        this.queryResultsTable.setData(data);

        const copyBtn = document.getElementById('copyQueryBtn');
        if (copyBtn) {
            copyBtn.addEventListener('click', () => {
                navigator.clipboard.writeText(query);
                notify.success('Query copied to clipboard');
            });
        }

        setTimeout(() => {
            resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
    }

    /**
     * Build query from query builder
     */
    buildQuery() {
        const selectFields = document.getElementById('qbSelect')?.value.trim() || '*';
        const fromTable = document.getElementById('qbFrom')?.value.trim();
        const whereClause = document.getElementById('qbWhere')?.value.trim();
        const orderByClause = document.getElementById('qbOrderBy')?.value.trim();
        const limitValue = document.getElementById('qbLimit')?.value.trim();

        if (!fromTable) {
            notify.warning('Please select a table');
            return;
        }

        let query = `SELECT ${selectFields} FROM \`${fromTable}\``;

        if (whereClause) {
            query += ` WHERE ${whereClause}`;
        }

        if (orderByClause) {
            query += ` ORDER BY ${orderByClause}`;
        }

        if (limitValue) {
            query += ` LIMIT ${limitValue}`;
        }

        const textarea = document.getElementById('sqlQueryInput');
        if (textarea) {
            textarea.value = query;
            textarea.focus();
        }

        notify.success('Query built successfully');
    }

    /**
     * Clear query and results
     */
    clearQuery() {
        const textarea = document.getElementById('sqlQueryInput');
        if (textarea) {
            textarea.value = '';
            textarea.focus();
        }

        const resultsContainer = document.getElementById('queryResults');
        if (resultsContainer) {
            resultsContainer.style.display = 'none';
            resultsContainer.innerHTML = '';
        }

        if (this.queryResultsTable) {
            this.queryResultsTable.destroy();
            this.queryResultsTable = null;
        }

        const qbSelect = document.getElementById('qbSelect');
        const qbFrom = document.getElementById('qbFrom');
        const qbWhere = document.getElementById('qbWhere');
        const qbOrderBy = document.getElementById('qbOrderBy');
        const qbLimit = document.getElementById('qbLimit');

        if (qbSelect) qbSelect.value = '*';
        if (qbFrom) qbFrom.value = '';
        if (qbWhere) qbWhere.value = '';
        if (qbOrderBy) qbOrderBy.value = '';
        if (qbLimit) qbLimit.value = '1000';
    }

    /**
     * Clear query builder fields
     */
    clearQueryBuilder() {
        const qbSelect = document.getElementById('qbSelect');
        const qbFrom = document.getElementById('qbFrom');
        const qbWhere = document.getElementById('qbWhere');
        const qbOrderBy = document.getElementById('qbOrderBy');
        const qbLimit = document.getElementById('qbLimit');

        if (qbSelect) qbSelect.value = '*';
        if (qbFrom) qbFrom.value = '';
        if (qbWhere) qbWhere.value = '';
        if (qbOrderBy) qbOrderBy.value = '';
        if (qbLimit) qbLimit.value = '1000';

        notify.success('Query builder cleared');
    }

    /**
     * Show import modal
     */
    async showImportModal(tableName = null) {
        const isNewTable = !tableName;
        
        const content = `
            <div class="import-modal">
                <div class="form-group">
                    <label for="importTableName">Target Table</label>
                    ${isNewTable ? `
                        <input 
                            type="text" 
                            id="importTableName" 
                            class="form-input" 
                            placeholder="e.g., my_data_table"
                            required
                        />
                        <small style="color: var(--color-text-secondary); display: block; margin-top: 0.5rem;">
                            Use letters, numbers, and underscores only
                        </small>
                    ` : `
                        <input 
                            type="text" 
                            id="importTableName" 
                            class="form-input" 
                            value="${tableName}"
                            readonly
                            style="background: var(--color-surface); cursor: not-allowed;"
                        />
                    `}
                </div>
                
                <div class="form-group">
                    <label for="importFile">Select File</label>
                    <input 
                        type="file" 
                        id="importFile" 
                        class="form-input" 
                        accept=".csv,.json,.xlsx,.xls,.txt,.gz,.zip,.bz2,.xz"
                        required
                    />
                    <small style="color: var(--color-text-secondary); display: block; margin-top: 0.5rem;">
                        ✅ Supported: CSV, JSON, Excel, Text, Compressed files (.gz, .zip, .bz2, .xz)
                    </small>
                </div>
                
                <div class="form-group">
                    <label>Import Mode</label>
                    <div style="display: flex; flex-direction: column; gap: var(--spacing-sm);">
                        <label class="radio-label">
                            <input type="radio" name="importMode" value="append" checked />
                            <span>
                                <strong>Append</strong> - Add to existing data
                                <small style="display: block; color: var(--color-text-secondary); margin-top: 0.25rem;">
                                    Keeps existing rows, adds new rows
                                </small>
                            </span>
                        </label>
                        <label class="radio-label">
                            <input type="radio" name="importMode" value="replace" />
                            <span>
                                <strong>Replace</strong> - Delete existing data, insert new
                                <small style="display: block; color: var(--color-text-secondary); margin-top: 0.25rem;">
                                    ⚠️ Deletes all existing rows first
                                </small>
                            </span>
                        </label>
                    </div>
                </div>
                
                <div class="info-box" style="background: var(--color-info-bg); border-left: 4px solid var(--color-info); padding: var(--spacing-md); border-radius: var(--radius-md); margin-top: var(--spacing-md);">
                    <svg style="width: 20px; height: 20px; display: inline-block; vertical-align: middle; margin-right: var(--spacing-xs);" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="16" x2="12" y2="12"/>
                        <line x1="12" y1="8" x2="12.01" y2="8"/>
                    </svg>
                    <strong>Auto-Detection:</strong> File format and structure are automatically detected. 
                    Column names will be cleaned (spaces → underscores, special characters removed).
                </div>
                
                <div id="importProgress" style="display: none; margin-top: var(--spacing-md);">
                    <div class="progress-bar-container">
                        <div class="progress-bar-fill" id="importProgressBar" style="width: 0%;"></div>
                    </div>
                    <p id="importProgressText" style="text-align: center; margin-top: var(--spacing-xs); font-size: 0.875rem; color: var(--color-text-secondary);">
                        Uploading...
                    </p>
                </div>
            </div>
        `;
        
        modal.show({
            title: isNewTable ? 'Import Data to New Table' : `Import Data to ${tableName}`,
            content: content,
            size: 'medium',
            buttons: [
                {
                    text: 'Cancel',
                    class: 'btn-secondary',
                    onClick: () => modal.close()
                },
                {
                    text: 'Import',
                    class: 'btn-primary',
                    onClick: async () => {
                        await this.executeImport(isNewTable);
                    }
                }
            ]
        });
    }

    /**
     * Execute import
     */
    async executeImport(isNewTable) {
        const tableNameInput = document.getElementById('importTableName');
        const fileInput = document.getElementById('importFile');
        const modeInputs = document.getElementsByName('importMode');
        
        const targetTable = tableNameInput.value.trim();
        const file = fileInput.files[0];
        const mode = Array.from(modeInputs).find(r => r.checked)?.value || 'append';
        
        if (!targetTable) {
            notify.error('Please enter a table name');
            return;
        }
        
        if (!/^[a-zA-Z][a-zA-Z0-9_]*$/.test(targetTable)) {
            notify.error('Invalid table name. Use letters, numbers, and underscores only.');
            return;
        }
        
        if (!file) {
            notify.error('Please select a file');
            return;
        }
        
        const progressDiv = document.getElementById('importProgress');
        const progressBar = document.getElementById('importProgressBar');
        const progressText = document.getElementById('importProgressText');
        
        if (progressDiv) progressDiv.style.display = 'block';
        
        const buttons = document.querySelectorAll('.modal-footer .btn');
        buttons.forEach(btn => btn.disabled = true);
        
        try {
            const result = await api.database.importFromFile(targetTable, file, {
                mode: mode,
                createIfMissing: isNewTable,
                onProgress: (percent) => {
                    if (progressBar) progressBar.style.width = `${percent}%`;
                    if (progressText) progressText.textContent = `Uploading... ${Math.round(percent)}%`;
                }
            });
            
            if (result.success) {
                modal.close();
                
                const quickMessage = [
                    `✅ Imported ${Utils.formatNumber(result.rows_imported)} rows`,
                    `${result.column_count} columns`,
                    `${result.size_mb.toFixed(2)} MB`,
                    result.created_table ? '(new table)' : ''
                ].filter(Boolean).join(' • ');
                
                notify.success(quickMessage);
                
                await this.loadTables();
                
                const viewData = await modal.confirm({
                    title: 'Import Successful',
                    message: `
                        <div style="text-align: left;">
                            <p style="margin-bottom: var(--spacing-md);">
                                <strong>${Utils.formatNumber(result.rows_imported)}</strong> rows imported to 
                                <strong>"${targetTable}"</strong>
                            </p>
                            
                            <div style="background: var(--color-surface); padding: var(--spacing-md); border-radius: var(--radius-md); margin-bottom: var(--spacing-md);">
                                <table style="width: 100%; font-size: 0.875rem;">
                                    <tr>
                                        <td style="color: var(--color-text-secondary); padding: 0.25rem 0;">Columns:</td>
                                        <td style="text-align: right; font-weight: var(--font-weight-semibold);">${result.column_count}</td>
                                    </tr>
                                    <tr>
                                        <td style="color: var(--color-text-secondary); padding: 0.25rem 0;">Total Rows:</td>
                                        <td style="text-align: right; font-weight: var(--font-weight-semibold);">${Utils.formatNumber(result.total_rows)}</td>
                                    </tr>
                                    <tr>
                                        <td style="color: var(--color-text-secondary); padding: 0.25rem 0;">Size:</td>
                                        <td style="text-align: right; font-weight: var(--font-weight-semibold);">${result.size_mb.toFixed(2)} MB</td>
                                    </tr>
                                    <tr>
                                        <td style="color: var(--color-text-secondary); padding: 0.25rem 0;">Format:</td>
                                        <td style="text-align: right; font-weight: var(--font-weight-semibold);">${result.file_format.toUpperCase()}</td>
                                    </tr>
                                    <tr>
                                        <td style="color: var(--color-text-secondary); padding: 0.25rem 0;">Duration:</td>
                                        <td style="text-align: right; font-weight: var(--font-weight-semibold);">${result.duration.toFixed(2)}s</td>
                                    </tr>
                                    <tr>
                                        <td style="color: var(--color-text-secondary); padding: 0.25rem 0;">Mode:</td>
                                        <td style="text-align: right; font-weight: var(--font-weight-semibold);">${result.mode.charAt(0).toUpperCase() + result.mode.slice(1)}</td>
                                    </tr>
                                </table>
                            </div>
                            
                            ${result.columns && result.columns.length > 0 ? `
                                <details style="margin-top: var(--spacing-md);">
                                    <summary style="cursor: pointer; color: var(--color-primary); font-weight: var(--font-weight-medium);">
                                        View Columns (${result.columns.length})
                                    </summary>
                                    <div style="margin-top: var(--spacing-sm); padding: var(--spacing-sm); background: var(--color-surface); border-radius: var(--radius-md); max-height: 200px; overflow-y: auto;">
                                        <code style="font-size: 0.75rem; line-height: 1.6;">
                                            ${result.columns.join(', ')}
                                        </code>
                                    </div>
                                </details>
                            ` : ''}
                            
                            <p style="margin-top: var(--spacing-md); color: var(--color-text-secondary); font-size: 0.875rem;">
                                Would you like to view the imported data now?
                            </p>
                        </div>
                    `,
                    confirmText: 'View Data',
                    cancelText: 'Close',
                    type: 'success'
                });
                
                if (viewData) {
                    this.loadTableData(targetTable);
                }
            }
            
        } catch (error) {
            notify.error(`Import failed: ${error.message}`);
            
            buttons.forEach(btn => btn.disabled = false);
            
            if (progressDiv) progressDiv.style.display = 'none';
        }
    }

    /**
     * Cleanup method
     */
    destroy() {
        this.eventListeners.forEach(({ element, event, handler }) => {
            element.removeEventListener(event, handler);
        });
        this.eventListeners = [];

        this.tables = [];
        this.currentTable = null;
        this.expandedTables.clear();

        if (this.dataTable) {
            this.dataTable.destroy();
            this.dataTable = null;
        }

        // Disconnect all sync WebSockets
        this.syncWebsockets.forEach((ws, tableName) => {
            this.disconnectSyncWebSocket(tableName);
        });
    
        // ✅ NEW: Disconnect sync all WebSocket
        this.disconnectSyncAllWebSocket();
    }

    // ============================================
    // COMMON WEBSOCKET METHODS
    // ============================================
    
    /**
     * ✅ COMMON: Create WebSocket connection
     */
    createWebSocket(endpoint, topic) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const wsUrl = `${protocol}//${host}${endpoint}`;
        
        // console.log(`🔌 Connecting to WebSocket: ${wsUrl}`);
        
        const ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            // console.log(`✅ WebSocket connected: ${topic}`);
            
            // Ping interval to keep connection alive
            const pingInterval = setInterval(() => {
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send('ping');
                } else {
                    clearInterval(pingInterval);
                }
            }, 10000);
            
            ws.pingInterval = pingInterval;
        };
        
        ws.onerror = (error) => {
            console.error(`❌ WebSocket error for ${topic}:`, error);
        };
        
        ws.onclose = () => {
            // console.log(`🔌 WebSocket closed: ${topic}`);
            
            if (ws.pingInterval) {
                clearInterval(ws.pingInterval);
            }
        };
        
        return ws;
    }
    
    /**
     * Connect WebSocket for active syncs on page load
     */
    connectActiveSyncWebSockets() {
        this.tables.forEach(table => {
            const syncInfo = this.syncStatusMap[table.name];
            
            if (!syncInfo) return;
            
            const isConnected = this.syncWebsockets.has(table.name);
            const isSyncing = syncInfo.status === 'syncing' || syncInfo.status === 'pending';
            
            const shouldConnect = isSyncing && !isConnected;
            
            if (shouldConnect) {
                // console.log(`🔌 Connecting WebSocket for syncing table: ${table.name}`);
                this.connectSyncWebSocket(table.name);
            }
        });
    }

    /**
     * ✅ COMMON: Disconnect WebSocket
     */
    disconnectWebSocket(ws, topic) {
        if (ws) {
            if (ws.pingInterval) {
                clearInterval(ws.pingInterval);
            }
            
            ws.close();
            // console.log(`🔌 Disconnected WebSocket: ${topic}`);
        }
    }

    // ============================================
    // SYNC TABLE WEBSOCKET
    // ============================================
    
    /**
     * Connect to WebSocket for single table sync
     */
    connectSyncWebSocket(tableName) {
        if (this.syncWebsockets.has(tableName)) {
            // console.log(`WebSocket already connected for sync ${tableName}`);
            return;
        }
        
        const endpoint = `/api/v1/trap-sync/ws/${tableName}`;
        const topic = `sync:${tableName}`;
        
        const ws = this.createWebSocket(endpoint, topic);
        
        ws.onmessage = (event) => {
            try {
                if (event.data === 'pong') {
                    return;
                }
                
                const message = JSON.parse(event.data);
                
                if (message.topic && message.topic.startsWith('sync:')) {
                    this.handleSyncProgress(message.data);
                }
            } catch (error) {
                console.error('WebSocket message parse error:', error);
            }
        };
        
        this.syncWebsockets.set(tableName, ws);
    }
    
    /**
     * Disconnect sync WebSocket for single table
     */
    disconnectSyncWebSocket(tableName) {
        const ws = this.syncWebsockets.get(tableName);
        
        if (ws) {
            this.disconnectWebSocket(ws, `sync:${tableName}`);
            this.syncWebsockets.delete(tableName);
        }
    }
    

    /**
     * ✅ UPDATED: Handle individual table sync progress
     */
    handleSyncProgress(data) {
        const { table_name, status, progress, message } = data;
        
        console.log(`📊 Sync progress for ${table_name}: ${progress}% - ${message}`);
        
        if (status === 'started') {
            // Only show notification if not part of sync all
            if (!this.syncAllWebsocket) {
                // notify.info(`Starting sync for ${table_name}...`);
            }
            this.showSyncProgressBar(table_name, 0, message);
        } else if (status === 'syncing') {
            this.updateSyncProgressBar(table_name, progress, message);
        } else if (status === 'completed') {
            this.hideSyncProgressBar(table_name);

            // ✅ OPTIMIZED: Reload only sync status (faster than full table reload)
            this.loadSyncStatus().then(() => {
                // Re-render the table list with updated sync status
                this.displayTables();
            });
            
            // Only show notification if not part of sync all
            if (!this.syncAllWebsocket) {
                // notify.success(message, { duration: 5000 });
            }
            
            // Only reload and disconnect if not part of sync all
            if (!this.syncAllWebsocket) {
                // this.loadTables();
                this.disconnectSyncWebSocket(table_name);
            }
        } else if (status === 'failed') {
            this.hideSyncProgressBar(table_name);
            
            // Only show notification if not part of sync all
            if (!this.syncAllWebsocket) {
                notify.error(message);
                this.loadTables();
                this.disconnectSyncWebSocket(table_name);
            }
        }
    }


    /**
     * ✅ NEW: Show sync progress bar
     */
    showSyncProgressBar(tableName, progress, message) {
        const tableRow = document.querySelector(`[data-table="${tableName}"]`);
        if (!tableRow) return;
        
        // Find sync status div
        const syncStatusDiv = tableRow.querySelector('.table-list-sync-status');
        if (!syncStatusDiv) return;
        
        // Create progress bar container
        let progressContainer = tableRow.querySelector('.sync-progress-container');
        
        if (!progressContainer) {
            progressContainer = document.createElement('div');
            progressContainer.className = 'sync-progress-container';
            progressContainer.style.cssText = `
                margin-top: 0.5rem;
                width: 100%;
            `;
            
            progressContainer.innerHTML = `
                <div class="sync-progress-bar" style="
                    width: 100%;
                    height: 4px;
                    background: var(--color-border);
                    border-radius: 2px;
                    overflow: hidden;
                ">
                    <div class="sync-progress-fill" style="
                        height: 100%;
                        background: var(--color-primary);
                        transition: width 0.3s ease;
                        width: 0%;
                    "></div>
                </div>
                <div class="sync-progress-text" style="
                    font-size: 0.75rem;
                    color: var(--color-text-secondary);
                    margin-top: 0.25rem;
                "></div>
            `;
            
            syncStatusDiv.appendChild(progressContainer);
        }
        
        // Update progress
        const progressFill = progressContainer.querySelector('.sync-progress-fill');
        const progressText = progressContainer.querySelector('.sync-progress-text');
        
        if (progressFill) {
            progressFill.style.width = `${progress}%`;
        }
        
        if (progressText) {
            progressText.textContent = `${Math.round(progress)}% - ${message}`;
        }
    }

    /**
     * ✅ NEW: Update sync progress bar
     */
    updateSyncProgressBar(tableName, progress, message) {
        const tableRow = document.querySelector(`[data-table="${tableName}"]`);
        if (!tableRow) return;
        
        const progressContainer = tableRow.querySelector('.sync-progress-container');
        if (!progressContainer) {
            // Create if doesn't exist
            this.showSyncProgressBar(tableName, progress, message);
            return;
        }
        
        const progressFill = progressContainer.querySelector('.sync-progress-fill');
        const progressText = progressContainer.querySelector('.sync-progress-text');
        
        if (progressFill) {
            progressFill.style.width = `${progress}%`;
        }
        
        if (progressText) {
            progressText.textContent = `${Math.round(progress)}% - ${message}`;
        }
    }

    /**
     * ✅ NEW: Hide sync progress bar
     */
    hideSyncProgressBar(tableName) {
        const tableRow = document.querySelector(`[data-table="${tableName}"]`);
        if (!tableRow) return;
        
        const progressContainer = tableRow.querySelector('.sync-progress-container');
        if (progressContainer) {
            progressContainer.remove();
        }
    }
    
    // ============================================
    // SYNC ALL WEBSOCKET
    // ============================================
    
    /**
     * Connect to WebSocket for sync all
     */
    connectSyncAllWebSocket() {
        if (this.syncAllWebsocket) {
            console.log('WebSocket already connected for sync all');
            return;
        }
        
        const endpoint = '/api/v1/trap-sync/ws/all';
        const topic = 'sync:all';
        
        const ws = this.createWebSocket(endpoint, topic);
        
        ws.onmessage = (event) => {
            try {
                if (event.data === 'pong') {
                    return;
                }
                
                const message = JSON.parse(event.data);
                
                if (message.topic === 'sync:all') {
                    this.handleSyncAllProgress(message.data);
                }
            } catch (error) {
                console.error('WebSocket message parse error:', error);
            }
        };
        
        this.syncAllWebsocket = ws;
    }
    
    /**
     * Disconnect sync all WebSocket
     */
    disconnectSyncAllWebSocket() {
        if (this.syncAllWebsocket) {
            this.disconnectWebSocket(this.syncAllWebsocket, 'sync:all');
            this.syncAllWebsocket = null;
        }
    }
    
    /**
     * ✅ UPDATED: Handle sync all progress with individual table subscriptions
     */
    handleSyncAllProgress(data) {
        const { status, progress, message, current_table } = data;
        
        console.log(`📊 Sync all progress: ${progress}% - ${message}`);
        
        if (status === 'started') {
            notify.info(message);
        } else if (status === 'syncing') {
            // ✅ Subscribe to individual table progress
            if (current_table && !this.syncWebsockets.has(current_table)) {
                // console.log(`📡 Subscribing to individual table progress: ${current_table}`);
                this.connectSyncWebSocket(current_table);
            }
            
            // Show overall progress in console
            console.log(`Overall progress: ${progress}%`);
        } else if (status === 'completed') {
            notify.success(message);
            
            // Unsubscribe from all individual table topics
            this.syncWebsockets.forEach((ws, tableName) => {
                this.disconnectSyncWebSocket(tableName);
            });
            
            // Reload tables to update sync status
            this.loadTables();
            
            // Disconnect sync all WebSocket
            this.disconnectSyncAllWebSocket();
        } else if (status === 'failed') {
            notify.error(message);
            
            // Unsubscribe from all individual table topics
            this.syncWebsockets.forEach((ws, tableName) => {
                this.disconnectSyncWebSocket(tableName);
            });
            
            // Reload tables
            this.loadTables();
            
            // Disconnect sync all WebSocket
            this.disconnectSyncAllWebSocket();
        }
    }


}

// Initialize when DOM is ready
function initDatabaseComponent() {
    if (typeof Utils === 'undefined' || typeof api === 'undefined') {
        console.warn('DatabaseComponent: Waiting for dependencies...');
        setTimeout(initDatabaseComponent, 100);
        return;
    }

    window.databaseComponent = new DatabaseComponent();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(initDatabaseComponent, 100);
    });
} else {
    setTimeout(initDatabaseComponent, 100);
}
