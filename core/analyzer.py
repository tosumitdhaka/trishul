#!/usr/bin/env python3
"""
Analyzer Service - Data analysis and reporting
Provides comprehensive analysis of MIB data
"""

import re
from datetime import datetime
from typing import Any, Dict

import pandas as pd

from utils.logger import get_logger


class AnalyzerService:
    """Provides data analysis and reporting for MIB data."""

    def __init__(self):
        """Initialize analyzer service."""
        self.logger = get_logger(self.__class__.__name__)

    def analyze_coverage(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze data coverage and completeness - FIXED for notification counting.

        Args:
            df: DataFrame to analyze

        Returns:
            Coverage analysis results
        """
        if df.empty:
            return {"error": "Empty DataFrame"}

        coverage = {
            "total_records": len(df),
            "field_coverage": {},
            "notification_coverage": {},
            "module_coverage": {},
            "tc_coverage": {},
        }

        # Analyze field coverage
        for col in df.columns:
            non_null = df[col].notna().sum()
            coverage["field_coverage"][col] = {
                "filled": non_null,
                "empty": len(df) - non_null,
                "percentage": round((non_null / len(df)) * 100, 2),
            }

        # Analyze notification coverage (FIXED)
        if "node_type" in df.columns:
            # Only count records with node_type == 'NotificationType' as notification objects
            notif_df = df[df["node_type"] == "NotificationType"]

            if len(notif_df) > 0 and "notification_name" in df.columns:
                # Count unique notifications
                unique_notifications = notif_df["notification_name"].dropna().unique()

                coverage["notification_coverage"] = {
                    "total_notifications": len(unique_notifications),
                    "notification_list": list(unique_notifications),
                    "total_notification_objects": len(notif_df),
                    "avg_objects_per_notification": (
                        round(len(notif_df) / len(unique_notifications), 2)
                        if len(unique_notifications) > 0
                        else 0
                    ),
                }

                # Count objects per notification
                objects_per_notif = {}
                for notif in unique_notifications:
                    count = len(notif_df[notif_df["notification_name"] == notif])
                    objects_per_notif[notif] = count

                coverage["notification_coverage"]["objects_per_notification"] = objects_per_notif

        # Analyze module coverage
        if "module_name" in df.columns:
            module_counts = df["module_name"].value_counts()
            coverage["module_coverage"] = {
                "total_modules": len(module_counts),
                "module_list": list(module_counts.index),
                "records_per_module": module_counts.to_dict(),
                "avg_records_per_module": (
                    round(len(df) / len(module_counts), 2) if len(module_counts) > 0 else 0
                ),
                "max_records_module": module_counts.index[0] if len(module_counts) > 0 else None,
                "min_records_module": module_counts.index[-1] if len(module_counts) > 0 else None,
            }

        # Analyze TC coverage
        if "tc_name" in df.columns:
            tc_df = df[df["tc_name"].notna()]
            if len(tc_df) > 0:
                tc_counts = tc_df["tc_name"].value_counts()

                coverage["tc_coverage"] = {
                    "total_tcs_used": len(tc_counts),
                    "tc_list": list(tc_counts.index),
                    "records_with_tc": len(tc_df),
                    "percentage_with_tc": round((len(tc_df) / len(df)) * 100, 2),
                    "top_tcs": tc_counts.head(10).to_dict(),
                }

                # Check TC resolution
                if "tc_base_type" in df.columns:
                    resolved = tc_df["tc_base_type"].notna().sum()
                    coverage["tc_coverage"]["resolved_tcs"] = resolved
                    coverage["tc_coverage"]["resolution_rate"] = round(
                        (resolved / len(tc_df)) * 100, 2
                    )

        return coverage

    def analyze_quality(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze data quality - FULLY FIXED"""
        if df.empty:
            return {"error": "Empty DataFrame"}

        quality = {
            "total_records": len(df),
            "issues": [],
            "warnings": [],
            "quality_score": 100.0,
            "field_quality": {},
            "oid_quality": {},
            "description_quality": {},
        }

        penalties = 0

        # Check for missing critical fields
        critical_fields = ["object_name", "object_oid", "node_type"]
        for field in critical_fields:
            if field in df.columns:
                missing = df[field].isna().sum()

                if field == "object_oid" and "node_type" in df.columns:
                    non_notif_missing = (
                        df[df["node_type"] != "NotificationType"][field].isna().sum()
                        if len(df[df["node_type"] != "NotificationType"]) > 0
                        else 0
                    )
                    if non_notif_missing > 0:
                        quality["issues"].append(
                            f"{non_notif_missing} non-notification records missing {field}"
                        )
                        penalties += (non_notif_missing / len(df)) * 10
                elif missing > 0:
                    quality["issues"].append(f"{missing} records missing {field}")
                    penalties += (missing / len(df)) * 20

                quality["field_quality"][field] = {
                    "missing": missing,
                    "percentage": round((missing / len(df)) * 100, 2),
                }

        # Check OID quality
        if "object_oid" in df.columns:
            if "node_type" in df.columns:
                non_notif_df = df[df["node_type"] != "NotificationType"]
                notif_df = df[df["node_type"] == "NotificationType"]

                if len(non_notif_df) > 0:
                    oid_issues = self._analyze_oid_quality(non_notif_df["object_oid"])
                    quality["oid_quality"]["non_notification"] = oid_issues

                    if oid_issues["invalid_format"] > 0:
                        quality["issues"].append(
                            f"{oid_issues['invalid_format']} invalid OID formats in non-notification objects"
                        )
                        penalties += (oid_issues["invalid_format"] / len(df)) * 10

                if len(notif_df) > 0:
                    notif_oid_issues = self._analyze_oid_quality(notif_df["object_oid"])
                    quality["oid_quality"]["notification"] = notif_oid_issues
            else:
                oid_issues = self._analyze_oid_quality(df["object_oid"])
                quality["oid_quality"] = oid_issues

                if oid_issues["invalid_format"] > 0:
                    quality["issues"].append(f"{oid_issues['invalid_format']} invalid OID formats")
                    penalties += (oid_issues["invalid_format"] / len(df)) * 10

        # Check description quality
        desc_fields = ["object_description", "notification_description"]
        for field in desc_fields:
            if field in df.columns:
                desc_quality = self._analyze_description_quality(df[field])
                quality["description_quality"][field] = desc_quality

                if desc_quality["missing"] > len(df) * 0.5:
                    quality["warnings"].append(
                        f"More than 50% missing {field} ({desc_quality['missing_percentage']:.1f}%)"
                    )
                    penalties += 5

                if field == "notification_description":
                    pass  # Don't penalize for short notification descriptions
                elif desc_quality["too_short"] > len(df) * 0.3:
                    quality["warnings"].append(
                        f"Many short {field} (< 10 chars): {desc_quality['too_short']}"
                    )
                    penalties += 3

        # Calculate quality score
        quality["quality_score"] = max(0, 100 - penalties)

        # Add quality grade
        if quality["quality_score"] >= 90:
            quality["grade"] = "A"
        elif quality["quality_score"] >= 80:
            quality["grade"] = "B"
        elif quality["quality_score"] >= 70:
            quality["grade"] = "C"
        elif quality["quality_score"] >= 60:
            quality["grade"] = "D"
        else:
            quality["grade"] = "F"

        # FIXED: Add correct data structure info
        if "node_type" in df.columns:
            notif_type_df = df[df["node_type"] == "NotificationType"]
            if len(notif_type_df) > 0 and "notification_name" in df.columns:
                unique_notifs = notif_type_df["notification_name"].dropna().unique()
                quality["data_structure"] = {
                    "type": "Notification-enriched MIB data",
                    "notifications": len(unique_notifs),
                    "notification_objects": len(notif_type_df),
                    "avg_objects_per_notification": (
                        round(len(notif_type_df) / len(unique_notifs), 2)
                        if len(unique_notifs) > 0
                        else 0
                    ),
                }

        return quality

    def analyze_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze statistical information - FULLY FIXED"""
        if df.empty:
            return {"error": "Empty DataFrame"}

        stats = {
            "total_records": len(df),
            "basic_stats": {},
            "node_type_distribution": {},
            "module_statistics": {},
            "notification_statistics": {},
            "tc_statistics": {},
            "temporal_statistics": {},
        }

        # Basic statistics
        stats["basic_stats"] = {
            "total_records": len(df),
            "total_columns": len(df.columns),
            "memory_usage_mb": round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2),
        }

        # Node type distribution
        if "node_type" in df.columns:
            node_counts = df["node_type"].value_counts()
            stats["node_type_distribution"] = {
                "counts": node_counts.to_dict(),
                "percentages": (node_counts / len(df) * 100).round(2).to_dict(),
            }

        # Module statistics
        if "module_name" in df.columns:
            module_counts = df["module_name"].value_counts()
            stats["module_statistics"] = {"total_modules": len(module_counts), "module_details": {}}

            for module in module_counts.index:
                module_df = df[df["module_name"] == module]

                # FIXED: Count actual notifications correctly
                if "node_type" in df.columns:
                    notif_count = len(module_df[module_df["node_type"] == "NotificationType"])
                else:
                    notif_count = 0

                stats["module_statistics"]["module_details"][module] = {
                    "total_objects": len(module_df),
                    "notification_objects": notif_count,
                }

            stats["module_statistics"]["largest_module"] = module_counts.index[0]
            stats["module_statistics"]["smallest_module"] = module_counts.index[-1]

        # FIXED: Notification statistics
        if "node_type" in df.columns and "notification_name" in df.columns:
            notif_df = df[df["node_type"] == "NotificationType"]

            if len(notif_df) > 0:
                unique_notifs = notif_df["notification_name"].dropna().unique()

                # Count objects per notification
                obj_counts = {}
                for notif in unique_notifs:
                    count = len(notif_df[notif_df["notification_name"] == notif])
                    obj_counts[notif] = count

                stats["notification_statistics"] = {
                    "total_notifications": len(unique_notifs),
                    "total_notification_objects": len(notif_df),
                    "avg_objects_per_notification": (
                        round(len(notif_df) / len(unique_notifs), 2)
                        if len(unique_notifs) > 0
                        else 0
                    ),
                    "objects_per_notification": obj_counts,
                }

                if obj_counts:
                    max_notif = max(obj_counts, key=obj_counts.get)
                    min_notif = min(obj_counts, key=obj_counts.get)
                    stats["notification_statistics"][
                        "max_objects_notification"
                    ] = f"{max_notif} ({obj_counts[max_notif]} objects)"
                    stats["notification_statistics"][
                        "min_objects_notification"
                    ] = f"{min_notif} ({obj_counts[min_notif]} objects)"

        # TC statistics
        if "tc_name" in df.columns and "tc_base_type" in df.columns:
            tc_df = df[df["tc_name"].notna()]
            if len(tc_df) > 0:
                base_type_counts = tc_df["tc_base_type"].value_counts()
                stats["tc_statistics"] = {
                    "total_with_tc": len(tc_df),
                    "percentage_with_tc": round((len(tc_df) / len(df)) * 100, 2),
                    "base_type_distribution": base_type_counts.to_dict(),
                    "most_common_base_type": (
                        base_type_counts.index[0] if len(base_type_counts) > 0 else None
                    ),
                }

        # Temporal statistics
        if "processed_at" in df.columns:
            try:
                df["processed_at_dt"] = pd.to_datetime(df["processed_at"])
                stats["temporal_statistics"] = {
                    "earliest_processing": str(df["processed_at_dt"].min()),
                    "latest_processing": str(df["processed_at_dt"].max()),
                    "processing_span_days": (
                        df["processed_at_dt"].max() - df["processed_at_dt"].min()
                    ).days,
                }
            except:
                pass

        return stats

    def analyze_duplicates(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze duplicate data - FULLY FIXED"""
        if df.empty:
            return {"error": "Empty DataFrame"}

        duplicates = {"total_records": len(df), "duplicate_analysis": {}, "recommendations": []}

        # Check for exact duplicates
        exact_dupes = df.duplicated().sum()
        duplicates["duplicate_analysis"]["exact_duplicates"] = {
            "count": exact_dupes,
            "percentage": round((exact_dupes / len(df)) * 100, 2),
        }

        if exact_dupes > 0:
            duplicates["recommendations"].append(f"Remove {exact_dupes} exact duplicate rows")

        # Check for duplicate OIDs (excluding notification objects)
        if "object_oid" in df.columns and "node_type" in df.columns:
            non_notif_df = df[df["node_type"] != "NotificationType"].copy()

            if len(non_notif_df) > 0:
                oid_dupes = non_notif_df["object_oid"].duplicated().sum()
                duplicates["duplicate_analysis"]["duplicate_oids"] = {
                    "count": oid_dupes,
                    "percentage": round((oid_dupes / len(non_notif_df)) * 100, 2),
                }

                if oid_dupes > 0:
                    dup_oids = non_notif_df[non_notif_df["object_oid"].duplicated(keep=False)][
                        "object_oid"
                    ].value_counts()
                    duplicates["duplicate_analysis"]["most_duplicated_oids"] = dup_oids.head(
                        10
                    ).to_dict()
                    duplicates["recommendations"].append(
                        f"Investigate {oid_dupes} duplicate OIDs in non-notification objects"
                    )

        # Check for duplicate names (excluding notification objects)
        if "object_name" in df.columns and "node_type" in df.columns:
            non_notif_df = df[df["node_type"] != "NotificationType"].copy()

            if len(non_notif_df) > 0:
                name_dupes = non_notif_df["object_name"].duplicated().sum()
                duplicates["duplicate_analysis"]["duplicate_names"] = {
                    "count": name_dupes,
                    "percentage": round((name_dupes / len(non_notif_df)) * 100, 2),
                }

                if name_dupes > 10:
                    duplicates["recommendations"].append(
                        "High number of duplicate object names - verify if intentional"
                    )

        # FIXED: Notification object structure analysis
        if "node_type" in df.columns and "notification_name" in df.columns:
            notif_df = df[df["node_type"] == "NotificationType"]

            if len(notif_df) > 0:
                unique_notifs = notif_df["notification_name"].dropna().unique()
                duplicates["duplicate_analysis"]["notification_object_structure"] = {
                    "total_notification_objects": len(notif_df),
                    "unique_notifications": len(unique_notifs),
                    "avg_objects_per_notification": (
                        round(len(notif_df) / len(unique_notifs), 2)
                        if len(unique_notifs) > 0
                        else 0
                    ),
                    "info": "Multiple objects per notification is normal structure",
                }

        return duplicates

    def generate_html_report(self, analysis_results: Dict[str, Any]) -> str:
        """
        Generate HTML report from analysis results.

        Args:
            analysis_results: Dictionary of analysis results

        Returns:
            HTML report string
        """
        # Use triple quotes but avoid format string issues
        html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MIB Data Analysis Report</title>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
            }}
            h2 {{
                color: #34495e;
                margin-top: 30px;
                border-bottom: 1px solid #ecf0f1;
                padding-bottom: 5px;
            }}
            .metric {{
                display: inline-block;
                margin: 10px 20px 10px 0;
                padding: 10px 15px;
                background-color: #ecf0f1;
                border-radius: 4px;
            }}
            .metric-label {{
                font-weight: bold;
                color: #7f8c8d;
                font-size: 0.9em;
            }}
            .metric-value {{
                font-size: 1.2em;
                color: #2c3e50;
            }}
            .grade {{
                display: inline-block;
                padding: 5px 15px;
                border-radius: 20px;
                font-weight: bold;
                color: white;
            }}
            .grade-A {{ background-color: #27ae60; }}
            .grade-B {{ background-color: #3498db; }}
            .grade-C {{ background-color: #f39c12; }}
            .grade-D {{ background-color: #e67e22; }}
            .grade-F {{ background-color: #e74c3c; }}
            .issue {{
                padding: 5px 10px;
                margin: 5px 0;
                border-left: 3px solid #e74c3c;
                background-color: #ffe5e5;
            }}
            .warning {{
                padding: 5px 10px;
                margin: 5px 0;
                border-left: 3px solid #f39c12;
                background-color: #fff5e5;
            }}
            .recommendation {{
                padding: 5px 10px;
                margin: 5px 0;
                border-left: 3px solid #3498db;
                background-color: #e5f5ff;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 15px 0;
            }}
            th {{
                background-color: #34495e;
                color: white;
                padding: 10px;
                text-align: left;
            }}
            td {{
                padding: 8px;
                border-bottom: 1px solid #ecf0f1;
            }}
            tr:hover {{
                background-color: #f8f9fa;
            }}
            .timestamp {{
                text-align: right;
                color: #7f8c8d;
                font-size: 0.9em;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>MIB Data Analysis Report</h1>
            <p class="timestamp">Generated: {timestamp}</p>
            {content}
        </div>
    </body>
    </html>
        """

        content_parts = []

        # Add each analysis section
        for section_name, section_data in analysis_results.items():
            if isinstance(section_data, dict):
                content_parts.append(self._format_section_html(section_name, section_data))

        # Format the template with actual data
        # Note the double curly braces in CSS are escaped
        return html_template.format(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), content="\n".join(content_parts)
        )

    def _format_section_html(self, section_name: str, section_data: Dict[str, Any]) -> str:
        """Format a section of analysis results as HTML - FIXED."""
        html = f"<h2>{section_name.replace('_', ' ').title()}</h2>\n"

        for key, value in section_data.items():
            if isinstance(value, dict):
                # Special handling for notification coverage
                if key == "notification_coverage":
                    html += "<h3>Notification Coverage</h3>\n"
                    html += "<table>\n"

                    # Basic stats
                    html += f"<tr><td><strong>Total Notifications</strong></td>"
                    html += f"<td>{value.get('total_notifications', 0)}</td></tr>\n"

                    # List notifications
                    if "notification_list" in value:
                        html += f"<tr><td><strong>Notifications</strong></td>"
                        html += f"<td>{', '.join(value['notification_list'])}</td></tr>\n"

                    # Objects per notification
                    if "objects_per_notification" in value:
                        html += f"<tr><td><strong>Objects per Notification</strong></td><td></td></tr>\n"
                        for notif, count in value["objects_per_notification"].items():
                            html += f"<tr><td>&nbsp;&nbsp;{notif}</td><td>{count}</td></tr>\n"

                    # Other stats
                    for k, v in value.items():
                        if k not in ["notification_list", "objects_per_notification"]:
                            html += f"<tr><td><strong>{k.replace('_', ' ').title()}</strong></td>"
                            html += f"<td>{v}</td></tr>\n"

                    html += "</table>\n"

                # Special handling for module coverage
                elif key == "module_coverage":
                    html += "<h3>Module Coverage</h3>\n"
                    html += "<table>\n"

                    # Basic stats
                    for k, v in value.items():
                        if k == "module_list":
                            html += f"<tr><td><strong>Modules</strong></td>"
                            html += f"<td>{', '.join(v)}</td></tr>\n"
                        elif k == "records_per_module":
                            html += (
                                f"<tr><td><strong>Records per Module</strong></td><td></td></tr>\n"
                            )
                            for module, count in v.items():
                                html += f"<tr><td>&nbsp;&nbsp;{module}</td><td>{count}</td></tr>\n"
                        elif not isinstance(v, (dict, list)):
                            html += f"<tr><td><strong>{k.replace('_', ' ').title()}</strong></td>"
                            html += f"<td>{v}</td></tr>\n"

                    html += "</table>\n"

                # Default dict handling
                else:
                    html += f"<h3>{key.replace('_', ' ').title()}</h3>\n"
                    html += self._dict_to_table_html(value)

            elif isinstance(value, list):
                html += f"<h3>{key.replace('_', ' ').title()}</h3>\n"
                for item in value:
                    if "issue" in key.lower():
                        html += f'<div class="issue">{item}</div>\n'
                    elif "warning" in key.lower():
                        html += f'<div class="warning">{item}</div>\n'
                    elif "recommendation" in key.lower():
                        html += f'<div class="recommendation">{item}</div>\n'
                    else:
                        html += f"<div>{item}</div>\n"

            elif key == "grade":
                html += f'<div class="grade grade-{value}">Grade: {value}</div>\n'

            elif key == "quality_score":
                html += f'<div class="metric"><div class="metric-label">Quality Score</div>'
                html += f'<div class="metric-value">{value:.1f}%</div></div>\n'

            elif not key.startswith("_") and key != "total_records":
                # Skip internal fields and total_records (shown elsewhere)
                pass

        return html

    def _dict_to_table_html(self, data: Dict[str, Any]) -> str:
        """Convert dictionary to HTML table."""
        if not data:
            return ""

        # Check if it's a simple key-value dict
        if all(not isinstance(v, dict) for v in data.values()):
            rows = []
            for key, value in data.items():
                if isinstance(value, float):
                    value = f"{value:.2f}"
                elif isinstance(value, (list, dict)):
                    value = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                rows.append(f"<tr><td><strong>{key}</strong></td><td>{value}</td></tr>")

            return f"<table><tbody>{''.join(rows)}</tbody></table>"
        else:
            # Complex nested dict - create a proper table
            headers = set()
            for value in data.values():
                if isinstance(value, dict):
                    headers.update(value.keys())

            headers = sorted(headers)

            html = "<table><thead><tr><th>Item</th>"
            for header in headers:
                html += f"<th>{header}</th>"
            html += "</tr></thead><tbody>"

            for key, value in data.items():
                html += f"<tr><td><strong>{key}</strong></td>"
                if isinstance(value, dict):
                    for header in headers:
                        cell_value = value.get(header, "")
                        if isinstance(cell_value, float):
                            cell_value = f"{cell_value:.2f}"
                        html += f"<td>{cell_value}</td>"
                else:
                    html += f"<td colspan='{len(headers)}'>{value}</td>"
                html += "</tr>"

            html += "</tbody></table>"
            return html

    def _analyze_oid_quality(self, oid_series: pd.Series) -> Dict[str, Any]:
        """Analyze OID quality issues - FIXED to handle empty OIDs better."""
        quality = {
            "total": len(oid_series),
            "missing": oid_series.isna().sum(),
            "empty": (oid_series == "").sum(),  # Count empty strings
            "invalid_format": 0,
            "duplicates": 0,
            "suspicious": [],
        }

        # Check for invalid OID format (excluding empty/null)
        valid_oid_pattern = r"^[\d\.]+$"
        non_null_oids = oid_series[(oid_series.notna()) & (oid_series != "")]

        for oid in non_null_oids:
            if not re.match(valid_oid_pattern, str(oid)):
                quality["invalid_format"] += 1

        # Check for duplicates (excluding empty/null)
        if len(non_null_oids) > 0:
            quality["duplicates"] = non_null_oids.duplicated().sum()

        # Check for suspicious OIDs (too short or too long)
        for oid in non_null_oids:
            oid_str = str(oid)
            parts = oid_str.split(".")
            if len(parts) < 3:
                quality["suspicious"].append(f"Too short: {oid_str}")
            elif len(parts) > 20:
                quality["suspicious"].append(f"Too long: {oid_str}")

        return quality

    def _analyze_description_quality(self, desc_series: pd.Series) -> Dict[str, Any]:
        """Analyze description quality."""
        quality = {
            "total": len(desc_series),
            "missing": desc_series.isna().sum(),
            "missing_percentage": 0,
            "too_short": 0,
            "too_long": 0,
            "avg_length": 0,
            "min_length": 0,
            "max_length": 0,
        }

        non_null_desc = desc_series.dropna()

        if len(non_null_desc) > 0:
            lengths = non_null_desc.str.len()
            quality["avg_length"] = lengths.mean()
            quality["min_length"] = lengths.min()
            quality["max_length"] = lengths.max()
            quality["too_short"] = (lengths < 10).sum()
            quality["too_long"] = (lengths > 1000).sum()

        quality["missing_percentage"] = (quality["missing"] / quality["total"]) * 100

        return quality
