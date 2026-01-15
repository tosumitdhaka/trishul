/* ============================================
   Analyzer Component - FIXED
   ============================================ */

class AnalyzerComponent {
    constructor() {
        this.availableMetrics = [];
        this.init();
    }

    async init() {
        await this.loadAvailableMetrics();
        await this.loadDataSources(); // ✅ ADDED
        this.setupEventListeners();
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        const analyzeBtn = document.getElementById('analyzeBtn');
        if (analyzeBtn) {
            analyzeBtn.addEventListener('click', () => {
                this.runAnalysis();
            });
        }
    }

    /**
     * Load available data sources (tables)
     */
    async loadDataSources() {
        try {
            const tables = await api.listUserTables();
            const sourceSelect = document.getElementById('analyzeSource');

            if (sourceSelect && tables && tables.length > 0) {
                sourceSelect.innerHTML = `
                    <option value="">Select a table...</option>
                    ${tables
                        .map(
                            (table) => `
                        <option value="${table.name}">${table.name} (${Utils.formatNumber(table.row_count)} rows)</option>
                    `
                        )
                        .join('')}
                `;
            }
        } catch (error) {
            console.error('Failed to load data sources:', error);
        }
    }

    /**
     * Load available metrics
     */
    async loadAvailableMetrics() {
        try {
            const response = await api.get('/analyzer/metrics');
            if (response && response.metrics) {
                this.availableMetrics = response.metrics;
                this.displayMetricsOptions(response.metrics);
            } else {
                throw new Error('Invalid metrics response');
            }
        } catch (error) {
            console.error('Failed to load metrics:', error);
            // Use default metrics
            this.displayMetricsOptions({
                all: 'All Metrics',
                quality: 'Data Quality',
                statistics: 'Statistics',
                completeness: 'Completeness',
                consistency: 'Consistency',
                relationships: 'Relationships',
            });
        }
    }

    /**
     * Display metrics options
     */
    displayMetricsOptions(metrics) {
        const metricsGroup = document.getElementById('metricsGroup');
        if (!metricsGroup) return;

        metricsGroup.innerHTML = Object.entries(metrics)
            .map(([key, label]) => {
                const checkboxId = `metric_${key}`;
                return `
                <label class="checkbox-label" for="${checkboxId}">
                    <input type="checkbox" id="${checkboxId}" name="metric_${key}" value="${key}" ${key === 'all' ? 'checked' : ''}>
                    <span>${label}</span>
                </label>
            `;
            })
            .join('');

        // Handle "All" checkbox
        const allCheckbox = metricsGroup.querySelector('input[value="all"]');
        if (allCheckbox) {
            allCheckbox.addEventListener('change', (e) => {
                const checkboxes = metricsGroup.querySelectorAll('input[type="checkbox"]');
                checkboxes.forEach((cb) => {
                    if (cb !== allCheckbox) {
                        cb.checked = e.target.checked;
                        cb.disabled = e.target.checked;
                    }
                });
            });
        }
    }

    /**
     * Run analysis - FIXED
     */
    async runAnalysis() {
        const source = document.getElementById('analyzeSource')?.value;

        if (!source) {
            notify.warning('Please select a data source');
            return;
        }

        // Get selected metrics
        const checkboxes = document.querySelectorAll(
            '#metricsGroup input[type="checkbox"]:checked'
        );
        const metrics = Array.from(checkboxes).map((cb) => cb.value);

        if (metrics.length === 0) {
            notify.warning('Please select at least one metric');
            return;
        }

        try {
            window.showLoading('Running analysis...');

            // ✅ FIX: Pass data array instead of source string
            // First, fetch the table data
            const tableData = await api.getUserTableData(source, { limit: 10000 });

            if (!tableData || !tableData.data || tableData.data.length === 0) {
                window.hideLoading();
                notify.warning('No data available in selected table');
                return;
            }

            // Now analyze the data
            const results = await api.analyzeData(tableData.data, metrics);

            window.hideLoading();

            if (results && results.length > 0) {
                notify.success('Analysis completed successfully');
                this.displayAnalysisResults(results);

                // ✅ Show results section
                const resultsSection = document.getElementById('analysisResults');
                if (resultsSection) {
                    resultsSection.style.display = 'block';
                    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            } else {
                notify.warning('No analysis results returned');
            }
        } catch (error) {
            window.hideLoading();
            console.error('Analysis failed:', error);
            notify.error(`Analysis failed: ${error.message}`);
        }
    }

    /**
     * Display analysis results
     */
    displayAnalysisResults(results) {
        const analysisResults = document.getElementById('analysisResults');
        if (!analysisResults) return;

        if (!results || results.length === 0) {
            analysisResults.innerHTML = `
                <div class="empty-state">
                    <p class="empty-message">No analysis results available</p>
                </div>
            `;
            return;
        }

        analysisResults.innerHTML = results
            .map((result) => {
                return this.renderAnalysisCard(result);
            })
            .join('');
    }

    /**
     * Render analysis card
     */
    renderAnalysisCard(result) {
        const { metric, result: data } = result;

        // Different rendering based on metric type
        switch (metric) {
            case 'quality':
                return this.renderQualityCard(data);
            case 'statistics':
                return this.renderStatisticsCard(data);
            case 'completeness':
                return this.renderCompletenessCard(data);
            case 'consistency':
                return this.renderConsistencyCard(data);
            case 'relationships':
                return this.renderRelationshipsCard(data);
            default:
                return this.renderGenericCard(metric, data);
        }
    }

    /**
     * Render quality card
     */
    renderQualityCard(data) {
        const score = data.quality_score || data.score || 0;
        const scoreColor =
            score >= 90
                ? 'var(--color-success)'
                : score >= 70
                  ? 'var(--color-warning)'
                  : 'var(--color-danger)';

        return `
            <div class="analysis-card">
                <div class="analysis-header">
                    <svg class="analysis-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M22 11.08V12a10 10 0 11-5.93-9.14"/>
                        <polyline points="22 4 12 14.01 9 11.01"/>
                    </svg>
                    <h3 class="analysis-title">Data Quality</h3>
                </div>
                <div class="analysis-body">
                    <div style="text-align: center; margin-bottom: 1.5rem;">
                        <div style="font-size: 3rem; font-weight: bold; color: ${scoreColor};">
                            ${score.toFixed(1)}%
                        </div>
                        <div class="progress-bar-container" style="margin-top: 1rem;">
                            <div class="progress-bar-fill" style="width: ${score}%; background-color: ${scoreColor};"></div>
                        </div>
                    </div>
                    ${this.renderMetrics(data.metrics || data)}
                </div>
            </div>
        `;
    }

    /**
     * Render statistics card
     */
    renderStatisticsCard(data) {
        return `
            <div class="analysis-card">
                <div class="analysis-header">
                    <svg class="analysis-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <line x1="18" y1="20" x2="18" y2="10"/>
                        <line x1="12" y1="20" x2="12" y2="4"/>
                        <line x1="6" y1="20" x2="6" y2="14"/>
                    </svg>
                    <h3 class="analysis-title">Statistics</h3>
                </div>
                <div class="analysis-body">
                    <div class="stats-grid">
                        ${Object.entries(data)
                            .map(
                                ([key, value]) => `
                            <div class="stat-card">
                                <div class="stat-value">${typeof value === 'number' ? Utils.formatNumber(value) : value}</div>
                                <div class="stat-label">${key.replace(/_/g, ' ')}</div>
                            </div>
                        `
                            )
                            .join('')}
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render completeness card
     */
    renderCompletenessCard(data) {
        return `
            <div class="analysis-card">
                <div class="analysis-header">
                    <svg class="analysis-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <polyline points="9 11 12 14 22 4"/>
                        <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
                    </svg>
                    <h3 class="analysis-title">Completeness</h3>
                </div>
                <div class="analysis-body">
                    ${this.renderMetrics(data.fields || data)}
                </div>
            </div>
        `;
    }

    /**
     * Render consistency card
     */
    renderConsistencyCard(data) {
        return `
            <div class="analysis-card">
                <div class="analysis-header">
                    <svg class="analysis-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/>
                    </svg>
                    <h3 class="analysis-title">Consistency</h3>
                </div>
                <div class="analysis-body">
                    ${this.renderMetrics(data.checks || data)}
                </div>
            </div>
        `;
    }

    /**
     * Render relationships card
     */
    renderRelationshipsCard(data) {
        return `
            <div class="analysis-card">
                <div class="analysis-header">
                    <svg class="analysis-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>
                        <circle cx="9" cy="7" r="4"/>
                        <path d="M23 21v-2a4 4 0 00-3-3.87"/>
                        <path d="M16 3.13a4 4 0 010 7.75"/>
                    </svg>
                    <h3 class="analysis-title">Relationships</h3>
                </div>
                <div class="analysis-body">
                    ${this.renderMetrics(data.relationships || data)}
                </div>
            </div>
        `;
    }

    /**
     * Render generic card
     */
    renderGenericCard(metric, data) {
        return `
            <div class="analysis-card">
                <div class="analysis-header">
                    <h3 class="analysis-title">${metric.charAt(0).toUpperCase() + metric.slice(1)}</h3>
                </div>
                <div class="analysis-body">
                    <pre style="background: var(--color-surface); padding: 1rem; border-radius: var(--radius-md); overflow-x: auto;">
${JSON.stringify(data, null, 2)}
                    </pre>
                </div>
            </div>
        `;
    }

    /**
     * Render metrics list
     */
    renderMetrics(metrics) {
        if (!Array.isArray(metrics)) {
            metrics = Object.entries(metrics).map(([key, value]) => ({
                label: key.replace(/_/g, ' '),
                value: typeof value === 'number' ? Utils.formatNumber(value) : value,
                status: 'info',
            }));
        }

        return `<div class="analysis-metrics-list">
            ${metrics
                .map((metric) => {
                    const icon = this.getMetricIcon(metric.status);
                    return `
                    <div class="analysis-metric">
                        ${icon}
                        <span class="metric-text">${metric.label || metric.name}: ${metric.value}</span>
                    </div>
                `;
                })
                .join('')}
        </div>`;
    }

    /**
     * Get metric icon
     */
    getMetricIcon(status) {
        const icons = {
            success: `<svg class="metric-icon success" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <polyline points="20 6 9 17 4 12"/>
            </svg>`,
            warning: `<svg class="metric-icon warning" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                <line x1="12" y1="9" x2="12" y2="13"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>`,
            error: `<svg class="metric-icon error" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <circle cx="12" cy="12" r="10"/>
                <line x1="15" y1="9" x2="9" y2="15"/>
                <line x1="9" y1="9" x2="15" y2="15"/>
            </svg>`,
            info: `<svg class="metric-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" style="color: var(--color-info)">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="16" x2="12" y2="12"/>
                <line x1="12" y1="8" x2="12.01" y2="8"/>
            </svg>`,
        };
        return icons[status] || icons.info;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.analyzerComponent = new AnalyzerComponent();
});
