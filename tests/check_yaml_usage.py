#!/usr/bin/env python3
import yaml
import os
import sys

# Directories to exclude (hardcoded)
EXCLUDE_DIRS = {'.git', 'node_modules', 'build', '__pycache__',
                '.venv', 'cache', 'compiled_mibs', 'uploads',
                'exports', 'docs', 'standard_mibs', 'config'
                }


def extract_leaf_keys(data, parent_key=""):
    """Extract only leaf keys (full path) from YAML."""
    keys = []
    if isinstance(data, dict):
        for k, v in data.items():
            full_key = f"{parent_key}.{k}" if parent_key else k
            if isinstance(v, dict) or isinstance(v, list):
                keys.extend(extract_leaf_keys(v, full_key))
            else:
                keys.append(full_key)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            full_key = f"{parent_key}[{i}]"
            keys.extend(extract_leaf_keys(item, full_key))
    return keys

def search_keys(keys, search_dir):
    """Search for keys in files under search_dir, excluding EXCLUDE_DIRS."""
    for root, dirs, files in os.walk(search_dir):
        # Remove excluded directories from traversal
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for file in files:
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for lineno, line in enumerate(f, start=1):
                        for key in keys:
                            if key in line:
                                print(f"[MATCH] {key} -> {file_path}:{lineno}   .......  {line.strip()}")
            except Exception as e:
                print(f"Could not read {file_path}: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python check_yaml_usage.py <yaml_file> <search_directory>")
        sys.exit(1)

    yaml_file = sys.argv[1]
    search_dir = sys.argv[2]

    with open(yaml_file, 'r') as f:
        yaml_data = yaml.safe_load(f)

    keys = extract_leaf_keys(yaml_data)
    print(f"Extracted {len(keys)} leaf keys from YAML:")
    for k in keys:
        print(f" - {k}")

    print("\nSearching for keys...")
    search_keys(keys, search_dir)

