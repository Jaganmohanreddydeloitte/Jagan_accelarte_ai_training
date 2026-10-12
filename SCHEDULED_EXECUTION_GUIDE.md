# Running IDAMP Pipeline on a Schedule

Complete guide to run your pipeline automatically on a schedule with CLI parameters, logging, and error handling.

---

## 1. Create Command-Line Interface (agents/cli.py)

### New File: agents/cli.py

```python
"""
Command-line interface for IDAMP pipeline.

Allows running the pipeline programmatically with parameters instead of web UI.
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
import uuid

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import LANDING_DIR, REPORTS_DIR, DATA_DIR
from core.audit import AuditLogger
from agents.orchestrator import (
    run_until_bronze_sttm,
    run_bronze_to_silver_sttm,
    run_silver_to_gold_sttm,
    run_gold_and_report,
)


# ─── Logging Configuration ──────────────────────────────────────────────────

def setup_logging(log_dir: Path, run_id: str) -> logging.Logger:
    """Setup logging to file and console."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"cli_{run_id}.log"
    
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    
    # File handler (debug level)
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    
    # Console handler (info level)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    
    # Format
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger, log_file


# ─── CLI Functions ──────────────────────────────────────────────────────────

def validate_input_files(file_paths: list[str]) -> list[Path]:
    """Validate that input files exist and are readable."""
    validated_paths = []
    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not path.is_file():
            raise ValueError(f"Not a file: {file_path}")
        if not path.suffix.lower() in [".csv", ".xlsx", ".xls"]:
            raise ValueError(f"Unsupported file type: {path.suffix}")
        validated_paths.append(path)
    
    return validated_paths


def copy_files_to_landing(file_paths: list[Path]) -> list[str]:
    """Copy input files to LANDING_DIR."""
    LANDING_DIR.mkdir(parents=True, exist_ok=True)
    copied_paths = []
    
    for file_path in file_paths:
        dest_path = LANDING_DIR / file_path.name
        # Copy file
        import shutil
        shutil.copy2(file_path, dest_path)
        copied_paths.append(str(dest_path))
    
    return copied_paths


def run_pipeline(
    input_files: list[str],
    business_intent: str,
    run_id: str = None,
    email_recipients: str = None,
    logger: logging.Logger = None,
) -> dict:
    """
    Run the complete IDAMP pipeline.
    
    Args:
        input_files: List of CSV/Excel file paths
        business_intent: Business question/intent
        run_id: Unique run ID (generated if not provided)
        email_recipients: Comma-separated email addresses
        logger: Logger instance
    
    Returns:
        Pipeline state dict
    """
    if not logger:
        logger = logging.getLogger(__name__)
    
    # Generate run_id if not provided
    if not run_id:
        run_id = str(uuid.uuid4())
    
    logger.info(f"Starting IDAMP pipeline run: {run_id}")
    logger.info(f"Input files: {input_files}")
    logger.info(f"Business intent: {business_intent}")
    
    try:
        # Validate input files
        logger.info("Validating input files...")
        validated_paths = validate_input_files(input_files)
        logger.info(f"✓ Validated {len(validated_paths)} file(s)")
        
        # Copy to landing directory
        logger.info("Copying files to landing directory...")
        landing_paths = copy_files_to_landing(validated_paths)
        logger.info(f"✓ Copied {len(landing_paths)} file(s) to {LANDING_DIR}")
        
        # Phase 1: Profile & Bronze STTM
        logger.info("Phase 1: Running profiler and Bronze STTM generator...")
        state = run_until_bronze_sttm(landing_paths, business_intent)
        
        if state.get("error"):
            logger.error(f"Phase 1 failed: {state['error']}")
            return state
        
        logger.info(f"✓ Phase 1 complete. Profile: {state.get('profile_path')}")
        
        # Phase 2: Bronze Load & Silver STTM
        logger.info("Phase 2: Loading Bronze layer and generating Silver STTM...")
        state = run_bronze_to_silver_sttm(state)
        
        if state.get("error"):
            logger.error(f"Phase 2 failed: {state['error']}")
            return state
        
        logger.info(f"✓ Phase 2 complete. Silver STTM: {state.get('sttm_silver_path')}")
        
        # Phase 3: Silver Load & Gold STTM
        logger.info("Phase 3: Loading Silver layer and generating Gold STTM...")
        state = run_silver_to_gold_sttm(state)
        
        if state.get("error"):
            logger.error(f"Phase 3 failed: {state['error']}")
            return state
        
        logger.info(f"✓ Phase 3 complete. Gold STTM: {state.get('sttm_gold_path')}")
        
        # Phase 4: Gold Load & Report
        logger.info("Phase 4: Loading Gold layer and generating report...")
        state = run_gold_and_report(state)
        
        if state.get("error"):
            logger.error(f"Phase 4 failed: {state['error']}")
            return state
        
        logger.info(f"✓ Phase 4 complete. Report: {state.get('report_path')}")
        
        # Summary
        logger.info("=" * 70)
        logger.info("PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("=" * 70)
        logger.info(f"Run ID: {run_id}")
        logger.info(f"Report: {state.get('report_path')}")
        logger.info(f"Gold tables: {state.get('gold_output_paths')}")
        logger.info("=" * 70)
        
        return state
    
    except Exception as e:
        logger.error(f"Pipeline failed with exception: {e}", exc_info=True)
        
        # Send failure email if configured
        try:
            from core.email_notifier import send_pipeline_completion_email
            send_pipeline_completion_email(
                run_id=run_id,
                report_path="",
                status="failed",
                error_message=str(e),
            )
        except Exception as email_error:
            logger.warning(f"Failed to send error email: {email_error}")
        
        return {"error": str(e), "run_id": run_id, "status": "failed"}


# ─── Main CLI Entry Point ───────────────────────────────────────────────────

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run IDAMP pipeline from command line with parameters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic run with single file
  python -m agents.cli --files data.csv --intent "Analyze customer trends"
  
  # Multiple files with email
  python -m agents.cli --files file1.csv file2.xlsx --intent "Data analysis" --email admin@company.com
  
  # With custom run ID and log directory
  python -m agents.cli --files data.csv --intent "Analysis" --run-id my-run-001 --log-dir logs/
        """,
    )
    
    parser.add_argument(
        "--files",
        nargs="+",
        required=True,
        help="Input CSV/Excel files (space-separated)",
    )
    
    parser.add_argument(
        "--intent",
        required=True,
        help="Business question/intent for the analysis",
    )
    
    parser.add_argument(
        "--run-id",
        default=None,
        help="Unique run ID (generated if not provided)",
    )
    
    parser.add_argument(
        "--email",
        default=None,
        help="Email recipient(s) for completion notification (comma-separated)",
    )
    
    parser.add_argument(
        "--log-dir",
        default="logs",
        help="Directory for log files (default: logs/)",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_dir = Path(args.log_dir)
    run_id = args.run_id or str(uuid.uuid4())
    logger, log_file = setup_logging(log_dir, run_id)
    
    logger.info(f"Log file: {log_file}")
    
    # Run pipeline
    state = run_pipeline(
        input_files=args.files,
        business_intent=args.intent,
        run_id=run_id,
        email_recipients=args.email,
        logger=logger,
    )
    
    # Exit with appropriate code
    if state.get("error"):
        logger.error("Pipeline execution failed")
        sys.exit(1)
    else:
        logger.info("Pipeline execution completed successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()
```

---

## 2. Using the CLI

### Basic Usage

```bash
# Single file
python -m agents.cli --files data.csv --intent "What are the top customers?"

# Multiple files
python -m agents.cli --files file1.csv file2.xlsx file3.csv --intent "Analyze trends"

# With custom run ID
python -m agents.cli --files data.csv --intent "Analysis" --run-id my-analysis-001

# With email notification
python -m agents.cli --files data.csv --intent "Analysis" --email admin@company.com

# With custom log directory
python -m agents.cli --files data.csv --intent "Analysis" --log-dir /var/log/idamp/

# All options
python -m agents.cli \
  --files /data/input1.csv /data/input2.xlsx \
  --intent "Customer analysis" \
  --run-id weekly-run-001 \
  --email data-team@company.com,admin@company.com \
  --log-dir /var/log/idamp/
```

---

## 3. Scheduling with Cron (Linux/Mac)

### Setup Cron Job

```bash
# Open crontab editor
crontab -e

# Add this line to run every Monday at 9 AM
0 9 * * 1 cd /path/to/Accelerate_with_ai_lab && python -m agents.cli --files /data/input.csv --intent "Weekly analysis" --log-dir /var/log/idamp/ >> /var/log/idamp/cron.log 2>&1
```

### Common Cron Schedules

```bash
# Every day at 9 AM
0 9 * * * cd /path/to/project && python -m agents.cli --files /data/input.csv --intent "Daily analysis"

# Every Monday at 9 AM
0 9 * * 1 cd /path/to/project && python -m agents.cli --files /data/input.csv --intent "Weekly analysis"

# First day of month at 8 AM
0 8 1 * * cd /path/to/project && python -m agents.cli --files /data/input.csv --intent "Monthly analysis"

# Every 6 hours
0 */6 * * * cd /path/to/project && python -m agents.cli --files /data/input.csv --intent "Regular analysis"

# Every weekday at 5 PM
0 17 * * 1-5 cd /path/to/project && python -m agents.cli --files /data/input.csv --intent "Weekday analysis"
```

### Verify Cron Job

```bash
# List all cron jobs
crontab -l

# Check cron logs
tail -f /var/log/syslog | grep CRON

# Or on macOS
log stream --predicate 'process == "cron"' --level debug
```

---

## 4. Scheduling with Task Scheduler (Windows)

### Create Scheduled Task

**PowerShell (Run as Administrator):**

```powershell
# Define task details
$TaskName = "IDAMP-Pipeline-Daily"
$TaskPath = "\IDAMP\"
$TaskDescription = "Run IDAMP pipeline daily at 9 AM"

# Define action (what to run)
$Action = New-ScheduledTaskAction `
  -Execute "python.exe" `
  -Argument "-m agents.cli --files C:\data\input.csv --intent `"Daily analysis`" --log-dir C:\logs\idamp\" `
  -WorkingDirectory "C:\path\to\Accelerate_with_ai_lab"

# Define trigger (when to run)
$Trigger = New-ScheduledTaskTrigger `
  -Daily `
  -At "09:00"

# Define principal (who runs it)
$Principal = New-ScheduledTaskPrincipal `
  -UserID "SYSTEM" `
  -LogonType S3

# Create task
Register-ScheduledTask `
  -TaskName $TaskName `
  -TaskPath $TaskPath `
  -Action $Action `
  -Trigger $Trigger `
  -Principal $Principal `
  -Description $TaskDescription `
  -Force
```

**Using GUI:**

1. Open Task Scheduler (Start → Task Scheduler)
2. Click "Create Basic Task"
3. Name: "IDAMP Pipeline Daily"
4. Trigger: Daily at 9:00 AM
5. Action: Start a program
   - Program: `python.exe`
   - Arguments: `-m agents.cli --files C:\data\input.csv --intent "Daily analysis" --log-dir C:\logs\idamp\`
   - Start in: `C:\path\to\Accelerate_with_ai_lab`
6. Conditions: Check "Run only if user is logged on"
7. Settings: "If the task fails, retry after 1 hour" (3 times)
8. Click OK

### Common Task Schedules (Windows)

```powershell
# Daily
$Trigger = New-ScheduledTaskTrigger -Daily -At "09:00"

# Weekly (Mondays)
$Trigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek Monday -At "09:00"

# Monthly (1st of month)
$Trigger = New-ScheduledTaskTrigger -Monthly -At "08:00" -DaysOfMonth 1

# Every 6 hours
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 6) -RepetitionDuration (New-TimeSpan -Days 1)
```

---

## 5. Passing Parameters Dynamically

### Script to Run Multiple Analyses

Create `run_scheduled_pipeline.sh` (Linux/Mac):

```bash
#!/bin/bash
# Run IDAMP pipeline with different parameters

PROJECT_DIR="/path/to/Accelerate_with_ai_lab"
LOG_DIR="/var/log/idamp"
DATA_DIR="/data/input"

cd $PROJECT_DIR

# Monday: Customer analysis
if [ $(date +%u) -eq 1 ]; then
    python -m agents.cli \
      --files $DATA_DIR/customers.csv \
      --intent "Customer segmentation and RFM analysis" \
      --run-id "weekly-customers-$(date +%Y%m%d)" \
      --email analytics@company.com \
      --log-dir $LOG_DIR
fi

# Wednesday: Sales analysis
if [ $(date +%u) -eq 3 ]; then
    python -m agents.cli \
      --files $DATA_DIR/sales.csv $DATA_DIR/products.csv \
      --intent "Sales trends and product performance" \
      --run-id "weekly-sales-$(date +%Y%m%d)" \
      --email sales@company.com \
      --log-dir $LOG_DIR
fi

# Friday: Inventory analysis
if [ $(date +%u) -eq 5 ]; then
    python -m agents.cli \
      --files $DATA_DIR/inventory.csv \
      --intent "Inventory levels and reorder points" \
      --run-id "weekly-inventory-$(date +%Y%m%d)" \
      --email operations@company.com \
      --log-dir $LOG_DIR
fi
```

Make executable and add to cron:
```bash
chmod +x run_scheduled_pipeline.sh
# In crontab: 0 9 * * * /path/to/run_scheduled_pipeline.sh
```

### Windows Batch Script

Create `run_scheduled_pipeline.bat`:

```batch
@echo off
REM Run IDAMP pipeline with different parameters

set PROJECT_DIR=C:\path\to\Accelerate_with_ai_lab
set LOG_DIR=C:\logs\idamp
set DATA_DIR=C:\data\input

cd /d %PROJECT_DIR%

REM Monday: Customer analysis
for /f %%a in ('powershell -Command "[int][System.DayOfWeek]::Monday"') do set MONDAY=%%a
for /f %%b in ('powershell -Command "[int](Get-Date).DayOfWeek"') do set TODAY=%%b

if %TODAY%==%MONDAY% (
    python -m agents.cli ^
      --files %DATA_DIR%\customers.csv ^
      --intent "Customer segmentation and RFM analysis" ^
      --run-id "weekly-customers-%DATE:~-4,4%%DATE:~-10,2%%DATE:~-7,2%" ^
      --email analytics@company.com ^
      --log-dir %LOG_DIR%
)

REM Wednesday: Sales analysis
if %TODAY%==3 (
    python -m agents.cli ^
      --files %DATA_DIR%\sales.csv %DATA_DIR%\products.csv ^
      --intent "Sales trends and product performance" ^
      --run-id "weekly-sales-%DATE:~-4,4%%DATE:~-10,2%%DATE:~-7,2%" ^
      --email sales@company.com ^
      --log-dir %LOG_DIR%
)

REM Friday: Inventory analysis
if %TODAY%==5 (
    python -m agents.cli ^
      --files %DATA_DIR%\inventory.csv ^
      --intent "Inventory levels and reorder points" ^
      --run-id "weekly-inventory-%DATE:~-4,4%%DATE:~-10,2%%DATE:~-7,2%" ^
      --email operations@company.com ^
      --log-dir %LOG_DIR%
)
```

---

## 6. Logging and Error Handling

### Log File Location

```
logs/
├── cli_abc123de-1234-5678-90ab-cdef12345678.log
├── cli_weekly-run-001.log
└── cli_manual-test-001.log
```

### Log File Contents

```
2026-10-07 09:00:00,123 - agents.cli - INFO - Starting IDAMP pipeline run: abc123de
2026-10-07 09:00:00,456 - agents.cli - INFO - Input files: ['/data/input.csv']
2026-10-07 09:00:00,789 - agents.cli - INFO - Business intent: What are the top customers?
2026-10-07 09:00:01,012 - agents.cli - INFO - Validating input files...
2026-10-07 09:00:01,234 - agents.cli - INFO - ✓ Validated 1 file(s)
2026-10-07 09:00:01,456 - agents.cli - INFO - Copying files to landing directory...
2026-10-07 09:00:01,678 - agents.cli - INFO - ✓ Copied 1 file(s) to /path/to/data/landing
2026-10-07 09:00:01,900 - agents.cli - INFO - Phase 1: Running profiler and Bronze STTM generator...
...
2026-10-07 09:15:30,123 - agents.cli - INFO - ======================================================================
2026-10-07 09:15:30,345 - agents.cli - INFO - PIPELINE COMPLETED SUCCESSFULLY
2026-10-07 09:15:30,567 - agents.cli - INFO - ======================================================================
2026-10-07 09:15:30,789 - agents.cli - INFO - Run ID: abc123de
2026-10-07 09:15:31,012 - agents.cli - INFO - Report: /path/to/data/reports/report_abc123de.html
2026-10-07 09:15:31,234 - agents.cli - INFO - Gold tables: ['/path/to/data/gold_layer/table1.parquet', ...]
```

### Error Handling

CLI automatically:
- ✅ Validates input files before running
- ✅ Catches pipeline exceptions
- ✅ Logs full traceback to file
- ✅ Sends failure email if configured
- ✅ Exits with error code 1 on failure (for monitoring)
- ✅ Exits with code 0 on success

---

## 7. Testing the CLI

### Test 1: Basic Execution

```bash
python -m agents.cli --files test_data.csv --intent "Test analysis"
```

Expected output:
```
2026-10-07 10:00:00 - agents.cli - INFO - Starting IDAMP pipeline run: ...
2026-10-07 10:00:00 - agents.cli - INFO - ✓ Validated 1 file(s)
...
2026-10-07 10:02:30 - agents.cli - INFO - PIPELINE COMPLETED SUCCESSFULLY
```

### Test 2: With Multiple Files

```bash
python -m agents.cli --files file1.csv file2.xlsx --intent "Multi-file analysis" --run-id test-run-001
```

### Test 3: Error Handling

```bash
# Non-existent file (should fail)
python -m agents.cli --files /nonexistent/file.csv --intent "Analysis"
```

Expected output:
```
2026-10-07 10:00:00 - agents.cli - ERROR - File not found: /nonexistent/file.csv
...
2026-10-07 10:00:00 - agents.cli - ERROR - Pipeline execution failed
```

Exit code: 1

### Test 4: Cron Dry Run (Linux/Mac)

```bash
# Test that cron command works
0 9 * * 1 cd /path/to/project && python -m agents.cli --files /data/input.csv --intent "Weekly analysis" >> /tmp/cron-test.log 2>&1
```

Then check:
```bash
cat /tmp/cron-test.log
```

---

## 8. Production Checklist

- [ ] Create logs directory: `mkdir logs`
- [ ] Create data/input directory: `mkdir -p data/input`
- [ ] Test CLI locally: `python -m agents.cli --files ...`
- [ ] Verify email notifications configured (from EMAIL_NOTIFICATIONS_GUIDE.md)
- [ ] Create scheduled task/cron job
- [ ] Verify first scheduled run completes
- [ ] Check logs directory for log file: `ls -la logs/`
- [ ] Check email received successfully
- [ ] Verify data in data/reports/ and data/gold_layer/
- [ ] Set up log rotation (see below)

---

## 9. Log Rotation (Production)

### Linux/Mac (logrotate)

Create `/etc/logrotate.d/idamp`:

```
/var/log/idamp/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 nobody nobody
}
```

Then:
```bash
sudo logrotate /etc/logrotate.d/idamp
```

### Windows (PowerShell)

Create `rotate_logs.ps1`:

```powershell
$LogDir = "C:\logs\idamp"
$MaxAgeInDays = 7

Get-ChildItem -Path $LogDir -Filter "cli_*.log" | Where-Object {
    $_.LastWriteTime -lt (Get-Date).AddDays(-$MaxAgeInDays)
} | Remove-Item
```

Add to Task Scheduler to run weekly.

---

## Summary of Files

| File | Type | Purpose |
|------|------|---------|
| `agents/cli.py` | NEW | CLI entry point with argparse |
| `run_scheduled_pipeline.sh` | NEW | Script for conditional scheduling |
| `run_scheduled_pipeline.bat` | NEW | Windows batch script |
| crontab entry | CONFIG | Linux/Mac scheduling |
| Task Scheduler | CONFIG | Windows scheduling |
| `logs/` directory | OUTPUT | Log files from CLI runs |

---

## Quick Start

```bash
# 1. Create CLI module
# (Copy agents/cli.py from above)

# 2. Test locally
python -m agents.cli --files data.csv --intent "Analysis"

# 3. Create logs directory
mkdir logs

# 4. Create scheduled task (example: daily at 9 AM)
# Linux/Mac:
crontab -e
# Add: 0 9 * * * cd /path/to/project && python -m agents.cli --files /data/input.csv --intent "Daily analysis" --log-dir logs/

# Windows (PowerShell as Admin):
# See section 4 for PowerShell commands

# 5. Verify it runs
# Check logs/ directory after scheduled time
ls logs/

# 6. View logs
tail -f logs/cli_*.log
```

Your IDAMP pipeline now runs **automatically on schedule**! 🚀📅
