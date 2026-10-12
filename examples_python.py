#!/usr/bin/env python3
"""
IDAMP REST API - Python Example Script

This script demonstrates how to interact with the REST API:
1. Upload a file
2. Poll for completion
3. Approve STTM at each layer
4. Download the report

Usage:
    python examples_python.py <csv_file> "<business_intent>"

Example:
    python examples_python.py customers.csv "Find high-value segments"
"""

import sys
import time
import json
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("ERROR: requests module not found")
    print("Install it with: pip install requests")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

API_BASE = "http://localhost:8000/api/v1"
POLL_INTERVAL = 5  # seconds
MAX_WAIT_TIME = 3600  # 1 hour


# ═══════════════════════════════════════════════════════════════════════════════
# API Client Class
# ═══════════════════════════════════════════════════════════════════════════════

class IdampApiClient:
    """Simple client for IDAMP REST API."""
    
    def __init__(self, base_url: str = API_BASE):
        self.base_url = base_url
        self.session = requests.Session()
    
    def health_check(self) -> bool:
        """Check if API is running."""
        try:
            response = self.session.get(f"{self.base_url}/../health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def upload_file(
        self,
        file_path: str,
        business_intent: str,
        user_email: str = "api_user"
    ) -> dict:
        """
        Upload a file and start a new run.
        
        Returns:
            Dictionary with run_id and other metadata
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, "rb") as f:
            files = {"file": f}
            data = {
                "business_intent": business_intent,
                "user_email": user_email
            }
            
            response = self.session.post(
                f"{self.base_url}/runs/upload",
                files=files,
                data=data
            )
        
        if response.status_code != 200:
            raise Exception(f"Upload failed: {response.text}")
        
        return response.json()
    
    def get_status(self, run_id: str) -> dict:
        """Get current status of a run."""
        response = self.session.get(f"{self.base_url}/runs/{run_id}")
        
        if response.status_code != 200:
            raise Exception(f"Status check failed: {response.text}")
        
        return response.json()
    
    def list_runs(self, status: Optional[str] = None, limit: int = 20) -> dict:
        """List all runs, optionally filtered by status."""
        params = {"limit": limit}
        if status:
            params["status"] = status
        
        response = self.session.get(f"{self.base_url}/runs", params=params)
        
        if response.status_code != 200:
            raise Exception(f"List failed: {response.text}")
        
        return response.json()
    
    def approve_sttm(self, run_id: str, layer: str) -> dict:
        """Approve STTM at a specific layer (bronze, silver, or gold)."""
        response = self.session.post(
            f"{self.base_url}/runs/{run_id}/approve",
            json={"layer": layer}
        )
        
        if response.status_code != 200:
            raise Exception(f"Approval failed: {response.text}")
        
        return response.json()
    
    def download_report(self, run_id: str, output_path: str) -> str:
        """Download the final report."""
        response = self.session.get(f"{self.base_url}/runs/{run_id}/report")
        
        if response.status_code != 200:
            raise Exception(f"Download failed: {response.text}")
        
        # Save to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(response.content)
        
        return str(output_file)
    
    def download_artifact(
        self,
        run_id: str,
        artifact_type: str,
        output_path: str
    ) -> str:
        """Download an artifact (bronze_sttm, silver_sttm, gold_sttm, profile, report)."""
        response = self.session.get(
            f"{self.base_url}/runs/{run_id}/artifacts/{artifact_type}"
        )
        
        if response.status_code != 200:
            raise Exception(f"Download failed: {response.text}")
        
        # Save to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(response.content)
        
        return str(output_file)
    
    def cancel_run(self, run_id: str) -> dict:
        """Cancel an in-progress run."""
        response = self.session.post(f"{self.base_url}/runs/{run_id}/cancel")
        
        if response.status_code != 200:
            raise Exception(f"Cancellation failed: {response.text}")
        
        return response.json()
    
    def delete_run(self, run_id: str, delete_files: bool = False) -> dict:
        """Delete a run."""
        response = self.session.delete(
            f"{self.base_url}/runs/{run_id}",
            params={"delete_files": delete_files}
        )
        
        if response.status_code != 200:
            raise Exception(f"Deletion failed: {response.text}")
        
        return response.json()


# ═══════════════════════════════════════════════════════════════════════════════
# Main Workflow
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Main workflow: upload, track, approve, and download."""
    
    if len(sys.argv) < 3:
        print("Usage: python examples_python.py <csv_file> '<business_intent>'")
        print("")
        print("Example:")
        print("  python examples_python.py customers.csv 'Find high-value segments'")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    business_intent = " ".join(sys.argv[2:])
    
    # Create API client
    client = IdampApiClient()
    
    # 1. Check if API is running
    print("=" * 80)
    print("1. Checking API health...")
    print("=" * 80)
    
    if not client.health_check():
        print("ERROR: API server is not running")
        print("Start it with: python app/run_api.py")
        sys.exit(1)
    
    print("✓ API is running at", API_BASE)
    print()
    
    # 2. Upload file
    print("=" * 80)
    print("2. Uploading file and starting run...")
    print("=" * 80)
    
    try:
        upload_result = client.upload_file(csv_file, business_intent)
        run_id = upload_result["run_id"]
        
        print(f"✓ Upload successful")
        print(f"  Run ID: {run_id}")
        print(f"  File: {upload_result['file_name']}")
        print(f"  Size: {upload_result['file_size_bytes']:,} bytes")
        print(f"  Status: {upload_result['status']}")
        print()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    
    # 3. Poll for completion
    print("=" * 80)
    print("3. Tracking progress (waiting for run to complete)...")
    print("=" * 80)
    
    start_time = time.time()
    last_phase = None
    
    while True:
        elapsed = time.time() - start_time
        
        if elapsed > MAX_WAIT_TIME:
            print(f"ERROR: Run did not complete within {MAX_WAIT_TIME}s")
            sys.exit(1)
        
        try:
            status = client.get_status(run_id)
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(1)
        
        # Show update if phase changed
        if status["phase"] != last_phase:
            last_phase = status["phase"]
            print(f"\n  Phase: {status['phase'].upper()}")
        
        # Show progress bar
        progress = status["progress_percent"]
        bar_length = 40
        filled = int(bar_length * progress / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        print(f"  [{bar}] {progress}% - {status['message']}", end="\r")
        
        # Check if done
        if status["status"] in ["completed", "failed"]:
            print()  # Newline after progress bar
            print()
            break
        
        time.sleep(POLL_INTERVAL)
    
    # 4. Check final status
    print("=" * 80)
    print(f"4. Run {status['status'].upper()}")
    print("=" * 80)
    
    print(f"  Status: {status['status']}")
    print(f"  Duration: {(time.time() - start_time):.1f} seconds")
    
    if status["status"] == "failed":
        print(f"  Error: {status['error_message']}")
        sys.exit(1)
    
    print()
    
    # 5. Approve STTM at each layer
    print("=" * 80)
    print("5. Approving STTM transformations...")
    print("=" * 80)
    
    for layer in ["bronze", "silver", "gold"]:
        try:
            approval = client.approve_sttm(run_id, layer)
            print(f"✓ {layer.upper()}: {approval['message']}")
        except Exception as e:
            print(f"⚠ {layer.upper()}: {e}")
    
    print()
    
    # 6. Download report
    print("=" * 80)
    print("6. Downloading final report...")
    print("=" * 80)
    
    try:
        report_path = client.download_report(run_id, f"report_{run_id}.html")
        print(f"✓ Report saved: {report_path}")
    except Exception as e:
        print(f"⚠ Report download: {e}")
    
    print()
    
    # 7. Download artifacts (optional)
    print("=" * 80)
    print("7. Downloading artifacts...")
    print("=" * 80)
    
    artifacts = ["profile", "bronze_sttm", "silver_sttm", "gold_sttm"]
    
    for artifact_type in artifacts:
        try:
            artifact_path = client.download_artifact(
                run_id,
                artifact_type,
                f"artifacts/{artifact_type}_{run_id}.json"
            )
            print(f"✓ {artifact_type}: {artifact_path}")
        except Exception as e:
            print(f"⚠ {artifact_type}: {e}")
    
    print()
    
    # Summary
    print("=" * 80)
    print("✓ WORKFLOW COMPLETE!")
    print("=" * 80)
    print(f"  Run ID: {run_id}")
    print(f"  Report: report_{run_id}.html")
    print(f"  Artifacts: artifacts/")
    print()
    print("Next: Open the report in a browser to see results!")
    print()


# ═══════════════════════════════════════════════════════════════════════════════
# Example 2: List Recent Runs
# ═══════════════════════════════════════════════════════════════════════════════

def list_recent_runs():
    """Example: List recent completed runs."""
    
    client = IdampApiClient()
    
    print("Listing recent completed runs...")
    runs_data = client.list_runs(status="completed", limit=5)
    
    print(f"\nTotal runs: {runs_data['total_runs']}")
    print("\nRuns:")
    
    for run in runs_data["runs"]:
        print(f"  • {run['run_id']}")
        print(f"    Status: {run['status']}")
        print(f"    Created: {run['created_at']}")
        print(f"    Progress: {run['progress_percent']}%")
        print()


# ═══════════════════════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()
