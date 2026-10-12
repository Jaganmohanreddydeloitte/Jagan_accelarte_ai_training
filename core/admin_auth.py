"""
Admin Authentication System

Simple username/password authentication with session management.
"""

import os
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone
import json


class AdminAuthenticator:
    """Simple admin authentication with password hashing"""

    def __init__(self, admin_file: Path = None):
        """
        Initialize authenticator.
        
        Args:
            admin_file: Path to admin credentials JSON file.
                       Creates with default credentials if not found.
        """
        self.admin_file = admin_file or Path(".auth") / "admins.json"
        self.admin_file.parent.mkdir(parents=True, exist_ok=True)
        self.session_timeout = timedelta(hours=8)
        
        # Initialize with defaults if not exists
        if not self.admin_file.exists():
            self._create_defaults()
    
    def _create_defaults(self) -> None:
        """Create default admin credentials"""
        defaults = {
            "admins": [
                {
                    "username": "admin",
                    "password_hash": self._hash_password("admin123"),
                    "full_name": "System Administrator",
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            ]
        }
        
        with open(self.admin_file, "w") as f:
            json.dump(defaults, f, indent=2)
    
    def _hash_password(self, password: str) -> str:
        """Hash password using SHA256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def _load_admins(self) -> list:
        """Load admin credentials from file"""
        try:
            with open(self.admin_file, "r") as f:
                data = json.load(f)
                return data.get("admins", [])
        except Exception:
            return []
    
    def authenticate(self, username: str, password: str) -> bool:
        """
        Authenticate admin with username and password.
        
        Args:
            username: Admin username
            password: Admin password (plain text)
        
        Returns:
            True if credentials valid, False otherwise
        """
        admins = self._load_admins()
        password_hash = self._hash_password(password)
        
        for admin in admins:
            if admin["username"] == username and admin["password_hash"] == password_hash:
                return True
        
        return False
    
    def get_admin(self, username: str) -> dict:
        """Get admin info by username"""
        admins = self._load_admins()
        
        for admin in admins:
            if admin["username"] == username:
                # Remove password hash from returned data
                admin_copy = admin.copy()
                admin_copy.pop("password_hash", None)
                return admin_copy
        
        return None
    
    def add_admin(self, username: str, password: str, full_name: str = None) -> bool:
        """
        Add new admin user.
        
        Args:
            username: Username (alphanumeric)
            password: Password
            full_name: Optional full name
        
        Returns:
            True if added, False if already exists
        """
        if not username.isalnum():
            return False
        
        admins = self._load_admins()
        
        # Check if already exists
        if any(a["username"] == username for a in admins):
            return False
        
        new_admin = {
            "username": username,
            "password_hash": self._hash_password(password),
            "full_name": full_name or username,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        admins.append(new_admin)
        
        with open(self.admin_file, "w") as f:
            json.dump({"admins": admins}, f, indent=2)
        
        return True
    
    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """
        Change admin password.
        
        Args:
            username: Admin username
            old_password: Current password
            new_password: New password
        
        Returns:
            True if successful, False if old password wrong
        """
        if not self.authenticate(username, old_password):
            return False
        
        admins = self._load_admins()
        
        for admin in admins:
            if admin["username"] == username:
                admin["password_hash"] = self._hash_password(new_password)
                admin["password_changed_at"] = datetime.now(timezone.utc).isoformat()
                break
        
        with open(self.admin_file, "w") as f:
            json.dump({"admins": admins}, f, indent=2)
        
        return True


def init_session_auth(authenticator: AdminAuthenticator) -> bool:
    """
    Initialize or check session authentication.
    Uses st.session_state to store login info.
    Returns True if user is authenticated.
    """
    import streamlit as st
    
    # Check if already authenticated
    if st.session_state.get("admin_authenticated"):
        # Check if session expired
        login_time = st.session_state.get("admin_login_time")
        if login_time:
            if datetime.now(timezone.utc) - login_time < authenticator.session_timeout:
                return True
        
        # Session expired
        st.session_state.admin_authenticated = False
    
    # Show login form
    st.sidebar.markdown("### 🔐 Admin Login")
    
    with st.sidebar.form("admin_login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if authenticator.authenticate(username, password):
                st.session_state.admin_authenticated = True
                st.session_state.admin_username = username
                st.session_state.admin_login_time = datetime.now(timezone.utc)
                st.success("✓ Logged in!")
                st.rerun()
            else:
                st.error("❌ Invalid credentials")
                return False
    
    return False


def show_logout_button():
    """Show logout button in sidebar"""
    import streamlit as st
    
    if st.session_state.get("admin_authenticated"):
        with st.sidebar:
            st.markdown("---")
            col1, col2 = st.columns([3, 1])
            
            with col1:
                username = st.session_state.get("admin_username", "Unknown")
                st.markdown(f"**Logged in as:** {username}")
            
            with col2:
                if st.button("Logout"):
                    st.session_state.admin_authenticated = False
                    st.session_state.admin_username = None
                    st.session_state.admin_login_time = None
                    st.success("Logged out!")
                    st.rerun()
