import base64
import csv
import io
from datetime import datetime, timedelta
import json
import os
import sqlite3
import uuid

import streamlit as st

# -----------------------------
# STORAGE CONFIG
# -----------------------------
UPLOAD_FOLDER = "ticket_attachments"
DATABASE_FILE = "it_support.db"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)



# -----------------------------
# GLOBAL UI STYLING
# -----------------------------
def apply_global_styles():
    """Apply app-wide visual polish."""
    st.markdown("""
    <style>
    /* Main app spacing */
    .block-container {
        padding-top: 1.25rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f8f9fb 0%, #eef2f7 100%);
        border-right: 1px solid #d9dee8;
    }

    section[data-testid="stSidebar"] .stRadio label {
        font-weight: 500;
    }

    /* Dashboard metrics */
    [data-testid="metric-container"] {
        background: #ffffff;
        border: 1px solid #d8dee9;
        padding: 14px;
        border-radius: 14px;
        box-shadow: 0 2px 8px rgba(31, 41, 55, 0.08);
    }

    [data-testid="metric-container"] label {
        color: #4b5563 !important;
        font-weight: 600;
    }

    [data-testid="metric-container"] div[data-testid="stMetricValue"] {
        color: #111827;
        font-weight: 700;
    }

    /* Expanders as cards */
    div[data-testid="stExpander"] {
        background: #ffffff;
        border: 1px solid #d8dee9;
        border-radius: 14px;
        margin-bottom: 12px;
        box-shadow: 0 2px 6px rgba(31, 41, 55, 0.05);
    }

    div[data-testid="stExpander"] details summary {
        font-weight: 600;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 10px;
        padding: 0.45rem 1rem;
        font-weight: 600;
        border: 1px solid #cfd6e4;
    }

    .stButton > button:hover {
        border-color: #4e89ff;
        color: #1d4ed8;
    }

    /* Inputs */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        border-radius: 10px;
    }

    /* Alerts */
    .stAlert {
        border-radius: 12px;
        border: 1px solid rgba(0,0,0,0.05);
    }

    /* Custom cards */
    .app-card {
        padding: 1rem;
        background: #ffffff;
        border: 1px solid #d8dee9;
        border-radius: 14px;
        box-shadow: 0 2px 8px rgba(31, 41, 55, 0.06);
        margin-bottom: 1rem;
    }

    .description-box {
        padding: 14px;
        background: #f8fafc;
        border-left: 5px solid #4e89ff;
        border-radius: 10px;
        margin-bottom: 1rem;
        line-height: 1.5;
    }

    .sidebar-footer {
        margin-top: 1rem;
        padding: 0.75rem;
        background: #ffffff;
        border: 1px solid #d8dee9;
        border-radius: 12px;
        font-size: 0.85rem;
        color: #4b5563;
    }

    h1 {
        color: #172033;
    }

    h2, h3 {
        color: #1f2937;
        letter-spacing: -0.02em;
    }
    </style>
    """, unsafe_allow_html=True)


def render_description_box(text):
    """Render ticket descriptions in a readable box."""
    safe_text = str(text or "No description provided.")
    st.markdown(
        f"""
        <div class="description-box">
            {safe_text}
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_priority_text(priority):
    """Return colored HTML for priority labels."""
    colors = {
        "Critical": "#dc3545",
        "High": "#fd7e14",
        "Medium": "#0d6efd",
        "Low": "#198754",
    }
    color = colors.get(priority, "#6c757d")
    return f"<span style='color:{color}; font-weight:700;'>{priority}</span>"

# -----------------------------
# DATABASE SETUP
# -----------------------------
def get_db_connection():
    """Create and return a SQLite database connection."""
    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_relational_knowledge_schema(cursor):
    """Create relational tables for problems, KB articles, solutions, and diagnostic trees.

    This is the normalized foundation for the next upgrade.
    The current UI continues to work while we migrate the Knowledge Base
    and Guided Troubleshooting step by step.
    """

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS problem (
            problem_id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem_code TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'Medium',
            description TEXT,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS solution (
            solution_id INTEGER PRIMARY KEY AUTOINCREMENT,
            solution_code TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            resolution_steps TEXT NOT NULL,
            escalation_required INTEGER NOT NULL DEFAULT 0 CHECK (escalation_required IN (0, 1)),
            escalation_notes TEXT,
            priority_recommendation TEXT CHECK (
                priority_recommendation IN ('low', 'medium', 'high', 'critical')
            ),
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS diagnostic_node (
            diagnostic_node_id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_diagnostic_node_id INTEGER,
            problem_id INTEGER,
            diagnostic_tree_code TEXT NOT NULL,
            node_key TEXT NOT NULL,
            node_type TEXT NOT NULL CHECK (
                node_type IN ('category', 'question', 'check', 'instruction', 'solution')
            ),
            title TEXT NOT NULL,
            description TEXT,
            prompt_text TEXT,
            condition_label TEXT,
            condition_value TEXT,
            solution_id INTEGER,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (parent_diagnostic_node_id)
                REFERENCES diagnostic_node(diagnostic_node_id)
                ON DELETE CASCADE,

            FOREIGN KEY (problem_id)
                REFERENCES problem(problem_id)
                ON DELETE SET NULL,

            FOREIGN KEY (solution_id)
                REFERENCES solution(solution_id),

            CONSTRAINT chk_solution_node_requires_solution
                CHECK (node_type <> 'solution' OR solution_id IS NOT NULL),

            CONSTRAINT chk_non_solution_has_no_solution
                CHECK (node_type = 'solution' OR solution_id IS NULL),

            UNIQUE (diagnostic_tree_code, node_key)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kb_article (
            kb_article_id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem_id INTEGER UNIQUE NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            difficulty TEXT DEFAULT 'Beginner' CHECK (
                difficulty IN ('Beginner', 'Intermediate', 'Advanced')
            ),
            estimated_time TEXT DEFAULT '5 minutes',
            escalation_required INTEGER NOT NULL DEFAULT 0 CHECK (escalation_required IN (0, 1)),
            escalation_notes TEXT,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (problem_id)
                REFERENCES problem(problem_id)
                ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kb_article_tag (
            tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
            kb_article_id INTEGER NOT NULL,
            tag TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,

            FOREIGN KEY (kb_article_id)
                REFERENCES kb_article(kb_article_id)
                ON DELETE CASCADE,

            UNIQUE (kb_article_id, tag)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kb_article_symptom (
            symptom_id INTEGER PRIMARY KEY AUTOINCREMENT,
            kb_article_id INTEGER NOT NULL,
            symptom TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,

            FOREIGN KEY (kb_article_id)
                REFERENCES kb_article(kb_article_id)
                ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kb_article_cause (
            cause_id INTEGER PRIMARY KEY AUTOINCREMENT,
            kb_article_id INTEGER NOT NULL,
            cause TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,

            FOREIGN KEY (kb_article_id)
                REFERENCES kb_article(kb_article_id)
                ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kb_article_user_step (
            user_step_id INTEGER PRIMARY KEY AUTOINCREMENT,
            kb_article_id INTEGER NOT NULL,
            step_text TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,

            FOREIGN KEY (kb_article_id)
                REFERENCES kb_article(kb_article_id)
                ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kb_article_it_step (
            it_step_id INTEGER PRIMARY KEY AUTOINCREMENT,
            kb_article_id INTEGER NOT NULL,
            step_text TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,

            FOREIGN KEY (kb_article_id)
                REFERENCES kb_article(kb_article_id)
                ON DELETE CASCADE
        )
    """)

    # Helpful indexes for search, joins, and diagnostic traversal.
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_problem_code ON problem(problem_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_problem_category ON problem(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_solution_code ON solution(solution_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnostic_node_parent ON diagnostic_node(parent_diagnostic_node_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnostic_node_tree ON diagnostic_node(diagnostic_tree_code)")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_diagnostic_node_tree_parent_sort
        ON diagnostic_node(diagnostic_tree_code, parent_diagnostic_node_id, sort_order)
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnostic_node_solution ON diagnostic_node(solution_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_kb_article_problem ON kb_article(problem_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_kb_article_tag ON kb_article_tag(tag)")



# -----------------------------
# RELATIONAL SEED DATA
# -----------------------------
PROBLEM_SEED_DATA = [('NO_INTERNET_CONNECTION', 'No Internet Connection', 'Network', 'High', 'User cannot access the internet from their device.'), ('SOME_WEBSITES_NOT_LOADING', 'Some Websites Not Loading', 'Network', 'Medium', 'User can access the internet, but one or more websites fail to load.'), ('WIFI_DROPS_FREQUENTLY', 'Wi-Fi Drops Frequently', 'Network', 'Medium', 'User reports frequent wireless disconnections or weak signal.'), ('SLOW_INTERNET', 'Slow Internet', 'Performance', 'Medium', 'User reports that internet access works but is unusually slow.'), ('APPLICATION_CRASHING', 'Application Crashing', 'Software', 'High', 'User reports that an application closes unexpectedly, freezes, or displays a crash error.'), ('SOFTWARE_INSTALLATION_FAILURE', 'Software Installation Failure', 'Software', 'Medium', 'User cannot install software or the installer fails.'), ('COMPUTER_RUNNING_SLOW', 'Computer Running Slow', 'System', 'Medium', 'User reports general slowness, lag, or poor computer performance.'), ('DISK_SPACE_FULL', 'Disk Space Full', 'System', 'Medium', 'User reports that the device is out of storage or cannot save files or install updates.'), ('HIGH_CPU_USAGE', 'High CPU Usage', 'System', 'High', 'User reports fan noise, lag, high CPU usage, or system slowness.'), ('VPN_CONNECTION_FAILURE', 'VPN Connection Failure', 'VPN', 'High', 'User cannot connect to VPN or remote access.')]

SOLUTION_SEED_DATA = [('FIX_RECONNECT_NETWORK', 'Reconnect to the Network', 'The device is not connected to Wi-Fi or Ethernet.', 'Ask the user to reconnect to the correct Wi-Fi network or plug in the Ethernet cable. Confirm the device shows an active network connection before testing internet access again.', 0, None, 'low'), ('FIX_RESTART_NETWORK_EQUIPMENT', 'Restart Device and Network Equipment', 'A temporary device, router, modem, or access point issue may be blocking internet access.', 'Ask the user to restart the computer. If working remotely or at home, ask them to restart the router or modem. After the restart, reconnect to the network and test internet access again.', 0, 'Escalate if multiple users are affected or restarting does not restore service.', 'medium'), ('FIX_ESCALATE_NETWORK_OUTAGE', 'Escalate Possible Network Outage', 'Multiple users or systems may be affected by a network outage.', 'Collect the affected location, number of users affected, device names, time the issue began, and any error messages. Escalate to the Network Team.', 1, 'Escalate immediately if multiple users, departments, or business-critical systems are affected.', 'high'), ('FIX_CHECK_DNS_BROWSER', 'Clear Browser Cache and Check DNS', 'The user may have a DNS, browser cache, or site-specific access issue.', 'Ask the user to try another browser, clear browser cache, restart the browser, and test multiple websites. If only specific websites fail, record the affected URLs.', 0, 'Escalate if DNS errors continue or multiple users cannot access the same websites.', 'medium'), ('FIX_ESCALATE_BLOCKED_WEBSITE', 'Escalate Possible Blocked Website', 'The website may be blocked by policy, firewall, DNS filtering, or content filtering.', 'Collect the full website URL, screenshot of the error, user location, network used, and business justification. Escalate to IT Security or Network Team.', 1, 'Do not bypass security filtering without approval.', 'medium'), ('FIX_MOVE_CLOSER_TO_AP', 'Improve Wi-Fi Signal Strength', 'The Wi-Fi connection may be weak or unstable due to distance, interference, or poor signal.', 'Ask the user to move closer to the access point, remove physical obstructions if possible, disconnect and reconnect to Wi-Fi, and test again.', 0, 'Escalate if the issue happens in a known office area or affects multiple users.', 'medium'), ('FIX_FORGET_REJOIN_WIFI', 'Forget and Rejoin Wi-Fi Network', 'The saved Wi-Fi profile may be corrupted or using outdated credentials.', 'Ask the user to forget the Wi-Fi network, reconnect to the correct network, re-enter credentials, and test stability.', 0, None, 'low'), ('FIX_ESCALATE_WIFI_INFRASTRUCTURE', 'Escalate Wi-Fi Infrastructure Issue', 'Wi-Fi drops may be caused by an access point, roaming, interference, or infrastructure issue.', 'Collect location, device name, time of drops, signal strength if available, whether other users are affected, and frequency of disconnects. Escalate to the Network Team.', 1, 'Escalate if multiple users in the same location report drops.', 'high'), ('FIX_CLOSE_BANDWIDTH_APPS', 'Close Bandwidth-Heavy Applications', 'Streaming, large downloads, cloud sync, or video calls may be consuming bandwidth.', 'Ask the user to pause large downloads, close streaming applications, pause cloud sync temporarily, and retest the connection speed.', 0, None, 'low'), ('FIX_RUN_SPEED_TEST_ESCALATE', 'Document Speed Test and Escalate', 'The connection may be slower than expected after basic troubleshooting.', 'Ask the user to run a speed test, record download and upload results, note whether connected by Wi-Fi or Ethernet, and escalate if the speed is significantly below expected service levels.', 1, 'Escalate if multiple users report slow internet or speed is far below the expected baseline.', 'medium'), ('FIX_RESTART_APPLICATION', 'Restart the Application', 'The application may be stuck or temporarily unstable.', 'Ask the user to save work if possible, close the application completely, reopen it, and test again.', 0, None, 'low'), ('FIX_UPDATE_APPLICATION', 'Update or Repair the Application', 'The application may be crashing because it is outdated, corrupted, or missing required components.', 'Ask the user to check for updates. If supported, run the application repair option or reinstall using the approved software source.', 0, 'Escalate if the application requires admin rights or continues crashing after repair.', 'medium'), ('FIX_ESCALATE_APP_CRASH', 'Escalate Application Crash', 'The application crash may require advanced troubleshooting, logs, vendor support, or administrator access.', 'Collect the app name, version, operating system, crash message, screenshots, when the crash occurs, and whether other users are affected. Escalate to the Application Support Team.', 1, 'Escalate immediately if the affected app is business-critical.', 'high'), ('FIX_USE_APPROVED_INSTALLER', 'Use Approved Software Installer', 'The user may be using an unsupported installer or source.', 'Direct the user to the approved software portal or company-provided installer. Retry installation using the approved source.', 0, 'Do not install software from untrusted websites.', 'low'), ('FIX_FREE_SPACE_FOR_INSTALL', 'Free Disk Space and Retry Installation', 'The installation may be failing because the device does not have enough available disk space.', 'Ask the user to remove unnecessary files, empty the recycle bin or trash, and retry installation after confirming sufficient free space.', 0, None, 'medium'), ('FIX_ESCALATE_INSTALL_ADMIN', 'Escalate Installation Requiring Admin Rights', 'The software installation may require administrator privileges, licensing, or endpoint management approval.', 'Collect the software name, version, business reason, installer source, error message, and user device name. Escalate to IT Support or Endpoint Management.', 1, 'Do not share administrator credentials with the user.', 'medium'), ('FIX_RESTART_COMPUTER', 'Restart the Computer', 'The computer may be slow because of a temporary system issue or pending updates.', 'Ask the user to save work, restart the computer, sign back in, and test performance again.', 0, None, 'low'), ('FIX_DISABLE_STARTUP_APPS', 'Reduce Startup Applications', 'Too many startup applications may be slowing the computer.', 'Ask the user to close unnecessary applications. For supported users, review startup applications and disable non-essential startup items according to company policy.', 0, 'Escalate if startup controls require admin access.', 'medium'), ('FIX_ESCALATE_HARDWARE_PERFORMANCE', 'Escalate Possible Hardware Performance Issue', 'The computer may need hardware review, memory upgrade, storage replacement, or deeper endpoint troubleshooting.', 'Collect device name, operating system, available disk space, CPU and memory usage, recent changes, and examples of slow behavior. Escalate to Desktop Support.', 1, 'Escalate if the device is unusable or repeatedly freezes.', 'medium'), ('FIX_EMPTY_TRASH_DOWNLOADS', 'Remove Unneeded Files', 'The disk is full because of accumulated downloads, recycle bin contents, temporary files, or large personal files.', 'Ask the user to empty recycle bin or trash, delete unnecessary downloads, remove duplicate files, and move approved files to cloud or network storage.', 0, None, 'low'), ('FIX_CLEAN_TEMP_FILES', 'Clean Temporary Files', 'Temporary system files may be consuming disk space.', 'Use approved system cleanup tools to remove temporary files, cache, and old update files. Restart the computer and check available space again.', 0, 'Escalate if cleanup requires admin rights or space fills again quickly.', 'medium'), ('FIX_ESCALATE_STORAGE_EXPANSION', 'Escalate Storage Capacity Issue', 'The device may need storage expansion, profile cleanup, or deeper investigation.', 'Collect available disk space, largest folders if known, device name, user role, and business need. Escalate to Desktop Support.', 1, 'Escalate if less than 5 percent disk space remains or the system cannot complete updates.', 'medium'), ('FIX_CLOSE_HIGH_CPU_PROCESS', 'Close High CPU Application', 'One application or process may be consuming excessive CPU.', 'Ask the user to close unnecessary applications. If a specific application is using high CPU, restart that application and retest.', 0, 'Escalate if the high CPU process is security software, system service, or unknown.', 'medium'), ('FIX_REBOOT_AFTER_HIGH_CPU', 'Restart After High CPU Usage', 'High CPU usage may be caused by a stuck process or pending update.', 'Ask the user to save work, restart the computer, and monitor CPU usage after signing back in.', 0, None, 'low'), ('FIX_ESCALATE_MALWARE_OR_ENDPOINT', 'Escalate Possible Malware or Endpoint Issue', 'Unknown processes, repeated high CPU, or suspicious behavior may indicate malware or endpoint management issues.', 'Collect screenshots, process names, device name, user name, recent downloads, and symptoms. Escalate to Security or Endpoint Support.', 1, 'Escalate immediately if suspicious processes, pop-ups, or security alerts are present.', 'high'), ('FIX_CHECK_VPN_CREDENTIALS_MFA', 'Check VPN Credentials and MFA', 'The VPN failure may be caused by incorrect credentials, expired password, or MFA issue.', 'Ask the user to confirm their username, reset or verify password if needed, approve the MFA prompt, and retry VPN login.', 0, 'Escalate if MFA is not received or the account appears locked.', 'medium'), ('FIX_CHANGE_NETWORK_RETRY_VPN', 'Try Another Network for VPN', 'The current network may be blocking or interfering with VPN traffic.', 'Ask the user to try a different network, such as a mobile hotspot, trusted home network, or wired connection. Retry VPN after switching networks.', 0, None, 'medium'), ('FIX_UPDATE_VPN_CLIENT', 'Update or Reinstall VPN Client', 'The VPN client may be outdated, corrupted, or misconfigured.', 'Ask the user to update the VPN client using the approved software source. If needed, reinstall the client according to company instructions.', 0, 'Escalate if installation requires admin rights.', 'medium'), ('FIX_ESCALATE_VPN_SUPPORT', 'Escalate VPN Connection Failure', 'The VPN issue may require account, network, certificate, or client configuration review.', 'Collect username, device name, VPN client version, error message, network type, time of failure, MFA status, and screenshots. Escalate to Network or VPN Support.', 1, 'Escalate immediately if multiple users cannot connect to VPN.', 'high')]


def seed_problem_and_solution_data(cursor):
    """Seed stable problem and solution reference data.

    This step only inserts into the new relational tables:
    - problem
    - solution

    It uses INSERT OR IGNORE so app restarts do not duplicate rows or
    rewrite timestamps.
    """

    cursor.executemany(
        """
        INSERT OR IGNORE INTO problem (
            problem_code,
            title,
            category,
            severity,
            description
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        PROBLEM_SEED_DATA,
    )

    cursor.executemany(
        """
        INSERT OR IGNORE INTO solution (
            solution_code,
            title,
            summary,
            resolution_steps,
            escalation_required,
            escalation_notes,
            priority_recommendation
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        SOLUTION_SEED_DATA,
    )


def initialize_database():
    """Create SQLite tables if they do not already exist."""
    connection = get_db_connection()
    cursor = connection.cursor()

    initialize_relational_knowledge_schema(cursor)
    seed_problem_and_solution_data(cursor)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'User'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            severity TEXT NOT NULL,
            tags TEXT,
            symptoms TEXT,
            causes TEXT,
            user_steps TEXT,
            it_steps TEXT,
            steps TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            email TEXT,
            issue TEXT NOT NULL,
            description TEXT NOT NULL,
            severity TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open',
            assigned_to TEXT DEFAULT 'Unassigned',
            resolution_notes TEXT DEFAULT '',
            likely_infrastructure INTEGER DEFAULT 0,
            unread_for_admin INTEGER DEFAULT 1,
            unread_for_user INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticket_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            author TEXT NOT NULL,
            role TEXT NOT NULL,
            comment TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id) REFERENCES tickets (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticket_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            original_name TEXT NOT NULL,
            saved_name TEXT NOT NULL,
            path TEXT NOT NULL,
            file_type TEXT,
            size INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id) REFERENCES tickets (id)
        )
    """)

    # Add ticket_data column for full ticket JSON storage during migration.
    cursor.execute("PRAGMA table_info(tickets)")
    ticket_columns = [column[1] for column in cursor.fetchall()]
    if "ticket_data" not in ticket_columns:
        cursor.execute("ALTER TABLE tickets ADD COLUMN ticket_data TEXT")

    # Add Knowledge Base article quality columns during migration.
    cursor.execute("PRAGMA table_info(issues)")
    issue_columns = [column[1] for column in cursor.fetchall()]

    issue_quality_columns = {
        "difficulty": "TEXT DEFAULT 'Beginner'",
        "estimated_time": "TEXT DEFAULT '5 minutes'",
        "applies_to": "TEXT DEFAULT '[]'",
        "escalation_required": "INTEGER DEFAULT 0",
        "last_updated": "TEXT DEFAULT ''",
    }

    for column_name, column_definition in issue_quality_columns.items():
        if column_name not in issue_columns:
            cursor.execute(f"ALTER TABLE issues ADD COLUMN {column_name} {column_definition}")

    connection.commit()
    connection.close()


# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(page_title="IT Troubleshooting Tool", layout="wide")


# -----------------------------
# GLOBAL UI STYLING
# -----------------------------
def apply_global_styles():
    """Apply app-wide visual polish."""
    st.markdown("""
    <style>
    /* Main app spacing */
    .block-container {
        padding-top: 1.25rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f8f9fb 0%, #eef2f7 100%);
        border-right: 1px solid #d9dee8;
    }

    section[data-testid="stSidebar"] .stRadio label {
        font-weight: 500;
    }

    /* Dashboard metrics */
    [data-testid="metric-container"] {
        background: #ffffff;
        border: 1px solid #d8dee9;
        padding: 14px;
        border-radius: 14px;
        box-shadow: 0 2px 8px rgba(31, 41, 55, 0.08);
    }

    [data-testid="metric-container"] label {
        color: #4b5563 !important;
        font-weight: 600;
    }

    [data-testid="metric-container"] div[data-testid="stMetricValue"] {
        color: #111827;
        font-weight: 700;
    }

    /* Expanders as cards */
    div[data-testid="stExpander"] {
        background: #ffffff;
        border: 1px solid #d8dee9;
        border-radius: 14px;
        margin-bottom: 12px;
        box-shadow: 0 2px 6px rgba(31, 41, 55, 0.05);
    }

    div[data-testid="stExpander"] details summary {
        font-weight: 600;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 10px;
        padding: 0.45rem 1rem;
        font-weight: 600;
        border: 1px solid #cfd6e4;
    }

    .stButton > button:hover {
        border-color: #4e89ff;
        color: #1d4ed8;
    }

    /* Inputs */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        border-radius: 10px;
    }

    /* Alerts */
    .stAlert {
        border-radius: 12px;
        border: 1px solid rgba(0,0,0,0.05);
    }

    /* Custom cards */
    .app-card {
        padding: 1rem;
        background: #ffffff;
        border: 1px solid #d8dee9;
        border-radius: 14px;
        box-shadow: 0 2px 8px rgba(31, 41, 55, 0.06);
        margin-bottom: 1rem;
    }

    .description-box {
        padding: 14px;
        background: #f8fafc;
        border-left: 5px solid #4e89ff;
        border-radius: 10px;
        margin-bottom: 1rem;
        line-height: 1.5;
    }

    .sidebar-footer {
        margin-top: 1rem;
        padding: 0.75rem;
        background: #ffffff;
        border: 1px solid #d8dee9;
        border-radius: 12px;
        font-size: 0.85rem;
        color: #4b5563;
    }

    h1 {
        color: #172033;
    }

    h2, h3 {
        color: #1f2937;
        letter-spacing: -0.02em;
    }
    </style>
    """, unsafe_allow_html=True)


def render_description_box(text):
    """Render ticket descriptions in a readable box."""
    safe_text = str(text or "No description provided.")
    st.markdown(
        f"""
        <div class="description-box">
            {safe_text}
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_priority_text(priority):
    """Return colored HTML for priority labels."""
    colors = {
        "Critical": "#dc3545",
        "High": "#fd7e14",
        "Medium": "#0d6efd",
        "Low": "#198754",
    }
    color = colors.get(priority, "#6c757d")
    return f"<span style='color:{color}; font-weight:700;'>{priority}</span>"

# -----------------------------
# DATA
# -----------------------------
issues = [
    {
        "title": "No Internet Connection",
        "category": "Network",
        "severity": "High",
        "tags": ["internet", "connectivity", "dhcp"],
        "symptoms": ["No websites load", "Ping fails", "No network icon"],
        "causes": ["DHCP failure", "Cable unplugged", "Router failure"],
        "steps": ["Check cable/Wi-Fi", "ipconfig /renew", "Restart adapter"]
    },
    {
        "title": "DNS Resolution Failure",
        "category": "DNS",
        "severity": "High",
        "tags": ["dns", "resolution"],
        "symptoms": ["Domains not resolving", "IP works but names fail"],
        "causes": ["Wrong DNS", "DNS outage", "Cache corruption"],
        "steps": ["nslookup test", "flushdns", "change DNS"]
    },
    {
        "title": "Slow Internet",
        "category": "Performance",
        "severity": "Medium",
        "tags": ["slow", "latency"],
        "symptoms": ["Buffering", "Slow downloads"],
        "causes": ["Congestion", "Background apps"],
        "steps": ["Speed test", "Close apps", "Restart router"]
    },
    {
        "title": "VPN Connection Failure",
        "category": "VPN",
        "severity": "High",
        "tags": ["vpn"],
        "symptoms": ["Cannot connect", "Timeout"],
        "causes": ["Firewall", "Server down"],
        "steps": ["Check internet", "Check firewall", "Restart client"]
    },
    {
        "title": "Email Not Sending",
        "category": "Email",
        "severity": "Medium",
        "tags": ["smtp", "email"],
        "symptoms": ["Emails stuck in outbox", "Send failure"],
        "causes": ["SMTP misconfig", "Auth failure"],
        "steps": ["Check SMTP settings", "Re-login account", "Test mail server"]
    },
    {
        "title": "Email Not Receiving",
        "category": "Email",
        "severity": "Medium",
        "tags": ["imap", "email"],
        "symptoms": ["No new emails", "Inbox not updating"],
        "causes": ["IMAP issue", "Sync disabled"],
        "steps": ["Check sync", "Reconnect account", "Check server status"]
    },
    {
        "title": "Computer Running Slow",
        "category": "System",
        "severity": "Medium",
        "tags": ["performance"],
        "symptoms": ["Lag", "Slow startup"],
        "causes": ["High CPU", "Low RAM"],
        "steps": ["Task manager", "Disable startup apps", "Restart"]
    },
    {
        "title": "Application Crashing",
        "category": "Software",
        "severity": "High",
        "tags": ["crash"],
        "symptoms": ["App closes", "Error popup"],
        "causes": ["Bug", "Corrupt install"],
        "steps": ["Reinstall app", "Check logs", "Update software"]
    },
    {
        "title": "Printer Not Working",
        "category": "Hardware",
        "severity": "Low",
        "tags": ["printer"],
        "symptoms": ["No print", "Offline printer"],
        "causes": ["Driver issue", "Connection issue"],
        "steps": ["Restart printer", "Check drivers", "Reconnect"]
    },
    {
        "title": "Disk Space Full",
        "category": "System",
        "severity": "Medium",
        "tags": ["storage"],
        "symptoms": ["Low disk warning", "Cannot save files"],
        "causes": ["Too many files", "Logs accumulation"],
        "steps": ["Delete temp files", "Empty recycle bin", "Extend storage"]
    },
    {
        "title": "High CPU Usage",
        "category": "System",
        "severity": "High",
        "tags": ["cpu"],
        "symptoms": ["Fan noise", "System lag"],
        "causes": ["Background process", "Malware"],
        "steps": ["Task manager", "End process", "Run antivirus"]
    },
    {
        "title": "Login Failure",
        "category": "Authentication",
        "severity": "High",
        "tags": ["login"],
        "symptoms": ["Wrong password", "Access denied"],
        "causes": ["Wrong credentials", "Locked account"],
        "steps": ["Reset password", "Unlock account", "Contact admin"]
    },
    {
        "title": "Wi-Fi Drops Frequently",
        "category": "Network",
        "severity": "Medium",
        "tags": ["wifi"],
        "symptoms": ["Disconnects", "Weak signal"],
        "causes": ["Interference", "Router issue"],
        "steps": ["Move closer", "Change channel", "Restart router"]
    },
    {
        "title": "Software Installation Failure",
        "category": "Software",
        "severity": "Medium",
        "tags": ["install"],
        "symptoms": ["Install error", "Setup fails"],
        "causes": ["Permissions", "Corrupt file"],
        "steps": ["Run as admin", "Redownload", "Check logs"]
    }
    ,
    {
        "title": "Some Websites Not Loading",
        "category": "Network",
        "severity": "Medium",
        "tags": ["website", "web", "browser", "dns", "partial connectivity"],
        "symptoms": [
            "Internet works but one website does not load",
            "Some websites open but others fail",
            "Page keeps loading or times out",
            "Website works on another device or network"
        ],
        "causes": [
            "Website server is down",
            "DNS issue for a specific domain",
            "Browser cache or cookies problem",
            "Firewall or security policy blocking the website",
            "ISP routing issue"
        ],
        "steps": [
            "Try opening another website to confirm internet works",
            "Try the same website in another browser or private mode",
            "Clear browser cache and cookies",
            "Run nslookup for the website domain",
            "Flush DNS cache using ipconfig /flushdns",
            "Try changing DNS to 8.8.8.8 or 1.1.1.1",
            "Check if the website is down for everyone",
            "Check firewall, antivirus, or company web filtering rules"
        ]
    }
]

# -----------------------------
# SIMPLE LOGIN CONFIG
# -----------------------------
users = {
    "user": {"password": "user123", "role": "User", "email": "user@example.com"},
    "admin": {"password": "admin123", "role": "Admin", "email": "admin@example.com"},
}


def create_user(username, email, password, role="User"):
    """Create a user in the SQLite database."""
    username_clean = username.strip()
    email_clean = email.strip()

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO users (username, email, password, role)
            VALUES (?, ?, ?, ?)
            """,
            (username_clean, email_clean, password, role),
        )
        connection.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        connection.close()


def get_user(username):
    """Get one user from the SQLite database."""
    username_clean = username.strip()

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username_clean,))
    user = cursor.fetchone()
    connection.close()

    return dict(user) if user else None


def ensure_default_users():
    """Create default demo users if they do not exist."""
    for username, account in users.items():
        if not get_user(username):
            create_user(
                username=username,
                email=account.get("email", ""),
                password=account["password"],
                role=account["role"],
            )


def load_users():
    """Keep demo users available in SQLite."""
    ensure_default_users()


# -----------------------------
# ROLE-BASED STEP HELPERS
# -----------------------------
def is_likely_infrastructure_issue(description):
    """Detect if a ticket/issue sounds like a wider IT infrastructure problem."""
    if not description:
        return False

    text = description.lower()

    infrastructure_keywords = [
        "multiple users",
        "all users",
        "department",
        "same floor",
        "everyone",
        "shared drive",
        "network drive",
        "file server",
        "server",
        "unavailable",
        "cannot access",
        "network path not found",
        "started around",
        "began around",
        "outage",
    ]

    return any(keyword in text for keyword in infrastructure_keywords)


def get_user_friendly_steps(issue):
    """Return safe, category-aware, non-technical steps for end users."""
    if issue.get("user_steps"):
        return issue["user_steps"]

    category = issue.get("category", "").lower()
    title = issue.get("title", "").lower()

    if "email" in category or "email" in title or "outlook" in title:
        return [
            "Close and reopen your email application",
            "Try accessing your email using a web browser",
            "Restart your device",
            "Check if other users have the same email issue",
            "Take note of any error message",
            "Create a support ticket if the issue continues",
        ]

    if "network" in category or "wifi" in title or "wi-fi" in title or "internet" in title:
        return [
            "Check that Wi-Fi or the network cable is connected",
            "Restart your device",
            "Try disconnecting and reconnecting to the network",
            "Ask a nearby colleague if they have the same issue",
            "Take note of any error message",
            "Create a support ticket if the issue continues",
        ]

    if "printer" in title or "hardware" in category:
        return [
            "Check that the device is powered on",
            "Check that cables are connected if applicable",
            "Restart the device if safe to do so",
            "Try again after a few minutes",
            "Create a support ticket if the issue continues",
        ]

    if "software" in category or "application" in title or "app" in title:
        return [
            "Close and reopen the application",
            "Restart your device",
            "Try the same action again",
            "Take a screenshot or note the error message",
            "Create a support ticket if the issue continues",
        ]

    if "authentication" in category or "login" in title or "password" in title:
        return [
            "Check that your username is entered correctly",
            "Try logging in again carefully",
            "Restart the application or browser",
            "Take note of the exact error message",
            "Create a support ticket if you are still blocked",
        ]

    if "storage" in category or "disk" in title:
        return [
            "Close files or applications you are not using",
            "Delete files you no longer need if allowed",
            "Empty the recycle bin if safe to do so",
            "Restart your device",
            "Create a support ticket if you still cannot save files",
        ]

    return [
        "Restart your device",
        "Try again after a few minutes",
        "Take note of any error message you see",
        "Ask a colleague nearby if they have the same issue",
        "Create a support ticket and describe the issue in detail",
    ]


def get_user_guidance_for_ticket(description):
    """Return user-facing guidance based on the ticket description."""
    if is_likely_infrastructure_issue(description):
        return [
            "This may be a wider IT issue affecting multiple users or a shared service",
            "Do not try advanced technical troubleshooting yourself",
            "Create or submit a support ticket with the affected location, department, time started, and exact error message",
            "Ask affected users to avoid repeated changes while IT investigates",
        ]

    return [
        "Try the suggested user-friendly steps first",
        "If the issue continues, create a support ticket with details",
        "Include what you were trying to do, when it started, and any error message",
    ]


def get_it_steps(issue):
    """Return technical troubleshooting steps for admins."""
    if issue.get("it_steps"):
        return issue["it_steps"]
    return issue.get("steps", [])


def show_role_based_steps(issue):
    """Display troubleshooting steps depending on the logged-in role."""
    role = st.session_state.get("role", "User")

    if role == "Admin":
        st.write("**Advanced IT Troubleshooting Steps:**")
        for number, step in enumerate(get_it_steps(issue), 1):
            st.write(f"{number}. {step}")

        with st.expander("User-Friendly Steps"):
            for number, step in enumerate(get_user_friendly_steps(issue), 1):
                st.write(f"{number}. {step}")
    else:
        st.write("**Recommended User Actions:**")
        for number, step in enumerate(get_user_friendly_steps(issue), 1):
            st.write(f"{number}. {step}")


# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def login_user(username, password):
    """Validate a user login using SQLite."""
    username_clean = username.strip()
    account = get_user(username_clean)

    if account and account["password"] == password:
        st.session_state["logged_in"] = True
        st.session_state["username"] = username_clean
        st.session_state["role"] = account["role"]
        return True

    return False


def logout_user():
    """Clear login session."""
    st.session_state["logged_in"] = False
    st.session_state.pop("username", None)
    st.session_state.pop("role", None)


def show_login_page():
    """Show login and registration forms."""
    st.title("🔐 IT Troubleshooting Login")

    tab_login, tab_register = st.tabs(["Login", "Create Account"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login")

            if submitted:
                if login_user(username, password):
                    st.success("Login successful")
                    st.rerun()
                else:
                    st.error("Invalid username or password")

        st.markdown("### 🔑 Demo Credentials")
        col_user, col_admin = st.columns(2)

        with col_user:
            st.info(
                "**User Account**\n\n"
                "Username: `user`\n\n"
                "Password: `user123`"
            )

        with col_admin:
            st.warning(
                "**Admin Account**\n\n"
                "Username: `admin`\n\n"
                "Password: `admin123`"
            )

        st.caption(
            "⚠️ Demo app only. Do not enter real passwords, confidential company data, "
            "or sensitive support information."
        )

    with tab_register:
        with st.form("register_form"):
            new_username = st.text_input("Choose a username", key="register_username")
            new_email = st.text_input("Email", key="register_email")
            new_password = st.text_input("Password", type="password", key="register_password")
            confirm_password = st.text_input("Confirm password", type="password", key="confirm_password")
            submitted_register = st.form_submit_button("Create Account")

            if submitted_register:
                username_clean = new_username.strip()
                email_clean = new_email.strip()

                if not username_clean or not email_clean or not new_password:
                    st.error("Username, email, and password are required")
                elif get_user(username_clean):
                    st.error("This username already exists")
                elif new_password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    created = create_user(
                        username=username_clean,
                        email=email_clean,
                        password=new_password,
                        role="User",
                    )
                    if created:
                        st.success("✅ Account created. You can now log in.")
                    else:
                        st.error("Could not create account. Please try another username.")


def require_admin():
    """Stop access if current user is not an admin."""
    if st.session_state.get("role") != "Admin":
        st.error("Admin access required")
        st.stop()


def show_recommendations(title, message_type="info", items=None):
    """Display a troubleshooting result and store it for reporting."""
    items = items or []

    # Store result in session for report
    st.session_state["last_result"] = {
        "title": title,
        "type": message_type,
        "actions": items
    }

    if message_type == "error":
        st.error(title)
    elif message_type == "warning":
        st.warning(title)
    elif message_type == "success":
        st.success(title)
    else:
        st.info(title)

    for item in items:
        st.write(f"- {item}")

    show_download_button()


def ask_radio(question, options, key):
    """Create a radio question and stop until the user chooses an answer."""
    answer = st.radio(question, options, key=key)

    if answer == "Select":
        st.stop()

    return answer


def get_issue_titles_for_guided_mode():
    """Return issues currently available in guided troubleshooting mode."""
    return [
        "None",
        "No Internet Connection",
        "DNS Resolution Failure",
        "Slow Internet Performance",
        "VPN Connection Failure",
        "Wi-Fi Connected But No Internet",
    ]


def get_categories():
    """Return unique issue categories for filtering."""
    return ["All"] + sorted(set(issue["category"] for issue in issues))


def normalize_search_text(text):
    """Normalize text for searching."""
    return text.lower().strip()


def calculate_search_score(issue, search_query):
    """Calculate how strongly an issue matches the search query."""
    if not search_query:
        return 1

    stop_words = {
        "a", "an", "and", "are", "as", "at", "be", "but", "by", "for",
        "from", "had", "has", "have", "i", "in", "is", "it", "of", "on",
        "or", "that", "the", "this", "to", "was", "were", "with", "works",
        "fine", "tried", "try", "connect", "connected", "morning",
        "issue", "problem", "problems", "trouble", "error", "errors", "working"
    }

    query_words = [
        word
        for word in normalize_search_text(search_query).replace(".", " ").replace(",", " ").split()
        if word not in stop_words and len(word) > 2
    ]

    if not query_words:
        return 0

    score = 0

    title = normalize_search_text(issue["title"])
    category = normalize_search_text(issue["category"])
    severity = normalize_search_text(issue["severity"])
    tags = [normalize_search_text(tag) for tag in issue.get("tags", [])]
    symptoms = [normalize_search_text(symptom) for symptom in issue.get("symptoms", [])]
    causes = [normalize_search_text(cause) for cause in issue.get("causes", [])]
    steps = [normalize_search_text(step) for step in issue.get("steps", [])]

    full_text = " ".join([title, category, severity] + tags + symptoms + causes + steps)
    exact_query = normalize_search_text(search_query)

    if exact_query in title:
        score += 80
    if exact_query in full_text:
        score += 20

    for word in query_words:
        if word in title:
            score += 30
        if word in tags:
            score += 25
        if word in category:
            score += 15
        if any(word in symptom for symptom in symptoms):
            score += 18
        if any(word in cause for cause in causes):
            score += 12
        if any(word in step for step in steps):
            score += 8

    # Boost very specific real-world partial connectivity cases
    partial_website_words = {"website", "websites", "page", "load", "loading", "internet"}
    if partial_website_words.intersection(query_words):
        if issue["title"] == "Some Websites Not Loading":
            score += 100
        elif issue["title"] == "DNS Resolution Failure":
            score += 40
        elif issue["title"] == "Firewall Blocking Application":
            score += 25

    return score


def issue_matches_filters(issue, selected_category, selected_severity, search_query):
    """Apply category, severity, and search filters."""
    if selected_category != "All" and issue["category"] != selected_category:
        return False

    if selected_severity != "All" and issue["severity"] != selected_severity:
        return False

    return calculate_search_score(issue, search_query) > 0



def show_issue_metadata(issue):
    """Display professional Knowledge Base article metadata."""
    meta_col1, meta_col2, meta_col3 = st.columns(3)

    meta_col1.write(f"**Difficulty:** {issue.get('difficulty', 'Beginner')}")
    meta_col2.write(f"**Estimated Time:** {issue.get('estimated_time', '5 minutes')}")
    meta_col3.write(f"**Escalation Required:** {'Yes' if issue.get('escalation_required') else 'No'}")

    applies_to = issue.get("applies_to", [])
    if applies_to:
        st.write("**Applies To:**", ", ".join(applies_to))

    if issue.get("last_updated"):
        st.caption(f"Last updated: {issue.get('last_updated')}")

def show_severity(severity):
    """Display severity using Streamlit status styles."""
    if severity == "High":
        st.error(f"Severity: {severity}")
    elif severity == "Medium":
        st.warning(f"Severity: {severity}")
    else:
        st.info(f"Severity: {severity}")


def show_download_button():
    """Provide a download button for troubleshooting report."""
    result = st.session_state.get("last_result")
    if not result:
        return

    report = f"""IT Troubleshooting Report
Result: {result['title']}
Severity: {result['type']}

Recommended Actions:
"""

    for action in result["actions"]:
        report += f"- {action}"

    st.download_button(
        label="📄 Download Report",
        data=report,
        file_name="troubleshooting_report.txt",
        mime="text/plain"
    )


def show_issue_card(issue, search_score=None):
    """Display one knowledge base issue."""
    title = issue["title"]

    if search_score is not None:
        title = f"{title} — Match score: {search_score}"

    with st.expander(title):
        st.write("**Category:**", issue["category"])
        show_severity(issue["severity"])
        show_issue_metadata(issue)
        st.write("**Tags:**", ", ".join(issue["tags"]))

        st.write("**Symptoms:**")
        for symptom in issue["symptoms"]:
            st.write("-", symptom)

        st.write("**Causes:**")
        for cause in issue["causes"]:
            st.write("-", cause)

        show_role_based_steps(issue)


# -----------------------------
# GUIDED TROUBLESHOOTING DATA
# -----------------------------
guided_flows = {
    "No Internet Connection": {
        "subtitle": "🔌 No Internet Connection Flow",
        "start": "q1",
        "questions": {
            "q1": {
                "text": "Can you ping your default gateway?",
                "options": ["Yes", "No"],
                "answers": {
                    "No": {
                        "result": "👉 Likely LOCAL NETWORK issue",
                        "type": "error",
                        "actions": [
                            "Check Wi-Fi / Ethernet cable",
                            "Run: ipconfig /renew",
                            "Restart network adapter",
                        ],
                    },
                    "Yes": {"next": "q2"},
                },
            },
            "q2": {
                "text": "Can you ping 8.8.8.8?",
                "options": ["Yes", "No"],
                "answers": {
                    "No": {
                        "result": "👉 Likely ROUTER or ISP issue",
                        "type": "error",
                        "actions": ["Restart router", "Check ISP status"],
                    },
                    "Yes": {"next": "q3"},
                },
            },
            "q3": {
                "text": "Can you open websites (e.g. google.com)?",
                "options": ["Yes", "No"],
                "answers": {
                    "No": {
                        "result": "👉 Likely DNS issue",
                        "type": "warning",
                        "actions": [
                            "Run: nslookup google.com",
                            "Run: ipconfig /flushdns",
                            "Change DNS to 8.8.8.8",
                        ],
                    },
                    "Yes": {
                        "result": "✔ Network is fully working",
                        "type": "success",
                        "actions": [],
                    },
                },
            },
        },
    },
    "DNS Resolution Failure": {
        "subtitle": "🌐 DNS Troubleshooting Flow",
        "start": "q1",
        "questions": {
            "q1": {
                "text": "Can you ping 8.8.8.8?",
                "options": ["Yes", "No"],
                "answers": {
                    "No": {
                        "result": "👉 This is NOT a DNS issue (network problem instead)",
                        "type": "error",
                        "actions": [
                            "Check IP configuration",
                            "Check gateway connectivity",
                        ],
                    },
                    "Yes": {"next": "q2"},
                },
            },
            "q2": {
                "text": "Can you access websites using domain names (e.g. google.com)?",
                "options": ["Yes", "No"],
                "answers": {
                    "No": {
                        "result": "👉 DNS issue detected",
                        "type": "warning",
                        "actions": [
                            "Run: nslookup google.com",
                            "Run: ipconfig /flushdns",
                            "Change DNS to 8.8.8.8 or 1.1.1.1",
                        ],
                    },
                    "Yes": {
                        "result": "✔ DNS is working correctly",
                        "type": "success",
                        "actions": [],
                    },
                },
            },
        },
    },
    "Slow Internet": {
        "subtitle": "🐢 Slow Internet Flow",
        "start": "q1",
        "questions": {
            "q1": {
                "text": "Is CPU or network usage high on your device?",
                "options": ["Yes", "No"],
                "answers": {
                    "Yes": {
                        "result": "👉 Local system overload",
                        "type": "warning",
                        "actions": [
                            "Close heavy applications",
                            "Check Task Manager",
                            "Stop background downloads",
                        ],
                    },
                    "No": {"next": "q2"},
                },
            },
            "q2": {
                "text": "Is the issue affecting all devices?",
                "options": ["Yes", "No"],
                "answers": {
                    "Yes": {
                        "result": "👉 Network congestion likely",
                        "type": "warning",
                        "actions": [
                            "Restart router",
                            "Run speed test",
                            "Check ISP issues",
                        ],
                    },
                    "No": {
                        "result": "👉 Device-specific issue likely",
                        "type": "info",
                        "actions": [],
                    },
                },
            },
        },
    },
    "VPN Connection Failure": {
        "subtitle": "🔐 VPN Troubleshooting Flow",
        "start": "q1",
        "questions": {
            "q1": {
                "text": "Does normal internet work?",
                "options": ["Yes", "No"],
                "answers": {
                    "No": {
                        "result": "👉 Fix internet first before VPN troubleshooting",
                        "type": "error",
                        "actions": [],
                    },
                    "Yes": {"next": "q2"},
                },
            },
            "q2": {
                "text": "Does VPN connect or fail immediately?",
                "options": ["Connects", "Fails"],
                "answers": {
                    "Fails": {
                        "result": "👉 Likely firewall or credential issue",
                        "type": "warning",
                        "actions": [
                            "Check credentials",
                            "Check firewall rules",
                            "Restart VPN client",
                        ],
                    },
                    "Connects": {
                        "result": "✔ VPN is working",
                        "type": "success",
                        "actions": [],
                    },
                },
            },
        },
    },
    "Wi-Fi Drops Frequently": {
        "subtitle": "📶 Wi-Fi Issue Flow",
        "start": "q1",
        "questions": {
            "q1": {
                "text": "Can you ping your default gateway?",
                "options": ["Yes", "No"],
                "answers": {
                    "No": {
                        "result": "👉 Router or Wi-Fi connection issue",
                        "type": "error",
                        "actions": ["Forget and reconnect Wi-Fi", "Restart router"],
                    },
                    "Yes": {"next": "q2"},
                },
            },
            "q2": {
                "text": "Can you open websites?",
                "options": ["Yes", "No"],
                "answers": {
                    "No": {
                        "result": "👉 Likely DNS issue",
                        "type": "warning",
                        "actions": ["Flush DNS cache", "Change DNS server"],
                    },
                    "Yes": {
                        "result": "✔ Internet is working correctly",
                        "type": "success",
                        "actions": [],
                    },
                },
            },
        },
    },
}


# -----------------------------
# GUIDED TROUBLESHOOTING ENGINE
# -----------------------------
def find_issue_by_title(title):
    """Find an issue from the knowledge base by title."""
    for issue in issues:
        if issue["title"] == title:
            return issue
    return None


def run_guided_flow(flow_name):
    """Run a guided troubleshooting flow from guided_flows data."""
    flow = guided_flows[flow_name]
    questions = flow["questions"]
    current_question_id = flow["start"]

    st.subheader(flow["subtitle"])

    while current_question_id:
        question = questions[current_question_id]

        answer = st.radio(
            question["text"],
            question["options"],
            index=None,
            key=f"{flow_name}_{current_question_id}",
        )

        if answer is None:
            st.info("Select an option to continue.")
            st.stop()

        answer_config = question["answers"][answer]

        if "next" in answer_config:
            current_question_id = answer_config["next"]
            continue

        show_recommendations(
            answer_config["result"],
            answer_config.get("type", "info"),
            answer_config.get("actions", []),
        )
        break


def run_auto_guided_flow(issue):
    """Create a simple guided flow automatically from knowledge base issue data."""
    st.subheader(f"🧭 {issue['title']} Guided Flow")

    st.info("Review the symptoms first, then answer the question below.")

    st.write("**Category:**", issue["category"])
    show_severity(issue["severity"])
    if "show_issue_metadata" in globals():
        show_issue_metadata(issue)

    with st.expander("👁 View Symptoms", expanded=True):
        symptoms = issue.get("symptoms", [])
        if symptoms:
            for symptom in symptoms:
                st.write("-", symptom)
        else:
            st.write("No symptoms listed for this issue.")

    has_symptoms = st.radio(
        "Is the user experiencing one or more of these symptoms?",
        ["Yes", "No"],
        index=None,
        key=f"auto_{issue['title']}_symptoms",
    )

    if has_symptoms is None:
        st.info("Select Yes or No to continue.")
        st.stop()

    if has_symptoms == "No":
        show_recommendations(
            "👉 The selected issue may not fully match your problem.",
            "info",
            [
                "Do not worry if you are unsure about the exact symptoms",
                "Return to the issue list and choose a closer match",
                "Create a support ticket and describe what happened in your own words if you are not sure",
                "Include when it started, what you were trying to do, and any error message you saw",
            ],
        )
        return

    confirmed_scope = st.radio(
        "Does this issue category and severity look correct?",
        ["Yes", "No / Not sure"],
        index=None,
        key=f"auto_{issue['title']}_scope",
    )

    if confirmed_scope is None:
        st.info("Select Yes or No / Not sure to continue.")
        st.stop()

    if confirmed_scope == "No / Not sure":
        show_recommendations(
            "👉 Gather more information before applying a fix.",
            "warning",
            [
                "Confirm when the issue started",
                "Check whether one user or multiple users are affected",
                "Review recent changes, updates, or outages",
                "Create a support ticket if you are unsure how to proceed",
            ],
        )
        return

    if st.session_state.get("role") == "Admin":
        show_recommendations(
            f"👉 Advanced troubleshooting for {issue['title']}",
            "warning" if issue["severity"] in ["Medium", "High"] else "info",
            get_it_steps(issue),
        )

        with st.expander("User-Friendly Steps"):
            for number, step in enumerate(get_user_friendly_steps(issue), 1):
                st.write(f"{number}. {step}")
    else:
        show_recommendations(
            f"👉 Recommended troubleshooting for {issue['title']}",
            "warning" if issue["severity"] in ["Medium", "High"] else "info",
            get_user_friendly_steps(issue),
        )

    with st.expander("Possible causes"):
        causes = issue.get("causes", [])
        if causes:
            for cause in causes:
                st.write("-", cause)
        else:
            st.write("No possible causes listed for this issue.")


def show_guided_troubleshooting():
    st.title("🧭 Guided Troubleshooting Assistant")

    issue_titles = [issue["title"] for issue in issues]

    selected_issue = st.selectbox(
        "Select an issue",
        ["Other"] + issue_titles,
        help="Choose the issue that best matches your problem.",
    )

    if selected_issue == "Other":
        st.info("Select a known issue from the list, or create a support ticket if your issue is not listed.")
        return

    if selected_issue in guided_flows:
        run_guided_flow(selected_issue)
    else:
        issue = find_issue_by_title(selected_issue)
        if issue:
            run_auto_guided_flow(issue)
        else:
            st.error("Issue not found in the Knowledge Base.")


# -----------------------------
# KNOWLEDGE BASE STORAGE
# -----------------------------
DEFAULT_ISSUE_TITLES = {
    "No Internet Connection",
    "DNS Resolution Failure",
    "Slow Internet",
    "VPN Connection Failure",
    "Email Not Sending",
    "Email Not Receiving",
    "Computer Running Slow",
    "Application Crashing",
    "Printer Not Working",
    "Disk Space Full",
    "High CPU Usage",
    "Login Failure",
    "Wi-Fi Drops Frequently",
    "Software Installation Failure",
    "Some Websites Not Loading",
}


def serialize_list(items):
    """Convert a list to JSON text for database storage."""
    return json.dumps(items or [])


def deserialize_list(value):
    """Convert JSON text from database back to a list."""
    if not value:
        return []
    try:
        data = json.loads(value)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def save_issue_to_db(issue):
    """Insert or update one issue in SQLite."""
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO issues (
            title, category, severity, tags, symptoms, causes,
            user_steps, it_steps, steps,
            difficulty, estimated_time, applies_to, escalation_required, last_updated
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(title) DO UPDATE SET
            category = excluded.category,
            severity = excluded.severity,
            tags = excluded.tags,
            symptoms = excluded.symptoms,
            causes = excluded.causes,
            user_steps = excluded.user_steps,
            it_steps = excluded.it_steps,
            steps = excluded.steps,
            difficulty = excluded.difficulty,
            estimated_time = excluded.estimated_time,
            applies_to = excluded.applies_to,
            escalation_required = excluded.escalation_required,
            last_updated = excluded.last_updated
        """,
        (
            issue.get("title", ""),
            issue.get("category", "Uncategorized"),
            issue.get("severity", "Medium"),
            serialize_list(issue.get("tags", [])),
            serialize_list(issue.get("symptoms", [])),
            serialize_list(issue.get("causes", [])),
            serialize_list(issue.get("user_steps", [])),
            serialize_list(issue.get("it_steps", [])),
            serialize_list(issue.get("steps", [])),
            issue.get("difficulty", "Beginner"),
            issue.get("estimated_time", "5 minutes"),
            serialize_list(issue.get("applies_to", [])),
            1 if issue.get("escalation_required") else 0,
            issue.get("last_updated", ""),
        ),
    )

    connection.commit()
    connection.close()


def delete_issue_from_db(title):
    """Delete one issue from SQLite."""
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM issues WHERE title = ?", (title,))
    connection.commit()
    connection.close()


def load_issues_from_db():
    """Load all Knowledge Base issues from SQLite."""
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM issues ORDER BY category, title")
    rows = cursor.fetchall()
    connection.close()

    return [
        {
            "title": row["title"],
            "category": row["category"],
            "severity": row["severity"],
            "tags": deserialize_list(row["tags"]),
            "symptoms": deserialize_list(row["symptoms"]),
            "causes": deserialize_list(row["causes"]),
            "user_steps": deserialize_list(row["user_steps"]),
            "it_steps": deserialize_list(row["it_steps"]),
            "steps": deserialize_list(row["steps"]),
            "difficulty": row["difficulty"] if "difficulty" in row.keys() and row["difficulty"] else "Beginner",
            "estimated_time": row["estimated_time"] if "estimated_time" in row.keys() and row["estimated_time"] else "5 minutes",
            "applies_to": deserialize_list(row["applies_to"]) if "applies_to" in row.keys() else [],
            "escalation_required": bool(row["escalation_required"]) if "escalation_required" in row.keys() else False,
            "last_updated": row["last_updated"] if "last_updated" in row.keys() else "",
        }
        for row in rows
    ]


def seed_issues_if_empty():
    """Seed SQLite with current in-code issues if the issue table is empty."""
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) AS count FROM issues")
    count = cursor.fetchone()["count"]
    connection.close()

    if count == 0:
        for issue in issues:
            save_issue_to_db(issue)


def load_issues():
    """Load Knowledge Base issues from SQLite into the app."""
    seed_issues_if_empty()
    db_issues = load_issues_from_db()

    if db_issues:
        issues.clear()
        issues.extend(db_issues)


def save_issues():
    """Save the full Knowledge Base to SQLite."""
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM issues")
    connection.commit()
    connection.close()

    for issue in issues:
        save_issue_to_db(issue)


# -----------------------------
# KNOWLEDGE BASE MODE
# -----------------------------
def show_knowledge_base():
    st.title("🔧 IT Troubleshooting Knowledge Base")

    st.subheader("🔥 Common Issues")
    common_titles = [
        "No Internet Connection",
        "Login Failure",
        "Wi-Fi Drops Frequently",
        "Email Not Sending",
        "DNS Resolution Failure",
    ]

    common_issues = [issue for issue in issues if issue["title"] in common_titles]

    if common_issues:
        common_cols = st.columns(min(3, len(common_issues)))
        for index, issue in enumerate(common_issues):
            with common_cols[index % len(common_cols)]:
                with st.container(border=True):
                    st.write(f"**{issue['title']}**")
                    st.caption(issue["category"])
                    show_severity(issue["severity"])
                    if st.button("View Details", key=f"common_{issue['title']}"):
                        st.session_state["kb_search_focus"] = issue["title"]
                        st.rerun()
    else:
        st.info("No common issues available yet.")

    st.divider()

    search_query = st.text_input(
        "🔍 Search issues",
        value=st.session_state.pop("kb_search_focus", ""),
        placeholder="Search by title, tag, symptom, cause, or step...",
    )

    selected_category = st.selectbox("Filter by Category", get_categories())
    selected_severity = st.selectbox("Filter by Severity", ["All", "Low", "Medium", "High"])

    matching_issues = []

    for issue in issues:
        if issue_matches_filters(issue, selected_category, selected_severity, search_query):
            search_score = calculate_search_score(issue, search_query)
            matching_issues.append((issue, search_score))

    matching_issues.sort(key=lambda item: item[1], reverse=True)

    st.write(f"**Results found:** {len(matching_issues)}")

    if search_query:
        st.caption("Results are sorted by relevance: title matches rank highest, then tags, category, symptoms, causes, and steps.")

    if not matching_issues:
        st.warning("No matching issues found. Try another keyword or filter.")
        return

    grouped_issues = {}
    for issue, search_score in matching_issues:
        category = issue.get("category", "Uncategorized")
        if category not in grouped_issues:
            grouped_issues[category] = []
        grouped_issues[category].append((issue, search_score))

    for category in sorted(grouped_issues.keys()):
        category_issues = grouped_issues[category]

        with st.expander(f"📂 {category} ({len(category_issues)} issues)", expanded=bool(search_query)):
            for issue, search_score in category_issues:
                issue_title = issue["title"]
                if search_query:
                    issue_title = f"{issue_title} — Match score: {search_score}"

                with st.expander(f"🧩 {issue_title}"):
                    st.write("**Category:**", issue["category"])
                    show_severity(issue["severity"])
                    show_issue_metadata(issue)
                    st.write("**Tags:**", ", ".join(issue.get("tags", [])))

                    st.write("**Symptoms:**")
                    for symptom in issue.get("symptoms", []):
                        st.write("-", symptom)

                    st.write("**Possible Causes:**")
                    for cause in issue.get("causes", []):
                        st.write("-", cause)

                    show_role_based_steps(issue)


# -----------------------------
# ADMIN KNOWLEDGE BASE EDITOR
# -----------------------------
def clear_add_issue_form():
    """Clear Admin Knowledge Base form fields after successful submission."""
    form_keys = [
        "kb_title",
        "kb_category",
        "kb_tags",
        "kb_symptoms",
        "kb_causes",
        "kb_user_steps",
        "kb_steps",
    ]

    for key in form_keys:
        st.session_state[key] = ""

    st.session_state["kb_severity"] = "Medium"


def validate_issue_form(title, category, symptoms_text, steps_text):
    """Return validation errors for the Admin Knowledge Base form."""
    errors = []

    if not title.strip():
        errors.append("Issue Title is required.")
    if not category.strip():
        errors.append("Category is required.")
    if not symptoms_text.strip():
        errors.append("At least one symptom is required.")
    if not steps_text.strip():
        errors.append("At least one advanced IT step is required.")
    if title.strip() and find_issue_by_title(title.strip()):
        errors.append("An issue with this title already exists.")

    return errors


def show_admin_kb_editor():
    require_admin()
    st.title("🛠 Admin Knowledge Base Editor")

    st.info("Add new troubleshooting issues without editing the Python code.")

    if "issue_added_message" in st.session_state:
        st.success(st.session_state.pop("issue_added_message"))

    with st.form("add_issue_form", clear_on_submit=True):
        title = st.text_input("Issue Title", key="kb_title")
        category = st.text_input("Category", placeholder="Network, DNS, Email, System...", key="kb_category")
        severity = st.selectbox("Severity", ["Low", "Medium", "High"], index=1, key="kb_severity")
        difficulty = st.selectbox("Difficulty", ["Beginner", "Intermediate", "Advanced"], key="kb_difficulty")
        estimated_time = st.text_input("Estimated Fix Time", value="5 minutes", key="kb_estimated_time")
        applies_to_text = st.text_input("Applies To", placeholder="Windows, macOS, VPN, Email, Network...", key="kb_applies_to")
        escalation_required = st.checkbox("Escalation Required", key="kb_escalation_required")
        tags_text = st.text_input("Tags", placeholder="Separate tags with commas", key="kb_tags")
        symptoms_text = st.text_area("Symptoms", placeholder="Enter one symptom per line", key="kb_symptoms")
        causes_text = st.text_area("Possible Causes", placeholder="Enter one cause per line", key="kb_causes")
        user_steps_text = st.text_area(
            "User-Friendly Steps",
            placeholder="Enter simple steps users can safely do, one per line",
            key="kb_user_steps",
        )
        steps_text = st.text_area("Advanced IT Steps", placeholder="Enter technical admin steps, one per line", key="kb_steps")

        submitted = st.form_submit_button("Add Issue")

    if submitted:
        errors = validate_issue_form(title, category, symptoms_text, steps_text)

        if errors:
            st.error("Please fix the following before adding the issue:")
            for error in errors:
                st.write(f"- {error}")
            return

        new_issue = {
            "title": title.strip(),
            "category": category.strip(),
            "severity": severity,
            "difficulty": difficulty,
            "estimated_time": estimated_time.strip() or "5 minutes",
            "applies_to": [item.strip() for item in applies_to_text.split(",") if item.strip()],
            "escalation_required": escalation_required,
            "last_updated": get_current_timestamp(),
            "tags": [tag.strip() for tag in tags_text.split(",") if tag.strip()],
            "symptoms": [line.strip() for line in symptoms_text.splitlines() if line.strip()],
            "causes": [line.strip() for line in causes_text.splitlines() if line.strip()],
            "user_steps": [line.strip() for line in user_steps_text.splitlines() if line.strip()],
            "it_steps": [line.strip() for line in steps_text.splitlines() if line.strip()],
            "steps": [line.strip() for line in steps_text.splitlines() if line.strip()],
        }

        issues.append(new_issue)

        save_issues()
        st.session_state["issue_added_message"] = f"✅ Issue added successfully: {new_issue['title']}"
        st.rerun()

    st.divider()
    st.subheader("Current Knowledge Base Issues")

    for idx, issue in enumerate(issues):
        with st.expander(issue["title"]):
            st.write("**Category:**", issue["category"])
            show_severity(issue["severity"])
            show_issue_metadata(issue)
            st.write("**Tags:**", ", ".join(issue.get("tags", [])))

            st.write("**Symptoms:**")
            for symptom in issue.get("symptoms", []):
                st.write("-", symptom)

            show_role_based_steps(issue)

            st.divider()
            st.subheader("✏️ Edit Issue")

            edit_title = st.text_input("Title", value=issue["title"], key=f"edit_title_{idx}")
            edit_category = st.text_input("Category", value=issue["category"], key=f"edit_cat_{idx}")
            edit_severity = st.selectbox(
                "Severity",
                ["Low", "Medium", "High"],
                index=["Low", "Medium", "High"].index(issue["severity"]),
                key=f"edit_sev_{idx}",
            )
            edit_difficulty = st.selectbox(
                "Difficulty",
                ["Beginner", "Intermediate", "Advanced"],
                index=["Beginner", "Intermediate", "Advanced"].index(issue.get("difficulty", "Beginner")),
                key=f"edit_difficulty_{idx}",
            )
            edit_estimated_time = st.text_input(
                "Estimated Fix Time",
                value=issue.get("estimated_time", "5 minutes"),
                key=f"edit_estimated_time_{idx}",
            )
            edit_applies_to = st.text_input(
                "Applies To (comma separated)",
                value=", ".join(issue.get("applies_to", [])),
                key=f"edit_applies_to_{idx}",
            )
            edit_escalation_required = st.checkbox(
                "Escalation Required",
                value=bool(issue.get("escalation_required", False)),
                key=f"edit_escalation_{idx}",
            )
            edit_tags = st.text_input(
                "Tags (comma separated)",
                value=", ".join(issue.get("tags", [])),
                key=f"edit_tags_{idx}",
            )
            edit_symptoms = st.text_area(
                "Symptoms (one per line)",
                value = "\n".join(issue.get("symptoms", [])),
                key=f"edit_symptoms_{idx}",
            )
            edit_user_steps = st.text_area(
                "User-Friendly Steps (one per line)",
                value = "\n".join(get_user_friendly_steps(issue)),
                key=f"edit_user_steps_{idx}",
            )
            edit_steps = st.text_area(
                "Advanced IT Steps (one per line)",
                value = "\n".join(get_it_steps(issue)),
                key=f"edit_steps_{idx}",
            )



            col1, col2 = st.columns(2)

            with col1:
                if st.button("💾 Save Changes", key=f"save_issue_{idx}"):
                    issue["title"] = edit_title.strip()
                    issue["category"] = edit_category.strip()
                    issue["severity"] = edit_severity
                    issue["difficulty"] = edit_difficulty
                    issue["estimated_time"] = edit_estimated_time.strip() or "5 minutes"
                    issue["applies_to"] = [item.strip() for item in edit_applies_to.split(",") if item.strip()]
                    issue["escalation_required"] = edit_escalation_required
                    issue["last_updated"] = get_current_timestamp()
                    issue["tags"] = [t.strip() for t in edit_tags.split(",") if t.strip()]
                    issue["symptoms"] = [s.strip() for s in edit_symptoms.splitlines() if s.strip()]
                    issue["user_steps"] = [s.strip() for s in edit_user_steps.splitlines() if s.strip()]
                    issue["it_steps"] = [s.strip() for s in edit_steps.splitlines() if s.strip()]
                    issue["steps"] = [s.strip() for s in edit_steps.splitlines() if s.strip()]

                    save_issues()

                    st.success("✅ Issue updated")
                    st.rerun()

            with col2:
                if st.button("🗑 Delete Issue", key=f"delete_issue_{idx}"):
                    deleted_title = issue["title"]
                    issues.pop(idx)
                    delete_issue_from_db(deleted_title)

                    save_issues()

                    st.warning("🗑 Issue deleted")
                    st.rerun()






# -----------------------------
# TICKET LIFECYCLE HELPERS
# -----------------------------
ASSIGNMENT_OPTIONS = [
    "Unassigned",
    "Tier 1 Support",
    "Network Team",
    "Systems Team",
    "Security Team",
    "Help Desk Manager",
]

TICKET_STATUSES = [
    "Open",
    "Assigned",
    "In Progress",
    "Waiting on User",
    "Resolved",
    "Closed",
]


def normalize_ticket_status(status):
    """Return a valid ticket status."""
    if status in TICKET_STATUSES:
        return status
    return "Open"


def is_ticket_completed(status):
    """Return True if a ticket should no longer count against active SLA."""
    return status in ["Resolved", "Closed"]

# -----------------------------
# SLA HELPERS
# -----------------------------
def get_current_timestamp():
    """Return current timestamp as a readable string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")



def get_demo_timestamp(days_ago=0, hours_ago=0, minutes_ago=0):
    """Return a realistic historical timestamp for sample/demo tickets."""
    return (datetime.now() - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)).strftime("%Y-%m-%d %H:%M:%S")


def parse_timestamp(value):
    """Parse stored timestamp safely."""
    if not value:
        return None

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    return None


def get_sla_hours(priority):
    """Return SLA response target in hours based on priority."""
    sla_targets = {
        "Critical": 1,
        "High": 4,
        "Medium": 24,
        "Low": 72,
    }
    return sla_targets.get(priority, 24)


def get_sla_status(ticket):
    """Return SLA status label and remaining/overdue context."""
    priority = ticket.get("priority", "Medium")
    status = ticket.get("status", "Open")

    if is_ticket_completed(status):
        return "Completed", "Ticket is resolved or closed"

    created_at = parse_timestamp(ticket.get("created_at"))

    if not created_at:
        return "Unknown", "No creation timestamp available"

    sla_hours = get_sla_hours(priority)
    due_at = created_at + timedelta(hours=sla_hours)
    now = datetime.now()
    remaining = due_at - now

    if remaining.total_seconds() < 0:
        overdue_by = now - due_at
        hours = int(overdue_by.total_seconds() // 3600)
        minutes = int((overdue_by.total_seconds() % 3600) // 60)
        return "Overdue", f"Overdue by {hours}h {minutes}m"

    if remaining <= timedelta(hours=1):
        minutes = int(remaining.total_seconds() // 60)
        return "Due Soon", f"Due in {minutes}m"

    hours = int(remaining.total_seconds() // 3600)
    minutes = int((remaining.total_seconds() % 3600) // 60)
    return "On Track", f"Due in {hours}h {minutes}m"


def show_sla_badge(ticket):
    """Display SLA status using Streamlit alert styles."""
    sla_status, detail = get_sla_status(ticket)

    if sla_status == "Overdue":
        st.error(f"⏰ SLA: Overdue — {detail}")
    elif sla_status == "Due Soon":
        st.warning(f"⏳ SLA: Due Soon — {detail}")
    elif sla_status == "On Track":
        st.success(f"✅ SLA: On Track — {detail}")
    elif sla_status == "Completed":
        st.info(f"📌 SLA: Completed — {detail}")
    else:
        st.info(f"ℹ️ SLA: Unknown — {detail}")

# -----------------------------
# TICKET PRIORITY HELPERS
# -----------------------------
def calculate_ticket_priority(description, severity):
    """Calculate ticket priority from description and selected severity."""
    text = description.lower() if description else ""

    critical_keywords = [
        "multiple users",
        "all users",
        "everyone",
        "department",
        "outage",
        "server down",
        "cannot work",
        "business stopped",
        "production down",
        "file server",
        "shared drive",
        "network drive",
        "network path not found",
    ]

    high_keywords = [
        "cannot access",
        "unable to login",
        "login failed",
        "email unavailable",
        "vpn down",
        "urgent",
        "blocked",
        "not working",
    ]

    medium_keywords = [
        "slow",
        "intermittent",
        "sometimes",
        "delay",
        "keeps asking",
    ]

    if any(keyword in text for keyword in critical_keywords):
        return "Critical"

    if severity == "High" or any(keyword in text for keyword in high_keywords):
        return "High"

    if severity == "Medium" or any(keyword in text for keyword in medium_keywords):
        return "Medium"

    return "Low"


def show_priority_badge(priority):
    """Display priority using Streamlit alert styles."""
    if priority == "Critical":
        st.error("🚨 Priority: Critical")
    elif priority == "High":
        st.warning("⚠️ Priority: High")
    elif priority == "Medium":
        st.info("🔵 Priority: Medium")
    else:
        st.success("🟢 Priority: Low")


# -----------------------------
# ATTACHMENT HELPERS
# -----------------------------
def save_uploaded_attachments(uploaded_files):
    """Save uploaded ticket attachments and return attachment metadata.

    Attachments are saved in two ways:
    1. As files inside ticket_attachments/
    2. As Base64 content inside the ticket record for more reliable preview/download
    """
    saved_attachments = []

    if not uploaded_files:
        return saved_attachments

    for uploaded_file in uploaded_files:
        file_bytes = uploaded_file.getvalue()
        safe_name = uploaded_file.name.replace(" ", "_")
        unique_name = f"{uuid.uuid4().hex}_{safe_name}"
        file_path = os.path.abspath(os.path.join(UPLOAD_FOLDER, unique_name))

        with open(file_path, "wb") as file:
            file.write(file_bytes)

        saved_attachments.append({
            "original_name": uploaded_file.name,
            "saved_name": unique_name,
            "path": file_path,
            "type": uploaded_file.type,
            "size": uploaded_file.size,
            "content_base64": base64.b64encode(file_bytes).decode("utf-8"),
        })

    return saved_attachments


# -----------------------------
# TICKET STORAGE
# -----------------------------
def load_tickets():
    """Load tickets from SQLite into session state."""
    if "tickets" in st.session_state:
        return

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM tickets ORDER BY id DESC")
    rows = cursor.fetchall()
    connection.close()

    loaded_tickets = []

    for row in rows:
        row_dict = dict(row)
        ticket_data = row_dict.get("ticket_data")

        if ticket_data:
            try:
                ticket = json.loads(ticket_data)
                ticket["db_id"] = row_dict.get("id")
                ticket.setdefault("created_at", get_current_timestamp())
                ticket.setdefault("updated_at", ticket.get("created_at"))
                loaded_tickets.append(ticket)
                continue
            except json.JSONDecodeError:
                pass

        # Fallback for older database rows without ticket_data
        loaded_tickets.append({
            "db_id": row_dict.get("id"),
            "name": row_dict.get("username", ""),
            "username": row_dict.get("username", ""),
            "email": row_dict.get("email", ""),
            "issue": row_dict.get("issue", ""),
            "description": row_dict.get("description", ""),
            "severity": row_dict.get("severity", "Medium"),
            "priority": row_dict.get("priority", "Medium"),
            "status": row_dict.get("status", "Open"),
            "assigned_to": row_dict.get("assigned_to", "Unassigned"),
            "resolution_notes": row_dict.get("resolution_notes", ""),
            "likely_infrastructure": bool(row_dict.get("likely_infrastructure", 0)),
            "unread_for_admin": bool(row_dict.get("unread_for_admin", 0)),
            "unread_for_user": bool(row_dict.get("unread_for_user", 0)),
            "comments": [],
            "attachments": [],
            "suggestions": [],
            "user_guidance": [],
            "created_at": get_current_timestamp(),
            "updated_at": get_current_timestamp(),
            "assigned_at": "",
            "waiting_on_user_at": "",
            "resolved_at": "",
            "closed_at": "",
            "activity_log": [],
            "selected_resolution_template": "Select a template",
            "admin_unread_type": "new_ticket",
            "user_unread_type": "",
        })

    st.session_state["tickets"] = loaded_tickets


def save_tickets():
    """Save tickets from session state into SQLite."""
    tickets = st.session_state.get("tickets", [])

    connection = get_db_connection()
    cursor = connection.cursor()

    # Simple migration approach: session state is the source of truth for ticket objects.
    cursor.execute("DELETE FROM tickets")

    for ticket in tickets:
        ticket_data = json.dumps(ticket, indent=4)
        cursor.execute(
            """
            INSERT INTO tickets (
                username,
                email,
                issue,
                description,
                severity,
                priority,
                status,
                assigned_to,
                resolution_notes,
                likely_infrastructure,
                unread_for_admin,
                unread_for_user,
                ticket_data
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket.get("username") or ticket.get("name", ""),
                ticket.get("email", ""),
                ticket.get("issue", ""),
                ticket.get("description", ""),
                ticket.get("severity", "Medium"),
                ticket.get("priority", "Medium"),
                ticket.get("status", "Open"),
                ticket.get("assigned_to", "Unassigned"),
                ticket.get("resolution_notes", ""),
                1 if ticket.get("likely_infrastructure") else 0,
                1 if ticket.get("unread_for_admin") else 0,
                1 if ticket.get("unread_for_user") else 0,
                ticket_data,
            ),
        )

    connection.commit()
    connection.close()


# -----------------------------
# TICKET SYSTEM (STEP 5)
# -----------------------------
def suggest_issues_from_text(description, title="", max_results=3):
    """Suggest likely issues based on ticket title and description."""
    suggestions = []
    combined_text = f"{title} {description}".strip()

    for issue in issues:
        score = calculate_search_score(issue, combined_text)
        if score > 0:
            suggestions.append((issue, score))

    suggestions.sort(key=lambda item: item[1], reverse=True)
    return suggestions[:max_results]


def show_ticket_form():
    st.title("🎫 Create Support Ticket")

    current_username = st.session_state.get("username", "Unknown")
    current_user = get_user(current_username) or {}
    current_email = current_user.get("email", "")

    st.info(f"Creating ticket as: **{current_username}**")
    if current_email:
        st.caption(f"Email: {current_email}")

    with st.form("ticket_form"):
        issue_title = st.text_input("Issue Title")
        description = st.text_area("Describe the issue")
        severity = st.selectbox("Severity", ["Low", "Medium", "High"])
        uploaded_files = st.file_uploader(
            "Attach screenshots or log files (optional)",
            type=["png", "jpg", "jpeg", "txt", "log", "pdf"],
            accept_multiple_files=True,
        )

        st.info("💡 If you are not sure how to fix the issue, try Guided Troubleshooting before creating a ticket.")

        submitted = st.form_submit_button("Create Ticket")

        if submitted:
            if not issue_title or not description:
                st.error("Issue Title and Description are required")
                return

            attachments = save_uploaded_attachments(uploaded_files)
            priority = calculate_ticket_priority(description, severity)

            ticket = {
                "name": current_username,
                "username": current_username,
                "email": current_email,
                "issue": issue_title,
                "description": description,
                "severity": severity,
                "priority": priority,
                "status": "Open",
                "assigned_to": "Unassigned",
                "resolution_notes": "",
                "assigned_at": "",
                "waiting_on_user_at": "",
                "closed_at": "",
                "suggestions": [],
                "likely_infrastructure": is_likely_infrastructure_issue(description),
                "attachments": attachments,
                "comments": [],
                "unread_for_admin": True,
                "unread_for_user": False,
                "admin_unread_type": "new_ticket",
                "user_unread_type": "",
                "created_at": get_current_timestamp(),
                "updated_at": get_current_timestamp(),
                "activity_log": [],
            }
            if "tickets" not in st.session_state:
                st.session_state["tickets"] = []

            st.session_state["tickets"].append(ticket)
            save_tickets()

            st.success("✅ Ticket created successfully")

            if attachments:
                st.info(f"📎 {len(attachments)} attachment(s) saved with this ticket")

            show_priority_badge(priority)

            if is_likely_infrastructure_issue(description):
                st.warning("This looks like a possible wider IT or infrastructure issue.")




def get_priority_rank(priority):
    """Return sorting rank for ticket priority."""
    ranks = {
        "Critical": 1,
        "High": 2,
        "Medium": 3,
        "Low": 4,
    }
    return ranks.get(priority, 5)


def show_ticket_list():
    require_admin()
    st.title("📋 Submitted Tickets")

    tickets = st.session_state.get("tickets", [])

    if not tickets:
        st.info("No tickets submitted yet")
        return

    status_filter = st.selectbox(
        "Filter by status",
        ["All"] + TICKET_STATUSES,
    )

    priority_filter = st.selectbox(
        "Filter by priority",
        ["All", "Critical", "High", "Medium", "Low"],
    )

    sorted_tickets = sorted(
        tickets,
        key=lambda ticket: get_priority_rank(
            ticket.get(
                "priority",
                calculate_ticket_priority(ticket.get("description", ""), ticket.get("severity", "Medium")),
            )
        ),
    )

    for i, ticket in enumerate(sorted_tickets, 1):
        if status_filter != "All" and ticket.get("status", "Open") != status_filter:
            continue

        priority = ticket.get("priority", calculate_ticket_priority(ticket.get("description", ""), ticket.get("severity", "Medium")))
        if priority_filter != "All" and priority != priority_filter:
            continue

        status = ticket.get("status", "Open")
        assigned_to = ticket.get("assigned_to", "Unassigned")

        if priority == "Critical":
            st.error(f"🚨 CRITICAL: {ticket['issue']} — {status}")
        elif priority == "High":
            st.warning(f"⚠️ HIGH PRIORITY: {ticket['issue']} — {status}")

        sla_status, _ = get_sla_status(ticket)
        sla_label = f" — SLA: {sla_status}"
        unread_label = get_unread_label(ticket, "admin") if ticket.get("unread_for_admin") else ""
        with st.expander(f"Ticket {i}: {ticket['issue']} — {status} — {priority}{sla_label}{unread_label}"):
            st.write(f"**Name:** {ticket['name']}")
            st.write(f"**Email:** {ticket['email']}")
            st.write(f"**Severity:** {ticket['severity']}")
            show_priority_badge(priority)
            st.markdown(f"**Priority Label:** {format_priority_text(priority)}", unsafe_allow_html=True)
            show_sla_badge(ticket)
            st.write(f"**Status:** {status}")
            if ticket.get("created_at"):
                st.write(f"**Created:** {ticket.get('created_at')}")
            if ticket.get("assigned_at"):
                st.write(f"**Assigned At:** {ticket.get('assigned_at')}")
            if ticket.get("waiting_on_user_at"):
                st.write(f"**Waiting on User Since:** {ticket.get('waiting_on_user_at')}")
            if ticket.get("resolved_at"):
                st.write(f"**Resolved At:** {ticket.get('resolved_at')}")
            if ticket.get("closed_at"):
                st.write(f"**Closed At:** {ticket.get('closed_at')}")
            st.write(f"**Assigned To:** {assigned_to}")
            st.markdown("**📝 Description**")
            render_description_box(ticket.get("description", ""))

            if ticket.get("likely_infrastructure"):
                st.warning("Possible wider IT/infrastructure issue")

            attachments = ticket.get("attachments", [])
            if attachments:
                st.write("**Attachments:**")

                for attachment_index, attachment in enumerate(attachments):
                    file_path = attachment.get("path")
                    file_name = attachment.get("original_name", "attachment")
                    file_type = attachment.get("type", "")
                    file_size = attachment.get("size", 0)

                    st.write(f"📎 **{file_name}** ({file_size} bytes)")

                    resolved_path = file_path
                    saved_name = attachment.get("saved_name")
                    content_base64 = attachment.get("content_base64")
                    attachment_bytes = None

                    if content_base64:
                        try:
                            attachment_bytes = base64.b64decode(content_base64)
                        except Exception:
                            attachment_bytes = None

                    if not resolved_path or not os.path.exists(resolved_path):
                        if saved_name:
                            fallback_path = os.path.join(UPLOAD_FOLDER, saved_name)
                            if os.path.exists(fallback_path):
                                resolved_path = fallback_path

                    if attachment_bytes:
                        if file_type.startswith("image"):
                            st.image(attachment_bytes, caption=file_name, use_container_width=True)
                        else:
                            st.download_button(
                                label=f"⬇️ Download {file_name}",
                                data=attachment_bytes,
                                file_name=file_name,
                                key=f"download_db_{i}_{attachment_index}",
                            )
                    elif resolved_path and os.path.exists(resolved_path):
                        if file_type.startswith("image"):
                            st.image(resolved_path, caption=file_name, use_container_width=True)
                        else:
                            with open(resolved_path, "rb") as file:
                                st.download_button(
                                    label=f"⬇️ Download {file_name}",
                                    data=file,
                                    file_name=file_name,
                                    key=f"download_{i}_{attachment_index}",
                                )
                    else:
                        st.warning("Attachment file was not found.")
                        st.caption("The ticket has attachment metadata, but no file content or saved file was available.")

            suggestions = ticket.get("suggestions", [])
            if suggestions:
                st.write("**Suggested matching issues:**")
                for suggestion in suggestions:
                    st.write(
                        f"- {suggestion['title']} "
                        f"({suggestion['category']}, {suggestion['severity']}) "
                        f"— Score: {suggestion['score']}"
                    )

            st.divider()
            st.subheader("Update Ticket")

            current_status = normalize_ticket_status(status)
            new_status = st.selectbox(
                "Status",
                TICKET_STATUSES,
                index=TICKET_STATUSES.index(current_status),
                key=f"status_{i}",
            )

            assignment_options = ASSIGNMENT_OPTIONS.copy()
            if assigned_to not in assignment_options:
                assignment_options.append(assigned_to)

            new_assigned_to = st.selectbox(
                "Assigned To",
                assignment_options,
                index=assignment_options.index(assigned_to),
                key=f"assigned_{i}",
            )

            new_priority = st.selectbox(
                "Priority",
                ["Critical", "High", "Medium", "Low"],
                index=["Critical", "High", "Medium", "Low"].index(priority),
                key=f"priority_{i}",
            )

            template_key = f"resolution_template_{i}"
            notes_key = f"resolution_{i}"
            previous_template_key = f"previous_resolution_template_{i}"

            stored_template = ticket.get("selected_resolution_template", "Select a template")
            if stored_template not in RESOLUTION_TEMPLATES:
                stored_template = "Select a template"

            selected_template = st.selectbox(
                "Resolution Template",
                list(RESOLUTION_TEMPLATES.keys()),
                index=list(RESOLUTION_TEMPLATES.keys()).index(stored_template),
                key=template_key,
            )

            template_text = get_resolution_template_text(selected_template)
            current_resolution_notes = ticket.get("resolution_notes", "")

            if notes_key not in st.session_state:
                st.session_state[notes_key] = current_resolution_notes

            previous_template = st.session_state.get(previous_template_key, stored_template)
            if (
                selected_template != "Select a template"
                and selected_template != previous_template
                and template_text
            ):
                existing_notes = st.session_state.get(notes_key, "").strip()
                if not existing_notes:
                    st.session_state[notes_key] = template_text
                elif template_text not in existing_notes:
                    st.session_state[notes_key] = existing_notes + "" + template_text

            st.session_state[previous_template_key] = selected_template

            new_resolution_notes = st.text_area(
                "Resolution Notes",
                key=notes_key,
            )

            if st.button("Save Ticket Updates", key=f"save_ticket_{i}"):
                previous_status = ticket.get("status", "Open")
                previous_assigned_to = ticket.get("assigned_to", "Unassigned")
                previous_priority = ticket.get("priority", "Medium")
                previous_resolution_notes = ticket.get("resolution_notes", "")
                previous_template = ticket.get("selected_resolution_template", "Select a template")

                ticket["status"] = new_status
                ticket["priority"] = new_priority
                ticket["assigned_to"] = new_assigned_to
                ticket["resolution_notes"] = new_resolution_notes
                ticket["selected_resolution_template"] = selected_template
                ticket["updated_at"] = get_current_timestamp()

                if new_status == "Assigned" and not ticket.get("assigned_at"):
                    ticket["assigned_at"] = get_current_timestamp()
                if new_status == "Waiting on User" and not ticket.get("waiting_on_user_at"):
                    ticket["waiting_on_user_at"] = get_current_timestamp()
                if new_status == "Resolved" and not ticket.get("resolved_at"):
                    ticket["resolved_at"] = get_current_timestamp()
                if new_status == "Closed" and not ticket.get("closed_at"):
                    ticket["closed_at"] = get_current_timestamp()

                if previous_status != new_status:
                    add_ticket_activity(
                        ticket,
                        "status_change",
                        f"Status changed from {previous_status} to {new_status}.",
                        actor=st.session_state.get("username", "Unknown"),
                        role=st.session_state.get("role", "Admin"),
                    )
                    ticket["unread_for_user"] = True
                    ticket["user_unread_type"] = "status_change"

                if previous_assigned_to != new_assigned_to:
                    add_ticket_activity(
                        ticket,
                        "assignment",
                        f"Assignment changed from {previous_assigned_to} to {new_assigned_to}.",
                        actor=st.session_state.get("username", "Unknown"),
                        role=st.session_state.get("role", "Admin"),
                    )
                    ticket["unread_for_user"] = True
                    ticket["user_unread_type"] = "assignment"

                if previous_priority != new_priority:
                    add_ticket_activity(
                        ticket,
                        "priority",
                        f"Priority changed from {previous_priority} to {new_priority}.",
                        actor=st.session_state.get("username", "Unknown"),
                        role=st.session_state.get("role", "Admin"),
                    )
                    ticket["unread_for_user"] = True
                    ticket["user_unread_type"] = "priority"

                if previous_resolution_notes != new_resolution_notes:
                    add_ticket_activity(
                        ticket,
                        "resolution",
                        "Resolution notes updated.",
                        actor=st.session_state.get("username", "Unknown"),
                        role=st.session_state.get("role", "Admin"),
                    )
                    ticket["unread_for_user"] = True
                    ticket["user_unread_type"] = "resolution"

                if previous_template != selected_template:
                    add_ticket_activity(
                        ticket,
                        "resolution",
                        f"Resolution template changed from {previous_template} to {selected_template}.",
                        actor=st.session_state.get("username", "Unknown"),
                        role=st.session_state.get("role", "Admin"),
                    )
                    ticket["unread_for_user"] = True
                    ticket["user_unread_type"] = "resolution"
                save_tickets()
                st.success("✅ Ticket updated successfully")

            if ticket.get("resolution_notes"):
                st.write("**Saved Resolution Notes:**")
                if ticket.get("selected_resolution_template") and ticket.get("selected_resolution_template") != "Select a template":
                    st.caption(f"Template used: {ticket.get('selected_resolution_template')}")
                st.write(ticket["resolution_notes"])

            show_ticket_comments(ticket, i)




# -----------------------------
# TICKET TIMELINE HELPERS
# -----------------------------
def add_ticket_activity(ticket, event_type, message, actor=None, role=None):
    """Add an activity event to the ticket timeline."""
    ticket.setdefault("activity_log", [])
    ticket["activity_log"].append({
        "timestamp": get_current_timestamp(),
        "actor": actor or st.session_state.get("username", "System"),
        "role": role or st.session_state.get("role", "System"),
        "type": event_type,
        "message": message,
    })


def get_ticket_timeline(ticket):
    """Return ticket activity and comments as one chronological timeline."""
    timeline = []

    if ticket.get("created_at"):
        timeline.append({
            "timestamp": ticket.get("created_at"),
            "actor": ticket.get("username") or ticket.get("name", "User"),
            "role": "User",
            "type": "created",
            "message": "Ticket created by user",
        })

    for activity in ticket.get("activity_log", []):
        if activity.get("type") == "created":
            continue
        timeline.append({
            "timestamp": activity.get("timestamp", ""),
            "actor": activity.get("actor", "System"),
            "role": activity.get("role", "System"),
            "type": activity.get("type", "activity"),
            "message": activity.get("message", ""),
        })

    for comment in ticket.get("comments", []):
        timeline.append({
            "timestamp": comment.get("timestamp") or ticket.get("created_at", ""),
            "actor": comment.get("author", "Unknown"),
            "role": comment.get("role", "User"),
            "type": "comment",
            "message": comment.get("comment", ""),
        })

    def sort_key(item):
        parsed = parse_timestamp(item.get("timestamp"))
        return parsed or datetime.min

    return sorted(timeline, key=sort_key)


def show_ticket_timeline(ticket):
    """Display the ticket timeline."""
    st.subheader("🕒 Activity Timeline")

    timeline = get_ticket_timeline(ticket)

    if not timeline:
        st.info("No activity yet.")
        return

    icon_map = {
        "created": "🆕",
        "status_change": "🔄",
        "assignment": "👤",
        "priority": "🚦",
        "comment": "💬",
        "resolution": "📌",
        "activity": "📌",
    }

    for event in timeline:
        icon = icon_map.get(event.get("type"), "📌")
        timestamp = event.get("timestamp") or "No timestamp"
        actor = event.get("actor", "Unknown")
        role = event.get("role", "User")
        message = event.get("message", "")

        st.markdown(f"**{icon} {timestamp} — {actor} ({role})**")
        st.write(message)
        st.divider()



# -----------------------------
# RESOLUTION TEMPLATE HELPERS
# -----------------------------
RESOLUTION_TEMPLATES = {
    "Select a template": "",
    "Password reset completed": "Resolved by resetting the user's password and confirming successful login.",
    "Account unlocked": "Resolved by unlocking the user account and asking the user to try signing in again.",
    "DNS cache flushed": "Resolved by flushing DNS cache and confirming website access was restored.",
    "Application reinstalled": "Resolved by reinstalling the affected application and confirming it launches correctly.",
    "Printer queue cleared": "Resolved by clearing the print queue and restarting the printer spooler service.",
    "VPN access restored": "Resolved by verifying VPN access and confirming the user can connect successfully.",
    "Escalated to Network Team": "Escalated to the Network Team for further investigation.",
    "Escalated to Systems Team": "Escalated to the Systems Team for further investigation.",
    "Pending user confirmation": "Waiting for the user to confirm whether the issue is resolved.",
}


def get_resolution_template_text(template_name):
    """Return resolution text for a selected template."""
    return RESOLUTION_TEMPLATES.get(template_name, "")

# -----------------------------
# TICKET COMMENTS
# -----------------------------
def add_ticket_comment(ticket, comment_text):
    """Add a comment to a ticket timeline."""
    if not comment_text.strip():
        return False

    if "comments" not in ticket:
        ticket["comments"] = []

    author_role = st.session_state.get("role", "User")

    ticket["comments"].append({
        "author": st.session_state.get("username", "Unknown"),
        "role": author_role,
        "comment": comment_text.strip(),
        "timestamp": get_current_timestamp(),
    })

    add_ticket_activity(
        ticket,
        "comment",
        f"Comment added: {comment_text.strip()}",
        actor=st.session_state.get("username", "Unknown"),
        role=author_role,
    )

    if author_role == "Admin":
        ticket["unread_for_user"] = True
        ticket["user_unread_type"] = "comment"
    else:
        ticket["unread_for_admin"] = True
        ticket["admin_unread_type"] = "comment"

    save_tickets()
    return True


def show_ticket_comments(ticket, ticket_index):
    """Display ticket timeline and add comments."""
    role = st.session_state.get("role", "User")
    unread_key = "unread_for_admin" if role == "Admin" else "unread_for_user"

    if ticket.get(unread_key):
        audience = "admin" if role == "Admin" else "user"
        show_unread_notice(ticket, audience)
        if st.button("Mark updates as read", key=f"mark_read_{ticket_index}"):
            ticket[unread_key] = False
            if role == "Admin":
                ticket["admin_unread_type"] = ""
            else:
                ticket["user_unread_type"] = ""
            save_tickets()
            st.success("Updates marked as read")
            st.rerun()

    show_ticket_timeline(ticket)

    st.subheader("💬 Add Comment")
    new_comment = st.text_area(
        "Add a comment",
        key=f"comment_{ticket_index}",
        placeholder="Write an update, question, or troubleshooting note...",
    )

    if st.button("Add Comment", key=f"add_comment_{ticket_index}"):
        if add_ticket_comment(ticket, new_comment):
            st.success("✅ Comment added")
            st.rerun()
        else:
            st.error("Comment cannot be empty")






def reset_demo_tickets():
    """Clear all tickets and load fresh sample demo tickets."""
    st.session_state["tickets"] = []
    save_tickets()
    added_count = load_sample_tickets()
    return added_count


# -----------------------------
# EXPORT HELPERS
# -----------------------------
def flatten_ticket_for_export(ticket):
    """Convert a ticket dictionary into a flat row for CSV export."""
    comments = ticket.get("comments", [])
    attachments = ticket.get("attachments", [])
    sla_status, sla_detail = get_sla_status(ticket)

    return {
        "issue": ticket.get("issue", ""),
        "username": ticket.get("username") or ticket.get("name", ""),
        "email": ticket.get("email", ""),
        "description": ticket.get("description", ""),
        "severity": ticket.get("severity", ""),
        "priority": ticket.get("priority", ""),
        "status": ticket.get("status", ""),
        "assigned_to": ticket.get("assigned_to", ""),
        "likely_infrastructure": ticket.get("likely_infrastructure", False),
        "sla_status": sla_status,
        "sla_detail": sla_detail,
        "created_at": ticket.get("created_at", ""),
        "updated_at": ticket.get("updated_at", ""),
        "assigned_at": ticket.get("assigned_at", ""),
        "waiting_on_user_at": ticket.get("waiting_on_user_at", ""),
        "resolved_at": ticket.get("resolved_at", ""),
        "closed_at": ticket.get("closed_at", ""),
        "resolution_notes": ticket.get("resolution_notes", ""),
        "comments_count": len(comments),
        "activity_count": len(ticket.get("activity_log", [])),
        "attachments_count": len(attachments),
        "unread_for_admin": ticket.get("unread_for_admin", False),
        "unread_for_user": ticket.get("unread_for_user", False),
    }


def tickets_to_csv(tickets):
    """Convert tickets into CSV text."""
    output = io.StringIO()

    fieldnames = [
        "issue",
        "username",
        "email",
        "description",
        "severity",
        "priority",
        "status",
        "assigned_to",
        "likely_infrastructure",
        "sla_status",
        "sla_detail",
        "created_at",
        "updated_at",
        "assigned_at",
        "waiting_on_user_at",
        "resolved_at",
        "closed_at",
        "resolution_notes",
        "comments_count",
        "activity_count",
        "attachments_count",
        "unread_for_admin",
        "unread_for_user",
    ]

    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for ticket in tickets:
        writer.writerow(flatten_ticket_for_export(ticket))

    return output.getvalue()


def show_export_tools(tickets):
    """Display admin export tools."""
    st.subheader("📤 Export Tools")

    if not tickets:
        st.info("No tickets available to export.")
        return

    csv_data = tickets_to_csv(tickets)

    st.download_button(
        label="⬇️ Download Tickets CSV",
        data=csv_data,
        file_name="tickets_export.csv",
        mime="text/csv",
    )

    st.caption("CSV export includes ticket status, priority, SLA status, comments count, and attachments count.")

# -----------------------------
# SAMPLE DEMO DATA
# -----------------------------
def get_sample_tickets():
    """Return realistic sample tickets for portfolio/demo mode."""
    return [
        {
            "name": "sarah.finance",
            "username": "sarah.finance",
            "email": "sarah.finance@example.com",
            "issue": "Shared drive unavailable for Finance",
            "description": (
                "Multiple users in the Finance department cannot access the shared drive "
                "\\\\FIN-SERVER01\\Shared. They receive 'Network path not found'. "
                "Internet and email still work."
            ),
            "severity": "High",
            "priority": "Critical",
            "status": "Open",
            "assigned_to": "Systems Team",
            "resolution_notes": "",
            "suggestions": [],
            "likely_infrastructure": True,
            "attachments": [],
            "comments": [
                {
                    "author": "sarah.finance",
                    "role": "User",
                    "comment": "This started around 9:15 AM and affects everyone on our floor.",
                }
            ],
            "unread_for_admin": True,
            "unread_for_user": False,
        },
        {
            "name": "remote.user",
            "username": "remote.user",
            "email": "remote.user@example.com",
            "issue": "VPN connection failure",
            "description": "I am working remotely and the VPN keeps timing out when I try to connect.",
            "severity": "High",
            "priority": "High",
            "status": "In Progress",
            "assigned_to": "Network Team",
            "resolution_notes": "",
            "suggestions": [],
            "likely_infrastructure": False,
            "attachments": [],
            "comments": [
                {
                    "author": "admin",
                    "role": "Admin",
                    "comment": "Checking VPN service status and user account permissions.",
                }
            ],
            "unread_for_admin": False,
            "unread_for_user": True,
        },
        {
            "name": "maria.office",
            "username": "maria.office",
            "email": "maria.office@example.com",
            "issue": "Outlook not receiving email",
            "description": "Outlook has not received new emails since this morning, but webmail is working.",
            "severity": "Medium",
            "priority": "Medium",
            "status": "Open",
            "assigned_to": "Tier 1 Support",
            "resolution_notes": "",
            "suggestions": [],
            "likely_infrastructure": False,
            "attachments": [],
            "comments": [],
            "unread_for_admin": True,
            "unread_for_user": False,
        },
        {
            "name": "office.user",
            "username": "office.user",
            "email": "office.user@example.com",
            "issue": "Printer offline in break room",
            "description": "The break room printer shows offline and print jobs stay stuck in the queue.",
            "severity": "Low",
            "priority": "Low",
            "status": "Resolved",
            "assigned_to": "Tier 1 Support",
            "resolution_notes": "Restarted printer and cleared the print queue.",
            "suggestions": [],
            "likely_infrastructure": False,
            "attachments": [],
            "comments": [
                {
                    "author": "admin",
                    "role": "Admin",
                    "comment": "Printer is back online. Please try printing again.",
                }
            ],
            "unread_for_admin": False,
            "unread_for_user": True,
        },
        {
            "name": "james.sales",
            "username": "james.sales",
            "email": "james.sales@example.com",
            "issue": "Laptop running slow",
            "description": "My laptop is very slow today. Applications take a long time to open.",
            "severity": "Medium",
            "priority": "Medium",
            "status": "In Progress",
            "assigned_to": "Tier 1 Support",
            "resolution_notes": "",
            "suggestions": [],
            "likely_infrastructure": False,
            "attachments": [],
            "comments": [],
            "unread_for_admin": False,
            "unread_for_user": False,
        },
    ]


def load_sample_tickets():
    """Load sample tickets without duplicating them."""
    if "tickets" not in st.session_state:
        st.session_state["tickets"] = []

    existing_issues = {ticket.get("issue") for ticket in st.session_state["tickets"]}

    added_count = 0
    for sample_ticket in get_sample_tickets():
        if sample_ticket["issue"] not in existing_issues:
            sample_ticket.setdefault("created_at", get_demo_timestamp())
            sample_ticket.setdefault("updated_at", sample_ticket.get("created_at", get_demo_timestamp()))
            sample_ticket.setdefault("assigned_at", "")
            sample_ticket.setdefault("waiting_on_user_at", "")
            sample_ticket.setdefault("resolved_at", "")
            sample_ticket.setdefault("closed_at", "")
            sample_ticket.setdefault("activity_log", [])
            st.session_state["tickets"].append(sample_ticket)
            added_count += 1

    if added_count:
        save_tickets()

    return added_count



# -----------------------------
# DASHBOARD VIEW HELPERS
# -----------------------------
def show_dashboard_ticket_summary(ticket):
    """Display a compact ticket summary for dashboard tabs."""
    status = ticket.get("status", "Open")
    priority = ticket.get("priority", "Medium")
    sla_status, sla_detail = get_sla_status(ticket)

    unread_label = get_unread_label(ticket, "admin") if ticket.get("unread_for_admin") else ""

    with st.expander(f"{ticket.get('issue', 'Unknown issue')} — {status} — {priority} — SLA: {sla_status}{unread_label}"):
        st.write(f"**User:** {ticket.get('username') or ticket.get('name', 'Unknown')}")
        st.write(f"**Email:** {ticket.get('email', '')}")
        st.write(f"**Assigned To:** {ticket.get('assigned_to', 'Unassigned')}")
        st.write(f"**Created:** {ticket.get('created_at', 'N/A')}")
        st.write(f"**Updated:** {ticket.get('updated_at', 'N/A')}")
        st.write(f"**SLA:** {sla_status} — {sla_detail}")
        st.markdown("**📝 Description**")
        render_description_box(ticket.get("description", ""))

        if ticket.get("likely_infrastructure"):
            st.warning("🚨 Escalation recommended: possible wider IT/infrastructure issue.")


def show_dashboard_ticket_tabs(tickets):
    """Display dashboard tickets in clear tab-based sections."""
    st.subheader("📋 Ticket Views")

    all_tickets = tickets
    critical_tickets = [ticket for ticket in tickets if ticket.get("priority") == "Critical"]
    unread_tickets = [ticket for ticket in tickets if ticket.get("unread_for_admin")]
    sla_tickets = [ticket for ticket in tickets if get_sla_status(ticket)[0] == "Overdue"]

    tabs = st.tabs([
        f"📋 All Tickets ({len(all_tickets)})",
        f"🚨 Critical ({len(critical_tickets)})",
        f"🔔 Unread ({len(unread_tickets)})",
        f"⏱ SLA Issues ({len(sla_tickets)})",
    ])

    tab_data = [
        (tabs[0], all_tickets, "tickets"),
        (tabs[1], critical_tickets, "critical tickets"),
        (tabs[2], unread_tickets, "unread updates"),
        (tabs[3], sla_tickets, "SLA overdue tickets"),
    ]

    for tab, ticket_list, empty_label in tab_data:
        with tab:
            if not ticket_list:
                st.info(f"No {empty_label} found.")
            else:
                for ticket in ticket_list:
                    show_dashboard_ticket_summary(ticket)


def show_dashboard_analytics(tickets):
    """Display dashboard analytics and trends."""
    st.subheader("📊 Ticket Analytics")

    if not tickets:
        st.info("No analytics available yet.")
        return

    status_counts = {}
    priority_counts = {}
    category_counts = {}
    sla_counts = {"On Track": 0, "Due Soon": 0, "Overdue": 0, "Completed": 0, "Unknown": 0}
    created_by_day = {}

    for ticket in tickets:
        status = ticket.get("status", "Open")
        priority = ticket.get("priority", "Medium")
        issue_category = "Uncategorized"

        matching_issue = find_issue_by_title(ticket.get("issue", ""))
        if matching_issue:
            issue_category = matching_issue.get("category", "Uncategorized")

        sla_status, _ = get_sla_status(ticket)
        created_day = ticket.get("created_at", "")[:10] if ticket.get("created_at") else "Unknown"

        status_counts[status] = status_counts.get(status, 0) + 1
        priority_counts[priority] = priority_counts.get(priority, 0) + 1
        category_counts[issue_category] = category_counts.get(issue_category, 0) + 1
        sla_counts[sla_status] = sla_counts.get(sla_status, 0) + 1
        created_by_day[created_day] = created_by_day.get(created_day, 0) + 1

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("### Tickets by Status")
        st.bar_chart(status_counts)

        st.markdown("### Tickets by SLA Status")
        st.bar_chart(sla_counts)

    with col_chart2:
        st.markdown("### Tickets by Priority")
        st.bar_chart(priority_counts)

        st.markdown("### Tickets by Category")
        st.bar_chart(category_counts)

    st.markdown("### Tickets Created by Day")
    st.line_chart(dict(sorted(created_by_day.items())))

# -----------------------------
# ADMIN DASHBOARD
# -----------------------------
def show_admin_dashboard():
    require_admin()
    st.title("📊 Admin Dashboard")

    tickets = st.session_state.get("tickets", [])

    total_tickets = len(tickets)
    open_tickets = sum(1 for ticket in tickets if ticket.get("status", "Open") == "Open")
    assigned_tickets = sum(1 for ticket in tickets if ticket.get("status") == "Assigned")
    in_progress_tickets = sum(1 for ticket in tickets if ticket.get("status") == "In Progress")
    waiting_tickets = sum(1 for ticket in tickets if ticket.get("status") == "Waiting on User")
    resolved_tickets = sum(1 for ticket in tickets if ticket.get("status") == "Resolved")
    closed_tickets = sum(1 for ticket in tickets if ticket.get("status") == "Closed")
    critical_tickets = sum(1 for ticket in tickets if ticket.get("priority") == "Critical")
    unread_admin_comments = sum(1 for ticket in tickets if ticket.get("unread_for_admin"))
    overdue_tickets = sum(1 for ticket in tickets if get_sla_status(ticket)[0] == "Overdue")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Tickets", total_tickets)
    col2.metric("Open", open_tickets)
    col3.metric("Assigned", assigned_tickets)
    col4.metric("In Progress", in_progress_tickets)

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Waiting on User", waiting_tickets)
    col6.metric("Resolved", resolved_tickets)
    col7.metric("Critical", critical_tickets)
    col8.metric("SLA Overdue", overdue_tickets)

    st.caption(f"Closed tickets: {closed_tickets} | Unread comments: {unread_admin_comments}")

    st.divider()

    show_export_tools(tickets)

    st.divider()

    if not tickets:
        st.info("No ticket data available yet.")
        col_demo1, col_demo2 = st.columns(2)

        with col_demo1:
            if st.button("📦 Load sample demo tickets"):
                added_count = load_sample_tickets()
                if added_count:
                    st.success(f"✅ Loaded {added_count} sample ticket(s).")
                    st.rerun()
                else:
                    st.info("Sample tickets are already loaded.")

        with col_demo2:
            if st.button("♻️ Reset demo tickets"):
                added_count = reset_demo_tickets()
                st.success(f"✅ Demo reset complete. Loaded {added_count} sample ticket(s).")
                st.rerun()

        return

    with st.expander("🧪 Demo Data Tools"):
        st.caption("Use these tools only for portfolio demos or testing.")

        col_demo1, col_demo2 = st.columns(2)

        with col_demo1:
            if st.button("📦 Load sample demo tickets"):
                added_count = load_sample_tickets()
                if added_count:
                    st.success(f"✅ Loaded {added_count} sample ticket(s).")
                    st.rerun()
                else:
                    st.info("Sample tickets are already loaded.")

        with col_demo2:
            if st.button("♻️ Reset demo tickets"):
                added_count = reset_demo_tickets()
                st.success(f"✅ Demo reset complete. Loaded {added_count} sample ticket(s).")
                st.rerun()

        st.warning("Reset demo tickets removes all current tickets from this local demo database.")

    critical_items = [
        ticket for ticket in tickets
        if ticket.get("priority") == "Critical"
    ]

    if critical_items:
        st.error(f"🚨 {len(critical_items)} critical ticket(s) need immediate attention.")
        with st.expander("View critical tickets"):
            for ticket in critical_items:
                st.write(f"- **{ticket.get('issue', 'Unknown issue')}** — {ticket.get('status', 'Open')}")

    overdue_items = [ticket for ticket in tickets if get_sla_status(ticket)[0] == "Overdue"]
    if overdue_items:
        st.error(f"⏰ {len(overdue_items)} ticket(s) are SLA overdue.")
        with st.expander("View SLA overdue tickets"):
            for ticket in overdue_items:
                sla_status, detail = get_sla_status(ticket)
                st.write(f"- **{ticket.get('issue', 'Unknown issue')}** — {detail}")

    unread_comment_items = [ticket for ticket in tickets if ticket.get("unread_for_admin")]
    if unread_comment_items:
        st.warning(f"🔔 {len(unread_comment_items)} ticket(s) have unread comments for admin.")
        with st.expander("View tickets with unread comments"):
            for ticket in unread_comment_items:
                st.write(f"- **{ticket.get('issue', 'Unknown issue')}** — {ticket.get('status', 'Open')}")

    show_dashboard_ticket_tabs(tickets)

    st.divider()

    show_dashboard_analytics(tickets)


# -----------------------------
# USER TICKET VIEW
# -----------------------------
def show_my_tickets():
    st.title("🎟 My Tickets")

    tickets = st.session_state.get("tickets", [])
    username = st.session_state.get("username")

    user_tickets = [
        ticket for ticket in tickets
        if ticket.get("username") == username
        or ticket.get("name") == username
        or ticket.get("email") == username
    ]

    if not user_tickets:
        st.info("No tickets found for your account.")
        return

    for i, ticket in enumerate(user_tickets, 1):
        unread_label = get_unread_label(ticket, "user") if ticket.get("unread_for_user") else ""
        with st.expander(f"Ticket {i}: {ticket.get('issue')} — {ticket.get('status', 'Open')}{unread_label}"):
            st.write(f"**Severity:** {ticket.get('severity')}")
            show_priority_badge(ticket.get("priority", "Medium"))
            st.markdown(f"**Priority Label:** {format_priority_text(ticket.get('priority', 'Medium'))}", unsafe_allow_html=True)
            show_sla_badge(ticket)
            st.write(f"**Status:** {ticket.get('status', 'Open')}")
            if ticket.get("created_at"):
                st.write(f"**Created:** {ticket.get('created_at')}")
            if ticket.get("resolved_at"):
                st.write(f"**Resolved At:** {ticket.get('resolved_at')}")
            if ticket.get("closed_at"):
                st.write(f"**Closed At:** {ticket.get('closed_at')}")
            st.markdown("**📝 Description**")
            render_description_box(ticket.get("description", ""))

            if ticket.get("resolution_notes"):
                st.write("**Resolution Notes:**")
                st.write(ticket["resolution_notes"])

            show_ticket_comments(ticket, f"user_{i}")




# -----------------------------
# HOME / OVERVIEW PAGE
# -----------------------------
def show_home_page():
    st.title("🛠 IT Support Troubleshooting Portal")

    role = st.session_state.get("role", "User")

    if role == "Admin":
        st.markdown("""
### 👨‍💼 Admin Overview

Use this system to:
- Review and manage support tickets
- Assign and update ticket status
- Monitor priorities and critical issues
- Manage Knowledge Base articles
- Track support activity and trends
""")
    else:
        st.markdown("""
### 👤 User Overview

Use this system to:
- Troubleshoot common IT issues
- Search the Knowledge Base
- Create and track support tickets
- Upload screenshots or logs
- Communicate with IT support
""")

    if role == "Admin":
        st.info("💡 Start with the Dashboard to review critical tickets, unread comments, and ticket trends.")
    else:
        st.info("💡 Start with Guided Troubleshooting before creating a ticket.")



# -----------------------------
# NOTIFICATION HELPERS
# -----------------------------
def get_admin_notification_counts(tickets):
    """Return admin notification counts."""
    critical_count = sum(1 for ticket in tickets if ticket.get("priority") == "Critical")
    unread_updates = sum(1 for ticket in tickets if ticket.get("unread_for_admin"))
    overdue_count = sum(1 for ticket in tickets if get_sla_status(ticket)[0] == "Overdue")

    return {
        "critical": critical_count,
        "unread_updates": unread_updates,
        "overdue": overdue_count,
        "total": critical_count + unread_updates + overdue_count,
    }


def get_user_notification_counts(tickets, username):
    """Return notification counts for the logged-in user."""
    user_tickets = [
        ticket for ticket in tickets
        if ticket.get("username") == username
        or ticket.get("name") == username
        or ticket.get("email") == username
    ]

    unread_updates = sum(1 for ticket in user_tickets if ticket.get("unread_for_user"))

    return {
        "unread_updates": unread_updates,
        "total": unread_updates,
    }


def build_menu_label(base_label, count=0):
    """Add a notification badge to a menu label."""
    if count and count > 0:
        return f"{base_label} 🔔 {count}"
    return base_label


def normalize_menu_choice(label):
    """Remove notification badge from menu label before routing."""
    return label.split(" 🔔 ")[0]


def get_unread_label(ticket, audience):
    """Return a clear unread notification label for admin or user."""
    if audience == "admin":
        notification_type = ticket.get("admin_unread_type", "")
        if notification_type == "new_ticket":
            return " 🆕 New ticket"
        if notification_type == "comment":
            return " 💬 New user comment"
        if notification_type == "update":
            return " 🔄 Ticket update"
        return " 🔔 New update"

    notification_type = ticket.get("user_unread_type", "")
    if notification_type == "comment":
        return " 💬 New admin comment"
    if notification_type == "status_change":
        return " 🔄 Status update"
    if notification_type == "assignment":
        return " 👤 Assignment update"
    if notification_type == "priority":
        return " 🚦 Priority update"
    if notification_type == "resolution":
        return " 📌 Resolution update"
    return " 🔔 New update"


def show_unread_notice(ticket, audience):
    """Display a clear unread notice inside the ticket."""
    label = get_unread_label(ticket, audience).strip()

    if "New ticket" in label:
        st.info(label)
    elif "comment" in label.lower():
        st.warning(label)
    else:
        st.warning(label)



# -----------------------------
# ABOUT PAGE
# -----------------------------
def show_about_page():
    """Display a portfolio-friendly explanation of the project."""
    st.title("ℹ️ About This App")

    st.markdown("""
## Intelligent IT Support & Troubleshooting Portal

This application is a portfolio project designed to simulate a real-world IT helpdesk workflow.
It combines a Knowledge Base, guided troubleshooting, ticket management, attachments, comments,
notifications, SLA tracking, and an admin dashboard.

The goal is to demonstrate practical IT Support / Help Desk skills and show how common support
processes can be organized into a working web application.
""")

    st.divider()

    st.subheader("🧩 Main Features")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
### 👤 User Features
- Guided troubleshooting for common IT issues
- Searchable Knowledge Base
- Support ticket creation
- Screenshot/log attachment upload
- Ticket tracking through My Tickets
- Comment-based communication with IT
- Notifications for ticket updates
""")

    with col2:
        st.markdown("""
### 👨‍💼 Admin Features
- Ticket dashboard with analytics
- Priority and SLA tracking
- Ticket assignment and lifecycle management
- Activity timeline for audit/history
- Resolution templates
- Knowledge Base management
- CSV ticket export
""")

    st.divider()

    st.subheader("🛠 Tech Stack")

    st.markdown("""
- **Python** — backend logic
- **Streamlit** — web application interface
- **SQLite** — local database persistence for demo/testing
- **Session State** — user interaction and state handling
- **File Uploads / Base64** — attachment preview and storage support
- **Charts** — dashboard analytics and ticket trends
""")

    st.divider()

    st.subheader("✅ Skills Demonstrated")

    st.markdown("""
- IT troubleshooting methodology
- Helpdesk ticket lifecycle design
- Role-based access control
- CRUD operations
- Database-backed application design
- User/admin workflow separation
- Dashboard analytics
- SLA and priority logic
- Attachment handling
- Audit-style activity timelines
""")

    st.divider()

    st.subheader("⚠️ Demo Notice")

    st.warning(
        "This is a portfolio demo application. Do not enter real passwords, confidential company data, "
        "or sensitive support information."
    )

    st.info(
        "For demos, admins can use Dashboard → Demo Data Tools to load or reset sample tickets. "
        "This keeps the application clean and easy to review."
    )

    st.caption("Built as a practical IT Support / Help Desk portfolio project.")

# -----------------------------
# MAIN APP
# -----------------------------
def main():
    apply_global_styles()
    initialize_database()
    load_users()
    load_issues()
    load_tickets()

    if not st.session_state.get("logged_in"):
        show_login_page()
        return

    st.sidebar.write(f"Logged in as: **{st.session_state.get('username')}**")
    st.sidebar.write(f"Role: **{st.session_state.get('role')}**")

    if st.sidebar.button("Logout"):
        logout_user()
        st.rerun()

    tickets = st.session_state.get("tickets", [])

    if st.session_state.get("role") == "Admin":
        admin_notifications = get_admin_notification_counts(tickets)

        if admin_notifications["total"] > 0:
            st.sidebar.warning(
                f"🔔 {admin_notifications['total']} admin alert(s): "
                f"{admin_notifications['critical']} critical, "
                f"{admin_notifications['overdue']} overdue, "
                f"{admin_notifications['unread_updates']} unread update(s)"
            )

        menu_options = [
            "ℹ️ About This App",
            "🏠 Home",
            build_menu_label("📊 Dashboard", admin_notifications["total"]),
            "🧭 Guided Troubleshooting",
            "🔍 Knowledge Base",
            "🎫 Create Ticket",
            build_menu_label("📋 View Tickets", admin_notifications["unread_updates"]),
            "🛠 Manage Knowledge Base",
        ]
    else:
        username = st.session_state.get("username")
        user_notifications = get_user_notification_counts(tickets, username)

        if user_notifications["total"] > 0:
            st.sidebar.warning(
                f"🔔 You have {user_notifications['total']} unread ticket update(s)."
            )

        menu_options = [
            "ℹ️ About This App",
            "🏠 Home",
            "🧭 Guided Troubleshooting",
            "🔍 Knowledge Base",
            "🎫 Create Ticket",
            build_menu_label("🎟 My Tickets", user_notifications["unread_updates"]),
        ]

    selected_mode = st.sidebar.radio(
        "Select Mode",
        menu_options,
    )

    mode = normalize_menu_choice(selected_mode)

    st.sidebar.markdown(
        """
        <div class="sidebar-footer">
            <strong>Portfolio Demo</strong><br>
            Built with Python, Streamlit, and SQLite.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if mode == "ℹ️ About This App":
        show_about_page()
    elif mode == "🏠 Home":
        show_home_page()
    elif mode == "📊 Dashboard":
        show_admin_dashboard()
    elif mode == "🧭 Guided Troubleshooting":
        show_guided_troubleshooting()
    elif mode == "🔍 Knowledge Base":
        show_knowledge_base()
    elif mode == "🎫 Create Ticket":
        show_ticket_form()
    elif mode == "🎟 My Tickets":
        show_my_tickets()
    elif mode == "📋 View Tickets":
        show_ticket_list()
    elif mode == "🛠 Manage Knowledge Base":
        show_admin_kb_editor()


if __name__ == "__main__":
    main()
