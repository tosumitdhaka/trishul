#!/usr/bin/env python3
"""
Deduplication Service - Handles duplicate detection and removal
Provides intelligent deduplication strategies for MIB data
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd

from utils.logger import get_logger


@dataclass
class DuplicateGroup:
    """Represents a group of duplicate records."""

    key: str
    indices: List[int]
    count: int
    preferred_index: Optional[int] = None
    reason: str = ""
    score_details: Dict[int, float] = None


class DeduplicationService:
    """Manages deduplication of MIB data."""

    def __init__(self):
        """Initialize deduplication service."""
        self.logger = get_logger(self.__class__.__name__)

        # Statistics
        self.stats = {
            "total_processed": 0,
            "duplicates_found": 0,
            "duplicates_removed": 0,
            "groups_found": 0,
        }

        # Deduplication strategies
        self.strategies = {
            "smart": self._deduplicate_smart,
            "keep_first": self._deduplicate_keep_first,
            "keep_last": self._deduplicate_keep_last,
            "keep_all_modules": self._deduplicate_keep_all_modules,
            "merge": self._deduplicate_merge,
            "none": self._deduplicate_none,  # New: no deduplication
        }

    def find_duplicates(
        self, df: pd.DataFrame, key_columns: List[str] = None
    ) -> Dict[str, DuplicateGroup]:
        """
        Find ACTUAL duplicate records in DataFrame.

        IMPORTANT: For MIB data, we need to understand what constitutes a real duplicate:
        1. Notification objects with same notification_name but different object_sequence are NOT duplicates
        2. Objects with different OIDs are NOT duplicates
        3. Same object in different modules might be intentional (imports)

        Args:
            df: Input DataFrame
            key_columns: Columns to use for duplicate detection

        Returns:
            Dictionary of duplicate groups
        """
        if df.empty:
            return {}

        # Debug: Let's see what columns we have
        self.logger.debug(f"DataFrame columns: {df.columns.tolist()}")
        self.logger.debug(f"DataFrame shape: {df.shape}")

        # FIXED: Proper duplicate detection for MIB data
        if key_columns is None:
            # Check what type of data we have
            has_notifications = (
                "notification_name" in df.columns and df["notification_name"].notna().any()
            )
            has_objects = "object_oid" in df.columns and df["object_oid"].notna().any()

            if has_notifications and has_objects:
                # For notification objects, we need ALL these fields to match for a duplicate
                # Different object_sequence means different objects in the same notification!
                key_columns = ["notification_name", "object_sequence", "object_name", "object_oid"]
                # Remove columns that don't exist
                key_columns = [col for col in key_columns if col in df.columns]

                # If we don't have enough columns, use OID as unique identifier
                if len(key_columns) < 3:
                    key_columns = ["object_oid"] if "object_oid" in df.columns else []

            elif "object_oid" in df.columns:
                # OID should be unique - this is the safest key
                key_columns = ["object_oid"]

            elif "tc_name" in df.columns:
                # For textual conventions
                key_columns = ["tc_name"]
                if "module_name" in df.columns:
                    key_columns.append("module_name")

            else:
                # Last resort - but this might be too aggressive
                self.logger.warning("Using fallback duplicate detection - may be inaccurate")
                key_columns = ["object_name"] if "object_name" in df.columns else []

        if not key_columns:
            self.logger.warning("No key columns for duplicate detection - skipping")
            return {}

        # Remove any columns that don't exist
        key_columns = [col for col in key_columns if col in df.columns]

        self.logger.info(f"Using key columns for duplicate detection: {key_columns}")

        # Find duplicates
        duplicate_groups = {}

        # Create composite key, handling NaN values properly
        df_copy = df.copy()

        # Create a key that handles NaN values
        key_parts = []
        for col in key_columns:
            # Convert to string and replace NaN with a unique marker
            col_str = df_copy[col].fillna(f"__NAN_{col}__").astype(str)
            key_parts.append(col_str)

        if key_parts:
            df_copy["_dup_key"] = pd.concat(key_parts, axis=1).agg("|".join, axis=1)
        else:
            # No valid key columns
            return {}

        # Group by key and find actual duplicates
        for key, group in df_copy.groupby("_dup_key"):
            # Skip if the key contains NaN markers (these aren't real duplicates)
            if "__NAN_" in key:
                continue

            if len(group) > 1:
                # Additional check: are these REALLY duplicates?
                # For notification objects, check if they're actually different objects
                if "notification_name" in df.columns and "object_sequence" in df.columns:
                    # If object_sequence is different, these are NOT duplicates
                    unique_sequences = group["object_sequence"].nunique()
                    if unique_sequences > 1:
                        continue  # Skip this group, not real duplicates

                dup_group = DuplicateGroup(key=key, indices=group.index.tolist(), count=len(group))
                duplicate_groups[key] = dup_group

        self.stats["groups_found"] = len(duplicate_groups)
        self.stats["duplicates_found"] = sum(g.count - 1 for g in duplicate_groups.values())

        if duplicate_groups:
            self.logger.info(
                f"Found {len(duplicate_groups)} duplicate groups with "
                f"{self.stats['duplicates_found']} duplicate records"
            )

            # Debug: Show what's being considered duplicate
            if self.logger.isEnabledFor(10):  # DEBUG level
                for key, group in list(duplicate_groups.items())[:3]:  # Show first 3
                    sample_indices = group.indices[:2]
                    self.logger.debug(f"Duplicate group key: {key}")
                    for idx in sample_indices:
                        row = df.iloc[idx]
                        self.logger.debug(
                            f"  Row {idx}: {row.get('object_name', 'N/A')} | "
                            f"{row.get('object_oid', 'N/A')} | "
                            f"{row.get('notification_name', 'N/A')}"
                        )
        else:
            self.logger.info("No duplicates found")

        return duplicate_groups

    def deduplicate(
        self, df: pd.DataFrame, strategy: str = "smart", key_columns: List[str] = None
    ) -> pd.DataFrame:
        """
        Remove duplicates using specified strategy.

        Args:
            df: Input DataFrame
            strategy: Deduplication strategy
            key_columns: Columns to use for duplicate detection

        Returns:
            Deduplicated DataFrame
        """
        if df.empty:
            return df

        self.stats["total_processed"] = len(df)

        # Special case: 'none' strategy means no deduplication
        if strategy == "none":
            self.logger.info("Deduplication disabled (strategy='none')")
            return df

        # Get strategy function
        if strategy not in self.strategies:
            self.logger.warning(f"Unknown strategy '{strategy}', using 'smart'")
            strategy = "smart"

        strategy_func = self.strategies[strategy]

        # Find duplicates with improved detection
        duplicate_groups = self.find_duplicates(df, key_columns)

        if not duplicate_groups:
            # No duplicates found - return original data
            return df

        # Apply strategy
        deduplicated_df = strategy_func(df, duplicate_groups)

        self.stats["duplicates_removed"] = len(df) - len(deduplicated_df)

        if self.stats["duplicates_removed"] > 0:
            self.logger.info(
                f"Removed {self.stats['duplicates_removed']} duplicates using '{strategy}' strategy"
            )

        return deduplicated_df

    def _deduplicate_none(
        self, df: pd.DataFrame, duplicate_groups: Dict[str, DuplicateGroup]
    ) -> pd.DataFrame:
        """No deduplication - return original DataFrame."""
        return df

    def _deduplicate_smart(
        self, df: pd.DataFrame, duplicate_groups: Dict[str, DuplicateGroup]
    ) -> pd.DataFrame:
        """Smart deduplication based on data quality scoring."""

        # Score each record in duplicate groups
        for key, group in duplicate_groups.items():
            scores = {}
            for idx in group.indices:
                scores[idx] = self._calculate_quality_score(df.iloc[idx])

            # Select highest scoring record
            group.preferred_index = max(scores, key=scores.get)
            group.score_details = scores
            group.reason = "Highest quality score"

        # Build list of indices to keep
        indices_to_keep = set(range(len(df)))

        for group in duplicate_groups.values():
            # Remove all but preferred
            for idx in group.indices:
                if idx != group.preferred_index:
                    indices_to_keep.discard(idx)

        return df.iloc[sorted(indices_to_keep)]

    def _deduplicate_keep_first(
        self, df: pd.DataFrame, duplicate_groups: Dict[str, DuplicateGroup]
    ) -> pd.DataFrame:
        """Keep first occurrence of duplicates."""

        indices_to_keep = set(range(len(df)))

        for group in duplicate_groups.values():
            # Keep only the first index
            group.preferred_index = min(group.indices)
            group.reason = "First occurrence"

            for idx in group.indices[1:]:
                indices_to_keep.discard(idx)

        return df.iloc[sorted(indices_to_keep)]

    def _deduplicate_keep_last(
        self, df: pd.DataFrame, duplicate_groups: Dict[str, DuplicateGroup]
    ) -> pd.DataFrame:
        """Keep last occurrence of duplicates."""

        indices_to_keep = set(range(len(df)))

        for group in duplicate_groups.values():
            # Keep only the last index
            group.preferred_index = max(group.indices)
            group.reason = "Last occurrence"

            for idx in group.indices[:-1]:
                indices_to_keep.discard(idx)

        return df.iloc[sorted(indices_to_keep)]

    def _deduplicate_keep_all_modules(
        self, df: pd.DataFrame, duplicate_groups: Dict[str, DuplicateGroup]
    ) -> pd.DataFrame:
        """Keep one copy per module for duplicates."""

        if "module_name" not in df.columns:
            self.logger.warning("No module_name column, falling back to keep_first")
            return self._deduplicate_keep_first(df, duplicate_groups)

        indices_to_keep = set(range(len(df)))

        for group in duplicate_groups.values():
            # Group by module within duplicate group
            module_indices = {}
            for idx in group.indices:
                module = df.iloc[idx]["module_name"]
                if module not in module_indices:
                    module_indices[module] = []
                module_indices[module].append(idx)

            # Keep first from each module, remove others
            for module, idx_list in module_indices.items():
                for idx in idx_list[1:]:
                    indices_to_keep.discard(idx)

            group.reason = f"One per module ({len(module_indices)} modules)"

        return df.iloc[sorted(indices_to_keep)]

    def _deduplicate_merge(
        self, df: pd.DataFrame, duplicate_groups: Dict[str, DuplicateGroup]
    ) -> pd.DataFrame:
        """Merge information from duplicates."""

        merged_rows = []
        indices_to_skip = set()

        for group in duplicate_groups.values():
            # Merge all rows in group
            merged_row = self._merge_rows(df, group.indices)
            merged_rows.append(merged_row)

            # Mark all indices in group to skip
            indices_to_skip.update(group.indices)

            group.reason = "Merged information"

        # Add non-duplicate rows
        for idx in range(len(df)):
            if idx not in indices_to_skip:
                merged_rows.append(df.iloc[idx])

        return pd.DataFrame(merged_rows)

    def _calculate_quality_score(self, row: pd.Series) -> float:
        """Calculate quality score for a record."""
        score = 0.0

        # Score based on completeness
        non_null_count = row.notna().sum()
        total_fields = len(row)
        completeness_score = (non_null_count / total_fields) * 30
        score += completeness_score

        # Score based on status
        if "status" in row or "object_status" in row:
            status_col = "status" if "status" in row else "object_status"
            status = str(row[status_col]).lower() if pd.notna(row[status_col]) else ""

            if status == "current":
                score += 20
            elif status == "deprecated":
                score -= 10
            elif status == "obsolete":
                score -= 20

        # Score based on description length
        desc_fields = ["description", "object_description", "notification_description"]
        for field in desc_fields:
            if field in row and pd.notna(row[field]):
                desc_len = len(str(row[field]))
                if desc_len > 50:
                    score += 10
                elif desc_len > 20:
                    score += 5
                break

        # Score based on TC resolution
        if "tc_base_type" in row and pd.notna(row["tc_base_type"]):
            score += 10

        # Score based on OID presence
        if "object_oid" in row and pd.notna(row["object_oid"]):
            score += 10

        # Score based on module information
        if "module_name" in row and pd.notna(row["module_name"]):
            score += 5

        # Score based on timestamp (prefer newer)
        if "processed_at" in row and pd.notna(row["processed_at"]):
            score += 5

        return score

    def _merge_rows(self, df: pd.DataFrame, indices: List[int]) -> pd.Series:
        """Merge multiple rows into one."""
        if len(indices) == 1:
            return df.iloc[indices[0]]

        # Start with the highest quality row
        scores = {idx: self._calculate_quality_score(df.iloc[idx]) for idx in indices}
        best_idx = max(scores, key=scores.get)
        merged = df.iloc[best_idx].copy()

        # Merge information from other rows
        for idx in indices:
            if idx == best_idx:
                continue

            row = df.iloc[idx]

            # Fill missing values
            for col in df.columns:
                if pd.isna(merged[col]) and pd.notna(row[col]):
                    merged[col] = row[col]

            # Merge descriptions (take longest)
            desc_fields = ["description", "object_description", "notification_description"]
            for field in desc_fields:
                if field in row.index:
                    if pd.notna(row[field]):
                        current_desc = str(merged[field]) if pd.notna(merged[field]) else ""
                        new_desc = str(row[field])
                        if len(new_desc) > len(current_desc):
                            merged[field] = new_desc

        return merged

    def analyze_duplicates(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze what would be considered duplicates with different strategies.
        Useful for debugging and understanding the data.
        """
        analysis = {
            "total_records": len(df),
            "columns": df.columns.tolist(),
            "duplicate_analysis": {},
        }

        # Test different key combinations
        test_scenarios = [
            ("exact_duplicates", None),  # All columns
            ("by_oid", ["object_oid"]),
            ("by_name", ["object_name"]),
            ("by_notification_and_sequence", ["notification_name", "object_sequence"]),
            (
                "by_notification_sequence_oid",
                ["notification_name", "object_sequence", "object_oid"],
            ),
            ("by_name_and_module", ["object_name", "module_name"]),
        ]

        for scenario_name, key_cols in test_scenarios:
            if key_cols is None:
                # Exact duplicates (all columns)
                dup_count = df.duplicated().sum()
            else:
                # Check if columns exist
                valid_cols = [col for col in key_cols if col in df.columns]
                if not valid_cols:
                    continue

                dup_count = df.duplicated(subset=valid_cols).sum()

            analysis["duplicate_analysis"][scenario_name] = {
                "key_columns": key_cols,
                "duplicate_count": int(dup_count),
                "unique_count": len(df) - int(dup_count),
                "percentage": round((dup_count / len(df)) * 100, 2) if len(df) > 0 else 0,
            }

        # Show sample of what would be considered duplicates
        if "object_oid" in df.columns:
            oid_dups = df[df.duplicated(subset=["object_oid"], keep=False)]
            if not oid_dups.empty:
                analysis["sample_oid_duplicates"] = (
                    oid_dups[["object_name", "object_oid", "module_name"]]
                    .head(10)
                    .to_dict("records")
                )

        return analysis

    def get_duplicate_report(
        self, df: pd.DataFrame, key_columns: List[str] = None
    ) -> Dict[str, Any]:
        """Generate detailed duplicate report."""
        duplicate_groups = self.find_duplicates(df, key_columns)

        report = {
            "summary": {
                "total_records": len(df),
                "duplicate_groups": len(duplicate_groups),
                "duplicate_records": self.stats["duplicates_found"],
                "duplicate_percentage": (
                    round((self.stats["duplicates_found"] / len(df)) * 100, 2) if len(df) > 0 else 0
                ),
            },
            "groups": [],
            "recommendations": [],
        }

        # Analyze each duplicate group (limit to first 10 for readability)
        for key, group in list(duplicate_groups.items())[:10]:
            group_info = {
                "key": key,
                "count": group.count,
                "indices": group.indices[:10],
                "samples": [],
            }

            # Add sample data from duplicates
            for idx in group.indices[:3]:
                row = df.iloc[idx]
                sample = {}

                # Include key fields
                for col in [
                    "object_name",
                    "module_name",
                    "status",
                    "object_oid",
                    "notification_name",
                    "object_sequence",
                ]:
                    if col in row.index:
                        sample[col] = row[col]

                group_info["samples"].append(sample)

            report["groups"].append(group_info)

        # Generate recommendations based on actual duplicates found
        if self.stats["duplicates_found"] > 0:
            dup_pct = (self.stats["duplicates_found"] / len(df)) * 100

            if dup_pct < 5:
                report["recommendations"].append(
                    f"Low duplicate rate ({dup_pct:.1f}%) - Normal, use 'smart' strategy"
                )
            elif dup_pct > 50:
                report["recommendations"].append(
                    f"Very high duplicate rate ({dup_pct:.1f}%) - Check if duplicate detection is too aggressive"
                )

            # Check for cross-module duplicates
            if "module_name" in df.columns and duplicate_groups:
                cross_module = 0
                for group in duplicate_groups.values():
                    modules = df.iloc[group.indices]["module_name"].nunique()
                    if modules > 1:
                        cross_module += 1

                if cross_module > 0:
                    report["recommendations"].append(
                        f"{cross_module} duplicate groups span multiple modules - "
                        "Consider 'keep_all_modules' strategy"
                    )
        else:
            report["recommendations"].append(
                "No duplicates found - deduplication may not be needed"
            )

        return report

    def compare_strategies(self, df: pd.DataFrame, key_columns: List[str] = None) -> Dict[str, Any]:
        """Compare different deduplication strategies."""
        duplicate_groups = self.find_duplicates(df, key_columns)

        if not duplicate_groups:
            return {"message": "No duplicates found", "recommendation": "none"}

        comparison = {
            "original_count": len(df),
            "duplicate_count": self.stats["duplicates_found"],
            "strategies": {},
        }

        # Test each strategy
        for strategy_name in self.strategies.keys():
            try:
                # Reset stats for each test
                self.reset_statistics()

                result_df = self.deduplicate(
                    df.copy(), strategy=strategy_name, key_columns=key_columns
                )

                comparison["strategies"][strategy_name] = {
                    "final_count": len(result_df),
                    "removed": len(df) - len(result_df),
                    "removal_rate": round(((len(df) - len(result_df)) / len(df)) * 100, 2),
                }

            except Exception as e:
                comparison["strategies"][strategy_name] = {"error": str(e)}

        # Smart recommendation based on data characteristics
        if self.stats["duplicates_found"] == 0:
            comparison["recommendation"] = "none"
            comparison["reason"] = "No duplicates detected"
        elif self.stats["duplicates_found"] < 10:
            comparison["recommendation"] = "smart"
            comparison["reason"] = "Few duplicates - use quality-based selection"
        else:
            comparison["recommendation"] = "smart"
            comparison["reason"] = "Default recommendation - quality-based selection"

        return comparison

    def get_statistics(self) -> Dict[str, Any]:
        """Get deduplication statistics."""
        return self.stats.copy()

    def reset_statistics(self):
        """Reset deduplication statistics."""
        self.stats = {
            "total_processed": 0,
            "duplicates_found": 0,
            "duplicates_removed": 0,
            "groups_found": 0,
        }
