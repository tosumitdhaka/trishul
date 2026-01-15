/* ============================================
   Modal Utility
   ============================================ */

class Modal {
    constructor() {
        this.currentModal = null;
    }

    /**
     * Show modal
     */
    show(options = {}) {
        const {
            title = 'Modal',
            content = '',
            size = 'medium',
            buttons = [],
            onClose = null,
        } = options;

        // Close existing modal
        this.close();

        const sizeClass = `modal-${size}`;

        const modalHTML = `
            <div class="modal-backdrop" id="modalBackdrop">
                <div class="modal ${sizeClass}" id="modalDialog">
                    <div class="modal-header">
                        <h3 class="modal-title">${title}</h3>
                        <svg class="modal-close" id="modalCloseBtn" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <line x1="18" y1="6" x2="6" y2="18"/>
                            <line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                    </div>
                    <div class="modal-body">
                        ${content}
                    </div>
                    ${
                        buttons.length > 0
                            ? `
                        <div class="modal-footer">
                            ${buttons
                                .map(
                                    (btn, index) => `
                                <button class="btn ${btn.class || 'btn-secondary'}" data-modal-btn="${index}">
                                    ${btn.text}
                                </button>
                            `
                                )
                                .join('')}
                        </div>
                    `
                            : ''
                    }
                </div>
            </div>
        `;

        const container = document.getElementById('modalContainer') || document.body;
        container.insertAdjacentHTML('beforeend', modalHTML);

        this.currentModal = document.getElementById('modalBackdrop');

        // Setup event listeners
        const closeBtn = document.getElementById('modalCloseBtn');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                if (onClose) onClose();
                this.close();
            });
        }

        // Close on backdrop click
        this.currentModal.addEventListener('click', (e) => {
            if (e.target === this.currentModal) {
                if (onClose) onClose();
                this.close();
            }
        });

        // Button handlers
        buttons.forEach((btn, index) => {
            const btnElement = this.currentModal.querySelector(`[data-modal-btn="${index}"]`);
            if (btnElement && btn.onClick) {
                btnElement.addEventListener('click', btn.onClick);
            }
        });

        // ESC key to close
        const escHandler = (e) => {
            if (e.key === 'Escape') {
                if (onClose) onClose();
                this.close();
                document.removeEventListener('keydown', escHandler);
            }
        };
        document.addEventListener('keydown', escHandler);
    }

    /**
     * Close modal
     */
    close() {
        if (this.currentModal) {
            this.currentModal.remove();
            this.currentModal = null;
        }
    }

    /**
     * Confirm dialog
     */
    async confirm(options = {}) {
        const {
            title = 'Confirm',
            message = 'Are you sure?',
            confirmText = 'Confirm',
            cancelText = 'Cancel',
            danger = false,
        } = options;

        return new Promise((resolve) => {
            this.show({
                title,
                content: `<p style="color: var(--color-text); font-size: 0.9375rem;">${message}</p>`,
                size: 'medium',
                buttons: [
                    {
                        text: cancelText,
                        class: 'btn-secondary',
                        onClick: () => {
                            this.close();
                            resolve(false);
                        },
                    },
                    {
                        text: confirmText,
                        class: danger ? 'btn-danger' : 'btn-primary',
                        onClick: () => {
                            this.close();
                            resolve(true);
                        },
                    },
                ],
                onClose: () => resolve(false),
            });
        });
    }

    /**
     * ✅ FIXED: Confirm with text input validation
     * Uses same CSS classes as existing modal system
     */
    async confirmWithInput(options = {}) {
        const {
            title = 'Confirm Action',
            message = 'Please confirm this action.',
            inputLabel = 'Type to confirm:',
            expectedValue = 'CONFIRM',
            confirmText = 'Confirm',
            cancelText = 'Cancel',
            danger = false,
        } = options;

        return new Promise((resolve) => {
            // ✅ FIXED: Use same structure as show() method
            const modalHTML = `
                <div class="modal-backdrop" id="confirmInputModal">
                    <div class="modal modal-medium" id="confirmInputDialog">
                        <div class="modal-header">
                            <h3 class="modal-title">${title}</h3>
                            <svg class="modal-close" id="confirmInputModalClose" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <line x1="18" y1="6" x2="6" y2="18"/>
                                <line x1="6" y1="6" x2="18" y2="18"/>
                            </svg>
                        </div>
                        <div class="modal-body">
                            <p style="margin-bottom: var(--spacing-lg); color: var(--color-text);">
                                ${message}
                            </p>
                            <div class="form-group">
                                <label class="form-label" for="confirmInput">
                                    ${inputLabel}
                                </label>
                                <input 
                                    type="text" 
                                    id="confirmInput" 
                                    class="form-control" 
                                    placeholder="${expectedValue}"
                                    autocomplete="off"
                                    style="width: 100%;"
                                >
                                <small style="display: block; margin-top: var(--spacing-xs); color: var(--color-text-secondary); font-size: var(--font-size-xs);">
                                    Type <strong>${expectedValue}</strong> to enable the ${confirmText} button
                                </small>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button class="btn btn-secondary" id="confirmInputCancelBtn">
                                ${cancelText}
                            </button>
                            <button 
                                class="btn ${danger ? 'btn-danger' : 'btn-primary'}" 
                                id="confirmInputConfirmBtn"
                                disabled
                            >
                                ${confirmText}
                            </button>
                        </div>
                    </div>
                </div>
            `;

            // ✅ FIXED: Use same container as show() method
            const container = document.getElementById('modalContainer') || document.body;
            container.insertAdjacentHTML('beforeend', modalHTML);

            const modal = document.getElementById('confirmInputModal');
            const input = document.getElementById('confirmInput');
            const confirmBtn = document.getElementById('confirmInputConfirmBtn');
            const cancelBtn = document.getElementById('confirmInputCancelBtn');
            const closeBtn = document.getElementById('confirmInputModalClose');

            // Enable/disable confirm button based on input
            input.addEventListener('input', (e) => {
                const isValid = e.target.value.trim() === expectedValue;
                confirmBtn.disabled = !isValid;
            });

            // Focus input
            setTimeout(() => input.focus(), 100);

            // Confirm handler
            const handleConfirm = () => {
                if (input.value.trim() === expectedValue) {
                    modal.remove();
                    resolve(true);
                }
            };

            // Cancel handler
            const handleCancel = () => {
                modal.remove();
                resolve(false);
            };

            // Event listeners
            confirmBtn.addEventListener('click', handleConfirm);
            cancelBtn.addEventListener('click', handleCancel);
            closeBtn.addEventListener('click', handleCancel);

            // Enter key to confirm (if input is valid)
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && input.value.trim() === expectedValue) {
                    handleConfirm();
                } else if (e.key === 'Escape') {
                    handleCancel();
                }
            });

            // Click outside to cancel
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    handleCancel();
                }
            });

            // ESC key handler
            const escHandler = (e) => {
                if (e.key === 'Escape') {
                    handleCancel();
                    document.removeEventListener('keydown', escHandler);
                }
            };
            document.addEventListener('keydown', escHandler);
        });
    }



    /**
     * Prompt dialog
     */
    async prompt(options = {}) {
        const {
            title = 'Input',
            message = 'Enter value:',
            defaultValue = '',
            placeholder = '',
            confirmText = 'OK',
            cancelText = 'Cancel',
        } = options;

        return new Promise((resolve) => {
            const inputId = 'modalPromptInput';

            this.show({
                title,
                content: `
                    <div>
                        <p style="color: var(--color-text); font-size: 0.9375rem; margin-bottom: var(--spacing-md);">${message}</p>
                        <input type="text" id="${inputId}" class="form-input" 
                               value="${defaultValue}" placeholder="${placeholder}" 
                               style="width: 100%;">
                    </div>
                `,
                size: 'medium',
                buttons: [
                    {
                        text: cancelText,
                        class: 'btn-secondary',
                        onClick: () => {
                            this.close();
                            resolve(null);
                        },
                    },
                    {
                        text: confirmText,
                        class: 'btn-primary',
                        onClick: () => {
                            const input = document.getElementById(inputId);
                            const value = input ? input.value : null;
                            this.close();
                            resolve(value);
                        },
                    },
                ],
                onClose: () => resolve(null),
            });

            // Focus input
            setTimeout(() => {
                const input = document.getElementById(inputId);
                if (input) {
                    input.focus();
                    input.select();
                }
            }, 100);
        });
    }

    /**
     * Alert dialog
     */
    async alert(options = {}) {
        const { title = 'Alert', message = '', buttonText = 'OK' } = options;

        return new Promise((resolve) => {
            this.show({
                title,
                content: `<p style="color: var(--color-text); font-size: 0.9375rem;">${message}</p>`,
                size: 'medium',
                buttons: [
                    {
                        text: buttonText,
                        class: 'btn-primary',
                        onClick: () => {
                            this.close();
                            resolve();
                        },
                    },
                ],
                onClose: () => resolve(),
            });
        });
    }
}

// Create global instance
window.modal = new Modal();
