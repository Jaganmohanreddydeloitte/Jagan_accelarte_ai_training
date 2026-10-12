# Adding Email Notifications to IDAMP

Complete guide to send email notifications when the pipeline completes, with the HTML report attached.

---

## 1. Packages to Install

### Add to requirements.txt:
```
python-dotenv==1.0.0  # Already have this
smtplib-mock==0.3.3  # For testing (optional, mocks SMTP)
```

**Note:** `smtplib` and `email` are built-in Python libraries (no install needed).

Run:
```bash
pip install python-dotenv
# smtplib and email are built-in
```

---

## 2. Configuration

### Add to .env file:

```bash
# ─── Email Configuration ───────────────────────────────────────────
# IMPORTANT: These are SENSITIVE. Never commit .env to git!
# WARNING: Do NOT use your personal email password. Use an app password.

# Email Provider: gmail, outlook, custom
EMAIL_PROVIDER=gmail

# For Gmail:
# 1. Go to https://myaccount.google.com/apppasswords
# 2. Select "Mail" and "Windows Computer" (or your device)
# 3. Copy the 16-character app password (without spaces)
# 4. Paste here:
GMAIL_ADDRESS=your-email@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx

# For Outlook:
# 1. Go to https://account.microsoft.com/security
# 2. Set up an app password if you have 2FA enabled
# 3. Use your email and app password:
OUTLOOK_ADDRESS=your-email@outlook.com
OUTLOOK_APP_PASSWORD=your-app-password

# For Custom SMTP (e.g., company email):
SMTP_SERVER=smtp.company.com
SMTP_PORT=587
SMTP_USERNAME=your-username
SMTP_PASSWORD=your-password
SMTP_FROM_EMAIL=your-email@company.com

# Recipients (comma-separated for multiple)
EMAIL_RECIPIENTS=user@example.com,admin@example.com

# Email Subject Line
EMAIL_SUBJECT_PREFIX=IDAMP Pipeline Report

# Enable/Disable Email Notifications
ENABLE_EMAIL_NOTIFICATIONS=true
```

---

## 3. Create Email Helper Module

### File: core/email_notifier.py

```python
"""Email notification sender for IDAMP pipeline completion."""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from datetime import datetime

from core.audit import AuditLogger


# ─── Configuration ──────────────────────────────────────────────────────────

ENABLE_EMAIL = os.getenv("ENABLE_EMAIL_NOTIFICATIONS", "false").lower() == "true"
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "").lower()
EMAIL_RECIPIENTS = [
    email.strip() 
    for email in os.getenv("EMAIL_RECIPIENTS", "").split(",") 
    if email.strip()
]

# Gmail configuration
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# Outlook configuration
OUTLOOK_ADDRESS = os.getenv("OUTLOOK_ADDRESS", "")
OUTLOOK_APP_PASSWORD = os.getenv("OUTLOOK_APP_PASSWORD", "")

# Custom SMTP configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")

EMAIL_SUBJECT_PREFIX = os.getenv("EMAIL_SUBJECT_PREFIX", "IDAMP Pipeline Report")


# ─── Email Sender ───────────────────────────────────────────────────────────

class EmailNotifier:
    """Send email notifications when pipeline completes."""
    
    def __init__(self, run_id: str):
        """Initialize email notifier for a pipeline run."""
        self.run_id = run_id
        self.logger = AuditLogger(run_id)
    
    def _get_smtp_config(self) -> tuple[str, int, str, str, str]:
        """Get SMTP configuration based on EMAIL_PROVIDER."""
        if EMAIL_PROVIDER == "gmail":
            if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
                raise ValueError(
                    "Gmail configured but GMAIL_ADDRESS or GMAIL_APP_PASSWORD missing in .env"
                )
            return (
                "smtp.gmail.com",
                587,
                GMAIL_ADDRESS,
                GMAIL_APP_PASSWORD,
                GMAIL_ADDRESS,
            )
        
        elif EMAIL_PROVIDER == "outlook":
            if not OUTLOOK_ADDRESS or not OUTLOOK_APP_PASSWORD:
                raise ValueError(
                    "Outlook configured but OUTLOOK_ADDRESS or OUTLOOK_APP_PASSWORD missing in .env"
                )
            return (
                "smtp.office365.com",
                587,
                OUTLOOK_ADDRESS,
                OUTLOOK_APP_PASSWORD,
                OUTLOOK_ADDRESS,
            )
        
        elif EMAIL_PROVIDER == "custom":
            if not SMTP_SERVER or not SMTP_USERNAME or not SMTP_PASSWORD:
                raise ValueError(
                    "Custom SMTP configured but required settings missing in .env"
                )
            return (
                SMTP_SERVER,
                SMTP_PORT,
                SMTP_USERNAME,
                SMTP_PASSWORD,
                SMTP_FROM_EMAIL or SMTP_USERNAME,
            )
        
        else:
            raise ValueError(
                f"Unknown EMAIL_PROVIDER: {EMAIL_PROVIDER}. "
                "Use: gmail, outlook, or custom"
            )
    
    def send_completion_email(
        self,
        report_path: str,
        status: str = "success",
        error_message: str = "",
        gold_output_paths: list[str] = None,
    ) -> bool:
        """
        Send completion email with report attached.
        
        Args:
            report_path: Path to HTML report file
            status: "success" or "failed"
            error_message: Error details if status is "failed"
            gold_output_paths: List of output file paths
        
        Returns:
            True if email sent successfully, False otherwise
        """
        if not ENABLE_EMAIL:
            return False
        
        if not EMAIL_RECIPIENTS:
            self.logger.log(
                "email_notifier",
                "send_email_skipped",
                reason="No EMAIL_RECIPIENTS configured in .env",
            )
            return False
        
        try:
            smtp_server, smtp_port, from_email, password, sender_email = (
                self._get_smtp_config()
            )
            
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = (
                f"[{status.upper()}] {EMAIL_SUBJECT_PREFIX} - "
                f"Run {self.run_id[:8]} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            msg["From"] = sender_email
            msg["To"] = ", ".join(EMAIL_RECIPIENTS)
            
            # Build email body
            status_emoji = "✅" if status == "success" else "❌"
            body_text = self._build_email_body(
                status=status,
                error_message=error_message,
                gold_output_paths=gold_output_paths or [],
            )
            
            msg.attach(MIMEText(body_text, "html"))
            
            # Attach report if it exists
            if report_path and Path(report_path).exists():
                self._attach_file(msg, report_path)
            
            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(from_email, password)
                server.sendmail(sender_email, EMAIL_RECIPIENTS, msg.as_string())
            
            self.logger.log(
                "email_notifier",
                "send_email_success",
                recipients=EMAIL_RECIPIENTS,
                report_path=report_path,
                status=status,
            )
            return True
        
        except Exception as e:
            self.logger.log(
                "email_notifier",
                "send_email_failed",
                error=str(e),
                recipients=EMAIL_RECIPIENTS,
            )
            print(f"❌ Email notification failed: {e}")
            return False
    
    def _build_email_body(
        self,
        status: str,
        error_message: str,
        gold_output_paths: list[str],
    ) -> str:
        """Build HTML email body."""
        status_color = "#28a745" if status == "success" else "#dc3545"
        status_icon = "✅" if status == "success" else "❌"
        
        html = f"""
        <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: {status_color}; color: white; padding: 15px; border-radius: 5px; }}
                    .content {{ padding: 20px; border: 1px solid #ddd; margin-top: 20px; }}
                    .section {{ margin-bottom: 15px; }}
                    .label {{ font-weight: bold; color: #666; }}
                    .value {{ margin-top: 5px; padding: 10px; background-color: #f5f5f5; border-radius: 3px; }}
                    .footer {{ color: #999; font-size: 12px; margin-top: 30px; border-top: 1px solid #ddd; padding-top: 10px; }}
                    .output-file {{ margin: 5px 0; padding: 5px; background-color: #e8f4f8; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>{status_icon} IDAMP Pipeline {status.upper()}</h2>
                        <p>Run ID: <code>{self.run_id}</code></p>
                    </div>
                    
                    <div class="content">
                        <div class="section">
                            <div class="label">Status:</div>
                            <div class="value">{status.upper()}</div>
                        </div>
                        
                        <div class="section">
                            <div class="label">Run ID:</div>
                            <div class="value">{self.run_id}</div>
                        </div>
                        
                        <div class="section">
                            <div class="label">Completed At:</div>
                            <div class="value">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
                        </div>
        """
        
        if status == "failed" and error_message:
            html += f"""
                        <div class="section">
                            <div class="label">Error Details:</div>
                            <div class="value" style="color: #dc3545; font-family: monospace;">
                                {error_message[:500]}
                            </div>
                        </div>
            """
        
        if gold_output_paths:
            html += """
                        <div class="section">
                            <div class="label">Output Tables:</div>
            """
            for path in gold_output_paths:
                filename = Path(path).name
                html += f'<div class="output-file">{filename}</div>'
            html += """
                        </div>
            """
        
        html += """
                        <div class="section">
                            <p>The HTML report is attached to this email.</p>
                        </div>
                    </div>
                    
                    <div class="footer">
                        <p>IDAMP — Intent-Driven Agentic Medallion Pipeline</p>
                        <p>This is an automated message. Please do not reply to this email.</p>
                    </div>
                </div>
            </body>
        </html>
        """
        
        return html
    
    def _attach_file(self, msg: MIMEMultipart, file_path: str) -> None:
        """Attach a file to the email message."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            return
        
        with open(file_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
        
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {file_path.name}",
        )
        msg.attach(part)


# ─── Convenience Function ───────────────────────────────────────────────────

def send_pipeline_completion_email(
    run_id: str,
    report_path: str,
    status: str = "success",
    error_message: str = "",
    gold_output_paths: list[str] = None,
) -> bool:
    """
    Send pipeline completion email.
    
    Args:
        run_id: Pipeline run ID
        report_path: Path to HTML report
        status: "success" or "failed"
        error_message: Error details if failed
        gold_output_paths: List of output tables
    
    Returns:
        True if email sent, False otherwise
    """
    notifier = EmailNotifier(run_id)
    return notifier.send_completion_email(
        report_path=report_path,
        status=status,
        error_message=error_message,
        gold_output_paths=gold_output_paths or [],
    )
```

---

## 4. Where to Add Email Sending Code

### File: agents/orchestrator.py

Find the `run_gold_and_report()` function. At the very end (after setting status to "completed"):

### Current Code:
```python
def run_gold_and_report(state) -> PipelineState:
    """Phase 4: Execute Gold layer and generate report."""
    try:
        state["status"] = "awaiting_gold_sttm_approval"
        
        # ... gold processing code ...
        
        state["status"] = "completed"
        return state
    
    except Exception as e:
        state["error"] = str(e)
        return state
```

### New Code:
```python
def run_gold_and_report(state) -> PipelineState:
    """Phase 4: Execute Gold layer and generate report."""
    try:
        state["status"] = "awaiting_gold_sttm_approval"
        
        # ... gold processing code ...
        
        state["status"] = "completed"
        
        # ──────────────────────────────────────────────────────────────
        # NEW: Send completion email with report attached
        # ──────────────────────────────────────────────────────────────
        from core.email_notifier import send_pipeline_completion_email
        
        report_path = state.get("report_path", "")
        gold_output_paths = state.get("gold_output_paths", [])
        run_id = state.get("run_id", "")
        
        send_pipeline_completion_email(
            run_id=run_id,
            report_path=report_path,
            status="success",
            gold_output_paths=gold_output_paths,
        )
        
        return state
    
    except Exception as e:
        state["error"] = str(e)
        
        # ──────────────────────────────────────────────────────────────
        # NEW: Send failure email with error details
        # ──────────────────────────────────────────────────────────────
        from core.email_notifier import send_pipeline_completion_email
        
        run_id = state.get("run_id", "")
        send_pipeline_completion_email(
            run_id=run_id,
            report_path="",
            status="failed",
            error_message=str(e),
        )
        
        return state
```

---

## 5. Update Streamlit App (Optional)

### File: app/streamlit_app.py

In Phase 5, add a message to user:

```python
# Phase 5: Report
if st.session_state.phase == "report":
    st.header("📊 Phase 5: Executive Report")
    st.session_state.report_complete = True
    
    report_path = st.session_state.get("pipeline_state", {}).get("report_path")
    
    if report_path and Path(report_path).exists():
        with open(report_path) as f:
            report_html = f.read()
        
        st.components.v1.html(report_html, height=2000, scrolling=True)
        
        # NEW: Email notification message
        if os.getenv("ENABLE_EMAIL_NOTIFICATIONS", "").lower() == "true":
            st.info(
                "📧 **Email notification sent!** Check your inbox for the report with attachment."
            )
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.download_button(
                label="📥 Download Report",
                data=report_html.encode(),
                file_name=f"report_{run_id[:8]}.html",
                mime="text/html",
            )
        
        with col2:
            if st.button("🔄 Start New Analysis"):
                _reset_analysis_session()
                st.rerun()
    
    else:
        st.error("Report file not found. Please check the pipeline execution.")
```

---

## 6. How to Get SMTP Credentials

### Option 1: Gmail (Recommended for Testing)

1. **Enable 2-Factor Authentication:**
   - Go to https://myaccount.google.com/security
   - Scroll to "2-Step Verification"
   - Enable it

2. **Generate App Password:**
   - Go to https://myaccount.google.com/apppasswords
   - Select "Mail" and "Windows Computer" (or your OS)
   - Click "Generate"
   - Copy the 16-character password (without spaces)

3. **Add to .env:**
   ```bash
   EMAIL_PROVIDER=gmail
   GMAIL_ADDRESS=your-email@gmail.com
   GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
   EMAIL_RECIPIENTS=recipient@example.com
   ENABLE_EMAIL_NOTIFICATIONS=true
   ```

### Option 2: Outlook/Microsoft

1. **Enable 2-Factor Authentication:**
   - Go to https://account.microsoft.com/security
   - Set up 2-Step verification if not already done

2. **Generate App Password:**
   - Account settings → Security → Create app password
   - Select "Mail" and "Windows"
   - Copy the generated password

3. **Add to .env:**
   ```bash
   EMAIL_PROVIDER=outlook
   OUTLOOK_ADDRESS=your-email@outlook.com
   OUTLOOK_APP_PASSWORD=your-app-password
   EMAIL_RECIPIENTS=recipient@example.com
   ENABLE_EMAIL_NOTIFICATIONS=true
   ```

### Option 3: Company Email (Custom SMTP)

1. **Get SMTP Details from IT:**
   - SMTP Server: `smtp.company.com`
   - SMTP Port: `587` (or `465`)
   - Username: your email or user ID
   - Password: your company password or app password

2. **Add to .env:**
   ```bash
   EMAIL_PROVIDER=custom
   SMTP_SERVER=smtp.company.com
   SMTP_PORT=587
   SMTP_USERNAME=your-username
   SMTP_PASSWORD=your-password
   SMTP_FROM_EMAIL=your-email@company.com
   EMAIL_RECIPIENTS=recipient@example.com
   ENABLE_EMAIL_NOTIFICATIONS=true
   ```

---

## 7. Testing Email Notifications

### Test 1: Unit Test with Mock SMTP

File: `tests/test_email_notifier.py`

```python
import sys
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
import tempfile
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.email_notifier import EmailNotifier, send_pipeline_completion_email


class TestEmailNotifier:
    """Tests for email notification sender."""
    
    @patch("smtplib.SMTP")
    def test_send_success_email(self, mock_smtp):
        """Test sending a success email."""
        # Arrange
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        notifier = EmailNotifier("test-run-001")
        
        # Act
        result = notifier.send_completion_email(
            report_path="",
            status="success",
            gold_output_paths=["output1.parquet", "output2.parquet"],
        )
        
        # Assert
        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.sendmail.assert_called_once()
    
    @patch("smtplib.SMTP")
    def test_send_failed_email(self, mock_smtp):
        """Test sending a failure email with error message."""
        # Arrange
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        notifier = EmailNotifier("test-run-002")
        
        # Act
        result = notifier.send_completion_email(
            report_path="",
            status="failed",
            error_message="Bronze STTM file is empty",
        )
        
        # Assert
        assert result is True
        mock_server.sendmail.assert_called_once()
        
        # Verify error message in email
        call_args = mock_server.sendmail.call_args
        email_body = call_args[0][2]  # Third argument is the message
        assert "failed" in email_body.lower() or "error" in email_body.lower()
    
    @patch("smtplib.SMTP")
    def test_send_email_with_attachment(self, mock_smtp, tmp_path):
        """Test sending email with HTML report attached."""
        # Arrange
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        # Create test report file
        report_path = tmp_path / "report.html"
        report_path.write_text("<html><body>Test Report</body></html>")
        
        notifier = EmailNotifier("test-run-003")
        
        # Act
        result = notifier.send_completion_email(
            report_path=str(report_path),
            status="success",
        )
        
        # Assert
        assert result is True
        mock_server.sendmail.assert_called_once()
    
    def test_get_smtp_config_gmail(self, monkeypatch):
        """Test SMTP config for Gmail."""
        # Arrange
        monkeypatch.setenv("EMAIL_PROVIDER", "gmail")
        monkeypatch.setenv("GMAIL_ADDRESS", "test@gmail.com")
        monkeypatch.setenv("GMAIL_APP_PASSWORD", "xxxx xxxx xxxx xxxx")
        
        # Need to reimport to pick up env vars
        from core import email_notifier
        import importlib
        importlib.reload(email_notifier)
        
        notifier = email_notifier.EmailNotifier("test-run")
        
        # Act
        server, port, username, password, from_email = notifier._get_smtp_config()
        
        # Assert
        assert server == "smtp.gmail.com"
        assert port == 587
        assert username == "test@gmail.com"
    
    def test_send_email_disabled_by_default(self, monkeypatch):
        """Test that emails are disabled by default."""
        # Arrange
        monkeypatch.setenv("ENABLE_EMAIL_NOTIFICATIONS", "false")
        from core import email_notifier
        import importlib
        importlib.reload(email_notifier)
        
        notifier = email_notifier.EmailNotifier("test-run")
        
        # Act
        result = notifier.send_completion_email(report_path="", status="success")
        
        # Assert
        assert result is False


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

Run tests:
```bash
pytest tests/test_email_notifier.py -v
```

### Test 2: Manual Test with Real Email

1. **Configure .env with your credentials:**
   ```bash
   EMAIL_PROVIDER=gmail
   GMAIL_ADDRESS=your-test-email@gmail.com
   GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
   EMAIL_RECIPIENTS=your-recipient@example.com
   ENABLE_EMAIL_NOTIFICATIONS=true
   ```

2. **Run a quick test:**
   ```python
   from core.email_notifier import send_pipeline_completion_email
   
   result = send_pipeline_completion_email(
       run_id="test-run-001",
       report_path="",
       status="success",
       gold_output_paths=["table1.parquet", "table2.parquet"],
   )
   
   print("Email sent successfully!" if result else "Email failed")
   ```

3. **Check your inbox** for the email

### Test 3: Full Pipeline Test

1. **Start Streamlit:**
   ```bash
   streamlit run app/streamlit_app.py
   ```

2. **Upload test data and complete all phases**

3. **Check email inbox** when Phase 5 completes

4. **Verify:**
   - Email received with correct subject
   - HTML report attached
   - Status shown correctly (success/failed)
   - Output table names listed

---

## 8. Summary of Files

| File | Change |
|------|--------|
| `core/email_notifier.py` | NEW: Email notification module |
| `agents/orchestrator.py` | Add email sending in success/error handlers |
| `app/streamlit_app.py` | Add optional notification message in Phase 5 |
| `tests/test_email_notifier.py` | NEW: Email notification tests |
| `.env` | Add email configuration (NEVER commit) |
| `.env.example` | Add email configuration template |
| `requirements.txt` | No changes (email libs are built-in) |

---

## 9. Security Checklist

- [ ] **Never commit .env file** — Already in .gitignore
- [ ] **Use App Passwords, not Gmail password** — Account security
- [ ] **Rotate app passwords regularly** — Best practice
- [ ] **Don't share .env file** — Contains sensitive credentials
- [ ] **Use EMAIL_RECIPIENTS environment variable** — Don't hardcode
- [ ] **ENABLE_EMAIL_NOTIFICATIONS=false by default** — Opt-in
- [ ] **Sanitize error messages** — Truncate to 500 chars
- [ ] **Use TLS/STARTTLS** — Encrypted communication
- [ ] **Log email success/failure to audit trail** — Track all notifications
- [ ] **Handle SMTP errors gracefully** — Don't crash pipeline

---

## 10. Troubleshooting

| Issue | Solution |
|-------|----------|
| `GMAIL_APP_PASSWORD missing` | Generate app password at https://myaccount.google.com/apppasswords |
| `SMTPAuthenticationError` | Verify app password is correct (no extra spaces) |
| `SMTPNotSupportedError` | Enable "Less secure app access" (Gmail) or use app password |
| `Connection refused` | Check SMTP_SERVER and SMTP_PORT are correct |
| `Email not received` | Check SPAM folder; verify EMAIL_RECIPIENTS in .env |
| `Report not attached` | Verify report_path exists and is readable |
| `Tests failing` | Mock SMTP with @patch("smtplib.SMTP") |

---

## 11. Example .env Configuration

```bash
# ─── Email Configuration ───────────────────────────────────────────

# Email Provider: gmail, outlook, custom
EMAIL_PROVIDER=gmail

# Gmail Configuration
GMAIL_ADDRESS=your-email@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx

# Email Recipients (comma-separated)
EMAIL_RECIPIENTS=admin@company.com,data-team@company.com

# Email Subject Prefix
EMAIL_SUBJECT_PREFIX=IDAMP Pipeline Report

# Enable Email Notifications (true/false)
ENABLE_EMAIL_NOTIFICATIONS=true
```

---

## 12. Disable Email Notifications

To disable email notifications without modifying code:

```bash
# In .env
ENABLE_EMAIL_NOTIFICATIONS=false
```

Or remove email configuration entirely:
```bash
# Comment out or remove:
# EMAIL_RECIPIENTS=...
```

The pipeline will continue working normally without sending emails.

---

**Your IDAMP pipeline now has email notifications!** 📧✨

Next steps:
1. Create core/email_notifier.py with the code above
2. Add email configuration to .env and .env.example
3. Modify agents/orchestrator.py to call send_pipeline_completion_email()
4. Test with real credentials (Gmail recommended)
5. Update requirements.txt documentation
