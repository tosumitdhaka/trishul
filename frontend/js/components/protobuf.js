/* ============================================
   Protobuf Decoder Component - Session-based V2 (FIXED)
   ============================================ */

class ProtobufComponent {
    constructor() {
        this.sessionId = null;
        this.protoFiles = []; // ✅ Changed to array for multiple files
        this.binaryFiles = [];
        this.decodedResults = [];
        this.schemaValidated = false;
        this.compiledSchema = null;
        this.selectedMessageType = null;
        
        // Constants
        this.MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
        this.MAX_JSON_PREVIEW = 100000; // 100KB
        this.ALLOWED_BINARY_EXTENSIONS = ['.protobuf', '.pb', '.bin', '.dat', ''];
        
        this.init();
    }

    async init() {
        this.render();
        this.setupEventListeners();
        this.setupKeyboardShortcuts();
        
        // Create session on init
        await this.createSession();
    }

    async createSession() {
        try {
            const response = await uploadService.createSession();
            this.sessionId = response.id;
            console.log('✅ Session created:', this.sessionId);
        } catch (error) {
            console.error('Failed to create session:', error);
            notify.error('Failed to initialize session');
        }
    }

    setupEventListeners() {
        // Remove old listeners first (if they exist)
        document.removeEventListener('click', this._handleDocumentClick);
        document.removeEventListener('dragover', this._handleDragOver);
        document.removeEventListener('dragleave', this._handleDragLeave);
        document.removeEventListener('drop', this._handleDrop);
        
        // Store bound handlers as instance properties
        if (!this._handleDocumentClick) {
            this._handleDocumentClick = this.handleDocumentClick.bind(this);
            this._handleDragOver = this.handleDragOver.bind(this);
            this._handleDragLeave = this.handleDragLeave.bind(this);
            this._handleDrop = this.handleDrop.bind(this);
        }
        
        // Add event listeners
        document.addEventListener('click', this._handleDocumentClick);
        document.addEventListener('dragover', this._handleDragOver);
        document.addEventListener('dragleave', this._handleDragLeave);
        document.addEventListener('drop', this._handleDrop);
        
        // File input changes
        const protoFileInput = document.getElementById('protoFileInput');
        const binaryFileInput = document.getElementById('binaryFileInput');
        
        if (protoFileInput) {
            // Remove old listener
            if (this._protoInputHandler) {
                protoFileInput.removeEventListener('change', this._protoInputHandler);
            }
            
            // Create and store new handler
            this._protoInputHandler = (e) => {
                if (e.target.files.length > 0) {
                    this.handleProtoUpload(Array.from(e.target.files));
                }
            };
            
            protoFileInput.addEventListener('change', this._protoInputHandler);
        }
        
        if (binaryFileInput) {
            // Remove old listener
            if (this._binaryInputHandler) {
                binaryFileInput.removeEventListener('change', this._binaryInputHandler);
            }
            
            // Create and store new handler
            this._binaryInputHandler = (e) => {
                this.handleBinaryUpload(Array.from(e.target.files));
            };
            
            binaryFileInput.addEventListener('change', this._binaryInputHandler);
        }
    }


    handleDocumentClick(e) {
        const target = e.target;
        
        // Proto upload area click
        if (target.closest('#protoUploadArea')) {
            const input = document.getElementById('protoFileInput');
            if (input) input.click();
        }
        
        // Binary upload area click
        if (target.closest('#binaryUploadArea')) {
            const input = document.getElementById('binaryFileInput');
            if (input) input.click();
        }
        
        // Compile button
        if (target.closest('#compileProtoBtn')) {
            this.compileProtoSchema();
        }
        
        // Decode button
        if (target.closest('#decodeBtn')) {
            this.decodeBinary();
        }
    }

    handleDragOver(e) {
        const protoArea = document.getElementById('protoUploadArea');
        const binaryArea = document.getElementById('binaryUploadArea');
        
        if (e.target.closest('#protoUploadArea')) {
            e.preventDefault();
            if (protoArea) protoArea.classList.add('dragover');
        }
        
        if (e.target.closest('#binaryUploadArea')) {
            e.preventDefault();
            if (binaryArea) binaryArea.classList.add('dragover');
        }
    }

    handleDragLeave(e) {
        const protoArea = document.getElementById('protoUploadArea');
        const binaryArea = document.getElementById('binaryUploadArea');
        
        if (e.target.closest('#protoUploadArea')) {
            if (protoArea) protoArea.classList.remove('dragover');
        }
        
        if (e.target.closest('#binaryUploadArea')) {
            if (binaryArea) binaryArea.classList.remove('dragover');
        }
    }

    handleDrop(e) {
        e.preventDefault();
        
        const protoArea = document.getElementById('protoUploadArea');
        const binaryArea = document.getElementById('binaryUploadArea');
        
        if (e.target.closest('#protoUploadArea')) {
            if (protoArea) protoArea.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                this.handleProtoUpload(Array.from(e.dataTransfer.files)); // ✅ Handle multiple files
            }
        }
        
        if (e.target.closest('#binaryUploadArea')) {
            if (binaryArea) binaryArea.classList.remove('dragover');
            this.handleBinaryUpload(Array.from(e.dataTransfer.files));
        }
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + U = Upload proto
            if ((e.ctrlKey || e.metaKey) && e.key === 'u') {
                e.preventDefault();
                const input = document.getElementById('protoFileInput');
                if (input) input.click();
            }
            
            // Ctrl/Cmd + B = Upload binary
            if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
                e.preventDefault();
                const input = document.getElementById('binaryFileInput');
                if (input && this.protoFiles.length > 0) input.click();
            }
            
            // Ctrl/Cmd + D = Decode
            if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
                e.preventDefault();
                const decodeBtn = document.getElementById('decodeBtn');
                if (decodeBtn && !decodeBtn.disabled) {
                    this.decodeBinary();
                }
            }
            
            // Ctrl/Cmd + R = Reset
            if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
                e.preventDefault();
                this.fullReset();
            }
        });
    }

    scrollToElement(elementId, offset = 100) {
        setTimeout(() => {
            const element = document.getElementById(elementId);
            if (element) {
                element.scrollIntoView({ 
                    behavior: 'smooth', 
                    block: 'start',
                    inline: 'nearest'
                });
                
                setTimeout(() => {
                    window.scrollBy({
                        top: -offset,
                        behavior: 'smooth'
                    });
                }, 100);
            }
        }, 500);
    }

    render() {
        const container = document.getElementById('protobufContent');
        if (!container) return;

        container.innerHTML = `
            <!-- Step 1: Upload Proto Schema -->
            <section class="step-section">
                <div class="step-header">
                    <div class="step-number">1</div>
                    <h3>Upload Proto Schema</h3>
                </div>
                
                <div class="upload-area" id="protoUploadArea">
                    <svg class="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                        <polyline points="17 8 12 3 7 8"/>
                        <line x1="12" y1="3" x2="12" y2="15"/>
                    </svg>
                    <p class="upload-text">Drop .proto file(s) here</p>
                    <p class="upload-hint">Or click to browse</p>
                    <p class="upload-formats">Supports: .proto files (max 10MB each)</p>
                    <input type="file" id="protoFileInput" accept=".proto" multiple hidden>
                </div>

                <div id="protoFileDisplay"></div>

                <div style="margin-top: var(--spacing-md); display: flex; justify-content: flex-end; gap: var(--spacing-sm);">
                    <button class="btn btn-primary" id="compileProtoBtn" disabled>
                        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <polyline points="20 6 9 17 4 12"/>
                        </svg>
                        Compile Schema
                    </button>
                </div>

                <div id="schemaInfoDisplay"></div>
            </section>

            <!-- Step 2: Upload Binary Data -->
            <section class="step-section" id="binaryUploadSection" style="display: none;">
                <div class="step-header">
                    <div class="step-number">2</div>
                    <h3>Upload Binary Data</h3>
                </div>

                <div class="upload-area" id="binaryUploadArea">
                    <svg class="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                        <polyline points="17 8 12 3 7 8"/>
                        <line x1="12" y1="3" x2="12" y2="15"/>
                    </svg>
                    <p class="upload-text">Drop binary file(s) here</p>
                    <p class="upload-hint">Or click to browse</p>
                    <p class="upload-formats">Supports: .protobuf, .pb, .bin, .dat (max 10MB each)</p>
                    <input type="file" id="binaryFileInput" multiple hidden>
                </div>

                <div id="binaryFilesDisplay"></div>

                <div style="margin-top: var(--spacing-md); display: flex; justify-content: flex-end;">
                    <button class="btn btn-primary" id="decodeBtn" disabled>
                        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <circle cx="11" cy="11" r="8"/>
                            <path d="m21 21-4.35-4.35"/>
                        </svg>
                        Decode Binary Data
                    </button>
                </div>
            </section>

            <!-- Decoded Results -->
            <section class="step-section" id="decodedResultSection" style="display: none;">
                <div class="step-header">
                    <div class="step-number">✓</div>
                    <h3>Decoded Results</h3>
                </div>

                <div id="decodedResultsDisplay"></div>
            </section>

            <!-- Keyboard Shortcuts Info -->
            <div class="info-box" style="margin-bottom: var(--spacing-md); background: var(--color-info-bg); border-left: 4px solid var(--color-info); padding: var(--spacing-sm); border-radius: var(--radius-md); font-size: var(--font-size-sm);">
                <strong>⌨️ Keyboard Shortcuts:</strong> 
                <span style="margin-left: var(--spacing-sm);">
                    <kbd>Ctrl+U</kbd> Upload Proto | 
                    <kbd>Ctrl+B</kbd> Upload Binary | 
                    <kbd>Ctrl+D</kbd> Decode | 
                    <kbd>Ctrl+R</kbd> Reset All
                </span>
            </div>

        `;

        this.updateUI();
    }

    async handleProtoUpload(files) {
        // ✅ Validate all files
        const validFiles = [];
        const errors = [];

        for (const file of files) {
            if (!file.name.endsWith('.proto')) {
                errors.push(`${file.name}: not a .proto file`);
                continue;
            }

            if (file.size > this.MAX_FILE_SIZE) {
                errors.push(`${file.name}: exceeds 10MB limit`);
                continue;
            }

            if (file.size === 0) {
                errors.push(`${file.name}: file is empty`);
                continue;
            }

            validFiles.push(file);
        }

        if (errors.length > 0) {
            const errorMsg = errors.length > 3 
                ? `${errors.slice(0, 3).join('; ')} ... and ${errors.length - 3} more`
                : errors.join('; ');
            notify.warning(`Skipped ${errors.length} file(s): ${errorMsg}`);
        }

        if (validFiles.length === 0) {
            notify.error('No valid .proto files to upload');
            return;
        }

        try {
            window.showLoading(`Uploading ${validFiles.length} proto file(s)...`);

            // Upload to session
            const uploadResult = await uploadService.uploadFiles(this.sessionId, validFiles);

            if (!uploadResult || !uploadResult.success) {
                throw new Error('Upload failed');
            }

            this.protoFiles = validFiles;
            this.schemaValidated = false;
            this.compiledSchema = null;
            this.renderProtoFiles();
            this.updateUI();

            window.hideLoading();

            notify.success(`Uploaded ${validFiles.length} proto file(s)`);

            this.scrollToElement('protoFileDisplay');

        } catch (error) {
            window.hideLoading();
            console.error('Proto upload error:', error);
            notify.error(`Failed to upload proto files: ${error.message}`);
        }
    }

    renderProtoFiles() {
        const container = document.getElementById('protoFileDisplay');
        if (!container) return;

        if (this.protoFiles.length === 0) {
            container.innerHTML = '';
            return;
        }

        container.innerHTML = `
            <div class="selected-files-list" style="margin-top: var(--spacing-md);">
                <div class="list-header">
                    <span style="font-weight: var(--font-weight-semibold); color: var(--color-text);">
                        Selected Proto Schema Files (${this.protoFiles.length})
                        ${this.schemaValidated ? '<span class="badge-compact" style="background: var(--color-success-light); color: var(--color-success); margin-left: var(--spacing-xs);">✓ Compiled</span>' : ''}
                    </span>
                    <button class="btn btn-sm btn-secondary" onclick="protobufComponent.clearProtoFiles()">
                        Clear All
                    </button>
                </div>
                <div class="list-body">
                    ${this.protoFiles.map((file, index) => `
                        <div class="file-list-item">
                            <div style="display: flex; align-items: center; gap: var(--spacing-sm);">
                                <svg style="width: 20px; height: 20px; color: var(--color-primary);" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z"/>
                                    <polyline points="13 2 13 9 20 9"/>
                                </svg>
                                <div>
                                    <div style="font-weight: var(--font-weight-medium); color: var(--color-text);">${this.escapeHtml(file.name)}</div>
                                    <div style="font-size: var(--font-size-xs); color: var(--color-text-secondary);">${this.formatFileSize(file.size)}</div>
                                </div>
                            </div>
                            <button class="btn btn-sm btn-danger" onclick="protobufComponent.removeProtoFile(${index})" title="Remove file" style="padding: var(--spacing-xs);">
                                <svg style="width: 16px; height: 16px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <line x1="18" y1="6" x2="6" y2="18"/>
                                    <line x1="6" y1="6" x2="18" y2="18"/>
                                </svg>
                            </button>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    removeProtoFile(index) {
        this.protoFiles.splice(index, 1);
        this.renderProtoFiles();
        this.updateUI();
    }

    async clearProtoFiles() {
        this.protoFiles = [];
        this.schemaValidated = false;
        this.compiledSchema = null;
        this.selectedMessageType = null;
        
        const protoInput = document.getElementById('protoFileInput');
        if (protoInput) {
            protoInput.value = '';
        }
        
        this.renderProtoFiles();
        
        const schemaInfoDisplay = document.getElementById('schemaInfoDisplay');
        if (schemaInfoDisplay) {
            schemaInfoDisplay.innerHTML = '';
        }
        
        this.updateUI();
    }

    async compileProtoSchema() {
        if (this.protoFiles.length === 0) {
            notify.error('Please upload .proto file(s) first');
            return;
        }

        if (!this.sessionId) {
            notify.error('Session not initialized');
            return;
        }

        try {
            window.showLoading('Compiling schema...');

            const formData = new FormData();
            formData.append('session_id', this.sessionId);

            const response = await fetch('/api/v1/protobuf/compile-schema', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            window.hideLoading();

            if (!data.success) {
                throw new Error(data.message || 'Compilation failed');
            }

            this.schemaValidated = true; // ✅ Set flag
            this.compiledSchema = data;
            this.selectedMessageType = data.auto_detected_root;

            notify.success('✅ Schema compiled successfully!');
            
            this.displaySchemaInfo(data);
            this.renderProtoFiles();
            this.updateUI(); // ✅ Update UI to show binary section

            this.scrollToElement('schemaInfoDisplay');

        } catch (error) {
            window.hideLoading();
            console.error('Compilation error:', error);
            notify.error(`Compilation failed: ${error.message}`);
        }
    }

    // ✅ Helper to strip package prefix from message type
    stripPackagePrefix(messageType) {
        if (!messageType) return '';
        const parts = messageType.split('.');
        return parts[parts.length - 1]; // Return last part (message name only)
    }

    displaySchemaInfo(data) {
        const container = document.getElementById('schemaInfoDisplay');
        if (!container) return;

        container.innerHTML = `
            <div style="margin-top: var(--spacing-md);">
                <!-- Stats Summary -->
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: var(--spacing-sm); margin-bottom: var(--spacing-md);">
                    <div class="stat-card-compact" style="background: var(--color-success-light); border-left: 4px solid var(--color-success);">
                        <div class="stat-value-compact" style="color: var(--color-success);">✓ Compiled</div>
                        <div class="stat-label-compact">Schema Status</div>
                    </div>
                    <div class="stat-card-compact">
                        <div class="stat-value-compact">${data.total_messages || 0}</div>
                        <div class="stat-label-compact">Total Messages</div>
                    </div>
                    <div class="stat-card-compact">
                        <div class="stat-value-compact">${(data.message_types || []).length}</div>
                        <div class="stat-label-compact">Available Types</div>
                    </div>
                    <div class="stat-card-compact">
                        <div class="stat-value-compact">${this.escapeHtml(data.package || 'N/A')}</div>
                        <div class="stat-label-compact">Package</div>
                    </div>
                </div>

                <!-- Message Types List (Clickable) -->
                ${data.message_types && data.message_types.length > 0 ? `
                    <div class="selected-files-list">
                        <div class="list-header">
                            <span style="font-weight: var(--font-weight-semibold); color: var(--color-text);">
                                Select Message Type for Decoding
                            </span>
                        </div>
                        <div class="list-body" style="max-height: 200px; overflow-y: auto;">
                            ${data.message_types.map((msg, index) => {
                                const score = data.dependency_scores ? data.dependency_scores[msg] || 0 : 0;
                                const isAutoDetected = msg === data.auto_detected_root;
                                const isSelected = msg === this.selectedMessageType;
                                return `
                                    <div class="file-list-item" 
                                         style="cursor: pointer; ${isSelected ? 'background: var(--color-primary-light); border-left: 3px solid var(--color-primary);' : ''} ${isAutoDetected && !isSelected ? 'background: var(--color-success-bg); border-left: 3px solid var(--color-success);' : ''}"
                                         onclick="protobufComponent.selectMessageType('${this.escapeHtml(msg)}')">
                                        <div style="display: flex; align-items: center; gap: var(--spacing-sm);">
                                            <svg style="width: 20px; height: 20px; color: ${isSelected ? 'var(--color-primary)' : isAutoDetected ? 'var(--color-success)' : 'var(--color-text-secondary)'};" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                                ${isSelected ? '<circle cx="12" cy="12" r="10"/><polyline points="9 12 11 14 15 10"/>' : '<path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>'}
                                            </svg>
                                            <div style="flex: 1;">
                                                <div style="font-weight: var(--font-weight-medium); color: var(--color-text);">
                                                    ${this.escapeHtml(this.stripPackagePrefix(msg))}
                                                    ${isAutoDetected ? '<span style="color: var(--color-success); font-size: var(--font-size-xs); margin-left: var(--spacing-xs);">★ Auto-detected</span>' : ''}
                                                    ${isSelected ? '<span style="color: var(--color-primary); font-size: var(--font-size-xs); margin-left: var(--spacing-xs);">✓ Selected</span>' : ''}
                                                </div>
                                                <div style="font-size: var(--font-size-xs); color: var(--color-text-secondary);">
                                                    ${this.escapeHtml(msg)} • Score: ${score}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                `;
                            }).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
    }

    // ✅ Method to select message type
    selectMessageType(messageType) {
        this.selectedMessageType = messageType;
        console.log('Selected message type:', this.selectedMessageType);
        
        // Re-render schema info to update selection
        if (this.compiledSchema) {
            this.displaySchemaInfo(this.compiledSchema);
        }
        
        notify.info(`Selected: ${this.stripPackagePrefix(messageType)}`);
    }

    async handleBinaryUpload(files) {
        try {
            window.showLoading('Uploading binary files...');

            const validFiles = [];
            const errors = [];

            for (const file of files) {
                if (file.size > this.MAX_FILE_SIZE) {
                    errors.push(`${file.name}: exceeds 10MB limit`);
                    continue;
                }

                if (file.size === 0) {
                    errors.push(`${file.name}: file is empty`);
                    continue;
                }

                const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
                const hasExtension = file.name.includes('.');
                
                if (hasExtension && !this.ALLOWED_BINARY_EXTENSIONS.includes(ext)) {
                    errors.push(`${file.name}: unsupported file type`);
                    continue;
                }

                validFiles.push(file);
            }

            if (errors.length > 0) {
                const errorMsg = errors.length > 3 
                    ? `${errors.slice(0, 3).join('; ')} ... and ${errors.length - 3} more`
                    : errors.join('; ');
                notify.warning(`Skipped ${errors.length} file(s): ${errorMsg}`);
            }

            if (validFiles.length === 0) {
                window.hideLoading();
                notify.error('No valid files to upload');
                return;
            }

            // Upload files to session
            const uploadResult = await uploadService.uploadFiles(this.sessionId, validFiles);

            if (!uploadResult || !uploadResult.success) {
                throw new Error('Upload failed');
            }

            this.binaryFiles = validFiles;
            this.renderBinaryFiles();
            this.updateUI();

            window.hideLoading();

            notify.success(`Uploaded ${validFiles.length} file(s)`);

            this.scrollToElement('binaryFilesDisplay');

        } catch (error) {
            window.hideLoading();
            console.error('Binary upload error:', error);
            notify.error(`Failed to upload files: ${error.message}`);
        }
    }

    renderBinaryFiles() {
        const container = document.getElementById('binaryFilesDisplay');
        if (!container) return;

        if (this.binaryFiles.length === 0) {
            container.innerHTML = '';
            return;
        }

        container.innerHTML = `
            <div class="selected-files-list" style="margin-top: var(--spacing-md);">
                <div class="list-header">
                    <span style="font-weight: var(--font-weight-semibold); color: var(--color-text);">
                        Selected Binary Files (${this.binaryFiles.length})
                    </span>
                    <button class="btn btn-sm btn-secondary" onclick="protobufComponent.clearBinaryFiles()">
                        Clear All
                    </button>
                </div>
                <div class="list-body">
                    ${this.binaryFiles.map((file, index) => `
                        <div class="file-list-item">
                            <div style="display: flex; align-items: center; gap: var(--spacing-sm);">
                                <svg style="width: 20px; height: 20px; color: var(--color-accent);" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z"/>
                                    <polyline points="13 2 13 9 20 9"/>
                                </svg>
                                <div>
                                    <div style="font-weight: var(--font-weight-medium); color: var(--color-text);">${this.escapeHtml(file.name)}</div>
                                    <div style="font-size: var(--font-size-xs); color: var(--color-text-secondary);">${this.formatFileSize(file.size)}</div>
                                </div>
                            </div>
                            <button class="btn btn-sm btn-danger" onclick="protobufComponent.removeBinaryFile(${index})" title="Remove file" style="padding: var(--spacing-xs);">
                                <svg style="width: 16px; height: 16px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <line x1="18" y1="6" x2="6" y2="18"/>
                                    <line x1="6" y1="6" x2="18" y2="18"/>
                                </svg>
                            </button>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    removeBinaryFile(index) {
        this.binaryFiles.splice(index, 1);
        this.renderBinaryFiles();
        this.updateUI();
    }

    clearBinaryFiles() {
        this.binaryFiles = [];
        
        const binaryInput = document.getElementById('binaryFileInput');
        if (binaryInput) {
            binaryInput.value = '';
        }
        
        this.renderBinaryFiles();
        this.updateUI();
    }

    async decodeBinary() {
        if (this.protoFiles.length === 0 || this.binaryFiles.length === 0) {
            notify.error('Please upload proto schema and binary files');
            return;
        }

        if (!this.schemaValidated) {
            notify.error('Please compile schema first');
            return;
        }

        if (!this.selectedMessageType) {
            notify.error('Please select a message type');
            return;
        }

        try {
            const totalFiles = this.binaryFiles.length;
            window.showLoading(`Decoding ${totalFiles} file(s)...`);

            const formData = new FormData();
            formData.append('session_id', this.sessionId);
            formData.append('message_type', this.selectedMessageType);
            formData.append('indent', '2');

            const response = await fetch('/api/v1/protobuf/decode', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            window.hideLoading();

            if (!data.success) {
                throw new Error(data.message || 'Decoding failed');
            }

            this.decodedResults = data.results || [];

            notify.success(`✅ Decoded ${data.files_success}/${data.files_processed} file(s) successfully!`);
            
            this.renderDecodedResults(data);
            this.updateUI();

            this.scrollToElement('decodedResultSection');

        } catch (error) {
            window.hideLoading();
            console.error('Decode error:', error);
            notify.error(`Decoding failed: ${error.message}`);
        }
    }

    renderDecodedResults(data) {
        const container = document.getElementById('decodedResultsDisplay');
        if (!container) return;

        const batchDownloadUrl = `/api/v1/protobuf/download-batch/${this.sessionId}`;

        container.innerHTML = `
            <!-- Stats Summary -->
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: var(--spacing-sm); margin-bottom: var(--spacing-md);">
                <div class="stat-card-compact" style="background: var(--color-success-light); border-left: 4px solid var(--color-success);">
                    <div class="stat-value-compact" style="color: var(--color-success);">${data.files_success}</div>
                    <div class="stat-label-compact">Success</div>
                </div>
                <div class="stat-card-compact" style="${data.files_failed > 0 ? 'background: var(--color-danger-light); border-left: 4px solid var(--color-danger);' : ''}">
                    <div class="stat-value-compact" style="${data.files_failed > 0 ? 'color: var(--color-danger);' : ''}">${data.files_failed}</div>
                    <div class="stat-label-compact">Failed</div>
                </div>
                <div class="stat-card-compact">
                    <div class="stat-value-compact">${this.escapeHtml(this.stripPackagePrefix(data.message_type))}</div>
                    <div class="stat-label-compact">Message Type</div>
                </div>
            </div>

            <!-- Download All Button -->
            ${data.files_success > 1 ? `
                <div style="margin-bottom: var(--spacing-md); display: flex; justify-content: flex-end;">
                    <button class="btn btn-primary" onclick="protobufComponent.downloadBatchZip('${batchDownloadUrl}')">
                        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                            <polyline points="7 10 12 15 17 10"/>
                            <line x1="12" y1="15" x2="12" y2="3"/>
                        </svg>
                        Download All as ZIP (${data.files_success} files)
                    </button>
                </div>
            ` : ''}

            <!-- Decoded Files List -->
            <div class="selected-files-list">
                <div class="list-header">
                    <span style="font-weight: var(--font-weight-semibold); color: var(--color-text);">
                        Decoded Files (${this.decodedResults.length})
                    </span>
                </div>
                <div class="list-body">
                    ${this.decodedResults.map((result, index) => `
                        <div class="file-list-item">
                            <div style="display: flex; align-items: center; gap: var(--spacing-sm); flex: 1;">
                                <div style="font-size: var(--font-size-lg);">
                                    ${result.status === 'success' ? '✅' : '❌'}
                                </div>
                                <div style="flex: 1;">
                                    <div style="font-weight: var(--font-weight-medium); color: var(--color-text);">
                                        ${this.escapeHtml(result.filename)}
                                    </div>
                                    <div style="font-size: var(--font-size-xs); color: var(--color-text-secondary); display: flex; gap: var(--spacing-sm); margin-top: 2px;">
                                        ${result.status === 'success' ? `
                                            <span>Fields: ${result.fields_decoded || 0}</span>
                                            <span>•</span>
                                            <span>Size: ${this.formatFileSize(result.file_size || 0)}</span>
                                        ` : `
                                            <span style="color: var(--color-danger);">${this.escapeHtml(result.error || 'Failed')}</span>
                                        `}
                                    </div>
                                </div>
                            </div>
                            ${result.status === 'success' ? `
                                <div style="display: flex; gap: var(--spacing-xs);">
                                    <button class="btn btn-sm btn-secondary" onclick="protobufComponent.viewResult('${this.escapeHtml(result.file_url)}', '${this.escapeHtml(result.output_filename)}')" title="View JSON">
                                        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                            <circle cx="12" cy="12" r="3"/>
                                        </svg>
                                        View
                                    </button>
                                    <button class="btn btn-sm btn-primary" onclick="protobufComponent.downloadResult('${this.escapeHtml(result.file_url)}', '${this.escapeHtml(result.output_filename)}')" title="Download JSON">
                                        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                                            <polyline points="7 10 12 15 17 10"/>
                                            <line x1="12" y1="15" x2="12" y2="3"/>
                                        </svg>
                                        Download
                                    </button>
                                </div>
                            ` : ''}
                        </div>
                    `).join('')}
                </div>
            </div>

            ${data.note ? `
                <div class="info-box" style="margin-top: var(--spacing-md); background: var(--color-info-bg); border-left: 4px solid var(--color-info); padding: var(--spacing-md); border-radius: var(--radius-md);">
                    <strong>ℹ️ Note:</strong> ${this.escapeHtml(data.note)}
                </div>
            ` : ''}

            <!-- Reset buttons -->
            <div style="margin-top: var(--spacing-md); display: flex; justify-content: flex-end; gap: var(--spacing-sm);">
                <button class="btn btn-secondary" onclick="protobufComponent.clearResults()" title="Clear only decoded results">
                    <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                    </svg>
                    Clear Results
                </button>
                <button class="btn btn-secondary" onclick="protobufComponent.clearBinaryAndResults()" title="Clear binary files and results">
                    <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M3 6h18"/>
                        <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6"/>
                        <path d="M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                        <line x1="10" y1="11" x2="10" y2="17"/>
                        <line x1="14" y1="11" x2="14" y2="17"/>
                    </svg>
                    Clear Binary Files
                </button>
                <button class="btn btn-danger" onclick="protobufComponent.fullReset()" title="Reset everything">
                    <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <polyline points="1 4 1 10 7 10"/>
                        <path d="M3.51 15a9 9 0 102.13-9.36L1 10"/>
                    </svg>
                    Reset All
                </button>
            </div>
        `;
    }

    async downloadBatchZip(url) {
        try {
            const link = document.createElement('a');
            link.href = url;
            link.download = `protobuf_decoded_${this.sessionId.substring(0, 8)}.zip`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            notify.success('Downloading batch ZIP...');

        } catch (error) {
            console.error('Batch download error:', error);
            notify.error(`Batch download failed: ${error.message}`);
        }
    }

    async downloadResult(fileUrl, filename) {
        try {
            const link = document.createElement('a');
            link.href = fileUrl;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            notify.success(`Downloading ${filename}`);

        } catch (error) {
            console.error('Download error:', error);
            notify.error(`Download failed: ${error.message}`);
        }
    }

    async viewResult(fileUrl, filename) {
        try {
            window.showLoading('Loading JSON...');

            const response = await fetch(fileUrl);
            
            if (!response.ok) {
                throw new Error('File not found or expired');
            }

            const text = await response.text();

            window.hideLoading();

            let jsonString;
            let isTruncated = false;

            if (text.length > this.MAX_JSON_PREVIEW) {
                jsonString = text.substring(0, this.MAX_JSON_PREVIEW);
                isTruncated = true;
            } else {
                try {
                    const jsonData = JSON.parse(text);
                    jsonString = JSON.stringify(jsonData, null, 2);
                } catch (e) {
                    jsonString = text;
                }
            }

            const preview = isTruncated 
                ? jsonString + '\n\n... (truncated, download full file)'
                : jsonString;

            const content = `
                <div style="max-height: 60vh; overflow: auto;">
                    <pre class="json-preview" style="margin: 0; padding: var(--spacing-md); background: var(--color-surface); border-radius: var(--radius-sm); font-family: var(--font-family-mono); font-size: var(--font-size-sm); line-height: var(--line-height-relaxed); color: var(--color-text); overflow-x: auto;"><code>${this.escapeHtml(preview)}</code></pre>
                </div>
            `;

            modal.show({
                title: `View JSON - ${this.escapeHtml(filename)}`,
                content: content,
                size: 'large',
                buttons: [
                    {
                        text: 'Copy to Clipboard',
                        class: 'btn-secondary',
                        onClick: async () => {
                            try {
                                await navigator.clipboard.writeText(text);
                                notify.success('Copied to clipboard!');
                            } catch (error) {
                                notify.error('Failed to copy to clipboard');
                            }
                        }
                    },
                    {
                        text: 'Download',
                        class: 'btn-primary',
                        onClick: () => {
                            this.downloadResult(fileUrl, filename);
                            modal.close();
                        }
                    },
                    {
                        text: 'Close',
                        class: 'btn-secondary',
                        onClick: () => modal.close()
                    }
                ]
            });

        } catch (error) {
            window.hideLoading();
            console.error('View error:', error);
            notify.error(`Failed to load JSON: ${error.message}`);
        }
    }

    clearResults() {
        this.decodedResults = [];
        const resultSection = document.getElementById('decodedResultSection');
        if (resultSection) {
            resultSection.style.display = 'none';
        }
        notify.info('Results cleared');
    }

    clearBinaryAndResults() {
        this.binaryFiles = [];
        this.decodedResults = [];
        
        const binaryInput = document.getElementById('binaryFileInput');
        if (binaryInput) binaryInput.value = '';
        
        this.renderBinaryFiles();
        this.updateUI();
        
        notify.info('Binary files and results cleared');
    }

    async fullReset() {
        // Cleanup session
        if (this.sessionId) {
            try {
                await uploadService.cleanupSession(this.sessionId);
            } catch (error) {
                console.error('Session cleanup error:', error);
            }
        }

        // Reset state
        this.protoFiles = [];
        this.binaryFiles = [];
        this.decodedResults = [];
        this.schemaValidated = false;
        this.compiledSchema = null;
        this.selectedMessageType = null;
        
        // Create new session
        await this.createSession();
        
        // Re-render
        this.render();
        
        // ✅ Re-attach event listeners after render
        this.setupEventListeners();
        
        notify.info('Full reset complete');
        
        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }


    updateUI() {
        const compileBtn = document.getElementById('compileProtoBtn');
        if (compileBtn) {
            compileBtn.disabled = this.protoFiles.length === 0;
        }

        const binarySection = document.getElementById('binaryUploadSection');
        if (binarySection) {
            binarySection.style.display = this.schemaValidated ? 'block' : 'none';
        }

        const decodeBtn = document.getElementById('decodeBtn');
        if (decodeBtn) {
            decodeBtn.disabled = !this.schemaValidated || this.binaryFiles.length === 0;
        }

        const resultSection = document.getElementById('decodedResultSection');
        if (resultSection) {
            resultSection.style.display = this.decodedResults.length > 0 ? 'block' : 'none';
        }
    }

    formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.protobufComponent = new ProtobufComponent();
});
