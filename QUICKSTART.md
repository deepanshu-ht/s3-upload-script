# Quick Start Guide

Get started with S3 Large Directory Upload in just a few minutes!

## Prerequisites
- Python 3.7+
- AWS credentials configured
- S3 bucket with write permissions

## Installation

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Make script executable
chmod +x s3_large_upload.py
```

## 5-Minute Demo

### Step 1: Create Test Data
```bash
# Create test files to upload
python test_upload.py --num-files 50 --max-size 2 --create-only
```

### Step 2: Dry Run Test
```bash
# Test upload (dry run - no actual upload)
python s3_large_upload.py /path/to/test/directory your-bucket-name --dry-run
```

### Step 3: Real Upload
```bash
# Remove --dry-run when ready for actual upload
python s3_large_upload.py /path/to/test/directory your-bucket-name --prefix uploads/
```

## Common Use Cases

### Backup Home Directory
```bash
python s3_large_upload.py ~/Documents my-backup-bucket --prefix home-backup/ \
  --exclude "*.log" --exclude ".DS_Store"
```

### Large Media Upload
```bash
python s3_large_upload.py /media/photos my-media-bucket \
  --max-concurrency 8 --multipart-threshold 16777216
```

### Configuration File Setup
```bash
# 1. Copy example config
cp config.example.json my-config.json

# 2. Edit with your settings
# 3. Run upload
python s3_large_upload.py --config my-config.json
```

## Key Features Demo

**Resume Interrupted Upload:**
- Script automatically saves progress
- Restart with same command to resume
- Skips already uploaded files

**Progress Tracking:**
- Real-time progress bar
- Transfer speed display
- ETA calculation
- Upload statistics

**Error Handling:**
- Automatic retry with backoff
- Detailed error logging
- Graceful failure handling

## Next Steps

1. Read the full [README.md](README.md) for complete documentation
2. Customize settings in `config.example.json`
3. Test with your own directories using `--dry-run`
4. Set up automated backups with cron/scheduled tasks

## Troubleshooting

**Permission Errors:**
```bash
aws s3 ls s3://your-bucket-name  # Test access
```

**Memory Issues:**
- Reduce `max_concurrency` (try 2-4)
- Reduce `multipart_chunksize`

**Slow Uploads:**
- Increase `max_concurrency` (try 6-8)
- Check AWS region proximity
- Verify network bandwidth

---

**Need help?** Check the full documentation in [README.md](README.md) or create an issue. 