/* ============================================
   API Client
   ============================================ */

class API {
    constructor() {
        this.baseURL = '/api/v1';
        this.timeout = 30000; // 30 seconds
    }

    /**
     * Generic request handler
     */
    async request(method, endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        
        // ✅ Dynamic timeout based on endpoint
        const timeout = this.getTimeoutForEndpoint(endpoint);
        
        const config = {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
            ...options,
        };
    
        // Add body for POST/PUT/PATCH
        if (options.body && typeof options.body === 'object') {
            config.body = JSON.stringify(options.body);
        }
    
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), timeout);
            config.signal = controller.signal;
    
            const response = await fetch(url, config);
            clearTimeout(timeoutId);
    
            // Handle non-JSON responses
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(
                        data.detail || `HTTP ${response.status}: ${response.statusText}`
                    );
                }
                return data;
            } else {
                // For file downloads, etc.
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                return response;
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error('Request timeout');
            }
            throw error;
        }
    }
    
    /**
     * ✅ NEW: Get timeout based on endpoint
     */
    getTimeoutForEndpoint(endpoint) {
        // Sync operations need longer timeout
        if (endpoint.includes('/trap-sync/sync/table')) {
            return 300000; // 5 minutes for single table sync
        }
        if (endpoint.includes('/trap-sync/sync/all')) {
            return 600000; // 10 minutes for sync all
        }
        // SNMP walk operations
        if (endpoint.includes('/snmp-walk/execute')) {
            return 180000; // 3 minutes
        }
        // Default timeout
        return this.timeout; // 30 seconds
    }

    /**
     * Convenience methods
     */
    async get(endpoint, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;
        return this.request('GET', url);
    }

    async post(endpoint, body = {}) {
        return this.request('POST', endpoint, { body });
    }

    async put(endpoint, body = {}) {
        return this.request('PUT', endpoint, { body });
    }

    async delete(endpoint, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;
        return this.request('DELETE', url);
    }

    // ============================================
    // JOBS (mib_tool_system + mib_tool_jobs)
    // ============================================

    /**
     * List all jobs
     */
    async listJobs(options = {}) {
        const params = {
            limit: options.limit || 100,
            offset: options.offset || 0,
            ...(options.status && { status: options.status }),
            ...(options.job_type && { job_type: options.job_type }),
        };
        return this.get('/jobs/', params);
    }

    async cancelJob(jobId) {
        const response = await fetch(`${this.baseURL}/jobs/${jobId}/cancel`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to cancel job');
        }

        return await response.json();
    }

    /**
     * Retry a failed job
     */
    async retryJob(jobId) {
        const response = await fetch(`${this.baseURL}/jobs/${jobId}/retry`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to retry job');
        }

        return await response.json();
    }

    /**
     * Preview cleanup (dry run)
     */
    async previewCleanup() {
        const response = await fetch(`${this.baseURL}/jobs/cleanup/preview`, {
            headers: {
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to preview cleanup');
        }

        return await response.json();
    }

    /**
     * Execute cleanup
     */
    async cleanupJobs(dryRun = false) {
        const response = await fetch(`${this.baseURL}/jobs/cleanup?dry_run=${dryRun}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to cleanup jobs');
        }

        return await response.json();
    }

    /**
     * Save job data to user database
     */
    async saveJobToDatabase(jobId, tableName) {
        return this.post(`/jobs/${jobId}/save-to-database`, { table_name: tableName });
    }

    /**
     * Delete job
     */
    async deleteJob(jobId, deleteData = true) {
        return this.delete(`/jobs/${jobId}`, { delete_data: deleteData });
    }

    /**
     * Cleanup old jobs
     */
    async cleanupJobs(days = 30, deleteData = true) {
        return this.post('/jobs/cleanup', { days, delete_data: deleteData });
    }

    // ============================================
    // PARSER
    // ============================================

    /**
     * Parse session directory
     */
    async parseSession(sessionId, options = {}) {
        return this.post('/parser/parse/session', {
            session_id: sessionId,
            deduplicate: options.deduplicate !== false,
            dedup_strategy: options.dedup_strategy || 'smart',
            force_compile: options.force_compile || false,
            job_name: options.job_name || null,
        });
    }

    /**
     * Parse text content
     */
    async parseText(content, moduleName) {
        return this.post('/parser/parse/text', {
            content,
            module_name: moduleName,
        });
    }

    // ============================================
    // UPLOAD
    // ============================================

    /**
     * Create upload session
     */
    async createUploadSession() {
        return this.post('/upload/session');
    }

    /**
     * Upload file to session
     */
    async uploadFile(sessionId, file, onProgress = null) {
        const formData = new FormData();
        formData.append('file', file);

        const xhr = new XMLHttpRequest();

        return new Promise((resolve, reject) => {
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable && onProgress) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    onProgress(percentComplete);
                }
            });

            xhr.addEventListener('load', () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        resolve(response);
                    } catch (e) {
                        reject(new Error('Invalid JSON response'));
                    }
                } else {
                    try {
                        const error = JSON.parse(xhr.responseText);
                        reject(new Error(error.detail || `Upload failed: ${xhr.status}`));
                    } catch (e) {
                        reject(new Error(`Upload failed: ${xhr.status}`));
                    }
                }
            });

            xhr.addEventListener('error', () => {
                reject(new Error('Upload failed'));
            });

            xhr.addEventListener('abort', () => {
                reject(new Error('Upload cancelled'));
            });

            xhr.open('POST', `${this.baseURL}/upload/file?session_id=${sessionId}`);
            xhr.send(formData);
        });
    }

    // ============================================
    // EXPORTS
    // ============================================

    /**
     * Export table to file
     */
    async exportTable(tableName, format = 'csv', options = {}) {
        return this.post('/export/table', {
            table: tableName,
            format: format,
            columns: options.columns || null,
            filters: options.filters || null,
            limit: options.limit || null,
        });
    }

    /**
     * Export table as stream (for large datasets)
     */
    async exportTableStream(tableName, format = 'csv', options = {}) {
        const response = await this.request('POST', '/export/table/stream', {
            body: {
                table: tableName,
                format: format,
                columns: options.columns || null,
                filters: options.filters || null,
                limit: options.limit || null,
            },
        });

        // Return raw response for streaming
        return response;
    }

    /**
     * Get supported export formats
     */
    async getExportFormats() {
        return this.get('/export/formats');
    }

    /**
     * Get supported compression types
     */
    async getExportCompressions() {
        return this.get('/export/compressions');
    }

    /**
     * Download file by filename
     */
    downloadFile(filename) {
        window.open(`${this.baseURL}/export/download/${filename}`, '_blank');
    }

    // ============================================
    // ANALYZER
    // ============================================

    /**
     * ✅ FIXED: Analyze data
     */
    async analyzeData(data, metrics = ['all']) {
        return this.post('/analyzer/analyze', {
            data: data,
            metrics: metrics,
        });
    }

    /**
     * ✅ FIXED: Analyze table
     */
    async analyzeTable(tableName, database = 'data', metrics = ['all'], limit = null) {
        const body = {
            table: tableName,
            database: database,
            metrics: metrics,
        };

        if (limit) {
            body.limit = limit;
        }

        return this.post('/analyzer/analyze/table', body);
    }

    /**
     * Get all settings with structure
     */
    async getAllSettings() {
        const response = await fetch(`${this.baseURL}/settings/`, {
            headers: {
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to get settings');
        }
        
        return await response.json();
    }

    /**
     * Update application settings
     */
    async updateApplicationSettings(settings) {
        const response = await fetch(`${this.baseURL}/settings/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
            body: JSON.stringify(settings)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to update settings');
        }
        
        return await response.json();
    }

    /**
     * Reset settings to defaults
     */
    async resetApplicationSettings(category = null) {
        const url = category 
            ? `${this.baseURL}/settings/reset?category=${category}`
            : `${this.baseURL}/settings/reset`;
        
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to reset settings');
        }
        
        return await response.json();
    }

    /**
     * Update settings (new format)
     */
    async updateSettings(updates) {
        const response = await fetch(`${this.baseURL}/settings/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
            body: JSON.stringify({ updates })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to update settings');
        }
        
        return await response.json();
    }

    /**
     * Get raw YAML content
     */
    async getRawYAML() {
        const response = await fetch(`${this.baseURL}/settings/raw`, {
            headers: {
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to get raw YAML');
        }
        
        return await response.json();
    }

    /**
     * List backups
     */
    async listBackups() {
        const response = await fetch(`${this.baseURL}/settings/backups`, {
            headers: {
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to list backups');
        }
        
        return await response.json();
    }

    /**
     * Restore from backup
     */
    async restoreBackup(backupName) {
        const response = await fetch(`${this.baseURL}/settings/restore/${backupName}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to restore backup');
        }
        
        return await response.json();
    }

    /**
     * Get database status
     */
    async getDatabaseStatus() {
        const response = await fetch(`${this.baseURL}/settings/database/status`, {
            headers: {
                'Content-Type': 'application/json',
                Accept: 'application/json'
            },
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to get database status');
        }
        
        return await response.json();
    }


    // ============================================
    // SYSTEM
    // ============================================

    /**
     * Health check
     */
    async healthCheck() {
        return this.get('/health');
    }

    /**
     * Get system info
     */
    async getSystemInfo() {
        return this.get('/system/info');
    }

}

// ============================================
// DATABASE API (Simplified)
// ============================================

class DatabaseAPI {
    constructor(apiClient) {
        this.api = apiClient;
    }
    
    async listTables(pattern = null) {
        const params = {};
        if (pattern) params.pattern = pattern;
        return this.api.get('/database/tables', params);
    }
    
    async getTable(tableName) {
        return this.api.get(`/database/tables/${tableName}`);
    }
    
    async query(params) {
        return this.api.post('/database/query', params);
    }
    
    async deleteTable(tableName) {
        return this.api.delete(`/database/tables/${tableName}`, { confirm: true });
    }
    
    async importData(tableName, data, mode = 'append') {
        return this.api.post(`/database/tables/${tableName}/import`, { data, mode });
    }
    
    // ✅ NEW
    async renameTable(oldName, newName) {
        return this.api.post(`/database/tables/${oldName}/rename`, { new_name: newName });
    }
    
    // ✅ NEW
    async duplicateTable(sourceName, targetName) {
        return this.api.post(`/database/tables/${sourceName}/duplicate`, { target_name: targetName });
    }
    
    // ✅ NEW
    async getTableStats(tableName) {
        return this.api.get(`/database/tables/${tableName}/stats`);
    }

    /**
     * ✅ UPDATED: Import from file (refactored to match new backend)
     */
    async importFromFile(tableName, file, options = {}) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('mode', options.mode || 'append');
        formData.append('create_if_missing', options.createIfMissing || false);
        
        // ✅ REMOVED: has_header (FileManager handles this automatically)
        
        // Use XMLHttpRequest for progress tracking
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            
            // Progress tracking
            if (options.onProgress) {
                xhr.upload.addEventListener('progress', (e) => {
                    if (e.lengthComputable) {
                        const percentComplete = (e.loaded / e.total) * 100;
                        options.onProgress(percentComplete);
                    }
                });
            }
            
            xhr.addEventListener('load', () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        resolve(response);
                    } catch (e) {
                        reject(new Error('Invalid JSON response'));
                    }
                } else {
                    try {
                        const error = JSON.parse(xhr.responseText);
                        reject(new Error(error.detail || `Import failed: ${xhr.status}`));
                    } catch (e) {
                        reject(new Error(`Import failed: ${xhr.status}`));
                    }
                }
            });
            
            xhr.addEventListener('error', () => {
                reject(new Error('Import failed'));
            });
            
            xhr.addEventListener('abort', () => {
                reject(new Error('Import cancelled'));
            });
            
            xhr.open('POST', `${this.api.baseURL}/database/tables/${tableName}/import/file`);
            xhr.send(formData);
        });
    }

}


// Create global instance
window.api = new API();
window.api.database = new DatabaseAPI(window.api);


// ✅ Keep old methods with deprecation warnings (for backward compatibility)
window.api.listUserTables = function(pattern) {
    console.warn('⚠️ Deprecated: Use api.database.listTables() instead');
    return this.database.listTables(pattern);
};

window.api.getUserTableInfo = function(tableName) {
    console.warn('⚠️ Deprecated: Use api.database.getTable() instead');
    return this.database.getTable(tableName);
};

window.api.executeSafeQuery = function(params) {
    // ✅ NO WARNING: This is still the primary method
    return this.database.query(params);
};

window.api.deleteUserTable = function(tableName, confirm) {
    console.warn('⚠️ Deprecated: Use api.database.deleteTable() instead');
    return this.database.deleteTable(tableName);
};