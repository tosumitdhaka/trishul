
import json
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Response
from backend.services.metrics_service import get_metrics_service

router = APIRouter()


@router.get("/")
async def get_metrics(request: Request):
    """Get application metrics in human-readable format."""
    metrics_service = get_metrics_service()
    
    if not metrics_service:
        return {"error": "Metrics service not initialized"}
    
    all_metrics = metrics_service.get_all()
    resource_stats = metrics_service.get_resource_stats()
    
    # Format for readability
    formatted = {
        "parser": {
            "files_compiled": _sum_metric(all_metrics.get('app_parser_files_compiled', [])),
            "files_failed": _sum_metric(all_metrics.get('app_parser_files_failed', [])),
            "records_parsed": _sum_metric(all_metrics.get('app_parser_records_parsed', [])),
            "throughput_files_per_sec": _get_gauge(all_metrics.get('app_parser_throughput_files_per_sec', [])),
            "throughput_records_per_sec": _get_gauge(all_metrics.get('app_parser_throughput_records_per_sec', [])),
        },
        "jobs": {
            "total": _sum_metric(all_metrics.get('app_jobs_total', [])),
            "completed": _sum_metric(all_metrics.get('app_jobs_total', []), {'status': 'completed'}),
            "failed": _sum_metric(all_metrics.get('app_jobs_total', []), {'status': 'failed'}),
            "cancelled": _sum_metric(all_metrics.get('app_jobs_total', []), {'status': 'cancelled'}),
        },
        "cache": {
            "hits": _sum_metric(all_metrics.get('app_cache_operations', []), {'operation': 'hit'}),
            "misses": _sum_metric(all_metrics.get('app_cache_operations', []), {'operation': 'miss'}),
            "saves": _sum_metric(all_metrics.get('app_cache_operations', []), {'operation': 'save'}),
            "total_files": _get_gauge(all_metrics.get('app_cache_files_total', [])),
            "total_size_bytes": _get_gauge(all_metrics.get('app_cache_size_bytes', [])),
            "total_size_mb": round(_get_gauge(all_metrics.get('app_cache_size_bytes', [])) / (1024 * 1024), 2),
        },
        "protobuf": {
            "compile": {
                "total": _sum_metric(all_metrics.get('protobuf_compile_total', [])),
                "success": _sum_metric(all_metrics.get('protobuf_compile_total', []), {'status': 'success'}),
                "failed": _sum_metric(all_metrics.get('protobuf_compile_total', []), {'status': 'failed'}),
                "duration_seconds": _get_gauge(all_metrics.get('protobuf_compile_duration_seconds', [])),
            },
            "decode": {
                "total": _sum_metric(all_metrics.get('protobuf_decode_total', [])),
                "success": _sum_metric(all_metrics.get('protobuf_decode_total', []), {'status': 'success'}),
                "failed": _sum_metric(all_metrics.get('protobuf_decode_total', []), {'status': 'failed'}),
                "files_decoded": _sum_metric(all_metrics.get('protobuf_files_decoded', [])),
                "fields_decoded": _sum_metric(all_metrics.get('protobuf_fields_decoded_total', [])),
                "duration_seconds": _get_gauge(all_metrics.get('protobuf_decode_duration_seconds', [])),
            },
            "message_types": _get_gauge(all_metrics.get('protobuf_message_types_count', [])),
        },
        "snmp_walk": {
            "walk": {
                "total": _sum_metric(all_metrics.get('snmp_walk_total', [])),
                "success": _sum_metric(all_metrics.get('snmp_walk_total', []), {'status': 'success'}),
                "failed": _sum_metric(all_metrics.get('snmp_walk_total', []), {'status': 'failed'}),
                "timeout": _sum_metric(all_metrics.get('snmp_walk_total', []), {'status': 'timeout'}),
                "duration_seconds": _get_gauge(all_metrics.get('snmp_walk_duration_seconds', [])),
            },
            "oids": {
                "collected": _sum_metric(all_metrics.get('snmp_walk_oids_collected_total', [])),
                "resolution_percentage": _get_gauge(all_metrics.get('snmp_walk_resolution_percentage', [])),
            }
        },
        "snmp_traps": {
            "sender": {
                "total_sent": _sum_metric(all_metrics.get('snmp_traps_sent_total', [])),
                "success": _sum_metric(all_metrics.get('snmp_traps_sent_total', []), {'status': 'success'}),
                "failed": _sum_metric(all_metrics.get('snmp_traps_sent_total', []), {'status': 'failed'}),
                "timeout": _sum_metric(all_metrics.get('snmp_traps_sent_total', []), {'status': 'timeout'}),
                "last_send_duration_seconds": _get_gauge(all_metrics.get('snmp_trap_send_duration_seconds', [])),
                "total_send_duration_seconds": round(_sum_metric(all_metrics.get('snmp_trap_send_duration_total_seconds', [])), 2),
            },
            "receiver": {
                "total_received": _sum_metric(all_metrics.get('snmp_traps_received_total', [])),
                "last_receive_duration_seconds": _get_gauge(all_metrics.get('snmp_trap_receive_duration_seconds', [])),
                "total_receive_duration_seconds": round(_sum_metric(all_metrics.get('snmp_trap_receive_duration_total_seconds', [])), 2),
            }
        },
        
        "oid_resolver": {
            "cache": {
                "hits": _sum_metric(all_metrics.get('app_oid_cache_operations_total', []), {'operation': 'hit'}),
                "misses": _sum_metric(all_metrics.get('app_oid_cache_operations_total', []), {'operation': 'miss'}),
                "total_operations": _sum_metric(all_metrics.get('app_oid_cache_operations_total', [])),
                "hit_rate_percent": _calculate_hit_rate(all_metrics.get('app_oid_cache_operations_total', [])),
                "size": _get_gauge(all_metrics.get('app_oid_cache_size', [])),
            },
            "resolutions": {
                "total": _sum_metric(all_metrics.get('app_oid_resolutions_total', [])),
                "success": _sum_metric(all_metrics.get('app_oid_resolutions_total', []), {'status': 'success'}),
                "failed": _sum_metric(all_metrics.get('app_oid_resolutions_total', []), {'status': 'failed'}),
                "from_cache": _sum_metric(all_metrics.get('app_oid_resolutions_total', []), {'status': 'success', 'source': 'cache'}),
                "from_database": _sum_metric(all_metrics.get('app_oid_resolutions_total', []), {'status': 'success', 'source': 'database'}),
                "success_rate_percent": _calculate_success_rate(all_metrics.get('app_oid_resolutions_total', [])),
                "last_batch_duration_seconds": _get_gauge(all_metrics.get('app_oid_resolution_batch_duration_seconds', [])),
                "total_duration_seconds": round(_sum_metric(all_metrics.get('app_oid_resolution_duration_total_seconds', [])), 2),
            }
        },

        "database": {
            "queries": {
                "total": _sum_metric(all_metrics.get('app_db_queries_total', [])),
                "insert_success": _sum_metric(all_metrics.get('app_db_queries_total', []), {'operation': 'insert', 'status': 'success'}),
                "insert_failed": _sum_metric(all_metrics.get('app_db_queries_total', []), {'operation': 'insert', 'status': 'failed'}),
                "select_success": _sum_metric(all_metrics.get('app_db_queries_total', []), {'operation': 'select', 'status': 'success'}),
                "select_failed": _sum_metric(all_metrics.get('app_db_queries_total', []), {'operation': 'select', 'status': 'failed'}),
                "last_query_duration_seconds": _get_gauge(all_metrics.get('app_db_query_duration_seconds', [])),
                "total_query_duration_seconds": round(_sum_metric(all_metrics.get('app_db_query_duration_total_seconds', [])), 2),
            },
            "jobs_table": {
                "operations_total": _sum_metric(all_metrics.get('app_jobs_db_operations_total', [])),
                "create": _sum_metric(all_metrics.get('app_jobs_db_operations_total', []), {'operation': 'create'}),
                "update": _sum_metric(all_metrics.get('app_jobs_db_operations_total', []), {'operation': 'update'}),
                "delete": _sum_metric(all_metrics.get('app_jobs_db_operations_total', []), {'operation': 'delete'}),
                "select": _sum_metric(all_metrics.get('app_jobs_db_operations_total', []), {'operation': 'select'}),
            },
            "table_operations": {
                "total": _sum_metric(all_metrics.get('app_db_table_operations_total', [])),
                "create_success": _sum_metric(all_metrics.get('app_db_table_operations_total', []), {'operation': 'create', 'status': 'success'}),
                "delete_success": _sum_metric(all_metrics.get('app_db_table_operations_total', []), {'operation': 'delete', 'status': 'success'}),
            },
            "sync": {
                "operations_total": _sum_metric(all_metrics.get('app_db_sync_operations_total', [])),
                "success": _sum_metric(all_metrics.get('app_db_sync_operations_total', []), {'status': 'success'}),
                "failed": _sum_metric(all_metrics.get('app_db_sync_operations_total', []), {'status': 'failed'}),
                "rows_inserted": _sum_metric(all_metrics.get('app_db_sync_rows_total', []), {'operation': 'inserted'}),
                "rows_updated": _sum_metric(all_metrics.get('app_db_sync_rows_total', []), {'operation': 'updated'}),
                "rows_skipped": _sum_metric(all_metrics.get('app_db_sync_rows_total', []), {'operation': 'skipped'}),
                "last_sync_duration_seconds": _get_gauge(all_metrics.get('app_db_sync_duration_seconds', [])),
                "total_sync_duration_seconds": round(_sum_metric(all_metrics.get('app_db_sync_duration_total_seconds', [])), 2),
            }
        },

        "resources": {
            "memory": {
                "current_mb": resource_stats['current_memory_mb'],
                "max_mb": resource_stats['max_memory_mb'],
            },
            "cpu": {
                "current_percent": resource_stats['current_cpu_percent'],
                "max_percent": resource_stats['max_cpu_percent'],
            }
        },
        "system": {
            "timestamp": datetime.now().isoformat(),
        }
    }
    
    return formatted


@router.get("/prometheus")
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    metrics_service = get_metrics_service()
    
    if not metrics_service:
        return "# Metrics service not initialized\n"
    
    all_metrics = metrics_service.get_all()
    
    lines = []
    
    # Parser metrics
    lines.append("# HELP app_parser_files_compiled Total files compiled")
    lines.append("# TYPE app_parser_files_compiled counter")
    for m in all_metrics.get('app_parser_files_compiled', []):
        lines.append(f"app_parser_files_compiled {m['value']}")
    
    lines.append("# HELP app_parser_files_failed Total files failed")
    lines.append("# TYPE app_parser_files_failed counter")
    for m in all_metrics.get('app_parser_files_failed', []):
        lines.append(f"app_parser_files_failed {m['value']}")
    
    lines.append("# HELP app_parser_records_parsed Total records parsed")
    lines.append("# TYPE app_parser_records_parsed counter")
    for m in all_metrics.get('app_parser_records_parsed', []):
        lines.append(f"app_parser_records_parsed {m['value']}")
    
    lines.append("# HELP app_parser_throughput_files_per_sec Parser throughput in files per second")
    lines.append("# TYPE app_parser_throughput_files_per_sec gauge")
    for m in all_metrics.get('app_parser_throughput_files_per_sec', []):
        lines.append(f"app_parser_throughput_files_per_sec {m['value']}")
    
    lines.append("# HELP app_parser_throughput_records_per_sec Parser throughput in records per second")
    lines.append("# TYPE app_parser_throughput_records_per_sec gauge")
    for m in all_metrics.get('app_parser_throughput_records_per_sec', []):
        lines.append(f"app_parser_throughput_records_per_sec {m['value']}")
    
    # Job metrics
    lines.append("# HELP app_jobs_total Total jobs")
    lines.append("# TYPE app_jobs_total counter")
    for m in all_metrics.get('app_jobs_total', []):
        labels = ','.join(f'{k}="{v}"' for k, v in m['labels'].items())
        lines.append(f"app_jobs_total{{{labels}}} {m['value']}")
    
    # Cache metrics
    lines.append("# HELP app_cache_operations Cache operations")
    lines.append("# TYPE app_cache_operations counter")
    for m in all_metrics.get('app_cache_operations', []):
        labels = ','.join(f'{k}="{v}"' for k, v in m['labels'].items())
        lines.append(f"app_cache_operations{{{labels}}} {m['value']}")
    
    lines.append("# HELP app_cache_files_total Total cache files")
    lines.append("# TYPE app_cache_files_total gauge")
    for m in all_metrics.get('app_cache_files_total', []):
        lines.append(f"app_cache_files_total {m['value']}")
    
    lines.append("# HELP app_cache_size_bytes Cache size in bytes")
    lines.append("# TYPE app_cache_size_bytes gauge")
    for m in all_metrics.get('app_cache_size_bytes', []):
        lines.append(f"app_cache_size_bytes {m['value']}")

    # Protobuf metrics
    lines.append("# HELP protobuf_compile_total Total protobuf schema compilations")
    lines.append("# TYPE protobuf_compile_total counter")
    for m in all_metrics.get('protobuf_compile_total', []):
        labels = ','.join(f'{k}="{v}"' for k, v in m['labels'].items())
        lines.append(f"protobuf_compile_total{{{labels}}} {m['value']}")
    
    lines.append("# HELP protobuf_compile_duration_seconds Last compilation duration")
    lines.append("# TYPE protobuf_compile_duration_seconds gauge")
    for m in all_metrics.get('protobuf_compile_duration_seconds', []):
        lines.append(f"protobuf_compile_duration_seconds {m['value']}")
    
    lines.append("# HELP protobuf_message_types_count Number of message types in schema")
    lines.append("# TYPE protobuf_message_types_count gauge")
    for m in all_metrics.get('protobuf_message_types_count', []):
        lines.append(f"protobuf_message_types_count {m['value']}")
    
    lines.append("# HELP protobuf_decode_total Total protobuf decode operations")
    lines.append("# TYPE protobuf_decode_total counter")
    for m in all_metrics.get('protobuf_decode_total', []):
        labels = ','.join(f'{k}="{v}"' for k, v in m['labels'].items())
        lines.append(f"protobuf_decode_total{{{labels}}} {m['value']}")
    
    lines.append("# HELP protobuf_files_decoded Total protobuf files decoded")
    lines.append("# TYPE protobuf_files_decoded counter")
    for m in all_metrics.get('protobuf_files_decoded', []):
        lines.append(f"protobuf_files_decoded {m['value']}")
    
    lines.append("# HELP protobuf_fields_decoded_total Total protobuf fields decoded")
    lines.append("# TYPE protobuf_fields_decoded_total counter")
    for m in all_metrics.get('protobuf_fields_decoded_total', []):
        lines.append(f"protobuf_fields_decoded_total {m['value']}")
    
    lines.append("# HELP protobuf_decode_duration_seconds Last decode duration")
    lines.append("# TYPE protobuf_decode_duration_seconds gauge")
    for m in all_metrics.get('protobuf_decode_duration_seconds', []):
        lines.append(f"protobuf_decode_duration_seconds {m['value']}")

    # SNMP Walk metrics
    lines.append("# HELP snmp_walk_total Total SNMP walks")
    lines.append("# TYPE snmp_walk_total counter")
    for m in all_metrics.get('snmp_walk_total', []):
        labels = ','.join(f'{k}="{v}"' for k, v in m['labels'].items())
        lines.append(f"snmp_walk_total{{{labels}}} {m['value']}")
    
    lines.append("# HELP snmp_walk_duration_seconds Last walk duration")
    lines.append("# TYPE snmp_walk_duration_seconds gauge")
    for m in all_metrics.get('snmp_walk_duration_seconds', []):
        lines.append(f"snmp_walk_duration_seconds {m['value']}")
    
    lines.append("# HELP snmp_walk_oids_collected_total Total OIDs collected")
    lines.append("# TYPE snmp_walk_oids_collected_total counter")
    for m in all_metrics.get('snmp_walk_oids_collected_total', []):
        lines.append(f"snmp_walk_oids_collected_total {m['value']}")
    
    lines.append("# HELP snmp_walk_resolution_percentage OID resolution percentage")
    lines.append("# TYPE snmp_walk_resolution_percentage gauge")
    for m in all_metrics.get('snmp_walk_resolution_percentage', []):
        lines.append(f"snmp_walk_resolution_percentage {m['value']}")

    # Trap Sender
    lines.append("# HELP snmp_traps_sent_total Total SNMP traps sent")
    lines.append("# TYPE snmp_traps_sent_total counter")
    for m in all_metrics.get('snmp_traps_sent_total', []):
        labels = ','.join(f'{k}="{v}"' for k, v in m['labels'].items())
        lines.append(f"snmp_traps_sent_total{{{labels}}} {m['value']}")
    
    lines.append("# HELP snmp_trap_send_duration_seconds Last trap send duration")
    lines.append("# TYPE snmp_trap_send_duration_seconds gauge")
    for m in all_metrics.get('snmp_trap_send_duration_seconds', []):
        lines.append(f"snmp_trap_send_duration_seconds {m['value']}")
    
    lines.append("# HELP snmp_trap_send_duration_total_seconds Total trap send duration")
    lines.append("# TYPE snmp_trap_send_duration_total_seconds counter")
    for m in all_metrics.get('snmp_trap_send_duration_total_seconds', []):
        lines.append(f"snmp_trap_send_duration_total_seconds {m['value']}")
    
    # Trap Receiver
    lines.append("# HELP snmp_traps_received_total Total SNMP traps received")
    lines.append("# TYPE snmp_traps_received_total counter")
    for m in all_metrics.get('snmp_traps_received_total', []):
        lines.append(f"snmp_traps_received_total {m['value']}")
    
    lines.append("# HELP snmp_trap_receive_duration_seconds Last trap receive processing duration")
    lines.append("# TYPE snmp_trap_receive_duration_seconds gauge")
    for m in all_metrics.get('snmp_trap_receive_duration_seconds', []):
        lines.append(f"snmp_trap_receive_duration_seconds {m['value']}")
    
    lines.append("# HELP snmp_trap_receive_duration_total_seconds Total trap receive processing duration")
    lines.append("# TYPE snmp_trap_receive_duration_total_seconds counter")
    for m in all_metrics.get('snmp_trap_receive_duration_total_seconds', []):
        lines.append(f"snmp_trap_receive_duration_total_seconds {m['value']}")
    
    # OID Resolutions
    lines.append("# HELP app_oid_resolutions_total Total OID resolutions")
    lines.append("# TYPE app_oid_resolutions_total counter")
    for m in all_metrics.get('app_oid_resolutions_total', []):
        labels = ','.join(f'{k}="{v}"' for k, v in m['labels'].items())
        lines.append(f"app_oid_resolutions_total{{{labels}}} {m['value']}")
    
    lines.append("# HELP app_oid_resolution_batch_duration_seconds Last batch resolution duration")
    lines.append("# TYPE app_oid_resolution_batch_duration_seconds gauge")
    for m in all_metrics.get('app_oid_resolution_batch_duration_seconds', []):
        lines.append(f"app_oid_resolution_batch_duration_seconds {m['value']}")
    
    lines.append("# HELP app_oid_resolution_duration_total_seconds Total resolution duration")
    lines.append("# TYPE app_oid_resolution_duration_total_seconds counter")
    for m in all_metrics.get('app_oid_resolution_duration_total_seconds', []):
        lines.append(f"app_oid_resolution_duration_total_seconds {m['value']}")
    
    # OID Cache
    lines.append("# HELP app_oid_cache_operations_total Total OID cache operations")
    lines.append("# TYPE app_oid_cache_operations_total counter")
    for m in all_metrics.get('app_oid_cache_operations_total', []):
        labels = ','.join(f'{k}="{v}"' for k, v in m['labels'].items())
        lines.append(f"app_oid_cache_operations_total{{{labels}}} {m['value']}")
    
    lines.append("# HELP app_oid_cache_size Current OID cache size")
    lines.append("# TYPE app_oid_cache_size gauge")
    for m in all_metrics.get('app_oid_cache_size', []):
        lines.append(f"app_oid_cache_size {m['value']}")

    # DB Queries
    lines.append("# HELP app_db_queries_total Total database queries")
    lines.append("# TYPE app_db_queries_total counter")
    for m in all_metrics.get('app_db_queries_total', []):
        labels = ','.join(f'{k}="{v}"' for k, v in m['labels'].items())
        lines.append(f"app_db_queries_total{{{labels}}} {m['value']}")
    
    lines.append("# HELP app_db_query_duration_seconds Last query duration")
    lines.append("# TYPE app_db_query_duration_seconds gauge")
    for m in all_metrics.get('app_db_query_duration_seconds', []):
        labels = ','.join(f'{k}="{v}"' for k, v in m['labels'].items())
        lines.append(f"app_db_query_duration_seconds{{{labels}}} {m['value']}")

    lines.append("# HELP app_db_query_duration_total_seconds Total query duration")
    lines.append("# TYPE app_db_query_duration_total_seconds counter")
    for m in all_metrics.get('app_db_query_duration_total_seconds', []):
        labels = ','.join(f'{k}="{v}"' for k, v in m['labels'].items())
        lines.append(f"app_db_query_duration_total_seconds{{{labels}}} {m['value']}")
    
    # Jobs table operations
    lines.append("# HELP app_jobs_db_operations_total Total jobs table operations")
    lines.append("# TYPE app_jobs_db_operations_total counter")
    for m in all_metrics.get('app_jobs_db_operations_total', []):
        labels = ','.join(f'{k}="{v}"' for k, v in m['labels'].items())
        lines.append(f"app_jobs_db_operations_total{{{labels}}} {m['value']}")
    
    # Table operations
    lines.append("# HELP app_db_table_operations_total Total table operations")
    lines.append("# TYPE app_db_table_operations_total counter")
    for m in all_metrics.get('app_db_table_operations_total', []):
        labels = ','.join(f'{k}="{v}"' for k, v in m['labels'].items())
        lines.append(f"app_db_table_operations_total{{{labels}}} {m['value']}")
    
    # Sync operations
    lines.append("# HELP app_db_sync_operations_total Total table sync operations")
    lines.append("# TYPE app_db_sync_operations_total counter")
    for m in all_metrics.get('app_db_sync_operations_total', []):
        labels = ','.join(f'{k}="{v}"' for k, v in m['labels'].items())
        lines.append(f"app_db_sync_operations_total{{{labels}}} {m['value']}")
    
    lines.append("# HELP app_db_sync_rows_total Total rows synced")
    lines.append("# TYPE app_db_sync_rows_total counter")
    for m in all_metrics.get('app_db_sync_rows_total', []):
        labels = ','.join(f'{k}="{v}"' for k, v in m['labels'].items())
        lines.append(f"app_db_sync_rows_total{{{labels}}} {m['value']}")
    
    lines.append("# HELP app_db_sync_duration_seconds Last sync duration")
    lines.append("# TYPE app_db_sync_duration_seconds gauge")
    for m in all_metrics.get('app_db_sync_duration_seconds', []):
        labels = ','.join(f'{k}="{v}"' for k, v in m['labels'].items())
        lines.append(f"app_db_sync_duration_seconds{{{labels}}} {m['value']}")

    lines.append("# HELP app_db_sync_duration_total_seconds Total sync duration")
    lines.append("# TYPE app_db_sync_duration_total_seconds counter")
    for m in all_metrics.get('app_db_sync_duration_total_seconds', []):
        # ✅ FIX: Don't add empty labels
        if m['labels']:
            labels = ','.join(f'{k}="{v}"' for k, v in m['labels'].items())
            lines.append(f"app_db_sync_duration_total_seconds{{{labels}}} {m['value']}")
        else:
            lines.append(f"app_db_sync_duration_total_seconds {m['value']}")
    
    # Resource metrics
    lines.append("# HELP app_resource_memory_current_mb Current memory usage in MB")
    lines.append("# TYPE app_resource_memory_current_mb gauge")
    for m in all_metrics.get('app_resource_memory_current_mb', []):
        lines.append(f"app_resource_memory_current_mb {m['value']}")
    
    lines.append("# HELP app_resource_memory_max_mb Maximum memory usage in MB")
    lines.append("# TYPE app_resource_memory_max_mb gauge")
    for m in all_metrics.get('app_resource_memory_max_mb', []):
        lines.append(f"app_resource_memory_max_mb {m['value']}")
    
    lines.append("# HELP app_resource_cpu_current_percent Current CPU usage percentage")
    lines.append("# TYPE app_resource_cpu_current_percent gauge")
    for m in all_metrics.get('app_resource_cpu_current_percent', []):
        lines.append(f"app_resource_cpu_current_percent {m['value']}")
    
    lines.append("# HELP app_resource_cpu_max_percent Maximum CPU usage percentage")
    lines.append("# TYPE app_resource_cpu_max_percent gauge")
    for m in all_metrics.get('app_resource_cpu_max_percent', []):
        lines.append(f"app_resource_cpu_max_percent {m['value']}")
    
    return Response(
        content="\n".join(lines) + "\n",
        media_type="text/plain; version=0.0.4"
    )


@router.post("/reset-max-resources")
async def reset_max_resources():
    """Reset max CPU/Memory tracking (for debugging)."""
    metrics_service = get_metrics_service()
    
    if not metrics_service:
        return {"error": "Metrics service not initialized"}
    
    metrics_service.reset_max_resources()
    
    return {
        "success": True,
        "message": "Max resource tracking reset"
    }

@router.get("/history")
async def get_metrics_history(days: int = 7):
    """Get historical metrics for last N days."""
    metrics_service = get_metrics_service()
    
    if not metrics_service:
        return {"error": "Metrics service not initialized"}
    
    metrics_dir = metrics_service.metrics_file.parent
    files = sorted(metrics_dir.glob("metrics_*.json"))
    
    # Filter by days
    cutoff = datetime.now() - timedelta(days=days)
    recent_files = [f for f in files if f.stat().st_mtime >= cutoff.timestamp()]
    
    history = []
    for file in recent_files:
        try:
            with open(file, 'r') as f:
                data = json.load(f)
                history.append({
                    'date': file.stem.replace('metrics_', ''),
                    'updated_at': data.get('updated_at'),
                    'max_memory_mb': data.get('max_memory_mb'),
                    'max_cpu_percent': data.get('max_cpu_percent'),
                    'metrics_count': len(data.get('metrics', {}))
                })
        except Exception as e:
            continue
    
    return {
        "success": True,
        "days_requested": days,
        "files_found": len(history),
        "history": history
    }

@router.get("/export")
async def export_metrics(days: int = 7):
    """Export full metrics history as JSON."""
    metrics_service = get_metrics_service()
    
    if not metrics_service:
        return {"error": "Metrics service not initialized"}
    
    metrics_dir = metrics_service.metrics_file.parent
    files = sorted(metrics_dir.glob("metrics_*.json"))
    
    cutoff = datetime.now() - timedelta(days=days)
    recent_files = [f for f in files if f.stat().st_mtime >= cutoff.timestamp()]
    
    export_data = []
    for file in recent_files:
        try:
            with open(file, 'r') as f:
                data = json.load(f)
                export_data.append({
                    'date': file.stem.replace('metrics_', ''),
                    'data': data
                })
        except Exception as e:
            continue
    
    return {
        "success": True,
        "exported_days": len(export_data),
        "data": export_data
    }

@router.get("/prometheus/health")
async def prometheus_health(request: Request):
    """
    Check Prometheus availability.
    
    Returns information about whether Prometheus monitoring is available
    in the current deployment (CNF vs VNF).
    """
    config = request.app.state.config
    
    # Check if monitoring is enabled in config
    monitoring_enabled = getattr(config, 'monitoring_enabled', False)
    
    # Try to check Prometheus health
    prometheus_available = False
    prometheus_url = None
    error_message = None
    
    if monitoring_enabled:
        try:
            import requests
            prometheus_url = "/prometheus"
            
            # ✅ FIXED: Check Prometheus directly via service, not through nginx
            prometheus_service = os.getenv('PROMETHEUS_SERVICE', 'trishul-prometheus:9090')
            
            response = requests.get(
                f"http://{prometheus_service}/-/healthy",
                timeout=2
            )
            prometheus_available = response.status_code == 200
            
            if not prometheus_available:
                error_message = f"Prometheus returned status {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            error_message = "Cannot connect to Prometheus service"
        except requests.exceptions.Timeout:
            error_message = "Prometheus health check timed out"
        except Exception as e:
            error_message = f"Prometheus health check failed: {str(e)}"
    else:
        error_message = "Monitoring not enabled in configuration"
    
    return {
        "available": prometheus_available,
        "enabled": monitoring_enabled,
        "url": prometheus_url if prometheus_available else None,
        "deployment_type": "CNF" if monitoring_enabled else "VNF",
        "status": "healthy" if prometheus_available else "unavailable",
        "message": (
            "Prometheus is available and healthy" if prometheus_available
            else error_message or "Prometheus not available in this deployment"
        )
    }

def _calculate_hit_rate(metrics: list) -> float:
    """Calculate cache hit rate percentage."""
    hits = 0
    misses = 0
    
    for m in metrics:
        if m['labels'].get('operation') == 'hit':
            hits += m['value']
        elif m['labels'].get('operation') == 'miss':
            misses += m['value']
    
    total = hits + misses
    if total == 0:
        return 0.0
    
    return round((hits / total) * 100, 1)


def _calculate_success_rate(metrics: list) -> float:
    """Calculate resolution success rate percentage."""
    success = 0
    failed = 0
    
    for m in metrics:
        if m['labels'].get('status') == 'success':
            success += m['value']
        elif m['labels'].get('status') == 'failed':
            failed += m['value']
    
    total = success + failed
    if total == 0:
        return 0.0
    
    return round((success / total) * 100, 1)

def _sum_metric(metrics: list, label_filter: dict = None) -> int:
    """Sum metric values, optionally filtering by labels."""
    total = 0
    for m in metrics:
        if label_filter:
            if all(m['labels'].get(k) == v for k, v in label_filter.items()):
                total += m['value']
        else:
            total += m['value']
    return total


def _get_gauge(metrics: list) -> float:
    """Get gauge value (latest)."""
    if metrics:
        return metrics[0]['value']
    return 0

