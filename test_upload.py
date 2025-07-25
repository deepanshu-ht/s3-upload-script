#!/usr/bin/env python3
"""
Test Script for S3 Large Directory Upload

This script creates a test directory structure with various file types and sizes
to demonstrate the S3 upload functionality. It can also run the upload in dry-run
mode to show what would be uploaded.
"""

import os
import sys
import tempfile
import shutil
import json
from pathlib import Path
from random import randint
import argparse


def create_test_files(test_dir: Path, num_files: int = 50, max_size_mb: int = 10):
    """Create test files of various sizes and types"""
    print(f"Creating {num_files} test files in {test_dir}")
    
    # Create subdirectories
    subdirs = ['documents', 'images', 'data', 'logs', 'temp']
    for subdir in subdirs:
        (test_dir / subdir).mkdir(exist_ok=True)
    
    # File extensions and their typical subdirectories
    file_types = {
        'documents': ['.txt', '.pdf', '.doc', '.md'],
        'images': ['.jpg', '.png', '.gif', '.bmp'],
        'data': ['.csv', '.json', '.xml', '.sql'],
        'logs': ['.log', '.out'],
        'temp': ['.tmp', '.cache']
    }
    
    files_created = 0
    for subdir, extensions in file_types.items():
        subdir_path = test_dir / subdir
        files_per_subdir = num_files // len(file_types)
        
        for i in range(files_per_subdir):
            # Random file extension
            ext = extensions[randint(0, len(extensions) - 1)]
            filename = f"test_file_{i:03d}{ext}"
            file_path = subdir_path / filename
            
            # Create file with random size (1KB to max_size_mb MB)
            file_size = randint(1024, max_size_mb * 1024 * 1024)
            
            with open(file_path, 'wb') as f:
                # Write random data in chunks to avoid memory issues
                chunk_size = 64 * 1024  # 64KB chunks
                remaining = file_size
                
                while remaining > 0:
                    write_size = min(chunk_size, remaining)
                    # Create predictable but varied content
                    chunk = bytes([(i + j) % 256 for j in range(write_size)])
                    f.write(chunk)
                    remaining -= write_size
            
            files_created += 1
            if files_created % 10 == 0:
                print(f"  Created {files_created} files...")
    
    # Create some special files to test exclusion patterns
    (test_dir / '.DS_Store').touch()
    (test_dir / 'debug.log').write_text("Debug log content")
    (test_dir / 'temp.tmp').write_text("Temporary file")
    
    print(f"Created {files_created} test files plus special files")
    return files_created


def calculate_directory_size(directory: Path) -> tuple:
    """Calculate total size and file count of directory"""
    total_size = 0
    file_count = 0
    
    for file_path in directory.rglob('*'):
        if file_path.is_file():
            total_size += file_path.stat().st_size
            file_count += 1
    
    return total_size, file_count


def create_test_config(test_dir: Path, bucket_name: str = "test-bucket") -> Path:
    """Create a test configuration file"""
    config = {
        "source_directory": str(test_dir),
        "bucket_name": bucket_name,
        "s3_prefix": "test-upload/",
        "aws_profile": "default",
        "aws_region": "us-east-1",
        "max_concurrency": 2,
        "verify_checksums": True,
        "resume_upload": True,
        "exclude_patterns": [
            ".DS_Store",
            "*.tmp",
            "*.log"
        ],
        "dry_run": True
    }
    
    config_file = test_dir.parent / "test_config.json"
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Created test configuration: {config_file}")
    return config_file


def run_upload_test(config_file: Path):
    """Run the upload script with test configuration"""
    script_path = Path(__file__).parent / "s3_large_upload.py"
    
    if not script_path.exists():
        print(f"Error: S3 upload script not found at {script_path}")
        return False
    
    print(f"\nRunning upload test with config: {config_file}")
    print("Command that would be executed:")
    print(f"python {script_path} --config {config_file}")
    
    # Import and run the script directly for testing
    try:
        import subprocess
        result = subprocess.run([
            sys.executable, str(script_path), 
            "--config", str(config_file)
        ], capture_output=True, text=True)
        
        print(f"\nScript output:")
        print(result.stdout)
        
        if result.stderr:
            print(f"Script errors:")
            print(result.stderr)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"Error running upload script: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Test script for S3 Large Directory Upload",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_upload.py --create-only
  python test_upload.py --num-files 100 --max-size 5
  python test_upload.py --bucket my-test-bucket --run-upload
        """
    )
    
    parser.add_argument('--num-files', type=int, default=20,
                       help='Number of test files to create (default: 20)')
    parser.add_argument('--max-size', type=int, default=5,
                       help='Maximum file size in MB (default: 5)')
    parser.add_argument('--bucket', default='test-bucket',
                       help='S3 bucket name for testing (default: test-bucket)')
    parser.add_argument('--test-dir', 
                       help='Test directory path (default: creates temp directory)')
    parser.add_argument('--create-only', action='store_true',
                       help='Only create test files, do not run upload test')
    parser.add_argument('--run-upload', action='store_true',
                       help='Actually run the upload script (dry-run mode)')
    parser.add_argument('--cleanup', action='store_true',
                       help='Clean up test files after completion')
    
    args = parser.parse_args()
    
    # Create or use specified test directory
    if args.test_dir:
        test_dir = Path(args.test_dir)
        test_dir.mkdir(exist_ok=True)
        cleanup_dir = False
    else:
        test_dir = Path(tempfile.mkdtemp(prefix="s3_upload_test_"))
        cleanup_dir = args.cleanup
    
    print(f"Using test directory: {test_dir}")
    
    try:
        # Create test files
        files_created = create_test_files(
            test_dir, 
            args.num_files, 
            args.max_size
        )
        
        # Calculate directory statistics
        total_size, file_count = calculate_directory_size(test_dir)
        size_mb = total_size / (1024 * 1024)
        
        print(f"\nTest directory statistics:")
        print(f"  Total files: {file_count}")
        print(f"  Total size: {size_mb:.2f} MB")
        print(f"  Directory: {test_dir}")
        
        # Create test configuration
        config_file = create_test_config(test_dir, args.bucket)
        
        if not args.create_only:
            print(f"\nTest files created successfully!")
            print(f"You can now test the upload script with:")
            print(f"  python s3_large_upload.py --config {config_file}")
            print(f"  python s3_large_upload.py {test_dir} {args.bucket} --dry-run")
        
        # Optionally run the upload test
        if args.run_upload:
            success = run_upload_test(config_file)
            if success:
                print("\n✅ Upload test completed successfully!")
            else:
                print("\n❌ Upload test failed!")
                return 1
        
        # Show example commands
        if not args.create_only:
            print(f"\nExample commands to test:")
            print(f"# Dry run to see what would be uploaded:")
            print(f"python s3_large_upload.py {test_dir} {args.bucket} --dry-run")
            print(f"\n# Upload with exclusions:")
            print(f"python s3_large_upload.py {test_dir} {args.bucket} --exclude '*.log' --exclude '*.tmp' --dry-run")
            print(f"\n# Use configuration file:")
            print(f"python s3_large_upload.py --config {config_file}")
            
            print(f"\nNote: All examples use --dry-run mode for safety.")
            print(f"Remove --dry-run to perform actual uploads.")
    
    except Exception as e:
        print(f"Error during testing: {e}")
        return 1
    
    finally:
        # Cleanup if requested
        if cleanup_dir and test_dir.exists():
            print(f"\nCleaning up test directory: {test_dir}")
            shutil.rmtree(test_dir)
            if config_file.exists():
                config_file.unlink()
    
    return 0


if __name__ == '__main__':
    sys.exit(main()) 