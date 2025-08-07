#!/usr/bin/env python3
"""
Script to find duplicate function names within each Python file.
"""

import os
import ast
from collections import Counter
from pathlib import Path


class FunctionVisitor(ast.NodeVisitor):
    """AST visitor to extract function names from Python code."""
    
    def __init__(self):
        self.functions = []
    
    def visit_FunctionDef(self, node):
        """Visit function definitions and record their names."""
        self.functions.append(node.name)
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node):
        """Visit async function definitions and record their names."""
        self.functions.append(node.name)
        self.generic_visit(node)


def find_duplicates_in_file(file_path):
    """Find duplicate function names within a single Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        visitor = FunctionVisitor()
        visitor.visit(tree)
        
        # Count function occurrences
        function_counts = Counter(visitor.functions)
        
        # Find duplicates (count > 1)
        duplicates = {name: count for name, count in function_counts.items() if count > 1}
        
        return duplicates, len(visitor.functions)
    
    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}")
        return {}, 0
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return {}, 0


def scan_files_for_duplicates(directory='.'):
    """Scan all Python files in directory for duplicate function names within each file."""
    
    # Find Python files only in current directory
    directory_path = Path(directory)
    python_files = list(directory_path.glob('*.py'))
    
    if not python_files:
        print(f"No Python files found in directory: {directory}")
        return
    
    print(f"Scanning {len(python_files)} Python files for duplicate functions within each file...\n")
    
    total_files_with_duplicates = 0
    total_duplicate_functions = 0
    total_functions = 0
    
    # Process each Python file
    for py_file in sorted(python_files):
        duplicates, func_count = find_duplicates_in_file(py_file)
        total_functions += func_count
        
        if duplicates:
            total_files_with_duplicates += 1
            total_duplicate_functions += len(duplicates)
            
            print(f"📄 File: {py_file.name}")
            print("=" * 50)
            
            for func_name, count in sorted(duplicates.items()):
                print(f"  ⚠️  Function '{func_name}' appears {count} times")
            
            print(f"  Total functions in file: {func_count}")
            print(f"  Duplicate function names: {len(duplicates)}")
            print()
        else:
            print(f"✅ {py_file.name} - No duplicates found ({func_count} functions)")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print(f"  Files scanned: {len(python_files)}")
    print(f"  Files with duplicate functions: {total_files_with_duplicates}")
    print(f"  Total functions found: {total_functions}")
    print(f"  Total duplicate function names: {total_duplicate_functions}")
    
    if total_files_with_duplicates == 0:
        print("\n🎉 No duplicate function names found in any files!")


def main():
    """Main function with command line argument support."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Find duplicate function names within each Python file"
    )
    parser.add_argument(
        'directory', 
        nargs='?', 
        default='.', 
        help='Directory to scan (default: current directory)'
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.directory):
        print(f"Error: Directory '{args.directory}' does not exist!")
        return
    
    print(f"Searching for duplicate function names within files in: {os.path.abspath(args.directory)}")
    print("Note: Only scanning .py files in the current directory (no subdirectories)\n")
    
    scan_files_for_duplicates(args.directory)


if __name__ == "__main__":
    main()