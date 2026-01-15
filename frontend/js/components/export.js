/* ============================================
   Export Component - UI ONLY
   Handles export modal and user interaction
   All export logic delegated to ExportService
   ============================================ */

class ExportComponent {
    constructor() {
        this.availableFormats = [];
        this.availableCompressions = [];
        this.currentData = null;
        this.currentExport = null;
        this.init();
    }

    async init() {
        try {
            // Load available formats and compressions
            const [formats, compressions] = await Promise.all([
                window.exportService.getFormats(),
                window.exportService.getCompressions()
            ]);
            
            this.availableFormats = formats;
            this.availableCompressions = compressions;
            
            // console.log('✅ ExportComponent initialized:', {
            //     formats: this.availableFormats.length,
            //     compressions: this.availableCompressions.length
            // });
        } catch (error) {
            console.error('❌ ExportComponent initialization failed:', error);
            
            // Use default formats
            this.availableFormats = [
                { id: 'csv', name: 'CSV', icon: '📊', description: 'Comma-Separated Values' },
                { id: 'json', name: 'JSON', icon: '📄', description: 'JavaScript Object Notation' },
                { id: 'excel', name: 'Excel', icon: '📋', description: 'Microsoft Excel (.xlsx)' },
            ];
            
            // Default compressions
            this.availableCompressions = [
                { id: 'zip', name: 'ZIP', extension: '.zip', description: 'ZIP archive' }
            ];
        }
    }

    showExportModal(source, name, recordCount, options = {}) {
        // console.log('📤 showExportModal called:', { source, name, recordCount, options, });

        if (options.data) {
            // console.log('💾 Storing data for export:', options.data.length, 'rows');
            this.currentData = options.data;
        } else {
            this.currentData = null;
        }

        this.currentExport = {
            source: source,
            name: name,
            recordCount: recordCount,
            options: options,
        };

        const content = this._renderModalContent(source, name, recordCount, options);

        modal.show({
            title: 'Export Data',
            content: content,
            size: 'medium',
            buttons: [
                {
                    text: 'Cancel',
                    class: 'btn-secondary',
                    onClick: () => {
                        this.currentData = null;
                        modal.close();
                    },
                },
                {
                    text: 'Export',
                    class: 'btn-primary',
                    onClick: () => this._handleExport(source, name, options),
                },
            ],
        });
        
        setTimeout(() => this._setupEventListeners(), 100);
    }

    _renderModalContent(source, name, recordCount, options) {
        const sourceLabels = {
            table: 'table',
            job: 'job result',
            query: 'query result',
        };

        const sourceLabel = sourceLabels[source] || 'data';
        let displayName = name;
        let defaultFilename;

        if (source === 'job') {
            const shortJobId = name.substring(0, 12);
            displayName = `Job ${shortJobId}...`;
            defaultFilename = `job_${shortJobId}`;
        } else {
            defaultFilename = `${name}`;
        }
        
        const defaultCompression = window.settings?.getBackend('export.compression', 'zip');

        return `
            <div class="export-modal">
                <p style="margin-bottom: 1.5rem; color: var(--color-text-secondary);">
                    Export data from <strong>${displayName}</strong> (${sourceLabel})
                </p>

                <div class="form-group">
                    <label>Export Format</label>
                    <div class="format-grid-compact" id="formatGrid">
                        ${this.availableFormats.map((format, index) => `
                            <label class="format-option-compact" for="format_${format.id}">
                                <input 
                                    type="radio" 
                                    id="format_${format.id}" 
                                    name="exportFormat" 
                                    value="${format.id}"
                                    ${index === 0 ? 'checked' : ''}
                                />
                                <div class="format-card-compact">
                                    <span class="format-icon-small">${format.icon}</span>
                                    <span class="format-name-small">${format.name}</span>
                                </div>
                            </label>
                        `).join('')}
                    </div>
                </div>

                <div class="form-group">
                    <label for="exportFilename">Filename</label>
                    <input 
                        type="text" 
                        id="exportFilename" 
                        class="form-input" 
                        value="${defaultFilename}"
                        placeholder="Enter filename (without extension)"
                    />
                    <small style="color: var(--color-text-tertiary); display: block; margin-top: 0.5rem;">
                        Extension will be added automatically based on format
                    </small>
                </div>

                ${recordCount > 0 ? `
                    <div class="form-group">
                        <label for="exportLimit">Record Limit (optional)</label>
                        <input 
                            type="number" 
                            id="exportLimit" 
                            class="form-input" 
                            placeholder="Leave empty for all records"
                            min="1"
                            max="${recordCount}"
                        />
                        <small style="color: var(--color-text-tertiary); display: block; margin-top: 0.5rem;">
                            Total records available: ${Utils.formatNumber(recordCount)}
                        </small>
                    </div>
                ` : ''}

                <div class="form-group">
                    <label>Compression</label>
                    <label class="checkbox-label">
                        <input type="checkbox" id="exportCompress">
						<span>Enable</span>
                    </label>
                    <div class="format-grid-compact" id="compressionGrid">
                        ${this.availableCompressions.map((comp) => `
                            <label class="format-option-compact disabled" for="compression_${comp.id}">
                                <input 
                                    type="radio" 
                                    id="compression_${comp.id}" 
                                    name="exportCompression" 
                                    value="${comp.id}"
                                    ${comp.id === defaultCompression ? 'checked' : ''}
                                    disabled
                                />
                                <div class="format-card-compact">
                                    <span class="format-icon-small">${comp.icon}</span>
                                    <span class="format-name-small">${comp.name}</span>
                                </div>
                            </label>
                        `).join('')}
                    </div>
                    <small style="color: var(--color-text-tertiary); display: block; margin-top: 0.5rem;">
                        <strong>Tip:</strong> ZIP is most compatible, GZIP is faster, XZ has best compression ratio
                    </small>
                </div>

                <div class="info-box" style="background: var(--color-info-bg); border-left: 4px solid var(--color-info); padding: 1rem; border-radius: var(--radius-md); margin-top: 1rem;">
                    <strong>Note:</strong> Large exports may take some time. The file will be downloaded automatically when ready.
                </div>
            </div>
        `;
    }
    
    _setupEventListeners() {
        const compressCheckbox = document.getElementById('exportCompress');
        const compressionGrid = document.getElementById('compressionGrid');
        
        if (compressCheckbox && compressionGrid) {
            compressCheckbox.addEventListener('change', (e) => {
                const isEnabled = e.target.checked;
                const compressionOptions = compressionGrid.querySelectorAll('.compression-option-compact');
                const compressionInputs = compressionGrid.querySelectorAll('input[name="exportCompression"]');
                
                compressionOptions.forEach(option => {
                    if (isEnabled) {
                        option.classList.remove('disabled');
                    } else {
                        option.classList.add('disabled');
                    }
                });
                
                compressionInputs.forEach(input => {
                    input.disabled = !isEnabled;
                });
            });
        }
    }

    async _handleExport(source, name, options) {
        const format = document.querySelector('input[name="exportFormat"]:checked')?.value;
        const filename = document.getElementById('exportFilename')?.value.trim();
        const limitInput = document.getElementById('exportLimit');
        const limit = limitInput ? (limitInput.value.trim() ? parseInt(limitInput.value) : null) : null;
        const compress = document.getElementById('exportCompress')?.checked || false;
        const compressionType = document.querySelector('input[name="exportCompression"]:checked')?.value || 'zip';

        if (!format) {
            notify.error('Please select an export format');
            return;
        }

        if (!filename) {
            notify.error('Please enter a filename');
            return;
        }

        modal.close();

        try {
            const exportOptions = {
                source: source,
                name: name,
                format: format,
                filename: filename,
                database: options.database || 'data',
                filters: options.filters,
                columns: options.columns,
                limit: limit,
                compress: compress,
                compression: compress ? compressionType : null,
            };

            if (source === 'query' && this.currentData) {
                // console.log('📦 Passing stored data to export service:', this.currentData.length, 'rows');
                exportOptions.data = this.currentData;
            }

            await window.exportService.export(exportOptions);
            this.currentData = null;
        } catch (error) {
            console.error('Export error:', error);
            this.currentData = null;
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.exportComponent = new ExportComponent();
    // console.log('✅ ExportComponent ready');
});
