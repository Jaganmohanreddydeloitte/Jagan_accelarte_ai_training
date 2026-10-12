# Adding Excel Support to IDAMP

This guide shows you how to add Excel (.xlsx) file support to your Agentic Medallion Pipeline alongside existing CSV support.

---

## Files to Modify

1. **app/streamlit_app.py** — Accept .xlsx files in Phase 1 uploader
2. **agents/profiler.py** — Read .xlsx files and handle multiple sheets
3. **core/config.py** — Add Excel-related paths (optional)
4. **tests/test_profiler.py** — Add Excel file tests

---

## Change 1: Streamlit File Uploader (app/streamlit_app.py)

### Find This Section:
Search for `if st.session_state.phase == "upload":` in Phase 1

### Current Code:
```python
# Phase 1: Upload & Intent
if st.session_state.phase == "upload":
    st.header("📤 Phase 1: Upload Data & Define Intent")
    st.markdown("Upload your CSV files and describe what you want to analyze.")
    
    uploaded_files = st.file_uploader(
        "Upload CSV files",
        type=["csv"],
        accept_multiple_files=True,
        help="Upload one or more CSV files with your data.",
    )
```

### New Code:
```python
# Phase 1: Upload & Intent
if st.session_state.phase == "upload":
    st.header("📤 Phase 1: Upload Data & Define Intent")
    st.markdown("Upload your CSV or Excel files and describe what you want to analyze.")
    
    uploaded_files = st.file_uploader(
        "Upload CSV or Excel files",
        type=["csv", "xlsx"],
        accept_multiple_files=True,
        help="Upload one or more CSV or Excel files with your data. For Excel files with multiple sheets, all sheets will be processed as separate tables.",
    )
```

### Then Find:
The section where files are saved to LANDING_DIR

### Current Code:
```python
saved_paths = []
if uploaded_files:
    for uploaded_file in uploaded_files:
        file_path = LANDING_DIR / uploaded_file.name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        saved_paths.append(str(file_path))
```

### New Code:
```python
saved_paths = []
if uploaded_files:
    for uploaded_file in uploaded_files:
        file_path = LANDING_DIR / uploaded_file.name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        saved_paths.append(str(file_path))
        
        # If Excel file, extract all sheets as separate CSVs
        if uploaded_file.name.endswith('.xlsx'):
            try:
                xl_file = pd.ExcelFile(file_path)
                for sheet_name in xl_file.sheet_names:
                    sheet_df = pd.read_excel(file_path, sheet_name=sheet_name)
                    # Save each sheet as a separate CSV
                    sheet_csv_path = LANDING_DIR / f"{uploaded_file.name.replace('.xlsx', '')}_{sheet_name}.csv"
                    sheet_df.to_csv(sheet_csv_path, index=False)
                    saved_paths.append(str(sheet_csv_path))
                    st.info(f"📊 Extracted sheet '{sheet_name}' from {uploaded_file.name}")
            except Exception as e:
                st.error(f"❌ Error extracting sheets from {uploaded_file.name}: {e}")
```

---

## Change 2: Profiler File Reading (agents/profiler.py)

### Find This Function:
`_inspect_files(file_paths: list[str]) -> dict:`

### Current Code:
```python
def _inspect_files(file_paths: list[str]) -> dict:
    """Preview files: shape, columns, dtypes, 3 sample rows."""
    result = {}
    for fpath in file_paths:
        try:
            df = pd.read_csv(fpath)
            result[fpath] = {
                "shape": df.shape,
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "sample_values": {
                    col: df[col].dropna().head(3).tolist() for col in df.columns
                },
            }
        except Exception as e:
            result[fpath] = {"error": str(e)}
    return result
```

### New Code:
```python
def _read_data_file(file_path: str) -> pd.DataFrame:
    """Read CSV or Excel file and return DataFrame."""
    if file_path.endswith('.xlsx') or file_path.endswith('.xls'):
        # For Excel files, read all sheets and concatenate them
        try:
            xl_file = pd.ExcelFile(file_path)
            dfs = []
            for sheet_name in xl_file.sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                df['_source_sheet'] = sheet_name  # Track which sheet each row came from
                dfs.append(df)
            return pd.concat(dfs, ignore_index=True)
        except Exception as e:
            raise ValueError(f"Error reading Excel file {file_path}: {e}")
    else:
        # Read CSV file
        return pd.read_csv(file_path)


def _inspect_files(file_paths: list[str]) -> dict:
    """Preview files: shape, columns, dtypes, 3 sample rows. Supports CSV and Excel."""
    result = {}
    for fpath in file_paths:
        try:
            df = _read_data_file(fpath)
            result[fpath] = {
                "shape": df.shape,
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "sample_values": {
                    col: df[col].dropna().head(3).tolist() for col in df.columns
                },
                "file_type": "excel" if fpath.endswith(('.xlsx', '.xls')) else "csv",
            }
        except Exception as e:
            result[fpath] = {"error": str(e)}
    return result
```

### Find This Function:
`_compute_stats(file_paths: list[str]) -> dict:`

### Current Code:
```python
def _compute_stats(file_paths: list[str]) -> dict:
    """Compute full statistics for each file."""
    result = {}
    for fpath in file_paths:
        try:
            df = pd.read_csv(fpath)
            # ... rest of stats computation ...
```

### New Code:
```python
def _compute_stats(file_paths: list[str]) -> dict:
    """Compute full statistics for each file. Supports CSV and Excel."""
    result = {}
    for fpath in file_paths:
        try:
            df = _read_data_file(fpath)
            # ... rest of stats computation ...
```

---

## Change 3: Update Core Config (Optional - core/config.py)

If you want to add constants for supported file types:

### Find or Add:
At the top of the file with other constants

### Add These Lines:
```python
# Supported file types for data ingestion
SUPPORTED_FILE_TYPES = ['csv', 'xlsx', 'xls']
FILE_TYPE_DESCRIPTIONS = {
    'csv': 'Comma-separated values',
    'xlsx': 'Excel 2007+ workbook (supports multiple sheets)',
    'xls': 'Legacy Excel workbook',
}
```

---

## Change 4: Add Tests for Excel Support (tests/test_profiler.py)

### Add These Test Fixtures:

```python
import openpyxl
from openpyxl import Workbook

def _make_test_excel(tmp_path, filename="test_data.xlsx", sheets=None):
    """Create a test Excel file with multiple sheets."""
    if sheets is None:
        sheets = {
            "customers": [
                {"id": 1, "name": "Alice", "email": "alice@example.com"},
                {"id": 2, "name": "Bob", "email": "bob@example.com"},
            ],
            "orders": [
                {"order_id": 101, "customer_id": 1, "amount": 150.00},
                {"order_id": 102, "customer_id": 2, "amount": 200.00},
            ],
        }
    
    excel_path = tmp_path / filename
    
    # Create workbook with multiple sheets
    wb = Workbook()
    wb.remove(wb.active)  # Remove default sheet
    
    for sheet_name, rows in sheets.items():
        ws = wb.create_sheet(sheet_name)
        
        # Write headers
        if rows:
            headers = list(rows[0].keys())
            for col_idx, header in enumerate(headers, 1):
                ws.cell(row=1, column=col_idx, value=header)
            
            # Write data
            for row_idx, row_data in enumerate(rows, 2):
                for col_idx, header in enumerate(headers, 1):
                    ws.cell(row=row_idx, column=col_idx, value=row_data[header])
    
    wb.save(excel_path)
    return str(excel_path)
```

### Add These Test Methods:

```python
class TestProfiler:
    
    def test_profile_excel_file_single_sheet(self, tmp_path, monkeypatch):
        """Test profiling an Excel file with a single sheet."""
        # Arrange
        monkeypatch.setattr("agents.profiler.PROFILES_DIR", tmp_path)
        excel_path = _make_test_excel(tmp_path, sheets={
            "data": [
                {"customer_id": 1, "name": "Alice", "email": "alice@example.com"},
                {"customer_id": 2, "name": "Bob", "email": "bob@example.com"},
            ]
        })
        
        with patch("agents.profiler._make_llm") as mock_llm:
            mock_llm.return_value = Mock(invoke=Mock(return_value=Mock(content=json.dumps({
                "semantic_meanings": {"customer_id": "unique id", "name": "customer name"},
                "join_keys": ["customer_id"],
                "quality_notes": {},
                "overall_quality_score": 95,
            }))))
            
            # Act
            result = profile_dataset([excel_path], "Test Excel profile", "test-run-001")
            
            # Assert
            assert result is not None
            assert Path(result).exists()
            profile_json = json.load(open(result))
            assert profile_json["overall_quality_score"] == 95
    
    def test_profile_excel_file_multiple_sheets(self, tmp_path, monkeypatch):
        """Test profiling an Excel file with multiple sheets (concatenates all)."""
        # Arrange
        monkeypatch.setattr("agents.profiler.PROFILES_DIR", tmp_path)
        excel_path = _make_test_excel(tmp_path, sheets={
            "customers": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ],
            "orders": [
                {"id": 101, "customer_id": 1, "amount": 150},
                {"id": 102, "customer_id": 2, "amount": 200},
            ]
        })
        
        with patch("agents.profiler._make_llm") as mock_llm:
            mock_llm.return_value = Mock(invoke=Mock(return_value=Mock(content=json.dumps({
                "semantic_meanings": {},
                "join_keys": [],
                "quality_notes": {},
                "overall_quality_score": 85,
            }))))
            
            # Act
            result = profile_dataset([excel_path], "Test multi-sheet", "test-run-002")
            
            # Assert
            assert result is not None
            assert Path(result).exists()
            profile_json = json.load(open(result))
            assert profile_json["overall_quality_score"] == 85
    
    def test_read_data_file_csv(self, tmp_path):
        """Test reading a CSV file."""
        # Arrange
        csv_path = tmp_path / "test.csv"
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        df.to_csv(csv_path, index=False)
        
        # Act
        from agents.profiler import _read_data_file
        result = _read_data_file(str(csv_path))
        
        # Assert
        assert result.shape == (3, 2)
        assert list(result.columns) == ["a", "b"]
    
    def test_read_data_file_excel(self, tmp_path):
        """Test reading an Excel file."""
        # Arrange
        excel_path = _make_test_excel(tmp_path, sheets={
            "sheet1": [
                {"col1": 1, "col2": "a"},
                {"col1": 2, "col2": "b"},
            ]
        })
        
        # Act
        from agents.profiler import _read_data_file
        result = _read_data_file(excel_path)
        
        # Assert
        assert result.shape[0] == 2  # 2 data rows (may have extra columns)
        assert "col1" in result.columns
        assert "col2" in result.columns
        assert "_source_sheet" in result.columns  # Track which sheet each row came from
```

---

## Step-by-Step Implementation

### Step 1: Install openpyxl (for Excel support)
```bash
pip install openpyxl
```

Update `requirements.txt`:
```
openpyxl==3.11.2
```

### Step 2: Modify app/streamlit_app.py
- Change `type=["csv"]` to `type=["csv", "xlsx"]`
- Add code to extract sheets from Excel files as separate CSVs (see Change 1 above)

### Step 3: Modify agents/profiler.py
- Add `_read_data_file()` helper function
- Update `_inspect_files()` to use the new helper
- Update `_compute_stats()` to use the new helper
- Update `profile_dataset()` docstring to mention Excel support

### Step 4: Add Tests
- Add `_make_test_excel()` helper to create test Excel files
- Add test methods for Excel profiling (single sheet, multiple sheets)
- Add tests for `_read_data_file()` with both CSV and Excel

### Step 5: Update Documentation
- Update README.md Phase 1 section: "Upload CSV or Excel files"
- Update app description in streamlit_app.py docstring

---

## How to Test Excel Support

### Test 1: Manual UI Test
```
1. Start Streamlit: streamlit run app/streamlit_app.py
2. Go to Phase 1: Upload & Intent
3. Create a test Excel file (e.g., test_data.xlsx)
   - Add a sheet named "customers" with columns: id, name, email
   - Add a sheet named "orders" with columns: order_id, customer_id, amount
4. Upload test_data.xlsx
5. Expected: You should see messages like:
   - "📊 Extracted sheet 'customers' from test_data.xlsx"
   - "📊 Extracted sheet 'orders' from test_data.xlsx"
6. Enter business question and click "🚀 Start Workflow"
7. Verify Phase 1 completes successfully
```

### Test 2: Run Unit Tests
```bash
# Run all profiler tests
pytest tests/test_profiler.py -v

# Run only Excel tests
pytest tests/test_profiler.py::TestProfiler::test_profile_excel_file_single_sheet -v
pytest tests/test_profiler.py::TestProfiler::test_profile_excel_file_multiple_sheets -v
pytest tests/test_profiler.py::TestProfiler::test_read_data_file_excel -v
```

### Test 3: Create Test Excel File Programmatically
```python
import pandas as pd
from openpyxl import Workbook

# Create test Excel file
with pd.ExcelWriter('test_data.xlsx', engine='openpyxl') as writer:
    # Sheet 1: Customers
    customers_df = pd.DataFrame({
        'customer_id': [1, 2, 3],
        'name': ['Alice Johnson', 'Bob Smith', 'Charlie Brown'],
        'email': ['alice@example.com', 'bob@example.com', 'charlie@example.com'],
    })
    customers_df.to_excel(writer, sheet_name='customers', index=False)
    
    # Sheet 2: Orders
    orders_df = pd.DataFrame({
        'order_id': [101, 102, 103],
        'customer_id': [1, 2, 1],
        'amount': [150.50, 200.00, 75.25],
    })
    orders_df.to_excel(writer, sheet_name='orders', index=False)

print("✓ test_data.xlsx created successfully")
```

### Test 4: Verify File Extraction
```bash
# After uploading test_data.xlsx, check landing directory
ls -la data/landing/    # macOS/Linux
dir data\landing\       # Windows

# Expected output:
# - test_data.xlsx (original)
# - test_data_customers.csv (extracted)
# - test_data_orders.csv (extracted)
```

### Test 5: Full Workflow Test
```
1. Upload test_data.xlsx (with multiple sheets)
2. Ask question: "What are the top customers by total order amount?"
3. Complete all 5 phases
4. Expected: All phases succeed; audit logs show successful processing
5. Check data/ folders for Parquet files:
   - data/bronze_layer/ should have files for both extracted sheets
   - data/silver_layer/ should have deduplicated data
   - data/gold_layer/ should have analytics tables
```

---

## Handling Excel Quirks

### Multiple Sheets Strategy
**Option 1 (Recommended):** Extract sheets as separate CSVs at upload time
- ✅ Simpler downstream processing
- ✅ Clear file naming
- ✅ No schema conflicts between sheets
- ❌ Temporary CSV files created

**Option 2:** Process Excel file directly in Profiler
- ✅ No temporary files
- ❌ More complex code
- ❌ Potential schema conflicts

This guide uses **Option 1**.

### Handling Missing/Extra Columns
When concatenating multiple sheets, columns may differ:
- Pandas uses outer join (union of all columns)
- Missing values filled with NaN
- The `_source_sheet` column tracks which sheet each row came from
- Silver layer's null-handling logic handles NaN values

### Named Ranges & Formulas
- openpyxl ignores formulas (only reads values)
- Named ranges are ignored
- Hidden sheets are included in processing

### Large Files
- Excel files larger than available RAM may fail
- Consider splitting large Excel files before upload
- Pandas handles both .xlsx (modern) and .xls (legacy) formats

---

## Summary of Changes

| File | Change | Lines |
|------|--------|-------|
| `app/streamlit_app.py` | Accept .xlsx, extract sheets | ~15 lines |
| `agents/profiler.py` | Add `_read_data_file()`, update helper functions | ~20 lines |
| `core/config.py` | Add SUPPORTED_FILE_TYPES constant (optional) | ~5 lines |
| `tests/test_profiler.py` | Add Excel test methods and fixtures | ~100 lines |
| `requirements.txt` | Add openpyxl dependency | 1 line |

**Total:** ~140 lines of code added, fully backward compatible with CSV

---

## Rollback Instructions

If Excel support causes issues, revert with:
```bash
git checkout app/streamlit_app.py agents/profiler.py
```

Or simply remove the Excel extraction code from Streamlit uploader and the `_read_data_file()` function from profiler.

---

**Next Steps:**
1. Install openpyxl: `pip install openpyxl`
2. Update requirements.txt
3. Make changes to 4 files (follow Steps 1-5 above)
4. Run tests: `pytest tests/test_profiler.py -v`
5. Test manually with sample Excel file
