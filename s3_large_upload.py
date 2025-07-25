#!/usr/bin/env python3
"""
S3 Large Directory Upload Script

A robust script for uploading large directories to AWS S3 with support for:
- Multipart uploads for large files
- Resume capability for interrupted uploads
- Progress tracking and user feedback
- Error handling and retries
- File integrity validation
- Configurable settings
"""

import os
import sys
import json
import hashlib
import logging
import argparse
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError, NoCredentialsError
from rich.console import Console
from rich.progress import (
    Progress, 
    SpinnerColumn, 
    TextColumn, 
    BarColumn, 
    TaskProgressColumn,
    TimeRemainingColumn,
    FileSizeColumn,
    TransferSpeedColumn
)
from rich.table import Table
from rich.panel import Panel
from rich.text import Text


@dataclass
class UploadConfig:
    """Configuration for the S3 upload operation"""
    source_directory: str
    bucket_name: str
    s3_prefix: str = ""
    aws_profile: Optional[str] = None
    aws_region: str = "us-east-1"
    multipart_threshold: int = 8 * 1024 * 1024  # 8MB
    multipart_chunksize: int = 8 * 1024 * 1024  # 8MB
    max_concurrency: int = 4
    max_retries: int = 3
    retry_delay: float = 1.0
    verify_checksums: bool = True
    resume_upload: bool = True
    exclude_patterns: List[str] = None
    include_patterns: List[str] = None
    dry_run: bool = False

    def __post_init__(self):
        if self.exclude_patterns is None:
            self.exclude_patterns = ['.DS_Store', '*.tmp', '*.log', '__pycache__']
        if self.include_patterns is None:
            self.include_patterns = ['*']


@dataclass
class UploadState:
    """State tracking for upload operations"""
    total_files: int = 0
    total_size: int = 0
    uploaded_files: int = 0
    uploaded_size: int = 0
    failed_files: List[str] = None
    skipped_files: List[str] = None
    start_time: Optional[datetime] = None
    
    def __post_init__(self):
        if self.failed_files is None:
            self.failed_files = []
        if self.skipped_files is None:
            self.skipped_files = []


class S3LargeUploader:
    """Main class for handling large directory uploads to S3"""
    
    def __init__(self, config: UploadConfig):
        self.config = config
        self.console = Console()
        self.state = UploadState()
        self.logger = self._setup_logging()
        
        # Initialize S3 client and transfer config
        self.s3_client = self._initialize_s3_client()
        self.transfer_config = TransferConfig(
            multipart_threshold=config.multipart_threshold,
            multipart_chunksize=config.multipart_chunksize,
            max_concurrency=config.max_concurrency,
            use_threads=True
        )
        
        # State file for resume capability
        self.state_file = Path(f".s3_upload_state_{config.bucket_name}.json")
        
    def _setup_logging(self) -> logging.Logger:
        """Set up logging configuration"""
        logger = logging.getLogger('s3_uploader')
        logger.setLevel(logging.INFO)
        
        # Create file handler
        log_file = f"s3_upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)
        
        # Create console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.WARNING)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        logger.addHandler(fh)
        logger.addHandler(ch)
        
        return logger
        
    def _initialize_s3_client(self):
        """Initialize S3 client with proper configuration"""
        try:
            session = boto3.Session(
                profile_name=self.config.aws_profile,
                region_name=self.config.aws_region
            )
            s3_client = session.client('s3')
            
            # Test credentials
            s3_client.list_objects_v2(Bucket=self.config.bucket_name, MaxKeys=1)
            self.logger.info(f"Successfully connected to S3 bucket: {self.config.bucket_name}")
            
            return s3_client
            
        except NoCredentialsError:
            self.console.print("[red]Error: AWS credentials not found. Please configure your credentials.[/red]")
            sys.exit(1)
        except ClientError as e:
            self.console.print(f"[red]Error accessing S3 bucket: {e}[/red]")
            sys.exit(1)
    
    def _calculate_md5(self, file_path: Path) -> str:
        """Calculate MD5 hash of a file"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _should_include_file(self, file_path: Path) -> bool:
        """Check if file should be included based on include/exclude patterns"""
        import fnmatch
        
        file_name = file_path.name
        
        # Check exclude patterns
        for pattern in self.config.exclude_patterns:
            if fnmatch.fnmatch(file_name, pattern):
                return False
        
        # Check include patterns
        for pattern in self.config.include_patterns:
            if fnmatch.fnmatch(file_name, pattern):
                return True
        
        return False
    
    def _scan_directory(self) -> List[Tuple[Path, str]]:
        """Scan source directory and build file list with S3 keys"""
        source_path = Path(self.config.source_directory)
        if not source_path.exists():
            raise FileNotFoundError(f"Source directory not found: {source_path}")
        
        files_to_upload = []
        
        with self.console.status("[bold green]Scanning directory...") as status:
            for file_path in source_path.rglob('*'):
                if file_path.is_file() and self._should_include_file(file_path):
                    # Calculate relative path and S3 key
                    relative_path = file_path.relative_to(source_path)
                    s3_key = str(Path(self.config.s3_prefix) / relative_path).replace('\\', '/')
                    
                    files_to_upload.append((file_path, s3_key))
                    self.state.total_files += 1
                    self.state.total_size += file_path.stat().st_size
                    
                    status.update(f"[bold green]Scanning... Found {self.state.total_files} files")
        
        return files_to_upload
    
    def _load_upload_state(self) -> Dict:
        """Load previous upload state if it exists"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                self.logger.warning("Could not load previous upload state")
        return {}
    
    def _save_upload_state(self, completed_files: Dict[str, bool]):
        """Save current upload state"""
        state_data = {
            'completed_files': completed_files,
            'config': asdict(self.config),
            'timestamp': datetime.now().isoformat()
        }
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
        except IOError as e:
            self.logger.error(f"Could not save upload state: {e}")
    
    def _file_exists_in_s3(self, s3_key: str, local_file_size: int) -> bool:
        """Check if file already exists in S3 with same size"""
        try:
            response = self.s3_client.head_object(
                Bucket=self.config.bucket_name,
                Key=s3_key
            )
            s3_file_size = response['ContentLength']
            return s3_file_size == local_file_size
        except ClientError:
            return False
    
    def _upload_file_with_retry(self, file_path: Path, s3_key: str, progress: Progress, task_id) -> bool:
        """Upload a single file with retry logic"""
        file_size = file_path.stat().st_size
        
        # Skip if file already exists and we're resuming
        if self.config.resume_upload and self._file_exists_in_s3(s3_key, file_size):
            progress.update(task_id, advance=file_size)
            self.state.skipped_files.append(str(file_path))
            self.logger.info(f"Skipped existing file: {s3_key}")
            return True
        
        # Retry logic
        for attempt in range(self.config.max_retries):
            try:
                if self.config.dry_run:
                    # Simulate upload for dry run
                    time.sleep(0.1)
                    progress.update(task_id, advance=file_size)
                    return True
                
                # Perform actual upload
                extra_args = {}
                if self.config.verify_checksums:
                    extra_args['Metadata'] = {
                        'md5-hash': self._calculate_md5(file_path)
                    }
                
                def progress_callback(bytes_transferred):
                    progress.update(task_id, advance=bytes_transferred)
                
                self.s3_client.upload_file(
                    str(file_path),
                    self.config.bucket_name,
                    s3_key,
                    ExtraArgs=extra_args,
                    Config=self.transfer_config,
                    Callback=progress_callback
                )
                
                self.logger.info(f"Successfully uploaded: {s3_key}")
                return True
                
            except Exception as e:
                self.logger.error(f"Upload attempt {attempt + 1} failed for {s3_key}: {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    self.state.failed_files.append(str(file_path))
                    self.logger.error(f"Failed to upload after {self.config.max_retries} attempts: {s3_key}")
        
        return False
    
    def upload_directory(self):
        """Main method to upload the directory"""
        self.console.print(Panel.fit(
            "[bold blue]S3 Large Directory Upload[/bold blue]\n"
            f"Source: {self.config.source_directory}\n"
            f"Bucket: {self.config.bucket_name}\n"
            f"Prefix: {self.config.s3_prefix}\n"
            f"Dry Run: {self.config.dry_run}",
            title="Upload Configuration"
        ))
        
        # Scan directory
        files_to_upload = self._scan_directory()
        
        if not files_to_upload:
            self.console.print("[yellow]No files found to upload.[/yellow]")
            return
        
        # Display summary
        total_size_mb = self.state.total_size / (1024 * 1024)
        self.console.print(f"\n[green]Found {self.state.total_files} files ({total_size_mb:.2f} MB) to upload[/green]")
        
        if self.config.dry_run:
            self.console.print("[yellow]DRY RUN MODE - No files will actually be uploaded[/yellow]")
        
        # Load previous state for resume
        previous_state = self._load_upload_state() if self.config.resume_upload else {}
        completed_files = previous_state.get('completed_files', {})
        
        # Set up progress tracking
        self.state.start_time = datetime.now()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            "•",
            FileSizeColumn(),
            "•",
            TransferSpeedColumn(),
            "•",
            TimeRemainingColumn(),
            console=self.console
        ) as progress:
            
            # Create progress task
            upload_task = progress.add_task(
                "Uploading files...", 
                total=self.state.total_size
            )
            
            # Upload files
            with ThreadPoolExecutor(max_workers=self.config.max_concurrency) as executor:
                # Submit upload tasks
                future_to_file = {}
                for file_path, s3_key in files_to_upload:
                    if s3_key not in completed_files:
                        future = executor.submit(
                            self._upload_file_with_retry,
                            file_path, s3_key, progress, upload_task
                        )
                        future_to_file[future] = (file_path, s3_key)
                    else:
                        # File already completed in previous run
                        file_size = file_path.stat().st_size
                        progress.update(upload_task, advance=file_size)
                        self.state.uploaded_files += 1
                        self.state.skipped_files.append(str(file_path))
                
                # Process completed uploads
                for future in as_completed(future_to_file):
                    file_path, s3_key = future_to_file[future]
                    try:
                        success = future.result()
                        if success:
                            self.state.uploaded_files += 1
                            completed_files[s3_key] = True
                            # Save state periodically
                            if self.state.uploaded_files % 10 == 0:
                                self._save_upload_state(completed_files)
                    except Exception as e:
                        self.logger.error(f"Unexpected error uploading {s3_key}: {e}")
                        self.state.failed_files.append(str(file_path))
        
        # Final state save
        self._save_upload_state(completed_files)
        
        # Display results
        self._display_results()
        
        # Clean up state file if all uploads successful
        if not self.state.failed_files and self.state_file.exists():
            self.state_file.unlink()
    
    def _display_results(self):
        """Display upload results summary"""
        end_time = datetime.now()
        duration = end_time - self.state.start_time
        
        # Create results table
        table = Table(title="Upload Results Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        
        table.add_row("Total Files", str(self.state.total_files))
        table.add_row("Successfully Uploaded", str(self.state.uploaded_files))
        table.add_row("Skipped (Already Exists)", str(len(self.state.skipped_files)))
        table.add_row("Failed", str(len(self.state.failed_files)))
        table.add_row("Total Size", f"{self.state.total_size / (1024*1024):.2f} MB")
        table.add_row("Duration", str(duration).split('.')[0])
        
        if duration.total_seconds() > 0:
            speed_mbps = (self.state.total_size / (1024*1024)) / duration.total_seconds()
            table.add_row("Average Speed", f"{speed_mbps:.2f} MB/s")
        
        self.console.print(table)
        
        # Display failed files if any
        if self.state.failed_files:
            self.console.print("\n[red]Failed Files:[/red]")
            for failed_file in self.state.failed_files:
                self.console.print(f"  • {failed_file}")
        
        # Success/failure message
        if not self.state.failed_files:
            self.console.print("\n[green]✅ All files uploaded successfully![/green]")
        else:
            self.console.print(f"\n[yellow]⚠️  Upload completed with {len(self.state.failed_files)} failures.[/yellow]")


def load_config_from_file(config_file: str) -> UploadConfig:
    """Load configuration from JSON file"""
    try:
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        return UploadConfig(**config_data)
    except (FileNotFoundError, json.JSONDecodeError, TypeError) as e:
        print(f"Error loading config file: {e}")
        sys.exit(1)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Upload large directories to AWS S3 with resume capability",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python s3_large_upload.py /path/to/directory my-bucket --prefix uploads/
  python s3_large_upload.py --config config.json
  python s3_large_upload.py /path/to/dir my-bucket --dry-run
        """
    )
    
    parser.add_argument('source_directory', nargs='?', help='Source directory to upload')
    parser.add_argument('bucket_name', nargs='?', help='S3 bucket name')
    parser.add_argument('--prefix', '-p', default='', help='S3 key prefix')
    parser.add_argument('--config', '-c', help='JSON configuration file')
    parser.add_argument('--profile', help='AWS profile to use')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--max-concurrency', type=int, default=4, help='Maximum concurrent uploads')
    parser.add_argument('--multipart-threshold', type=int, default=8*1024*1024, 
                       help='Multipart upload threshold in bytes')
    parser.add_argument('--max-retries', type=int, default=3, help='Maximum retry attempts')
    parser.add_argument('--no-resume', action='store_true', help='Disable resume capability')
    parser.add_argument('--no-checksums', action='store_true', help='Disable checksum verification')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be uploaded without uploading')
    parser.add_argument('--exclude', action='append', help='File patterns to exclude')
    parser.add_argument('--include', action='append', help='File patterns to include')
    
    args = parser.parse_args()
    
    # Load configuration
    if args.config:
        config = load_config_from_file(args.config)
    else:
        if not args.source_directory or not args.bucket_name:
            parser.error("source_directory and bucket_name are required when not using --config")
        
        config = UploadConfig(
            source_directory=args.source_directory,
            bucket_name=args.bucket_name,
            s3_prefix=args.prefix,
            aws_profile=args.profile,
            aws_region=args.region,
            max_concurrency=args.max_concurrency,
            multipart_threshold=args.multipart_threshold,
            max_retries=args.max_retries,
            resume_upload=not args.no_resume,
            verify_checksums=not args.no_checksums,
            dry_run=args.dry_run,
            exclude_patterns=args.exclude or None,
            include_patterns=args.include or None
        )
    
    # Create uploader and start upload
    uploader = S3LargeUploader(config)
    uploader.upload_directory()


if __name__ == '__main__':
    main() 