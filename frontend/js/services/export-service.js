/* ============================================
   Export Service - Unified Export Handler
   Single source of truth for all exports
   ============================================ */

class ExportService {
    constructor() {
        this.logger = console;
        this.activeExports = new Map(); // Track ongoing exports
    }

    /**
     * ✅ MAIN METHOD: Export from any source
     *
     * @param {Object} options - Export options
     * @param {string} options.source - 'table' | 'job' | 'query'
     * @param {string} options.name - Table name, job ID, or query identifier
     * @param {string} options.format - Export format (csv, json, excel, yaml, parquet)
     * @param {Object} options.filters - Optional filters
     * @param {Array} options.columns - Optional column selection
     * @param {number} options.limit - Optional record limit
     * @param {boolean} options.compress - Compress as ZIP
     * @param {Object} options.data - Optional: data array for preview
     * @returns {Promise<Object>} Export result
     */
    /**
     * ✅ UPDATED: Export with database context
     */
    async export(options) {
        const {
            source = 'table',
            name,
            format = 'csv',
            filename = null,
            database = 'data', // ✅ Add database parameter
            filters = null,
            columns = null,
            limit = null,
            compress = false,
            compression = null,
            data = null,
        } = options;

        // ✅ Get default compression if compress=true but no type specified
        let compressionType = compression;
        if (compress && !compressionType) {
            compressionType = await this.getDefaultCompression() || 'zip';
        }

        // ✅ Log what we're sending
        console.log('📤 Export request:', {
            source,
            name,
            format,
            filename,
            database, // ✅ Log database
            filters,
            columns,
            limit,
            compress,
            compression: compressionType,
            dataRows: data ? data.length : 0, // ✅ Log data length
        });

        // Validate
        if (!name) {
            throw new Error('Export name/identifier is required');
        }

        // For query exports, data is required
        if (source === 'query' && (!data || data.length === 0)) {
            throw new Error('No data provided for query export');
        }

        // Generate export ID for tracking
        const exportId = `export_${Date.now()}`;

        try {
            // Show loading
            window.showLoading(`Exporting to ${format.toUpperCase()}...`);

            // Track export
            this.activeExports.set(exportId, {
                source,
                name,
                format,
                filename,
                database, // ✅ Track database
                startTime: Date.now(),
                status: 'processing',
            });

            let result;

            // Route to appropriate export method
            switch (source) {
                case 'table':
                    result = await this._exportTable(name, format, {
                        filename,
                        database, // ✅ Pass database
                        filters,
                        columns,
                        limit,
                        compress,
                        compression: compressionType,
                    });
                    break;

                case 'job':
                    result = await this._exportJob(name, format, {
                        filename,
                        filters,
                        columns,
                        limit,
                        compress,
                        compression: compressionType,
                    });
                    break;

                case 'query':
                    result = await this._exportQuery(data, format, {
                        filename,
                        compress,
                        compression: compressionType,
                    });
                    break;

                default:
                    throw new Error(`Unknown export source: ${source}`);
            }

            // Hide loading
            window.hideLoading();

            // Update tracking
            this.activeExports.get(exportId).status = 'completed';
            this.activeExports.get(exportId).result = result;

            // Show success notification
            notify.success(
                `Exported ${Utils.formatNumber(result.records_exported)} records ` +
                    `(${Utils.formatFileSize(result.file_size)})`
            );

            // Trigger download
            if (result.file_url) {
                this._triggerDownload(result.file_url, result.filename);

                // Show cleanup message
                if (result.message) {
                    notify.info(result.message, 10000);
                }
            }

            return result;
        } catch (error) {
            window.hideLoading();

            // Update tracking
            if (this.activeExports.has(exportId)) {
                this.activeExports.get(exportId).status = 'failed';
                this.activeExports.get(exportId).error = error.message;
            }

            this.logger.error('Export failed:', error);
            notify.error(`Export failed: ${error.message}`);

            throw error;
        } finally {
            // Cleanup tracking after 5 minutes
            setTimeout(() => {
                this.activeExports.delete(exportId);
            }, 300000);
        }
    }

    /**
     * Export from database table
     */
    async _exportTable(tableName, format, options) {
        const response = await api.post('/export/table', {
            table: tableName,
            format: format,
            filename: options.filename || null,
            columns: options.columns,
            filters: options.filters,
            limit: options.limit,
            compress: options.compress,
            compression: options.compression,
        });

        if (!response || !response.success) {
            throw new Error(response?.message || 'Export failed');
        }

        return response;
    }

    /**
     * ✅ FIXED: Export from job result using dedicated endpoint
     */
    async _exportJob(jobId, format, options) {
        this.logger.info(`📤 Exporting job: ${jobId}`);
        // ✅ Convert UI filters to backend format if needed
        let backendFilters = options.filters;
        if (backendFilters && Array.isArray(backendFilters)) {
            // Filters are in UI format, convert to backend format
            backendFilters = window.filterService.convertToBackend(backendFilters);
        }

        // ✅ Call dedicated job export endpoint
        const response = await api.post(`/export/job/${jobId}`, {
            format: format,
            filename: options.filename || null,
            columns: options.columns,
            filters: backendFilters,
            limit: options.limit,
            compress: options.compress,
            compression: options.compression,
        });

        if (!response || !response.success) {
            throw new Error(response?.message || 'Job export failed');
        }

        return response;
    }

    /**
     * ✅ FIXED: Export query results
     */
    async _exportQuery(data, format, options) {
        this.logger.info(`📤 Exporting query results: ${data.length} rows`);

        if (!data || data.length === 0) {
            throw new Error('No data to export');
        }

        const response = await api.post('/export/query', {
            data: data, // ✅ Send data array
            format: format,
            filename: options.filename || null,
            compress: options.compress,
            compression: options.compression,
        });

        if (!response || !response.success) {
            throw new Error(response?.message || 'Query export failed');
        }

        return response;
    }

    /**
     * Trigger file download
     */
    _triggerDownload(url, filename) {
        const link = document.createElement('a');
        link.href = url;
        link.download = filename || 'export';
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    /**
     * Get list of supported formats
     */
    async getFormats() {
        try {
            const response = await api.get('/export/formats');
            return response.formats || [];
        } catch (error) {
            this.logger.error('Failed to get formats:', error);
            // Return default formats
            return [
                { id: 'csv', name: 'CSV', icon: '📊', description: 'Comma-Separated Values' },
                { id: 'json', name: 'JSON', icon: '📄', description: 'JavaScript Object Notation' },
                { id: 'excel', name: 'Excel', icon: '📋', description: 'Microsoft Excel (.xlsx)' },
                { id: 'yaml', name: 'YAML', icon: '📝', description: "YAML Ain't Markup Language" },
                {
                    id: 'parquet',
                    name: 'Parquet',
                    icon: '🗄️',
                    description: 'Apache Parquet (columnar)',
                },
            ];
        }
    }

    /**
     * Get active exports
     */
    getActiveExports() {
        return Array.from(this.activeExports.values());
    }

    /**
     * ✅ NEW: Get supported compressions from backend
     */
    async getCompressions() {
        if (this.supportedCompressions) {
            return this.supportedCompressions;
        }
        
        try {
            const response = await api.getExportCompressions();
            if (response && response.success) {
                this.supportedCompressions = response.compressions;
                return this.supportedCompressions;
            }
        } catch (error) {
            this.logger.error('Failed to get compressions:', error);
            // Fallback to default
            return [
                { id: 'zip', name: 'ZIP', extension: '.zip', description: 'ZIP archive' }
            ];
        }
    }
    
    /**
     * ✅ NEW: Get default compression from config
     */
    async getDefaultCompression() {
        const defaultComp = window.settings?.getBackend('export.compression', null);
        return defaultComp;
    }

}

// ✅ Create singleton instance
const exportService = new ExportService();

// ✅ Make globally available
window.exportService = exportService;

// ✅ Also export for ES6 imports
if (typeof module !== 'undefined' && module.exports) {
    module.exports = exportService;
}
