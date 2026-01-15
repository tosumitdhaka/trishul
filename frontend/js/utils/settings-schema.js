/**
 * Settings Schema - Redesigned & Cleaned
 * Defines the structure, validation, and UI for application settings
 * 
 * Structure:
 * - System (info + logging)
 * - Parsing (parser + cache)
 * - Jobs (processing + cleanup)
 * - Files (export + upload)
 * - UI (data table preferences)
 */

const SETTINGS_SCHEMA = {
    // ============================================
    // 1. SYSTEM
    // ============================================
    system: {
        label: 'System',
        icon: '📊',
        description: 'System information and logging',
        sections: {
            info: {
                label: 'System Information',
                description: 'Application metadata (read-only)',
                fields: {
                    'project.name': {
                        label: 'Application Name',
                        type: 'text',
                        default: 'Trishul',
                        readonly: true,
                        description: 'Application name'
                    },
                    'project.version': {
                        label: 'Version',
                        type: 'text',
                        default: '1.3.0',
                        readonly: true,
                        description: 'Application version'
                    },
                    'database.type': {
                        label: 'Database Type',
                        type: 'text',
                        default: 'MySQL',
                        readonly: true,
                        description: 'Database type',
                        computed: true // Computed from database config
                    },
                    'web.api_v1_prefix': {
                        label: 'API Prefix',
                        type: 'text',
                        default: '/api/v1',
                        readonly: true,
                        description: 'API version prefix'
                    }
                }
            },
            logging: {
                label: 'Logging',
                description: 'Application logging configuration',
                fields: {
                    'logging.level': {
                        label: 'Log Level',
                        type: 'select',
                        options: ['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        default: 'WARNING',
                        required: true,
                        description: 'Minimum log level to record',
                        help: 'DEBUG: All logs | INFO: General info | WARNING: Warnings only | ERROR: Errors only'
                    },
                    'logging.console': {
                        label: 'Console Logging',
                        type: 'boolean',
                        default: true,
                        description: 'Enable console output'
                    }
                }
            }
        }
    },

    // ============================================
    // 2. PARSING
    // ============================================
    parsing: {
        label: 'Parsing',
        icon: '📝',
        description: 'MIB parser and cache settings',
        sections: {
            parser: {
                label: 'Parser Settings',
                description: 'MIB parsing behavior',
                fields: {
                    'parser.force_compile': {
                        label: 'Force Recompile',
                        type: 'boolean',
                        default: false,
                        description: 'Always recompile MIBs (ignore cache)',
                        help: 'Enable this to force recompilation of all MIB files, even if they are already compiled'
                    },
                    'parser.deduplication_enabled': {
                        label: 'Enable Deduplication',
                        type: 'boolean',
                        default: false,
                        description: 'Remove duplicate records after parsing',
                        help: 'Automatically remove duplicate MIB objects based on the selected strategy'
                    },
                    'parser.deduplication_strategy': {
                        label: 'Deduplication Strategy',
                        type: 'select',
                        options: ['smart', 'strict', 'keep_first', 'keep_last'],
                        default: 'smart',
                        required: true,
                        description: 'Strategy for removing duplicates',
                        help: 'smart: Intelligent deduplication | strict: Exact match only | keep_first/last: Keep first or last occurrence',
                        showIf: { field: 'parser.deduplication_enabled', value: true }
                    },
                    'parser.show_parse_summary': {
                        label: 'Show Parse Summary',
                        type: 'boolean',
                        default: false,
                        description: 'Display detailed parsing summary',
                        help: 'Show detailed statistics after parsing (useful for debugging)'
                    }
                }
            },
            cache: {
                label: 'Cache Settings',
                description: 'Parser cache configuration',
                fields: {
                    'cache.enabled': {
                        label: 'Enable Cache',
                        type: 'boolean',
                        default: true,
                        description: 'Cache parsed MIB data for faster reloads',
                        help: 'Caching significantly improves performance for repeated parsing of the same files'
                    },
                    'cache.ttl_hours': {
                        label: 'Cache TTL (hours)',
                        type: 'number',
                        default: 720,
                        required: true,
                        description: 'Cache time-to-live (720 hours = 30 days)',
                        help: 'Cached data older than this will be automatically removed',
                        showIf: { field: 'cache.enabled', value: true },
                        validation: {
                            min: 1,
                            max: 8760,
                            message: 'TTL must be between 1 and 8760 hours (1 year)'
                        }
                    },
                    'cache.max_size_mb': {
                        label: 'Max Cache Size (MB)',
                        type: 'number',
                        default: 500,
                        required: true,
                        description: 'Maximum cache size in megabytes',
                        help: 'Cache will be cleaned up when it exceeds this size',
                        showIf: { field: 'cache.enabled', value: true },
                        validation: {
                            min: 10,
                            max: 10000,
                            message: 'Cache size must be between 10 MB and 10 GB'
                        }
                    },
                    'cache.cleanup_on_startup': {
                        label: 'Cleanup on Startup',
                        type: 'boolean',
                        default: false,
                        description: 'Clear all cache on application startup',
                        help: 'Enable this to start with a fresh cache every time the application starts',
                        showIf: { field: 'cache.enabled', value: true }
                    }
                }
            }
        }
    },

    // ============================================
    // 3. JOBS
    // ============================================
    jobs: {
        label: 'Jobs',
        icon: '⚙️',
        description: 'Job processing and cleanup settings',
        sections: {
            processing: {
                label: 'Job Processing',
                description: 'Job execution settings',
                fields: {
                    'jobs.concurrency': {
                        label: 'Max Concurrent Jobs',
                        type: 'number',
                        default: 2,
                        required: true,
                        description: 'Maximum number of jobs running simultaneously',
                        help: 'Higher values allow more parallel processing but use more resources',
                        validation: {
                            min: 1,
                            max: 10,
                            message: 'Concurrency must be between 1 and 10'
                        }
                    },
                    'jobs.auto_refresh_interval': {
                        label: 'Auto Refresh Interval (seconds)',
                        type: 'number',
                        default: 15,
                        required: true,
                        description: 'How often to refresh job status in UI',
                        help: 'Lower values provide more real-time updates but increase server load',
                        validation: {
                            min: 5,
                            max: 300,
                            message: 'Interval must be between 5 and 300 seconds'
                        }
                    }
                }
            },
            cleanup: {
                label: 'Cleanup Service',
                description: 'Automatic job cleanup configuration',
                fields: {
                    'cleanup.enabled': {
                        label: 'Enable Cleanup',
                        type: 'boolean',
                        default: true,
                        description: 'Automatically clean up old job data',
                        help: 'Recommended to keep enabled to prevent database bloat'
                    },
                    'cleanup.retention_days': {
                        label: 'Retention Days',
                        type: 'number',
                        default: 30,
                        required: true,
                        description: 'Delete job data older than this many days',
                        help: 'Jobs older than this will be permanently deleted',
                        showIf: { field: 'cleanup.enabled', value: true },
                        validation: {
                            min: 1,
                            max: 365,
                            message: 'Retention must be between 1 and 365 days'
                        }
                    },
                    'cleanup.schedule_hour': {
                        label: 'Schedule Hour (0-23)',
                        type: 'number',
                        default: 2,
                        required: true,
                        description: 'Hour of day to run cleanup (24-hour format)',
                        help: 'Cleanup runs daily at this hour (server time)',
                        showIf: { field: 'cleanup.enabled', value: true },
                        validation: {
                            min: 0,
                            max: 23,
                            message: 'Hour must be between 0 and 23'
                        }
                    },
                    'cleanup.schedule_minute': {
                        label: 'Schedule Minute (0-59)',
                        type: 'number',
                        default: 0,
                        required: true,
                        description: 'Minute of hour to run cleanup',
                        help: 'Cleanup runs at this minute of the scheduled hour',
                        showIf: { field: 'cleanup.enabled', value: true },
                        validation: {
                            min: 0,
                            max: 59,
                            message: 'Minute must be between 0 and 59'
                        }
                    },
                    'cleanup.delete_data': {
                        label: 'Delete Data',
                        type: 'boolean',
                        default: true,
                        description: 'Delete job data tables when cleaning up',
                        help: 'If disabled, only job metadata is deleted, not the parsed data',
                        showIf: { field: 'cleanup.enabled', value: true }
                    },
                    'cleanup.keep_statuses': {
                        label: 'Keep Job Statuses',
                        type: 'array',
                        default: [],
                        required: false,
                        description: 'Job statuses to keep (never delete)',
                        help: 'Jobs with these statuses will not be deleted. Leave empty to delete all old jobs.',
                        placeholder: 'completed',
                        showIf: { field: 'cleanup.enabled', value: true },
                        arrayType: 'text'
                    }
                }
            }
        }
    },

    // ============================================
    // 4. FILES
    // ============================================
    files: {
        label: 'Files',
        icon: '💾',
        description: 'Export and upload settings',
        sections: {
            export: {
                label: 'Export Settings',
                description: 'Data export configuration',
                fields: {
                    'export.chunk_size': {
                        label: 'Chunk Size',
                        type: 'number',
                        default: 10000,
                        required: true,
                        description: 'Number of records per chunk for large exports',
                        help: 'Larger chunks are faster but use more memory',
                        validation: {
                            min: 1000,
                            max: 100000,
                            message: 'Chunk size must be between 1,000 and 100,000'
                        }
                    },
                    'export.include_timestamp': {
                        label: 'Include Timestamp',
                        type: 'boolean',
                        default: true,
                        description: 'Add timestamp to exported filenames',
                        help: 'Helps identify when files were exported'
                    },
                    'export.timestamp_format': {
                        label: 'Timestamp Format',
                        type: 'text',
                        default: '%Y%m%d_%H%M%S',
                        required: true,
                        description: 'Timestamp format (Python strftime)',
                        help: 'Format: %Y=year, %m=month, %d=day, %H=hour, %M=minute, %S=second',
                        showIf: { field: 'export.include_timestamp', value: true },
                        placeholder: '%Y%m%d_%H%M%S'
                    },
                    'export.compression': {
                        label: 'Compression Format',
                        type: 'select',
                        options: ['null', 'gzip', 'zip', 'bz2', 'xz'],
                        default: 'zip',
                        required: true,
                        description: 'Default compression format',
                        help: 'null = no compression | zip = best compatibility | gzip/bz2/xz = better compression'
                    }
                }
            },
            upload: {
                label: 'Upload Settings',
                description: 'File upload configuration',
                fields: {
                    'upload.max_size_mb': {
                        label: 'Max File Size (MB)',
                        type: 'number',
                        default: 100,
                        required: true,
                        description: 'Maximum individual file size',
                        help: 'Files larger than this will be rejected',
                        validation: {
                            min: 1,
                            max: 1000,
                            message: 'Max size must be between 1 MB and 1 GB'
                        }
                    },
                    'upload.max_archive_size_mb': {
                        label: 'Max Archive Size (MB)',
                        type: 'number',
                        default: 500,
                        required: true,
                        description: 'Maximum archive file size (zip, tar, etc.)',
                        help: 'Archive files larger than this will be rejected',
                        validation: {
                            min: 1,
                            max: 5000,
                            message: 'Max archive size must be between 1 MB and 5 GB'
                        }
                    },
                    'upload.max_archive_entries': {
                        label: 'Max Archive Entries',
                        type: 'number',
                        default: 10000,
                        required: true,
                        description: 'Maximum number of files in an archive',
                        help: 'Archives with more files than this will be rejected',
                        validation: {
                            min: 1,
                            max: 100000,
                            message: 'Max entries must be between 1 and 100,000'
                        }
                    },
                    'upload.supported_extensions': {
                        label: 'Supported Extensions',
                        type: 'array',
                        default: ['.mib', '.txt', '.my', ''],
                        required: true,
                        description: 'Allowed file extensions',
                        help: 'Only files with these extensions can be uploaded. Empty string allows files without extension.',
                        placeholder: '.mib',
                        arrayType: 'text'
                    },
                    'upload.session_timeout_hours': {
                        label: 'Session Timeout (hours)',
                        type: 'number',
                        default: 24,
                        required: true,
                        description: 'Upload session timeout',
                        help: 'Uploaded files are deleted after this time if not processed',
                        validation: {
                            min: 1,
                            max: 168,
                            message: 'Timeout must be between 1 and 168 hours (1 week)'
                        }
                    }
                }
            }
        }
    },

    // ============================================
    // 5. UI
    // ============================================
    ui: {
        label: 'UI',
        icon: '🎨',
        description: 'User interface preferences',
        sections: {
            data_table: {
                label: 'Data Table',
                description: 'Data table display settings',
                fields: {
                    'ui.data_table.max_height_px': {
                        label: 'Max Height (px)',
                        type: 'number',
                        default: 800,
                        required: true,
                        description: 'Maximum table height in pixels',
                        help: 'Tables taller than this will scroll',
                        validation: {
                            min: 300,
                            max: 2000,
                            message: 'Height must be between 300 and 2000 pixels'
                        }
                    },
                    'ui.data_table.default_page_size': {
                        label: 'Default Page Size',
                        type: 'select',
                        options: [25, 50, 100, 500, 1000],
                        default: 50,
                        required: true,
                        description: 'Default rows per page',
                        help: 'Number of rows to display per page by default'
                    },
                    'ui.data_table.page_size_options': {
                        label: 'Page Size Options',
                        type: 'array',
                        default: [25, 50, 100, 500, 1000],
                        required: true,
                        description: 'Available page size options',
                        help: 'Users can choose from these page sizes',
                        arrayType: 'number'
                    },
                    'ui.data_table.db_fetch_limit_default': {
                        label: 'DB Fetch Limit',
                        type: 'select',
                        options: [500, 1000, 2000, 5000, 10000],
                        default: 1000,
                        required: true,
                        description: 'Default database fetch limit',
                        help: 'Maximum number of records to fetch from database at once'
                    },
                    'ui.data_table.db_fetch_limit_options': {
                        label: 'DB Fetch Limit Options',
                        type: 'array',
                        default: [500, 1000, 2000, 5000, 10000],
                        required: true,
                        description: 'Available fetch limit options',
                        help: 'Users can choose from these fetch limits',
                        arrayType: 'number'
                    },
                    'ui.data_table.priority_columns': {
                        label: 'Priority Columns',
                        type: 'array',
                        default: [
                            'notification_name',
                            'notification_oid',
                            'object_name',
                            'object_oid',
                            'node_type',
                            'module_name',
                            'object_status',
                            'object_description'
                        ],
                        required: true,
                        description: 'Columns shown by default',
                        help: 'These columns are displayed by default when viewing data',
                        placeholder: 'column_name',
                        arrayType: 'text'
                    },
                    'ui.data_table.node_type_options': {
                        label: 'Node Type Filters',
                        type: 'array',
                        default: [
                            'NotificationType',
                            'ObjectType',
                            'TypeDefinition',
                            'ModuleIdentity',
                            'MibTable',
                            'MibTableRow',
                            'MibTableColumn',
                            'MibScalar',
                            'MibIdentifier'
                        ],
                        required: true,
                        description: 'Available node type filters',
                        help: 'Users can filter data by these node types',
                        placeholder: 'NodeType',
                        arrayType: 'text'
                    }
                }
            }
        }
    }
};

// Helper function to get nested value from config
function getNestedValue(obj, path) {
    return path.split('.').reduce((current, key) => current?.[key], obj);
}

// Helper function to set nested value in config
function setNestedValue(obj, path, value) {
    const keys = path.split('.');
    const lastKey = keys.pop();
    const target = keys.reduce((current, key) => {
        if (!current[key]) current[key] = {};
        return current[key];
    }, obj);
    target[lastKey] = value;
}

// ============================================
// EXPOSE TO GLOBAL SCOPE
// ============================================
window.SETTINGS_SCHEMA = SETTINGS_SCHEMA;
window.getNestedValue = getNestedValue;
window.setNestedValue = setNestedValue;

// Also expose as helpers object
window.settingsSchemaHelpers = {
    getNestedValue,
    setNestedValue
};

// console.log('✅ Settings schema loaded:', Object.keys(SETTINGS_SCHEMA));