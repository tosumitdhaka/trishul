// js/components/notification-center.js - COMPLETE REWRITE

class NotificationCenter {
    constructor() {
        this.notifications = [];
        this.maxNotifications = 50;
        this.unreadCount = 0;
        this.isOpen = false;
        this.init();
    }

    init() {
        this.createPanel();
        this.createToggleButton();
        this.loadNotifications();
        this.setupOutsideClickHandler();
        this.closeOnModalOpen();
    }

    /**
     * Create notification panel
     */
    createPanel() {
        const panel = document.createElement('div');
        panel.id = 'notificationPanel';
        panel.className = 'notification-panel';
        panel.innerHTML = `
            <div class="notification-panel-header">
                <h3>Notifications</h3>
                <div class="notification-panel-actions">
                    <button class="icon-btn" id="markAllReadBtn" title="Mark all as read">
                        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <polyline points="20 6 9 17 4 12"/>
                        </svg>
                    </button>
                    <button class="icon-btn" id="clearAllBtn" title="Clear all">
                        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                        </svg>
                    </button>
                    <button class="icon-btn" id="closePanelBtn" title="Close">
                        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <line x1="18" y1="6" x2="6" y2="18"/>
                            <line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                    </button>
                </div>
            </div>
            <div class="notification-panel-body" id="notificationPanelBody">
                <!-- Notifications will be rendered here -->
            </div>
        `;

        document.body.appendChild(panel);

        // Event listeners
        document
            .getElementById('markAllReadBtn')
            .addEventListener('click', () => this.markAllRead());
        document.getElementById('clearAllBtn').addEventListener('click', () => this.clearAll());
        document.getElementById('closePanelBtn').addEventListener('click', () => this.toggle());
    }

    /**
     * Create toggle button in header
     */
    createToggleButton() {
        const headerRight = document.querySelector('.header-right');
        if (!headerRight) return;

        const button = document.createElement('button');
        button.className = 'icon-btn notification-toggle';
        button.id = 'notificationToggle';
        button.title = 'Notifications';
        button.innerHTML = `
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                <path d="M13.73 21a2 2 0 01-3.46 0"/>
            </svg>
            <span class="notification-badge" id="notificationBadge" style="display: none;">0</span>
        `;

        button.addEventListener('click', () => this.toggle());

        // Insert before health status
        const healthStatus = document.getElementById('healthStatus');
        if (healthStatus) {
            headerRight.insertBefore(button, healthStatus);
        } else {
            headerRight.insertBefore(button, headerRight.firstChild);
        }
    }

    /**
     * Toggle panel
     */
    toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    }

    /**
     * ✅ NEW: Open panel
     */
    open() {
        this.isOpen = true;
        const panel = document.getElementById('notificationPanel');
        if (panel) {
            panel.classList.add('open');
        }
        this.render();
        this.markAllRead();
    }

    /**
     * ✅ NEW: Close panel
     */
    close() {
        this.isOpen = false;
        const panel = document.getElementById('notificationPanel');
        if (panel) {
            panel.classList.remove('open');
        }
    }

    /**
     * Add notification
     */
    add(notification) {
        const notif = {
            id: Utils.generateId('notif'),
            type: notification.type || 'info',
            title: notification.title || 'Notification',
            message: notification.message || '',
            timestamp: new Date(),
            read: false,
            action: notification.action || null,
        };

        this.notifications.unshift(notif);

        // Limit notifications
        if (this.notifications.length > this.maxNotifications) {
            this.notifications = this.notifications.slice(0, this.maxNotifications);
        }

        this.unreadCount++;
        this.updateBadge();
        this.saveNotifications();

        if (this.isOpen) {
            this.render();
        }
    }

    /**
     * Mark all as read
     */
    markAllRead() {
        this.notifications.forEach((n) => (n.read = true));
        this.unreadCount = 0;
        this.updateBadge();
        this.saveNotifications();
        this.render();
    }

    /**
     * Clear all
     */
    async clearAll() {
        const confirmed = await modal.confirm({
            title: 'Clear All Notifications',
            message: 'Are you sure you want to clear all notifications?',
            confirmText: 'Clear',
            cancelText: 'Cancel',
        });

        if (confirmed) {
            this.notifications = [];
            this.unreadCount = 0;
            this.updateBadge();
            this.saveNotifications();
            this.render();
        }
    }

    /**
     * Update badge
     */
    updateBadge() {
        const badge = document.getElementById('notificationBadge');
        if (badge) {
            if (this.unreadCount > 0) {
                badge.textContent = this.unreadCount > 99 ? '99+' : this.unreadCount;
                badge.style.display = 'flex';
            } else {
                badge.style.display = 'none';
            }
        }
    }

    /**
     * ✅ NEW: Setup outside click handler
     */
    setupOutsideClickHandler() {
        document.addEventListener('click', (e) => {
            if (!this.isOpen) return;

            const panel = document.getElementById('notificationPanel');
            const toggle = document.getElementById('notificationToggle');

            // Check if click is outside panel and toggle button
            if (panel && toggle && !panel.contains(e.target) && !toggle.contains(e.target)) {
                this.close(); // ✅ Close panel
            }
        });

        // ✅ Also close on ESC key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) {
                this.close();
            }
        });
    }

    /**
     * Render notifications
     */
    render() {
        const body = document.getElementById('notificationPanelBody');
        if (!body) return;

        if (this.notifications.length === 0) {
            body.innerHTML = `
                <div class="notification-empty">
                    <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                        <path d="M13.73 21a2 2 0 01-3.46 0"/>
                    </svg>
                    <p>No notifications</p>
                </div>
            `;
            return;
        }

        body.innerHTML = this.notifications.map((notif) => this.renderNotification(notif)).join('');

        // Add click listeners
        this.notifications.forEach((notif) => {
            const element = document.getElementById(notif.id);
            if (element && notif.action) {
                element.addEventListener('click', () => {
                    notif.action();
                    this.toggle();
                });
            }
        });
    }

    /**
     * Render single notification
     */
    renderNotification(notif) {
        const icons = {
            success: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><polyline points="20 6 9 17 4 12"/></svg>`,
            error: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
            warning: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
            info: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
        };

        return `
            <div class="notification-item ${notif.read ? 'read' : 'unread'} notification-${notif.type}" id="${notif.id}">
                <div class="notification-icon">${icons[notif.type] || icons.info}</div>
                <div class="notification-content">
                    <div class="notification-title">${notif.title}</div>
                    <div class="notification-message">${notif.message}</div>
                    <div class="notification-time">${Utils.formatRelativeTime(notif.timestamp)}</div>
                </div>
            </div>
        `;
    }

    /**
     * ✅ NEW: Close panel when modal opens
     */
    closeOnModalOpen() {
        // Listen for modal open events
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.classList && node.classList.contains('modal-backdrop')) {
                        // Modal opened, close notification panel
                        this.close();
                    }
                });
            });
        });

        observer.observe(document.body, {
            childList: true,
            subtree: false
        });
    }


    /**
     * Save to localStorage
     */
    saveNotifications() {
        try {
            localStorage.setItem('mib_notifications', JSON.stringify(this.notifications));
        } catch (error) {
            console.error('Failed to save notifications:', error);
        }
    }

    /**
     * Load from localStorage
     */
    loadNotifications() {
        try {
            const saved = localStorage.getItem('mib_notifications');
            if (saved) {
                this.notifications = JSON.parse(saved);
                this.unreadCount = this.notifications.filter((n) => !n.read).length;
                this.updateBadge();
            }
        } catch (error) {
            console.error('Failed to load notifications:', error);
        }
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    window.notificationCenter = new NotificationCenter();
});

// ✅ Integrate with existing notify system
const originalNotify = window.notify;
if (originalNotify) {
    ['success', 'error', 'warning', 'info'].forEach((type) => {
        const original = originalNotify[type].bind(originalNotify);
        originalNotify[type] = function (message, duration) {
            // Show toast
            original(message, duration);

            // Add to notification center
            if (window.notificationCenter) {
                window.notificationCenter.add({
                    type: type,
                    title: type.charAt(0).toUpperCase() + type.slice(1),
                    message: message,
                });
            }
        };
    });
}
