#!/usr/bin/env python3
"""
MIB Parser - Optimized Version with Resource Sharing and Batch Processing
Handles MIB file compilation, dependency resolution, and data extraction efficiently
Version: 5.0.0 - Fixed enrichment, thread-safe, progress tracking
"""

import asyncio
import json
import os
import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import pandas as pd

from utils.cache import CacheManager

# Import Utils
from utils.logger import get_logger

# PySnmp/PySMI imports

from pysmi.codegen.pysnmp import PySnmpCodeGen
from pysmi.compiler import MibCompiler
from pysmi.parser.smi import parserFactory
from pysmi.reader.localfile import FileReader
from pysmi.searcher import StubSearcher
from pysmi.searcher.anyfile import AnyFileSearcher
from pysmi.searcher.stub import StubSearcher
from pysmi.writer.pyfile import PyFileWriter
from pysnmp.smi import builder


# Constants
BASE_TYPES = {
    "Integer32",
    "Integer",
    "OctetString",
    "ObjectIdentifier",
    "IpAddress",
    "Counter32",
    "Counter64",
    "Gauge32",
    "TimeTicks",
    "Unsigned32",
    "Bits",
    "Opaque",
}

STUB_MIBS = {"SNMPv2-SMI", "SNMPv2-TC", "SNMPv2-CONF", "RFC1155-SMI", "RFC1212", "RFC1213-MIB"}

# ============= PROGRESS TRACKING =============


@dataclass
class ProgressUpdate:
    """Structured progress update with backward compatibility"""

    phase: str  # "scanning" | "compiling" | "parsing" | "enriching" | "deduplicating" | "complete"
    current: int  # Current item number
    total: int  # Total items
    message: str  # Human-readable message
    percentage: float  # 0-100 overall progress
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_simple_callback(self) -> Tuple[int, int, str]:
        """Convert to simple (current, total, message) format for backward compatibility"""
        return (self.current, self.total, self.message)


# ============= DATA CLASSES (FIXED) =============


@dataclass
class MibObject:
    """Represents a MIB object with all enrichment fields."""

    # Core identification
    module_name: str
    object_name: str
    object_oid: str = ""
    node_type: str = ""

    # Object properties
    status: Optional[str] = None
    access_level: Optional[str] = None
    syntax_type: Optional[str] = None
    base_syntax: Optional[str] = None  # ✅ Now properly populated

    # Descriptive fields
    description: Optional[str] = None
    display_hint: Optional[str] = None
    units: Optional[str] = None
    default_value: Optional[str] = None  # ✅ Now extracted
    reference: Optional[str] = None

    # Constraints and enumerations
    value_range: Optional[str] = None
    enumerations: Optional[Dict] = None  # ✅ Now properly extracted

    # Table-specific
    table_indexes: Optional[str] = None  # ✅ Now extracted
    augments_table: Optional[str] = None  # ✅ Now extracted

    # Notification-specific
    notification_objects: Optional[List[str]] = None
    notification_objects_detail: Optional[Dict] = None
    notification_enterprise: Optional[str] = None  # ✅ Now extracted

    # Parent relationships
    parent_oid: Optional[str] = None
    parent_name: Optional[str] = None
    parent_type: Optional[str] = None

    # Metadata
    source_file: Optional[str] = None
    processed_at: Optional[datetime] = None
    mib_revision: Optional[str] = None
    mib_imports: Optional[str] = None

    # TC resolution (enhanced)
    tc_name: Optional[str] = None
    tc_base_type: Optional[str] = None
    tc_display_hint: Optional[str] = None
    tc_status: Optional[str] = None
    tc_description: Optional[str] = None  # ✅ Now properly extracted
    tc_constraints: Optional[str] = None
    tc_resolution_chain: Optional[str] = None  # ✅ Now complete


@dataclass
class TextualConvention:
    """Represents a TEXTUAL-CONVENTION."""

    name: str
    module: str
    status: str = "current"
    description: str = ""
    reference: Optional[str] = None
    display_hint: Optional[str] = None
    syntax: str = ""
    base_type: str = ""
    constraints: str = ""
    enumerations: Optional[Dict[str, int]] = None


# ============= SHARED RESOURCES MANAGER (THREAD-SAFE) =============


class SharedMibResources:
    """Thread-safe singleton resource manager for MIB parsing."""

    _instance = None
    _lock = threading.Lock()  # ✅ Thread-safe singleton

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:  # Double-check
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def initialize(self, compiled_dir: Path, search_paths: List[Path], logger=None):
        """Initialize shared resources once (thread-safe)."""
        with self._lock:
            if self._initialized:
                return

            self.logger = logger or get_logger(self.__class__.__name__)
            self.compiled_dir = compiled_dir
            self.search_paths = search_paths  # ✅ Now stored here

            # Thread-safe access lock for shared resources
            self.resource_lock = threading.RLock()  # ✅ Reentrant lock

            # Create shared MIB builder
            self.logger.debug("Initializing shared MIB builder...")
            self.mib_builder = builder.MibBuilder()
            self.mib_builder.loadTexts = False
            self.mib_builder.addMibSources(
                builder.DirMibSource(str(compiled_dir)),
                builder.DirMibSource(os.path.join(os.path.dirname(builder.__file__), "mibs")),
            )

            # Pre-load common modules
            self.preloaded_modules = set()
            self._preload_common_modules()

            # Global indices (thread-safe access via resource_lock)
            self.all_objects = {}
            self.all_tcs = {}
            self.all_notifications = {}
            self.oid_to_object = {}
            self.module_objects = defaultdict(list)

            # Caches
            self.external_object_cache = {}
            self.tc_resolution_cache = {}
            self.description_cache = {}
            self.module_symbols_cache = {}

            # Statistics
            self.stats = {"modules_loaded": 0, "cache_hits": 0, "cache_misses": 0}

            self._initialized = True
            self.logger.info("Shared resources initialized (thread-safe)")

    def _preload_common_modules(self):
        """Pre-load frequently used modules."""
        common_modules = [
            "SNMPv2-SMI",
            "SNMPv2-TC",
            "SNMPv2-CONF",
            "SNMPv2-MIB",
            "IF-MIB",
            "RFC1213-MIB",
            "INET-ADDRESS-MIB",
        ]

        for module in common_modules:
            try:
                if module not in self.mib_builder.mibSymbols:
                    self.mib_builder.loadModules(module)
                    self.preloaded_modules.add(module)
                    self.stats["modules_loaded"] += 1
            except Exception:
                pass

        self.logger.debug(f"Pre-loaded {len(self.preloaded_modules)} common modules")

    def get_module_symbols(self, module_name: str) -> Dict:
        """Get all symbols from a module (cached, thread-safe)."""
        with self.resource_lock:
            # Check cache first
            if module_name in self.module_symbols_cache:
                self.stats["cache_hits"] += 1
                return self.module_symbols_cache[module_name]

            # Load if not in cache
            if module_name not in self.mib_builder.mibSymbols:
                try:
                    self.logger.debug(f"Loading module: {module_name}")
                    self.mib_builder.loadModules(module_name)
                    self.stats["modules_loaded"] += 1
                except Exception as e:
                    self.logger.debug(f"Failed to load module {module_name}: {e}")
                    return {}

            symbols = self.mib_builder.mibSymbols.get(module_name, {})
            self.module_symbols_cache[module_name] = symbols
            self.stats["cache_misses"] += 1
            return symbols

    def reset_stats(self):
        """Reset statistics."""
        with self.resource_lock:
            self.stats = {"modules_loaded": 0, "cache_hits": 0, "cache_misses": 0}


# ============= BATCH PROCESSOR (ENHANCED) =============


class BatchProcessor:
    """Process multiple objects in single pass with complete enrichment."""

    def __init__(self, resources: SharedMibResources, logger=None):
        self.resources = resources
        self.logger = logger or get_logger(self.__class__.__name__)

    def batch_resolve_tcs(self, objects: List[MibObject]) -> None:
        """Resolve all TCs with complete resolution chain - ENHANCED."""
        start_time = time.time()

        # Collect all unique TC names
        tc_names = set()
        for obj in objects:
            if obj.syntax_type and obj.syntax_type not in BASE_TYPES:
                tc_names.add(obj.syntax_type)

        if not tc_names:
            return

        self.logger.debug(f"Resolving {len(tc_names)} unique TCs...")

        # Build complete TC map
        tc_map = {}
        tc_load_queue = list(tc_names)
        loaded_tcs = set()
        failed_tcs = set()  # ✅ Track failed TCs to avoid retrying

        max_iterations = 10
        iteration = 0

        while tc_load_queue and iteration < max_iterations:
            iteration += 1
            next_queue = []

            for tc_name in tc_load_queue:
                if tc_name in loaded_tcs or tc_name in failed_tcs:
                    continue

                # Try cache first
                with self.resources.resource_lock:
                    if tc_name in self.resources.tc_resolution_cache:
                        tc = self.resources.tc_resolution_cache[tc_name]
                    else:
                        tc = self._find_tc_in_loaded_modules(tc_name)
                        if tc:
                            self.resources.tc_resolution_cache[tc_name] = tc

                if tc:
                    tc_map[tc_name] = tc
                    loaded_tcs.add(tc_name)

                    # If this TC's base is another TC, add it to queue
                    if (
                        tc.base_type
                        and tc.base_type not in BASE_TYPES
                        and tc.base_type not in loaded_tcs
                    ):
                        next_queue.append(tc.base_type)
                else:
                    failed_tcs.add(tc_name)  # ✅ Don't retry

            tc_load_queue = next_queue

        # Apply to all objects with complete resolution chain
        resolved_count = 0
        for obj in objects:
            if obj.syntax_type in tc_map:
                tc = tc_map[obj.syntax_type]

                # Set TC fields
                obj.tc_name = tc.name
                obj.tc_base_type = tc.base_type or ""
                obj.tc_display_hint = tc.display_hint or ""
                obj.tc_status = tc.status or ""
                obj.tc_description = tc.description or ""  # ✅ Now properly extracted
                obj.tc_constraints = tc.constraints or ""

                # Build complete resolution chain
                chain = []
                visited = set()
                current_name = tc.name

                while current_name:
                    if current_name in visited:
                        break  # Circular reference

                    chain.append(current_name)
                    visited.add(current_name)

                    # Get next in chain
                    if current_name in tc_map:
                        current_tc = tc_map[current_name]
                        if current_tc.base_type and current_tc.base_type != current_name:
                            if current_tc.base_type in BASE_TYPES:
                                chain.append(current_tc.base_type)  # Add base type to chain
                                break
                            current_name = current_tc.base_type
                        else:
                            break
                    elif current_name in BASE_TYPES:
                        break
                    else:
                        # Really can't find it - stop here, don't add garbage
                        self.logger.debug(
                            f"TC chain for {tc.name} stops at {current_name} (not found)"
                        )
                        break  # ✅ Just break, don't add "...(incomplete)"

                obj.tc_resolution_chain = "->".join(chain)
                resolved_count += 1

        elapsed = time.time() - start_time
        self.logger.debug(f"Resolved {resolved_count} TCs in {elapsed:.2f}s")

    def _find_tc_in_loaded_modules(self, tc_name: str) -> Optional[TextualConvention]:
        """Find TC in all loaded modules."""
        # Check global TC cache first
        with self.resources.resource_lock:
            if tc_name in self.resources.all_tcs:
                return self.resources.all_tcs[tc_name]

        # Search in all loaded modules
        for module_name in self.resources.mib_builder.mibSymbols:
            module_symbols = self.resources.mib_builder.mibSymbols[module_name]
            if tc_name in module_symbols:
                tc_node = module_symbols[tc_name]
                if self._is_textual_convention(tc_node):
                    tc = self._extract_tc_from_node(tc_name, tc_node, module_name)
                    if tc:
                        with self.resources.resource_lock:
                            self.resources.all_tcs[tc_name] = tc
                        return tc

        return None

    def _is_textual_convention(self, mib_node) -> bool:
        """Check if a MIB node is a TextualConvention."""
        class_name = type(mib_node).__name__
        if "TextualConvention" in class_name:
            return True

        # Check for TC-specific attributes
        if hasattr(mib_node, "getDisplayHint") and hasattr(mib_node, "getStatus"):
            if not hasattr(mib_node, "getMaxAccess"):
                return True

        return False

    def _extract_tc_from_node(
        self, tc_name: str, tc_node, module_name: str
    ) -> Optional[TextualConvention]:
        """Extract TextualConvention details - FIXED to use source MIB file."""
        try:
            self.logger.debug(f"Extracting TC: {tc_name} from module: {module_name}")

            tc = TextualConvention(name=tc_name, module=module_name, status="current")  # Default

            # ============================================
            # ATTEMPT 1: Try to get from compiled node (rarely works for TCs)
            # ============================================

            # Try to get syntax object (this sometimes works)
            if hasattr(tc_node, "getSyntax"):
                try:
                    syntax_obj = tc_node.getSyntax()
                    if syntax_obj:
                        # Get base type from class hierarchy
                        for base_class in syntax_obj.__class__.__mro__:
                            base_name = base_class.__name__
                            if base_name in BASE_TYPES:
                                tc.base_type = base_name
                                break

                        # Get constraints
                        if hasattr(syntax_obj, "subtypeSpec") and syntax_obj.subtypeSpec:
                            tc.constraints = str(syntax_obj.subtypeSpec)

                        # Get enumerations
                        if hasattr(syntax_obj, "namedValues") and syntax_obj.namedValues:
                            tc.enumerations = dict(syntax_obj.namedValues)
                except Exception as e:
                    self.logger.debug(f"Could not extract from compiled node: {e}")

            # ============================================
            # ATTEMPT 2: Extract everything from source MIB file
            # ============================================
            self.logger.debug("Extracting TC details from source MIB file...")

            # Find the MIB file
            mib_file = None
            for search_path in self.resources.search_paths:
                for ext in ["", ".mib", ".txt", ".my"]:
                    test_path = search_path / f"{module_name}{ext}"
                    if test_path.exists():
                        mib_file = test_path
                        break
                if mib_file:
                    break

            if mib_file:
                try:
                    with open(mib_file, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    # Pattern to match TEXTUAL-CONVENTION definition
                    pattern = (
                        rf"{tc_name}\s+::=\s+TEXTUAL-CONVENTION\s+"
                        r"(?:.*?)"
                        r'(?:DISPLAY-HINT\s+"([^"]+)"\s+)?'  # Optional display hint
                        r"(?:.*?)"
                        r"STATUS\s+(\w+)\s+"  # Status
                        r"(?:.*?)"
                        r'DESCRIPTION\s+"((?:[^"]|"")*?)"\s+'  # Description
                        r"(?:.*?)"
                        r'(?:REFERENCE\s+"((?:[^"]|"")*?)"\s+)?'  # Optional reference
                        r"(?:.*?)"
                        r"SYNTAX\s+([A-Z][A-Za-z0-9]*)"  # Syntax type
                        r"(?:\s*\(([^)]+)\))?"  # Optional constraints in parentheses
                        r"(?:\s*\{([^}]+)\})?"  # Optional enumerations in braces
                    )

                    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

                    if match:
                        display_hint, status, description, reference, syntax, constraints, enums = (
                            match.groups()
                        )

                        # Set display hint
                        if display_hint:
                            tc.display_hint = display_hint.strip()
                            # self.logger.debug(f"  ✅ Display hint: {tc.display_hint}")

                        # Set status
                        if status:
                            tc.status = status.strip()
                            # self.logger.debug(f"  ✅ Status: {tc.status}")

                        # Set description
                        if description:
                            tc.description = description.replace('""', '"').strip()
                            tc.description = re.sub(r"\s+", " ", tc.description)
                            # self.logger.debug(f"  ✅ Description: {len(tc.description)} chars")

                        # Set reference
                        if reference:
                            tc.reference = reference.replace('""', '"').strip()

                        # Set base type
                        if syntax:
                            syntax_map = {
                                "INTEGER": "Integer32",
                                "Integer": "Integer32",
                                "OCTET": "OctetString",
                                "OBJECT": "ObjectIdentifier",
                            }
                            tc.base_type = syntax_map.get(syntax, syntax)
                            # self.logger.debug(f"  ✅ Base type: {tc.base_type}")

                        # Set constraints
                        if constraints:
                            tc.constraints = constraints.strip()
                            # self.logger.debug(f"  ✅ Constraints: {tc.constraints}")

                        # Parse enumerations
                        if enums:
                            enum_dict = {}
                            # Pattern: name(value)
                            enum_pattern = r"(\w+)\s*\(\s*(\d+)\s*\)"
                            for enum_match in re.finditer(enum_pattern, enums):
                                enum_name = enum_match.group(1)
                                enum_value = int(enum_match.group(2))
                                enum_dict[enum_name] = enum_value

                            if enum_dict:
                                tc.enumerations = enum_dict
                                # self.logger.debug(f"  ✅ Enumerations: {tc.enumerations}")

                    else:
                        self.logger.debug("  ⚠️ Could not parse TC definition from source")

                except Exception as e:
                    self.logger.debug(f"Error reading source MIB file: {e}")

            # Fallback: If still no base type, extract just the syntax
            if not tc.base_type or tc.base_type == tc_name:
                extracted = self._extract_tc_syntax_from_mib(tc_name, module_name)
                if extracted:
                    tc.base_type = extracted

            self.logger.debug(
                f"Final TC: {tc.name} -> {tc.base_type}, hint={tc.display_hint}, desc_len={len(tc.description) if tc.description else 0}"
            )

            return tc

        except Exception as e:
            self.logger.error(f"Error extracting TC {tc_name}: {e}", exc_info=True)
            return None

    def _extract_tc_syntax_from_mib(self, tc_name: str, module_name: str) -> str:
        """Extract TC SYNTAX from MIB file directly - FIXED."""
        try:
            # Find the MIB file
            mib_file = None
            for search_path in self.resources.search_paths:
                for ext in ["", ".mib", ".txt", ".my"]:
                    test_path = search_path / f"{module_name}{ext}"
                    if test_path.exists():
                        mib_file = test_path
                        break
                if mib_file:
                    break

            if not mib_file:
                return ""

            # Read MIB file
            with open(mib_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # ✅ FIXED: Match SYNTAX that comes AFTER the DESCRIPTION ends
            # Pattern: TC_NAME ::= TEXTUAL-CONVENTION ... DESCRIPTION "..." ... SYNTAX Type
            pattern = (
                rf"{tc_name}\s+::=\s+TEXTUAL-CONVENTION\s+"  # TC definition start
                r"(?:.*?)"  # Any content
                r'DESCRIPTION\s+"(?:[^"]|"")*?"'  # DESCRIPTION with quoted text (skip it!)
                r"(?:.*?)"  # Any content after description
                r"SYNTAX\s+([A-Z][A-Za-z0-9]*)"  # SYNTAX keyword followed by type
            )

            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

            if match:
                syntax = match.group(1).strip()
                # ✅ Clean up - remove newlines and take only first word
                syntax = syntax.replace("\n", " ").replace("\r", "")
                syntax = syntax.split()[0] if syntax else ""

                # Map common variations
                syntax_map = {
                    "INTEGER": "Integer32",
                    "Integer": "Integer32",
                    "OCTET": "OctetString",
                    "OBJECT": "ObjectIdentifier",
                }

                return syntax_map.get(syntax, syntax) if syntax else ""

            # Fallback: Try simpler pattern without description
            pattern2 = rf"{tc_name}\s+::=\s+TEXTUAL-CONVENTION.*?SYNTAX\s+([A-Z][A-Za-z0-9]*)"
            match2 = re.search(pattern2, content, re.DOTALL)
            if match2:
                syntax = match2.group(1).strip()
                return syntax_map.get(syntax, syntax) if "syntax_map" in locals() else syntax

        except Exception as e:
            self.logger.debug(f"Error extracting TC syntax for {tc_name}: {e}")

        return ""

    def batch_resolve_notifications(self, objects: List[MibObject]) -> None:
        """Resolve all notification objects in single pass - ENHANCED."""
        start_time = time.time()

        all_notif_objects = set()
        notifications = []

        for obj in objects:
            if obj.node_type == "NotificationType" and obj.notification_objects:
                notifications.append(obj)
                all_notif_objects.update(obj.notification_objects)

        if not notifications:
            return

        self.logger.debug(
            f"Resolving {len(all_notif_objects)} notification objects for {len(notifications)} notifications..."
        )

        # Build lookup map from current objects
        local_objects = {obj.object_name: obj for obj in objects}

        # Load external objects ONCE for all
        external_objects = {}
        missing_objects = all_notif_objects - set(local_objects.keys())

        if missing_objects:
            self.logger.debug(f"Loading {len(missing_objects)} external objects...")
            external_objects = self._batch_load_external_objects(missing_objects)

        # Apply to all notifications
        for notif in notifications:
            resolved_details = {}
            for obj_name in notif.notification_objects:
                if obj_name in local_objects:
                    resolved_details[obj_name] = self._extract_object_detail(
                        local_objects[obj_name]
                    )
                elif obj_name in external_objects:
                    resolved_details[obj_name] = external_objects[obj_name]
                else:
                    resolved_details[obj_name] = self._empty_object_detail()

            notif.notification_objects_detail = {
                "object_count": len(notif.notification_objects),
                "objects": notif.notification_objects,
                "details": resolved_details,
            }

        elapsed = time.time() - start_time
        self.logger.debug(f"Resolved notifications in {elapsed:.2f}s")

    def _batch_load_external_objects(self, object_names: Set[str]) -> Dict:
        """Load multiple external objects in single pass."""
        results = {}

        # Check cache first
        uncached = set()
        with self.resources.resource_lock:
            for obj_name in object_names:
                if obj_name in self.resources.external_object_cache:
                    results[obj_name] = self.resources.external_object_cache[obj_name]
                else:
                    uncached.add(obj_name)

        if not uncached:
            return results

        # Search in all loaded modules
        for module_name in self.resources.mib_builder.mibSymbols:
            if not uncached:
                break

            module_symbols = self.resources.mib_builder.mibSymbols[module_name]
            found_in_module = []

            for obj_name in uncached:
                if obj_name in module_symbols:
                    detail = self._extract_from_symbol(module_symbols[obj_name], obj_name)
                    results[obj_name] = detail
                    with self.resources.resource_lock:
                        self.resources.external_object_cache[obj_name] = detail
                    found_in_module.append(obj_name)

            uncached -= set(found_in_module)

        # Cache negative results
        with self.resources.resource_lock:
            for obj_name in uncached:
                self.resources.external_object_cache[obj_name] = self._empty_object_detail()

        return results

    def _extract_from_symbol(self, mib_node, obj_name: str) -> Dict[str, Any]:
        """Extract details from a MIB symbol - ENHANCED with TC fields."""
        detail = {
            "oid": "",
            "node_type": type(mib_node).__name__,
            "syntax": "",
            "access": "",
            "status": "",
            "description": "",
            "base_syntax": "",
            # ✅ Add TC fields
            "tc_name": "",
            "tc_base_type": "",
            "tc_display_hint": "",
            "tc_status": "",
            "tc_description": "",
            "tc_constraints": "",
            "tc_resolution_chain": "",
            "enumerations": None,
        }

        try:
            if hasattr(mib_node, "getName"):
                detail["oid"] = ".".join(map(str, mib_node.getName()))

            if hasattr(mib_node, "getDescription"):
                desc = mib_node.getDescription()
                if desc:
                    detail["description"] = str(desc)

            if hasattr(mib_node, "getStatus"):
                detail["status"] = str(mib_node.getStatus())

            if hasattr(mib_node, "getMaxAccess"):
                detail["access"] = str(mib_node.getMaxAccess())

            if hasattr(mib_node, "getSyntax"):
                syntax_obj = mib_node.getSyntax()
                if syntax_obj:
                    syntax_name = syntax_obj.__class__.__name__
                    detail["syntax"] = syntax_name

                    # ✅ Resolve base syntax
                    for base_class in syntax_obj.__class__.__mro__:
                        base_name = base_class.__name__
                        if base_name in BASE_TYPES:
                            detail["base_syntax"] = base_name
                            break

                    if not detail["base_syntax"]:
                        detail["base_syntax"] = syntax_name

                    # ✅ Check if syntax is a TC and resolve it
                    if syntax_name not in BASE_TYPES:
                        tc = self._find_tc_in_loaded_modules(syntax_name)
                        if tc:
                            detail["tc_name"] = tc.name
                            detail["tc_base_type"] = tc.base_type
                            detail["tc_display_hint"] = tc.display_hint or ""
                            detail["tc_status"] = tc.status
                            detail["tc_description"] = tc.description
                            detail["tc_constraints"] = tc.constraints
                            detail["tc_resolution_chain"] = f"{tc.name}->{tc.base_type}"

                    # ✅ Extract enumerations
                    if hasattr(syntax_obj, "namedValues") and syntax_obj.namedValues:
                        detail["enumerations"] = dict(syntax_obj.namedValues)

        except Exception as e:
            self.logger.debug(f"Error extracting symbol {obj_name}: {e}")

        return detail

    def _extract_object_detail(self, obj: MibObject) -> Dict[str, Any]:
        """Extract detail from MibObject - ENHANCED."""
        return {
            "oid": obj.object_oid,
            "node_type": obj.node_type,
            "syntax": obj.syntax_type or "",
            "access": obj.access_level or "",
            "status": obj.status or "",
            "description": obj.description or "",
            "base_syntax": obj.base_syntax or obj.syntax_type or "",
            "tc_name": obj.tc_name or "",
            "tc_base_type": obj.tc_base_type or "",
            "tc_display_hint": obj.tc_display_hint or "",
            "tc_status": obj.tc_status or "",
            "tc_description": obj.tc_description or "",
            "tc_constraints": obj.tc_constraints or "",
            "tc_resolution_chain": obj.tc_resolution_chain or "",
            "enumerations": obj.enumerations,  # ✅ Include enumerations
        }

    def _empty_object_detail(self) -> Dict[str, Any]:
        """Return empty object detail."""
        return {
            "oid": "",
            "node_type": "",
            "syntax": "",
            "access": "",
            "status": "",
            "description": "",
            "base_syntax": "",
            "tc_name": "",
            "tc_base_type": "",
            "tc_display_hint": "",
            "tc_status": "",
            "tc_description": "",
            "tc_constraints": "",
            "tc_resolution_chain": "",
            "enumerations": None,
        }


# ============= OPTIMIZED MIB PARSER (SINGLE CLASS, WELL-ORGANIZED) =============


class MibParser:
    """
    Optimized MIB Parser with resource sharing and batch processing.

    Architecture: Single class with logical sections:
    - Initialization & Setup
    - Compilation & Dependencies
    - Parsing & Object Extraction
    - Enrichment (TCs, Parents, Notifications)
    - DataFrame Conversion
    - Progress Tracking
    - Async/Background Support
    """

    # ============================================
    # CLASS-LEVEL ATTRIBUTES (SHARED ACROSS INSTANCES)
    # ============================================

    # ✅ Thread-safe compilation lock (shared across all parser instances)
    _compilation_lock = threading.Lock()

    # ✅ Track active compilations to avoid duplicate work
    _active_compilations = set()  # Set of module names currently being compiled
    _active_compilations_lock = threading.Lock()  # Lock for the set itself

    # ============================================
    # SECTION 1: INITIALIZATION & SETUP
    # ============================================

    def __init__(self, config):
        """Initialize the optimized MIB parser."""
        self.config = config
        self.logger = get_logger(self.__class__.__name__)

        # Setup directories
        self.compiled_dir = Path(config.parser.compiled_dir)
        self.compiled_dir.mkdir(parents=True, exist_ok=True)

        # Mib Patterns
        # self.mib_patterns = config.parser.mib_patterns

        # ✅ Safety: Clean up stale compilations on init
        # (in case previous process crashed)
        if hasattr(self.__class__, "_active_compilations"):
            with self.__class__._active_compilations_lock:
                if self.__class__._active_compilations:
                    self.logger.debug("Clearing stale compilation markers from previous session")
                    self.__class__._active_compilations.clear()

        # Search paths
        self.search_paths = self._setup_search_paths()

        # Initialize shared resources (thread-safe singleton)
        self.resources = SharedMibResources()
        self.resources.initialize(self.compiled_dir, self.search_paths, self.logger)

        # Batch processor
        self.batch_processor = BatchProcessor(self.resources, self.logger)

        # Initialize cache
        self.cache = CacheManager(
            cache_dir=config.cache.directory,
            enabled=config.cache.enabled,
            config=config.cache  # ✅ Pass full config
        ) if config.cache.enabled else None

        # File content cache (shared across all operations)
        self.file_content_cache = {}

        # Statistics (✅ removed tier references)
        self.stats = {
            "files_processed": 0,
            "files_failed": 0,
            "corrupt_files_removed": 0,
            "objects_parsed": 0,
            "cache_hits": 0,
            "dependencies_compiled": 0,
            "total_time": 0,
            "last_dedup_count": 0,
            "total_records": 0,
            "failed_files": [],  # List of {filename, error}
            "missing_dependencies": [],  # List of missing MIB names
        }

        # Progress tracking
        self._progress_callback: Optional[Callable] = None

    def _setup_search_paths(self) -> List[Path]:
        """Setup MIB search paths."""
        paths = []

        # Add configured paths
        for path in self.config.parser.mib_search_dirs:
            p = Path(path)
            if p.exists():
                paths.append(p)

        # Add compiled directory
        paths.append(self.compiled_dir)

        return paths

    # ============================================
    # SECTION 2: PROGRESS TRACKING
    # ============================================

    def _emit_progress(
        self,
        phase: str,
        current: int,
        total: int,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Emit progress update with backward compatibility.

        Supports both old callback(current, total, message) and new ProgressUpdate.
        """
        if not self._progress_callback:
            return

        # ✅ FIXED: Match backend phase ranges
        phase_percentages = {
            "scanning": (2, 5),          # 2-5%
            "compiling": (5, 35),        # 5-15%
            "parsing": (35, 80),         # 15-70%
            "enriching": (80, 85),       # 70-80%
            "deduplicating": (85, 90),   # 80-90%
            "complete": (90, 90),        # 90%
        }

        if phase not in phase_percentages:
            phase = "parsing"  # Default fallback

        phase_start, phase_end = phase_percentages[phase]

        # Calculate progress within phase
        if total > 0:
            phase_progress = (current / total) * (phase_end - phase_start)
        else:
            phase_progress = 0

        overall_percentage = phase_start + phase_progress
        overall_percentage = min(overall_percentage, 90.0)  # ✅ FIXED: Cap at 90% (backend handles 90-100)

        # Create structured progress update
        progress = ProgressUpdate(
            phase=phase,
            current=current,
            total=total,
            message=message,
            percentage=overall_percentage,
            metadata=metadata or {},
        )

        try:
            # Try new signature first (ProgressUpdate object)
            self._progress_callback(progress)
        except TypeError:
            # Fallback to old signature (current, total, message)
            try:
                self._progress_callback(current, total, message)
            except Exception as e:
                self.logger.debug(f"Progress callback error: {e}")

    # ============================================
    # SECTION 3: PUBLIC API - DIRECTORY PARSING
    # ============================================

    def parse_directory(
        self,
        dir_path: str,
        pattern: str = "*.mib",
        recursive: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> pd.DataFrame:
        """
        Parse all MIB files in a directory with progress tracking.
        
        Args:
            dir_path: Directory containing MIB files
            pattern: File pattern to match (default: *.mib)
            recursive: Search subdirectories
            progress_callback: Callback for progress updates
                              Supports both (current, total, message) and ProgressUpdate
        
        Returns:
            DataFrame with parsed MIB objects
        """
        # Store callback
        self._progress_callback = progress_callback
        
        # Reset stats
        self.stats["files_processed"] = 0
        self.stats["files_failed"] = 0
        self.stats["last_dedup_count"] = 0
        self.stats["total_records"] = 0
        
        dir_path = Path(dir_path).absolute()
        if not dir_path.exists():
            self.logger.error(f"Directory not found: {dir_path}")
            return pd.DataFrame()
        
        # PHASE 1: Scanning
        self._emit_progress("scanning", 0, 100, "Scanning directory for MIB files...")
        
        if recursive:
            mib_files = list(dir_path.rglob(pattern))
        else:
            mib_files = list(dir_path.glob(pattern))
            if not mib_files:
                mib_files = list(dir_path.glob("*.my"))
            if not mib_files:
                mib_files = list(dir_path.glob("*.txt"))
        
        if not mib_files:
            self.logger.warning(f"No MIB files found matching {pattern} in {dir_path}")
            return pd.DataFrame()
        
        total_files = len(mib_files)
        self._emit_progress(
            "scanning", total_files, total_files, f"Found {total_files} MIB file(s)"
        )
        self.logger.info(f"Found {total_files} MIB files to process")
        
        # PHASE 2: Build dependency graph
        self._emit_progress(
            "compiling", 0, total_files, f"Analyzing dependencies for {total_files} files..."
        )
        self.logger.info(f"Phase 1: Analyzing dependencies for {total_files} files...")
        
        dep_graph = self._build_dependency_graph(mib_files)
        
        # PHASE 3: Compile in dependency order
        self._emit_progress("compiling", 0, total_files, "Compiling MIBs in dependency order...")
        self.logger.info("Phase 2: Compiling MIBs in dependency order...")
        
        compilation_order = self._topological_sort(dep_graph)
        self._compile_in_order(compilation_order, mib_files)
        
        # PHASE 4: Parse all files
        self._emit_progress("parsing", 0, total_files, f"Parsing {total_files} file(s)...")
        self.logger.info(f"Phase 3: Parsing {total_files} files...")
        
        all_dfs = []
        failed_files = []
        
        for idx, mib_file in enumerate(mib_files, 1):
            self.logger.debug(f"[{idx}/{total_files}] Parsing {mib_file.name}")
            
            # Emit per-file progress
            self._emit_progress(
                "parsing",
                idx - 1,
                total_files,
                f"Parsing {mib_file.name} ({idx}/{total_files})...",
                metadata={"file_name": mib_file.name, "file_index": idx},
            )
            
            try:
                df = self.parse_file(str(mib_file), skip_dedup=True)
                if not df.empty:
                    all_dfs.append(df)
                    self.logger.debug(f"✓ {mib_file.name} ({len(df)} records)")
                    
                    # Update progress with success
                    self._emit_progress(
                        "parsing",
                        idx,
                        total_files,
                        f"✓ {mib_file.name} ({len(df)} records)",
                        metadata={
                            "file_name": mib_file.name,
                            "records": len(df),
                            "status": "success",
                        },
                    )
                else:
                    failed_files.append(mib_file.name)
                    self.logger.warning(f"⚠ {mib_file.name} (no records)")
                    
                    self._emit_progress(
                        "parsing",
                        idx,
                        total_files,
                        f"⚠ {mib_file.name} (no records)",
                        metadata={"file_name": mib_file.name, "status": "empty"},
                    )
            except Exception as e:
                failed_files.append(mib_file.name)
                self.logger.error(f"✗ {mib_file.name}: {e}")
                
                # Track failed file with error
                self.stats["failed_files"].append({
                    "filename": mib_file.name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                })
                
                self._emit_progress(
                    "parsing",
                    idx,
                    total_files,
                    f"✗ {mib_file.name} (failed: {str(e)[:50]})",
                    metadata={"file_name": mib_file.name, "status": "failed", "error": str(e)},
                )
        
        # PHASE 5: Summary
        self.logger.info("=" * 50)
        self.logger.info("Processing Complete:")
        self.logger.info(f"  Successful: {len(all_dfs)}/{total_files}")
        self.logger.info(f"  Failed: {len(failed_files)}")
        if self.resources.stats["modules_loaded"] > 0:
            self.logger.info(f"  Modules loaded: {self.resources.stats['modules_loaded']}")
            self.logger.info(f"  Cache hits: {self.resources.stats['cache_hits']}")
            self.logger.info(f"  Cache misses: {self.resources.stats['cache_misses']}")
        
        # Combine results
        if all_dfs:
            self._emit_progress("deduplicating", 0, 1, "Combining results...")
            combined_df = pd.concat(all_dfs, ignore_index=True)
            total_records = len(combined_df)
            
            self.logger.info(f"✅ Total records parsed: {total_records}")
            
            # Apply deduplication
            if not combined_df.empty and self.config.parser.deduplication_enabled:
                self._emit_progress(
                    "deduplicating", 0, 1, f"Removing duplicates from {total_records} records..."
                )
                combined_df = self._apply_deduplication(combined_df, "directory:combined")
            
            self.stats["total_records"] = len(combined_df)
            
            # Final progress update (90% - backend handles 90-100%)
            self._emit_progress(
                "deduplicating",
                1,
                1,
                f"Parsing complete: {self.stats['total_records']} records from {self.stats['files_processed']} files",
                metadata={
                    "total_records": self.stats["total_records"],
                    "files_processed": self.stats["files_processed"],
                    "files_failed": self.stats["files_failed"],
                },
            )
            return combined_df
        else:
            self.logger.warning("No data parsed from any files")
            self._emit_progress(
                "deduplicating", 0, 1, "⚠ No data parsed from any files"
            )
            return pd.DataFrame()
    

    # ============================================
    # SECTION 4: PUBLIC API - FILE PARSING
    # ============================================

    def parse_file(
        self, file_path: str, force_compile: bool = False, skip_dedup: bool = False
    ) -> pd.DataFrame:
        """
        Parse single MIB file with optimized flow.

        Args:
            file_path: Path to MIB file
            force_compile: Force recompilation even if cached
            skip_dedup: Skip deduplication (used in directory parsing)

        Returns:
            DataFrame with parsed MIB objects
        """
        start_time = time.time()

        file_path = Path(file_path).absolute()

        if not file_path.exists():
            self.logger.error(f"MIB file not found: {file_path}")
            self.stats["files_failed"] += 1
            return pd.DataFrame()

        module_name = self._extract_module_name(file_path)
        self.logger.info(f"Parsing {module_name} from {file_path.name}")

        # Override force compile from config file
        force_compile = self.config.parser.force_compile
        
        # Check cache
        if not force_compile and self.cache:
            cached = self.cache.get(str(file_path))
            if cached is not None:
                self.stats["cache_hits"] += 1
                self.logger.info(f"Using cached data for {module_name}")
                return cached

        try:
            # STEP 1: Ensure compiled (with dependencies)
            compiled_path = self._ensure_compiled(file_path, module_name, force_compile)
            if not compiled_path:
                raise Exception(f"Failed to compile {module_name}")

            # STEP 2: Parse all objects at once
            objects = self._parse_all_objects(compiled_path, module_name)
            if not objects:
                raise Exception(f"No objects extracted from {module_name}")

            # STEP 3: Batch enrichment (single pass for each type)
            self._batch_enrich_objects(objects, file_path)

            # STEP 4: Convert to DataFrame
            df = self._objects_to_expanded_df(objects, file_path)

            # STEP 5: Deduplication if single file
            if not df.empty and not skip_dedup and self.config.parser.deduplication_enabled:
                df = self._apply_deduplication(df, f"file:{file_path.name}")

            # STEP 6: Cache result
            if self.cache and not df.empty:
                self.cache.cache(
                    str(file_path),
                    df,
                    {"module_name": module_name, "object_count": len(objects), "enriched": True},
                )

            # Update statistics
            self.stats["files_processed"] += 1
            self.stats["objects_parsed"] += len(objects)

            elapsed = time.time() - start_time
            self.stats["total_time"] += elapsed
            self.logger.info(
                f"Successfully parsed {module_name}: {len(objects)} objects in {elapsed:.2f}s"
            )

            return df

        except Exception as e:
            self.logger.error(f"Failed to parse {module_name}: {e}")

            # ✅ NEW: Track failed file with error
            self.stats["failed_files"].append({
                "filename": file_path.name,
                "error": str(e),
                "error_type": type(e).__name__,
                "module_name": module_name
            })

            self.stats["files_failed"] += 1
            return pd.DataFrame()

    # ============================================
    # SECTION 5: COMPILATION & DEPENDENCIES
    # ============================================

    def _ensure_compiled(
        self, file_path: Path, module_name: str, force: bool = False
    ) -> Optional[Path]:
        """Ensure MIB is compiled with dependencies."""
        compiled_path = self.compiled_dir / f"{module_name}.py"
        compiled_path_alt = self.compiled_dir / f"{module_name.replace('-', '_')}.py"

        # Check if already compiled
        if not force:
            for path in [compiled_path, compiled_path_alt]:
                if path.exists():
                    if self._validate_compiled_file(path, module_name):
                        return path
                    else:
                        self.logger.warning(f"Removing corrupt compiled file: {path}")
                        path.unlink()
                        self.stats["corrupt_files_removed"] += 1

        # Extract dependencies
        dependencies = self._extract_all_dependencies(file_path)

        # Batch compile dependencies
        if dependencies:
            self._batch_compile_dependencies(dependencies, file_path.parent)

        # Compile main MIB
        return self._compile_mib(file_path, module_name)

    def _validate_compiled_file(self, compiled_path: Path, module_name: str) -> bool:
        """
        Validate that a compiled MIB file is loadable and not corrupted.

        Performs basic validation without being overly strict:
        1. File exists and has reasonable size
        2. File is valid Python syntax
        3. File contains pysnmp-related content

        Args:
            compiled_path: Path to compiled .py file
            module_name: Expected module name

        Returns:
            True if file is valid, False otherwise
        """
        if not compiled_path.exists():
            return False

        try:
            # Check 1: File size (must be at least 50 bytes)
            file_size = compiled_path.stat().st_size
            if file_size < 50:
                self.logger.debug(
                    f"Compiled file {compiled_path.name} too small ({file_size} bytes)"
                )
                return False

            # Check 2: File is valid Python and contains pysnmp content
            try:
                with open(compiled_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                # Must contain pysnmp imports (anywhere in file, not just first 1KB)
                if "pysnmp" not in content.lower() and "pyasn1" not in content.lower():
                    self.logger.debug(
                        f"Compiled file {compiled_path.name} missing pysnmp/pyasn1 imports"
                    )
                    return False

                # Basic Python syntax check - try to compile it
                compile(content, str(compiled_path), "exec")

            except SyntaxError as e:
                self.logger.debug(f"Compiled file {compiled_path.name} has syntax errors: {e}")
                return False
            except Exception as e:
                # If we can't read or compile, but file exists and has size, it might still be valid
                # Don't be too strict here
                self.logger.debug(f"Could not fully validate {compiled_path.name}: {e}")
                # If file is large enough, assume it's valid
                if file_size > 500:
                    return True
                return False

            # All checks passed
            return True

        except Exception as e:
            self.logger.debug(f"Validation failed for {compiled_path.name}: {e}")
            return False

    def _cleanup_stale_compilations(self):
        """
        Clean up stale compilation markers.

        Call this if you suspect a thread crashed during compilation.
        """
        with self._active_compilations_lock:
            if self._active_compilations:
                self.logger.warning(
                    f"Clearing {len(self._active_compilations)} stale compilation markers"
                )
                self._active_compilations.clear()

    def _extract_all_dependencies(self, file_path: Path) -> List[str]:
        """Extract all dependencies from MIB file."""
        try:
            # Use cached content if available
            if str(file_path) in self.file_content_cache:
                content = self.file_content_cache[str(file_path)]
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    self.file_content_cache[str(file_path)] = content

            # Find IMPORTS section
            imports_match = re.search(r"IMPORTS\s+(.*?);", content, re.DOTALL)
            if not imports_match:
                return []

            imports_text = imports_match.group(1)
            from_clauses = re.findall(r"FROM\s+([A-Za-z][\w-]*)", imports_text)

            # Filter out stub MIBs
            dependencies = [d for d in from_clauses if d not in STUB_MIBS]

            return dependencies

        except Exception as e:
            self.logger.debug(f"Error extracting dependencies: {e}")
            return []

    def _batch_compile_dependencies(self, dependencies: List[str], search_dir: Path):
        """
        Compile all dependencies in single compiler session - THREAD-SAFE.

        Note: This method is already thread-safe because it calls _compile_mib()
        which has its own locking. However, we optimize by checking all at once.
        """
        # Filter out already compiled
        deps_to_compile = []
        for dep in dependencies:
            compiled = False
            for pattern in [f"{dep}.py", f"{dep.replace('-', '_')}.py"]:
                compiled_path = self.compiled_dir / pattern
                if compiled_path.exists() and self._validate_compiled_file(compiled_path, dep):
                    compiled = True
                    break
            if not compiled:
                deps_to_compile.append(dep)

        if not deps_to_compile:
            return

        self.logger.info(f"Compiling {len(deps_to_compile)} dependencies...")

        # ============================================
        # OPTION A: Sequential compilation (SAFE, SIMPLE)
        # ============================================
        # Compile dependencies one by one using thread-safe _compile_mib()
        compiled_count = 0
        failed_deps = []

        for dep in deps_to_compile:
            # Find the dependency file
            dep_file = None
            for search_path in [search_dir] + self.search_paths:
                for ext in ["", ".mib", ".txt", ".my"]:
                    test_path = search_path / f"{dep}{ext}"
                    if test_path.exists():
                        dep_file = test_path
                        break
                if dep_file:
                    break

            if dep_file:
                result = self._compile_mib(dep_file, dep)
                if result:
                    compiled_count += 1
                else:
                    failed_deps.append(dep)
            else:
                self.logger.debug(f"Dependency {dep} not found in search paths")
                failed_deps.append(dep)

        self.stats["dependencies_compiled"] += compiled_count

        if compiled_count > 0:
            self.logger.info(f"Compiled {compiled_count} dependencies successfully")
        if failed_deps:
            self.logger.warning(
                f"Failed to compile {len(failed_deps)} dependencies: {failed_deps[:5]}"
            )

    def _compile_mib(self, file_path: Path, module_name: str) -> Optional[Path]:
        """
        Compile a single MIB file - THREAD-SAFE.

        Uses double-check locking pattern:
        1. Check if already compiled (fast path, no lock)
        2. If not, acquire lock
        3. Check again (another thread might have compiled while waiting)
        4. Compile if still needed
        5. Release lock

        Args:
            file_path: Path to source MIB file
            module_name: Module name to compile

        Returns:
            Path to compiled .py file, or None if compilation failed
        """

        # ============================================
        # FAST PATH: Check if already compiled (no lock needed)
        # ============================================
        compiled_path = self.compiled_dir / f"{module_name}.py"
        compiled_path_alt = self.compiled_dir / f"{module_name.replace('-', '_')}.py"

        # Quick check without lock
        for path in [compiled_path, compiled_path_alt]:
            if path.exists() and self._validate_compiled_file(path, module_name):
                self.logger.debug(f"Using existing compiled MIB: {path.name}")
                return path

        # ============================================
        # SLOW PATH: Need to compile - acquire lock
        # ============================================

        # Check if another thread is already compiling this module
        with self._active_compilations_lock:
            if module_name in self._active_compilations:
                self.logger.debug(f"Another thread is compiling {module_name}, waiting...")

        # Acquire main compilation lock
        with self._compilation_lock:
            # ============================================
            # DOUBLE-CHECK: Verify still needs compilation
            # ============================================
            # Another thread might have compiled while we waited for lock
            for path in [compiled_path, compiled_path_alt]:
                if path.exists() and self._validate_compiled_file(path, module_name):
                    self.logger.debug(f"Module {module_name} was compiled by another thread")
                    return path

            # ============================================
            # MARK AS ACTIVE COMPILATION
            # ============================================
            with self._active_compilations_lock:
                self._active_compilations.add(module_name)

            try:
                # ============================================
                # PERFORM COMPILATION
                # ============================================
                self.logger.info(f"Compiling {module_name}...")

                parser = parserFactory()()
                codegen = PySnmpCodeGen()
                codegen.genTexts = True  # Generate texts for main MIB
                writer = PyFileWriter(str(self.compiled_dir))

                compiler = MibCompiler(parser, codegen, writer)

                # Add sources
                mib_dir = file_path.parent
                compiler.add_sources(FileReader(str(mib_dir)))
                for path in self.search_paths:
                    if path.exists():
                        compiler.add_sources(FileReader(str(path)))

                # Add searchers
                searchers = [AnyFileSearcher(str(self.compiled_dir))]
                for path in self.search_paths:
                    if path.exists():
                        searchers.append(AnyFileSearcher(str(path)))
                compiler.add_searchers(*searchers)
                compiler.add_searchers(StubSearcher(*STUB_MIBS))

                # Compile and track missing dependencies
                try:
                    results = compiler.compile(module_name, ignoreErrors=True)
                    
                    # ✅ NEW: Check for missing dependencies in compilation results
                    if results:
                        for mib_name, status in results.items():
                            if status == 'missing':
                                if mib_name not in self.stats["missing_dependencies"]:
                                    self.stats["missing_dependencies"].append(mib_name)
                                    self.logger.warning(f"Missing dependency: {mib_name}")
                except Exception as compile_error:
                    self.logger.error(f"Compilation error for {module_name}: {compile_error}")

                # ============================================
                # VERIFY COMPILATION SUCCESS
                # ============================================
                # Check if compilation produced a valid file
                for path in [compiled_path, compiled_path_alt]:
                    if path.exists():
                        # Validate the compiled file
                        if self._validate_compiled_file(path, module_name):
                            self.logger.info(f"Successfully compiled {module_name} -> {path.name}")
                            return path
                        else:
                            # Compiled file is invalid, remove it
                            self.logger.warning(f"Compiled file {path.name} is invalid, removing")
                            try:
                                path.unlink()
                            except Exception as e:
                                self.logger.debug(f"Failed to remove invalid file: {e}")

                # Compilation failed
                self.logger.error(f"Compilation of {module_name} produced no valid output")
                return None

            except Exception as e:
                self.logger.error(f"Failed to compile {module_name}: {e}")
                return None

            finally:
                # ============================================
                # CLEANUP: Remove from active compilations
                # ============================================
                with self._active_compilations_lock:
                    self._active_compilations.discard(module_name)

    def _build_dependency_graph(self, mib_files: List[Path]) -> Dict[str, List[str]]:
        """Build dependency graph for all MIB files."""
        dep_graph = {}

        for mib_file in mib_files:
            module_name = self._extract_module_name(mib_file)
            dependencies = self._extract_all_dependencies(mib_file)
            dep_graph[module_name] = dependencies

        return dep_graph

    def _topological_sort(self, dep_graph: Dict[str, List[str]]) -> List[str]:
        """Perform topological sort on dependency graph."""
        in_degree = defaultdict(int)
        for module in dep_graph:
            if module not in in_degree:
                in_degree[module] = 0
            for dep in dep_graph[module]:
                if dep in dep_graph:
                    in_degree[dep] += 1

        queue = deque([module for module in dep_graph if in_degree[module] == 0])
        result = []

        while queue:
            module = queue.popleft()
            result.append(module)

            for dep in dep_graph.get(module, []):
                if dep in in_degree:
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        queue.append(dep)

        # Add remaining modules (cycles)
        for module in dep_graph:
            if module not in result:
                result.append(module)
                # ✅ Log circular dependencies
                self.logger.warning(f"Circular dependency detected involving: {module}")

        return result

    def _compile_in_order(self, compilation_order: List[str], mib_files: List[Path]):
        """Compile MIBs in dependency order with progress."""
        module_to_file = {}
        for mib_file in mib_files:
            module_name = self._extract_module_name(mib_file)
            module_to_file[module_name] = mib_file
        
        need_compilation = []
        for module_name in compilation_order:
            if module_name not in module_to_file:
                continue
            
            compiled_path = self.compiled_dir / f"{module_name}.py"
            compiled_path_alt = self.compiled_dir / f"{module_name.replace('-', '_')}.py"
            
            if not compiled_path.exists() and not compiled_path_alt.exists():
                need_compilation.append(module_name)
            elif self.config.parser.force_compile:
                need_compilation.append(module_name)
        
        if not need_compilation:
            self.logger.info("All MIBs already compiled!")
            return
        
        self.logger.info(f"Need to compile {len(need_compilation)} MIBs")
        
        compiled_count = 0
        failed_modules = []
        total = len(need_compilation)
        
        for idx, module_name in enumerate(need_compilation, 1):
            # Emit compilation progress
            self._emit_progress(
                "compiling",
                idx,
                total,
                f"Compiling {module_name} ({idx}/{total})...",
                metadata={"module_name": module_name},
            )
            
            # Log every 10 modules or first/last
            if idx == 1 or idx % 10 == 0 or idx == total:
                percent = (idx / total) * 100
                self.logger.info(f"Progress: {idx}/{total} ({percent:.1f}%) - Compiling {module_name[:30]}...")
            
            mib_file = module_to_file[module_name]
            try:
                result = self._compile_mib(mib_file, module_name)
                if result:
                    compiled_count += 1
                else:
                    failed_modules.append(module_name)
            except Exception as e:
                self.logger.debug(f"Failed to compile {module_name}: {e}")
                failed_modules.append(module_name)
        
        self.logger.info(f"✓ Compiled {compiled_count} MIBs successfully")
        if failed_modules:
            self.logger.warning(f"✗ Failed to compile {len(failed_modules)} MIBs")


    # ============================================
    # SECTION 6: PARSING & OBJECT EXTRACTION
    # ============================================

    def _parse_all_objects(self, compiled_path: Path, module_name: str) -> List[MibObject]:
        """Parse all objects from compiled MIB in single pass."""
        objects = []

        try:
            # Get module symbols from shared resources
            module_symbols = self.resources.get_module_symbols(module_name)

            for sym_name, mib_node in module_symbols.items():
                obj = self._create_mib_object(sym_name, mib_node, module_name)
                if obj:
                    objects.append(obj)
                    # Add to global indices
                    with self.resources.resource_lock:
                        self.resources.all_objects[sym_name] = obj
                        if obj.object_oid:
                            self.resources.oid_to_object[obj.object_oid] = obj
                        self.resources.module_objects[module_name].append(obj)

            self.logger.debug(f"Extracted {len(objects)} objects from {module_name}")

        except Exception as e:
            self.logger.error(f"Error parsing compiled MIB: {e}")

        return objects

    def _create_mib_object(
        self, sym_name: str, mib_node: Any, module_name: str
    ) -> Optional[MibObject]:
        """Create MibObject from pysnmp node."""
        try:
            # Determine node type
            node_type = self._determine_node_type(mib_node)

            # Skip certain types
            if node_type in ["MibScalarInstance"]:
                return None

            # Create object
            obj = MibObject(
                module_name=module_name,
                object_name=sym_name,
                node_type=node_type,
                processed_at=datetime.now(),
            )

            # Extract OID
            if hasattr(mib_node, "getName"):
                try:
                    oid_tuple = mib_node.getName()
                    if oid_tuple:  # ✅ Check for None
                        obj.object_oid = ".".join(map(str, oid_tuple))
                except Exception as e:
                    self.logger.debug(f"Failed to extract OID for {sym_name}: {e}")

            # Extract attributes
            self._extract_attributes(obj, mib_node)

            return obj

        except Exception as e:
            self.logger.debug(f"Error creating MibObject for {sym_name}: {e}")
            return None

    def _determine_node_type(self, mib_node) -> str:
        """Determine the node type of a MIB object."""
        class_name = type(mib_node).__name__

        # Direct mapping
        type_map = {
            "MibScalar": "MibScalar",
            "MibScalarInstance": "MibScalarInstance",
            "MibTable": "MibTable",
            "MibTableRow": "MibTableRow",
            "MibTableColumn": "MibTableColumn",
            "NotificationType": "NotificationType",
            "MibIdentifier": "MibIdentifier",
            "ObjectGroup": "ObjectGroup",
            "NotificationGroup": "NotificationGroup",
            "ModuleCompliance": "ModuleCompliance",
            "AgentCapabilities": "AgentCapabilities",
            "ObjectIdentity": "ObjectIdentity",
            "ModuleIdentity": "ModuleIdentity",
        }

        if class_name in type_map:
            return type_map[class_name]

        # Check for TextualConvention
        if "TextualConvention" in class_name or hasattr(mib_node, "getDisplayHint"):
            if hasattr(mib_node, "getStatus") and not hasattr(mib_node, "getMaxAccess"):
                return "TextualConvention"

        # Check by attributes
        if hasattr(mib_node, "getMaxAccess"):
            if hasattr(mib_node, "getIndexNames"):
                return "MibTableRow"
            return "MibScalar"

        if hasattr(mib_node, "getObjects"):
            return "NotificationType"

        return "MibObject"

    def _extract_attributes(self, obj: MibObject, mib_node):
        """Extract attributes from MIB node - ENHANCED."""

        # Status - with proper error handling for unbound methods
        if hasattr(mib_node, "getStatus"):
            try:
                get_status = getattr(mib_node, "getStatus")
                # Check if it's a bound method (has __self__)
                if hasattr(get_status, "__self__"):
                    obj.status = str(get_status())
                else:
                    # It's an unbound method (class method), try calling anyway
                    try:
                        obj.status = str(get_status())
                    except TypeError:
                        # Requires 'self', skip
                        pass
            except Exception as e:
                self.logger.debug(f"Failed to extract status for {obj.object_name}: {e}")

        # Description - with proper error handling
        if hasattr(mib_node, "getDescription"):
            try:
                get_desc = getattr(mib_node, "getDescription")
                if hasattr(get_desc, "__self__"):
                    # It's a bound method (instance)
                    desc = get_desc()
                    if desc:
                        obj.description = str(desc)
                else:
                    # It's an unbound method (class) - try calling anyway
                    try:
                        desc = get_desc()
                        if desc:
                            obj.description = str(desc)
                    except TypeError:
                        # Requires 'self', skip
                        pass
            except Exception as e:
                self.logger.debug(f"Failed to extract description for {obj.object_name}: {e}")

        # Access level
        if hasattr(mib_node, "getMaxAccess"):
            try:
                obj.access_level = str(mib_node.getMaxAccess())
            except Exception as e:
                self.logger.debug(f"Failed to extract access level for {obj.object_name}: {e}")

        # Syntax and related fields
        if hasattr(mib_node, "getSyntax"):
            try:
                syntax_obj = mib_node.getSyntax()
                if syntax_obj is not None:
                    obj.syntax_type = syntax_obj.__class__.__name__

                    # ✅ Extract base syntax by walking class hierarchy
                    obj.base_syntax = self._resolve_base_syntax(syntax_obj)

                    # Get constraints
                    if hasattr(syntax_obj, "subtypeSpec") and syntax_obj.subtypeSpec:
                        obj.value_range = str(syntax_obj.subtypeSpec)

                    # ✅ Get enumerations (for INTEGER with named values)
                    if hasattr(syntax_obj, "namedValues") and syntax_obj.namedValues:
                        obj.enumerations = dict(syntax_obj.namedValues)
            except Exception as e:
                self.logger.debug(f"Failed to extract syntax for {obj.object_name}: {e}")

        # Units
        if hasattr(mib_node, "getUnits"):
            try:
                units = mib_node.getUnits()
                if units:
                    obj.units = str(units)
            except Exception as e:
                self.logger.debug(f"Failed to extract units for {obj.object_name}: {e}")

        # Reference - with proper error handling
        if hasattr(mib_node, "getReference"):
            try:
                get_ref = getattr(mib_node, "getReference")
                if hasattr(get_ref, "__self__"):
                    ref = get_ref()
                    if ref:
                        obj.reference = str(ref)
                else:
                    try:
                        ref = get_ref()
                        if ref:
                            obj.reference = str(ref)
                    except TypeError:
                        pass
            except Exception as e:
                self.logger.debug(f"Failed to extract reference for {obj.object_name}: {e}")

        # Display hint - with proper error handling
        if hasattr(mib_node, "getDisplayHint"):
            try:
                get_hint = getattr(mib_node, "getDisplayHint")
                if hasattr(get_hint, "__self__"):
                    hint = get_hint()
                    if hint:
                        obj.display_hint = str(hint)
                else:
                    try:
                        hint = get_hint()
                        if hint:
                            obj.display_hint = str(hint)
                    except TypeError:
                        pass
            except Exception as e:
                self.logger.debug(f"Failed to extract display hint for {obj.object_name}: {e}")

        # ✅ Default value (NEW)
        if hasattr(mib_node, "getDefaultValue"):
            try:
                default = mib_node.getDefaultValue()
                if default is not None:
                    obj.default_value = str(default)
            except Exception as e:
                self.logger.debug(f"Failed to extract default value for {obj.object_name}: {e}")

        # ✅ Table indexes (NEW)
        if hasattr(mib_node, "getIndexNames"):
            try:
                indexes = mib_node.getIndexNames()
                if indexes:
                    # self.logger.debug(f"Extracting indexes for {obj.object_name}: {indexes}")
                    obj.table_indexes = self._format_indexes(indexes)
                    # self.logger.debug(f"Formatted indexes: {obj.table_indexes}")
            except Exception as e:
                self.logger.debug(f"Failed to extract indexes for {obj.object_name}: {e}")

        # ✅ Augments table (NEW)
        if hasattr(mib_node, "getAugmention"):
            try:
                augments = mib_node.getAugmention()
                if augments:
                    obj.augments_table = str(augments)
            except Exception as e:
                self.logger.debug(f"Failed to extract augments for {obj.object_name}: {e}")

        # Notification objects
        if obj.node_type == "NotificationType":
            if hasattr(mib_node, "getObjects"):
                try:
                    notif_objects = mib_node.getObjects()
                    if notif_objects:
                        obj.notification_objects = []
                        for notif_obj in notif_objects:
                            if isinstance(notif_obj, tuple) and len(notif_obj) >= 2:
                                obj.notification_objects.append(str(notif_obj[-1]))
                            else:
                                obj.notification_objects.append(str(notif_obj))
                except Exception as e:
                    self.logger.debug(
                        f"Failed to extract notification objects for {obj.object_name}: {e}"
                    )

            # ✅ Extract notification enterprise OID (NEW)
            if obj.object_oid:
                obj.notification_enterprise = self._extract_enterprise_oid(obj.object_oid)

    def _resolve_base_syntax(self, syntax_obj) -> str:
        """
        Resolve base syntax by walking class hierarchy.
        Returns the first base type found in BASE_TYPES.
        """
        try:
            # Walk the MRO (Method Resolution Order) to find base type
            for base_class in syntax_obj.__class__.__mro__:
                base_name = base_class.__name__
                if base_name in BASE_TYPES:
                    return base_name

            # If not found, return the class name itself
            return syntax_obj.__class__.__name__
        except Exception as e:
            self.logger.debug(f"Failed to resolve base syntax: {e}")
            return ""

    def _format_indexes(self, indexes) -> str:
        """
        Format table indexes into readable string - FIXED.

        Args:
            indexes: Index tuple from getIndexNames()o
            Format: ((implied_flag, module_name, object_name), ...)

        Returns:
            Formatted string like "ifIndex" or "ifStackHigherLayer,ifStackLowerLayer"
        """
        try:
            index_names = []

            for idx in indexes:
                if isinstance(idx, tuple):
                    # ✅ FIX: Structure is (implied, module, object) - 3 elements!
                    if len(idx) >= 3:
                        implied = idx[0]
                        # module_name = idx[1]
                        obj_name = idx[2]  # ✅ Third element is the object name!

                        if implied:
                            obj_name = f"IMPLIED {obj_name}"

                        index_names.append(obj_name)
                    elif len(idx) == 2:
                        # Fallback for 2-element tuples
                        implied = idx[0]
                        obj_name = idx[1]
                        if implied:
                            obj_name = f"IMPLIED {obj_name}"
                        index_names.append(obj_name)
                    else:
                        # Single element or unknown
                        index_names.append(str(idx))
                else:
                    # Not a tuple
                    index_names.append(str(idx))

            return ",".join(index_names) if index_names else ""

        except Exception as e:
            self.logger.error(f"Failed to format indexes: {e}", exc_info=True)
            return str(indexes)

    def _extract_enterprise_oid(self, notification_oid: str) -> Optional[str]:
        """
        Extract enterprise OID from notification OID.

        For SNMPv2 traps: enterprise is typically the parent OID
        For SNMPv1 traps: enterprise is in the trap definition

        Args:
            notification_oid: Full notification OID

        Returns:
            Enterprise OID or None
        """
        try:
            # For SNMPv2 traps under snmpTraps (1.3.6.1.6.3.1.1.5)
            if notification_oid.startswith("1.3.6.1.6.3.1.1.5"):
                # Standard SNMP trap, no specific enterprise
                return None

            # For vendor-specific traps, enterprise is typically parent OID
            parts = notification_oid.split(".")
            if len(parts) > 1:
                # Return parent OID (all but last component)
                return ".".join(parts[:-1])

            return None
        except Exception as e:
            self.logger.debug(f"Failed to extract enterprise OID: {e}")
            return None

    # ============================================
    # SECTION 7: ENRICHMENT METHODS
    # ============================================

    def _batch_enrich_objects(self, objects: List[MibObject], file_path: Path):
        """Enrich all objects in organized batches."""
        self.logger.debug(f"Enriching {len(objects)} objects...")

        # 1. Extract descriptions from source (single file read)
        self._batch_extract_descriptions(objects, file_path)

        # 2. Extract module metadata
        self._extract_module_metadata(objects, file_path)

        # 3. Resolve parents (single pass)
        self._batch_resolve_parents(objects)

        # 4. Resolve TCs (single pass)
        self.batch_processor.batch_resolve_tcs(objects)

        # 5. Resolve notifications (single pass)
        self.batch_processor.batch_resolve_notifications(objects)

        # ✅ 6. Enrich notification objects with source descriptions
        for obj in objects:
            if obj.node_type == "NotificationType" and obj.notification_objects:
                self._enrich_notification_objects_from_source(obj, file_path)

    def _batch_extract_descriptions(self, objects: List[MibObject], file_path: Path):
        """Extract all descriptions in single file read - FIXED."""
        # Get cached content
        if str(file_path) in self.file_content_cache:
            content = self.file_content_cache[str(file_path)]
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                self.file_content_cache[str(file_path)] = content

        # ✅ FIXED: Regex that handles both OBJECT-TYPE and NOTIFICATION-TYPE
        # Pattern: name (OBJECT-TYPE|NOTIFICATION-TYPE) ... DESCRIPTION "..." <STOP>
        desc_pattern = re.compile(
            r"(\w+)\s+"  # Object/notification name
            r"(?:OBJECT-TYPE|NOTIFICATION-TYPE|OBJECT-IDENTITY|MODULE-IDENTITY)\s+"  # Type
            r"(?:.*?)"  # Any content before DESCRIPTION
            r"DESCRIPTION\s+"  # DESCRIPTION keyword
            r'"((?:[^"]|"")*?)"'  # Capture description (handle escaped quotes)
            r"\s*"  # Optional whitespace
            r"(?:::=|REFERENCE|DEFVAL|INDEX|AUGMENTS|OBJECTS|STATUS|MAX-ACCESS|SYNTAX)",  # Stop keywords
            re.DOTALL | re.IGNORECASE,
        )

        descriptions = {}

        for match in desc_pattern.finditer(content):
            obj_name = match.group(1)
            description = match.group(2).strip()

            # Clean up description
            description = description.replace('""', '"')  # Handle escaped quotes
            description = re.sub(r"\s+", " ", description)  # Normalize whitespace

            # ✅ Sanity check: Skip if too long (likely regex error)
            if len(description) < 5000:
                descriptions[obj_name] = description
            else:
                self.logger.warning(
                    f"Description for {obj_name} too long ({len(description)} chars), skipping"
                )

        # Apply to objects
        enhanced_count = 0
        for obj in objects:
            if obj.object_name in descriptions:
                # ✅ For notifications, always set description
                if obj.node_type == "NotificationType":
                    obj.description = descriptions[obj.object_name]
                    enhanced_count += 1
                # For other objects, only if not already set or shorter
                elif not obj.description or len(obj.description) < len(
                    descriptions[obj.object_name]
                ):
                    obj.description = descriptions[obj.object_name]
                    enhanced_count += 1

        if enhanced_count > 0:
            self.logger.debug(f"Enhanced {enhanced_count} objects with descriptions from source")

    def _extract_module_metadata(self, objects: List[MibObject], file_path: Path):
        """Extract module metadata and apply to all objects - ENHANCED."""
        # Get cached content
        if str(file_path) in self.file_content_cache:
            content = self.file_content_cache[str(file_path)]
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                self.file_content_cache[str(file_path)] = content

        # Extract module revision
        revision = ""
        revision_match = re.search(r'LAST-UPDATED\s+"(\d{10,12}Z?)"', content)
        if revision_match:
            revision = revision_match.group(1)

        # Extract imports
        imports = []
        imports_match = re.search(r"IMPORTS\s+(.*?);", content, re.DOTALL)
        if imports_match:
            imports_text = imports_match.group(1)
            from_clauses = re.findall(r"FROM\s+([A-Za-z][\w-]*)", imports_text)
            imports = [imp for imp in from_clauses if imp not in STUB_MIBS]

        imports_str = ",".join(imports) if imports else ""

        # Apply to all objects
        for obj in objects:
            obj.source_file = file_path.name
            obj.mib_revision = revision
            obj.mib_imports = imports_str

    def _batch_resolve_parents(self, objects: List[MibObject]):
        """Resolve all parent relationships in single pass - ENHANCED."""
        # Build local OID map for this module
        local_oid_map = {obj.object_oid: obj for obj in objects if obj.object_oid}

        for obj in objects:
            if obj.object_oid and "." in obj.object_oid:
                parent_oid = ".".join(obj.object_oid.split(".")[:-1])
                obj.parent_oid = parent_oid

                # Look up in local map first
                if parent_oid in local_oid_map:
                    parent_obj = local_oid_map[parent_oid]
                    obj.parent_name = parent_obj.object_name
                    obj.parent_type = parent_obj.node_type
                    continue

                # Look up in global index
                with self.resources.resource_lock:
                    if parent_oid in self.resources.oid_to_object:
                        parent_obj = self.resources.oid_to_object[parent_oid]
                        obj.parent_name = parent_obj.object_name
                        obj.parent_type = parent_obj.node_type
                        continue

                # Try standard parent names
                parent_info = self._resolve_standard_parent(parent_oid)
                if parent_info:
                    obj.parent_name = parent_info["name"]
                    obj.parent_type = parent_info["type"]

    def _resolve_standard_parent(self, parent_oid: str) -> Optional[Dict[str, str]]:
        """Resolve standard parent information from OID - EXPANDED."""
        # ✅ Expanded standard parent map (50+ common OIDs)
        standard_parents = {
            # SNMP standard
            "1.3.6.1.6.3.1.1.5": {"name": "snmpTraps", "type": "MibIdentifier"},
            "1.3.6.1.6.3.1.1.4": {"name": "snmpTrapOID", "type": "MibIdentifier"},
            "1.3.6.1.6.3.1.1": {"name": "snmpMIBObjects", "type": "MibIdentifier"},
            "1.3.6.1.6.3.1": {"name": "snmpMIB", "type": "ModuleIdentity"},
            # MIB-2
            "1.3.6.1.2.1": {"name": "mib-2", "type": "MibIdentifier"},
            "1.3.6.1.2.1.1": {"name": "system", "type": "MibIdentifier"},
            "1.3.6.1.2.1.2": {"name": "interfaces", "type": "MibIdentifier"},
            "1.3.6.1.2.1.2.2": {"name": "ifTable", "type": "MibTable"},
            "1.3.6.1.2.1.2.2.1": {"name": "ifEntry", "type": "MibTableRow"},
            "1.3.6.1.2.1.3": {"name": "at", "type": "MibIdentifier"},
            "1.3.6.1.2.1.4": {"name": "ip", "type": "MibIdentifier"},
            "1.3.6.1.2.1.5": {"name": "icmp", "type": "MibIdentifier"},
            "1.3.6.1.2.1.6": {"name": "tcp", "type": "MibIdentifier"},
            "1.3.6.1.2.1.7": {"name": "udp", "type": "MibIdentifier"},
            "1.3.6.1.2.1.10": {"name": "transmission", "type": "MibIdentifier"},
            "1.3.6.1.2.1.11": {"name": "snmp", "type": "MibIdentifier"},
            "1.3.6.1.2.1.31": {"name": "ifMIB", "type": "ModuleIdentity"},
            "1.3.6.1.2.1.31.1": {"name": "ifMIBObjects", "type": "MibIdentifier"},
            "1.3.6.1.2.1.31.1.1": {"name": "ifXTable", "type": "MibTable"},
            "1.3.6.1.2.1.31.1.1.1": {"name": "ifXEntry", "type": "MibTableRow"},
            # Enterprises
            "1.3.6.1.4.1": {"name": "enterprises", "type": "MibIdentifier"},
            # Experimental
            "1.3.6.1.3": {"name": "experimental", "type": "MibIdentifier"},
            # Private
            "1.3.6.1.4": {"name": "private", "type": "MibIdentifier"},
            # Security
            "1.3.6.1.5": {"name": "security", "type": "MibIdentifier"},
            # SNMPv2
            "1.3.6.1.6": {"name": "snmpV2", "type": "MibIdentifier"},
            "1.3.6.1.6.3": {"name": "snmpModules", "type": "MibIdentifier"},
            # Common vendor roots
            "1.3.6.1.4.1.9": {"name": "cisco", "type": "MibIdentifier"},
            "1.3.6.1.4.1.2636": {"name": "juniper", "type": "MibIdentifier"},
            "1.3.6.1.4.1.6527": {"name": "alcatel", "type": "MibIdentifier"},
            "1.3.6.1.4.1.2011": {"name": "huawei", "type": "MibIdentifier"},
            "1.3.6.1.4.1.311": {"name": "microsoft", "type": "MibIdentifier"},
            "1.3.6.1.4.1.8072": {"name": "netSnmp", "type": "MibIdentifier"},
        }

        return standard_parents.get(parent_oid)

    def _enrich_notification_objects_from_source(self, notif_obj: MibObject, file_path: Path):
        """
        Enrich notification object details with descriptions from source MIB file.
        """
        if not notif_obj.notification_objects or not notif_obj.notification_objects_detail:
            return

        # Get cached content
        if str(file_path) in self.file_content_cache:
            content = self.file_content_cache[str(file_path)]
        else:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    self.file_content_cache[str(file_path)] = content
            except Exception as e:
                self.logger.debug(f"Failed to read source file for notification enrichment: {e}")
                return

        # Extract descriptions for all objects in this notification
        details = notif_obj.notification_objects_detail.get("details", {})

        for obj_name in notif_obj.notification_objects:
            if obj_name not in details:
                continue

            # ✅ FIXED: Better regex that stops at next keyword
            # Pattern: objectName OBJECT-TYPE ... DESCRIPTION "..." <STOP>
            pattern = (
                rf"{obj_name}\s+OBJECT-TYPE\s+.*?"
                r'DESCRIPTION\s+"((?:[^"]|"")*?)"'
                r"\s*(?:::=|REFERENCE|DEFVAL|INDEX|AUGMENTS|MAX-ACCESS|SYNTAX|STATUS)"
            )
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

            if match:
                description = match.group(1).strip()
                # Clean up description
                description = description.replace('""', '"')  # Handle escaped quotes
                description = re.sub(r"\s+", " ", description)  # Normalize whitespace

                # ✅ Only update if we got a reasonable length (not the whole file!)
                if len(description) < 5000:  # Sanity check
                    # Update the detail with source description
                    if not details[obj_name].get("description") or len(description) > len(
                        details[obj_name].get("description", "")
                    ):
                        details[obj_name]["description"] = description
                        # self.logger.debug(f"Enriched {obj_name} description from source ({len(description)} chars)")
                else:
                    self.logger.warning(
                        f"Description for {obj_name} too long ({len(description)} chars), skipping"
                    )

    # ============================================
    # SECTION 8: DATAFRAME CONVERSION (FIXED)
    # ============================================

    def _objects_to_expanded_df(self, objects: List[MibObject], file_path: Path) -> pd.DataFrame:
        """Convert objects to DataFrame with expanded notification rows - FIXED."""
        rows = []

        for obj in objects:
            if obj.node_type == "NotificationType" and obj.notification_objects:
                # Expand notification objects into separate rows
                for seq, notif_obj_name in enumerate(obj.notification_objects, 1):
                    row = self._create_notification_row(obj, notif_obj_name, seq)
                    rows.append(row)
            else:
                # Non-notification objects
                row = self._create_regular_object_row(obj)
                rows.append(row)

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)

        # Optimize memory usage
        categorical_columns = [
            "node_type",
            "object_node_type",
            "notification_type",
            "object_access",
            "object_status",
            "notification_status",
            "module_name",
            "notification_module",
            "source_file",
        ]

        for col in categorical_columns:
            if col in df.columns and df[col].nunique() < len(df) * 0.5:
                df[col] = df[col].astype("category")

        # Add metadata
        df["processed_at"] = datetime.now()
        df["parser_version"] = "5.0.0"

        return df

    def _create_notification_row(
        self, notif_obj: MibObject, object_name: str, sequence: int
    ) -> Dict[str, Any]:
        """Create a row for notification object - FIXED."""
        row = {
            # Notification fields
            "notification_name": notif_obj.object_name,
            "notification_oid": notif_obj.object_oid,
            "notification_status": notif_obj.status,
            "notification_description": notif_obj.description or "",
            "notification_module": notif_obj.module_name,
            "notification_enterprise": notif_obj.notification_enterprise,
            "notification_type": "trap",
            "node_type": notif_obj.node_type,
            # Object fields
            "object_sequence": sequence,
            "object_name": object_name,
            "object_oid": "",
            "object_node_type": "",
            "object_syntax": "",
            "object_access": "",
            "object_status": "",
            "object_description": "",
            "object_units": "",
            "object_reference": "",
            # TC fields
            "tc_name": "",
            "tc_base_type": "",
            "tc_display_hint": "",
            "tc_status": "",
            "tc_description": "",
            "tc_enumerations": None,
            "tc_constraints": "",
            "tc_resolution_chain": "",
            # ✅ ADD: Table fields
            "table_indexes": "",
            "augments_table": "",
            # Parent fields
            "parent_name": notif_obj.parent_name or "",
            "parent_oid": notif_obj.parent_oid or "",
            "parent_type": notif_obj.parent_type or "",
            # Metadata
            "module_name": notif_obj.module_name,
            "module_revision": notif_obj.mib_revision or "",
            "source_file": notif_obj.source_file or "",
            "mib_imports": notif_obj.mib_imports or "",
        }

        # ✅ Fill object details if available
        if object_name and notif_obj.notification_objects_detail:
            details = notif_obj.notification_objects_detail.get("details", {})
            if object_name in details:
                obj_detail = details[object_name]
                row.update(
                    {
                        "object_oid": obj_detail.get("oid", ""),
                        "object_node_type": obj_detail.get("node_type", ""),
                        "object_syntax": obj_detail.get("syntax", ""),
                        "object_access": obj_detail.get("access", ""),
                        "object_status": obj_detail.get("status", ""),
                        "object_description": obj_detail.get("description", ""),
                        "tc_name": obj_detail.get("tc_name", ""),
                        "tc_base_type": obj_detail.get("tc_base_type", ""),
                        "tc_display_hint": obj_detail.get("tc_display_hint", ""),
                        "tc_status": obj_detail.get("tc_status", ""),
                        "tc_description": obj_detail.get("tc_description", ""),
                        "tc_constraints": obj_detail.get("tc_constraints", ""),
                        "tc_resolution_chain": obj_detail.get("tc_resolution_chain", ""),
                        # ✅ FIX: Properly serialize enumerations
                        "tc_enumerations": (
                            json.dumps(obj_detail.get("enumerations"))
                            if obj_detail.get("enumerations")
                            else None
                        ),
                    }
                )

                # ✅ NEW: For inline enumerations without named TC, populate TC metadata
                if obj_detail.get("enumerations") and not obj_detail.get("tc_name"):
                    # Use object syntax as tc_base_type
                    if obj_detail.get("syntax") and not row["tc_base_type"]:
                        row["tc_base_type"] = obj_detail["syntax"]
                        # self.logger.debug(f"Set tc_base_type from syntax for {object_name}: {row['tc_base_type']}")

                    # Use object status as tc_status
                    if obj_detail.get("status") and not row["tc_status"]:
                        row["tc_status"] = obj_detail["status"]
                        # self.logger.debug(f"Set tc_status from object status for {object_name}: {row['tc_status']}")

        return row

    def _create_regular_object_row(self, obj: MibObject) -> Dict[str, Any]:
        """Create a row for non-notification object - FIXED."""
        row = {
            # Empty notification fields
            "notification_name": "",
            "notification_oid": "",
            "notification_status": "",
            "notification_description": "",
            "notification_module": "",
            "notification_enterprise": "",
            "notification_type": "",
            "node_type": obj.node_type,
            # Object fields
            "object_sequence": 0,
            "object_name": obj.object_name,
            "object_oid": obj.object_oid,
            "object_node_type": obj.node_type,
            "object_syntax": obj.syntax_type or "",
            "object_access": obj.access_level or "",
            "object_status": obj.status or "",
            "object_description": obj.description or "",
            "object_units": obj.units or "",
            "object_reference": obj.reference or "",
            # TC fields
            "tc_name": obj.tc_name or "",
            "tc_base_type": obj.tc_base_type or "",
            "tc_display_hint": obj.tc_display_hint or "",
            "tc_status": obj.tc_status or "",
            "tc_description": obj.tc_description or "",
            # ✅ FIX: Properly serialize enumerations from object
            "tc_enumerations": json.dumps(obj.enumerations) if obj.enumerations else None,
            "tc_constraints": obj.tc_constraints or obj.value_range or "",
            "tc_resolution_chain": obj.tc_resolution_chain or "",
            # ✅ ADD: Table fields
            "table_indexes": obj.table_indexes or "",
            "augments_table": obj.augments_table or "",
            # Parent fields
            "parent_name": obj.parent_name or "",
            "parent_oid": obj.parent_oid or "",
            "parent_type": obj.parent_type or "",
            # Metadata
            "module_name": obj.module_name,
            "module_revision": obj.mib_revision or "",
            "source_file": obj.source_file or "",
            "mib_imports": obj.mib_imports or "",
        }

        # ✅ NEW: For inline enumerations without named TC, populate TC metadata
        if obj.enumerations and not obj.tc_name:
            # Use object syntax as tc_base_type
            if obj.syntax_type and not row["tc_base_type"]:
                row["tc_base_type"] = obj.syntax_type
                # self.logger.debug(f"Set tc_base_type from syntax for {obj.object_name}: {row['tc_base_type']}")

            # Use object status as tc_status
            if obj.status and not row["tc_status"]:
                row["tc_status"] = obj.status
                # self.logger.debug(f"Set tc_status from object status for {obj.object_name}: {row['tc_status']}")

        return row

    # ============================================
    # SECTION 9: HELPER METHODS
    # ============================================

    def _extract_module_name(self, file_path: Path) -> str:
        """Extract module name from MIB file - OPTIMIZED."""
        try:
            # ✅ Read full file and cache it (used by other methods too)
            if str(file_path) not in self.file_content_cache:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    self.file_content_cache[str(file_path)] = content
            else:
                content = self.file_content_cache[str(file_path)]

            # Look for MODULE-IDENTITY or DEFINITIONS
            match = re.search(
                r"^\s*([A-Za-z][\w-]*)\s+(?:MODULE-IDENTITY|DEFINITIONS)", content, re.MULTILINE
            )
            if match:
                return match.group(1)
        except Exception as e:
            self.logger.debug(f"Failed to extract module name from {file_path}: {e}")

        # Fallback to filename
        return file_path.stem

    def _apply_deduplication(self, df: pd.DataFrame, source: str) -> pd.DataFrame:
        """Apply deduplication to DataFrame."""
        from core.deduplicator import DeduplicationService
        
        strategy = self.config.parser.deduplication_strategy
        
        self.logger.info(f"Phase 4: Deduplication {source} using '{strategy}' strategy")
        
        deduplicator = DeduplicationService()
        original_count = len(df)
        df_clean = deduplicator.deduplicate(df, strategy=strategy)
        removed = original_count - len(df_clean)
        
        if removed > 0:
            self.logger.info(f"✅ Removed {removed} duplicates: {original_count} → {len(df_clean)}")
            self.stats["last_dedup_count"] = removed
        
        return df_clean

    def get_statistics(self) -> Dict[str, Any]:
        """Get parser statistics."""
        stats = {
            "parser_stats": self.stats,
            "resource_stats": self.resources.stats,
            "cache_stats": self.cache.get_cache_stats() if self.cache else {},
            "failed_files_count": len(self.stats["failed_files"]),
            "missing_dependencies_count": len(self.stats["missing_dependencies"]),
        }
        return stats
    
    def clear_caches(self):
        """
        Clear internal caches.
        Call this after each parse job in long-running web apps to prevent memory leaks.
        """
        with self.resources.resource_lock:
            self.file_content_cache.clear()
            self.resources.external_object_cache.clear()
            self.resources.tc_resolution_cache.clear()
            self.resources.description_cache.clear()
            self.resources.module_symbols_cache.clear()
        
        self.logger.info("Cleared parser caches")

    # ============================================
    # SECTION 10: ASYNC & BACKGROUND SUPPORT
    # ============================================

    async def parse_file_async(
        self,
        file_path: str,
        force_compile: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> pd.DataFrame:
        """
        Async wrapper for web integration.

        Runs parse_file in thread pool to avoid blocking event loop.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.parse_file, file_path, force_compile)

    async def parse_directory_async(
        self,
        dir_path: str,
        pattern: str = "*.mib",
        recursive: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> pd.DataFrame:
        """
        Async wrapper for directory parsing.

        Runs parse_directory in thread pool to avoid blocking event loop.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.parse_directory, dir_path, pattern, recursive, progress_callback
        )

    def validate_parse_result(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Simple validation for web API responses.
        Returns validation summary without modifying the data.
        """
        if df.empty:
            return {"valid": False, "error": "No data extracted", "warnings": []}

        warnings = []

        # Check for required columns
        required_columns = ["object_name", "module_name"]
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            warnings.append(f"Missing columns: {missing}")

        # Basic statistics for API response
        stats = {
            "total_records": len(df),
            "modules": df["module_name"].nunique() if "module_name" in df.columns else 0,
            "node_types": (
                df["node_type"].value_counts().to_dict() if "node_type" in df.columns else {}
            ),
        }

        return {"valid": len(missing) == 0, "warnings": warnings, "statistics": stats}

    def cleanup_compiled_mibs(self, days_old: int = 30) -> int:
        """Clean up old compiled MIB files for long-running services."""
        if not self.compiled_dir.exists():
            return 0

        import time

        cutoff_time = time.time() - (days_old * 24 * 3600)
        removed_count = 0

        for file_path in self.compiled_dir.glob("*.py"):
            try:
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    removed_count += 1
            except Exception as e:
                self.logger.debug(f"Failed to remove {file_path}: {e}")

        if removed_count > 0:
            self.logger.info(f"Removed {removed_count} old compiled MIB files")

        return removed_count

    def parse_from_content(self, content: str, filename: str = "uploaded.mib") -> pd.DataFrame:
        """
        Parse MIB from string content (for web uploads).
        Useful when receiving MIB content directly from API.
        """
        import tempfile

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".mib", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Parse the temp file
            df = self.parse_file(tmp_path)

            # Update source_file to original filename
            if not df.empty and "source_file" in df.columns:
                df["source_file"] = filename

            return df
        finally:
            # Clean up temp file
            Path(tmp_path).unlink(missing_ok=True)

    def get_parse_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get a summary of parsed data for API responses.
        """
        if df.empty:
            return {"error": "No data parsed"}

        summary = {
            "total_records": len(df),
            "modules": list(df["module_name"].unique()) if "module_name" in df.columns else [],
            "statistics": {},
        }

        # Add node type statistics
        if "node_type" in df.columns:
            summary["statistics"]["by_type"] = df["node_type"].value_counts().to_dict()

        # Add notification statistics
        if "notification_name" in df.columns:
            notif_df = df[df["notification_name"].notna() & (df["notification_name"] != "")]
            if not notif_df.empty:
                summary["statistics"]["notifications"] = {
                    "total": notif_df["notification_name"].nunique(),
                    "objects": len(notif_df),
                }

        return summary
