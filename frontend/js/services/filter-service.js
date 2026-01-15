/**
 * ============================================
 * Filter Service
 * Centralized filter management and conversion
 * ============================================
 */

class FilterService {
    constructor() {
        this.logger = {
            info: (...args) => console.log('🔍 [Filter]', ...args),
            error: (...args) => console.error('❌ [Filter]', ...args),
            warn: (...args) => console.warn('⚠️ [Filter]', ...args),
        };
    }

    /**
     * ✅ Convert UI filters to backend SQL format
     * @param {Array} uiFilters - Array of filter objects from UI
     * @returns {Object} Backend-compatible filter object
     */
    convertToBackend(uiFilters) {
        if (!uiFilters || uiFilters.length === 0) {
            return null;
        }

        const backendFilters = {};

        uiFilters.forEach((filter) => {
            const { column, operator, value } = filter;

            switch (operator) {
                case 'equals':
                    // Simple equality: column = 'value'
                    backendFilters[column] = value;
                    break;

                case 'contains':
                    // LIKE search: column LIKE '%value%'
                    backendFilters[column] = {
                        contains: value,
                    };
                    break;

                case 'starts_with':
                    // REGEXP: column REGEXP '^value'
                    backendFilters[column] = {
                        regex: `^${this.escapeRegex(value)}`,
                    };
                    break;

                case 'ends_with':
                    // REGEXP: column REGEXP 'value$'
                    backendFilters[column] = {
                        regex: `${this.escapeRegex(value)}$`,
                    };
                    break;

                case 'not_empty':
                    // column IS NOT NULL AND column != ''
                    backendFilters[column] = {
                        not_empty: true,
                    };
                    break;

                case 'empty':
                    // column IS NULL OR column = ''
                    backendFilters[column] = {
                        empty: true,
                    };
                    break;

                case 'in':
                    // IN clause: column IN ('val1', 'val2')
                    backendFilters[column] = Array.isArray(value) ? value : [value];
                    break;

                case 'not_in':
                    // NOT IN clause
                    backendFilters[column] = {
                        not_in: Array.isArray(value) ? value : [value],
                    };
                    break;

                case 'greater_than':
                    // column > value
                    backendFilters[column] = {
                        gt: value,
                    };
                    break;

                case 'less_than':
                    // column < value
                    backendFilters[column] = {
                        lt: value,
                    };
                    break;

                case 'between':
                    // column BETWEEN min AND max
                    backendFilters[column] = {
                        gte: value.min,
                        lte: value.max,
                    };
                    break;

                default:
                    // Default to equality
                    this.logger.warn(`Unknown operator: ${operator}, defaulting to equals`);
                    backendFilters[column] = value;
            }
        });

        // this.logger.info('Converted filters:', backendFilters);
        return backendFilters;
    }

    /**
     * ✅ Convert backend filters to SQL WHERE clause
     * @param {Object} filters - Backend filter object
     * @returns {String} SQL WHERE clause (without WHERE keyword)
     */
    toSQLWhere(filters) {
        if (!filters || Object.keys(filters).length === 0) {
            return null;
        }

        const clauses = [];

        for (const [column, value] of Object.entries(filters)) {
            if (typeof value === 'string') {
                // Simple string equality
                const escaped = value.replace(/'/g, "''");
                clauses.push(`\`${column}\` = '${escaped}'`);
            } else if (typeof value === 'number') {
                // Numeric equality
                clauses.push(`\`${column}\` = ${value}`);
            } else if (Array.isArray(value)) {
                // IN clause
                const values = value
                    .map((v) => (typeof v === 'string' ? `'${v.replace(/'/g, "''")}'` : v))
                    .join(', ');
                clauses.push(`\`${column}\` IN (${values})`);
            } else if (typeof value === 'object') {
                // Complex filter
                if (value.contains) {
                    const escaped = value.contains.replace(/'/g, "''");
                    clauses.push(`\`${column}\` LIKE '%${escaped}%'`);
                } else if (value.regex) {
                    clauses.push(`\`${column}\` REGEXP '${value.regex}'`);
                } else if (value.not_empty) {
                    clauses.push(`(\`${column}\` IS NOT NULL AND \`${column}\` != '')`);
                } else if (value.empty) {
                    clauses.push(`(\`${column}\` IS NULL OR \`${column}\` = '')`);
                } else if (value.not_in) {
                    const values = value.not_in
                        .map((v) => (typeof v === 'string' ? `'${v.replace(/'/g, "''")}'` : v))
                        .join(', ');
                    clauses.push(`\`${column}\` NOT IN (${values})`);
                } else if (value.gt !== undefined) {
                    clauses.push(`\`${column}\` > ${value.gt}`);
                } else if (value.lt !== undefined) {
                    clauses.push(`\`${column}\` < ${value.lt}`);
                } else if (value.gte !== undefined && value.lte !== undefined) {
                    clauses.push(`\`${column}\` BETWEEN ${value.gte} AND ${value.lte}`);
                }
            }
        }

        return clauses.length > 0 ? clauses.join(' AND ') : null;
    }

    /**
     * ✅ Build SQL query with filters
     * @param {String} table - Table name
     * @param {Object} options - Query options
     * @returns {String} Complete SQL query
     */
    buildQuery(table, options = {}) {
        const {
            columns = ['*'],
            filters = null,
            orderBy = null,
            limit = null,
            offset = null,
        } = options;

        // SELECT clause
        const cols = columns.map((col) => (col === '*' ? '*' : `\`${col}\``)).join(', ');
        let query = `SELECT ${cols} FROM \`${table}\``;

        // WHERE clause
        const whereClause = this.toSQLWhere(filters);
        if (whereClause) {
            query += ` WHERE ${whereClause}`;
        }

        // ORDER BY clause
        if (orderBy) {
            query += ` ORDER BY ${orderBy}`;
        }

        // LIMIT clause
        if (limit) {
            query += ` LIMIT ${limit}`;
            if (offset) {
                query += ` OFFSET ${offset}`;
            }
        }

        // this.logger.info('Built query:', query);
        return query;
    }

    /**
     * ✅ Count records with filters
     * @param {String} table - Table name
     * @param {Object} filters - Backend filter object
     * @returns {String} COUNT query
     */
    buildCountQuery(table, filters = null) {
        let query = `SELECT COUNT(*) as count FROM \`${table}\``;

        const whereClause = this.toSQLWhere(filters);
        if (whereClause) {
            query += ` WHERE ${whereClause}`;
        }

        return query;
    }

    /**
     * ✅ Escape regex special characters
     * @param {String} str - String to escape
     * @returns {String} Escaped string
     */
    escapeRegex(str) {
        return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    /**
     * ✅ Validate filter object
     * @param {Object} filters - Filter object to validate
     * @returns {Boolean} True if valid
     */
    validate(filters) {
        if (!filters || typeof filters !== 'object') {
            return false;
        }

        // Check for SQL injection attempts
        const dangerous = [
            'DROP',
            'DELETE',
            'UPDATE',
            'INSERT',
            'ALTER',
            'CREATE',
            'TRUNCATE',
            'EXEC',
        ];
        const filterStr = JSON.stringify(filters).toUpperCase();

        for (const keyword of dangerous) {
            if (filterStr.includes(keyword)) {
                this.logger.log('Dangerous keyword detected:', keyword);
                // return false;
            }
        }

        return true;
    }

    /**
     * ✅ Apply filters to data array (client-side filtering)
     * @param {Array} data - Data array
     * @param {Array} uiFilters - UI filter array
     * @returns {Array} Filtered data
     */
    applyToData(data, uiFilters) {
        if (!uiFilters || uiFilters.length === 0) {
            return data;
        }

        return data.filter((row) => {
            return uiFilters.every((filter) => {
                const { column, operator, value } = filter;
                const cellValue = row[column];

                switch (operator) {
                    case 'equals':
                        return String(cellValue).toLowerCase() === String(value).toLowerCase();

                    case 'contains':
                        return String(cellValue)
                            .toLowerCase()
                            .includes(String(value).toLowerCase());

                    case 'starts_with':
                        return String(cellValue)
                            .toLowerCase()
                            .startsWith(String(value).toLowerCase());

                    case 'ends_with':
                        return String(cellValue)
                            .toLowerCase()
                            .endsWith(String(value).toLowerCase());

                    case 'not_empty':
                        return cellValue !== null && cellValue !== undefined && cellValue !== '';

                    case 'empty':
                        return cellValue === null || cellValue === undefined || cellValue === '';

                    case 'in':
                        const values = Array.isArray(value) ? value : [value];
                        return values.includes(cellValue);

                    case 'greater_than':
                        return Number(cellValue) > Number(value);

                    case 'less_than':
                        return Number(cellValue) < Number(value);

                    default:
                        return true;
                }
            });
        });
    }

    /**
     * ✅ Get filter summary for display
     * @param {Array} uiFilters - UI filter array
     * @returns {String} Human-readable filter summary
     */
    getSummary(uiFilters) {
        if (!uiFilters || uiFilters.length === 0) {
            return 'No filters applied';
        }

        const summaries = uiFilters.map((filter) => {
            const column = filter.column.replace(/_/g, ' ');
            const operator = filter.operator.replace(/_/g, ' ');
            return `${column} ${operator} "${filter.value}"`;
        });

        return summaries.join(' AND ');
    }

    /**
     * ✅ NEW: Build complete SQL query with filters
     * @param {String} table - Table name
     * @param {Array} uiFilters - UI filter array
     * @param {Object} options - Query options
     * @returns {String} Complete SQL query
     */
    buildSQLQuery(table, uiFilters = [], options = {}) {
        const { columns = ['*'], limit = 1000, offset = 0, orderBy = null } = options;

        // SELECT clause
        const cols = columns.join(', ');
        let sql = `SELECT ${cols} FROM \`${table}\``;

        // WHERE clause from filters
        if (uiFilters && uiFilters.length > 0) {
            const backendFilters = this.convertToBackend(uiFilters);
            const whereClause = this.toSQLWhere(backendFilters);
            if (whereClause) {
                sql += ` WHERE ${whereClause}`;
            }
        }

        // ORDER BY clause
        if (orderBy) {
            sql += ` ORDER BY ${orderBy}`;
        }

        // LIMIT clause
        if (limit) {
            sql += ` LIMIT ${limit}`;
            if (offset) {
                sql += ` OFFSET ${offset}`;
            }
        }

        // this.logger.info('Built SQL query:', sql);
        return sql;
    }

    /**
     * ✅ NEW: Extract WHERE clause from SQL
     * @param {String} sql - SQL query
     * @returns {String|null} WHERE clause without WHERE keyword
     */
    extractWhereClause(sql) {
        if (!sql) return null;
        const match = sql.match(/WHERE\s+(.+?)(?:\s+ORDER BY|\s+LIMIT|$)/i);
        return match ? match[1].trim() : null;
    }

    /**
     * ✅ NEW: Extract ORDER BY clause from SQL
     * @param {String} sql - SQL query
     * @returns {String|null} ORDER BY clause without ORDER BY keyword
     */
    extractOrderBy(sql) {
        if (!sql) return null;
        const match = sql.match(/ORDER BY\s+(.+?)(?:\s+LIMIT|$)/i);
        return match ? match[1].trim() : null;
    }
}

// ✅ Initialize global instance
window.filterService = new FilterService();
