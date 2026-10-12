#!/bin/bash
# IDAMP REST API - Example curl Commands
# Run these commands in your terminal to test all endpoints
# Make sure the API server is running: python app/run_api.py

API="http://localhost:8000"
API_V1="http://localhost:8000/api/v1"

# ═══════════════════════════════════════════════════════════════════════════════
# 1. HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

echo "1. Testing health check..."
curl "$API/health"
echo ""
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# 2. UPLOAD FILE & START RUN
# ═══════════════════════════════════════════════════════════════════════════════

echo "2. Uploading file and starting run..."
# Note: Replace 'customers.csv' with your actual file
UPLOAD_RESPONSE=$(curl -s -X POST "$API_V1/runs/upload" \
  -F "file=@customers.csv" \
  -F "business_intent=Find high-value customer segments" \
  -F "user_email=analyst@company.com")

echo "$UPLOAD_RESPONSE"
RUN_ID=$(echo "$UPLOAD_RESPONSE" | grep -oP '"run_id":"?\K[^,"]*')
echo "Run ID: $RUN_ID"
echo ""
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# 3. GET RUN STATUS
# ═══════════════════════════════════════════════════════════════════════════════

echo "3. Checking run status..."
curl -s "$API_V1/runs/$RUN_ID" | jq .
echo ""
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# 4. LIST ALL RUNS
# ═══════════════════════════════════════════════════════════════════════════════

echo "4. Listing all runs..."
curl -s "$API_V1/runs?limit=10" | jq .
echo ""
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# 5. LIST COMPLETED RUNS ONLY
# ═══════════════════════════════════════════════════════════════════════════════

echo "5. Listing completed runs..."
curl -s "$API_V1/runs?status=completed&limit=5" | jq .
echo ""
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# 6. APPROVE BRONZE STTM
# ═══════════════════════════════════════════════════════════════════════════════

echo "6. Approving Bronze STTM..."
curl -s -X POST "$API_V1/runs/$RUN_ID/approve" \
  -H "Content-Type: application/json" \
  -d '{"layer":"bronze"}' | jq .
echo ""
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# 7. APPROVE SILVER STTM
# ═══════════════════════════════════════════════════════════════════════════════

echo "7. Approving Silver STTM..."
curl -s -X POST "$API_V1/runs/$RUN_ID/approve" \
  -H "Content-Type: application/json" \
  -d '{"layer":"silver"}' | jq .
echo ""
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# 8. APPROVE GOLD STTM
# ═══════════════════════════════════════════════════════════════════════════════

echo "8. Approving Gold STTM..."
curl -s -X POST "$API_V1/runs/$RUN_ID/approve" \
  -H "Content-Type: application/json" \
  -d '{"layer":"gold"}' | jq .
echo ""
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# 9. DOWNLOAD REPORT
# ═══════════════════════════════════════════════════════════════════════════════

echo "9. Downloading report (if available)..."
curl -s "$API_V1/runs/$RUN_ID/report" -o "report_${RUN_ID}.html"
if [ -f "report_${RUN_ID}.html" ]; then
    echo "✓ Report saved as: report_${RUN_ID}.html"
else
    echo "✗ Report not available yet (run may still be processing)"
fi
echo ""
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# 10. DOWNLOAD ARTIFACT (Bronze STTM)
# ═══════════════════════════════════════════════════════════════════════════════

echo "10. Downloading Bronze STTM artifact..."
curl -s "$API_V1/runs/$RUN_ID/artifacts/bronze_sttm" -o "bronze_sttm_${RUN_ID}.json"
if [ -f "bronze_sttm_${RUN_ID}.json" ]; then
    echo "✓ Bronze STTM saved as: bronze_sttm_${RUN_ID}.json"
else
    echo "✗ Artifact not available yet"
fi
echo ""
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# 11. CANCEL RUN
# ═══════════════════════════════════════════════════════════════════════════════

echo "11. Cancelling run (optional - uncomment to use)..."
# curl -s -X POST "$API_V1/runs/$RUN_ID/cancel" | jq .
echo "    # curl -s -X POST \"$API_V1/runs/$RUN_ID/cancel\" | jq ."
echo ""
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# 12. DELETE RUN
# ═══════════════════════════════════════════════════════════════════════════════

echo "12. Deleting run (optional - uncomment to use)..."
# curl -s -X DELETE "$API_V1/runs/$RUN_ID?delete_files=true" | jq .
echo "    # curl -s -X DELETE \"$API_V1/runs/$RUN_ID?delete_files=true\" | jq ."
echo ""
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# 13. GET API INFO
# ═══════════════════════════════════════════════════════════════════════════════

echo "13. Getting API info..."
curl -s "$API_V1/info" | jq .
echo ""
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# POLLING EXAMPLE - Wait for run to complete
# ═══════════════════════════════════════════════════════════════════════════════

echo "═════════════════════════════════════════════════════════════════════════════"
echo "BONUS: Polling for completion (waiting for run to finish)..."
echo "═════════════════════════════════════════════════════════════════════════════"
echo ""

max_attempts=60
attempt=0

while [ $attempt -lt $max_attempts ]; do
    attempt=$((attempt + 1))
    
    status=$(curl -s "$API_V1/runs/$RUN_ID" | jq -r '.status')
    phase=$(curl -s "$API_V1/runs/$RUN_ID" | jq -r '.phase')
    progress=$(curl -s "$API_V1/runs/$RUN_ID" | jq -r '.progress_percent')
    
    echo "[$attempt/$max_attempts] Status: $status | Phase: $phase | Progress: $progress%"
    
    if [ "$status" == "completed" ] || [ "$status" == "failed" ]; then
        echo ""
        echo "Run $status!"
        break
    fi
    
    sleep 10
done

echo ""
echo "═════════════════════════════════════════════════════════════════════════════"
echo "All examples completed!"
echo "═════════════════════════════════════════════════════════════════════════════"
