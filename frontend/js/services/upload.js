/* ============================================
   Upload Service - Handles file uploads to session directory
   ============================================ */

class UploadService {
    constructor() {
        this.baseURL = '/api/v1/upload';
        this.currentSession = null;
        this.uploadProgress = new Map();
    }

    /**
     * Create new upload session
     */
    async createSession() {
        try {
            // console.log('📁 Creating upload session...');
            const response = await api.post('/upload/session/create'); // ✅ Relative path

            if (response && response.success) {
                this.currentSession = {
                    id: response.session_id,
                    path: response.session_path,
                    created: new Date(),
                };

                console.log('✅ Upload session created:', this.currentSession.id);
                return this.currentSession;
            }

            throw new Error('Failed to create session: Invalid response');
        } catch (error) {
            console.error('❌ Failed to create upload session:', error);
            throw error;
        }
    }

    /**
     * Upload single file to session
     */
    async uploadFile(sessionId, file, onProgress = null) {
        const formData = new FormData();
        formData.append('files', file);

        try {
            const xhr = new XMLHttpRequest();

            return new Promise((resolve, reject) => {
                // Progress tracking
                if (onProgress) {
                    xhr.upload.addEventListener('progress', (e) => {
                        if (e.lengthComputable) {
                            const percentComplete = (e.loaded / e.total) * 100;
                            onProgress(percentComplete, e.loaded, e.total);
                        }
                    });
                }

                // Success
                xhr.addEventListener('load', () => {
                    if (xhr.status === 200) {
                        const response = JSON.parse(xhr.responseText);
                        resolve(response);
                    } else {
                        reject(new Error(`Upload failed: ${xhr.statusText}`));
                    }
                });

                // Error
                xhr.addEventListener('error', () => {
                    reject(new Error('Upload failed'));
                });

                // Abort
                xhr.addEventListener('abort', () => {
                    reject(new Error('Upload cancelled'));
                });

                // Send request
                xhr.open('POST', `${this.baseURL}/session/${sessionId}/upload`);
                xhr.send(formData);
            });
        } catch (error) {
            console.error('File upload failed:', error);
            throw error;
        }
    }

    /**
     * Upload multiple files to session
     */
    async uploadFiles(sessionId, files, onProgress = null) {
        const formData = new FormData();

        // Add all files to form data
        files.forEach((file) => {
            formData.append('files', file);
        });

        try {
            const xhr = new XMLHttpRequest();

            return new Promise((resolve, reject) => {
                // Progress tracking
                if (onProgress) {
                    xhr.upload.addEventListener('progress', (e) => {
                        if (e.lengthComputable) {
                            const percentComplete = (e.loaded / e.total) * 100;
                            onProgress(percentComplete, e.loaded, e.total);
                        }
                    });
                }

                // Success
                xhr.addEventListener('load', () => {
                    if (xhr.status === 200) {
                        const response = JSON.parse(xhr.responseText);
                        resolve(response);
                    } else {
                        reject(new Error(`Upload failed: ${xhr.statusText}`));
                    }
                });

                // Error
                xhr.addEventListener('error', () => {
                    reject(new Error('Upload failed'));
                });

                // Abort
                xhr.addEventListener('abort', () => {
                    reject(new Error('Upload cancelled'));
                });

                // Send request
                xhr.open('POST', `${this.baseURL}/session/${sessionId}/upload`);
                xhr.send(formData);
            });
        } catch (error) {
            console.error('Files upload failed:', error);
            throw error;
        }
    }

    /**
     * Extract archive in session
     */
    async extractArchive(sessionId, archiveFilename) {
        try {
            const response = await api.extractArchive(sessionId, archiveFilename);
            return response;
        } catch (error) {
            console.error('Archive extraction failed:', error);
            throw error;
        }
    }

    /**
     * List files in session
     */
    async listSessionFiles(sessionId) {
        try {
            const response = await api.get(`${this.baseURL}/session/${sessionId}/files`);
            return response;
        } catch (error) {
            console.error('List session files failed:', error);
            throw error;
        }
    }

    /**
     * Get session info
     */
    async getSessionInfo(sessionId) {
        try {
            const response = await api.get(`${this.baseURL}/session/${sessionId}/info`);
            return response;
        } catch (error) {
            console.error('Get session info failed:', error);
            throw error;
        }
    }

    /**
     * Cleanup session
     */
    async cleanupSession(sessionId) {
        try {
            const response = await api.cleanupSession(sessionId);

            if (this.currentSession && this.currentSession.id === sessionId) {
                this.currentSession = null;
            }

            return response;
        } catch (error) {
            console.error('Session cleanup failed:', error);
            throw error;
        }
    }

    /**
     * Get current session
     */
    getCurrentSession() {
        return this.currentSession;
    }

    /**
     * Clear current session
     */
    clearCurrentSession() {
        this.currentSession = null;
    }

    /**
     * Check if file size requires job creation
     */
    shouldCreateJob(files) {
        if (!files || files.length === 0) return false;

        // Multiple files: always create job
        if (files.length > 1) return true;

        // Single file > 5MB: create job
        const singleFile = files[0];
        if (singleFile.size > 5 * 1024 * 1024) return true;

        return false;
    }

    /**
     * Estimate processing time (rough estimate)
     */
    estimateProcessingTime(files) {
        if (!files || files.length === 0) return 0;

        const totalSize = files.reduce((sum, file) => sum + file.size, 0);
        const totalMB = totalSize / (1024 * 1024);

        // Rough estimate: 1MB = 0.5 seconds
        return Math.ceil(totalMB * 0.5);
    }
}

// Create global instance
window.uploadService = new UploadService();
