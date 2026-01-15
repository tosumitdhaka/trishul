/**
 * ============================================
 * Unified Data Table Component (Phase 1)
 * ============================================
 * 
 * Features:
 * - Dual pagination (client-side table + server-side DB)
 * - Advanced filtering (38 columns, 9 operators)
 * - Node type quick filter
 * - Column selector (38 columns, configurable defaults)
 * - DB fetch limit dropdown
 * - Configurable height from settings
 * - Export/Analyze integration
 * 
 * @version 2.0.0
 * @author MIB Tool Team
 */

class UnifiedDataTable {
    /**
     * Create a new data table
     * @param {string} containerId - DOM element ID for table container
     * @param {Object} options - Configuration options
     */
    constructor(containerId, options = {}) {
        // console.log('🎨 [DataTable] Creating new UnifiedDataTable...');
        
        this.container = document.getElementById(containerId);
        if (!this.container) {
            throw new Error(`Container #${containerId} not found`);
        }

        // Load UI settings from backend
        const uiSettings = window.settings?.getBackend('ui.data_table', {});
        // console.log('📋 [DataTable] UI settings loaded:', uiSettings);
        
        // Store configurable values from settings
        this.maxHeight = uiSettings.max_height_px || 600;
        this.dbFetchLimit = uiSettings.db_fetch_limit_default || 1000;
        this.dbFetchLimitOptions = uiSettings.db_fetch_limit_options || [500, 1000, 2000, 5000, 10000];
        this.priorityColumns = uiSettings.priority_columns || [];
        this.nodeTypeOptions = uiSettings.node_type_options || [
            'NotificationType',
            'ObjectType',
            'TypeDefinition',
            'ModuleIdentity',
            'MibTable',
            'MibTableRow',
            'MibTableColumn',
            'MibScalar',
            'MibIdentifier'
        ];

        // Merge options with defaults
        this.options = {
            title: 'Data Table',
            data: [],
            columns: [],
            pageSize: window.settings?.get('tablePageSize') || uiSettings.default_page_size || 50,
            searchable: true,
            sortable: true,
            filterable: true,
            exportable: true,
            analyzable: true,
            selectable: false,
            persistColumns: true,
            viewName: containerId,
            tableName: options.tableName || null,
            onAnalyze: null,
            onExport: null,
            onClose: null,
            onFilterChange: null,
            onFetchBatch: null,
            ...options,
        };

        // Initialize state
        this.state = {
            // Data
            data: [],                    // Currently loaded records (e.g., 1,000)
            filteredData: [],            // After client-side search
            displayData: [],             // Current page (e.g., 1-100)
            
            // Table pagination (client-side)
            currentPage: 1,
            totalPages: 0,
            
            // DB pagination (server-side)
            dbOffset: 0,
            dbLimit: this.dbFetchLimit,
            dbTotalCount: 0,
            dbFetchedCount: 0,
            
            // Columns
            allColumns: [],
            visibleColumns: [],
            
            // Sorting
            sortColumn: null,
            sortDirection: 'asc',
            
            // Filtering
            searchQuery: '',
            filters: [],
            
            // Selection
            selectedRows: new Set(),
        };

        // Context (for export/analyze)
        this.context = {
            source: 'unknown',
            database: null,
            tableName: null,
            jobId: null,
        };

        // console.log('✅ [DataTable] UnifiedDataTable created');
    }

    /**
     * Set data and render table
     * @param {Array} data - Array of data objects
     * @param {number} total - Total count in database
     * @param {boolean} skipDefaultFilter - Skip applying default filters
     */
    setData(data, total = null, skipDefaultFilter = false) {
        // console.log(`📊 [DataTable] Setting data: ${data.length} records, total: ${total || 'unknown'}`);
        
        this.state.data = data || [];
        this.state.dbFetchedCount = data.length;
        this.state.dbTotalCount = total || data.length;
        this.state.dbOffset = 0;

        // Extract columns from first row
        if (data.length > 0) {
            this.state.allColumns = Object.keys(data[0]);
            
            // Set visible columns (priority columns if available, otherwise first 8)
            if (this.options.persistColumns) {
                const saved = window.settings?.getTableColumns(this.options.viewName);
                if (saved && saved.length > 0) {
                    this.state.visibleColumns = saved.filter(col => this.state.allColumns.includes(col));
                }
            }
            
            if (this.state.visibleColumns.length === 0) {
                // Use priority columns from config
                const priorityCols = this.priorityColumns.filter(col => this.state.allColumns.includes(col));
                this.state.visibleColumns = priorityCols.length > 0 
                    ? priorityCols 
                    : this.state.allColumns.slice(0, 8);
            }
        }

        // Apply filters and render
        if (!skipDefaultFilter) {
            this.applyFilters();
        } else {
            this.state.filteredData = [...this.state.data];
        }
        
        this.updateDisplay();
        this.render();
        this.setupEventListeners();
        
        // console.log('✅ [DataTable] Data set and rendered');
    }

    /**
     * Render complete table HTML
     */
    render() {
        if (!this.container) return;

        this.container.innerHTML = `
            <div class="data-table-container">
                ${this.renderHeader()}
                ${this.options.filterable ? this.renderFilterRow() : ''}
                ${this.renderToolbar()}
                <div class="table-layout" style="max-height: ${this.maxHeight}px;">
                    ${this.renderColumnSelector()}
                    <div class="table-wrapper">
                        ${this.renderTable()}
                    </div>
                </div>
                ${this.renderFooter()}
            </div>
        `;
        // ✅ NEW: Expose instance for filter removal
        window[`${this.options.viewName}DataTable`] = this;
    }

    /**
     * Render table header
     */
    renderHeader() {
        return `
            <div class="table-header">
                <h3 class="table-title">${this.options.title}</h3>
                <div class="table-actions">
                    <!-- ✅ FIXED: Only show DB Fetch Limit if onFetchBatch callback exists -->
                    ${this.options.onFetchBatch ? `
                        <label style="display: flex; align-items: center; gap: 8px; margin-right: var(--spacing-md);">
                            <span style="font-size: 0.875rem; color: var(--color-text-secondary); white-space: nowrap;">DB Fetch Limit:</span>
                            <select id="${this.options.viewName}_dbFetchLimit" class="form-select" style="width: 100px;">
                                ${this.dbFetchLimitOptions.map(opt => 
                                    `<option value="${opt}" ${opt === this.state.dbLimit ? 'selected' : ''}>${opt}</option>`
                                ).join('')}
                            </select>
                        </label>
                    ` : ''}
                    
                    ${this.options.analyzable ? `
                        <button class="btn btn-sm btn-secondary" id="${this.options.viewName}_analyzeBtn">
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <line x1="18" y1="20" x2="18" y2="10"/>
                                <line x1="12" y1="20" x2="12" y2="4"/>
                                <line x1="6" y1="20" x2="6" y2="14"/>
                            </svg>
                            Analyze
                        </button>
                    ` : ''}
                    
                    ${this.options.exportable ? `
                        <button class="btn btn-sm btn-secondary" id="${this.options.viewName}_exportBtn">
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                                <polyline points="7 10 12 15 17 10"/>
                                <line x1="12" y1="15" x2="12" y2="3"/>
                            </svg>
                            Export
                        </button>
                    ` : ''}
                    
                    <button class="btn btn-sm btn-secondary" id="${this.options.viewName}_closeBtn">
                        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <line x1="18" y1="6" x2="6" y2="18"/>
                            <line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                        Close
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Render filter row
     */
    renderFilterRow() {
        const columns = this.state.allColumns.length > 0 
            ? this.state.allColumns 
            : this.options.columns;

        return `
            <div class="filter-row" id="${this.options.viewName}_filterRow">
                <div class="filter-group">
                    <span class="filter-label">Filter:</span>
                    <select class="form-select filter-input" id="${this.options.viewName}_filterColumn">
                        <option value="">Select column...</option>
                        ${columns.map(col => 
                            `<option value="${col}">${this.formatColumnName(col)}</option>`
                        ).join('')}
                    </select>
                    <select class="form-select filter-input" id="${this.options.viewName}_filterOperator">
                        <option value="contains">Contains</option>
                        <option value="equals">Equals</option>
                        <option value="starts_with">Starts with</option>
                        <option value="ends_with">Ends with</option>
                        <option value="not_empty">Not empty</option>
                        <option value="empty">Empty</option>
                        <option value="greater_than">Greater than</option>
                        <option value="less_than">Less than</option>
                        <option value="between">Between</option>
                    </select>
                    <input type="text" class="form-input filter-input" id="${this.options.viewName}_filterValue" placeholder="Value...">
                    <button class="btn btn-sm filter-add-btn btn-secondary" id="${this.options.viewName}_addFilterBtn">Add</button>
                </div>
                
                <!-- Node Type Quick Filter -->
                <div class="filter-group" style="margin-left: auto;">
                    <span class="filter-label">Node Type:</span>
                    <select id="${this.options.viewName}_nodeTypeFilter" class="form-select" style="min-width: 180px;">
                        <option value="">All Types</option>
                        ${this.nodeTypeOptions.map(type => {
                            const isSelected = this.state.filters.some(f => f.column === 'node_type' && f.value === type);
                            return `<option value="${type}" ${isSelected ? 'selected' : ''}>${type}</option>`;
                        }).join('')}
                    </select>
                </div>
                
                <div class="active-filters" id="${this.options.viewName}_activeFilters"></div>
            </div>
        `;
    }

    /**
     * ✅ NEW: Remove filter by column
     */
    removeFilter(column) {
        this.state.filters = this.state.filters.filter(f => f.column !== column);
        
        if (this.options.onFilterChange) {
            this.options.onFilterChange(this.state.filters);
        } else {
            this.applyFilters();
            this.updateDisplay();
        }
        
        this.renderActiveFilters();
    }


    /**
     * ✅ NEW: Render active filter tags
     */
    renderActiveFilters() {
        const container = document.getElementById(`${this.options.viewName}_activeFilters`);
        if (!container) return;
        
        if (this.state.filters.length === 0) {
            container.innerHTML = '<div class="active-filters-empty">No active filters</div>';
            return;
        }
        
        container.innerHTML = this.state.filters.map(filter => `
            <div class="filter-tag">
                <span class="filter-tag-text">
                    ${this.formatColumnName(filter.column)} ${filter.operator} "${filter.value}"
                </span>
                <svg class="filter-tag-close" viewBox="0 0 24 24" fill="none" stroke="currentColor" 
                     onclick="window.${this.options.viewName}DataTable?.removeFilter('${filter.column}')">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
            </div>
        `).join('');
    }


    /**
     * Render toolbar (search + pagination)
     */
    renderToolbar() {
        const totalPages = Math.ceil(this.state.filteredData.length / this.options.pageSize);
        const start = (this.state.currentPage - 1) * this.options.pageSize + 1;
        const end = Math.min(start + this.options.pageSize - 1, this.state.filteredData.length);

        return `
            <div class="table-toolbar">
                <div class="table-toolbar-left">
                    ${this.options.searchable ? `
                        <input type="text" 
                               class="search-input" 
                               id="${this.options.viewName}_searchInput" 
                               placeholder="Search in current data..."
                               value="${this.state.searchQuery}">
                    ` : ''}
                </div>
                <div class="table-toolbar-right">
                    <div class="table-info">
                        Showing <strong>${start}-${end}</strong> of <strong>${this.state.filteredData.length}</strong>
                    </div>
                    ${totalPages > 1 ? this.renderPagination(totalPages) : ''}
                    <div class="page-size-selector">
                        <label>Show:</label>
                        <select id="${this.options.viewName}_pageSizeSelect" class="form-select">
                            ${[25, 50, 100, 500, 1000].map(size => 
                                `<option value="${size}" ${size === this.options.pageSize ? 'selected' : ''}>${size}</option>`
                            ).join('')}
                        </select>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render pagination controls
     */
    renderPagination(totalPages) {
        const current = this.state.currentPage;
        const pages = [];
        
        // Always show first page
        pages.push(1);
        
        // Show pages around current
        for (let i = Math.max(2, current - 1); i <= Math.min(totalPages - 1, current + 1); i++) {
            if (!pages.includes(i)) pages.push(i);
        }
        
        // Always show last page
        if (totalPages > 1 && !pages.includes(totalPages)) {
            pages.push(totalPages);
        }

        return `
            <div class="pagination">
                <button class="pagination-btn" id="${this.options.viewName}_prevPageBtn" ${current === 1 ? 'disabled' : ''}>
                    ◀
                </button>
                ${pages.map((page, index) => {
                    const prevPage = pages[index - 1];
                    const gap = prevPage && page - prevPage > 1 ? '<span class="pagination-ellipsis">...</span>' : '';
                    return `
                        ${gap}
                        <button class="pagination-btn ${page === current ? 'active' : ''}" 
                                data-page="${page}">
                            ${page}
                        </button>
                    `;
                }).join('')}
                <button class="pagination-btn" id="${this.options.viewName}_nextPageBtn" ${current === totalPages ? 'disabled' : ''}>
                    ▶
                </button>
            </div>
        `;
    }

    /**
     * Render column selector
     */
    renderColumnSelector() {
        return `
            <div class="column-selector">
                <div class="column-selector-header">
                    <h4 class="column-selector-title">Columns</h4>
                </div>
                <div class="column-selector-body">
                    ${this.state.allColumns.map(col => `
                        <div class="column-item">
                            <input type="checkbox" 
                                   id="col_${col}" 
                                   value="${col}" 
                                   ${this.state.visibleColumns.includes(col) ? 'checked' : ''}>
                            <label class="column-item-label" for="col_${col}">
                                ${this.formatColumnName(col)}
                            </label>
                        </div>
                    `).join('')}
                </div>
                <div class="column-selector-footer">
                    <button class="btn btn-sm btn-secondary" id="${this.options.viewName}_selectAllBtn">All</button>
                    <button class="btn btn-sm btn-secondary" id="${this.options.viewName}_selectNoneBtn">None</button>
                    <button class="btn btn-sm btn-secondary" id="${this.options.viewName}_resetColumnsBtn">Reset</button>
                </div>
            </div>
        `;
    }

    /**
     * Render data table
     */
    renderTable() {
        if (this.state.displayData.length === 0) {
            return this.renderEmptyState();
        }

        return `
            <div class="table-scroll-container">
                <table class="data-table">
                    <thead>
                        <tr>
                            ${this.state.visibleColumns.map(col => `
                                <th class="${this.options.sortable ? 'sortable' : ''}" data-column="${col}">
                                    ${this.formatColumnName(col)}
                                    ${this.state.sortColumn === col ? (this.state.sortDirection === 'asc' ? ' ▲' : ' ▼') : ''}
                                </th>
                            `).join('')}
                        </tr>
                    </thead>
                    <tbody>
                        ${this.state.displayData.map(row => `
                            <tr>
                                ${this.state.visibleColumns.map(col => `
                                    <td title="${this.escapeHtml(String(row[col] || ''))}">${this.formatCellValue(row[col], col)}</td>
                                `).join('')}
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    /**
     * Render empty state
     */
    renderEmptyState() {
        return `
            <div class="table-empty">
                <svg class="table-empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                <p class="table-empty-message">No data to display</p>
                <p class="table-empty-hint">Try adjusting your filters or loading more data</p>
            </div>
        `;
    }

    /**
     * Render footer (DB pagination only)
     */
    renderFooter() {
        const dbBatchNumber = Math.floor(this.state.dbOffset / this.state.dbLimit) + 1;
        const dbTotalBatches = Math.ceil(this.state.dbTotalCount / this.state.dbLimit);
        const hasMoreData = this.state.dbFetchedCount < this.state.dbTotalCount;
        
        return `
            <div class="table-footer">
                <div class="db-pagination-info">
                    Loaded <strong>${Utils.formatNumber(this.state.dbOffset)}</strong>-<strong>${Utils.formatNumber(this.state.dbFetchedCount)}</strong> of <strong>${Utils.formatNumber(this.state.dbTotalCount)}</strong> total records
                    ${hasMoreData ? `<span class="text-muted">(${Utils.formatNumber(this.state.dbTotalCount - this.state.dbFetchedCount)} more available)</span>` : ''}
                </div>
                <div class="db-pagination-controls">
                    <button class="btn btn-sm btn-secondary" id="${this.options.viewName}_prevBatchBtn" ${dbBatchNumber === 1 ? 'disabled' : ''}>
                        ◀ Prev Batch
                    </button>
                    <span class="db-batch-indicator">Batch ${dbBatchNumber} of ${dbTotalBatches}</span>
                    <button class="btn btn-sm btn-secondary" id="${this.options.viewName}_nextBatchBtn" ${!hasMoreData ? 'disabled' : ''}>
                        Next Batch ▶
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Setup all event listeners (with proper cleanup)
     */
    setupEventListeners() {
        const container = this.container;
        if (!container) return;

        // ✅ CRITICAL FIX: Remove ALL old event listeners first
        // Clone and replace container to remove all listeners
        const newContainer = container.cloneNode(true);
        container.parentNode.replaceChild(newContainer, container);
        this.container = newContainer;

        // Now add fresh listeners to the new container
        
        // Search (with debounce)
        const searchInput = this.container.querySelector(`#${this.options.viewName}_searchInput`);
        if (searchInput) {
            let searchTimeout;
            searchInput.addEventListener('input', (e) => {
                this.state.searchQuery = e.target.value;
                
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    this.applyFilters();
                    this.updateDisplay();
                }, 800);
            });
        }

        // Page size
        const pageSizeSelect = this.container.querySelector(`#${this.options.viewName}_pageSizeSelect`);
        if (pageSizeSelect) {
            pageSizeSelect.addEventListener('change', (e) => {
                this.options.pageSize = parseInt(e.target.value);
                this.state.currentPage = 1;
                this.updateDisplay();
            });
        }

        // Pagination buttons
        const prevPageBtn = this.container.querySelector(`#${this.options.viewName}_prevPageBtn`);
        const nextPageBtn = this.container.querySelector(`#${this.options.viewName}_nextPageBtn`);
        
        if (prevPageBtn) {
            prevPageBtn.addEventListener('click', () => this.goToPage(this.state.currentPage - 1));
        }
        
        if (nextPageBtn) {
            nextPageBtn.addEventListener('click', () => this.goToPage(this.state.currentPage + 1));
        }

        // Page number buttons
        this.container.querySelectorAll('.pagination-btn[data-page]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const page = parseInt(e.target.dataset.page);
                this.goToPage(page);
            });
        });

        // Column selector checkboxes
        this.state.allColumns.forEach(col => {
            const checkbox = this.container.querySelector(`#col_${col}`);
            if (checkbox) {
                checkbox.addEventListener('change', (e) => {
                    if (e.target.checked) {
                        if (!this.state.visibleColumns.includes(col)) {
                            this.state.visibleColumns.push(col);
                        }
                    } else {
                        this.state.visibleColumns = this.state.visibleColumns.filter(c => c !== col);
                    }
                    
                    if (this.options.persistColumns) {
                        window.settings?.setTableColumns(this.options.viewName, this.state.visibleColumns);
                    }
                    
                    this.updateDisplay();
                });
            }
        });

        // Column selector buttons
        const selectAllBtn = this.container.querySelector(`#${this.options.viewName}_selectAllBtn`);
        const selectNoneBtn = this.container.querySelector(`#${this.options.viewName}_selectNoneBtn`);
        const resetColumnsBtn = this.container.querySelector(`#${this.options.viewName}_resetColumnsBtn`);

        if (selectAllBtn) {
            selectAllBtn.addEventListener('click', () => {
                this.state.visibleColumns = [...this.state.allColumns];
                if (this.options.persistColumns) {
                    window.settings?.setTableColumns(this.options.viewName, this.state.visibleColumns);
                }
                this.render();
                this.setupEventListeners();
            });
        }

        if (selectNoneBtn) {
            selectNoneBtn.addEventListener('click', () => {
                this.state.visibleColumns = [this.state.allColumns[0]];
                if (this.options.persistColumns) {
                    window.settings?.setTableColumns(this.options.viewName, this.state.visibleColumns);
                }
                this.render();
                this.setupEventListeners();
            });
        }

        if (resetColumnsBtn) {
            resetColumnsBtn.addEventListener('click', () => {
                const priorityCols = this.priorityColumns.filter(col => this.state.allColumns.includes(col));
                this.state.visibleColumns = priorityCols.length > 0 
                    ? priorityCols 
                    : this.state.allColumns.slice(0, 8);
                if (this.options.persistColumns) {
                    window.settings?.setTableColumns(this.options.viewName, this.state.visibleColumns);
                }
                this.render();
                this.setupEventListeners();
            });
        }

        // Sorting
        if (this.options.sortable) {
            this.container.querySelectorAll('.data-table th.sortable').forEach(th => {
                th.addEventListener('click', (e) => {
                    const column = e.target.dataset.column;
                    this.sortBy(column);
                });
            });
        }

        // Add filter button
        const addFilterBtn = this.container.querySelector(`#${this.options.viewName}_addFilterBtn`);
        if (addFilterBtn) {
            addFilterBtn.addEventListener('click', () => this.addFilterFromUI());
        }

        // Node Type filter
        const nodeTypeFilter = this.container.querySelector(`#${this.options.viewName}_nodeTypeFilter`);
        if (nodeTypeFilter) {
            nodeTypeFilter.addEventListener('change', (e) => {
                const value = e.target.value;
                if (value) {
                    this.addFilter({ column: 'node_type', operator: 'equals', value });
                } else {
                    this.state.filters = this.state.filters.filter(f => f.column !== 'node_type');
                    if (this.options.onFilterChange) {
                        this.options.onFilterChange(this.state.filters);
                    } else {
                        this.applyFilters();
                        this.updateDisplay();
                    }
                    this.renderActiveFilters();
                }
            });
        }

        // ✅ CRITICAL: DB Fetch Limit - single listener only
        const dbFetchLimitSelect = this.container.querySelector(`#${this.options.viewName}_dbFetchLimit`);
        if (dbFetchLimitSelect) {
            dbFetchLimitSelect.addEventListener('change', async (e) => {
                const newLimit = parseInt(e.target.value);
                // console.log(`🔄 DB Fetch Limit changed to: ${newLimit}, current state.dbLimit: ${this.state.dbLimit}`);
                this.state.dbLimit = newLimit;
                this.dbFetchLimit = newLimit;
                // console.log(`✅ Updated state.dbLimit to: ${this.state.dbLimit}`);
                
                if (this.options.onFetchBatch) {
                    await this.fetchBatch(0);
                    // console.log(`✅ After fetchBatch, state.dbLimit: ${this.state.dbLimit}`);
                } else {
                    notify.info('DB fetch limit updated. Reload data to apply.');
                }
            });
        }

        // Action buttons
        const analyzeBtn = this.container.querySelector(`#${this.options.viewName}_analyzeBtn`);
        const exportBtn = this.container.querySelector(`#${this.options.viewName}_exportBtn`);
        const closeBtn = this.container.querySelector(`#${this.options.viewName}_closeBtn`);

        if (analyzeBtn) {
            analyzeBtn.addEventListener('click', () => this.handleAnalyze());
        }

        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.handleExport());
        }

        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                if (this.options.onClose) {
                    this.options.onClose();
                } else {
                    this.container.style.display = 'none';
                }
            });
        }

        // DB Pagination
        const prevBatchBtn = this.container.querySelector(`#${this.options.viewName}_prevBatchBtn`);
        const nextBatchBtn = this.container.querySelector(`#${this.options.viewName}_nextBatchBtn`);

        if (prevBatchBtn) {
            prevBatchBtn.addEventListener('click', () => this.fetchPrevBatch());
        }

        if (nextBatchBtn) {
            nextBatchBtn.addEventListener('click', () => this.fetchNextBatch());
        }

        // console.log('✅ Event listeners attached (cleaned)');

        // ✅ CRITICAL FIX: Re-render header to reflect current state after clone
        this.updateHeaderDropdowns();
    }

    /**
     * ✅ NEW: Update header dropdowns to reflect current state
     * Called after setupEventListeners() which clones container
     */
    updateHeaderDropdowns() {
        // Update DB Fetch Limit dropdown
        const dbFetchLimitSelect = this.container.querySelector(`#${this.options.viewName}_dbFetchLimit`);
        if (dbFetchLimitSelect && this.state.dbLimit) {
            dbFetchLimitSelect.value = this.state.dbLimit;
            // console.log(`🔄 Updated dropdown to show: ${this.state.dbLimit}`);
        }
        
        // Update Node Type dropdown
        const nodeTypeFilter = this.container.querySelector(`#${this.options.viewName}_nodeTypeFilter`);
        if (nodeTypeFilter) {
            const nodeTypeFilter_value = this.state.filters.find(f => f.column === 'node_type')?.value || '';
            nodeTypeFilter.value = nodeTypeFilter_value;
        }
    }


    /**
     * Apply filters and search
     */
    applyFilters() {
        let filtered = [...this.state.data];

        // Apply search
        if (this.state.searchQuery) {
            const query = this.state.searchQuery.toLowerCase();
            filtered = filtered.filter(row => {
                return this.state.visibleColumns.some(col => {
                    const value = String(row[col] || '').toLowerCase();
                    return value.includes(query);
                });
            });
        }

        // Apply filters
        this.state.filters.forEach(filter => {
            filtered = filtered.filter(row => {
                const value = row[filter.column];
                return this.matchesFilter(value, filter);
            });
        });

        this.state.filteredData = filtered;
        this.state.currentPage = 1;
    }

    /**
     * Check if value matches filter
     */
    matchesFilter(value, filter) {
        const val = String(value || '').toLowerCase();
        const filterVal = String(filter.value || '').toLowerCase();

        switch (filter.operator) {
            case 'equals':
                return val === filterVal;
            case 'contains':
                return val.includes(filterVal);
            case 'starts_with':
                return val.startsWith(filterVal);
            case 'ends_with':
                return val.endsWith(filterVal);
            case 'not_empty':
                return val.length > 0;
            case 'empty':
                return val.length === 0;
            case 'greater_than':
                return parseFloat(value) > parseFloat(filter.value);
            case 'less_than':
                return parseFloat(value) < parseFloat(filter.value);
            default:
                return true;
        }
    }

    /**
     * Add filter from UI
     */
    addFilterFromUI() {
        const column = document.getElementById(`${this.options.viewName}_filterColumn`).value;
        const operator = document.getElementById(`${this.options.viewName}_filterOperator`).value;
        const value = document.getElementById(`${this.options.viewName}_filterValue`).value;

        if (!column) {
            notify.warning('Please select a column');
            return;
        }

        if (!value && operator !== 'not_empty' && operator !== 'empty') {
            notify.warning('Please enter a value');
            return;
        }

        this.addFilter({ column, operator, value });
    }

    /**
     * Add filter
     */
    addFilter(filter) {
        // Remove existing filter for same column
        this.state.filters = this.state.filters.filter(f => f.column !== filter.column);
        
        // Add new filter
        this.state.filters.push(filter);

        if (this.options.onFilterChange) {
            // ✅ FIXED: Render tags after callback completes
            Promise.resolve(this.options.onFilterChange(this.state.filters)).then(() => {
                setTimeout(() => this.renderActiveFilters(), 0);
            });
        } else {
            this.applyFilters();
            this.updateDisplay();
            // Tags will be rendered by updateDisplay()
        }
    }

    /**
     * Update display (re-render table and toolbar)
     */
    updateDisplay() {
        // Calculate display data
        const start = (this.state.currentPage - 1) * this.options.pageSize;
        const end = start + this.options.pageSize;
        this.state.displayData = this.state.filteredData.slice(start, end);

        // Re-render table and toolbar
        const tableWrapper = this.container.querySelector('.table-wrapper');
        if (tableWrapper) {
            tableWrapper.innerHTML = this.renderTable();
        }

        const toolbar = this.container.querySelector('.table-toolbar');
        if (toolbar) {
            toolbar.outerHTML = this.renderToolbar();
        }

        const footer = this.container.querySelector('.table-footer');
        if (footer) {
            footer.outerHTML = this.renderFooter();
        }

        // Re-attach event listeners (this clones container, destroying filter tags)
        this.setupEventListeners();
        
        // ✅ CRITICAL: Render filter tags AFTER setupEventListeners (which clones container)
        // Use setTimeout to ensure it runs after clone completes
        setTimeout(() => {
            if (this.options.filterable) {
                this.renderActiveFilters();
            }
        }, 0);
    }

    /**
     * Go to page
     */
    goToPage(page) {
        const totalPages = Math.ceil(this.state.filteredData.length / this.options.pageSize);
        if (page < 1 || page > totalPages) return;
        
        this.state.currentPage = page;
        this.updateDisplay();
    }

    /**
     * Sort by column
     */
    sortBy(column) {
        if (this.state.sortColumn === column) {
            this.state.sortDirection = this.state.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            this.state.sortColumn = column;
            this.state.sortDirection = 'asc';
        }

        this.state.filteredData.sort((a, b) => {
            const aVal = a[column];
            const bVal = b[column];
            
            if (aVal === bVal) return 0;
            if (aVal === null || aVal === undefined) return 1;
            if (bVal === null || bVal === undefined) return -1;
            
            const comparison = aVal < bVal ? -1 : 1;
            return this.state.sortDirection === 'asc' ? comparison : -comparison;
        });

        this.updateDisplay();
    }

    /**
     * Fetch next batch from DB
     */
    async fetchNextBatch() {
        if (this.state.dbFetchedCount >= this.state.dbTotalCount) {
            notify.info('All records loaded');
            return;
        }
        
        const nextOffset = this.state.dbOffset + this.state.dbLimit;
        await this.fetchBatch(nextOffset);
    }

    /**
     * Fetch previous batch from DB
     */
    async fetchPrevBatch() {
        if (this.state.dbOffset === 0) {
            notify.info('Already at first batch');
            return;
        }
        
        const prevOffset = Math.max(0, this.state.dbOffset - this.state.dbLimit);
        await this.fetchBatch(prevOffset);
    }

    /**
     * Fetch batch from DB
     */
    async fetchBatch(offset) {
        if (!this.options.onFetchBatch) {
            notify.error('Batch fetching not supported');
            return;
        }
        
        window.showLoading('Loading data...');
        try {
            const result = await this.options.onFetchBatch(offset, this.state.dbLimit, this.state.filters);
            
            this.state.data = result.data;
            this.state.dbOffset = offset;
            this.state.dbFetchedCount = offset + result.data.length;
            this.state.dbTotalCount = result.total;
            this.state.currentPage = 1;

            const totalPage = Math.floor(this.state.dbTotalCount / this.state.dbLimit) + 1
            
            this.applyFilters();
            this.updateDisplay();
            
            window.hideLoading();
            notify.success(`Loaded batch ${Math.floor(offset / this.state.dbLimit) + 1}/${totalPage}`);
        } catch (error) {
            window.hideLoading();
            notify.error(`Failed to load batch: ${error.message}`);
        }
    }

    /**
     * Handle analyze button
     */
    async handleAnalyze() {
        if (this.options.onAnalyze) {
            this.options.onAnalyze(this.state.filteredData);
        } else if (window.analyzerService) {
            // Filter data to only visible columns
            const filteredData = this.state.filteredData.map(row => {
                const filtered = {};
                this.state.visibleColumns.forEach(col => {
                    filtered[col] = row[col];
                });
                return filtered;
            });
            
            await window.analyzerService.analyze(filteredData, {
                source: this.context.source,
                name: this.context.tableName || this.context.jobId,
                showModal: true,
            });
        }
    }

    /**
     * Handle export button
     */
    handleExport() {
        if (this.options.onExport) {
            this.options.onExport(this.state.filteredData);
        } else if (window.exportComponent) {
            window.exportComponent.showExportModal(
                this.context.source,
                this.context.jobId || this.context.tableName,
                this.state.dbTotalCount,
                {
                    database: this.context.database,
                    filters: window.filterService?.convertToBackend(this.state.filters),
                    columns: this.state.visibleColumns,
                }
            );
        }
    }

    /**
     * Format column name for display
     */
    formatColumnName(name) {
        return name
            .replace(/_/g, ' ')
            .replace(/\b\w/g, l => l.toUpperCase());
    }

    /**
     * Format cell value
     */
    formatCellValue(value, column) {
        if (value === null || value === undefined || value === '') {
            return '<span style="color: var(--color-text-muted);">—</span>';
        }
        
        const str = String(value);
        if (str.length > 100) {
            return this.escapeHtml(str.substring(0, 100)) + '...';
        }
        
        return this.escapeHtml(str);
    }

    /**
     * Escape HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Destroy table
     */
    destroy() {
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

// Export for use in other components
window.UnifiedDataTable = UnifiedDataTable;
