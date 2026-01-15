/* ============================================
   Utility Helpers - Enhanced
   ============================================ */

class Utils {
    /**
     * Format number with thousands separator
     */
    static formatNumber(num) {
        if (num === null || num === undefined) return '0';
        return new Intl.NumberFormat().format(num);
    }

    /**
     * Format file size
     */
    static formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
    }

    /**
     * Format date
     */
    static formatDate(date, format = null) {
        if (!date) return '';

        const d = new Date(date);
        if (isNaN(d.getTime())) return '';

        const formatString = format || window.settings?.get('dateFormat') || 'YYYY-MM-DD HH:mm:ss';

        const pad = (n) => String(n).padStart(2, '0');

        const replacements = {
            YYYY: d.getFullYear(),
            MM: pad(d.getMonth() + 1),
            DD: pad(d.getDate()),
            HH: pad(d.getHours()),
            mm: pad(d.getMinutes()),
            ss: pad(d.getSeconds()),
        };

        return formatString.replace(/YYYY|MM|DD|HH|mm|ss/g, (match) => replacements[match]);
    }

    /**
     * Format relative time
     */
    static formatRelativeTime(date) {
        if (!date) return '';

        const d = new Date(date);
        if (isNaN(d.getTime())) return '';

        const now = new Date();
        const diff = now - d;
        const seconds = Math.floor(diff / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (seconds < 60) return 'just now';
        if (minutes < 60) return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
        if (hours < 24) return `${hours} hour${hours > 1 ? 's' : ''} ago`;
        if (days < 30) return `${days} day${days > 1 ? 's' : ''} ago`;

        return this.formatDate(date);
    }

    /**
     * Truncate string
     */
    static truncate(str, length = 100, suffix = '...') {
        if (!str) return '';
        if (str.length <= length) return str;
        return str.substring(0, length - suffix.length) + suffix;
    }

    /**
     * Escape HTML
     */
    static escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Build query string
     */
    static buildQueryString(params) {
        const filtered = Object.entries(params)
            .filter(([_, value]) => value !== null && value !== undefined && value !== '')
            .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`);
        return filtered.length > 0 ? filtered.join('&') : '';
    }

    /**
     * Debounce function
     */
    static debounce(func, wait = 300) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * Throttle function
     */
    static throttle(func, limit = 300) {
        let inThrottle;
        return function (...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => (inThrottle = false), limit);
            }
        };
    }

    /**
     * Deep clone object
     */
    static deepClone(obj) {
        return JSON.parse(JSON.stringify(obj));
    }

    /**
     * Download blob as file
     */
    static downloadBlob(blob, filename) {
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
    }

    /**
     * Copy to clipboard
     */
    static async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (error) {
            // Fallback for older browsers
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            const success = document.execCommand('copy');
            document.body.removeChild(textarea);
            return success;
        }
    }

    /**
     * Generate unique ID
     */
    static generateId(prefix = 'id') {
        return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * Parse CSV
     */
    static parseCSV(csv) {
        const lines = csv.split('\n');
        const headers = lines[0].split(',').map((h) => h.trim());
        const data = [];

        for (let i = 1; i < lines.length; i++) {
            if (!lines[i].trim()) continue;
            const values = lines[i].split(',').map((v) => v.trim());
            const row = {};
            headers.forEach((header, index) => {
                row[header] = values[index];
            });
            data.push(row);
        }

        return data;
    }

    /**
     * Convert to CSV
     */
    static toCSV(data) {
        if (!data || data.length === 0) return '';

        const headers = Object.keys(data[0]);
        const csvRows = [];

        // Add header row
        csvRows.push(headers.join(','));

        // Add data rows
        for (const row of data) {
            const values = headers.map((header) => {
                const value = row[header];
                // Escape quotes and wrap in quotes if contains comma
                const escaped = String(value).replace(/"/g, '""');
                return escaped.includes(',') ? `"${escaped}"` : escaped;
            });
            csvRows.push(values.join(','));
        }

        return csvRows.join('\n');
    }

    /**
     * Group array by key
     */
    static groupBy(array, key) {
        return array.reduce((result, item) => {
            const group = item[key];
            if (!result[group]) {
                result[group] = [];
            }
            result[group].push(item);
            return result;
        }, {});
    }

    /**
     * Sort array by key
     */
    static sortBy(array, key, direction = 'asc') {
        return [...array].sort((a, b) => {
            const aVal = a[key];
            const bVal = b[key];

            if (aVal === bVal) return 0;

            const comparison = aVal < bVal ? -1 : 1;
            return direction === 'asc' ? comparison : -comparison;
        });
    }

    /**
     * Filter array by search term
     */
    static filterBySearch(array, searchTerm, keys = null) {
        if (!searchTerm) return array;

        const term = searchTerm.toLowerCase();

        return array.filter((item) => {
            const searchKeys = keys || Object.keys(item);
            return searchKeys.some((key) => {
                const value = item[key];
                if (value === null || value === undefined) return false;
                return String(value).toLowerCase().includes(term);
            });
        });
    }

    /**
     * Paginate array
     */
    static paginate(array, page = 1, pageSize = 50) {
        const start = (page - 1) * pageSize;
        const end = start + pageSize;
        return {
            data: array.slice(start, end),
            page,
            pageSize,
            total: array.length,
            totalPages: Math.ceil(array.length / pageSize),
        };
    }

    /**
     * Format datetime for display
     * @param {string|Date} dateStr - Date string or Date object
     * @returns {string} Formatted date string
     */
    static formatDateTime(dateStr) {
        if (!dateStr) return 'N/A';

        try {
            const date = new Date(dateStr);

            // Check if valid date
            if (isNaN(date.getTime())) {
                return 'Invalid date';
            }

            // Format: "Jan 15, 2024 at 2:30 PM"
            const options = {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                hour12: true,
            };

            return date.toLocaleString('en-US', options);
        } catch (error) {
            console.error('Date formatting error:', error);
            return dateStr;
        }
    }
}

// Make Utils available globally
window.Utils = Utils;
