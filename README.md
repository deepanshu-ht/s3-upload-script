# S3 Large Directory Upload Script

A robust Python script for uploading large directories to AWS S3 with advanced features like resume capability, progress tracking, multipart uploads, and comprehensive error handling.

## Features

✅ **Large File Handling**
- Automatic multipart uploads for large files
- Memory-efficient processing
- Configurable chunk sizes and thresholds

✅ **Robustness & Resume Capability**
- Resume interrupted uploads automatically
- Retry failed transfers with exponential backoff
- Comprehensive error logging
- State persistence across sessions

✅ **Progress Tracking**
- Real-time progress bar with transfer speed
- Detailed upload statistics
- File count and size information
- Estimated time remaining

✅ **Flexible Configuration**
- Command-line arguments or JSON config files
- File include/exclude patterns
- Customizable S3 paths and AWS settings
- Dry-run mode for testing

✅ **File Integrity**
- MD5 checksum verification
- Skip files that already exist (with size verification)
- Comprehensive upload validation

## Installation

### Prerequisites

- Python 3.7 or higher
- AWS CLI configured with appropriate credentials
- An S3 bucket with write permissions

### Setup

1. **Clone or download the script files:**
   ```bash
   # Download the script files to your desired directory
   curl -O https://raw.githubusercontent.com/your-repo/s3_large_upload.py
   curl -O https://raw.githubusercontent.com/your-repo/requirements.txt
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure AWS credentials** (choose one method):

   **Option A: AWS CLI**
   ```bash
   aws configure
   ```

   **Option B: Environment variables**
   ```bash
   export AWS_ACCESS_KEY_ID=your_access_key
   export AWS_SECRET_ACCESS_KEY=your_secret_key
   export AWS_DEFAULT_REGION=us-east-1
   ```

   **Option C: AWS Profile**
   ```bash
   aws configure --profile myprofile
   ```

4. **Verify S3 access:**
   ```bash
   aws s3 ls s3://your-bucket-name
   ```

## Usage

### Basic Usage

```bash
# Upload directory to S3 bucket
python s3_large_upload.py /path/to/directory my-bucket-name

# Upload with custom S3 prefix
python s3_large_upload.py /path/to/directory my-bucket-name --prefix backups/2024/

# Dry run to see what would be uploaded
python s3_large_upload.py /path/to/directory my-bucket-name --dry-run
```

### Advanced Usage

```bash
# Use specific AWS profile and region
python s3_large_upload.py /path/to/directory my-bucket-name \
  --profile production --region eu-west-1

# Customize concurrency and retry settings
python s3_large_upload.py /path/to/directory my-bucket-name \
  --max-concurrency 8 --max-retries 5

# Exclude specific file patterns
python s3_large_upload.py /path/to/directory my-bucket-name \
  --exclude "*.log" --exclude "*.tmp" --exclude ".DS_Store"

# Use configuration file
python s3_large_upload.py --config config.json
```

### Configuration File Usage

Create a `config.json` file (see `config.example.json`):

```json
{
  "source_directory": "/path/to/your/large/directory",
  "bucket_name": "your-s3-bucket-name",
  "s3_prefix": "uploads/backup-2024/",
  "aws_profile": "default",
  "aws_region": "us-east-1",
  "max_concurrency": 4,
  "verify_checksums": true,
  "resume_upload": true,
  "exclude_patterns": [".DS_Store", "*.tmp", "*.log"],
  "dry_run": false
}
```

Then run:
```bash
python s3_large_upload.py --config config.json
```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `source_directory` | Source directory to upload | Required |
| `bucket_name` | S3 bucket name | Required |
| `--prefix, -p` | S3 key prefix | "" |
| `--config, -c` | JSON configuration file | None |
| `--profile` | AWS profile to use | None |
| `--region` | AWS region | us-east-1 |
| `--max-concurrency` | Maximum concurrent uploads | 4 |
| `--multipart-threshold` | Multipart upload threshold (bytes) | 8MB |
| `--max-retries` | Maximum retry attempts | 3 |
| `--no-resume` | Disable resume capability | False |
| `--no-checksums` | Disable checksum verification | False |
| `--dry-run` | Show what would be uploaded | False |
| `--exclude` | File patterns to exclude | None |
| `--include` | File patterns to include | None |

## Resume Capability

The script automatically saves its state and can resume interrupted uploads:

1. **Automatic State Saving**: Progress is saved every 10 successful uploads
2. **State File**: `.s3_upload_state_{bucket_name}.json` in the current directory
3. **Resume Detection**: On restart, the script checks for existing files in S3
4. **Size Verification**: Files are skipped only if they exist with the same size

To disable resume capability:
```bash
python s3_large_upload.py /path/to/directory my-bucket --no-resume
```

## File Patterns

Use glob patterns to include or exclude files:

```bash
# Exclude common temporary files
python s3_large_upload.py /path/to/directory my-bucket \
  --exclude "*.tmp" --exclude "*.log" --exclude ".DS_Store"

# Include only specific file types
python s3_large_upload.py /path/to/directory my-bucket \
  --include "*.jpg" --include "*.png" --include "*.pdf"
```

## Performance Tuning

### For Large Files (>100MB each)
```json
{
  "multipart_threshold": 16777216,
  "multipart_chunksize": 16777216,
  "max_concurrency": 8
}
```

### For Many Small Files
```json
{
  "multipart_threshold": 8388608,
  "multipart_chunksize": 8388608,
  "max_concurrency": 12
}
```

### For Limited Bandwidth
```json
{
  "max_concurrency": 2,
  "max_retries": 5,
  "retry_delay": 2.0
}
```

## Logging

The script creates detailed logs:

- **Log File**: `s3_upload_YYYYMMDD_HHMMSS.log`
- **Log Levels**: INFO for successful operations, ERROR for failures
- **Content**: Upload attempts, retries, errors, and timing information

## Error Handling

The script handles various error scenarios:

- **Network interruptions**: Automatic retry with exponential backoff
- **Authentication errors**: Clear error messages and exit
- **Permission errors**: Logged with specific file information
- **Large file timeouts**: Multipart upload chunking
- **Disk space issues**: Graceful handling and logging

## Examples

### Example 1: Basic Backup
```bash
# Backup home directory to S3
python s3_large_upload.py /Users/username/Documents my-backup-bucket --prefix home-backup/
```

### Example 2: Media Library Upload
```bash
# Upload media files with exclusions
python s3_large_upload.py /media/photos my-media-bucket \
  --exclude "*.tmp" --exclude ".DS_Store" \
  --max-concurrency 6
```

### Example 3: Production Data Migration
```json
{
  "source_directory": "/var/data/production",
  "bucket_name": "company-data-archive",
  "s3_prefix": "production-backup/2024-01-15/",
  "aws_profile": "production",
  "aws_region": "us-west-2",
  "max_concurrency": 8,
  "verify_checksums": true,
  "exclude_patterns": ["*.log", "*.tmp", "cache/*"]
}
```

## Troubleshooting

### Common Issues

**1. AWS Credentials Not Found**
```
Error: AWS credentials not found. Please configure your credentials.
```
Solution: Configure AWS CLI or set environment variables.

**2. S3 Bucket Access Denied**
```
Error accessing S3 bucket: An error occurred (AccessDenied)
```
Solution: Verify bucket permissions and AWS credentials.

**3. Large File Upload Failures**
```
Upload attempt failed: An error occurred (RequestTimeout)
```
Solution: Increase multipart threshold or reduce concurrency.

**4. Out of Memory Errors**
Solution: Reduce `max_concurrency` and `multipart_chunksize`.

### Performance Issues

**Slow Upload Speeds:**
1. Increase `max_concurrency` (try 6-8)
2. Use appropriate AWS region
3. Check network bandwidth
4. Optimize multipart settings

**High Memory Usage:**
1. Reduce `max_concurrency`
2. Reduce `multipart_chunksize`
3. Process smaller batches

## Security Considerations

- **Credentials**: Never commit AWS credentials to version control
- **Permissions**: Use IAM roles with minimal required permissions
- **Logging**: Log files may contain file paths - secure appropriately
- **State Files**: Contain upload progress - clean up when not needed

## Contributing

To contribute to this script:

1. Test with various file sizes and directory structures
2. Report issues with detailed error logs
3. Suggest performance improvements
4. Add support for additional cloud storage providers

## License

This script is provided as-is for educational and practical use. Modify as needed for your specific requirements.

---

**Note**: Always test with a small dataset and `--dry-run` option before uploading large directories to production S3 buckets. 