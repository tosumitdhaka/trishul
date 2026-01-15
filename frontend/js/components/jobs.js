/* ============================================
   Jobs Component - Collapsible List View
   ============================================ */

class JobsComponent {
    constructor() {
        this.jobs = [];
        this.selectedJob = null;
        this.autoRefreshInterval = null;
        this.filterStatus = 'all';
        this.searchQuery = '';
        this.expandedJobs = new Set(); // Track expanded job cards
        this.currentDataView = null; // Track if viewing job data

        // ✅ NEW: WebSocket management
        this.websockets = new Map(); // Track WebSocket connections per job

        // ✅ NEW: Progress tracking for ETA
        this.jobTimestamps = new Map();

        this.pageSize = 1000;  // ✅ ADD
        this.currentPage = 1;  // ✅ ADD
        this.totalRecords = 0;  // ✅ ADD
        this.currentJobData = null;  // ✅ ADD
        this.jobDataTable = null;  // ✅ ADD

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadJobs();
        this.startAutoRefresh();
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = document.getElementById('refreshJobsBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', async () => {
                // Show loading state
                refreshBtn.disabled = true;
                refreshBtn.innerHTML = `
                    <svg class="btn-icon loading-spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M21 12a9 9 0 11-6.219-8.56"/>
                    </svg>
                    Refreshing...
                `;

                await this.loadJobs();

                // Restore button
                refreshBtn.disabled = false;
                refreshBtn.innerHTML = `
                    <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <polyline points="23 4 23 10 17 10"/>
                        <path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/>
                    </svg>
                    Refresh
                `;

                notify.success('Jobs refreshed');
            });
        }

        // ✅ UPDATED: Clear history button
        const clearHistoryBtn = document.getElementById('clearJobHistoryBtn');
        if (clearHistoryBtn) {
            clearHistoryBtn.addEventListener('click', () => {
                this.showCleanupModal();
            });
        }
    }

    // ============================================
    // ✅ NEW: PHASE INDICATORS
    // ============================================

    /**
     * Get phase icon and label
     */
    getPhaseInfo(phase) {
        const phases = {
            scanning: { icon: '🔍', label: 'Scanning', color: '#2196F3' },
            compiling: { icon: '⚙️', label: 'Compiling', color: '#FF9800' },
            parsing: { icon: '📝', label: 'Parsing', color: '#9C27B0' },
            enriching: { icon: '✨', label: 'Enriching', color: '#4CAF50' },
            deduplicating: { icon: '🔄', label: 'Deduplicating', color: '#00BCD4' },
            saving: { icon: '💾', label: 'Saving', color: '#3F51B5' },
            complete: { icon: '✅', label: 'Complete', color: '#4CAF50' },
            failed: { icon: '❌', label: 'Failed', color: '#F44336' },
        };

        return phases[phase] || { icon: '⏳', label: 'Processing', color: '#9E9E9E' };
    }

    /**
     * Render phase progress bar
     */
    renderPhaseProgress(job) {
        if (job.status !== 'running') {
            return '';
        }

        const allPhases = [
            'scanning',
            'compiling',
            'parsing',
            'enriching',
            'deduplicating',
            'saving',
        ];
        const currentPhaseIndex = allPhases.indexOf(job.phase);
        const currentPhase = job.phase || 'scanning';

        return `
            <div class="phase-progress">
                <div class="phase-steps">
                    ${allPhases
                        .map((phase, index) => {
                            const phaseInfo = this.getPhaseInfo(phase);
                            const isActive = index === currentPhaseIndex;
                            const isComplete = index < currentPhaseIndex;
                            const statusClass = isComplete
                                ? 'complete'
                                : isActive
                                  ? 'active'
                                  : 'pending';

                            return `
                            <div class="phase-step ${statusClass}" title="${phaseInfo.label}">
                                <div class="phase-icon" style="color: ${isActive || isComplete ? phaseInfo.color : '#ccc'}">
                                    ${phaseInfo.icon}
                                </div>
                                <div class="phase-label">${phaseInfo.label}</div>
                            </div>
                        `;
                        })
                        .join('')}
                </div>
            </div>
        `;
    }

    /**
     * ✅ COMPLETE FIX: Update progress without full re-render
     */
    updateJobProgress(jobId, progress, message, phase) {
        // Find job element
        const jobElement = document.querySelector(`.job-list-item[data-job-id="${jobId}"]`);
        if (!jobElement) {
            console.warn(`Job element not found: ${jobId}`);
            return;
        }

        // Get job data
        const job = this.jobs.find(j => j.job_id === jobId);
        if (!job) {
            console.warn(`Job data not found: ${jobId}`);
            return;
        }

        // Check if expanded
        const isExpanded = this.expandedJobs.has(jobId);

        // Update progress bar
        const progressBar = jobElement.querySelector('.progress-bar-fill');
        if (progressBar) {
            progressBar.style.width = `${Math.round(progress)}%`;
        }

        // Update progress text
        const progressText = jobElement.querySelector('.progress-text');
        if (progressText) {
            progressText.textContent = `${Math.round(progress)}% - ${message || 'Processing...'}`;
        }

        // ✅ CRITICAL FIX: Update ETA in progress-info container
        const progressInfo = jobElement.querySelector('.progress-info');
        if (progressInfo) {
            // Remove existing ETA
            const existingETA = progressInfo.querySelector('.job-eta');
            if (existingETA) {
                existingETA.remove();
            }
            
            // Add new ETA (job.eta_seconds is now updated)
            const newETAHtml = this.renderETA(job);
            if (newETAHtml) {
                progressInfo.insertAdjacentHTML('beforeend', newETAHtml);
            }
        }

        // Update phase progress if expanded
        if (isExpanded && phase) {
            const phaseProgress = jobElement.querySelector('.phase-progress');
            if (phaseProgress) {
                const newPhaseProgressHtml = this.renderPhaseProgress(job);
                if (newPhaseProgressHtml) {
                    phaseProgress.outerHTML = newPhaseProgressHtml;
                }
            }
        }
    }

    /**
     * Calculate estimated time remaining
     */
    calculateETA(job) {
        const jobId = job.job_id;
        const currentProgress = job.progress || 0;

        if (currentProgress === 0 || currentProgress >= 100) {
            return null;
        }

        // Get or initialize timestamp tracking
        if (!this.jobTimestamps.has(jobId)) {
            this.jobTimestamps.set(jobId, {
                startTime: Date.now(),
                lastProgress: 0,
                lastUpdate: Date.now(),
            });
            return null;
        }

        const timestamps = this.jobTimestamps.get(jobId);
        const now = Date.now();
        const elapsedMs = now - timestamps.startTime;

        // Update timestamps
        timestamps.lastProgress = currentProgress;
        timestamps.lastUpdate = now;

        // Calculate rate (progress per ms)
        const rate = currentProgress / elapsedMs;

        if (rate <= 0) {
            return null;
        }

        // Calculate remaining time
        const remainingProgress = 100 - currentProgress;
        const remainingMs = remainingProgress / rate;

        return remainingMs;
    }

    /**
     * Format time duration
     */
    formatDuration(ms) {
        if (!ms || ms < 0) {
            return 'Calculating...';
        }

        const seconds = Math.floor(ms / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);

        if (hours > 0) {
            return `${hours}h ${minutes % 60}m`;
        } else if (minutes > 0) {
            return `${minutes}m ${seconds % 60}s`;
        } else {
            return `${seconds}s`;
        }
    }

    /**
     * ✅ UPDATED: Render ETA using backend-provided value
     */
    renderETA(job) {
        if (job.status !== 'running') {
            return '';
        }
    
        // ✅ Use backend ETA if available
        if (job.eta_seconds !== undefined && job.eta_seconds !== null) {
            const etaMs = job.eta_seconds * 1000;
            const etaText = this.formatDuration(etaMs);
            
            return `
                <div class="job-eta">
                    <svg class="icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <circle cx="12" cy="12" r="10"/>
                        <polyline points="12 6 12 12 16 14"/>
                    </svg>
                    <span>ETA: ${etaText}</span>
                </div>
            `;
        }
    
        // ✅ Fallback to frontend calculation if backend ETA not available
        const etaMs = this.calculateETA(job);
        if (!etaMs) {
            return '';
        }
    
        const etaText = this.formatDuration(etaMs);
        
        return `
            <div class="job-eta">
                <svg class="icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <circle cx="12" cy="12" r="10"/>
                    <polyline points="12 6 12 12 16 14"/>
                </svg>
                <span>ETA: ${etaText}</span>
            </div>
        `;
    }

    // ============================================
    // ✅ NEW: JOB FILTERING & SEARCH
    // ============================================

    /**
     * Setup filter controls
     */
    setupFilterControls() {
        const header = document.querySelector('#jobsView .section-header');
        if (!header) return;

        // Check if already added
        if (document.getElementById('jobsFilterControls')) return;

        const controlsHTML = `
            <div class="jobs-filter-controls" id="jobsFilterControls">
                <select class="filter-select" id="jobsStatusFilter">
                    <option value="all">All Jobs</option>
                    <option value="running">Running</option>
                    <option value="queued">Queued</option>
                    <option value="completed">Completed</option>
                    <option value="failed">Failed</option>
                    <option value="cancelled">Cancelled</option>
                </select>
                
                <div class="search-box">
                    <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <circle cx="11" cy="11" r="8"/>
                        <path d="m21 21-4.35-4.35"/>
                    </svg>
                    <input 
                        type="text" 
                        class="search-input" 
                        id="jobsSearchInput"
                        placeholder="Search jobs..."
                    />
                </div>
            </div>
        `;

        // Insert before section-actions
        const actions = header.querySelector('.section-actions');
        if (actions) {
            actions.insertAdjacentHTML('beforebegin', controlsHTML);
        }

        // Add event listeners
        const statusFilter = document.getElementById('jobsStatusFilter');
        const searchInput = document.getElementById('jobsSearchInput');

        if (statusFilter) {
            statusFilter.value = this.filterStatus;
            statusFilter.addEventListener('change', (e) => {
                this.filterStatus = e.target.value;
                this.renderJobsList();
            });
        }

        if (searchInput) {
            searchInput.value = this.searchQuery;
            searchInput.addEventListener('input', (e) => {
                this.searchQuery = e.target.value.toLowerCase();
                this.renderJobsList();
            });
        }
    }

    /**
     * Filter jobs based on status and search
     */
    filterJobs(jobs) {
        let filtered = jobs;

        // Filter by status
        if (this.filterStatus !== 'all') {
            filtered = filtered.filter((job) => job.status === this.filterStatus);
        }

        // Filter by search query
        if (this.searchQuery) {
            filtered = filtered.filter((job) => {
                const jobName = (job.job_name || '').toLowerCase();
                const jobId = (job.job_id || '').toLowerCase();
                const message = (job.message || '').toLowerCase();

                return (
                    jobName.includes(this.searchQuery) ||
                    jobId.includes(this.searchQuery) ||
                    message.includes(this.searchQuery)
                );
            });
        }

        return filtered;
    }

    // ============================================
    // WEBSOCKET METHODS (from Phase 2)
    // ============================================
    /**
     * Connect to WebSocket for job progress
     */
    connectJobWebSocket(jobId) {
        if (this.websockets.has(jobId)) {
            // console.log(`WebSocket already connected for job ${jobId}`);
            return;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const wsUrl = `${protocol}//${host}/api/v1/jobs/ws/${jobId}`;

        // console.log(`🔌 Connecting to WebSocket: ${wsUrl}`);

        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log(`✅ WebSocket connected for job ${jobId}`);
            this.websockets.set(jobId, ws);

            const pingInterval = setInterval(() => {
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send('ping');
                } else {
                    clearInterval(pingInterval);
                }
            }, 10000);

            ws.pingInterval = pingInterval;
        };

        ws.onmessage = (event) => {
            try {
                if (event.data === 'pong') {
                    return;
                }

                const message = JSON.parse(event.data);

                if (message.topic && message.topic.startsWith('job:')) {
                    this.handleProgressUpdate(message.data);
                }
            } catch (error) {
                console.error('WebSocket message parse error:', error);
            }
        };

        ws.onerror = (error) => {
            console.error(`❌ WebSocket error for job ${jobId}:`, error);
        };

        ws.onclose = () => {
            // console.log(`🔌 WebSocket closed for job ${jobId}`);

            if (ws.pingInterval) {
                clearInterval(ws.pingInterval);
            }

            this.websockets.delete(jobId);
        };
    }

    disconnectJobWebSocket(jobId) {
        const ws = this.websockets.get(jobId);
        if (ws) {
            if (ws.pingInterval) {
                clearInterval(ws.pingInterval);
            }

            ws.close();
            this.websockets.delete(jobId);
            console.log(`🔌 Disconnected WebSocket for job ${jobId}`);
        }
    }

    handleProgressUpdate(data) {
        const { job_id, phase, percentage, message, metadata, eta_seconds } = data;
        const roundedPercentage = Math.round(percentage * 100) / 100;

        const job = this.jobs.find((j) => j.job_id === job_id);
        if (!job) {
            console.warn(`Job ${job_id} not found in list`);
            return;
        }

        // ✅ CRITICAL FIX: Update job data FIRST (before calling updateJobProgress)
        job.progress = roundedPercentage;
        job.message = message;
        job.phase = phase;
        job.eta_seconds = eta_seconds;  // ✅ Update BEFORE updateJobProgress

        if (phase === 'complete') {
            job.status = 'completed';
            job.completed_at = new Date().toISOString();
            job.result = metadata;
            this.disconnectJobWebSocket(job_id);
            this.jobTimestamps.delete(job_id);
            notify.success(`✅ Job completed: ${message}`);
            
            this.renderJobsList();
            this.updateStats();
            
        } else if (phase === 'failed') {
            job.status = 'failed';
            job.completed_at = new Date().toISOString();
            job.errors = [metadata.error || 'Unknown error'];
            this.disconnectJobWebSocket(job_id);
            this.jobTimestamps.delete(job_id);
            notify.error(`❌ Job failed: ${message}`);
            
            this.renderJobsList();
            this.updateStats();
            
        } else if (phase === 'cancelled') {
            job.status = 'cancelled';
            job.completed_at = new Date().toISOString();
            this.disconnectJobWebSocket(job_id);
            this.jobTimestamps.delete(job_id);
            notify.warning(`🚫 Job cancelled: ${message}`);
            
            this.renderJobsList();
            this.updateStats();
            
        } else {
            // ✅ NOW job.eta_seconds is already updated
            this.updateJobProgress(job_id, roundedPercentage, message, phase);
            this.updateStats();
        }
    }

    // ============================================
    // JOB LIST RENDERING (UPDATED)
    // ============================================

    async loadJobs() {
        try {
            const response = await api.listJobs();

            if (response && response.success) {
                this.jobs = response.jobs || [];
                this.jobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

                // ✅ FIX: Only connect WebSocket for truly active jobs
                this.jobs.forEach((job) => {
                    const currentProgress = job.progress || 0;
                    const isConnected = this.websockets.has(job.job_id);

                    // ✅ CRITICAL: Don't reconnect if progress is 100% (job is finishing)
                    const shouldConnect =
                        (job.status === 'running') &&
                        currentProgress < 100 && // ✅ Don't connect if 100%
                        !isConnected;

                    if (shouldConnect) {
                        console.log(
                            `🔌 Connecting WebSocket for job ${job.job_id} (${currentProgress}%)`
                        );
                        this.connectJobWebSocket(job.job_id);
                    } else if (isConnected && job.status !== 'running') {
                        // Disconnect if job is no longer running
                        console.log(`🔌 Disconnecting WebSocket for non-running job ${job.job_id}`);
                        this.disconnectJobWebSocket(job.job_id);
                    } else if (isConnected && currentProgress >= 100) {
                        // ✅ NEW: Disconnect if progress reached 100%
                        console.log(
                            `🔌 Disconnecting WebSocket for completed job ${job.job_id} (100%)`
                        );
                        this.disconnectJobWebSocket(job.job_id);
                    }
                });

                this.renderJobsList();
                this.updateStats();
            }
        } catch (error) {
            console.error('Failed to load jobs:', error);
            notify.error(`Failed to load jobs: ${error.message}`);
        }
    }

    renderJobsList() {
        const container = document.getElementById('jobsList');
        if (!container) return;
    
        if (this.currentDataView) return;
    
        // ✅ SIMPLIFIED: Always use list view
        container.className = 'jobs-list';
    
        // Setup filter controls
        this.setupFilterControls();
    
        // Apply filters
        let filteredJobs = this.filterJobs(this.jobs);
    
        if (filteredJobs.length === 0) {
            const emptyMessage = this.searchQuery
                ? `No jobs found matching "${this.searchQuery}"`
                : `No ${this.filterStatus === 'all' ? '' : this.filterStatus} jobs found`;
    
            container.innerHTML = `
                <div class="empty-state">
                    <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <circle cx="11" cy="11" r="8"/>
                        <path d="m21 21-4.35-4.35"/>
                    </svg>
                    <p class="empty-message">${emptyMessage}</p>
                    <p class="empty-hint">Try adjusting your filters or search query</p>
                </div>
            `;
            return;
        }
    
        // ✅ SIMPLIFIED: Only render list items
        container.innerHTML = filteredJobs.map((job) => this.renderJobListItem(job)).join('');
    }

    renderJobListItem(job) {
        const statusConfig = this.getStatusConfig(job.status);
        const progress = job.progress || 0;
        const isExpanded = this.expandedJobs.has(job.job_id);

        let result = {};
        if (job.result) {
            result = typeof job.result === 'string' ? JSON.parse(job.result) : job.result;
        }

        const hasData = result.has_data || false;

        return `
            <div class="job-list-item job-status-${job.status}" data-job-id="${job.job_id}">
                <div class="job-list-header">
                    <div class="job-list-icon" style="background: ${statusConfig.bgColor}; color: ${statusConfig.color};">
                        ${statusConfig.icon}
                    </div>
                    <div class="job-list-info">
                        <span class="job-list-title">${this.getJobTitle(job)}</span>
                        <span class="job-list-meta">
                            ${Utils.formatRelativeTime(job.created_at)}
                        </span>
                    </div>

                    ${result.missing_dependencies && result.missing_dependencies.length > 0 ? `
                        <button 
                            class="job-warning-badge clickable" 
                            onclick="jobsComponent.showMissingDepsModal('${job.job_id}'); event.stopPropagation();"
                            title="Click to view missing dependencies"
                        >
                            <svg class="icon-warning-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                                <line x1="12" y1="9" x2="12" y2="13"/>
                                <line x1="12" y1="17" x2="12.01" y2="17"/>
                            </svg>
                            <span>${result.missing_dependencies.length} missing dep${result.missing_dependencies.length > 1 ? 's' : ''}</span>
                        </button>
                    ` : ''}

                    ${
                        job.status === 'completed' && result.records_parsed
                            ? `
                        <div class="job-list-summary">
                            <div class="summary-stats">
                                <div class="summary-stat">
                                    <svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                        <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                                    </svg>
                                    <span>${Utils.formatNumber(result.records_parsed)} records</span>
                                </div>
                                ${
                                    result.performance && result.performance.parse_time_seconds
                                        ? `
                                    <div class="summary-stat">
                                        <svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                            <circle cx="12" cy="12" r="10"/>
                                            <polyline points="12 6 12 12 16 14"/>
                                        </svg>
                                        <span>${result.performance.parse_time_seconds.toFixed(1)}s</span>
                                    </div>
                                    <div class="summary-stat">
                                        <svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                                        </svg>
                                        <span>${result.performance.records_per_second.toFixed(1)} rec/s</span>
                                    </div>
                                `
                                        : ''
                                }
                            </div>
                        </div>
                    `
                            : ''
                    }

                    <div class="job-list-status">
                        <span class="status-badge status-${job.status}">${job.status.toUpperCase()}</span>
                        ${
                            job.status === 'queued'
                                ? `
                            <button class="btn btn-sm btn-danger" onclick="jobsComponent.cancelJob('${job.job_id}'); event.stopPropagation();" title="Cancel Job" style="margin-left: var(--spacing-sm);">
                                <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <circle cx="12" cy="12" r="10"/>
                                    <line x1="15" y1="9" x2="9" y2="15"/>
                                    <line x1="9" y1="9" x2="15" y2="15"/>
                                </svg>
                                Cancel
                            </button>
                        `
                                : ''
                        }
                    </div>
                    <div class="job-list-actions">
                        ${
                            job.status === 'completed' && hasData
                                ? `
                            <button class="btn btn-sm btn-primary" onclick="jobsComponent.loadJobData('${job.job_id}'); event.stopPropagation();" title="View Data">
                                <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                    <circle cx="12" cy="12" r="3"/>
                                </svg>
                                View
                            </button>
                            <button class="btn btn-sm btn-secondary" onclick="jobsComponent.showSaveToDbModal('${job.job_id}'); event.stopPropagation();" title="Save to Database">
                                <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/>
                                </svg>
                                Save
                            </button>
                            <button class="btn btn-sm btn-secondary" onclick="jobsComponent.exportJobResult('${job.job_id}'); event.stopPropagation();">
                                <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                                    <polyline points="7 10 12 15 17 10"/>
                                    <line x1="12" y1="15" x2="12" y2="3"/>
                                </svg>
                                Export
                            </button>
                            <button class="btn btn-sm btn-danger" onclick="jobsComponent.deleteJob('${job.job_id}'); event.stopPropagation();" title="Delete">
                                <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <polyline points="3 6 5 6 21 6"/>
                                    <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                                </svg>
                                Delete
                            </button>
                        `
                                : ''
                        }
                        
                        ${
                            job.status === 'failed' || job.status === 'cancelled'
                                ? `
                            <button class="btn btn-sm btn-secondary" onclick="jobsComponent.retryJob('${job.job_id}'); event.stopPropagation();" title="Retry Job">
                                <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <polyline points="23 4 23 10 17 10"/>
                                    <polyline points="1 20 1 14 7 14"/>
                                    <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>
                                </svg>
                                Retry
                            </button>
                            <button class="btn btn-sm btn-danger" onclick="jobsComponent.deleteJob('${job.job_id}'); event.stopPropagation();" title="Delete">
                                <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <polyline points="3 6 5 6 21 6"/>
                                    <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                                </svg>
                                Delete
                            </button>
                        `
                                : ''
                        }
                        <button class="btn btn-sm btn-icon job-expand-btn" onclick="jobsComponent.toggleJobExpansion('${job.job_id}'); event.stopPropagation();" title="${isExpanded ? 'Collapse' : 'Expand'}">
                            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" style="transform: rotate(${isExpanded ? '180' : '0'}deg); transition: transform 0.3s;">
                                <polyline points="6 9 12 15 18 9"/>
                            </svg>
                        </button>
                    </div>
                </div>
                
                ${job.status === 'running' ? `
                    ${isExpanded ? this.renderPhaseProgress(job) : ''}
                    
                    <div class="job-list-progress">
                        <div class="progress-bar-container">
                            <div class="progress-bar-fill" style="width: ${Math.round(progress)}%;">
                            </div>
                        </div>
                        <div class="progress-info">
                            <span class="progress-text">${Math.round(progress)}% - ${job.message || 'Processing...'}</span>
                            ${this.renderETA(job)}
                        </div>
                    </div>
                ` : ''}

                ${job.status === 'queued' ? `
                    <div class="job-list-progress">
                        <div class="progress-info">
                            <span class="progress-text">${job.message || 'Processing...'}</span>
                            ${this.renderETA(job)}
                        </div>
                    </div>
                ` : ''}
                
                ${
                    job.status === 'failed'
                        ? `
                    <div class="job-list-error">
                        <svg class="icon-error" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <circle cx="12" cy="12" r="10"/>
                            <line x1="12" y1="8" x2="12" y2="12"/>
                            <line x1="12" y1="16" x2="12.01" y2="16"/>
                        </svg>
                        <span>${this.getErrorMessage(job)}</span>
                    </div>
                `
                        : ''
                }
                
                ${
                    isExpanded
                        ? `
                    <div class="job-list-details">
                        <div class="detail-grid">
                            <div class="detail-item">
                                <span class="detail-label">Job ID</span>
                                <span class="detail-value"><code>${job.job_id}</code></span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Type</span>
                                <span class="detail-value">${job.job_type || 'parse'}</span>
                            </div>
                            ${(() => {
                                const metadata =
                                    typeof job.metadata === 'string'
                                        ? JSON.parse(job.metadata)
                                        : job.metadata || {};
                                const originalJobId = metadata.original_job_id;
                                const retryCount = metadata.retry_count || 0;

                                if (originalJobId) {
                                    return `
                                        <div class="detail-item">
                                            <span class="detail-label">Retry Count</span>
                                            <span class="detail-value">#${retryCount}</span>
                                        </div>
                                        <div class="detail-item">
                                            <span class="detail-label">Original Job</span>
                                            <span class="detail-value">
                                                <a href="#" onclick="jobsComponent.showJobDetails('${originalJobId}'); event.preventDefault();" style="color: var(--color-primary);">
                                                    ${originalJobId.substring(0, 8)}...
                                                </a>
                                            </span>
                                        </div>
                                    `;
                                }
                                return '';
                            })()}
                            <div class="detail-item">
                                <span class="detail-label">Created</span>
                                <span class="detail-value">${Utils.formatDateTime(job.created_at)}</span>
                            </div>
                            ${
                                job.started_at
                                    ? `
                                <div class="detail-item">
                                    <span class="detail-label">Started</span>
                                    <span class="detail-value">${Utils.formatDateTime(job.started_at)}</span>
                                </div>
                            `
                                    : ''
                            }
                            ${
                                job.completed_at
                                    ? `
                                <div class="detail-item">
                                    <span class="detail-label">Completed</span>
                                    <span class="detail-value">${Utils.formatDateTime(job.completed_at)}</span>
                                </div>
                                <div class="detail-item">
                                    <span class="detail-label">Duration</span>
                                    <span class="detail-value">${this.calculateDuration(job)}</span>
                                </div>
                            `
                                    : ''
                            }
                            ${
                                result.files_processed !== undefined
                                    ? `
                                <div class="detail-item">
                                    <span class="detail-label">Files Processed</span>
                                    <span class="detail-value">${result.files_processed}</span>
                                </div>
                            `
                                    : ''
                            }

                            ${
                                result.duplicates_removed !== undefined &&
                                result.duplicates_removed > 0
                                    ? `
                                <div class="detail-item">
                                    <span class="detail-label">Duplicates Removed</span>
                                    <span class="detail-value">${Utils.formatNumber(result.duplicates_removed)}</span>
                                </div>
                            `
                                    : ''
                            }

                            ${result.files_failed !== undefined && result.files_failed > 0 ? `
                                <div class="detail-item">
                                    <span class="detail-label">Files Failed</span>
                                    <div class="detail-value-with-toggle">
                                        <span class="detail-value error-value">${result.files_failed}</span>
                                        <button 
                                            class="btn-toggle-details" 
                                            onclick="jobsComponent.showFailedFilesModal('${job.job_id}'); event.stopPropagation();"
                                            title="View failed files"
                                        >
                                            <svg class="icon-eye" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                                <circle cx="12" cy="12" r="3"/>
                                            </svg>
                                        </button>
                                    </div>
                                </div>
                            ` : ''}

                            ${result.missing_dependencies && result.missing_dependencies.length > 0 ? `
                                <div class="detail-item">
                                    <span class="detail-label">Missing Dependencies</span>
                                    <div class="detail-value-with-toggle">
                                        <span class="detail-value warning-value">${result.missing_dependencies.length}</span>
                                        <button 
                                            class="btn-toggle-details" 
                                            onclick="jobsComponent.showMissingDepsModal('${job.job_id}'); event.stopPropagation();"
                                            title="View missing dependencies"
                                        >
                                            <svg class="icon-eye" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                                <circle cx="12" cy="12" r="3"/>
                                            </svg>
                                        </button>
                                    </div>
                                </div>
                            ` : ''}

                        </div>
                        
                        ${/* ✅ UPDATED: Performance Metrics with Phase Breakdown */ ''}
                        ${
                            job.status === 'completed' &&
                            result.performance &&
                            result.performance.parse_time_seconds
                                ? `
                            <div class="expanded-performance">
                                <h4 class="performance-title">
                                    <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                                    </svg>
                                    Performance Metrics
                                </h4>
                                
                                <!-- Summary Metrics -->
                                <div class="performance-grid-compact">
                                    <div class="performance-metric">
                                        <div class="metric-icon" style="background: #dbeafe; color: #2563eb;">
                                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                                <circle cx="12" cy="12" r="10"/>
                                                <polyline points="12 6 12 12 16 14"/>
                                            </svg>
                                        </div>
                                        <div class="metric-info">
                                            <div class="metric-label">Total Time</div>
                                            <div class="metric-value">${this.formatDuration(result.performance.total_time_seconds * 1000)}</div>
                                        </div>
                                    </div>
                                    
                                    <div class="performance-metric">
                                        <div class="metric-icon" style="background: #dcfce7; color: #16a34a;">
                                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                                            </svg>
                                        </div>
                                        <div class="metric-info">
                                            <div class="metric-label">Throughput</div>
                                            <div class="metric-value">${result.performance.records_per_second.toFixed(1)} rec/s</div>
                                        </div>
                                    </div>
                                    
                                    <div class="performance-metric">
                                        <div class="metric-icon" style="background: #fef3c7; color: #d97706;">
                                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                                <path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z"/>
                                                <polyline points="13 2 13 9 20 9"/>
                                            </svg>
                                        </div>
                                        <div class="metric-info">
                                            <div class="metric-label">File Rate</div>
                                            <div class="metric-value">${result.performance.files_per_second.toFixed(2)} files/s</div>
                                        </div>
                                    </div>
                                    
                                    <div class="performance-metric">
                                        <div class="metric-icon" style="background: #e0e7ff; color: #6366f1;">
                                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                                <line x1="12" y1="1" x2="12" y2="23"/>
                                                <path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/>
                                            </svg>
                                        </div>
                                        <div class="metric-info">
                                            <div class="metric-label">Avg per File</div>
                                            <div class="metric-value">${result.performance.average_file_time_seconds.toFixed(2)}s</div>
                                        </div>
                                    </div>
                                </div>
                                
                                ${/* ✅ NEW: Phase-Wise Breakdown */ ''}
                                ${result.performance.phase_timings ? `
                                    <div class="phase-breakdown-section">
                                        <h5 class="breakdown-title">Phase-Wise Time Breakdown</h5>
                                        
                                        <!-- Visual Bar -->
                                        <div class="breakdown-bar-compact">
                                            ${(() => {
                                                const phases = result.performance.phase_timings;
                                                const total = result.performance.total_time_seconds;
                                                
                                                const phaseColors = {
                                                    'scanning': '#10b981',
                                                    'compiling': '#8b5cf6',
                                                    'parsing': '#3b82f6',
                                                    'enriching': '#06b6d4',
                                                    'deduplicating': '#ef4444',
                                                    'saving': '#f59e0b',
                                                };
                                                
                                                const phaseIcons = {
                                                    'scanning': '🔍',
                                                    'compiling': '⚙️',
                                                    'parsing': '📝',
                                                    'enriching': '✨',
                                                    'deduplicating': '🔄',
                                                    'saving': '💾',
                                                };
                                                
                                                return Object.entries(phases).map(([phase, time]) => {
                                                    const percent = (time / total) * 100;
                                                    const color = phaseColors[phase] || '#94a3b8';
                                                    const icon = phaseIcons[phase] || '⏳';
                                                    
                                                    return `
                                                        <div class="breakdown-segment" 
                                                             style="width: ${percent}%; background: ${color};" 
                                                             title="${phase}: ${time.toFixed(2)}s (${percent.toFixed(1)}%)">
                                                            ${percent > 8 ? `<span>${icon} ${percent.toFixed(0)}%</span>` : ''}
                                                        </div>
                                                    `;
                                                }).join('');
                                            })()}
                                        </div>
                                        
                                        <!-- Legend -->
                                        <div class="breakdown-legend-compact">
                                            ${Object.entries(result.performance.phase_timings).map(([phase, time]) => {
                                                const phaseColors = {
                                                    'scanning': '#10b981',
                                                    'compiling': '#8b5cf6',
                                                    'parsing': '#3b82f6',
                                                    'enriching': '#06b6d4',
                                                    'deduplicating': '#ef4444',
                                                    'saving': '#f59e0b',
                                                };
                                                const color = phaseColors[phase] || '#94a3b8';
                                                const percent = (time / result.performance.total_time_seconds) * 100;
                                                
                                                return `
                                                    <span>
                                                        <span class="legend-dot" style="background: ${color};"></span>
                                                        ${phase.charAt(0).toUpperCase() + phase.slice(1)} (${time.toFixed(1)}s, ${percent.toFixed(1)}%)
                                                    </span>
                                                `;
                                            }).join('')}
                                        </div>
                                        
                                        <!-- Detailed Table -->
                                        <div class="phase-metrics-table" style="margin-top: var(--spacing-md);">
                                            <table style="width: 100%; border-collapse: collapse;">
                                                <thead>
                                                    <tr style="background: var(--color-surface); border-bottom: 2px solid var(--color-border);">
                                                        <th style="padding: var(--spacing-sm); text-align: left; font-size: var(--font-size-xs); text-transform: uppercase;">Phase</th>
                                                        <th style="padding: var(--spacing-sm); text-align: right; font-size: var(--font-size-xs); text-transform: uppercase;">Time</th>
                                                        <th style="padding: var(--spacing-sm); text-align: right; font-size: var(--font-size-xs); text-transform: uppercase;">% of Total</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    ${Object.entries(result.performance.phase_timings).map(([phase, time]) => {
                                                        const percent = (time / result.performance.total_time_seconds) * 100;
                                                        return `
                                                            <tr style="border-bottom: 1px solid var(--color-border);">
                                                                <td style="padding: var(--spacing-sm); font-size: var(--font-size-sm);">
                                                                    ${phase.charAt(0).toUpperCase() + phase.slice(1)}
                                                                </td>
                                                                <td style="padding: var(--spacing-sm); text-align: right; font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold);">
                                                                    ${time.toFixed(2)}s
                                                                </td>
                                                                <td style="padding: var(--spacing-sm); text-align: right; font-size: var(--font-size-sm); color: var(--color-text-secondary);">
                                                                    ${percent.toFixed(1)}%
                                                                </td>
                                                            </tr>
                                                        `;
                                                    }).join('')}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                ` : `
                                    <!-- Fallback: Old 2-phase breakdown -->
                                    <div class="time-breakdown">
                                        <div class="breakdown-label">Time Breakdown</div>
                                        <div class="breakdown-bar-compact">
                                            ${(() => {
                                                const parsePercent =
                                                    (result.performance.parse_time_seconds /
                                                        result.performance.total_time_seconds) *
                                                    100;
                                                const overheadPercent = 100 - parsePercent;
                                                return `
                                                    <div class="breakdown-segment" style="width: ${parsePercent}%; background: #3b82f6;" title="Parsing: ${result.performance.parse_time_seconds.toFixed(2)}s">
                                                        ${parsePercent > 10 ? `<span>${parsePercent.toFixed(0)}%</span>` : ''}
                                                    </div>
                                                    <div class="breakdown-segment" style="width: ${overheadPercent}%; background: #94a3b8;" title="Overhead: ${(result.performance.total_time_seconds - result.performance.parse_time_seconds).toFixed(2)}s">
                                                        ${overheadPercent > 10 ? `<span>${overheadPercent.toFixed(0)}%</span>` : ''}
                                                    </div>
                                                `;
                                            })()}
                                        </div>
                                        <div class="breakdown-legend-compact">
                                            <span><span class="legend-dot" style="background: #3b82f6;"></span> Parsing (${result.performance.parse_time_seconds.toFixed(1)}s)</span>
                                            <span><span class="legend-dot" style="background: #94a3b8;"></span> Overhead (${(result.performance.total_time_seconds - result.performance.parse_time_seconds).toFixed(1)}s)</span>
                                        </div>
                                    </div>
                                `}
                            </div>
                        `
                                : ''
                        }

                    </div>
                `
                        : ''
                }
            </div>
        `;
    }

    // ============================================
    // HELPER METHODS (keep all existing methods)
    // ============================================

    toggleJobExpansion(jobId) {
        if (this.expandedJobs.has(jobId)) {
            this.expandedJobs.delete(jobId);
        } else {
            this.expandedJobs.add(jobId);
        }
        this.renderJobsList();
    }

    /**
     * Show failed files modal - SIMPLIFIED
     */
    showFailedFilesModal(jobId) {
        const job = this.jobs.find(j => j.job_id === jobId);
        if (!job) return;
        
        const result = typeof job.result === 'string' ? JSON.parse(job.result) : job.result || {};
        const failedFiles = result.failed_files || [];
        
        if (failedFiles.length === 0) {
            notify.info('No failed files to display');
            return;
        }
        
        const content = `
            <div class="issues-modal-content">
                <div class="issues-modal-header">
                    <div class="issues-modal-icon error">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <circle cx="12" cy="12" r="10"/>
                            <line x1="15" y1="9" x2="9" y2="15"/>
                            <line x1="9" y1="9" x2="15" y2="15"/>
                        </svg>
                    </div>
                    <div class="issues-modal-title">
                        <h3>Failed Files</h3>
                        <p>${failedFiles.length} file${failedFiles.length > 1 ? 's' : ''} failed to parse</p>
                    </div>
                </div>
                
                <div class="issues-table-container">
                    <table class="issues-table">
                        <thead>
                            <tr>
                                <th style="width: 30%;">File Name</th>
                                <th style="width: 70%;">Error</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${failedFiles.map(f => `
                                <tr>
                                    <td>
                                        <div class="file-name-cell">
                                            <svg class="icon-file-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                                                <polyline points="14 2 14 8 20 8"/>
                                            </svg>
                                            <code>${f.filename}</code>
                                        </div>
                                    </td>
                                    <td>
                                        <span class="error-text">${f.error}</span>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        
        modal.show({
            title: '',
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
    }

    /**
     * Show missing dependencies modal - SIMPLIFIED
     */
    showMissingDepsModal(jobId) {
        const job = this.jobs.find(j => j.job_id === jobId);
        if (!job) return;
        
        const result = typeof job.result === 'string' ? JSON.parse(job.result) : job.result || {};
        const missingDeps = result.missing_dependencies || [];
        
        if (missingDeps.length === 0) {
            notify.info('No missing dependencies to display');
            return;
        }
        
        const content = `
            <div class="issues-modal-content">
                <div class="issues-modal-header">
                    <div class="issues-modal-icon warning">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                            <line x1="12" y1="9" x2="12" y2="13"/>
                            <line x1="12" y1="17" x2="12.01" y2="17"/>
                        </svg>
                    </div>
                    <div class="issues-modal-title">
                        <h3>Missing Dependencies</h3>
                        <p>${missingDeps.length} MIB dependenc${missingDeps.length > 1 ? 'ies' : 'y'} could not be found</p>
                    </div>
                </div>
                
                <div class="deps-grid">
                    ${missingDeps.map(dep => `
                        <div class="dep-badge">
                            <svg class="icon-package-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <line x1="16.5" y1="9.4" x2="7.5" y2="4.21"/>
                                <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/>
                                <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
                                <line x1="12" y1="22.08" x2="12" y2="12"/>
                            </svg>
                            <code>${dep}</code>
                        </div>
                    `).join('')}
                </div>
                
                <div class="issues-modal-footer">
                    <svg class="icon-info" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="16" x2="12" y2="12"/>
                        <line x1="12" y1="8" x2="12.01" y2="8"/>
                    </svg>
                    <span>These MIB files were referenced but not found in the search paths during compilation.</span>
                </div>
            </div>
        `;
        
        modal.show({
            title: '',
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
    }

    getStatusConfig(status) {
        const configs = {
            queued: { icon: '⏳', color: '#FF9800', bgColor: '#FFF3E0' },
            running: { icon: '⚙️', color: '#2196F3', bgColor: '#E3F2FD' },
            completed: { icon: '✅', color: '#4CAF50', bgColor: '#E8F5E9' },
            failed: { icon: '❌', color: '#F44336', bgColor: '#FFEBEE' },
            cancelled: { icon: '🚫', color: '#9E9E9E', bgColor: '#F5F5F5' },
        };
        return configs[status] || configs.queued;
    }

    getJobTitle(job) {
        let title = '';

        if (job.job_name) {
            title = job.job_name;
        } else {
            const typeMap = {
                parse: 'Parse MIB Files',
                parse_session: 'Parse MIB Files',
                import_data: 'Import Data',
                export_data: 'Export Data',
            };
            title = typeMap[job.job_type] || job.job_type;
        }

        // ✅ NEW: Add retry indicator
        const metadata =
            typeof job.metadata === 'string' ? JSON.parse(job.metadata) : job.metadata || {};
        const retryCount = metadata.retry_count || 0;

        if (retryCount > 0) {
            title += ` 🔄`; // Add retry emoji
        }

        return title;
    }

    /**
     * ✅ UPDATED: Load job data with pagination support
     */
    async loadJobData(jobId, page = 1, filters = []) {
        try {
            window.showLoading(`Loading data for job: ${jobId}...`);

            const tableName = `job_${jobId.replace(/-/g, '_')}_data`;
            // const tableInfo = await api.getUserTableInfo(tableName);
            const fetchLimit = (this.jobDataTable ? this.jobDataTable.state.dbLimit : this.pageSize);
            const offset = (page - 1) * fetchLimit;

            // console.log(`📊 Loading job data: limit=${fetchLimit}, offset=${offset}, page=${page}`);

            // Build SQL query
            const sql = window.filterService.buildSQLQuery(tableName, filters, {
                columns: ['*'],
                limit: fetchLimit,
                offset: offset,
                orderBy: 'notification_name ASC',
            });

            // console.log('📤 Executing SQL for job:', sql);

            const whereClause = window.filterService.extractWhereClause(sql);
            const orderByClause = window.filterService.extractOrderBy(sql);

            // Execute query using safe query endpoint
            const result = await api.database.query({
                table: tableName,
                database: 'jobs',
                columns: ['*'],
                where: whereClause,
                order_by: orderByClause,
                limit: fetchLimit,
                offset: offset,
            });

            window.hideLoading();

            if (!result.success) {
                throw new Error('Failed to load job data');
            }

            // Store current state
            this.currentJobData = {
                jobId: jobId,
                tableName: tableName,
                // info: tableInfo,
                data: result.data,
                total: result.total,
                filters: filters,
            };

            this.currentPage = page;
            this.totalRecords = result.total;

            // Display table
            this.displayJobData(jobId);

            const filterMsg =
                filters.length > 0
                    ? ` (${filters.length} filter${filters.length > 1 ? 's' : ''} applied)`
                    : '';
            notify.success(`Loaded ${result.returned} of ${result.total} records${filterMsg}`);

        } catch (error) {
            window.hideLoading();
            notify.error(`Failed to load job data: ${error.message}`);
            console.error('Load job data error:', error);
        }
    }

    /**
     * ✅ FIXED: Display job data
     */
    async displayJobData(jobId) {
        // console.log('📊 Displaying job data for:', jobId);

        const jobDataSection = document.getElementById('jobDataSection');
		
		
        if (jobDataSection) {
            jobDataSection.style.display = 'block';
            setTimeout(() => {
                jobDataSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 100);
        }

        const jobIdHeader = document.getElementById('currentJobId');
        if (jobIdHeader) {
            jobIdHeader.textContent = jobId.substring(0, 8) + '...';
        }

        // ✅ FIXED: Only destroy if job table doesn't exist or is for different job table
        if (this.jobDataTable) {
            const existingJobId = this.jobDataTable.context.jobId;

            if (existingJobId === jobId) {
                // ✅ Same job - just update data
                // console.log('♻️ Reusing existing job table, updating data...');
                this.jobDataTable.setData(this.currentJobData.data, this.currentJobData.total);

                // console.log('✅ Job data updated successfully');
                return; // ✅ Exit early
            } else {
                // Different job - destroy and recreate
                // console.log('🧹 Destroying old job data table (different job)...');
                this.jobDataTable.destroy();
                this.jobDataTable = null;
            }
        }

        // Create new table (only if doesn't exist or was destroyed)
        // console.log('🎨 Creating new UnifiedDataTable for job...');
        this.jobDataTable = new UnifiedDataTable('jobDataTableContainer', {
            title: `Job Data: ${jobId.substring(0, 8)}...`,
            tableName: this.currentJobData.tableName,
            viewName: 'job_data',
            searchable: true,
            sortable: true,
            filterable: true,
            exportable: true,
            analyzable: true,
            
            // ✅ NEW: Close callback
            onClose: () => {
                this.closeJobData();
            },
            
            // ✅ Filter change callback
            onFilterChange: (filters) => {
                console.log('🔄 Filter changed, reloading data');
                this.loadJobData(jobId, 1, filters);
            },
            
            // ✅ FIXED: Fetch batch callback (fetch directly without full reload)
            onFetchBatch: async (offset, limit, filters) => {
                console.log(`📡 Fetching batch: offset=${offset}, limit=${limit}`);
                
                try {
                    // Build SQL query
                    const sql = window.filterService.buildSQLQuery(this.currentJobData.tableName, filters, {
                        columns: ['*'],
                        limit: limit,
                        offset: offset,
                        orderBy: 'notification_name ASC',
                    });
                    
                    const whereClause = window.filterService.extractWhereClause(sql);
                    const orderByClause = window.filterService.extractOrderBy(sql);
                    
                    // Fetch data directly
                    const result = await api.database.query({
                        table: this.currentJobData.tableName,
                        database: 'jobs',
                        columns: ['*'],
                        where: whereClause,
                        order_by: orderByClause,
                        limit: limit,
                        offset: offset,
                    });
                    
                    if (result && result.success) {
                        // Update stored data
                        this.currentJobData.data = result.data;
                        this.currentJobData.total = result.total;
                        
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


        // Set context
        this.jobDataTable.context = {
            source: 'job',
            database: 'jobs',
            tableName: this.currentJobData.tableName,
            jobId: jobId,
        };
        // console.log('📋 Set job context:', this.jobDataTable.context);

        // Set data (skip default filter)
        // console.log('📥 Setting data:', this.currentJobData.data.length, 'rows, total:', this.currentJobData.total);
        this.jobDataTable.setData(this.currentJobData.data, this.currentJobData.total);
        // console.log('✅ Job data displayed successfully');

    }

    /**
     * ✅ NEW: Close job data view (hide inline section)
     */
    closeJobData() {
        const jobDataSection = document.getElementById('jobDataSection');
        if (jobDataSection) {
            jobDataSection.style.display = 'none';
        }

        if (this.jobDataTable) {
            this.jobDataTable.destroy();
            this.jobDataTable = null;
        }

        this.currentJobData = null;
    }

    /**
     * ✅ FIXED: Handle export with correct table reference
     */
    handleExport(data) {
        if (!this.currentJobData) {
            notify.warning('No job data loaded');
            return;
        }

        // console.log('📤 Exporting job with UI filters:', this.currentJobData.filters);

        // ✅ Convert UI filters to backend format
        const backendFilters =
            this.currentJobData.filters && this.currentJobData.filters.length > 0
                ? window.filterService.convertToBackend(this.currentJobData.filters)
                : null;

        // console.log('📤 Converted to backend filters:', backendFilters);

        // ✅ FIXED: Use loaded data count instead of total (respect limit)
        const exportCount = this.currentJobData.data.length;

        if (window.exportComponent) {
            window.exportComponent.showExportModal(
                'job',
                this.currentJobData.jobId,
                exportCount,  // ✅ CHANGED from this.currentJobData.total
                {
                    database: 'jobs',
                    filters: backendFilters,
                    columns: this.jobDataTable?.state?.visibleColumns || [],
                    limit: exportCount  // ✅ NEW: Pass limit explicitly
                }
            );
        }
    }


    /**
     * ✅ RENAMED: Handle analyze (was handleJobAnalyze)
     */
    async handleAnalyze(data) {
        if (!data || data.length === 0) {
            notify.warning('No data to analyze');
            return;
        }

        const jobTitle = this.currentJobData?.jobId
            ? `Job ${this.currentJobData.jobId.substring(0, 8)}...`
            : 'Unknown Job';

        await window.analyzerService.analyze(data, {
            source: 'job',
            name: jobTitle,
            showModal: true,
        });
    }

    /**
     * Get error message
     */
    getErrorMessage(job) {
        if (job.errors && Array.isArray(job.errors) && job.errors.length > 0) {
            return job.errors[0];
        }
        return job.message || 'Unknown error occurred';
    }

    /**
     * Show "Save to Database" modal
     */
    async showSaveToDbModal(jobId) {
        const job = this.jobs.find((j) => j.job_id === jobId);
        if (!job) return;

        const result = typeof job.result === 'string' ? JSON.parse(job.result) : job.result;
        const recordsCount = result.records_parsed || 0;

        const content = `
            <div class="save-to-db-modal">
                <p style="margin-bottom: 1.5rem; color: var(--color-text-secondary);">
                    Save ${Utils.formatNumber(recordsCount)} parsed records to your database for long-term storage.
                </p>
                
                <div class="form-group">
                    <label for="saveTableName">Table Name</label>
                    <input 
                        type="text" 
                        id="saveTableName" 
                        class="form-input" 
                        placeholder="e.g., cisco_mibs"
                        value="${this.suggestTableName(job)}"
                    />
                    <small style="color: var(--color-text-tertiary); display: block; margin-top: 0.5rem;">
                        Use letters, numbers, and underscores only
                    </small>
                </div>

                <div class="info-box" style="background: var(--color-info-bg); border-left: 4px solid var(--color-info); padding: 1rem; border-radius: var(--radius-md); margin-top: 1rem;">
                    <strong>Note:</strong> This will copy data from temporary storage to your permanent database.
                    The job data will remain available until you delete it.
                </div>
            </div>
        `;

        modal.show({
            title: 'Save to Database',
            content: content,
            size: 'medium',
            buttons: [
                {
                    text: 'Cancel',
                    class: 'btn-secondary',
                    onClick: () => modal.close(),
                },
                {
                    text: 'Save',
                    class: 'btn-primary',
                    onClick: async () => {
                        const tableName = document.getElementById('saveTableName').value.trim();

                        if (!tableName) {
                            notify.error('Please enter a table name');
                            return;
                        }

                        if (!/^[a-zA-Z][a-zA-Z0-9_]*$/.test(tableName)) {
                            notify.error(
                                'Invalid table name. Use letters, numbers, and underscores only.'
                            );
                            return;
                        }

                        modal.close();
                        await this.saveJobToDatabase(jobId, tableName);
                    },
                },
            ],
        });

        // Focus input
        setTimeout(() => {
            const input = document.getElementById('saveTableName');
            if (input) {
                input.focus();
                input.select();
            }
        }, 100);
    }

    /**
     * ✅ FIXED: Export job result (simplified - just pass job ID)
     */
    async exportJobResult(jobId) {
        // Get job info
        const job = this.jobs.find((j) => j.job_id === jobId);
        if (!job) {
            notify.error('Job not found');
            return;
        }

        const recordCount = job.result?.records_parsed || job.result?.total_records || 0;

        // ✅ Show export modal with job source type
        if (window.exportComponent) {
            window.exportComponent.showExportModal(
                'job', // Source type
                jobId, // Just pass job ID (backend will handle table lookup)
                recordCount
            );
        } else {
            // Fallback: direct export
            await window.exportService.export({
                source: 'job',
                name: jobId,
                format: 'csv',
            });
        }
    }

    /**
     * Suggest table name based on job
     */
    suggestTableName(job) {
        if (job.job_name) {
            return job.job_name
                .toLowerCase()
                .replace(/[^a-z0-9_]/g, '_')
                .replace(/^[0-9]/, 'tbl_$&')
                .substring(0, 64);
        }
        return 'mib_data';
    }

    /**
     * Save job to database
     */
    async saveJobToDatabase(jobId, tableName) {
        try {
            window.showLoading(`Saving to database table: ${tableName}...`);

            const response = await api.saveJobToDatabase(jobId, tableName);

            window.hideLoading();

            if (response && response.success) {
                notify.success(
                    `Saved ${Utils.formatNumber(response.records)} records to ${tableName}`
                );

                // Refresh database tables list
                if (window.databaseComponent) {
                    await window.databaseComponent.loadTables();
                }

                // Show success action
                const action = await modal.confirm({
                    title: 'Data Saved Successfully',
                    message: `${Utils.formatNumber(response.records)} records have been saved to table "${tableName}". Would you like to view the data now?`,
                    confirmText: 'View in Database',
                    cancelText: 'Stay Here',
                    type: 'success',
                });

                if (action) {
                    // Switch to database tab
                    const dbTab = document.querySelector('[data-view="database"]');
                    if (dbTab) dbTab.click();
                }
            } else {
                notify.error('Failed to save to database');
            }
        } catch (error) {
            window.hideLoading();
            console.error('Save to database failed:', error);
            notify.error(`Failed to save: ${error.message}`);
        }
    }

    /**
     * Show job details
     */
    async showJobDetails(jobId) {
        try {
            window.showLoading('Loading job details...');

            window.hideLoading();

        } catch (error) {
            window.hideLoading();
            console.error('Failed to load job details:', error);
            notify.error(`Failed to load details: ${error.message}`);
        }
    }

    /**
     * Calculate duration
     */
    calculateDuration(job) {
        if (!job.started_at || !job.completed_at) return 'N/A';

        const start = new Date(job.started_at);
        const end = new Date(job.completed_at);
        const duration = (end - start) / 1000;

        if (duration < 60) {
            return `${Math.round(duration)}s`;
        } else if (duration < 3600) {
            const minutes = Math.floor(duration / 60);
            const seconds = Math.round(duration % 60);
            return `${minutes}m ${seconds}s`;
        } else {
            const hours = Math.floor(duration / 3600);
            const minutes = Math.floor((duration % 3600) / 60);
            return `${hours}h ${minutes}m`;
        }
    }

    /**
     * Delete job
     */
    async deleteJob(jobId) {
        const confirmed = await modal.confirm({
            title: 'Delete Job',
            message:
                'Are you sure you want to delete this job? This will also delete the associated data.',
            confirmText: 'Delete',
            cancelText: 'Cancel',
            danger: true,
        });

        if (!confirmed) return;

        try {
            window.showLoading('Deleting job...');

            await api.deleteJob(jobId, true);

            window.hideLoading();

            notify.success('Job deleted successfully');

            // Reload jobs
            await this.loadJobs();
        } catch (error) {
            window.hideLoading();
            console.error('Delete job failed:', error);
            notify.error(`Failed to delete job: ${error.message}`);
        }
    }

    /**
     * Cancel a queued job
     */
    async cancelJob(jobId) {
        const confirmed = await modal.confirm({
            title: 'Cancel Job',
            message: 'Are you sure you want to cancel this job? This action cannot be undone.',
            confirmText: 'Cancel Job',
            cancelText: 'Keep Running',
            danger: true,
        });

        if (!confirmed) return;

        try {
            window.showLoading('Requesting cancellation...');

            const response = await api.cancelJob(jobId);

            window.hideLoading();

            if (response && response.success) {
                notify.info('✅ Jobs cancelled and removed');
            } else {
                notify.error('Failed to cancel job');
            }
        } catch (error) {
            window.hideLoading();
            console.error('Cancel job failed:', error);
            notify.error(`Failed to cancel: ${error.message}`);
        }
    }

    /**
     * Retry a failed or cancelled job
     */
    async retryJob(jobId) {
        const job = this.jobs.find((j) => j.job_id === jobId);
        if (!job) {
            notify.error('Job not found');
            return;
        }

        const confirmed = await modal.confirm({
            title: 'Retry Job',
            message: `Retry this job with the same files and settings?\n\nJob: ${this.getJobTitle(job)}`,
            confirmText: 'Retry Job',
            cancelText: 'Cancel',
            type: 'warning',
        });

        if (!confirmed) return;

        try {
            window.showLoading('Starting job retry...');

            const response = await api.retryJob(jobId);

            window.hideLoading();

            if (response && response.success) {
                notify.success(`✅ Job retry started: ${response.message}`);

                // Refresh jobs list to show new job
                await this.loadJobs();

                // Scroll to top to see new job
                window.scrollTo({ top: 0, behavior: 'smooth' });
            } else {
                notify.error('Failed to retry job');
            }
        } catch (error) {
            window.hideLoading();
            console.error('Retry job failed:', error);

            // Show user-friendly error message
            let errorMsg = error.message;
            if (errorMsg.includes('no longer available')) {
                errorMsg = 'Original files are no longer available. Please re-upload the files.';
            } else if (errorMsg.includes('session information not found')) {
                errorMsg = 'Cannot retry: job information incomplete. Please re-upload the files.';
            }

            notify.error(`Failed to retry: ${errorMsg}`);
        }
    }

    /**
     * Show cleanup modal with preview
     */
    async showCleanupModal() {
        try {
            window.showLoading('Loading cleanup preview...');

            // Get preview
            const preview = await api.previewCleanup();

            window.hideLoading();

            const stats = preview.statistics;

            if (stats.eligible_for_deletion === 0) {
                notify.info('No old jobs to clean up');
                return;
            }

            // Show confirmation with preview
            const confirmed = await modal.confirm({
                title: 'Clean Up Old Jobs',
                message: `
                    <div class="cleanup-preview">
                        <p>The following jobs will be permanently deleted:</p>
                        <ul class="cleanup-stats">
                            <li><strong>${stats.eligible_for_deletion}</strong> jobs older than 30 days</li>
                            <li><strong>${stats.total_jobs - stats.eligible_for_deletion}</strong> jobs will be kept</li>
                        </ul>
                        <p class="warning-text">⚠️ This action cannot be undone!</p>
                    </div>
                `,
                confirmText: 'Delete Old Jobs',
                cancelText: 'Cancel',
                danger: true,
            });

            if (!confirmed) return;

            // Execute cleanup
            window.showLoading('Cleaning up old jobs...');

            const result = await api.cleanupJobs(false);

            window.hideLoading();

            if (result && result.success) {
                const deleted = result.statistics.deleted;
                const failed = result.statistics.failed;

                if (failed > 0) {
                    notify.warning(`⚠️ Deleted ${deleted} jobs, ${failed} failed`);
                } else {
                    notify.success(`✅ Successfully deleted ${deleted} old jobs`);
                }

                // Refresh jobs list
                await this.loadJobs();
            } else {
                notify.error('Cleanup failed');
            }
        } catch (error) {
            window.hideLoading();
            console.error('Cleanup failed:', error);
            notify.error(`Cleanup failed: ${error.message}`);
        }
    }

    /**
     * Update statistics
     */
    updateStats() {
        const stats = {
            total: this.jobs.length,
            queued: this.jobs.filter((j) => j.status === 'queued').length,
            running: this.jobs.filter((j) => j.status === 'running').length,
            completed: this.jobs.filter((j) => j.status === 'completed').length,
            failed: this.jobs.filter((j) => j.status === 'failed').length,
        };

        const statsContainer = document.getElementById('jobsStats');
        if (statsContainer) {
            statsContainer.innerHTML = `
                <div class="stat-card">
                    <div class="stat-value">${stats.total}</div>
                    <div class="stat-label">Total Jobs</div>
                </div>
                <div class="stat-card stat-running">
                    <div class="stat-value">${stats.running}</div>
                    <div class="stat-label">Running</div>
                </div>
                <div class="stat-card stat-completed">
                    <div class="stat-value">${stats.completed}</div>
                    <div class="stat-label">Completed</div>
                </div>
                <div class="stat-card stat-failed">
                    <div class="stat-value">${stats.failed}</div>
                    <div class="stat-label">Failed</div>
                </div>
            `;
        }
    }

    /**
     * Start auto-refresh (less frequent, WebSocket handles real-time)
     */
    startAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
        }

        // ✅ Wait for backend settings if not loaded yet
        if (!window.settings.isBackendLoaded()) {
            // console.log('⏳ Waiting for backend settings...');
            setTimeout(() => this.startAutoRefresh(), 500);  // Retry in 500ms
            return;
        }

        // ✅ Get interval from backend config
        const intervalSeconds = window.settings?.getBackend('jobs.auto_refresh_interval', 15);
        const intervalMs = intervalSeconds * 1000;

        // console.log(`Auto-refresh enabled: ${intervalSeconds}s interval`);

        this.autoRefreshInterval = setInterval(() => {
            // ✅ FIXED: Check for queued OR running jobs without WebSocket
            const hasJobsNeedingRefresh  = this.jobs.some(
                (j) =>
                    // Queued jobs (no WebSocket needed)
                    (j.status === 'queued') ||
                    // Running jobs without WebSocket (connection failed/lost)
                    (j.status === 'running' && !this.websockets.has(j.job_id))
            );
            if (hasJobsNeedingRefresh ) {
                // console.log('⏰ Auto-refresh: Loading jobs (queued or no WebSocket)');
                this.loadJobs();
            }
        }, intervalMs);
    }

    /**
     * Stop auto-refresh
     */
    stopAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
        }
    }

    /**
     * Cleanup on destroy
     */
    destroy() {
        this.stopAutoRefresh();

        console.log(`🧹 Closing ${this.websockets.size} WebSocket connections`);
        this.websockets.forEach((ws, jobId) => {
            if (ws.pingInterval) {
                clearInterval(ws.pingInterval);
            }
            ws.close();
        });
        this.websockets.clear();
        this.jobTimestamps.clear();
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.jobsComponent = new JobsComponent();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.jobsComponent) {
        window.jobsComponent.destroy();
    }
});
