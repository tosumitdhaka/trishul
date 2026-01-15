/* ============================================
   Parser Component - Optimized v2.0
   ============================================ */

class ParserComponent {
    constructor() {
        this.currentFiles = [];
        this.currentData = null;
        this.dataTable = null;
        this.currentSession = null;
        this.uploadInProgress = false;
        this.init();
    }

    /**
     * Initialize parser component
     */
    init() {
        this.setupEventListeners();
        this.loadSettings();
        this.updateUploadAreaText();
    }

    /**
     * Load settings
     */
    loadSettings() {
        const deduplicate = window.settings?.get('parserDeduplicate', true);
        const strategy = window.settings?.get('parserDedupStrategy', 'smart');
        const recompile = window.settings?.get('forceCompile', false);

        const deduplicateCheckbox = document.getElementById('deduplicateOption');
        const strategySelect = document.getElementById('dedupStrategy');
        const forceCompileCheckbox = document.getElementById('forceCompile');

        if (deduplicateCheckbox) deduplicateCheckbox.checked = deduplicate;
        if (strategySelect) strategySelect.value = strategy;
        if (forceCompileCheckbox) forceCompileCheckbox.checked = recompile;
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Input type selector
        const inputTypeRadios = document.querySelectorAll('input[name="inputType"]');
        inputTypeRadios.forEach((radio) => {
            radio.addEventListener('change', (e) => {
                this.handleInputTypeChange(e.target.value);
            });
        });

        // Text input listener
        const textInput = document.getElementById('mibTextInput');
        if (textInput) {
            textInput.addEventListener('input', (e) => {
                this.updateParseButtonState();
            });
        }

        // Upload area
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');

        if (uploadArea && fileInput) {
            // Click to browse
            uploadArea.addEventListener('click', () => {
                if (this.uploadInProgress) return;

                const inputType = document.querySelector('input[name="inputType"]:checked').value;

                if (inputType === 'directory') {
                    fileInput.setAttribute('webkitdirectory', '');
                    fileInput.setAttribute('directory', '');
                    fileInput.removeAttribute('multiple');
                    fileInput.removeAttribute('accept');
                } else if (inputType === 'archive') {
                    fileInput.removeAttribute('webkitdirectory');
                    fileInput.removeAttribute('directory');
                    fileInput.removeAttribute('multiple');
                    fileInput.setAttribute('accept', '.zip');
                } else {
                    fileInput.removeAttribute('webkitdirectory');
                    fileInput.removeAttribute('directory');
                    fileInput.setAttribute('multiple', '');
                    fileInput.setAttribute('accept', '.mib,.txt,.my');
                }

                fileInput.click();
            });

            // File selection
            fileInput.addEventListener('change', (e) => {
                this.handleFileSelection(e.target.files);
            });

            // Drag and drop
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                if (!this.uploadInProgress) {
                    uploadArea.classList.add('dragover');
                }
            });

            uploadArea.addEventListener('dragleave', () => {
                uploadArea.classList.remove('dragover');
            });

            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');

                if (this.uploadInProgress) return;

                const items = e.dataTransfer.items;
                const files = e.dataTransfer.files;

                if (items && items.length > 0 && items[0].webkitGetAsEntry) {
                    this.handleDroppedItems(items);
                } else {
                    this.handleFileSelection(files);
                }
            });
        }

        // Parse button
        const parseBtn = document.getElementById('parseBtn');
        if (parseBtn) {
            parseBtn.addEventListener('click', () => {
                this.handleParse();
            });
        }

        // Settings changes
        const deduplicateCheckbox = document.getElementById('deduplicateOption');
        const strategySelect = document.getElementById('dedupStrategy');
        const forceCompileCheckbox = document.getElementById('forceCompile');

        if (deduplicateCheckbox) {
            deduplicateCheckbox.addEventListener('change', (e) => {
                window.settings?.set('parserDeduplicate', e.target.checked);
            });
        }

        if (strategySelect) {
            strategySelect.addEventListener('change', (e) => {
                window.settings?.set('parserDedupStrategy', e.target.value);
            });
        }

        if (forceCompileCheckbox) {
            forceCompileCheckbox.addEventListener('change', (e) => {
                window.settings?.set('forceCompile', e.target.checked);
            });
        }
    }

    /**
     * Handle input type change
     */
    handleInputTypeChange(type) {
        const textInputArea = document.getElementById('textInputArea');
        const uploadArea = document.getElementById('uploadArea');
        const selectedFiles = document.getElementById('selectedFiles');

        if (type === 'text') {
            if (textInputArea) textInputArea.style.display = 'block';
            if (uploadArea) uploadArea.style.display = 'none';
            if (selectedFiles) selectedFiles.style.display = 'none';
        } else {
            if (textInputArea) textInputArea.style.display = 'none';
            if (uploadArea) uploadArea.style.display = 'block';
            this.updateUploadAreaText(type);
        }

        this.currentFiles = [];
        this.updateSelectedFiles();
        this.updateParseButtonState();
    }

    /**
     * Update upload area text
     */
    updateUploadAreaText(type) {
        const uploadText = document.querySelector('.upload-text');
        const uploadHint = document.querySelector('.upload-hint');
        const uploadFormats = document.querySelector('.upload-formats');

        if (!uploadText || !uploadHint || !uploadFormats) return;

        const texts = {
            files: {
                text: 'Drop MIB files here',
                hint: 'Or click to browse',
                formats: 'Supports: .mib, .txt, .my',
            },
            directory: {
                text: 'Drop directory here',
                hint: 'Click to choose a folder',
                formats: 'Supports: Folders containing .mib, .txt, .my files',
            },
            archive: {
                text: 'Drop archive here',
                hint: 'Or click to browse',
                formats: 'Supports: .zip archives (max 100MB)',
            },
        };

        const config = texts[type] || texts.files;
        uploadText.textContent = config.text;
        uploadHint.textContent = config.hint;
        uploadFormats.textContent = config.formats;
    }

    /**
     * Handle file selection
     */
    async handleFileSelection(files) {
        if (!files || files.length === 0) return;

        const inputType = document.querySelector('input[name="inputType"]:checked').value;

        if (inputType === 'archive') {
            const archiveFiles = Array.from(files).filter((file) => {
                const ext = file.name.split('.').pop().toLowerCase();
                return ext === 'zip';
            });

            if (archiveFiles.length === 0) {
                notify.warning('No valid archive files selected. Supported: .zip');
                return;
            }

            await this.extractArchiveClientSide(archiveFiles[0]);
        } else {
            this.currentFiles = Array.from(files).filter((file) => {
                const ext = file.name.split('.').pop().toLowerCase();
                return ['mib', 'txt', 'my'].includes(ext);
            });

            if (this.currentFiles.length === 0) {
                notify.warning('No valid MIB files selected. Supported: .mib, .txt, .my');
                return;
            }

            this.updateSelectedFiles();
            this.updateParseButtonState();
        }
    }

    /**
     * Extract archive client-side using JSZip
     */
    async extractArchiveClientSide(archiveFile) {
        try {
            const maxSize = 100 * 1024 * 1024; // 100MB
            if (archiveFile.size > maxSize) {
                notify.error(
                    `Archive too large: ${Utils.formatFileSize(archiveFile.size)}. ` +
                        `Maximum: ${Utils.formatFileSize(maxSize)}`
                );
                return;
            }

            window.showLoading(`Extracting ${archiveFile.name}...`);

            if (typeof JSZip === 'undefined') {
                throw new Error('JSZip library not loaded. Please refresh the page.');
            }

            const arrayBuffer = await archiveFile.arrayBuffer();
            const zip = await JSZip.loadAsync(arrayBuffer);

            const supportedExtensions = ['mib', 'txt', 'my'];
            const extractedFiles = [];
            const ignoredFiles = [];
            const filePromises = [];

            zip.forEach((relativePath, zipEntry) => {
                if (zipEntry.dir) return;

                const fileName = relativePath.split('/').pop();
                const ext = fileName.split('.').pop().toLowerCase();

                if (supportedExtensions.includes(ext)) {
                    filePromises.push(
                        zipEntry.async('blob').then((blob) => {
                            const file = new File([blob], fileName, {
                                type: 'application/octet-stream',
                                lastModified: zipEntry.date?.getTime() || Date.now(),
                            });
                            extractedFiles.push(file);
                        })
                    );
                } else {
                    ignoredFiles.push(fileName);
                }
            });

            await Promise.all(filePromises);
            window.hideLoading();

            if (extractedFiles.length === 0) {
                notify.error('No MIB files found in archive');
                return;
            }

            this.currentFiles = extractedFiles;
            this.updateSelectedFiles();
            this.updateParseButtonState();

            notify.success(
                `Extracted ${extractedFiles.length} MIB file(s)` +
                    (ignoredFiles.length > 0 ? ` (${ignoredFiles.length} ignored)` : '')
            );
        } catch (error) {
            window.hideLoading();
            console.error('Archive extraction failed:', error);

            let errorMessage = 'Failed to extract archive';
            if (error.message.includes('Corrupted zip')) {
                errorMessage = 'Archive file is corrupted or invalid';
            } else if (error.message.includes('encrypted')) {
                errorMessage = 'Encrypted archives are not supported';
            }

            notify.error(errorMessage);
        }
    }

    /**
     * Handle dropped items (for directory support)
     */
    async handleDroppedItems(items) {
        const files = [];

        for (let i = 0; i < items.length; i++) {
            const item = items[i].webkitGetAsEntry();
            if (item) {
                await this.traverseFileTree(item, files);
            }
        }

        if (files.length > 0) {
            this.handleFileSelection(files);
        }
    }

    /**
     * Traverse file tree
     */
    async traverseFileTree(item, files) {
        return new Promise((resolve) => {
            if (item.isFile) {
                item.file((file) => {
                    const ext = file.name.split('.').pop().toLowerCase();
                    if (['mib', 'txt', 'my'].includes(ext)) {
                        files.push(file);
                    }
                    resolve();
                });
            } else if (item.isDirectory) {
                const dirReader = item.createReader();
                dirReader.readEntries(async (entries) => {
                    for (const entry of entries) {
                        await this.traverseFileTree(entry, files);
                    }
                    resolve();
                });
            }
        });
    }

    /**
     * ✅ OPTIMIZED: Update selected files display (removed inline styles)
     */
    updateSelectedFiles() {
        const selectedFilesDiv = document.getElementById('selectedFiles');
        if (!selectedFilesDiv) return;

        if (this.currentFiles.length === 0) {
            selectedFilesDiv.style.display = 'none';
            return;
        }

        const totalSize = this.currentFiles.reduce((sum, file) => sum + file.size, 0);

        selectedFilesDiv.style.display = 'block';
        selectedFilesDiv.innerHTML = `
            <div class="selected-files-list">
                <div class="list-header">
                    <span class="list-header-title">
                        ${this.currentFiles.length} file${this.currentFiles.length > 1 ? 's' : ''} selected 
                        (${Utils.formatFileSize(totalSize)})
                    </span>
                    <button class="btn btn-sm" id="clearFilesBtn">Clear All</button>
                </div>
                <div class="list-body">
                    ${this.currentFiles
                        .map(
                            (file, index) => `
                        <div class="file-list-item">
                            <div class="file-item-content">
                                <svg class="file-item-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                                    <polyline points="14 2 14 8 20 8"/>
                                </svg>
                                <div class="file-item-info">
                                    <div class="file-item-name" title="${file.name}">
                                        ${file.name}
                                    </div>
                                    <div class="file-item-size">
                                        ${Utils.formatFileSize(file.size)}
                                    </div>
                                </div>
                            </div>
                            <button class="btn btn-sm icon remove-file-btn" data-index="${index}" title="Remove file">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <line x1="18" y1="6" x2="6" y2="18"/>
                                    <line x1="6" y1="6" x2="18" y2="18"/>
                                </svg>
                            </button>
                        </div>
                    `
                        )
                        .join('')}
                </div>
            </div>
        `;

        // Event listeners
        const clearBtn = document.getElementById('clearFilesBtn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                this.currentFiles = [];
                this.updateSelectedFiles();
                this.updateParseButtonState();
            });
        }

        const removeButtons = selectedFilesDiv.querySelectorAll('.remove-file-btn');
        removeButtons.forEach((btn) => {
            btn.addEventListener('click', () => {
                const index = parseInt(btn.dataset.index);
                this.currentFiles.splice(index, 1);
                this.updateSelectedFiles();
                this.updateParseButtonState();
            });
        });
    }

    /**
     * Update parse button state
     */
    updateParseButtonState() {
        const parseBtn = document.getElementById('parseBtn');
        if (!parseBtn) return;

        const inputType = document.querySelector('input[name="inputType"]:checked').value;

        if (inputType === 'text') {
            const textInput = document.getElementById('mibTextInput');
            parseBtn.disabled = !textInput || textInput.value.trim().length === 0;
        } else {
            parseBtn.disabled = this.currentFiles.length === 0 || this.uploadInProgress;
        }
    }

    /**
     * Handle parse
     */
    async handleParse() {
        const inputType = document.querySelector('input[name="inputType"]:checked').value;

        if (inputType === 'text') {
            await this.parseText();
        } else {
            await this.parseFiles();
        }
    }

    /**
     * Parse text input
     */
    async parseText() {
        const textInput = document.getElementById('mibTextInput');
        if (!textInput || !textInput.value.trim()) {
            notify.warning('Please enter MIB content');
            return;
        }

        const content = textInput.value.trim();

        try {
            window.showLoading('Parsing MIB text...');

            const result = await api.parseText(content, 'inline.mib');

            window.hideLoading();

            if (result && result.success) {
                notify.success(`Parsed ${result.records_parsed} records`);

                if (result.data && Array.isArray(result.data) && result.data.length > 0) {
                    this.displayResults(result.data);
                } else {
                    notify.warning('Parse succeeded but no data returned');
                }
            } else {
                notify.error('Parse failed');
            }
        } catch (error) {
            window.hideLoading();
            console.error('Parse text error:', error);
            notify.error(`Parse failed: ${error.message}`);
        }
    }

    /**
     * Parse files using upload service
     */
    async parseFiles() {
        if (this.currentFiles.length === 0) {
            notify.warning('Please select files to parse');
            return;
        }

        const deduplicate = document.getElementById('deduplicateOption')?.checked || false;
        const strategy = document.getElementById('dedupStrategy')?.value || 'smart';
        const force_compile = document.getElementById('forceCompile')?.checked || false;
        const jobName = document.getElementById('jobName')?.value || null;

        try {
            this.uploadInProgress = true;
            this.updateParseButtonState();

            // Step 1: Create upload session
            notify.info('Creating upload session...');
            const session = await window.uploadService.createSession();

            if (!session || !session.id) {
                throw new Error('Failed to create upload session');
            }

            this.currentSession = session;

            // Step 2: Upload files
            const totalSize = this.currentFiles.reduce((sum, file) => sum + file.size, 0);
            const showProgress = totalSize > 10 * 1024 * 1024;

            if (showProgress) {
                this.showUploadProgress(0, 0, totalSize);
            } else {
                window.showLoading(`Uploading ${this.currentFiles.length} file(s)...`);
            }

            const uploadResult = await window.uploadService.uploadFiles(
                session.id,
                this.currentFiles,
                showProgress
                    ? (percent, loaded, total) => {
                          this.updateUploadProgress(percent, loaded, total);
                      }
                    : null
            );

            if (showProgress) {
                this.hideUploadProgress();
            } else {
                window.hideLoading();
            }

            if (!uploadResult || !uploadResult.success) {
                throw new Error('File upload failed');
            }

            if (uploadResult.files_uploaded === 0) {
                throw new Error('No files were uploaded successfully');
            }

            notify.success(`Uploaded ${uploadResult.files_uploaded} file(s)`);

            // Step 3: Parse session directory
            window.showLoading('Starting parse job...');

            const parseResult = await api.parseSession(session.id, {
                deduplicate: deduplicate,
                dedup_strategy: strategy,
                force_compile: force_compile,
                job_name: jobName,
            });

            window.hideLoading();

            // Always creates background job
            if (parseResult.job_id) {
                notify.success(`Job created: ${parseResult.message}`);

                // Switch to jobs tab
                setTimeout(() => {
                    const jobsTab = document.querySelector('[data-view="jobs"]');
                    if (jobsTab) jobsTab.click();
                }, 1000);
            } else {
                notify.error('Failed to create parse job');
            }
        } catch (error) {
            window.hideLoading();
            this.hideUploadProgress();

            console.error('Parse files failed:', error);
            notify.error(`Parse failed: ${error.message}`);

            // Cleanup session on error
            if (this.currentSession) {
                try {
                    await window.uploadService.cleanupSession(this.currentSession.id);
                    this.currentSession = null;
                } catch (cleanupError) {
                    console.error('Session cleanup failed:', cleanupError);
                }
            }
        } finally {
            this.uploadInProgress = false;
            this.updateParseButtonState();
        }
    }

    /**
     * ✅ OPTIMIZED: Show upload progress (removed inline styles)
     */
    showUploadProgress(percent, loaded, total) {
        const overlay = document.getElementById('loadingOverlay');
        const text = document.getElementById('loadingText');

        if (overlay && text) {
            overlay.style.display = 'flex';
            text.innerHTML = `
                <div class="upload-progress-container">
                    <div class="upload-progress-title">Uploading files...</div>
                    <div class="upload-progress-bar-container">
                        <div class="upload-progress-bar-fill" style="width: ${percent}%;"></div>
                    </div>
                    <div class="upload-progress-stats">
                        ${Utils.formatFileSize(loaded)} / ${Utils.formatFileSize(total)} (${Math.round(percent)}%)
                    </div>
                </div>
            `;
        }
    }

    /**
     * ✅ OPTIMIZED: Update upload progress (removed inline styles)
     */
    updateUploadProgress(percent, loaded, total) {
        const text = document.getElementById('loadingText');
        if (text) {
            text.innerHTML = `
                <div class="upload-progress-container">
                    <div class="upload-progress-title">Uploading files...</div>
                    <div class="upload-progress-bar-container">
                        <div class="upload-progress-bar-fill" style="width: ${percent}%;"></div>
                    </div>
                    <div class="upload-progress-stats">
                        ${Utils.formatFileSize(loaded)} / ${Utils.formatFileSize(total)} (${Math.round(percent)}%)
                    </div>
                </div>
            `;
        }
    }

    /**
     * Hide upload progress
     */
    hideUploadProgress() {
        window.hideLoading();
    }

    /**
     * Display results (for inline parsing only)
     */
    displayResults(data) {
        if (!data || !Array.isArray(data) || data.length === 0) {
            notify.warning('No data to display');
            return;
        }

        this.currentData = data;

        const resultsSection = document.getElementById('resultsSection');
        if (resultsSection) {
            resultsSection.style.display = 'block';
            resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        if (!this.dataTable) {
            this.dataTable = new UnifiedDataTable('parserDataTable', {
                title: 'Parsed Data',
                viewName: 'parser',
                searchable: true,
                sortable: true,
                filterable: true,
                exportable: true,
                analyzable: true,
                onAnalyze: (data) => this.handleAnalyze(data),
                onExport: (data) => this.handleExport(data),
            });
        }

        this.dataTable.setData(data);
        this.setupSaveToDbButton();
    }

    /**
     * Setup save to database button
     */
    setupSaveToDbButton() {
        const saveBtn = document.getElementById('saveToDbBtn');
        if (!saveBtn) return;

        const newBtn = saveBtn.cloneNode(true);
        saveBtn.parentNode.replaceChild(newBtn, saveBtn);

        newBtn.addEventListener('click', async () => {
            const tableName = await modal.prompt({
                title: 'Save to Database',
                message: 'Enter table name:',
                defaultValue: 'mib_objects',
                placeholder: 'table_name',
                confirmText: 'Save',
                cancelText: 'Cancel',
            });

            if (!tableName) return;

            if (!/^[a-zA-Z][a-zA-Z0-9_]*$/.test(tableName)) {
                notify.error('Invalid table name. Use letters, numbers, and underscores only.');
                return;
            }

            await this.saveToDatabase(tableName);
        });
    }

    /**
     * Save to database
     */
    async saveToDatabase(tableName) {
        if (!this.currentData || this.currentData.length === 0) {
            notify.warning('No data to save');
            return;
        }

        try {
            window.showLoading(`Saving ${this.currentData.length} records...`);

            await api.importToUserTable(tableName, this.currentData, 'replace');

            window.hideLoading();

            notify.success(`Saved ${this.currentData.length} records to ${tableName}`);

            // Refresh database tables list
            if (window.databaseComponent) {
                window.databaseComponent.loadTables();
            }
        } catch (error) {
            window.hideLoading();
            notify.error(`Save failed: ${error.message}`);
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

        try {
            window.showLoading('Analyzing data...');
            const results = await api.analyzeData(data, ['all']);
            window.hideLoading();

            // console.log('Analysis results:', results);
            notify.success('Analysis complete');
        } catch (error) {
            window.hideLoading();
            notify.error(`Analysis failed: ${error.message}`);
        }
    }

    /**
     * Handle export
     */
    handleExport(data) {
        if (!data || data.length === 0) {
            notify.warning('No data to export');
            return;
        }

        // console.log('Export data:', data.length, 'records');
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.parserComponent = new ParserComponent();
});
