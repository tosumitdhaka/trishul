/**
 * ============================================
 * Analyzer Service
 * Handles data analysis and result display
 * ============================================
 */

class AnalyzerService {
    constructor() {
        this.logger = {
            info: (...args) => console.log('📊 [Analyzer]', ...args),
            error: (...args) => console.error('❌ [Analyzer]', ...args),
            warn: (...args) => console.warn('⚠️ [Analyzer]', ...args),
        };
    }

    /**
     * ✅ Analyze data
     * @param {Array} data - Data to analyze
     * @param {Object} options - Analysis options
     * @returns {Promise<Object>} Analysis results
     */
    async analyze(data, options = {}) {
        const { metrics = ['all'], source = 'unknown', name = 'data', showModal = true } = options;

        if (!data || data.length === 0) {
            notify.warning('No data to analyze');
            return null;
        }

        try {
            this.logger.info(`Starting analysis: ${source} - ${name} (${data.length} rows)`);

            window.showLoading('Analyzing data...');

            // Call API
            const response = await api.analyzeData(data, metrics);

            this.logger.info('Analysis response:', response);

            window.hideLoading();

            if (response && response.success) {
                this.logger.info('Analysis successful');

                // Show modal if requested
                if (showModal) {
                    this.showAnalysisModal(response.metrics, {
                        source,
                        name,
                        recordCount: response.records_analyzed,
                    });
                }

                return response;
            } else {
                this.logger.error('Analysis response invalid:', response);
                notify.error('Analysis failed: Invalid response format');
                return null;
            }
        } catch (error) {
            window.hideLoading();
            this.logger.error('Analysis error:', error);
            notify.error(`Analysis failed: ${error.message}`);
            throw error;
        }
    }

    /**
     * ✅ Show analysis modal
     * @param {Array} results - Analysis results
     * @param {Object} options - Display options
     */
    showAnalysisModal(results, options = {}) {
        if (!results || results.length === 0) {
            notify.warning('No analysis results');
            return;
        }

        const { source = 'data', name = 'Unknown', recordCount = 0 } = options;

        let content = '<div class="analysis-results">';

        // Add summary header
        content += `
            <div class="analysis-summary" style="background: var(--color-background); padding: 1rem; border-radius: var(--radius-md); margin-bottom: 1.5rem;">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem;">
                    <div>
                        <div style="font-size: 0.875rem; color: var(--color-text-secondary);">Source</div>
                        <div style="font-weight: 600; color: var(--color-text);">${this.formatSourceName(source)}</div>
                    </div>
                    <div>
                        <div style="font-size: 0.875rem; color: var(--color-text-secondary);">Name</div>
                        <div style="font-weight: 600; color: var(--color-text);">${name}</div>
                    </div>
                    <div>
                        <div style="font-size: 0.875rem; color: var(--color-text-secondary);">Records Analyzed</div>
                        <div style="font-weight: 600; color: var(--color-text);">${Utils.formatNumber(recordCount)}</div>
                    </div>
                    <div>
                        <div style="font-size: 0.875rem; color: var(--color-text-secondary);">Metrics</div>
                        <div style="font-weight: 600; color: var(--color-text);">${results.length}</div>
                    </div>
                </div>
            </div>
        `;

        // Add each metric section
        results.forEach((result) => {
            const metricName = result.metric.charAt(0).toUpperCase() + result.metric.slice(1);
            content += `
                <div class="analysis-section" style="margin-bottom: 2rem;">
                    <h3 style="color: var(--color-text); border-bottom: 2px solid var(--color-primary); padding-bottom: 0.5rem; margin-bottom: 1rem;">
                        ${metricName} Analysis
                    </h3>
                    ${this.formatAnalysisResult(result.result)}
                </div>
            `;
        });

        content += '</div>';

        // Show modal
        modal.show({
            title: `Analysis Results: ${name}`,
            content: content,
            size: 'large',
            buttons: [
                {
                    text: 'Export Report',
                    class: 'btn-primary',
                    onClick: () => {
                        this.exportAnalysisReport(results, { source, name, recordCount });
                    },
                },
                {
                    text: 'Close',
                    class: 'btn-secondary',
                    onClick: () => modal.close(),
                },
            ],
        });
    }

    /**
     * ✅ Format analysis result
     * @param {Object} result - Analysis result
     * @returns {String} HTML string
     */
    formatAnalysisResult(result) {
        let html = '<div class="analysis-content">';

        // Quality Score & Grade
        if (result.quality_score !== undefined) {
            const scoreColor =
                result.quality_score >= 90
                    ? 'var(--color-success)'
                    : result.quality_score >= 80
                      ? 'var(--color-primary)'
                      : result.quality_score >= 70
                        ? 'var(--color-warning)'
                        : 'var(--color-danger)';

            html += `
                <div style="text-align: center; margin-bottom: 1.5rem;">
                    <div style="font-size: 3rem; font-weight: bold; color: ${scoreColor};">
                        ${result.quality_score.toFixed(1)}%
                    </div>
                    <div style="color: var(--color-text-secondary); font-size: 1.125rem;">
                        Quality Score ${result.grade ? `(Grade: ${result.grade})` : ''}
                    </div>
                </div>
            `;
        }

        // Issues
        if (result.issues && result.issues.length > 0) {
            html += '<div class="analysis-subsection" style="margin-bottom: 1rem;">';
            html +=
                '<h4 style="color: var(--color-danger); margin-bottom: 0.5rem;">⚠️ Issues Found</h4>';
            result.issues.forEach((issue) => {
                html += `<div class="issue-item" style="padding: 0.75rem; margin: 0.5rem 0; background: var(--color-danger-bg); border-left: 3px solid var(--color-danger); border-radius: var(--radius-sm);">${issue}</div>`;
            });
            html += '</div>';
        }

        // Warnings
        if (result.warnings && result.warnings.length > 0) {
            html += '<div class="analysis-subsection" style="margin-bottom: 1rem;">';
            html +=
                '<h4 style="color: var(--color-warning); margin-bottom: 0.5rem;">⚡ Warnings</h4>';
            result.warnings.forEach((warning) => {
                html += `<div class="warning-item" style="padding: 0.75rem; margin: 0.5rem 0; background: var(--color-warning-bg); border-left: 3px solid var(--color-warning); border-radius: var(--radius-sm);">${warning}</div>`;
            });
            html += '</div>';
        }

        // Recommendations
        if (result.recommendations && result.recommendations.length > 0) {
            html += '<div class="analysis-subsection" style="margin-bottom: 1rem;">';
            html +=
                '<h4 style="color: var(--color-info); margin-bottom: 0.5rem;">💡 Recommendations</h4>';
            result.recommendations.forEach((rec) => {
                html += `<div class="recommendation-item" style="padding: 0.75rem; margin: 0.5rem 0; background: var(--color-info-bg); border-left: 3px solid var(--color-info); border-radius: var(--radius-sm);">${rec}</div>`;
            });
            html += '</div>';
        }

        // Stats Grid
        html +=
            '<div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-top: 1rem;">';

        Object.entries(result).forEach(([key, value]) => {
            // Skip already displayed items
            if (['quality_score', 'grade', 'issues', 'warnings', 'recommendations'].includes(key)) {
                return;
            }

            if (typeof value === 'object' && !Array.isArray(value) && value !== null) {
                // Nested object - create subsection
                html += `
                    <div style="grid-column: 1 / -1;">
                        <h4 style="margin: 1rem 0 0.5rem 0; color: var(--color-text);">${this.formatKey(key)}</h4>
                        ${this.formatNestedObject(value)}
                    </div>
                `;
            } else if (Array.isArray(value)) {
                // Array - show as list
                if (value.length > 0 && !['issues', 'warnings', 'recommendations'].includes(key)) {
                    html += `
                        <div style="grid-column: 1 / -1;">
                            <h4 style="margin: 1rem 0 0.5rem 0; color: var(--color-text);">${this.formatKey(key)}</h4>
                            <ul style="margin: 0; padding-left: 1.5rem;">
                                ${value
                                    .slice(0, 10)
                                    .map((item) => `<li>${item}</li>`)
                                    .join('')}
                                ${value.length > 10 ? `<li style="color: var(--color-text-secondary);">... and ${value.length - 10} more</li>` : ''}
                            </ul>
                        </div>
                    `;
                }
            } else if (typeof value !== 'object') {
                // Simple value - show as stat card
                html += `
                    <div class="stat-card" style="background: var(--color-background); padding: 1rem; border-radius: var(--radius-md); text-align: center; border: 1px solid var(--color-border);">
                        <div class="stat-value" style="font-size: 1.5rem; font-weight: bold; color: var(--color-primary);">
                            ${this.formatValue(value)}
                        </div>
                        <div class="stat-label" style="font-size: 0.875rem; color: var(--color-text-secondary); margin-top: 0.5rem;">
                            ${this.formatKey(key)}
                        </div>
                    </div>
                `;
            }
        });

        html += '</div></div>';

        return html;
    }

    /**
     * ✅ Format nested object
     */
    formatNestedObject(obj) {
        let html =
            '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; padding: 1rem; background: var(--color-background); border-radius: var(--radius-md);">';

        Object.entries(obj).forEach(([key, value]) => {
            if (typeof value === 'object' && !Array.isArray(value) && value !== null) {
                html += `
                    <div style="grid-column: 1 / -1; padding: 0.5rem; background: var(--color-surface); border-radius: var(--radius-sm);">
                        <strong style="color: var(--color-text);">${this.formatKey(key)}:</strong>
                        ${this.formatNestedObject(value)}
                    </div>
                `;
            } else {
                html += `
                    <div>
                        <div style="font-size: 0.75rem; color: var(--color-text-secondary); margin-bottom: 0.25rem;">
                            ${this.formatKey(key)}
                        </div>
                        <div style="font-weight: 600; color: var(--color-text);">
                            ${this.formatValue(value)}
                        </div>
                    </div>
                `;
            }
        });

        html += '</div>';
        return html;
    }

    /**
     * ✅ Format key (snake_case to Title Case)
     */
    formatKey(key) {
        return key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
    }

    /**
     * ✅ Format value
     */
    formatValue(value) {
        if (typeof value === 'number') {
            return Utils.formatNumber(value);
        }
        if (typeof value === 'boolean') {
            return value ? 'Yes' : 'No';
        }
        if (value === null || value === undefined) {
            return 'N/A';
        }
        return String(value);
    }

    /**
     * ✅ Format source name
     */
    formatSourceName(source) {
        const sourceNames = {
            table: 'Database Table',
            job: 'Job Result',
            query: 'Query Result',
            file: 'File',
        };
        return sourceNames[source] || source;
    }

    /**
     * ✅ Export analysis report
     */
    async exportAnalysisReport(results, options = {}) {
        try {
            const { source = 'unknown', name = 'data', recordCount = 0 } = options;

            const reportData = {
                type: 'analysis_report',
                source: source,
                name: name,
                records_analyzed: recordCount,
                timestamp: new Date().toISOString(),
                metrics: results,
            };

            const blob = new Blob([JSON.stringify(reportData, null, 2)], {
                type: 'application/json',
            });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `analysis_${name}_${Date.now()}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            notify.success('Analysis report exported');
        } catch (error) {
            this.logger.error('Failed to export report:', error);
            notify.error('Failed to export report');
        }
    }
}

// ✅ Initialize global instance
window.analyzerService = new AnalyzerService();

