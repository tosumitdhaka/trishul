"""
Protobuf Decoder V2 - Google Protobuf Implementation

Uses official google.protobuf + grpc_tools.protoc for robust decoding
"""

import json
import sys
import time
import zipfile
import importlib.util
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from google.protobuf import json_format
from grpc_tools import protoc

from utils.logger import get_logger
from backend.services.metrics_service import get_metrics_service

logger = get_logger(__name__)


class ProtobufDecoderV2:
    """
    Protobuf decoder using official Google protobuf library.
    
    Two-phase approach:
    1. compile_schema() - Compile .proto files to Python modules
    2. decode_files() - Decode binary protobuf files using compiled schema
    """
    
    def __init__(self, session_dir: Path, verbose: bool = False):
        """
        Initialize decoder.
        
        Args:
            session_dir: Session directory containing .proto and .protobuf files
            verbose: Enable verbose logging
        """
        self.session_dir = Path(session_dir)
        self.verbose = verbose
        self.compiled_modules = {}
        self.message_classes = {}

        self.metrics = get_metrics_service()
        
        if not self.session_dir.exists():
            raise ValueError(f"Session directory not found: {session_dir}")
    
    def compile_schema(self) -> Dict[str, Any]:
        """
        Compile all .proto files in session directory.
        
        Returns:
            Dict with:
                - success: bool
                - message_types: List[str] (sorted by dependency score)
                - auto_detected_root: str (most likely root message)
                - proto_files: List[str] (compiled files)
                - package: str (proto package name)
                - dependency_scores: Dict[str, int]
        """

        start_time = time.time()

        try:
            # Find all .proto files
            proto_files = list(self.session_dir.rglob("*.proto"))
            
            if not proto_files:
                return {
                    "success": False,
                    "error": "No .proto files found in session directory",
                    "message_types": [],
                    "auto_detected_root": None,
                }
            
            logger.info(f"📦 Found {len(proto_files)} .proto file(s)")
            
            # Setup include paths
            include_paths = [str(self.session_dir), "."]
            python_out = str(self.session_dir)
            
            # Build protoc command
            cmd = [
                'grpc_tools.protoc',
                *[f'-I{p}' for p in include_paths],
                f'--python_out={python_out}',
                *[str(p) for p in proto_files]
            ]
            
            if self.verbose:
                logger.debug(f"Running protoc: {' '.join(cmd)}")
            
            # Compile
            result = protoc.main(cmd)
            
            if result != 0:
                if self.metrics:
                    self.metrics.counter('protobuf_compile_total', {'status': 'failed'})
                return {
                    "success": False,
                    "error": "Protobuf compilation failed. Check schema syntax and imports.",
                    "message_types": [],
                    "auto_detected_root": None,
                }
            
            logger.info("✅ Protobuf compilation successful")
            
            # Load compiled modules and extract message types
            sys.path.insert(0, str(self.session_dir))
            
            try:
                message_types, dependency_scores, package = self._load_message_types(proto_files)
                
                if not message_types:
                    if self.metrics:
                        self.metrics.counter('protobuf_compile_total', {'status': 'failed'})
                    return {
                        "success": False,
                        "error": "No message types found in compiled schema",
                        "message_types": [],
                        "auto_detected_root": None,
                    }
                
                # Track metrics
                if self.metrics:
                    self.metrics.counter('protobuf_compile_total', {'status': 'success'})
                    self.metrics.gauge_set('protobuf_message_types_count', len(message_types))
                    duration = time.time() - start_time
                    self.metrics.gauge_set('protobuf_compile_duration_seconds', round(duration, 2))
                
                # Sort by dependency score (highest first)
                sorted_types = sorted(
                    message_types.keys(),
                    key=lambda x: dependency_scores.get(x, 0),
                    reverse=True
                )
                
                auto_root = sorted_types[0] if sorted_types else None
                
                logger.info(f"✅ Found {len(message_types)} message type(s)")
                logger.info(f"🎯 Auto-detected root: {auto_root}")
                
                if self.verbose:
                    logger.debug(f"Dependency scores: {dependency_scores}")
                
                return {
                    "success": True,
                    "message_types": sorted_types,
                    "auto_detected_root": auto_root,
                    "proto_files": [p.name for p in proto_files],
                    "package": package,
                    "dependency_scores": dependency_scores,
                }
            
            finally:
                if str(self.session_dir) in sys.path:
                    sys.path.remove(str(self.session_dir))
        
        except Exception as e:
            if self.metrics:
                self.metrics.counter('protobuf_compile_total', {'status': 'failed'})

            logger.error(f"Schema compilation failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message_types": [],
                "auto_detected_root": None,
            }
    
    def _load_message_types(self, proto_files: List[Path]) -> Tuple[Dict, Dict, str]:
        """
        Load message types from compiled _pb2.py files.
        
        Returns:
            Tuple of (message_classes, dependency_scores, package_name)
        """
        message_classes = {}
        dependency_scores = {}
        package = ""
        
        for proto_file in proto_files:
            module_name = proto_file.stem + "_pb2"
            generated_path = proto_file.with_name(f"{proto_file.stem}_pb2.py")
            
            if not generated_path.exists():
                logger.warning(f"Generated file not found: {generated_path.name}")
                continue
            
            try:
                # Load module
                spec = importlib.util.spec_from_file_location(module_name, generated_path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                
                self.compiled_modules[module_name] = module
                
                # Extract message classes
                for name, obj in vars(module).items():
                    if isinstance(obj, type) and hasattr(obj, 'DESCRIPTOR'):
                        full_name = obj.DESCRIPTOR.full_name
                        message_classes[full_name] = obj
                        self.message_classes[full_name] = obj
                        
                        # Extract package from first message
                        if not package and '.' in full_name:
                            package = full_name.rsplit('.', 1)[0]
                        
                        # Calculate dependency score
                        score = self._calculate_dependency_score(obj)
                        dependency_scores[full_name] = score
                
                logger.debug(f"Loaded module: {module_name}")
            
            except Exception as e:
                logger.error(f"Failed to load module {module_name}: {e}")
                continue
        
        return message_classes, dependency_scores, package
    
    def _calculate_dependency_score(self, message_class) -> int:
        """
        Calculate dependency score for a message.
        Higher score = more likely to be root message.
        
        Score = number of fields that reference other messages
        """
        score = 0
        
        try:
            for field in message_class.DESCRIPTOR.fields:
                # Count message-type fields
                if field.type == field.TYPE_MESSAGE:
                    score += 1
                
                # Count map fields with message values
                if field.message_type and field.message_type.GetOptions().map_entry:
                    # This is a map field
                    for map_field in field.message_type.fields:
                        if map_field.name == 'value' and map_field.type == map_field.TYPE_MESSAGE:
                            score += 1
        
        except Exception as e:
            logger.debug(f"Error calculating score: {e}")
        
        return score
    
    def decode_files(
        self,
        binary_files: List[str],
        message_type: str,
        output_dir: Optional[Path] = None,
        indent: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Decode binary protobuf files.
        
        Args:
            binary_files: List of binary file names (relative to session_dir)
            message_type: Root message type (full name)
            output_dir: Output directory for JSON files (default: session_dir)
            indent: JSON indentation
        
        Returns:
            List of decode results
        """

        start_time = time.time()

        if not self.message_classes:
            raise ValueError("Schema not compiled. Call compile_schema() first.")
        
        if message_type not in self.message_classes:
            available = ', '.join(self.message_classes.keys())
            raise ValueError(
                f"Message type '{message_type}' not found. "
                f"Available types: {available}"
            )
        
        output_dir = output_dir or self.session_dir
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        message_class = self.message_classes[message_type]
        results = []

        success_count = 0
        failed_count = 0
        total_fields = 0
        
        sys.path.insert(0, str(self.session_dir))
        
        try:
            for filename in binary_files:
                result = self._decode_single_file(
                    filename,
                    message_class,
                    message_type,
                    output_dir,
                    indent
                )
                results.append(result)

                if result["status"] == "success":
                    success_count += 1
                    total_fields += result.get("fields_decoded", 0)
                else:
                    failed_count += 1
        
        finally:
            if str(self.session_dir) in sys.path:
                sys.path.remove(str(self.session_dir))

        # Track metrics
        if self.metrics:
            self.metrics.counter_add('protobuf_decode_total', success_count, {'status': 'success'})
            self.metrics.counter_add('protobuf_decode_total', failed_count, {'status': 'failed'})
            self.metrics.counter_add('protobuf_files_decoded', success_count)
            self.metrics.counter_add('protobuf_fields_decoded_total', total_fields)
            
            duration = time.time() - start_time
            self.metrics.gauge_set('protobuf_decode_duration_seconds', round(duration, 2))
        
        return results
    
    def _decode_single_file(
        self,
        filename: str,
        message_class,
        message_type: str,
        output_dir: Path,
        indent: int
    ) -> Dict[str, Any]:
        """Decode a single binary file."""
        file_path = self.session_dir / filename
        
        result = {
            "filename": filename,
            "status": "pending",
            "message_type": message_type,
        }
        
        try:
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {filename}")
            
            # Read binary data
            with open(file_path, 'rb') as f:
                binary_data = f.read()
            
            # Parse protobuf
            msg_instance = message_class()
            msg_instance.ParseFromString(binary_data)
            
            # Convert to dict
            data = json_format.MessageToDict(
                msg_instance,
                preserving_proto_field_name=True,
                use_integers_for_enums=False
            )
            
            # Save to JSON
            output_filename = f"{Path(filename).stem}.json"
            output_path = output_dir / output_filename
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            
            result.update({
                "status": "success",
                "output_filename": output_filename,
                "output_path": str(output_path),
                "file_size": output_path.stat().st_size,
                "fields_decoded": len(data),
            })
            
            logger.info(f"✅ Decoded: {filename} → {output_filename}")
        
        except Exception as e:
            logger.error(f"❌ Failed to decode {filename}: {e}")
            result.update({
                "status": "failed",
                "error": str(e),
            })
        
        return result
    
    def create_batch_zip(
        self,
        json_files: List[str],
        output_filename: str = "decoded_batch.zip"
    ) -> Optional[Path]:
        """
        Create a ZIP archive of JSON files.
        
        Args:
            json_files: List of JSON filenames (relative to session_dir)
            output_filename: Output ZIP filename
        
        Returns:
            Path to created ZIP file or None if failed
        """
        try:
            output_path = self.session_dir / output_filename
            
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for filename in json_files:
                    file_path = self.session_dir / filename
                    if file_path.exists():
                        zipf.write(file_path, arcname=filename)
            
            logger.info(f"✅ Created batch ZIP: {output_filename} ({len(json_files)} files)")
            return output_path
        
        except Exception as e:
            logger.error(f"Failed to create ZIP: {e}")
            return None
    
    def get_schema_info(self) -> Dict[str, Any]:
        """Get detailed schema information."""
        if not self.message_classes:
            return {
                "compiled": False,
                "message": "Schema not compiled"
            }
        
        messages_detail = []
        
        for full_name, msg_class in self.message_classes.items():
            try:
                descriptor = msg_class.DESCRIPTOR
                
                fields_info = []
                for field in descriptor.fields:
                    fields_info.append({
                        "number": field.number,
                        "name": field.name,
                        "type": field.type_name,
                        "label": field.label_name,
                    })
                
                messages_detail.append({
                    "name": full_name,
                    "fields_count": len(descriptor.fields),
                    "fields": fields_info,
                })
            
            except Exception as e:
                logger.debug(f"Error getting info for {full_name}: {e}")
        
        return {
            "compiled": True,
            "total_messages": len(self.message_classes),
            "messages": list(self.message_classes.keys()),
            "messages_detail": messages_detail,
        }
