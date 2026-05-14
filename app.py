import base64
import csv
import html
import io
from datetime import datetime, timedelta
import json
import os
import re
import secrets
import sqlite3
import uuid

import streamlit as st

# -----------------------------
# STORAGE CONFIG
# -----------------------------
UPLOAD_FOLDER = "ticket_attachments"
DATABASE_FILE = "it_support.db"
AUTH_SESSION_QUERY_PARAM = "auth_session"
AUTH_SESSION_TIMEOUT_HOURS = 2

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
    """Render ticket descriptions in a readable box.

    User-submitted ticket descriptions may contain characters that look like
    HTML. Escape them before rendering inside the styled card, while preserving
    line breaks for readability.
    """
    safe_text = html.escape(str(text or "No description provided.")).replace("\n", "<br>")
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
# MVP FLOW / NAVIGATION HELPERS
# -----------------------------
def normalize_mode_name(mode_name):
    """Normalize a sidebar/page name so buttons can navigate across badge labels."""
    return normalize_menu_choice(mode_name) if "normalize_menu_choice" in globals() else mode_name


def navigate_to_mode(mode_name):
    """Request navigation to a top-level sidebar mode and rerun the app."""
    st.session_state["selected_mode_request"] = mode_name
    st.rerun()


def render_mvp_flow_steps(active_step):
    """Render the MVP support flow as a compact visual stepper."""
    steps = [
        ("category", "1", "Select category"),
        ("question", "2", "Answer questions"),
        ("solution", "3", "Review solution"),
        ("ticket", "4", "Submit ticket if needed"),
    ]

    cols = st.columns(len(steps))
    for col, (step_key, number, label) in zip(cols, steps):
        is_active = step_key == active_step
        border_color = "#4e89ff" if is_active else "#d8dee9"
        background = "#eef5ff" if is_active else "#ffffff"
        col.markdown(
            f"""
            <div style="padding:0.75rem; border:1px solid {border_color}; background:{background}; border-radius:12px; text-align:center; min-height:78px;">
                <div style="font-weight:800; font-size:1.05rem;">{number}</div>
                <div style="font-size:0.9rem; color:#374151;">{label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_support_action_cards():
    """Show the three core portfolio MVP actions."""
    col_start, col_ticket, col_mine = st.columns(3)

    with col_start:
        st.markdown("""
        <div class="app-card">
            <h3>Start troubleshooting</h3>
            <p>Answer guided questions and receive a recommended fix.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Start guided troubleshooting", key="legacy_home_start_troubleshooting"):
            navigate_to_mode("🧭 Guided Troubleshooting")

    with col_ticket:
        st.markdown("""
        <div class="app-card">
            <h3>Create a ticket</h3>
            <p>Escalate unresolved issues with business impact and device details.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Create support ticket", key="legacy_home_create_ticket"):
            navigate_to_mode("🎫 Create Ticket")

    with col_mine:
        st.markdown("""
        <div class="app-card">
            <h3>Review tickets</h3>
            <p>Track submitted tickets, comments, status, and diagnostic history.</p>
        </div>
        """, unsafe_allow_html=True)
        target = "📋 View Tickets" if st.session_state.get("role") == "Admin" else "🎟 My Tickets"
        if st.button("View tickets", key="legacy_home_view_tickets"):
            navigate_to_mode(target)

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
            severity TEXT NOT NULL DEFAULT 'medium',
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


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS diagnostic_tree (
            diagnostic_tree_id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem_id INTEGER,
            diagnostic_tree_code TEXT UNIQUE NOT NULL,
            base_tree_code TEXT NOT NULL,
            audience TEXT NOT NULL CHECK (
                audience IN ('user', 'technician', 'admin')
            ),
            title TEXT NOT NULL,
            description TEXT,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (problem_id)
                REFERENCES problem(problem_id)
                ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS solution_step (
            solution_step_id INTEGER PRIMARY KEY AUTOINCREMENT,
            solution_id INTEGER NOT NULL,
            audience TEXT NOT NULL CHECK (
                audience IN ('user', 'technician', 'admin')
            ),
            step_text TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (solution_id)
                REFERENCES solution(solution_id)
                ON DELETE CASCADE
        )
    """)

    cursor.execute("PRAGMA table_info(diagnostic_node)")
    diagnostic_node_columns = [column[1] for column in cursor.fetchall()]
    if "diagnostic_tree_id" not in diagnostic_node_columns:
        cursor.execute("ALTER TABLE diagnostic_node ADD COLUMN diagnostic_tree_id INTEGER")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnostic_tree_code ON diagnostic_tree(diagnostic_tree_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnostic_tree_base_audience ON diagnostic_tree(base_tree_code, audience)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_solution_step_solution_audience ON solution_step(solution_id, audience)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnostic_node_tree_id ON diagnostic_node(diagnostic_tree_id)")

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
PROBLEM_SEED_DATA = [('NO_INTERNET_CONNECTION', 'No Internet Connection', 'Network', 'high', 'User cannot access the internet from their device.'), ('SOME_WEBSITES_NOT_LOADING', 'Some Websites Not Loading', 'Network', 'medium', 'User can access the internet, but one or more websites fail to load.'), ('WIFI_DROPS_FREQUENTLY', 'Wi-Fi Drops Frequently', 'Network', 'medium', 'User reports frequent wireless disconnections or weak signal.'), ('SLOW_INTERNET', 'Slow Internet', 'Performance', 'medium', 'User reports that internet access works but is unusually slow.'), ('APPLICATION_CRASHING', 'Application Crashing', 'Software', 'high', 'User reports that an application closes unexpectedly, freezes, or displays a crash error.'), ('SOFTWARE_INSTALLATION_FAILURE', 'Software Installation Failure', 'Software', 'medium', 'User cannot install software or the installer fails.'), ('COMPUTER_RUNNING_SLOW', 'Computer Running Slow', 'System', 'medium', 'User reports general slowness, lag, or poor computer performance.'), ('DISK_SPACE_FULL', 'Disk Space Full', 'System', 'medium', 'User reports that the device is out of storage or cannot save files or install updates.'), ('HIGH_CPU_USAGE', 'High CPU Usage', 'System', 'high', 'User reports fan noise, lag, high CPU usage, or system slowness.'), ('VPN_CONNECTION_FAILURE', 'VPN Connection Failure', 'VPN', 'high', 'User cannot connect to VPN or remote access.')]

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


# -----------------------------
# RELATIONAL KNOWLEDGE BASE SEED DATA
# -----------------------------
PROBLEM_CODE_BY_ISSUE_TITLE = {
    "No Internet Connection": "NO_INTERNET_CONNECTION",
    "Some Websites Not Loading": "SOME_WEBSITES_NOT_LOADING",
    "Wi-Fi Drops Frequently": "WIFI_DROPS_FREQUENTLY",
    "Slow Internet": "SLOW_INTERNET",
    "Application Crashing": "APPLICATION_CRASHING",
    "Software Installation Failure": "SOFTWARE_INSTALLATION_FAILURE",
    "Computer Running Slow": "COMPUTER_RUNNING_SLOW",
    "Disk Space Full": "DISK_SPACE_FULL",
    "High CPU Usage": "HIGH_CPU_USAGE",
    "VPN Connection Failure": "VPN_CONNECTION_FAILURE",
    "Printer Failure": "PRINTER_FAILURE",
    "Password Reset Request": "PASSWORD_RESET_REQUEST",
    "Account Locked": "ACCOUNT_LOCKED",
    "Multi-factor Authentication Issue": "MULTI_FACTOR_AUTHENTICATION_ISSUE",
    "Slow Computer Performance": "SLOW_COMPUTER_PERFORMANCE",
    "Application Not Opening": "APPLICATION_NOT_OPENING",
    "Application Crashing / Freezing": "APPLICATION_CRASHING_FREEZING",
    "Operating System Update Issue": "OPERATING_SYSTEM_UPDATE_ISSUE",
    "Device Running Out of Storage": "DEVICE_RUNNING_OUT_OF_STORAGE",
    "Phishing Email Reported": "PHISHING_EMAIL_REPORTED",
    "Malware or Virus Suspected": "MALWARE_OR_VIRUS_SUSPECTED",
    "Email Attachment Not Opening": "EMAIL_ATTACHMENT_NOT_OPENING",
    "Calendar Sync Issue": "CALENDAR_SYNC_ISSUE",
    "Software Installation Request": "SOFTWARE_INSTALLATION_REQUEST",
    "Browser Issue": "BROWSER_ISSUE",
    "Certificate / Security Warning": "CERTIFICATE_SECURITY_WARNING",
    "Mobile Email Setup Issue": "MOBILE_EMAIL_SETUP_ISSUE",
    "Video Conferencing Issue": "VIDEO_CONFERENCING_ISSUE",
}


# -----------------------------
# MVP CONTENT SCOPE
# -----------------------------
# The portfolio MVP should show fewer, higher-quality troubleshooting examples.
# Printer Failure is currently the reference-quality issue because it includes
# detailed symptoms, causes, user steps, technician steps, solutions, and
# user/technician diagnostic trees. Other older sample issues remain seeded in
# the database for future expansion, but they are hidden from the visible MVP
# until their content is upgraded to the same depth.
MVP_CONTENT_FOCUS_ENABLED = True
MVP_ACTIVE_PROBLEM_CODES = {"PRINTER_FAILURE", "PASSWORD_RESET_REQUEST", "ACCOUNT_LOCKED", "MULTI_FACTOR_AUTHENTICATION_ISSUE", "VPN_CONNECTION_FAILURE", "SHARED_DRIVE_NETWORK_DRIVE_ACCESS_ISSUE", "REMOTE_DESKTOP_CONNECTION_ISSUE", "SLOW_COMPUTER_PERFORMANCE", "APPLICATION_NOT_OPENING", "APPLICATION_CRASHING_FREEZING", "OPERATING_SYSTEM_UPDATE_ISSUE", "DEVICE_RUNNING_OUT_OF_STORAGE", "PHISHING_EMAIL_REPORTED", "MALWARE_OR_VIRUS_SUSPECTED", "EMAIL_ATTACHMENT_NOT_OPENING", "CALENDAR_SYNC_ISSUE", "SOFTWARE_INSTALLATION_REQUEST", "BROWSER_ISSUE", "CERTIFICATE_SECURITY_WARNING", "MOBILE_EMAIL_SETUP_ISSUE", "VIDEO_CONFERENCING_ISSUE"}
MVP_CONTENT_FOCUS_NOTE = (
    "The visible MVP currently focuses on a small set of high-quality troubleshooting examples: "
    "Printer Failure, Password Reset Request, Account Locked, Multi-factor Authentication Issue, VPN Connection Failure, Shared Drive / Network Drive Access Issue, Remote Desktop Connection Issue, Slow Computer Performance, Application Not Opening, Application Crashing / Freezing, Operating System Update Issue, Device Running Out of Storage, Phishing Email Reported, Malware or Virus Suspected, Email Attachment Not Opening, Calendar Sync Issue, Software Installation Request, Browser Issue, Certificate / Security Warning, Mobile Email Setup Issue, and Video Conferencing Issue. Other sample issues are hidden until they "
    "are expanded with detailed symptoms, causes, user steps, and technician steps."
)


def get_problem_code_for_issue(issue):
    """Return the stable problem code for an issue dictionary."""
    title = issue.get("title", "") if isinstance(issue, dict) else ""
    return (
        issue.get("problem_code")
        or PROBLEM_CODE_BY_ISSUE_TITLE.get(title)
        or make_problem_code(title)
    )


def is_visible_mvp_issue(issue):
    """Return True when an issue should appear in the visible MVP content set."""
    if not MVP_CONTENT_FOCUS_ENABLED:
        return True
    return get_problem_code_for_issue(issue) in MVP_ACTIVE_PROBLEM_CODES


def filter_visible_mvp_issues(issue_list):
    """Hide shallow sample issues from the visible MVP without deleting database rows."""
    return [issue for issue in issue_list if is_visible_mvp_issue(issue)]


def get_problem_id_by_code(cursor, problem_code):
    """Return the problem_id for a stable problem_code."""
    cursor.execute(
        "SELECT problem_id FROM problem WHERE problem_code = ?",
        (problem_code,),
    )
    row = cursor.fetchone()
    return row["problem_id"] if row else None


def get_kb_article_id_by_problem_id(cursor, problem_id):
    """Return the kb_article_id for a problem_id."""
    cursor.execute(
        "SELECT kb_article_id FROM kb_article WHERE problem_id = ?",
        (problem_id,),
    )
    row = cursor.fetchone()
    return row["kb_article_id"] if row else None


def table_has_kb_rows(cursor, table_name, kb_article_id):
    """Check whether a KB child table already has rows for an article."""
    cursor.execute(
        f"SELECT COUNT(*) AS count FROM {table_name} WHERE kb_article_id = ?",
        (kb_article_id,),
    )
    return cursor.fetchone()["count"] > 0


def seed_kb_child_rows(cursor, table_name, text_column, kb_article_id, values):
    """Seed ordered KB child rows without duplicating existing rows."""
    clean_values = [value for value in values if value]

    if not clean_values:
        return

    if table_has_kb_rows(cursor, table_name, kb_article_id):
        return

    cursor.executemany(
        f"""
        INSERT INTO {table_name} (
            kb_article_id,
            {text_column},
            sort_order
        )
        VALUES (?, ?, ?)
        """,
        [
            (kb_article_id, value, index)
            for index, value in enumerate(clean_values, start=1)
        ],
    )


def seed_kb_tags(cursor, kb_article_id, tags):
    """Seed KB tags without duplicates."""
    clean_tags = [tag for tag in tags if tag]

    if not clean_tags:
        return

    cursor.executemany(
        """
        INSERT OR IGNORE INTO kb_article_tag (
            kb_article_id,
            tag,
            sort_order
        )
        VALUES (?, ?, ?)
        """,
        [
            (kb_article_id, tag, index)
            for index, tag in enumerate(clean_tags, start=1)
        ],
    )


def seed_relational_kb_articles(cursor):
    """Seed relational KB article data from the current in-code issues list.

    This step populates:
    - kb_article
    - kb_article_tag
    - kb_article_symptom
    - kb_article_cause
    - kb_article_user_step
    - kb_article_it_step

    It only seeds the 10 problems that already exist in the new relational
    problem table. Existing rows are preserved to avoid overwriting future
    admin edits.
    """

    for issue in issues:
        problem_code = PROBLEM_CODE_BY_ISSUE_TITLE.get(issue.get("title"))
        if not problem_code:
            continue

        problem_id = get_problem_id_by_code(cursor, problem_code)
        if not problem_id:
            continue

        title = issue.get("title", "")
        category = issue.get("category", "")
        severity = issue.get("severity", "Medium")
        symptoms = issue.get("symptoms", [])
        causes = issue.get("causes", [])
        tags = issue.get("tags", [])

        summary = (
            f"{title} troubleshooting article for {category.lower()} issues."
            if category
            else f"{title} troubleshooting article."
        )

        difficulty = issue.get("difficulty", "Beginner")
        estimated_time = issue.get("estimated_time", "5 minutes")
        escalation_required = 1 if issue.get("escalation_required") or severity == "High" else 0

        cursor.execute(
            """
            INSERT OR IGNORE INTO kb_article (
                problem_id,
                title,
                summary,
                difficulty,
                estimated_time,
                escalation_required,
                escalation_notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                problem_id,
                title,
                summary,
                difficulty,
                estimated_time,
                escalation_required,
                "Escalate if multiple users are affected, the issue is business-critical, or basic troubleshooting fails.",
            ),
        )

        kb_article_id = get_kb_article_id_by_problem_id(cursor, problem_id)
        if not kb_article_id:
            continue

        user_steps = issue.get("user_steps") or get_user_friendly_steps(issue)
        it_steps = issue.get("it_steps") or issue.get("steps", [])

        seed_kb_tags(cursor, kb_article_id, tags)
        seed_kb_child_rows(cursor, "kb_article_symptom", "symptom", kb_article_id, symptoms)
        seed_kb_child_rows(cursor, "kb_article_cause", "cause", kb_article_id, causes)
        seed_kb_child_rows(cursor, "kb_article_user_step", "step_text", kb_article_id, user_steps)
        seed_kb_child_rows(cursor, "kb_article_it_step", "step_text", kb_article_id, it_steps)


# -----------------------------
# RELATIONAL DIAGNOSTIC TREE SEED DATA
# -----------------------------
DIAGNOSTIC_NODE_SEED_SQL = "-- =========================================================\n-- 1. NO INTERNET CONNECTION\n-- =========================================================\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, description, sort_order\n)\nVALUES (\n    'NO_INTERNET_CONNECTION', 'ROOT_NO_INTERNET_CONNECTION', NULL, 'category',\n    'No Internet Connection',\n    'User cannot access the internet from their device.',\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, prompt_text, sort_order\n)\nVALUES (\n    'NO_INTERNET_CONNECTION', 'Q_CONNECTED_TO_NETWORK',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'NO_INTERNET_CONNECTION' AND node_key = 'ROOT_NO_INTERNET_CONNECTION'),\n    'question',\n    'Check Network Connection',\n    'Is the device connected to Wi-Fi or Ethernet?',\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'NO_INTERNET_CONNECTION', 'S_RECONNECT_NETWORK',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'NO_INTERNET_CONNECTION' AND node_key = 'Q_CONNECTED_TO_NETWORK'),\n    'solution',\n    'Reconnect to the Network',\n    'Is the device connected to Wi-Fi or Ethernet?',\n    'No',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_RECONNECT_NETWORK'),\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, prompt_text, condition_label, condition_value, sort_order\n)\nVALUES (\n    'NO_INTERNET_CONNECTION', 'Q_MULTIPLE_USERS_AFFECTED',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'NO_INTERNET_CONNECTION' AND node_key = 'Q_CONNECTED_TO_NETWORK'),\n    'question',\n    'Check Scope',\n    'Are multiple users affected?',\n    'Is the device connected to Wi-Fi or Ethernet?',\n    'Yes',\n    2\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'NO_INTERNET_CONNECTION', 'S_ESCALATE_NETWORK_OUTAGE',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'NO_INTERNET_CONNECTION' AND node_key = 'Q_MULTIPLE_USERS_AFFECTED'),\n    'solution',\n    'Escalate Possible Network Outage',\n    'Are multiple users affected?',\n    'Yes',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_ESCALATE_NETWORK_OUTAGE'),\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'NO_INTERNET_CONNECTION', 'S_RESTART_NETWORK_EQUIPMENT',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'NO_INTERNET_CONNECTION' AND node_key = 'Q_MULTIPLE_USERS_AFFECTED'),\n    'solution',\n    'Restart Device and Network Equipment',\n    'Are multiple users affected?',\n    'No',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_RESTART_NETWORK_EQUIPMENT'),\n    2\n);\n\n-- =========================================================\n-- 2. SOME WEBSITES NOT LOADING\n-- =========================================================\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, description, sort_order\n)\nVALUES (\n    'SOME_WEBSITES_NOT_LOADING', 'ROOT_SOME_WEBSITES_NOT_LOADING', NULL, 'category',\n    'Some Websites Not Loading',\n    'User can access the internet, but one or more websites fail to load.',\n    2\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, prompt_text, sort_order\n)\nVALUES (\n    'SOME_WEBSITES_NOT_LOADING', 'Q_ONLY_ONE_SITE',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'SOME_WEBSITES_NOT_LOADING' AND node_key = 'ROOT_SOME_WEBSITES_NOT_LOADING'),\n    'question',\n    'Check Website Scope',\n    'Is only one website affected?',\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, prompt_text, condition_label, condition_value, sort_order\n)\nVALUES (\n    'SOME_WEBSITES_NOT_LOADING', 'Q_SECURITY_BLOCK_MESSAGE',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'SOME_WEBSITES_NOT_LOADING' AND node_key = 'Q_ONLY_ONE_SITE'),\n    'question',\n    'Check for Block Message',\n    'Does the user see a security, firewall, or blocked-site message?',\n    'Is only one website affected?',\n    'Yes',\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'SOME_WEBSITES_NOT_LOADING', 'S_ESCALATE_BLOCKED_WEBSITE',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'SOME_WEBSITES_NOT_LOADING' AND node_key = 'Q_SECURITY_BLOCK_MESSAGE'),\n    'solution',\n    'Escalate Possible Blocked Website',\n    'Does the user see a security, firewall, or blocked-site message?',\n    'Yes',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_ESCALATE_BLOCKED_WEBSITE'),\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'SOME_WEBSITES_NOT_LOADING', 'S_CHECK_DNS_BROWSER',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'SOME_WEBSITES_NOT_LOADING' AND node_key = 'Q_SECURITY_BLOCK_MESSAGE'),\n    'solution',\n    'Clear Browser Cache and Check DNS',\n    'Does the user see a security, firewall, or blocked-site message?',\n    'No',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_CHECK_DNS_BROWSER'),\n    2\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'SOME_WEBSITES_NOT_LOADING', 'S_CHECK_DNS_BROWSER_MULTIPLE',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'SOME_WEBSITES_NOT_LOADING' AND node_key = 'Q_ONLY_ONE_SITE'),\n    'solution',\n    'Clear Browser Cache and Check DNS',\n    'Is only one website affected?',\n    'No',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_CHECK_DNS_BROWSER'),\n    2\n);\n\n-- =========================================================\n-- 3. WI-FI DROPS FREQUENTLY\n-- =========================================================\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, description, sort_order\n)\nVALUES (\n    'WIFI_DROPS_FREQUENTLY', 'ROOT_WIFI_DROPS_FREQUENTLY', NULL, 'category',\n    'Wi-Fi Drops Frequently',\n    'User reports frequent wireless disconnections.',\n    3\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, prompt_text, sort_order\n)\nVALUES (\n    'WIFI_DROPS_FREQUENTLY', 'Q_WEAK_SIGNAL',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'WIFI_DROPS_FREQUENTLY' AND node_key = 'ROOT_WIFI_DROPS_FREQUENTLY'),\n    'question',\n    'Check Signal Strength',\n    'Is the Wi-Fi signal weak or does the issue happen far from the access point?',\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'WIFI_DROPS_FREQUENTLY', 'S_MOVE_CLOSER_TO_AP',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'WIFI_DROPS_FREQUENTLY' AND node_key = 'Q_WEAK_SIGNAL'),\n    'solution',\n    'Improve Wi-Fi Signal Strength',\n    'Is the Wi-Fi signal weak or does the issue happen far from the access point?',\n    'Yes',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_MOVE_CLOSER_TO_AP'),\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, prompt_text, condition_label, condition_value, sort_order\n)\nVALUES (\n    'WIFI_DROPS_FREQUENTLY', 'Q_MULTIPLE_WIFI_USERS',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'WIFI_DROPS_FREQUENTLY' AND node_key = 'Q_WEAK_SIGNAL'),\n    'question',\n    'Check Whether Others Are Affected',\n    'Are other users in the same area experiencing Wi-Fi drops?',\n    'Is the Wi-Fi signal weak or does the issue happen far from the access point?',\n    'No',\n    2\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'WIFI_DROPS_FREQUENTLY', 'S_ESCALATE_WIFI_INFRASTRUCTURE',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'WIFI_DROPS_FREQUENTLY' AND node_key = 'Q_MULTIPLE_WIFI_USERS'),\n    'solution',\n    'Escalate Wi-Fi Infrastructure Issue',\n    'Are other users in the same area experiencing Wi-Fi drops?',\n    'Yes',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_ESCALATE_WIFI_INFRASTRUCTURE'),\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'WIFI_DROPS_FREQUENTLY', 'S_FORGET_REJOIN_WIFI',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'WIFI_DROPS_FREQUENTLY' AND node_key = 'Q_MULTIPLE_WIFI_USERS'),\n    'solution',\n    'Forget and Rejoin Wi-Fi Network',\n    'Are other users in the same area experiencing Wi-Fi drops?',\n    'No',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_FORGET_REJOIN_WIFI'),\n    2\n);\n\n-- =========================================================\n-- 4. SLOW INTERNET\n-- =========================================================\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, description, sort_order\n)\nVALUES (\n    'SLOW_INTERNET', 'ROOT_SLOW_INTERNET', NULL, 'category',\n    'Slow Internet',\n    'User reports that internet access works but is unusually slow.',\n    4\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, prompt_text, sort_order\n)\nVALUES (\n    'SLOW_INTERNET', 'Q_BANDWIDTH_APPS',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'SLOW_INTERNET' AND node_key = 'ROOT_SLOW_INTERNET'),\n    'question',\n    'Check Bandwidth Usage',\n    'Are large downloads, streaming, video calls, or cloud sync running?',\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'SLOW_INTERNET', 'S_CLOSE_BANDWIDTH_APPS',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'SLOW_INTERNET' AND node_key = 'Q_BANDWIDTH_APPS'),\n    'solution',\n    'Close Bandwidth-Heavy Applications',\n    'Are large downloads, streaming, video calls, or cloud sync running?',\n    'Yes',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_CLOSE_BANDWIDTH_APPS'),\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, prompt_text, condition_label, condition_value, sort_order\n)\nVALUES (\n    'SLOW_INTERNET', 'Q_MULTIPLE_USERS_SLOW',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'SLOW_INTERNET' AND node_key = 'Q_BANDWIDTH_APPS'),\n    'question',\n    'Check Scope of Slowdown',\n    'Are multiple users experiencing slow internet?',\n    'Are large downloads, streaming, video calls, or cloud sync running?',\n    'No',\n    2\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'SLOW_INTERNET', 'S_ESCALATE_NETWORK_OUTAGE',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'SLOW_INTERNET' AND node_key = 'Q_MULTIPLE_USERS_SLOW'),\n    'solution',\n    'Escalate Possible Network Outage',\n    'Are multiple users experiencing slow internet?',\n    'Yes',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_ESCALATE_NETWORK_OUTAGE'),\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'SLOW_INTERNET', 'S_RUN_SPEED_TEST_ESCALATE',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'SLOW_INTERNET' AND node_key = 'Q_MULTIPLE_USERS_SLOW'),\n    'solution',\n    'Document Speed Test and Escalate',\n    'Are multiple users experiencing slow internet?',\n    'No',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_RUN_SPEED_TEST_ESCALATE'),\n    2\n);\n\n-- =========================================================\n-- 5. APPLICATION CRASHING\n-- =========================================================\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, description, sort_order\n)\nVALUES (\n    'APPLICATION_CRASHING', 'ROOT_APPLICATION_CRASHING', NULL, 'category',\n    'Application Crashing',\n    'User reports that an application closes unexpectedly, freezes, or displays a crash error.',\n    5\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, prompt_text, sort_order\n)\nVALUES (\n    'APPLICATION_CRASHING', 'Q_FIRST_CRASH',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'APPLICATION_CRASHING' AND node_key = 'ROOT_APPLICATION_CRASHING'),\n    'question',\n    'Check Whether Crash Is Temporary',\n    'Is this the first time the application has crashed?',\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'APPLICATION_CRASHING', 'S_RESTART_APPLICATION',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'APPLICATION_CRASHING' AND node_key = 'Q_FIRST_CRASH'),\n    'solution',\n    'Restart the Application',\n    'Is this the first time the application has crashed?',\n    'Yes',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_RESTART_APPLICATION'),\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, prompt_text, condition_label, condition_value, sort_order\n)\nVALUES (\n    'APPLICATION_CRASHING', 'Q_APP_UPDATED',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'APPLICATION_CRASHING' AND node_key = 'Q_FIRST_CRASH'),\n    'question',\n    'Check Application Version',\n    'Is the application up to date?',\n    'Is this the first time the application has crashed?',\n    'No',\n    2\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'APPLICATION_CRASHING', 'S_UPDATE_APPLICATION',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'APPLICATION_CRASHING' AND node_key = 'Q_APP_UPDATED'),\n    'solution',\n    'Update or Repair the Application',\n    'Is the application up to date?',\n    'No',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_UPDATE_APPLICATION'),\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'APPLICATION_CRASHING', 'S_ESCALATE_APP_CRASH',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'APPLICATION_CRASHING' AND node_key = 'Q_APP_UPDATED'),\n    'solution',\n    'Escalate Application Crash',\n    'Is the application up to date?',\n    'Yes',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_ESCALATE_APP_CRASH'),\n    2\n);\n\n-- =========================================================\n-- 6. SOFTWARE INSTALLATION FAILURE\n-- =========================================================\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, description, sort_order\n)\nVALUES (\n    'SOFTWARE_INSTALLATION_FAILURE', 'ROOT_SOFTWARE_INSTALLATION_FAILURE', NULL, 'category',\n    'Software Installation Failure',\n    'User reports that a software installation fails or cannot complete.',\n    6\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, prompt_text, sort_order\n)\nVALUES (\n    'SOFTWARE_INSTALLATION_FAILURE', 'Q_APPROVED_INSTALLER',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'SOFTWARE_INSTALLATION_FAILURE' AND node_key = 'ROOT_SOFTWARE_INSTALLATION_FAILURE'),\n    'question',\n    'Check Installer Source',\n    'Is the user installing from an approved company software source?',\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'SOFTWARE_INSTALLATION_FAILURE', 'S_USE_APPROVED_INSTALLER',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'SOFTWARE_INSTALLATION_FAILURE' AND node_key = 'Q_APPROVED_INSTALLER'),\n    'solution',\n    'Use Approved Software Installer',\n    'Is the user installing from an approved company software source?',\n    'No',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_USE_APPROVED_INSTALLER'),\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, prompt_text, condition_label, condition_value, sort_order\n)\nVALUES (\n    'SOFTWARE_INSTALLATION_FAILURE', 'Q_ENOUGH_DISK_SPACE',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'SOFTWARE_INSTALLATION_FAILURE' AND node_key = 'Q_APPROVED_INSTALLER'),\n    'question',\n    'Check Available Disk Space',\n    'Does the device have enough free disk space for the installation?',\n    'Is the user installing from an approved company software source?',\n    'Yes',\n    2\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'SOFTWARE_INSTALLATION_FAILURE', 'S_FREE_SPACE_FOR_INSTALL',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'SOFTWARE_INSTALLATION_FAILURE' AND node_key = 'Q_ENOUGH_DISK_SPACE'),\n    'solution',\n    'Free Disk Space and Retry Installation',\n    'Does the device have enough free disk space for the installation?',\n    'No',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_FREE_SPACE_FOR_INSTALL'),\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'SOFTWARE_INSTALLATION_FAILURE', 'S_ESCALATE_INSTALL_ADMIN',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'SOFTWARE_INSTALLATION_FAILURE' AND node_key = 'Q_ENOUGH_DISK_SPACE'),\n    'solution',\n    'Escalate Installation Requiring Admin Rights',\n    'Does the device have enough free disk space for the installation?',\n    'Yes',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_ESCALATE_INSTALL_ADMIN'),\n    2\n);\n\n-- =========================================================\n-- 7. COMPUTER RUNNING SLOW\n-- =========================================================\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, description, sort_order\n)\nVALUES (\n    'COMPUTER_RUNNING_SLOW', 'ROOT_COMPUTER_RUNNING_SLOW', NULL, 'category',\n    'Computer Running Slow',\n    'User reports general slowness, lag, or poor computer performance.',\n    7\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, prompt_text, sort_order\n)\nVALUES (\n    'COMPUTER_RUNNING_SLOW', 'Q_RESTARTED_RECENTLY',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'COMPUTER_RUNNING_SLOW' AND node_key = 'ROOT_COMPUTER_RUNNING_SLOW'),\n    'question',\n    'Check Recent Restart',\n    'Has the computer been restarted recently?',\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'COMPUTER_RUNNING_SLOW', 'S_RESTART_COMPUTER',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'COMPUTER_RUNNING_SLOW' AND node_key = 'Q_RESTARTED_RECENTLY'),\n    'solution',\n    'Restart the Computer',\n    'Has the computer been restarted recently?',\n    'No',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_RESTART_COMPUTER'),\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, prompt_text, condition_label, condition_value, sort_order\n)\nVALUES (\n    'COMPUTER_RUNNING_SLOW', 'Q_MANY_STARTUP_APPS',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'COMPUTER_RUNNING_SLOW' AND node_key = 'Q_RESTARTED_RECENTLY'),\n    'question',\n    'Check Startup and Open Applications',\n    'Are many applications opening at startup or running at once?',\n    'Has the computer been restarted recently?',\n    'Yes',\n    2\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'COMPUTER_RUNNING_SLOW', 'S_DISABLE_STARTUP_APPS',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'COMPUTER_RUNNING_SLOW' AND node_key = 'Q_MANY_STARTUP_APPS'),\n    'solution',\n    'Reduce Startup Applications',\n    'Are many applications opening at startup or running at once?',\n    'Yes',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_DISABLE_STARTUP_APPS'),\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'COMPUTER_RUNNING_SLOW', 'S_ESCALATE_HARDWARE_PERFORMANCE',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'COMPUTER_RUNNING_SLOW' AND node_key = 'Q_MANY_STARTUP_APPS'),\n    'solution',\n    'Escalate Possible Hardware Performance Issue',\n    'Are many applications opening at startup or running at once?',\n    'No',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_ESCALATE_HARDWARE_PERFORMANCE'),\n    2\n);\n\n-- =========================================================\n-- 8. DISK SPACE FULL\n-- =========================================================\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, description, sort_order\n)\nVALUES (\n    'DISK_SPACE_FULL', 'ROOT_DISK_SPACE_FULL', NULL, 'category',\n    'Disk Space Full',\n    'User reports that the device is out of storage or cannot save files or install updates.',\n    8\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, prompt_text, sort_order\n)\nVALUES (\n    'DISK_SPACE_FULL', 'Q_USER_FILES_LARGE',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'DISK_SPACE_FULL' AND node_key = 'ROOT_DISK_SPACE_FULL'),\n    'question',\n    'Check User Files',\n    'Are downloads, recycle bin, videos, or duplicate files using most of the space?',\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'DISK_SPACE_FULL', 'S_EMPTY_TRASH_DOWNLOADS',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'DISK_SPACE_FULL' AND node_key = 'Q_USER_FILES_LARGE'),\n    'solution',\n    'Remove Unneeded Files',\n    'Are downloads, recycle bin, videos, or duplicate files using most of the space?',\n    'Yes',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_EMPTY_TRASH_DOWNLOADS'),\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, prompt_text, condition_label, condition_value, sort_order\n)\nVALUES (\n    'DISK_SPACE_FULL', 'Q_TEMP_FILES',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'DISK_SPACE_FULL' AND node_key = 'Q_USER_FILES_LARGE'),\n    'question',\n    'Check Temporary Files',\n    'Are temporary files, cache, or update files consuming space?',\n    'Are downloads, recycle bin, videos, or duplicate files using most of the space?',\n    'No',\n    2\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'DISK_SPACE_FULL', 'S_CLEAN_TEMP_FILES',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'DISK_SPACE_FULL' AND node_key = 'Q_TEMP_FILES'),\n    'solution',\n    'Clean Temporary Files',\n    'Are temporary files, cache, or update files consuming space?',\n    'Yes',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_CLEAN_TEMP_FILES'),\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'DISK_SPACE_FULL', 'S_ESCALATE_STORAGE_EXPANSION',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'DISK_SPACE_FULL' AND node_key = 'Q_TEMP_FILES'),\n    'solution',\n    'Escalate Storage Capacity Issue',\n    'Are temporary files, cache, or update files consuming space?',\n    'No',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_ESCALATE_STORAGE_EXPANSION'),\n    2\n);\n\n-- =========================================================\n-- 9. HIGH CPU USAGE\n-- =========================================================\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, description, sort_order\n)\nVALUES (\n    'HIGH_CPU_USAGE', 'ROOT_HIGH_CPU_USAGE', NULL, 'category',\n    'High CPU Usage',\n    'User reports fan noise, heat, lag, or high processor usage.',\n    9\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, prompt_text, sort_order\n)\nVALUES (\n    'HIGH_CPU_USAGE', 'Q_ONE_APP_HIGH_CPU',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'HIGH_CPU_USAGE' AND node_key = 'ROOT_HIGH_CPU_USAGE'),\n    'question',\n    'Check for One High CPU Application',\n    'Is one known application using most of the CPU?',\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'HIGH_CPU_USAGE', 'S_CLOSE_HIGH_CPU_PROCESS',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'HIGH_CPU_USAGE' AND node_key = 'Q_ONE_APP_HIGH_CPU'),\n    'solution',\n    'Close High CPU Application',\n    'Is one known application using most of the CPU?',\n    'Yes',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_CLOSE_HIGH_CPU_PROCESS'),\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, prompt_text, condition_label, condition_value, sort_order\n)\nVALUES (\n    'HIGH_CPU_USAGE', 'Q_UNKNOWN_PROCESS',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'HIGH_CPU_USAGE' AND node_key = 'Q_ONE_APP_HIGH_CPU'),\n    'question',\n    'Check for Unknown Process',\n    'Is the high CPU caused by an unknown or suspicious process?',\n    'Is one known application using most of the CPU?',\n    'No',\n    2\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'HIGH_CPU_USAGE', 'S_ESCALATE_MALWARE_OR_ENDPOINT',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'HIGH_CPU_USAGE' AND node_key = 'Q_UNKNOWN_PROCESS'),\n    'solution',\n    'Escalate Possible Malware or Endpoint Issue',\n    'Is the high CPU caused by an unknown or suspicious process?',\n    'Yes',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_ESCALATE_MALWARE_OR_ENDPOINT'),\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'HIGH_CPU_USAGE', 'S_REBOOT_AFTER_HIGH_CPU',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'HIGH_CPU_USAGE' AND node_key = 'Q_UNKNOWN_PROCESS'),\n    'solution',\n    'Restart After High CPU Usage',\n    'Is the high CPU caused by an unknown or suspicious process?',\n    'No',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_REBOOT_AFTER_HIGH_CPU'),\n    2\n);\n\n-- =========================================================\n-- 10. VPN CONNECTION FAILURE\n-- =========================================================\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, description, sort_order\n)\nVALUES (\n    'VPN_CONNECTION_FAILURE', 'ROOT_VPN_CONNECTION_FAILURE', NULL, 'category',\n    'VPN Connection Failure',\n    'User cannot connect to the company VPN.',\n    10\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, prompt_text, sort_order\n)\nVALUES (\n    'VPN_CONNECTION_FAILURE', 'Q_VPN_LOGIN_ERROR',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'VPN_CONNECTION_FAILURE' AND node_key = 'ROOT_VPN_CONNECTION_FAILURE'),\n    'question',\n    'Check Login or MFA Error',\n    'Is the VPN failure related to username, password, or MFA?',\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'VPN_CONNECTION_FAILURE', 'S_CHECK_VPN_CREDENTIALS_MFA',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'VPN_CONNECTION_FAILURE' AND node_key = 'Q_VPN_LOGIN_ERROR'),\n    'solution',\n    'Check VPN Credentials and MFA',\n    'Is the VPN failure related to username, password, or MFA?',\n    'Yes',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_CHECK_VPN_CREDENTIALS_MFA'),\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, prompt_text, condition_label, condition_value, sort_order\n)\nVALUES (\n    'VPN_CONNECTION_FAILURE', 'Q_VPN_NETWORK_SPECIFIC',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'VPN_CONNECTION_FAILURE' AND node_key = 'Q_VPN_LOGIN_ERROR'),\n    'question',\n    'Check Network-Specific VPN Issue',\n    'Does VPN work on another trusted network or hotspot?',\n    'Is the VPN failure related to username, password, or MFA?',\n    'No',\n    2\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'VPN_CONNECTION_FAILURE', 'S_CHANGE_NETWORK_RETRY_VPN',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'VPN_CONNECTION_FAILURE' AND node_key = 'Q_VPN_NETWORK_SPECIFIC'),\n    'solution',\n    'Try Another Network for VPN',\n    'Does VPN work on another trusted network or hotspot?',\n    'Yes',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_CHANGE_NETWORK_RETRY_VPN'),\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, prompt_text, condition_label, condition_value, sort_order\n)\nVALUES (\n    'VPN_CONNECTION_FAILURE', 'Q_VPN_CLIENT_UPDATED',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'VPN_CONNECTION_FAILURE' AND node_key = 'Q_VPN_NETWORK_SPECIFIC'),\n    'question',\n    'Check VPN Client Version',\n    'Is the VPN client updated and installed correctly?',\n    'Does VPN work on another trusted network or hotspot?',\n    'No',\n    2\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'VPN_CONNECTION_FAILURE', 'S_UPDATE_VPN_CLIENT',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'VPN_CONNECTION_FAILURE' AND node_key = 'Q_VPN_CLIENT_UPDATED'),\n    'solution',\n    'Update or Reinstall VPN Client',\n    'Is the VPN client updated and installed correctly?',\n    'No',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_UPDATE_VPN_CLIENT'),\n    1\n);\n\nINSERT OR IGNORE INTO diagnostic_node (\n    diagnostic_tree_code, node_key, parent_diagnostic_node_id, node_type,\n    title, condition_label, condition_value, solution_id, sort_order\n)\nVALUES (\n    'VPN_CONNECTION_FAILURE', 'S_ESCALATE_VPN_SUPPORT',\n    (SELECT diagnostic_node_id FROM diagnostic_node WHERE diagnostic_tree_code = 'VPN_CONNECTION_FAILURE' AND node_key = 'Q_VPN_CLIENT_UPDATED'),\n    'solution',\n    'Escalate VPN Connection Failure',\n    'Is the VPN client updated and installed correctly?',\n    'Yes',\n    (SELECT solution_id FROM solution WHERE solution_code = 'FIX_ESCALATE_VPN_SUPPORT'),\n    2\n);"


def seed_diagnostic_node_data(cursor):
    """Seed diagnostic hierarchy data into diagnostic_node.

    This uses stable diagnostic_tree_code + node_key pairs and solution_code
    subqueries, so it does not depend on fragile numeric IDs.

    INSERT OR IGNORE allows the app to restart without duplicating nodes.
    """

    cursor.executescript(DIAGNOSTIC_NODE_SEED_SQL)


# -----------------------------
# RELATIONAL ROLE-SPECIFIC DIAGNOSTIC SEED DATA
# -----------------------------
TECHNICIAN_DIAGNOSTIC_TREE_SEED_DATA = {
    "NO_INTERNET_CONNECTION": {
        "title": "No Internet Connection - IT Support Specialist Diagnostic",
        "description": "IT Support Specialist diagnostic path for internet connectivity failures.",
        "sort_order": 101,
        "nodes": [
            {
                "node_key": "ROOT_NO_INTERNET_TECH",
                "parent_key": None,
                "node_type": "category",
                "title": "No Internet Connection - IT Support Specialist Diagnostic",
                "description": "Confirm whether the issue is client-side, network-side, or infrastructure-wide.",
                "prompt_text": None,
                "condition_label": None,
                "condition_value": None,
                "solution_code": None,
                "sort_order": 1,
            },
            {
                "node_key": "Q_IP_CONFIG_VALID",
                "parent_key": "ROOT_NO_INTERNET_TECH",
                "node_type": "question",
                "title": "Validate IP Configuration",
                "description": "Check the wireless or Ethernet adapter using ipconfig /all.",
                "prompt_text": "Does the client have a valid IP address, subnet mask, default gateway, and DNS server?",
                "condition_label": None,
                "condition_value": None,
                "solution_code": None,
                "sort_order": 1,
            },
            {
                "node_key": "S_RECONNECT_NETWORK_TECH",
                "parent_key": "Q_IP_CONFIG_VALID",
                "node_type": "solution",
                "title": "Reconnect or Renew Network Configuration",
                "description": None,
                "prompt_text": None,
                "condition_label": "Does the client have a valid IP address, subnet mask, default gateway, and DNS server?",
                "condition_value": "No",
                "solution_code": "FIX_RECONNECT_NETWORK",
                "sort_order": 1,
            },
            {
                "node_key": "Q_GATEWAY_REACHABLE",
                "parent_key": "Q_IP_CONFIG_VALID",
                "node_type": "question",
                "title": "Test Default Gateway",
                "description": "Ping the default gateway from the affected client.",
                "prompt_text": "Can the client ping the default gateway?",
                "condition_label": "Does the client have a valid IP address, subnet mask, default gateway, and DNS server?",
                "condition_value": "Yes",
                "solution_code": None,
                "sort_order": 2,
            },
            {
                "node_key": "S_RESTART_NETWORK_EQUIPMENT_TECH",
                "parent_key": "Q_GATEWAY_REACHABLE",
                "node_type": "solution",
                "title": "Restart Local Network Path",
                "description": None,
                "prompt_text": None,
                "condition_label": "Can the client ping the default gateway?",
                "condition_value": "No",
                "solution_code": "FIX_RESTART_NETWORK_EQUIPMENT",
                "sort_order": 1,
            },
            {
                "node_key": "Q_MULTIPLE_USERS_AFFECTED_TECH",
                "parent_key": "Q_GATEWAY_REACHABLE",
                "node_type": "question",
                "title": "Check Scope",
                "description": "Determine whether this is isolated or a wider incident.",
                "prompt_text": "Are multiple users, devices, or locations affected?",
                "condition_label": "Can the client ping the default gateway?",
                "condition_value": "Yes",
                "solution_code": None,
                "sort_order": 2,
            },
            {
                "node_key": "S_ESCALATE_NETWORK_OUTAGE_TECH",
                "parent_key": "Q_MULTIPLE_USERS_AFFECTED_TECH",
                "node_type": "solution",
                "title": "Escalate Possible Network Outage",
                "description": None,
                "prompt_text": None,
                "condition_label": "Are multiple users, devices, or locations affected?",
                "condition_value": "Yes",
                "solution_code": "FIX_ESCALATE_NETWORK_OUTAGE",
                "sort_order": 1,
            },
            {
                "node_key": "S_CHECK_DNS_BROWSER_TECH",
                "parent_key": "Q_MULTIPLE_USERS_AFFECTED_TECH",
                "node_type": "solution",
                "title": "Check DNS or Browser Layer",
                "description": None,
                "prompt_text": None,
                "condition_label": "Are multiple users, devices, or locations affected?",
                "condition_value": "No",
                "solution_code": "FIX_CHECK_DNS_BROWSER",
                "sort_order": 2,
            },
        ],
    },
    "SOME_WEBSITES_NOT_LOADING": {
        "title": "Some Websites Not Loading - IT Support Specialist Diagnostic",
        "description": "IT Support Specialist diagnostic path for partial website access issues.",
        "sort_order": 102,
        "nodes": [
            {
                "node_key": "ROOT_SOME_WEBSITES_TECH",
                "parent_key": None,
                "node_type": "category",
                "title": "Some Websites Not Loading - IT Support Specialist Diagnostic",
                "description": "Differentiate browser, DNS, filtering, and website availability issues.",
                "prompt_text": None,
                "condition_label": None,
                "condition_value": None,
                "solution_code": None,
                "sort_order": 1,
            },
            {
                "node_key": "Q_REPRO_OTHER_BROWSER",
                "parent_key": "ROOT_SOME_WEBSITES_TECH",
                "node_type": "question",
                "title": "Reproduce Across Browsers",
                "description": "Test the URL in another browser or private/incognito mode.",
                "prompt_text": "Does the website fail in multiple browsers or private mode?",
                "condition_label": None,
                "condition_value": None,
                "solution_code": None,
                "sort_order": 1,
            },
            {
                "node_key": "S_CHECK_DNS_BROWSER_CACHE_TECH",
                "parent_key": "Q_REPRO_OTHER_BROWSER",
                "node_type": "solution",
                "title": "Clear Browser Cache and Check DNS",
                "description": None,
                "prompt_text": None,
                "condition_label": "Does the website fail in multiple browsers or private mode?",
                "condition_value": "No",
                "solution_code": "FIX_CHECK_DNS_BROWSER",
                "sort_order": 1,
            },
            {
                "node_key": "Q_SECURITY_BLOCK",
                "parent_key": "Q_REPRO_OTHER_BROWSER",
                "node_type": "question",
                "title": "Check Security Filtering",
                "description": "Look for proxy, firewall, DNS filtering, or browser security warnings.",
                "prompt_text": "Is there a blocked-site, certificate, firewall, proxy, or security warning?",
                "condition_label": "Does the website fail in multiple browsers or private mode?",
                "condition_value": "Yes",
                "solution_code": None,
                "sort_order": 2,
            },
            {
                "node_key": "S_ESCALATE_BLOCKED_WEBSITE_TECH",
                "parent_key": "Q_SECURITY_BLOCK",
                "node_type": "solution",
                "title": "Escalate Possible Blocked Website",
                "description": None,
                "prompt_text": None,
                "condition_label": "Is there a blocked-site, certificate, firewall, proxy, or security warning?",
                "condition_value": "Yes",
                "solution_code": "FIX_ESCALATE_BLOCKED_WEBSITE",
                "sort_order": 1,
            },
            {
                "node_key": "S_CHECK_DNS_BROWSER_TECH",
                "parent_key": "Q_SECURITY_BLOCK",
                "node_type": "solution",
                "title": "Check DNS Resolution and Browser State",
                "description": None,
                "prompt_text": None,
                "condition_label": "Is there a blocked-site, certificate, firewall, proxy, or security warning?",
                "condition_value": "No",
                "solution_code": "FIX_CHECK_DNS_BROWSER",
                "sort_order": 2,
            },
        ],
    },
    "WIFI_DROPS_FREQUENTLY": {
        "title": "Wi-Fi Drops Frequently - IT Support Specialist Diagnostic",
        "description": "IT Support Specialist diagnostic path for unstable Wi-Fi connections.",
        "sort_order": 103,
        "nodes": [
            {
                "node_key": "ROOT_WIFI_DROPS_TECH",
                "parent_key": None,
                "node_type": "category",
                "title": "Wi-Fi Drops Frequently - IT Support Specialist Diagnostic",
                "description": "Check signal, client profile, access point, roaming, and local interference.",
                "prompt_text": None,
                "condition_label": None,
                "condition_value": None,
                "solution_code": None,
                "sort_order": 1,
            },
            {
                "node_key": "Q_RSSI_SNR_POOR",
                "parent_key": "ROOT_WIFI_DROPS_TECH",
                "node_type": "question",
                "title": "Review Signal Quality",
                "description": "Check RSSI, SNR, distance from AP, and interference if tools are available.",
                "prompt_text": "Is signal quality poor or does the issue happen far from the access point?",
                "condition_label": None,
                "condition_value": None,
                "solution_code": None,
                "sort_order": 1,
            },
            {
                "node_key": "S_MOVE_CLOSER_TO_AP_TECH",
                "parent_key": "Q_RSSI_SNR_POOR",
                "node_type": "solution",
                "title": "Improve Wi-Fi Signal Strength",
                "description": None,
                "prompt_text": None,
                "condition_label": "Is signal quality poor or does the issue happen far from the access point?",
                "condition_value": "Yes",
                "solution_code": "FIX_MOVE_CLOSER_TO_AP",
                "sort_order": 1,
            },
            {
                "node_key": "Q_AREA_USERS_AFFECTED",
                "parent_key": "Q_RSSI_SNR_POOR",
                "node_type": "question",
                "title": "Check Area Impact",
                "description": "Determine whether the issue follows the user/device or a specific office area.",
                "prompt_text": "Are other users in the same area also experiencing Wi-Fi drops?",
                "condition_label": "Is signal quality poor or does the issue happen far from the access point?",
                "condition_value": "No",
                "solution_code": None,
                "sort_order": 2,
            },
            {
                "node_key": "S_ESCALATE_WIFI_INFRA_TECH",
                "parent_key": "Q_AREA_USERS_AFFECTED",
                "node_type": "solution",
                "title": "Escalate Wi-Fi Infrastructure Issue",
                "description": None,
                "prompt_text": None,
                "condition_label": "Are other users in the same area also experiencing Wi-Fi drops?",
                "condition_value": "Yes",
                "solution_code": "FIX_ESCALATE_WIFI_INFRASTRUCTURE",
                "sort_order": 1,
            },
            {
                "node_key": "S_FORGET_REJOIN_WIFI_TECH",
                "parent_key": "Q_AREA_USERS_AFFECTED",
                "node_type": "solution",
                "title": "Forget and Rejoin Wi-Fi Network",
                "description": None,
                "prompt_text": None,
                "condition_label": "Are other users in the same area also experiencing Wi-Fi drops?",
                "condition_value": "No",
                "solution_code": "FIX_FORGET_REJOIN_WIFI",
                "sort_order": 2,
            },
        ],
    },
    "SLOW_INTERNET": {
        "title": "Slow Internet - IT Support Specialist Diagnostic",
        "description": "IT Support Specialist diagnostic path for slow internet performance.",
        "sort_order": 104,
        "nodes": [
            {
                "node_key": "ROOT_SLOW_INTERNET_TECH",
                "parent_key": None,
                "node_type": "category",
                "title": "Slow Internet - IT Support Specialist Diagnostic",
                "description": "Check endpoint load, bandwidth usage, scope, and speed-test evidence.",
                "prompt_text": None,
                "condition_label": None,
                "condition_value": None,
                "solution_code": None,
                "sort_order": 1,
            },
            {
                "node_key": "Q_LOCAL_BANDWIDTH_USAGE",
                "parent_key": "ROOT_SLOW_INTERNET_TECH",
                "node_type": "question",
                "title": "Check Local Bandwidth Usage",
                "description": "Review video calls, cloud sync, downloads, and local network usage.",
                "prompt_text": "Is the device running bandwidth-heavy applications or downloads?",
                "condition_label": None,
                "condition_value": None,
                "solution_code": None,
                "sort_order": 1,
            },
            {
                "node_key": "S_CLOSE_BANDWIDTH_APPS_TECH",
                "parent_key": "Q_LOCAL_BANDWIDTH_USAGE",
                "node_type": "solution",
                "title": "Close Bandwidth-Heavy Applications",
                "description": None,
                "prompt_text": None,
                "condition_label": "Is the device running bandwidth-heavy applications or downloads?",
                "condition_value": "Yes",
                "solution_code": "FIX_CLOSE_BANDWIDTH_APPS",
                "sort_order": 1,
            },
            {
                "node_key": "Q_MULTIPLE_USERS_SLOW_TECH",
                "parent_key": "Q_LOCAL_BANDWIDTH_USAGE",
                "node_type": "question",
                "title": "Check Scope of Slowdown",
                "description": "Ask whether multiple users, locations, or devices report slowness.",
                "prompt_text": "Are multiple users or devices experiencing slow internet?",
                "condition_label": "Is the device running bandwidth-heavy applications or downloads?",
                "condition_value": "No",
                "solution_code": None,
                "sort_order": 2,
            },
            {
                "node_key": "S_ESCALATE_NETWORK_SLOW_TECH",
                "parent_key": "Q_MULTIPLE_USERS_SLOW_TECH",
                "node_type": "solution",
                "title": "Escalate Possible Network Outage",
                "description": None,
                "prompt_text": None,
                "condition_label": "Are multiple users or devices experiencing slow internet?",
                "condition_value": "Yes",
                "solution_code": "FIX_ESCALATE_NETWORK_OUTAGE",
                "sort_order": 1,
            },
            {
                "node_key": "S_RUN_SPEED_TEST_TECH",
                "parent_key": "Q_MULTIPLE_USERS_SLOW_TECH",
                "node_type": "solution",
                "title": "Document Speed Test and Escalate",
                "description": None,
                "prompt_text": None,
                "condition_label": "Are multiple users or devices experiencing slow internet?",
                "condition_value": "No",
                "solution_code": "FIX_RUN_SPEED_TEST_ESCALATE",
                "sort_order": 2,
            },
        ],
    },
    "APPLICATION_CRASHING": {
        "title": "Application Crashing - IT Support Specialist Diagnostic",
        "description": "IT Support Specialist diagnostic path for crashing or freezing applications.",
        "sort_order": 105,
        "nodes": [
            {
                "node_key": "ROOT_APP_CRASH_TECH",
                "parent_key": None,
                "node_type": "category",
                "title": "Application Crashing - IT Support Specialist Diagnostic",
                "description": "Check whether the crash is temporary, version-related, or requires escalation.",
                "prompt_text": None,
                "condition_label": None,
                "condition_value": None,
                "solution_code": None,
                "sort_order": 1,
            },
            {
                "node_key": "Q_CRASH_REPRODUCIBLE",
                "parent_key": "ROOT_APP_CRASH_TECH",
                "node_type": "question",
                "title": "Check Reproducibility",
                "description": "Ask when the crash occurs and whether it repeats after restart.",
                "prompt_text": "Does the application crash repeatedly after restarting the app?",
                "condition_label": None,
                "condition_value": None,
                "solution_code": None,
                "sort_order": 1,
            },
            {
                "node_key": "S_RESTART_APP_TECH",
                "parent_key": "Q_CRASH_REPRODUCIBLE",
                "node_type": "solution",
                "title": "Restart the Application",
                "description": None,
                "prompt_text": None,
                "condition_label": "Does the application crash repeatedly after restarting the app?",
                "condition_value": "No",
                "solution_code": "FIX_RESTART_APPLICATION",
                "sort_order": 1,
            },
            {
                "node_key": "Q_APP_VERSION_CURRENT",
                "parent_key": "Q_CRASH_REPRODUCIBLE",
                "node_type": "question",
                "title": "Check Version and Repair Options",
                "description": "Check application version, updates, repair option, and installation source.",
                "prompt_text": "Is the application current and repaired/reinstalled from the approved source?",
                "condition_label": "Does the application crash repeatedly after restarting the app?",
                "condition_value": "Yes",
                "solution_code": None,
                "sort_order": 2,
            },
            {
                "node_key": "S_UPDATE_APP_TECH",
                "parent_key": "Q_APP_VERSION_CURRENT",
                "node_type": "solution",
                "title": "Update or Repair the Application",
                "description": None,
                "prompt_text": None,
                "condition_label": "Is the application current and repaired/reinstalled from the approved source?",
                "condition_value": "No",
                "solution_code": "FIX_UPDATE_APPLICATION",
                "sort_order": 1,
            },
            {
                "node_key": "S_ESCALATE_APP_CRASH_TECH",
                "parent_key": "Q_APP_VERSION_CURRENT",
                "node_type": "solution",
                "title": "Escalate Application Crash",
                "description": None,
                "prompt_text": None,
                "condition_label": "Is the application current and repaired/reinstalled from the approved source?",
                "condition_value": "Yes",
                "solution_code": "FIX_ESCALATE_APP_CRASH",
                "sort_order": 2,
            },
        ],
    },
    "SOFTWARE_INSTALLATION_FAILURE": {
        "title": "Software Installation Failure - IT Support Specialist Diagnostic",
        "description": "IT Support Specialist diagnostic path for failed software installations.",
        "sort_order": 106,
        "nodes": [
            {
                "node_key": "ROOT_INSTALL_FAIL_TECH",
                "parent_key": None,
                "node_type": "category",
                "title": "Software Installation Failure - IT Support Specialist Diagnostic",
                "description": "Check installer source, disk space, privileges, licensing, and endpoint controls.",
                "prompt_text": None,
                "condition_label": None,
                "condition_value": None,
                "solution_code": None,
                "sort_order": 1,
            },
            {
                "node_key": "Q_APPROVED_INSTALLER",
                "parent_key": "ROOT_INSTALL_FAIL_TECH",
                "node_type": "question",
                "title": "Validate Installer Source",
                "description": "Confirm whether the user is using an approved company installer or software portal.",
                "prompt_text": "Is the user using the approved software installer or portal?",
                "condition_label": None,
                "condition_value": None,
                "solution_code": None,
                "sort_order": 1,
            },
            {
                "node_key": "S_USE_APPROVED_INSTALLER_TECH",
                "parent_key": "Q_APPROVED_INSTALLER",
                "node_type": "solution",
                "title": "Use Approved Software Installer",
                "description": None,
                "prompt_text": None,
                "condition_label": "Is the user using the approved software installer or portal?",
                "condition_value": "No",
                "solution_code": "FIX_USE_APPROVED_INSTALLER",
                "sort_order": 1,
            },
            {
                "node_key": "Q_DISK_SPACE_FOR_INSTALL",
                "parent_key": "Q_APPROVED_INSTALLER",
                "node_type": "question",
                "title": "Check Disk Space",
                "description": "Confirm available storage before retrying installation.",
                "prompt_text": "Is there enough free disk space for the installation?",
                "condition_label": "Is the user using the approved software installer or portal?",
                "condition_value": "Yes",
                "solution_code": None,
                "sort_order": 2,
            },
            {
                "node_key": "S_FREE_SPACE_INSTALL_TECH",
                "parent_key": "Q_DISK_SPACE_FOR_INSTALL",
                "node_type": "solution",
                "title": "Free Disk Space and Retry Installation",
                "description": None,
                "prompt_text": None,
                "condition_label": "Is there enough free disk space for the installation?",
                "condition_value": "No",
                "solution_code": "FIX_FREE_SPACE_FOR_INSTALL",
                "sort_order": 1,
            },
            {
                "node_key": "S_ESCALATE_INSTALL_ADMIN_TECH",
                "parent_key": "Q_DISK_SPACE_FOR_INSTALL",
                "node_type": "solution",
                "title": "Escalate Installation Requiring Admin Rights",
                "description": None,
                "prompt_text": None,
                "condition_label": "Is there enough free disk space for the installation?",
                "condition_value": "Yes",
                "solution_code": "FIX_ESCALATE_INSTALL_ADMIN",
                "sort_order": 2,
            },
        ],
    },
    "COMPUTER_RUNNING_SLOW": {
        "title": "Computer Running Slow - IT Support Specialist Diagnostic",
        "description": "IT Support Specialist diagnostic path for endpoint performance issues.",
        "sort_order": 107,
        "nodes": [
            {
                "node_key": "ROOT_COMPUTER_SLOW_TECH",
                "parent_key": None,
                "node_type": "category",
                "title": "Computer Running Slow - IT Support Specialist Diagnostic",
                "description": "Check restart state, startup load, CPU, memory, disk, and hardware indicators.",
                "prompt_text": None,
                "condition_label": None,
                "condition_value": None,
                "solution_code": None,
                "sort_order": 1,
            },
            {
                "node_key": "Q_RESTARTED_RECENTLY",
                "parent_key": "ROOT_COMPUTER_SLOW_TECH",
                "node_type": "question",
                "title": "Check Restart State",
                "description": "Confirm uptime and pending restart/update state.",
                "prompt_text": "Has the computer been restarted recently?",
                "condition_label": None,
                "condition_value": None,
                "solution_code": None,
                "sort_order": 1,
            },
            {
                "node_key": "S_RESTART_COMPUTER_TECH",
                "parent_key": "Q_RESTARTED_RECENTLY",
                "node_type": "solution",
                "title": "Restart the Computer",
                "description": None,
                "prompt_text": None,
                "condition_label": "Has the computer been restarted recently?",
                "condition_value": "No",
                "solution_code": "FIX_RESTART_COMPUTER",
                "sort_order": 1,
            },
            {
                "node_key": "Q_STARTUP_OR_BACKGROUND_LOAD",
                "parent_key": "Q_RESTARTED_RECENTLY",
                "node_type": "question",
                "title": "Check Startup and Background Load",
                "description": "Review startup applications, memory use, and user background applications.",
                "prompt_text": "Are many startup apps or background processes using resources?",
                "condition_label": "Has the computer been restarted recently?",
                "condition_value": "Yes",
                "solution_code": None,
                "sort_order": 2,
            },
            {
                "node_key": "S_DISABLE_STARTUP_APPS_TECH",
                "parent_key": "Q_STARTUP_OR_BACKGROUND_LOAD",
                "node_type": "solution",
                "title": "Reduce Startup Applications",
                "description": None,
                "prompt_text": None,
                "condition_label": "Are many startup apps or background processes using resources?",
                "condition_value": "Yes",
                "solution_code": "FIX_DISABLE_STARTUP_APPS",
                "sort_order": 1,
            },
            {
                "node_key": "S_ESCALATE_HARDWARE_PERF_TECH",
                "parent_key": "Q_STARTUP_OR_BACKGROUND_LOAD",
                "node_type": "solution",
                "title": "Escalate Possible Hardware Performance Issue",
                "description": None,
                "prompt_text": None,
                "condition_label": "Are many startup apps or background processes using resources?",
                "condition_value": "No",
                "solution_code": "FIX_ESCALATE_HARDWARE_PERFORMANCE",
                "sort_order": 2,
            },
        ],
    },
    "DISK_SPACE_FULL": {
        "title": "Disk Space Full - IT Support Specialist Diagnostic",
        "description": "IT Support Specialist diagnostic path for storage capacity issues.",
        "sort_order": 108,
        "nodes": [
            {
                "node_key": "ROOT_DISK_FULL_TECH",
                "parent_key": None,
                "node_type": "category",
                "title": "Disk Space Full - IT Support Specialist Diagnostic",
                "description": "Check available storage, user files, temporary files, and capacity needs.",
                "prompt_text": None,
                "condition_label": None,
                "condition_value": None,
                "solution_code": None,
                "sort_order": 1,
            },
            {
                "node_key": "Q_USER_FILES_CAN_REMOVE",
                "parent_key": "ROOT_DISK_FULL_TECH",
                "node_type": "question",
                "title": "Check Removable User Files",
                "description": "Review downloads, recycle bin, duplicate files, and approved cloud/network storage.",
                "prompt_text": "Can unnecessary user files, downloads, or recycle bin contents be removed?",
                "condition_label": None,
                "condition_value": None,
                "solution_code": None,
                "sort_order": 1,
            },
            {
                "node_key": "S_EMPTY_TRASH_DOWNLOADS_TECH",
                "parent_key": "Q_USER_FILES_CAN_REMOVE",
                "node_type": "solution",
                "title": "Remove Unneeded Files",
                "description": None,
                "prompt_text": None,
                "condition_label": "Can unnecessary user files, downloads, or recycle bin contents be removed?",
                "condition_value": "Yes",
                "solution_code": "FIX_EMPTY_TRASH_DOWNLOADS",
                "sort_order": 1,
            },
            {
                "node_key": "Q_TEMP_FILES_OR_UPDATES",
                "parent_key": "Q_USER_FILES_CAN_REMOVE",
                "node_type": "question",
                "title": "Check Temporary/System Files",
                "description": "Check temporary files, update cache, logs, and approved cleanup tools.",
                "prompt_text": "Can temporary files or old update files be safely cleaned?",
                "condition_label": "Can unnecessary user files, downloads, or recycle bin contents be removed?",
                "condition_value": "No",
                "solution_code": None,
                "sort_order": 2,
            },
            {
                "node_key": "S_CLEAN_TEMP_FILES_TECH",
                "parent_key": "Q_TEMP_FILES_OR_UPDATES",
                "node_type": "solution",
                "title": "Clean Temporary Files",
                "description": None,
                "prompt_text": None,
                "condition_label": "Can temporary files or old update files be safely cleaned?",
                "condition_value": "Yes",
                "solution_code": "FIX_CLEAN_TEMP_FILES",
                "sort_order": 1,
            },
            {
                "node_key": "S_ESCALATE_STORAGE_TECH",
                "parent_key": "Q_TEMP_FILES_OR_UPDATES",
                "node_type": "solution",
                "title": "Escalate Storage Capacity Issue",
                "description": None,
                "prompt_text": None,
                "condition_label": "Can temporary files or old update files be safely cleaned?",
                "condition_value": "No",
                "solution_code": "FIX_ESCALATE_STORAGE_EXPANSION",
                "sort_order": 2,
            },
        ],
    },
    "HIGH_CPU_USAGE": {
        "title": "High CPU Usage - IT Support Specialist Diagnostic",
        "description": "IT Support Specialist diagnostic path for CPU spikes and suspicious processes.",
        "sort_order": 109,
        "nodes": [
            {
                "node_key": "ROOT_HIGH_CPU_TECH",
                "parent_key": None,
                "node_type": "category",
                "title": "High CPU Usage - IT Support Specialist Diagnostic",
                "description": "Check process ownership, restart state, endpoint health, and suspicious activity.",
                "prompt_text": None,
                "condition_label": None,
                "condition_value": None,
                "solution_code": None,
                "sort_order": 1,
            },
            {
                "node_key": "Q_IDENTIFIED_HIGH_CPU_APP",
                "parent_key": "ROOT_HIGH_CPU_TECH",
                "node_type": "question",
                "title": "Identify High CPU Process",
                "description": "Use Task Manager or endpoint tooling to identify the top CPU consumer.",
                "prompt_text": "Is a known user application consuming most of the CPU?",
                "condition_label": None,
                "condition_value": None,
                "solution_code": None,
                "sort_order": 1,
            },
            {
                "node_key": "S_CLOSE_HIGH_CPU_APP_TECH",
                "parent_key": "Q_IDENTIFIED_HIGH_CPU_APP",
                "node_type": "solution",
                "title": "Close High CPU Application",
                "description": None,
                "prompt_text": None,
                "condition_label": "Is a known user application consuming most of the CPU?",
                "condition_value": "Yes",
                "solution_code": "FIX_CLOSE_HIGH_CPU_PROCESS",
                "sort_order": 1,
            },
            {
                "node_key": "Q_SUSPICIOUS_OR_SYSTEM_PROCESS",
                "parent_key": "Q_IDENTIFIED_HIGH_CPU_APP",
                "node_type": "question",
                "title": "Check Suspicious/System Process",
                "description": "Determine whether the process is unknown, security-related, or a system service.",
                "prompt_text": "Is the high CPU process unknown, suspicious, security software, or a system service?",
                "condition_label": "Is a known user application consuming most of the CPU?",
                "condition_value": "No",
                "solution_code": None,
                "sort_order": 2,
            },
            {
                "node_key": "S_ESCALATE_MALWARE_ENDPOINT_TECH",
                "parent_key": "Q_SUSPICIOUS_OR_SYSTEM_PROCESS",
                "node_type": "solution",
                "title": "Escalate Possible Malware or Endpoint Issue",
                "description": None,
                "prompt_text": None,
                "condition_label": "Is the high CPU process unknown, suspicious, security software, or a system service?",
                "condition_value": "Yes",
                "solution_code": "FIX_ESCALATE_MALWARE_OR_ENDPOINT",
                "sort_order": 1,
            },
            {
                "node_key": "S_REBOOT_HIGH_CPU_TECH",
                "parent_key": "Q_SUSPICIOUS_OR_SYSTEM_PROCESS",
                "node_type": "solution",
                "title": "Restart After High CPU Usage",
                "description": None,
                "prompt_text": None,
                "condition_label": "Is the high CPU process unknown, suspicious, security software, or a system service?",
                "condition_value": "No",
                "solution_code": "FIX_REBOOT_AFTER_HIGH_CPU",
                "sort_order": 2,
            },
        ],
    },
    "VPN_CONNECTION_FAILURE": {
        "title": "VPN Connection Failure - IT Support Specialist Diagnostic",
        "description": "IT Support Specialist diagnostic path for VPN authentication, client, and network issues.",
        "sort_order": 110,
        "nodes": [
            {
                "node_key": "ROOT_VPN_FAILURE_TECH",
                "parent_key": None,
                "node_type": "category",
                "title": "VPN Connection Failure - IT Support Specialist Diagnostic",
                "description": "Check internet, credentials/MFA, network restrictions, client version, and escalation triggers.",
                "prompt_text": None,
                "condition_label": None,
                "condition_value": None,
                "solution_code": None,
                "sort_order": 1,
            },
            {
                "node_key": "Q_NORMAL_INTERNET_WORKS",
                "parent_key": "ROOT_VPN_FAILURE_TECH",
                "node_type": "question",
                "title": "Verify Base Internet",
                "description": "Confirm internet works outside of VPN before troubleshooting VPN-specific causes.",
                "prompt_text": "Does normal internet access work without VPN?",
                "condition_label": None,
                "condition_value": None,
                "solution_code": None,
                "sort_order": 1,
            },
            {
                "node_key": "S_RESTART_NETWORK_BEFORE_VPN_TECH",
                "parent_key": "Q_NORMAL_INTERNET_WORKS",
                "node_type": "solution",
                "title": "Restart Device and Network Equipment",
                "description": None,
                "prompt_text": None,
                "condition_label": "Does normal internet access work without VPN?",
                "condition_value": "No",
                "solution_code": "FIX_RESTART_NETWORK_EQUIPMENT",
                "sort_order": 1,
            },
            {
                "node_key": "Q_VPN_AUTH_MFA",
                "parent_key": "Q_NORMAL_INTERNET_WORKS",
                "node_type": "question",
                "title": "Check Authentication and MFA",
                "description": "Confirm password, account status, MFA prompt, and error text.",
                "prompt_text": "Does the error suggest credentials, account lockout, password expiry, or MFA failure?",
                "condition_label": "Does normal internet access work without VPN?",
                "condition_value": "Yes",
                "solution_code": None,
                "sort_order": 2,
            },
            {
                "node_key": "S_CHECK_VPN_CREDENTIALS_TECH",
                "parent_key": "Q_VPN_AUTH_MFA",
                "node_type": "solution",
                "title": "Check VPN Credentials and MFA",
                "description": None,
                "prompt_text": None,
                "condition_label": "Does the error suggest credentials, account lockout, password expiry, or MFA failure?",
                "condition_value": "Yes",
                "solution_code": "FIX_CHECK_VPN_CREDENTIALS_MFA",
                "sort_order": 1,
            },
            {
                "node_key": "Q_NETWORK_BLOCKING_VPN",
                "parent_key": "Q_VPN_AUTH_MFA",
                "node_type": "question",
                "title": "Check Network Path",
                "description": "Ask the user to test another trusted network or hotspot if available.",
                "prompt_text": "Does VPN work from another network or mobile hotspot?",
                "condition_label": "Does the error suggest credentials, account lockout, password expiry, or MFA failure?",
                "condition_value": "No",
                "solution_code": None,
                "sort_order": 2,
            },
            {
                "node_key": "S_CHANGE_NETWORK_VPN_TECH",
                "parent_key": "Q_NETWORK_BLOCKING_VPN",
                "node_type": "solution",
                "title": "Try Another Network for VPN",
                "description": None,
                "prompt_text": None,
                "condition_label": "Does VPN work from another network or mobile hotspot?",
                "condition_value": "Yes",
                "solution_code": "FIX_CHANGE_NETWORK_RETRY_VPN",
                "sort_order": 1,
            },
            {
                "node_key": "Q_VPN_CLIENT_CURRENT",
                "parent_key": "Q_NETWORK_BLOCKING_VPN",
                "node_type": "question",
                "title": "Check VPN Client",
                "description": "Review VPN client version, update status, and configuration.",
                "prompt_text": "Is the VPN client updated and correctly installed?",
                "condition_label": "Does VPN work from another network or mobile hotspot?",
                "condition_value": "No",
                "solution_code": None,
                "sort_order": 2,
            },
            {
                "node_key": "S_UPDATE_VPN_CLIENT_TECH",
                "parent_key": "Q_VPN_CLIENT_CURRENT",
                "node_type": "solution",
                "title": "Update or Reinstall VPN Client",
                "description": None,
                "prompt_text": None,
                "condition_label": "Is the VPN client updated and correctly installed?",
                "condition_value": "No",
                "solution_code": "FIX_UPDATE_VPN_CLIENT",
                "sort_order": 1,
            },
            {
                "node_key": "S_ESCALATE_VPN_SUPPORT_TECH",
                "parent_key": "Q_VPN_CLIENT_CURRENT",
                "node_type": "solution",
                "title": "Escalate VPN Connection Failure",
                "description": None,
                "prompt_text": None,
                "condition_label": "Is the VPN client updated and correctly installed?",
                "condition_value": "Yes",
                "solution_code": "FIX_ESCALATE_VPN_SUPPORT",
                "sort_order": 2,
            },
        ],
    },
}

ROLE_SPECIFIC_SOLUTION_STEPS = {
    "FIX_RECONNECT_NETWORK": {
        "technician": [
            "Verify Wi-Fi/Ethernet adapter status and confirm the correct SSID or cable connection.",
            "Check IP configuration using ipconfig /all and confirm IP address, gateway, and DNS values.",
            "Renew the DHCP lease if needed using ipconfig /release and ipconfig /renew.",
            "Confirm connectivity by pinging the default gateway and then an external IP.",
        ],
        "admin": [
            "Review the ticket for affected user, device, location, and connection type.",
            "Confirm whether the technician verified adapter state, IP configuration, gateway reachability, and DNS.",
            "Escalate to Network Team if the issue is not isolated to one device.",
        ],
    },
    "FIX_RESTART_NETWORK_EQUIPMENT": {
        "technician": [
            "Confirm whether the affected device, local router, modem, docking station, or access point may be causing the issue.",
            "Restart the client device and ask the user to reconnect.",
            "For remote/home users, ask them to power-cycle router/modem if appropriate.",
            "Retest gateway, DNS, and external connectivity after restart.",
        ],
        "admin": [
            "Confirm whether restarting local network equipment restored service.",
            "If repeated restarts are needed, document recurrence and escalate for infrastructure review.",
        ],
    },
    "FIX_ESCALATE_NETWORK_OUTAGE": {
        "technician": [
            "Collect affected location, number of impacted users, device names, start time, and error messages.",
            "Check whether gateway, DHCP, DNS, or upstream internet is unavailable.",
            "Review monitoring or network controller status if available.",
            "Escalate to Network Team with collected evidence.",
        ],
        "admin": [
            "Treat as possible incident if multiple users, departments, or business-critical services are affected.",
            "Prioritize as High or Critical depending on scope and business impact.",
            "Ensure escalation notes include impact, start time, affected systems, and troubleshooting already completed.",
        ],
    },
    "FIX_CHECK_DNS_BROWSER": {
        "technician": [
            "Test the affected website in another browser and private/incognito mode.",
            "Run nslookup for the affected domain and compare with known-good DNS.",
            "Flush DNS cache using ipconfig /flushdns.",
            "Clear browser cache/cookies or reset browser profile if only one browser is affected.",
            "Document affected URLs and error messages.",
        ],
        "admin": [
            "Confirm whether the issue is browser-specific, DNS-specific, or site-specific.",
            "Escalate if multiple users cannot access the same site or DNS failures continue.",
        ],
    },
    "FIX_ESCALATE_BLOCKED_WEBSITE": {
        "technician": [
            "Capture the full URL, screenshot, block message, certificate warning, and user location.",
            "Check whether the block appears in different browsers and networks.",
            "Do not bypass content filtering or security controls.",
            "Escalate to IT Security or Network Team with business justification.",
        ],
        "admin": [
            "Review business justification before approving any allow-list request.",
            "Route to Security/Network according to policy.",
            "Keep the ticket open until policy decision is confirmed.",
        ],
    },
    "FIX_MOVE_CLOSER_TO_AP": {
        "technician": [
            "Check signal quality, RSSI/SNR if tools are available, and distance from the access point.",
            "Ask user to test closer to the AP or in another known-good location.",
            "Check for interference, physical obstructions, or overloaded APs.",
            "Escalate if the location has repeated Wi-Fi coverage complaints.",
        ],
        "admin": [
            "Review whether the issue indicates a coverage gap or repeated location-based complaint.",
            "Escalate to Network Team if multiple tickets originate from the same area.",
        ],
    },
    "FIX_FORGET_REJOIN_WIFI": {
        "technician": [
            "Remove the saved Wi-Fi profile from the device.",
            "Reconnect to the correct SSID and verify credentials or certificate authentication.",
            "Confirm the device obtains a valid IP address and stable connection.",
            "Check MDM/NAC compliance if reconnection fails.",
        ],
        "admin": [
            "Confirm whether the issue was isolated to a corrupted wireless profile.",
            "If repeated profile resets are needed, review wireless policy or credential changes.",
        ],
    },
    "FIX_ESCALATE_WIFI_INFRASTRUCTURE": {
        "technician": [
            "Collect location, AP name/BSSID if available, affected users, device models, and timestamps.",
            "Check controller logs for association, authentication, roaming, or deauthentication events.",
            "Review channel utilization, AP client count, RSSI, and SNR.",
            "Escalate to Network Team with evidence.",
        ],
        "admin": [
            "Classify as infrastructure issue if multiple users or one area is affected.",
            "Prioritize according to business impact and number of affected users.",
        ],
    },
    "FIX_CLOSE_BANDWIDTH_APPS": {
        "technician": [
            "Review active downloads, cloud sync, streaming, and video conference usage.",
            "Ask the user to pause bandwidth-heavy activity and retest.",
            "Check whether performance improves on Ethernet or another network.",
            "Document before/after speed or latency results if available.",
        ],
        "admin": [
            "Confirm whether slowdown is user/device-specific or wider network congestion.",
            "Escalate if multiple users report performance degradation.",
        ],
    },
    "FIX_RUN_SPEED_TEST_ESCALATE": {
        "technician": [
            "Run a speed test from the affected device and record download/upload/latency.",
            "Compare Wi-Fi vs Ethernet if possible.",
            "Record location, SSID, device name, and time of test.",
            "Escalate if results are significantly below expected baseline.",
        ],
        "admin": [
            "Review speed-test evidence and affected scope.",
            "Escalate to Network Team if performance is below SLA or impacts multiple users.",
        ],
    },
    "FIX_RESTART_APPLICATION": {
        "technician": [
            "Ask user to save work if possible and fully close the application.",
            "Check Task Manager/Activity Monitor to ensure the process is closed.",
            "Restart the application and reproduce the user action.",
            "Document whether the crash returns.",
        ],
        "admin": [
            "If restart resolves the issue, close as transient application issue.",
            "If crashes recur, request logs and move to repair/update path.",
        ],
    },
    "FIX_UPDATE_APPLICATION": {
        "technician": [
            "Check application version and compare with approved/current version.",
            "Use approved software portal or installer to update or repair.",
            "Review application logs or Windows Event Viewer if available.",
            "Reproduce the crash after update/repair.",
        ],
        "admin": [
            "Confirm software source is approved and licensing is valid.",
            "Escalate to Application Support if update/repair does not resolve the issue.",
        ],
    },
    "FIX_ESCALATE_APP_CRASH": {
        "technician": [
            "Collect application name, version, crash message, screenshot, logs, and reproduction steps.",
            "Check if other users or devices experience the same crash.",
            "Verify recent updates, plugins, or configuration changes.",
            "Escalate to Application Support or vendor support.",
        ],
        "admin": [
            "Prioritize as High if the application is business-critical.",
            "Ensure escalation includes logs, version, affected users, and exact reproduction steps.",
        ],
    },
    "FIX_USE_APPROVED_INSTALLER": {
        "technician": [
            "Confirm the installer source and software name/version.",
            "Direct the user to the approved software portal or managed deployment tool.",
            "Remove untrusted installer copies if appropriate.",
            "Retry installation from the approved source.",
        ],
        "admin": [
            "Confirm business approval and licensing before installation.",
            "Do not authorize software from untrusted sources.",
        ],
    },
    "FIX_FREE_SPACE_FOR_INSTALL": {
        "technician": [
            "Check available disk space and installation requirements.",
            "Remove temporary files, recycle bin contents, or unnecessary downloads if allowed.",
            "Restart if cleanup tools require it.",
            "Retry installation and document result.",
        ],
        "admin": [
            "Review whether storage shortage is recurring or device requires capacity planning.",
            "Escalate if the device cannot maintain sufficient free space.",
        ],
    },
    "FIX_ESCALATE_INSTALL_ADMIN": {
        "technician": [
            "Collect software name, version, installer source, error message, and business reason.",
            "Confirm whether admin rights, licensing, or endpoint policy blocks installation.",
            "Escalate to Endpoint Management or IT Support lead.",
        ],
        "admin": [
            "Validate business need, license availability, and policy compliance.",
            "Approve or reject installation according to company policy.",
        ],
    },
    "FIX_RESTART_COMPUTER": {
        "technician": [
            "Check device uptime and pending restart status.",
            "Ask user to save work and restart the computer.",
            "After restart, check CPU, memory, disk usage, and responsiveness.",
        ],
        "admin": [
            "Close if performance returns to normal after restart.",
            "If issue repeats, continue with startup/process/hardware review.",
        ],
    },
    "FIX_DISABLE_STARTUP_APPS": {
        "technician": [
            "Review startup applications and background processes.",
            "Disable only non-essential startup items according to policy.",
            "Restart the device and compare boot time/performance.",
            "Document changes made.",
        ],
        "admin": [
            "Ensure startup changes follow policy and do not disable required security or management tools.",
            "Escalate recurring performance complaints for endpoint review.",
        ],
    },
    "FIX_ESCALATE_HARDWARE_PERFORMANCE": {
        "technician": [
            "Collect device model, asset tag, uptime, CPU, memory, disk health, and available storage.",
            "Check event logs and recent updates.",
            "Document examples of slow behavior and frequency.",
            "Escalate to Desktop Support for hardware or endpoint review.",
        ],
        "admin": [
            "Review whether replacement, memory upgrade, disk replacement, or reimage is appropriate.",
            "Prioritize according to productivity impact.",
        ],
    },
    "FIX_EMPTY_TRASH_DOWNLOADS": {
        "technician": [
            "Check largest user folders such as Downloads, Desktop, Videos, and Recycle Bin.",
            "Confirm with user before deleting personal or business files.",
            "Move approved files to cloud or network storage if appropriate.",
            "Retest available disk space.",
        ],
        "admin": [
            "Confirm user approval before file removal.",
            "Escalate if storage shortage affects updates or business applications.",
        ],
    },
    "FIX_CLEAN_TEMP_FILES": {
        "technician": [
            "Run approved disk cleanup tools.",
            "Remove temporary files, browser cache, and old update files where safe.",
            "Restart device and verify free space.",
            "Check if space fills again quickly.",
        ],
        "admin": [
            "If temporary files return quickly, investigate logs, sync tools, or misconfigured applications.",
            "Escalate if cleanup requires elevated access or recurring investigation.",
        ],
    },
    "FIX_ESCALATE_STORAGE_EXPANSION": {
        "technician": [
            "Record available free space, largest folders if known, and disk capacity.",
            "Check whether business files can be moved to approved storage.",
            "Escalate to Desktop Support for storage expansion, cleanup, or replacement review.",
        ],
        "admin": [
            "Review device lifecycle, storage capacity, and business justification.",
            "Approve replacement or expansion according to policy.",
        ],
    },
    "FIX_CLOSE_HIGH_CPU_PROCESS": {
        "technician": [
            "Identify the high CPU process in Task Manager or endpoint tool.",
            "Confirm whether it is a known user application.",
            "Restart the application and monitor CPU usage.",
            "Do not terminate security or system processes without approval.",
        ],
        "admin": [
            "If a business app repeatedly causes high CPU, route to Application Support.",
            "If a system/security process is involved, escalate to Endpoint/Security.",
        ],
    },
    "FIX_REBOOT_AFTER_HIGH_CPU": {
        "technician": [
            "Ask the user to save work and restart the device.",
            "Monitor CPU after restart.",
            "Check if pending updates or stuck processes clear after reboot.",
        ],
        "admin": [
            "Close as transient only if CPU remains normal after restart.",
            "If recurring, escalate with process and event log details.",
        ],
    },
    "FIX_ESCALATE_MALWARE_OR_ENDPOINT": {
        "technician": [
            "Collect process name, screenshots, security alerts, recent downloads, and device name.",
            "Do not disable endpoint protection.",
            "Disconnect from network only if instructed by Security policy.",
            "Escalate to Security or Endpoint Support immediately.",
        ],
        "admin": [
            "Treat suspicious behavior as security-sensitive.",
            "Ensure escalation contains evidence and affected asset information.",
            "Follow incident response procedures if malware is suspected.",
        ],
    },
    "FIX_CHECK_VPN_CREDENTIALS_MFA": {
        "technician": [
            "Confirm username format, password status, account lockout, and MFA prompt delivery.",
            "Ask the user to approve MFA and retry.",
            "Check identity provider or VPN logs if available.",
            "Escalate if MFA is not received or authentication fails repeatedly.",
        ],
        "admin": [
            "Review whether the issue is account-specific or affects multiple VPN users.",
            "Prioritize if the user is blocked from critical remote work.",
        ],
    },
    "FIX_CHANGE_NETWORK_RETRY_VPN": {
        "technician": [
            "Ask the user to test VPN from another trusted network or mobile hotspot.",
            "Check whether the current network blocks VPN ports/protocols.",
            "Document network type and whether the alternate network succeeds.",
        ],
        "admin": [
            "If VPN works on another network, document likely local ISP/router/firewall restriction.",
            "Escalate if company-managed network is blocking VPN.",
        ],
    },
    "FIX_UPDATE_VPN_CLIENT": {
        "technician": [
            "Check VPN client version and configuration profile.",
            "Update or reinstall VPN client from approved source.",
            "Confirm certificates/configuration are present if applicable.",
            "Retest connection and collect error logs if failure continues.",
        ],
        "admin": [
            "Verify endpoint management or software deployment status.",
            "Escalate if installation requires elevated rights or client configuration package is missing.",
        ],
    },
    "FIX_ESCALATE_VPN_SUPPORT": {
        "technician": [
            "Collect username, device name, VPN client version, error code, network type, MFA status, and screenshots.",
            "Check if multiple users are affected.",
            "Escalate to Network/VPN Support with all evidence.",
        ],
        "admin": [
            "Prioritize as High if multiple remote users are blocked.",
            "Ensure escalation includes authentication state, client version, and network test results.",
        ],
    },
}


def get_solution_id_by_code(cursor, solution_code):
    """Return solution_id for a stable solution_code."""
    cursor.execute(
        "SELECT solution_id FROM solution WHERE solution_code = ?",
        (solution_code,),
    )
    row = cursor.fetchone()
    return row["solution_id"] if row else None


def get_diagnostic_tree_id_by_code(cursor, diagnostic_tree_code):
    """Return diagnostic_tree_id for a stable diagnostic_tree_code."""
    cursor.execute(
        "SELECT diagnostic_tree_id FROM diagnostic_tree WHERE diagnostic_tree_code = ?",
        (diagnostic_tree_code,),
    )
    row = cursor.fetchone()
    return row["diagnostic_tree_id"] if row else None


def get_diagnostic_node_id_by_tree_and_key(cursor, diagnostic_tree_id, node_key):
    """Return diagnostic_node_id for a node inside a diagnostic tree."""
    cursor.execute(
        """
        SELECT diagnostic_node_id
        FROM diagnostic_node
        WHERE diagnostic_tree_id = ?
          AND node_key = ?
        """,
        (diagnostic_tree_id, node_key),
    )
    row = cursor.fetchone()
    return row["diagnostic_node_id"] if row else None


def seed_role_specific_solution_steps(cursor):
    """Seed technician/admin solution steps for all demo solutions."""
    for solution_code, audience_steps in ROLE_SPECIFIC_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue

        for audience, steps in audience_steps.items():
            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM solution_step
                WHERE solution_id = ?
                  AND audience = ?
                """,
                (solution_id, audience),
            )

            if cursor.fetchone()["count"] > 0:
                continue

            cursor.executemany(
                """
                INSERT INTO solution_step (
                    solution_id,
                    audience,
                    step_text,
                    sort_order
                )
                VALUES (?, ?, ?, ?)
                """,
                [
                    (solution_id, audience, step_text, index)
                    for index, step_text in enumerate(steps, start=1)
                ],
            )


def seed_technician_diagnostic_tree(cursor, base_tree_code, tree_config):
    """Seed one technician diagnostic tree and its nodes."""
    problem_id = get_problem_id_for_tree_code(cursor, base_tree_code)
    diagnostic_tree_code = f"{base_tree_code}_TECHNICIAN"

    cursor.execute(
        """
        INSERT OR IGNORE INTO diagnostic_tree (
            problem_id,
            diagnostic_tree_code,
            base_tree_code,
            audience,
            title,
            description
        )
        VALUES (?, ?, ?, 'technician', ?, ?)
        """,
        (
            problem_id,
            diagnostic_tree_code,
            base_tree_code,
            tree_config["title"],
            tree_config.get("description", ""),
        ),
    )

    diagnostic_tree_id = get_diagnostic_tree_id_by_code(cursor, diagnostic_tree_code)

    if not diagnostic_tree_id:
        return

    for node in tree_config["nodes"]:
        parent_id = None
        if node["parent_key"]:
            parent_id = get_diagnostic_node_id_by_tree_and_key(
                cursor,
                diagnostic_tree_id,
                node["parent_key"],
            )

        solution_id = None
        if node.get("solution_code"):
            solution_id = get_solution_id_by_code(cursor, node["solution_code"])

        cursor.execute(
            """
            INSERT OR IGNORE INTO diagnostic_node (
                diagnostic_tree_id,
                parent_diagnostic_node_id,
                problem_id,
                diagnostic_tree_code,
                node_key,
                node_type,
                title,
                description,
                prompt_text,
                condition_label,
                condition_value,
                solution_id,
                sort_order
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                diagnostic_tree_id,
                parent_id,
                problem_id,
                diagnostic_tree_code,
                node["node_key"],
                node["node_type"],
                node["title"],
                node.get("description"),
                node.get("prompt_text"),
                node.get("condition_label"),
                node.get("condition_value"),
                solution_id,
                node.get("sort_order", 0),
            ),
        )


def seed_role_specific_diagnostic_content(cursor):
    """Seed technician diagnostic trees and technician/admin solution steps."""
    seed_role_specific_solution_steps(cursor)

    for base_tree_code, tree_config in TECHNICIAN_DIAGNOSTIC_TREE_SEED_DATA.items():
        seed_technician_diagnostic_tree(cursor, base_tree_code, tree_config)


# -----------------------------
# PRINTER FAILURE RELATIONAL SEED DATA
# -----------------------------
PRINTER_FAILURE_PROBLEM = (
    'PRINTER_FAILURE',
    'Printer Failure',
    'Hardware',
    'medium',
    'User cannot print, printer is offline, print jobs are stuck, or printer shows hardware/network errors.',
)

PRINTER_FAILURE_KB = {
    'title': 'Printer Failure',
    'summary': 'Troubleshooting article for printer power, connectivity, queue, driver, paper, toner, permissions, and print server issues.',
    'difficulty': 'Intermediate',
    'estimated_time': '10-20 minutes',
    'escalation_required': 0,
    'escalation_notes': 'Escalate if multiple users are affected, printer is unreachable, print server issues are suspected, access/permission issues are present, or hardware damage is visible.',
    'tags': ['printer', 'printing', 'print queue', 'spooler', 'driver', 'paper jam', 'toner', 'print server', 'permissions'],
    'symptoms': [
        'Printer does not power on',
        'Printer shows Offline',
        'Print jobs are stuck in the queue',
        'User cannot print from one or all applications',
        'Paper jam, no paper, low toner, or door/tray warning',
        'Printer is unreachable on the network',
        'Multiple users cannot print to the same printer',
    ],
    'causes': [
        'Common: printer powered off, disconnected cable, wrong printer selected, offline mode enabled, stuck queue, Print Spooler issue, paper jam, no paper, low toner, incorrect driver, changed printer IP, lost Wi-Fi/network connection.',
        'Rare: firmware bug, corrupted print server driver, port misconfiguration, IP conflict, VLAN or firewall block, faulty network card, damaged rollers, faulty paper sensor, corrupted Windows print subsystem, user permission problem, failed Group Policy deployment, print server spooler crash, application-specific rendering issue, OS update driver incompatibility.',
    ],
    'user_steps': [
        'Check that the printer is powered on.',
        'Check for paper, toner, paper jam, or warning messages on the printer screen.',
        'Make sure you selected the correct printer.',
        'Cancel stuck print jobs if possible.',
        'Restart the printer and try again.',
        'If it is a USB printer, check that the cable is connected.',
        'If it is a network printer, ask whether nearby users can print.',
        'Create a support ticket if the issue continues.',
    ],
    'it_steps': [
        'Confirm printer name, model, location, connection type, and affected users.',
        'Check printer power, display panel, paper/toner status, and visible hardware errors.',
        'Check USB, Ethernet, Wi-Fi, or print server connectivity.',
        'For network printers, verify IP address and ping reachability.',
        'Check print queue and restart Print Spooler if needed.',
        'Remove/re-add the printer or update/reinstall the printer driver.',
        'Check print server queue, port, permissions, and Group Policy deployment.',
        'Escalate to Desktop, Network, Server/Endpoint, or Security/Access team based on root cause.',
    ],
}

PRINTER_FAILURE_SOLUTIONS = [
    ('FIX_PRINTER_POWER','Check Printer Power','The printer may be powered off, disconnected from power, or connected to a faulty outlet.','Check the power cable. Confirm the wall outlet works. Try another outlet. Bypass the power strip if needed. Check for visible damage, burning smell, or unusual noise.',0,'Escalate to Hardware/Desktop Support if the printer does not power on after testing another outlet or if there is visible damage.','medium'),
    ('FIX_PRINTER_USB_CONNECTION','Check USB Printer Connection','A USB printer may not be detected because of a loose cable, bad USB port, or cable failure.','Disconnect and reconnect the USB cable. Try another USB port. Try another USB cable if available. Restart the printer and computer. Confirm the printer appears in system printer settings.',0,'Escalate if the printer is not detected after testing another port/cable.','low'),
    ('FIX_PRINTER_NETWORK_CONNECTION','Check Network Printer Connection','The network printer may be disconnected from Wi-Fi/Ethernet or using an incorrect IP address.','Confirm the printer is on the correct network. Print a network configuration page if possible. Verify the printer IP address. Ping the printer IP from the computer. Confirm the user is on the same network/VPN as the printer.',0,'Escalate to Network Team if the printer has no IP address, cannot be pinged, or multiple users cannot reach it.','medium'),
    ('FIX_PRINTER_OFFLINE_REACHABLE','Fix Offline Printer That Is Reachable','The printer is reachable on the network but the print system marks it as offline.','Disable Use Printer Offline if enabled. Clear stuck jobs. Restart the Print Spooler. Remove and re-add the printer. Confirm the correct printer port/IP is configured.',0,'Escalate if the printer repeatedly goes offline or the print server queue is affected.','medium'),
    ('FIX_PRINTER_UNREACHABLE','Fix Unreachable Network Printer','The printer cannot be reached from the client device.','Confirm the printer is powered on. Check Ethernet/Wi-Fi connection. Compare current printer IP with configured printer port. Restart printer network connection. Check switch port or Wi-Fi signal if available.',1,'Escalate if the printer is unreachable from multiple devices, an IP conflict is suspected, or VLAN/DHCP/firewall issues are possible.','high'),
    ('FIX_CLEAR_PRINT_QUEUE','Clear Stuck Print Queue','Print jobs may be stuck in the local or server print queue.','Cancel stuck print jobs. Restart the printer. Restart the Print Spooler. Send a test print. If the queue remains stuck, remove and re-add the printer.',0,'Escalate if Print Spooler repeatedly crashes, jobs from multiple users are stuck, or the print server queue is affected.','medium'),
    ('FIX_PAPER_TONER_JAM','Resolve Paper, Toner, or Tray Warning','The printer may be blocked by a paper jam, empty tray, low toner, open door, or sensor warning.','Follow the printer screen instructions. Clear paper jam carefully. Check for torn paper pieces. Reload correct paper size. Reseat or replace toner/ink. Close all trays and doors. Print a test page.',0,'Escalate if jams keep returning, the printer reports a jam with no visible paper, toner warnings remain after replacement, or mechanical damage/noise is present.','medium'),
    ('FIX_REINSTALL_PRINTER_DRIVER','Reinstall Printer or Update Driver','The printer may be missing, duplicated, using the wrong driver, or affected by a corrupted driver.','Remove duplicate or old printer entries. Add the correct printer from the print server or approved printer list. Confirm the correct driver is used. Set as default if needed. Print a test page.',0,'Escalate if driver deployment requires admin/endpoint management or multiple computers fail with the same driver.','medium'),
    ('FIX_APPLICATION_PRINTING','Fix Application-Specific Printing Issue','Printing fails only from one application, likely due to document formatting, application settings, or rendering issue.','Try printing a simple test page. Try printing from another application. Export the document to PDF and print the PDF. Check page size, margins, and selected printer. Restart or update the application.',0,'Escalate if the business application repeatedly fails to print or vendor support may be required.','medium'),
    ('FIX_PRINT_SERVER_OR_PERMISSION','Escalate Print Server or Permission Issue','The issue may involve shared printer permissions, print server queue, driver package, or Group Policy deployment.','Check whether other users can print. Confirm the user has permission. Check print server queue, printer port, driver, and spooler. Check group membership or printer deployment policy if access is restricted.',1,'Escalate to Server/Endpoint or Access Management if multiple users are affected, print server is unavailable, spooler crashes, or printer permissions are controlled by AD/security groups.','high'),
]

PRINTER_FAILURE_SOLUTION_STEPS = {
    'FIX_PRINTER_POWER': {'user':['Make sure the printer is turned on.','Check that the power cable is connected firmly.','Try another wall outlet if possible.','Stop and call IT if you see smoke, burning smell, or damaged cables.'], 'technician':['Verify outlet power and printer power cable connection.','Bypass power strip if applicable.','Check display, LEDs, adapter, and visible cable damage.','Escalate to hardware support if the printer remains unpowered.'], 'admin':['Classify as hardware issue if power remains unavailable after outlet/cable checks.','Escalate immediately if safety risk, burning smell, or physical damage exists.']},
    'FIX_PRINTER_USB_CONNECTION': {'user':['Check that the USB cable is connected to the printer and computer.','Restart the printer and try printing again.','Restart your computer if the printer is still not detected.'], 'technician':['Reconnect USB cable and test another USB port.','Test another USB cable if available.','Verify printer appears in Devices and Printers or system printer settings.','Reinstall printer if the OS does not detect the device.'], 'admin':['Escalate to Desktop Support if the printer remains undetected after cable/port testing.']},
    'FIX_PRINTER_NETWORK_CONNECTION': {'user':['Check that the printer is connected to the office network or Wi-Fi.','Ask nearby users whether they can print to the same printer.','Restart the printer and try again.'], 'technician':['Print or view printer network configuration.','Verify IP address, subnet, gateway, and network status.','Ping printer IP from affected client.','Confirm the client is on the same network/VPN as the printer.'], 'admin':['Escalate to Network Team if the printer has no IP, cannot be reached, or multiple users are impacted.']},
    'FIX_PRINTER_OFFLINE_REACHABLE': {'user':['Check if the printer is showing Offline.','Restart the printer.','Cancel stuck jobs if possible.'], 'technician':['Disable Use Printer Offline if enabled.','Clear local queue and restart Print Spooler.','Validate configured printer port/IP.','Remove and re-add the printer if offline state persists.'], 'admin':['Investigate recurring offline state and check print server or port configuration if repeated.']},
    'FIX_PRINTER_UNREACHABLE': {'user':['Confirm the printer is turned on.','Check whether other users can print to the same printer.','Report the printer location and any screen error message.'], 'technician':['Ping the printer IP from client and print server.','Compare current printer IP with configured port.','Check Ethernet/Wi-Fi state, switch port, VLAN, DHCP reservation, and IP conflict indicators.','Escalate with printer name, IP, location, and ping results.'], 'admin':['Treat as network/infrastructure issue if multiple users cannot reach the printer.','Escalate to Network Team with scope, location, and test results.']},
    'FIX_CLEAR_PRINT_QUEUE': {'user':['Cancel stuck print jobs if you can.','Restart the printer.','Try printing a simple test page.'], 'technician':['Clear local and/or server-side print queue.','Restart Print Spooler service.','Use net stop spooler and net start spooler if appropriate.','Send a test print and monitor queue behavior.'], 'admin':['Escalate if spooler repeatedly crashes or several users/jobs are stuck on the print server.']},
    'FIX_PAPER_TONER_JAM': {'user':['Check the printer screen for paper, toner, tray, or door warnings.','Add paper if needed.','Follow printer instructions to clear a jam carefully.','Tell IT if the warning returns.'], 'technician':['Inspect indicated tray/door/path for jammed or torn paper.','Verify paper size/type and tray alignment.','Reseat or replace toner/ink if warning exists.','Print test page and confirm warning clears.'], 'admin':['Escalate to hardware/vendor support if jams repeat, sensor warning remains, or rollers appear damaged.']},
    'FIX_REINSTALL_PRINTER_DRIVER': {'user':['Make sure you selected the correct printer.','Try printing a test page.','Contact IT if the printer is missing from your printer list.'], 'technician':['Remove duplicate or stale printer entries.','Re-add printer from print server or approved printer list.','Verify correct driver and printer port.','Update or redeploy driver if needed.'], 'admin':['Escalate to Endpoint/Server team if driver package or deployment affects multiple devices.']},
    'FIX_APPLICATION_PRINTING': {'user':['Try printing from another application.','Save or export the document as PDF and try printing the PDF.','Restart the application.'], 'technician':['Test Notepad/simple page printing.','Compare behavior across applications.','Check document margins, page size, and selected printer.','Repair/update application if issue is application-specific.'], 'admin':['Escalate to Application Support if a business application repeatedly cannot print.']},
    'FIX_PRINT_SERVER_OR_PERMISSION': {'user':['Ask a nearby colleague if they can print to the same printer.','Tell IT whether the printer is missing or showing access denied.'], 'technician':['Check whether other users can print to the same shared printer.','Verify user has printer permissions and correct AD/security group membership.','Check print server queue, printer port, driver, and spooler service.','Check Group Policy printer deployment if applicable.'], 'admin':['Escalate to Server/Endpoint if print server, driver, or spooler affects multiple users.','Escalate to Access Management if permissions or security groups are the root cause.']},
}

PRINTER_USER_DIAGNOSTIC_NODES = [
    ('ROOT_PRINTER_FAILURE_USER',None,'category','Printer Failure - User Diagnostic','User-friendly diagnostic path for common printer issues.',None,None,None,None,1),
    ('Q_POWER_USER','ROOT_PRINTER_FAILURE_USER','question','Check Printer Power','Start with the safest visible check.','Is the printer powered on?',None,None,None,1),
    ('S_POWER_USER','Q_POWER_USER','solution','Check Printer Power',None,None,'Is the printer powered on?','No','FIX_PRINTER_POWER',1),
    ('Q_WARNING_USER','Q_POWER_USER','question','Check Printer Warning','Look for visible printer screen messages.','Does the printer show paper jam, no paper, low toner, or door/tray warning?','Is the printer powered on?','Yes',None,2),
    ('S_PAPER_TONER_USER','Q_WARNING_USER','solution','Resolve Paper, Toner, or Tray Warning',None,None,'Does the printer show paper jam, no paper, low toner, or door/tray warning?','Yes','FIX_PAPER_TONER_JAM',1),
    ('Q_OFFLINE_USER','Q_WARNING_USER','question','Check Offline Status','Determine whether the printer appears offline.','Does the printer show as Offline on your computer?','Does the printer show paper jam, no paper, low toner, or door/tray warning?','No',None,2),
    ('S_NETWORK_USER','Q_OFFLINE_USER','solution','Check Network Printer Connection',None,None,'Does the printer show as Offline on your computer?','Yes','FIX_PRINTER_NETWORK_CONNECTION',1),
    ('Q_QUEUE_USER','Q_OFFLINE_USER','question','Check Print Queue','Check whether print jobs are stuck.','Are print jobs stuck in the queue?','Does the printer show as Offline on your computer?','No',None,2),
    ('S_QUEUE_USER','Q_QUEUE_USER','solution','Clear Stuck Print Queue',None,None,'Are print jobs stuck in the queue?','Yes','FIX_CLEAR_PRINT_QUEUE',1),
    ('Q_APP_USER','Q_QUEUE_USER','question','Check Application Scope','Determine if printing fails everywhere or only one app.','Does printing fail only from one application?','Are print jobs stuck in the queue?','No',None,2),
    ('S_APP_USER','Q_APP_USER','solution','Fix Application-Specific Printing Issue',None,None,'Does printing fail only from one application?','Yes','FIX_APPLICATION_PRINTING',1),
    ('S_DRIVER_USER','Q_APP_USER','solution','Reinstall Printer or Update Driver',None,None,'Does printing fail only from one application?','No','FIX_REINSTALL_PRINTER_DRIVER',2),
]

PRINTER_TECH_DIAGNOSTIC_NODES = [
    ('ROOT_PRINTER_FAILURE_TECH',None,'category','Printer Failure - IT Support Specialist Diagnostic','IT Support Specialist diagnostic path for printer power, connectivity, queue, driver, hardware, permissions, and print server issues.',None,None,None,None,1),
    ('Q_POWER_TECH','ROOT_PRINTER_FAILURE_TECH','question','Check Power State','Confirm power, outlet, cable, display, and safety conditions.','Is the printer powered on with no visible power/safety issue?',None,None,None,1),
    ('S_POWER_TECH','Q_POWER_TECH','solution','Check Printer Power',None,None,'Is the printer powered on with no visible power/safety issue?','No','FIX_PRINTER_POWER',1),
    ('Q_USB_TECH','Q_POWER_TECH','question','Identify Connection Type','Determine whether the troubleshooting path is USB or network/print server.','Is this a USB-connected printer?','Is the printer powered on with no visible power/safety issue?','Yes',None,2),
    ('S_USB_TECH','Q_USB_TECH','solution','Check USB Printer Connection',None,None,'Is this a USB-connected printer?','Yes','FIX_PRINTER_USB_CONNECTION',1),
    ('Q_REACHABLE_TECH','Q_USB_TECH','question','Check Network Reachability','For network printers, verify IP address and ping reachability.','Can you ping or otherwise reach the printer IP address?','Is this a USB-connected printer?','No',None,2),
    ('S_UNREACHABLE_TECH','Q_REACHABLE_TECH','solution','Fix Unreachable Network Printer',None,None,'Can you ping or otherwise reach the printer IP address?','No','FIX_PRINTER_UNREACHABLE',1),
    ('Q_OFFLINE_TECH','Q_REACHABLE_TECH','question','Check Offline State','Printer is reachable but may be marked offline locally or on print server.','Is the printer marked Offline even though it is reachable?','Can you ping or otherwise reach the printer IP address?','Yes',None,2),
    ('S_OFFLINE_TECH','Q_OFFLINE_TECH','solution','Fix Offline Printer That Is Reachable',None,None,'Is the printer marked Offline even though it is reachable?','Yes','FIX_PRINTER_OFFLINE_REACHABLE',1),
    ('Q_QUEUE_TECH','Q_OFFLINE_TECH','question','Check Queue/Spooler','Review local and print server queues.','Are print jobs stuck in the queue or is the spooler unstable?','Is the printer marked Offline even though it is reachable?','No',None,2),
    ('S_QUEUE_TECH','Q_QUEUE_TECH','solution','Clear Stuck Print Queue',None,None,'Are print jobs stuck in the queue or is the spooler unstable?','Yes','FIX_CLEAR_PRINT_QUEUE',1),
    ('Q_PANEL_TECH','Q_QUEUE_TECH','question','Check Printer Panel Warnings','Look for physical printer errors.','Does the printer show paper jam, toner, tray, door, sensor, or mechanical warning?','Are print jobs stuck in the queue or is the spooler unstable?','No',None,2),
    ('S_PANEL_TECH','Q_PANEL_TECH','solution','Resolve Paper, Toner, or Tray Warning',None,None,'Does the printer show paper jam, toner, tray, door, sensor, or mechanical warning?','Yes','FIX_PAPER_TONER_JAM',1),
    ('Q_APP_TECH','Q_PANEL_TECH','question','Check Application Scope','Determine if failure is app-specific or system-wide.','Does printing fail only from one application?','Does the printer show paper jam, toner, tray, door, sensor, or mechanical warning?','No',None,2),
    ('S_APP_TECH','Q_APP_TECH','solution','Fix Application-Specific Printing Issue',None,None,'Does printing fail only from one application?','Yes','FIX_APPLICATION_PRINTING',1),
    ('Q_MULTIPLE_USERS_TECH','Q_APP_TECH','question','Check Shared Printer Scope','Determine whether this is one user/device or a shared printer issue.','Are multiple users unable to print to the same printer?','Does printing fail only from one application?','No',None,2),
    ('S_SERVER_PERMISSION_TECH','Q_MULTIPLE_USERS_TECH','solution','Escalate Print Server or Permission Issue',None,None,'Are multiple users unable to print to the same printer?','Yes','FIX_PRINT_SERVER_OR_PERMISSION',1),
    ('S_DRIVER_TECH','Q_MULTIPLE_USERS_TECH','solution','Reinstall Printer or Update Driver',None,None,'Are multiple users unable to print to the same printer?','No','FIX_REINSTALL_PRINTER_DRIVER',2),
]

def seed_printer_failure_content(cursor):
    """Seed Printer Failure KB article, solutions, role-specific steps, and diagnostic trees."""
    code_, title, category, severity, description = PRINTER_FAILURE_PROBLEM
    cursor.execute("""
        INSERT INTO problem (problem_code, title, category, severity, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(problem_code) DO UPDATE SET
            title=excluded.title, category=excluded.category, severity=excluded.severity,
            description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, PRINTER_FAILURE_PROBLEM)
    cursor.execute('SELECT problem_id FROM problem WHERE problem_code = ?', (code_,))
    row = cursor.fetchone()
    if not row:
        return
    problem_id = row['problem_id']
    cursor.execute("""
        INSERT INTO kb_article (problem_id, title, summary, difficulty, estimated_time, escalation_required, escalation_notes, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, difficulty=excluded.difficulty,
            estimated_time=excluded.estimated_time, escalation_required=excluded.escalation_required,
            escalation_notes=excluded.escalation_notes, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, PRINTER_FAILURE_KB['title'], PRINTER_FAILURE_KB['summary'], PRINTER_FAILURE_KB['difficulty'], PRINTER_FAILURE_KB['estimated_time'], PRINTER_FAILURE_KB['escalation_required'], PRINTER_FAILURE_KB['escalation_notes']))
    cursor.execute('SELECT kb_article_id FROM kb_article WHERE problem_id = ?', (problem_id,))
    article = cursor.fetchone()
    if article:
        kb_id = article['kb_article_id']
        delete_kb_child_rows(cursor, kb_id)
        insert_kb_child_rows(cursor, 'kb_article_tag', 'tag', kb_id, PRINTER_FAILURE_KB['tags'])
        insert_kb_child_rows(cursor, 'kb_article_symptom', 'symptom', kb_id, PRINTER_FAILURE_KB['symptoms'])
        insert_kb_child_rows(cursor, 'kb_article_cause', 'cause', kb_id, PRINTER_FAILURE_KB['causes'])
        insert_kb_child_rows(cursor, 'kb_article_user_step', 'step_text', kb_id, PRINTER_FAILURE_KB['user_steps'])
        insert_kb_child_rows(cursor, 'kb_article_it_step', 'step_text', kb_id, PRINTER_FAILURE_KB['it_steps'])
    cursor.executemany("""
        INSERT INTO solution (solution_code, title, summary, resolution_steps, escalation_required, escalation_notes, priority_recommendation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(solution_code) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, resolution_steps=excluded.resolution_steps,
            escalation_required=excluded.escalation_required, escalation_notes=excluded.escalation_notes,
            priority_recommendation=excluded.priority_recommendation, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, PRINTER_FAILURE_SOLUTIONS)
    for solution_code, audience_steps in PRINTER_FAILURE_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue
        for audience, steps in audience_steps.items():
            cursor.execute('DELETE FROM solution_step WHERE solution_id = ? AND audience = ?', (solution_id, audience))
            cursor.executemany('INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)', [(solution_id, audience, step, idx) for idx, step in enumerate(steps, start=1)])
    seed_printer_failure_tree(cursor, 'user', 'PRINTER_FAILURE_USER', 'Printer Failure - User Diagnostic', 'User-friendly diagnostic tree for printer failure symptoms.', PRINTER_USER_DIAGNOSTIC_NODES)
    seed_printer_failure_tree(cursor, 'technician', 'PRINTER_FAILURE_TECHNICIAN', 'Printer Failure - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for printer failure root-cause analysis.', PRINTER_TECH_DIAGNOSTIC_NODES)

def seed_printer_failure_tree(cursor, audience, tree_code, title, description, nodes):
    problem_id = get_problem_id_for_tree_code(cursor, 'PRINTER_FAILURE')
    cursor.execute("""
        INSERT INTO diagnostic_tree (problem_id, diagnostic_tree_code, base_tree_code, audience, title, description, is_active, updated_at)
        VALUES (?, ?, 'PRINTER_FAILURE', ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(diagnostic_tree_code) DO UPDATE SET
            problem_id=excluded.problem_id, base_tree_code=excluded.base_tree_code, audience=excluded.audience,
            title=excluded.title, description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, tree_code, audience, title, description))
    tree_id = get_diagnostic_tree_id_by_code(cursor, tree_code)
    if not tree_id:
        return
    # Do not delete/recreate diagnostic nodes here. Existing troubleshooting
    # sessions/events may reference diagnostic_node rows, so deleting them can
    # fail with FOREIGN KEY constraint errors and would also break audit history.
    # Instead, mark the existing tree inactive, then upsert the current seed
    # nodes back to active. This preserves stable node IDs across app restarts.
    cursor.execute('UPDATE diagnostic_node SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE diagnostic_tree_id = ?', (tree_id,))
    for node_key, parent_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_code, sort_order in nodes:
        parent_id = get_diagnostic_node_id_by_tree_and_key(cursor, tree_id, parent_key) if parent_key else None
        solution_id = get_solution_id_by_code(cursor, solution_code) if solution_code else None
        cursor.execute("""
            INSERT INTO diagnostic_node (
                diagnostic_tree_id, parent_diagnostic_node_id, problem_id, diagnostic_tree_code,
                node_key, node_type, title, description, prompt_text,
                condition_label, condition_value, solution_id, sort_order, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(diagnostic_tree_code, node_key) DO UPDATE SET
                diagnostic_tree_id=excluded.diagnostic_tree_id,
                parent_diagnostic_node_id=excluded.parent_diagnostic_node_id,
                problem_id=excluded.problem_id,
                node_type=excluded.node_type,
                title=excluded.title,
                description=excluded.description,
                prompt_text=excluded.prompt_text,
                condition_label=excluded.condition_label,
                condition_value=excluded.condition_value,
                solution_id=excluded.solution_id,
                sort_order=excluded.sort_order,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (tree_id, parent_id, problem_id, tree_code, node_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_id, sort_order))



# -----------------------------
# PASSWORD RESET REQUEST RELATIONAL SEED DATA
# -----------------------------
PASSWORD_RESET_REQUEST_PROBLEM = (
    'PASSWORD_RESET_REQUEST',
    'Password Reset Request',
    'Account & Access',
    'medium',
    'User cannot sign in because they forgot their password, believe their password expired, or need to reset it.',
)

PASSWORD_RESET_REQUEST_KB = {
    'title': 'Password Reset Request',
    'summary': 'Use this guide when a user forgot their password, their password expired, or the password reset process does not work.',
    'difficulty': 'Beginner',
    'estimated_time': '5-10 minutes',
    'escalation_required': 0,
    'escalation_notes': 'Escalate if identity cannot be verified, MFA/recovery methods are unavailable, suspicious sign-in activity exists, or reset succeeds in one system but fails in another.',
    'tags': ['password', 'reset', 'account', 'login', 'sign-in', 'expired password', 'forgot password', 'self-service password reset', 'MFA'],
    'symptoms': [
        'User forgot their password',
        'Password is not working',
        'Password expired message appears',
        'Password reset link or portal does not work',
        'Reset code, email, or MFA prompt is not received',
        'Password was changed but sign-in still fails',
        'User can sign in to some systems but not others',
        'Account locked message appears after repeated failed attempts',
    ],
    'causes': [
        'Common: forgotten password, expired password, wrong username, Caps Lock or keyboard layout issue, failed self-service reset, outdated recovery email/phone, old saved passwords on mobile/email/VPN, browser cached session, or account lockout.',
        'Advanced: directory synchronization delay, password writeback failure, conditional access block, missing MFA registration, disabled or expired account, password policy conflict, identity provider outage, separate local application credentials, or compromised-account protection.',
    ],
    'user_steps': [
        'Confirm you are using the correct company username or email address.',
        'Check that Caps Lock is off and the keyboard language/layout is correct.',
        'Try signing in from a private/incognito browser window.',
        'Use the company-approved password reset portal.',
        'Follow the password requirements shown on the reset page.',
        'After resetting the password, wait a few minutes and try signing in again.',
        'Update the new password on saved devices, email apps, VPN, and mobile devices.',
        'If you do not receive a reset code or email, check your recovery phone/email and spam/junk folder.',
        'Submit a support ticket if the reset portal does not work or you still cannot sign in.',
    ],
    'it_steps': [
        'Verify the user identity according to support policy before resetting or discussing account details.',
        'Confirm the exact username/email and the system the user is trying to access.',
        'Check whether the user can complete self-service password reset.',
        'Check account status: active/disabled, locked/unlocked, password expired, must-change-password flag, and MFA registration.',
        'If the account is locked, review failed sign-in attempts before unlocking.',
        'If admin reset is required, use the approved admin reset process and require password change at next sign-in.',
        'Ask the user to test sign-in from a private/incognito browser window.',
        'Confirm the user updates saved passwords on mobile email, VPN, browser password manager, mapped drives, remote desktop, and Wi-Fi if applicable.',
        'Check whether the reset synchronized to all required systems.',
        'Escalate if MFA, conditional access, disabled account, identity provider errors, or suspected compromise are involved.',
    ],
}

PASSWORD_RESET_REQUEST_SOLUTIONS = [
    ('FIX_USE_PASSWORD_RESET_PORTAL','Use the Password Reset Portal','User forgot their password and should use the approved self-service reset process.','Go to the company-approved password reset portal. Enter the company username or email address. Complete identity verification. Create a new password that meets requirements. Wait a few minutes, then try signing in again. Update saved passwords on devices and apps.',0,'Escalate if the reset portal is unavailable, recovery methods are outdated, or reset fails after verification.','medium'),
    ('FIX_RESET_EXPIRED_PASSWORD','Reset Expired Password','The user password expired and must be changed before sign-in can continue.','Follow the expired-password prompt. Enter the old password if requested. Create a compliant new password. Sign out and sign back in. Update saved credentials on other devices and apps.',0,'Escalate if the user cannot complete the expired-password flow or policy blocks the reset.','medium'),
    ('FIX_PASSWORD_RESET_RECOVERY_METHOD','Check Recovery Method or MFA Prompt','The user cannot complete password reset because the reset code, email, or MFA prompt is unavailable.','Check spam/junk folders, phone signal, authenticator prompts, and recovery email/phone. Try private/incognito mode. Do not approve unexpected MFA prompts. Contact IT if recovery methods are outdated or inaccessible.',1,'Escalate to Identity/Access Management if recovery method changes require approval or identity verification beyond help desk scope.','medium'),
    ('FIX_UNLOCK_ACCOUNT_REVIEW_ATTEMPTS','Unlock Account and Review Failed Attempts','The user may be locked out after repeated failed sign-in attempts.','Stop repeated password attempts. Verify identity. Review failed login source if available. Unlock the account if activity appears legitimate. Have the user sign in once and update saved passwords on all devices.',1,'Escalate to Security if failed attempts are suspicious or come from unknown locations.','medium'),
    ('FIX_ADMIN_PASSWORD_RESET','Complete Admin Password Reset','IT must reset the password because self-service reset is unavailable or unsuccessful.','Verify identity. Reset the password using the approved admin console. Require password change at next sign-in. Avoid insecure password sharing. Confirm successful sign-in and document the reset.',0,'Escalate if policy requires higher approval or if the account appears compromised.','medium'),
    ('FIX_ESCALATE_IDENTITY_SYNC_POLICY','Escalate Identity Sync or Policy Issue','Password reset completed but sign-in still fails due to sync, policy, or system-specific access issue.','Confirm reset succeeded in the identity provider. Identify whether one app or all apps fail. Check directory sync, password writeback, conditional access, licensing, and group membership. Capture errors and escalate.',1,'Escalate to Identity/Access Management when sync, writeback, conditional access, licensing, or app-specific identity issues are suspected.','high'),
    ('FIX_VERIFY_IDENTITY_BEFORE_RESET','Verify Identity Before Reset','Support must verify the user identity before performing account changes.','Do not reset the password until the user identity is verified using approved support policy. If identity cannot be verified, escalate or follow the exception process.',1,'Never reset a password for an unverified requester. Escalate exceptions to a manager or Identity/Access Management.','high'),
    ('FIX_ESCALATE_DISABLED_ACCOUNT','Escalate Disabled or Deprovisioned Account','The account is disabled, expired, or not fully provisioned and cannot be handled as a simple password reset.','Confirm the account state and collect user, manager, department, and business justification. Escalate to Identity/Access Management or HR/onboarding workflow as appropriate.',1,'Do not re-enable disabled or deprovisioned accounts without approval.','high'),
    ('FIX_ESCALATE_MFA_RECOVERY','Escalate MFA Recovery','MFA is preventing the reset and recovery methods may need to be updated or re-registered.','Verify identity, confirm registered MFA methods, determine whether the user still has access to them, and follow the approved MFA recovery process.',1,'Escalate if MFA reset requires identity governance approval or suspicious activity is present.','high'),
]

PASSWORD_RESET_SOLUTION_STEPS = {
    'FIX_USE_PASSWORD_RESET_PORTAL': {
        'user': ['Open the company-approved password reset portal.', 'Enter your company username or email address.', 'Complete identity verification.', 'Create a new password that meets the listed requirements.', 'Wait a few minutes and try signing in again.', 'Update saved passwords on mobile, email, VPN, and browser password managers.'],
        'technician': ['Confirm the user is using the correct reset portal.', 'Confirm the recovery email, phone, or MFA method is available.', 'Ask the user to retry in private/incognito mode.', 'Check identity logs if reset fails.', 'Escalate if the portal is unavailable or recovery methods are outdated.'],
        'admin': ['Verify self-service password reset availability and policy assignment.', 'Check identity provider health if multiple users report failures.', 'Escalate recovery method issues according to access policy.'],
    },
    'FIX_RESET_EXPIRED_PASSWORD': {
        'user': ['Follow the expired-password prompt on the sign-in page.', 'Enter your old password if requested.', 'Create a new password that meets requirements.', 'Sign out and sign back in with the new password.', 'Update saved passwords on other devices and apps.'],
        'technician': ['Confirm password expiration status.', 'Confirm whether the user can change the password through normal sign-in.', 'If needed, force password change at next login.', 'Confirm the user successfully signs in after the change.', 'Check stale credentials if lockouts continue.'],
        'admin': ['Review password policy if expiration/reset behavior is unexpected.', 'Check for repeated lockouts caused by stale credentials.'],
    },
    'FIX_PASSWORD_RESET_RECOVERY_METHOD': {
        'user': ['Check spam or junk folders for the reset email.', 'Confirm your phone can receive SMS or authenticator prompts.', 'Try again from a private/incognito browser window.', 'Do not approve unexpected MFA prompts.', 'Contact IT if your recovery phone/email is outdated or inaccessible.'],
        'technician': ['Verify user identity.', 'Check registered MFA/recovery methods.', 'Confirm whether the user still has access to the registered method.', 'Follow approved process to reset or update recovery information.', 'Escalate if recovery changes require approval.'],
        'admin': ['Approve recovery method changes only after identity verification.', 'Route high-risk recovery changes to Identity/Access Management.'],
    },
    'FIX_UNLOCK_ACCOUNT_REVIEW_ATTEMPTS': {
        'user': ['Stop retrying the password repeatedly.', 'Wait for IT confirmation that the account has been unlocked.', 'After unlock, sign in once using the correct password.', 'Update saved passwords on phones, email apps, VPN, and browser password managers.'],
        'technician': ['Verify user identity.', 'Check account lockout status.', 'Review failed login source if available.', 'Unlock the account if activity appears legitimate.', 'Ask the user to update saved passwords on all devices.', 'Escalate to Security if failed attempts look suspicious.'],
        'admin': ['Review repeated lockouts for stale credentials or suspicious activity.', 'Escalate suspicious lockout patterns to Security.'],
    },
    'FIX_ADMIN_PASSWORD_RESET': {
        'user': ['Confirm your identity with IT.', 'Use the temporary password only through the approved sign-in page.', 'Create a new password when prompted.', 'Do not share the temporary or new password with anyone.', 'Update saved credentials on all devices.'],
        'technician': ['Verify identity according to company policy.', 'Reset the password using the approved admin console.', 'Require password change at next sign-in.', 'Avoid sending passwords through insecure channels.', 'Confirm successful sign-in.', 'Document the reset in the support ticket.'],
        'admin': ['Confirm the reset follows policy.', 'Audit password resets when elevated or exception handling is used.'],
    },
    'FIX_ESCALATE_IDENTITY_SYNC_POLICY': {
        'user': ['Record the exact error message.', 'Note which systems work and which systems do not.', 'Avoid repeated login attempts until IT confirms next steps.'],
        'technician': ['Confirm password reset succeeded in the identity provider.', 'Check whether the issue affects one app or all apps.', 'Check directory sync, password writeback, conditional access, and licensing/group membership.', 'Capture error messages and timestamps.', 'Escalate to Identity/Access Management.'],
        'admin': ['Prioritize if the user is blocked from critical work or if multiple users are affected.', 'Coordinate with Identity/Access Management for sync or policy failures.'],
    },
    'FIX_VERIFY_IDENTITY_BEFORE_RESET': {
        'user': ['Provide the identity verification information requested by IT.', 'Do not share your password with anyone.', 'Wait for IT to confirm the approved reset path.'],
        'technician': ['Follow the approved identity verification process.', 'Do not reset the password if identity cannot be verified.', 'Document the verification result in the ticket.', 'Escalate exceptions to a manager or Identity/Access Management.'],
        'admin': ['Review exceptions where user identity cannot be verified.', 'Do not approve reset bypasses without documented justification.'],
    },
    'FIX_ESCALATE_DISABLED_ACCOUNT': {
        'user': ['Confirm your manager, department, and business need if requested.', 'Wait for IT or your manager to confirm access status.'],
        'technician': ['Confirm whether the account is disabled, expired, or not fully provisioned.', 'Collect user, manager, department, and business justification.', 'Escalate to Identity/Access Management or onboarding/offboarding workflow.', 'Do not re-enable the account without approval.'],
        'admin': ['Validate employment/access status before re-enabling accounts.', 'Coordinate with HR/onboarding/offboarding where needed.'],
    },
    'FIX_ESCALATE_MFA_RECOVERY': {
        'user': ['Tell IT whether you still have access to your registered MFA device.', 'Do not approve unexpected prompts.', 'Follow the approved recovery process for MFA re-registration.'],
        'technician': ['Verify user identity.', 'Review registered MFA methods.', 'Check whether MFA prompts are being delivered.', 'Follow approved MFA reset/re-registration workflow.', 'Escalate suspicious MFA activity to Security.'],
        'admin': ['Approve MFA recovery only after identity verification.', 'Escalate high-risk MFA resets to Identity/Access Management or Security.'],
    },
}

PASSWORD_RESET_USER_DIAGNOSTIC_NODES = [
    ('ROOT_PASSWORD_RESET_USER',None,'category','Password Reset Request - User Diagnostic','User-friendly path for forgotten, expired, or failed password reset issues.',None,None,None,None,1),
    ('Q_REMEMBER_PASSWORD_USER','ROOT_PASSWORD_RESET_USER','question','Check Whether Password Is Known','Determine whether the user needs self-service reset or another sign-in path.','Do you remember your current password?',None,None,None,1),
    ('S_USE_RESET_PORTAL_USER','Q_REMEMBER_PASSWORD_USER','solution','Use the Password Reset Portal',None,None,'Do you remember your current password?','No','FIX_USE_PASSWORD_RESET_PORTAL',1),
    ('Q_EXPIRED_MESSAGE_USER','Q_REMEMBER_PASSWORD_USER','question','Check for Expired Password Message','Expired passwords usually follow a different reset path.','Are you seeing a message that your password expired?','Do you remember your current password?','Yes',None,2),
    ('S_RESET_EXPIRED_USER','Q_EXPIRED_MESSAGE_USER','solution','Reset Expired Password',None,None,'Are you seeing a message that your password expired?','Yes','FIX_RESET_EXPIRED_PASSWORD',1),
    ('Q_PORTAL_ACCESS_USER','Q_EXPIRED_MESSAGE_USER','question','Check Password Reset Portal Access','Confirm whether the user can reach the self-service reset portal.','Can you access the company password reset portal?','Are you seeing a message that your password expired?','No',None,2),
    ('S_ADMIN_RESET_USER','Q_PORTAL_ACCESS_USER','solution','Submit Ticket for Password Reset Help',None,None,'Can you access the company password reset portal?','No','FIX_ADMIN_PASSWORD_RESET',1),
    ('Q_RECEIVE_CODE_USER','Q_PORTAL_ACCESS_USER','question','Check Reset Code or MFA Prompt','The reset may fail if recovery methods are outdated or unavailable.','Did you receive the reset code, email, or MFA prompt?','Can you access the company password reset portal?','Yes',None,2),
    ('S_RECOVERY_METHOD_USER','Q_RECEIVE_CODE_USER','solution','Check Recovery Method or MFA Prompt',None,None,'Did you receive the reset code, email, or MFA prompt?','No','FIX_PASSWORD_RESET_RECOVERY_METHOD',1),
    ('Q_RESET_COMPLETE_USER','Q_RECEIVE_CODE_USER','question','Check Whether Reset Completed','Confirm whether the reset process finished successfully.','Did the password reset complete successfully?','Did you receive the reset code, email, or MFA prompt?','Yes',None,2),
    ('S_UPDATE_SAVED_PASSWORDS_USER','Q_RESET_COMPLETE_USER','solution','Use the New Password and Update Saved Passwords',None,None,'Did the password reset complete successfully?','Yes','FIX_USE_PASSWORD_RESET_PORTAL',1),
    ('S_FAILED_RESET_USER','Q_RESET_COMPLETE_USER','solution','Submit Ticket for Failed Password Reset',None,None,'Did the password reset complete successfully?','No','FIX_ESCALATE_IDENTITY_SYNC_POLICY',2),
]

PASSWORD_RESET_TECH_DIAGNOSTIC_NODES = [
    ('ROOT_PASSWORD_RESET_TECH',None,'category','Password Reset Request - IT Support Specialist Diagnostic','IT Support Specialist path for identity verification, account status, MFA, lockout, and sync/policy issues.',None,None,None,None,1),
    ('Q_IDENTITY_VERIFIED_TECH','ROOT_PASSWORD_RESET_TECH','question','Verify User Identity','Password resets must start with identity verification.','Has the user identity been verified according to policy?',None,None,None,1),
    ('S_VERIFY_IDENTITY_TECH','Q_IDENTITY_VERIFIED_TECH','solution','Verify Identity Before Reset',None,None,'Has the user identity been verified according to policy?','No','FIX_VERIFY_IDENTITY_BEFORE_RESET',1),
    ('Q_ACCOUNT_ACTIVE_TECH','Q_IDENTITY_VERIFIED_TECH','question','Check Account State','Confirm whether this is a valid active account.','Is the account active and enabled?','Has the user identity been verified according to policy?','Yes',None,2),
    ('S_DISABLED_ACCOUNT_TECH','Q_ACCOUNT_ACTIVE_TECH','solution','Escalate Disabled or Deprovisioned Account',None,None,'Is the account active and enabled?','No','FIX_ESCALATE_DISABLED_ACCOUNT',1),
    ('Q_ACCOUNT_LOCKED_TECH','Q_ACCOUNT_ACTIVE_TECH','question','Check Lockout State','Repeated failed attempts may lock the account.','Is the account locked?','Is the account active and enabled?','Yes',None,2),
    ('S_UNLOCK_REVIEW_TECH','Q_ACCOUNT_LOCKED_TECH','solution','Unlock Account and Review Failed Attempts',None,None,'Is the account locked?','Yes','FIX_UNLOCK_ACCOUNT_REVIEW_ATTEMPTS',1),
    ('Q_PASSWORD_EXPIRED_TECH','Q_ACCOUNT_LOCKED_TECH','question','Check Password Expiration or Reset Flag','Expired passwords and forced reset flags have a standard path.','Is the password expired or marked for reset?','Is the account locked?','No',None,2),
    ('S_RESET_EXPIRED_TECH','Q_PASSWORD_EXPIRED_TECH','solution','Reset Expired Password',None,None,'Is the password expired or marked for reset?','Yes','FIX_RESET_EXPIRED_PASSWORD',1),
    ('Q_MFA_BLOCKING_TECH','Q_PASSWORD_EXPIRED_TECH','question','Check MFA or Recovery Block','MFA may prevent self-service reset completion.','Is MFA or an unavailable recovery method blocking the reset?','Is the password expired or marked for reset?','No',None,2),
    ('S_MFA_RECOVERY_TECH','Q_MFA_BLOCKING_TECH','solution','Escalate MFA Recovery',None,None,'Is MFA or an unavailable recovery method blocking the reset?','Yes','FIX_ESCALATE_MFA_RECOVERY',1),
    ('Q_RESET_FAILS_TECH','Q_MFA_BLOCKING_TECH','question','Check Sync or Policy Failure','If normal reset does not work, check sync, writeback, and conditional access.','Does sign-in still fail after password reset or admin action?','Is MFA or an unavailable recovery method blocking the reset?','No',None,2),
    ('S_SYNC_POLICY_TECH','Q_RESET_FAILS_TECH','solution','Escalate Identity Sync or Policy Issue',None,None,'Does sign-in still fail after password reset or admin action?','Yes','FIX_ESCALATE_IDENTITY_SYNC_POLICY',1),
    ('S_ADMIN_RESET_TECH','Q_RESET_FAILS_TECH','solution','Complete Admin Password Reset',None,None,'Does sign-in still fail after password reset or admin action?','No','FIX_ADMIN_PASSWORD_RESET',2),
]

def seed_password_reset_request_content(cursor):
    """Seed Password Reset Request KB article, solutions, role-specific steps, and diagnostic trees."""
    code_, title, category, severity, description = PASSWORD_RESET_REQUEST_PROBLEM
    cursor.execute("""
        INSERT INTO problem (problem_code, title, category, severity, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(problem_code) DO UPDATE SET
            title=excluded.title, category=excluded.category, severity=excluded.severity,
            description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, PASSWORD_RESET_REQUEST_PROBLEM)
    cursor.execute('SELECT problem_id FROM problem WHERE problem_code = ?', (code_,))
    row = cursor.fetchone()
    if not row:
        return
    problem_id = row['problem_id']
    cursor.execute("""
        INSERT INTO kb_article (problem_id, title, summary, difficulty, estimated_time, escalation_required, escalation_notes, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, difficulty=excluded.difficulty,
            estimated_time=excluded.estimated_time, escalation_required=excluded.escalation_required,
            escalation_notes=excluded.escalation_notes, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, PASSWORD_RESET_REQUEST_KB['title'], PASSWORD_RESET_REQUEST_KB['summary'], PASSWORD_RESET_REQUEST_KB['difficulty'], PASSWORD_RESET_REQUEST_KB['estimated_time'], PASSWORD_RESET_REQUEST_KB['escalation_required'], PASSWORD_RESET_REQUEST_KB['escalation_notes']))
    cursor.execute('SELECT kb_article_id FROM kb_article WHERE problem_id = ?', (problem_id,))
    article = cursor.fetchone()
    if article:
        kb_id = article['kb_article_id']
        delete_kb_child_rows(cursor, kb_id)
        insert_kb_child_rows(cursor, 'kb_article_tag', 'tag', kb_id, PASSWORD_RESET_REQUEST_KB['tags'])
        insert_kb_child_rows(cursor, 'kb_article_symptom', 'symptom', kb_id, PASSWORD_RESET_REQUEST_KB['symptoms'])
        insert_kb_child_rows(cursor, 'kb_article_cause', 'cause', kb_id, PASSWORD_RESET_REQUEST_KB['causes'])
        insert_kb_child_rows(cursor, 'kb_article_user_step', 'step_text', kb_id, PASSWORD_RESET_REQUEST_KB['user_steps'])
        insert_kb_child_rows(cursor, 'kb_article_it_step', 'step_text', kb_id, PASSWORD_RESET_REQUEST_KB['it_steps'])
    cursor.executemany("""
        INSERT INTO solution (solution_code, title, summary, resolution_steps, escalation_required, escalation_notes, priority_recommendation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(solution_code) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, resolution_steps=excluded.resolution_steps,
            escalation_required=excluded.escalation_required, escalation_notes=excluded.escalation_notes,
            priority_recommendation=excluded.priority_recommendation, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, PASSWORD_RESET_REQUEST_SOLUTIONS)
    for solution_code, audience_steps in PASSWORD_RESET_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue
        for audience, steps in audience_steps.items():
            cursor.execute('DELETE FROM solution_step WHERE solution_id = ? AND audience = ?', (solution_id, audience))
            cursor.executemany('INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)', [(solution_id, audience, step, idx) for idx, step in enumerate(steps, start=1)])
    seed_password_reset_tree(cursor, 'user', 'PASSWORD_RESET_REQUEST_USER', 'Password Reset Request - User Diagnostic', 'User-friendly diagnostic tree for password reset requests.', PASSWORD_RESET_USER_DIAGNOSTIC_NODES)
    seed_password_reset_tree(cursor, 'technician', 'PASSWORD_RESET_REQUEST_TECHNICIAN', 'Password Reset Request - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for password reset root-cause analysis.', PASSWORD_RESET_TECH_DIAGNOSTIC_NODES)

def seed_password_reset_tree(cursor, audience, tree_code, title, description, nodes):
    problem_id = get_problem_id_for_tree_code(cursor, 'PASSWORD_RESET_REQUEST')
    cursor.execute("""
        INSERT INTO diagnostic_tree (problem_id, diagnostic_tree_code, base_tree_code, audience, title, description, is_active, updated_at)
        VALUES (?, ?, 'PASSWORD_RESET_REQUEST', ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(diagnostic_tree_code) DO UPDATE SET
            problem_id=excluded.problem_id, base_tree_code=excluded.base_tree_code, audience=excluded.audience,
            title=excluded.title, description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, tree_code, audience, title, description))
    tree_id = get_diagnostic_tree_id_by_code(cursor, tree_code)
    if not tree_id:
        return
    # Do not delete/recreate diagnostic nodes here. Existing troubleshooting
    # sessions/events may reference diagnostic_node rows, so deleting them can
    # fail with FOREIGN KEY constraint errors and would also break audit history.
    # Instead, mark the existing tree inactive, then upsert the current seed
    # nodes back to active. This preserves stable node IDs across app restarts.
    cursor.execute('UPDATE diagnostic_node SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE diagnostic_tree_id = ?', (tree_id,))
    for node_key, parent_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_code, sort_order in nodes:
        parent_id = get_diagnostic_node_id_by_tree_and_key(cursor, tree_id, parent_key) if parent_key else None
        solution_id = get_solution_id_by_code(cursor, solution_code) if solution_code else None
        cursor.execute("""
            INSERT INTO diagnostic_node (
                diagnostic_tree_id, parent_diagnostic_node_id, problem_id, diagnostic_tree_code,
                node_key, node_type, title, description, prompt_text,
                condition_label, condition_value, solution_id, sort_order, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(diagnostic_tree_code, node_key) DO UPDATE SET
                diagnostic_tree_id=excluded.diagnostic_tree_id,
                parent_diagnostic_node_id=excluded.parent_diagnostic_node_id,
                problem_id=excluded.problem_id,
                node_type=excluded.node_type,
                title=excluded.title,
                description=excluded.description,
                prompt_text=excluded.prompt_text,
                condition_label=excluded.condition_label,
                condition_value=excluded.condition_value,
                solution_id=excluded.solution_id,
                sort_order=excluded.sort_order,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (tree_id, parent_id, problem_id, tree_code, node_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_id, sort_order))


# -----------------------------
# ACCOUNT LOCKED RELATIONAL SEED DATA
# -----------------------------
ACCOUNT_LOCKED_PROBLEM = (
    'ACCOUNT_LOCKED',
    'Account Locked',
    'Account & Access',
    'medium',
    'User cannot sign in because their account is temporarily locked after repeated failed sign-in attempts or suspicious activity.',
)

ACCOUNT_LOCKED_KB = {
    'title': 'Account Locked',
    'summary': 'Use this guide when an account is locked after too many failed sign-in attempts, saved old credentials, or possible suspicious activity.',
    'difficulty': 'Beginner',
    'estimated_time': '5-15 minutes',
    'escalation_required': 0,
    'escalation_notes': 'Escalate if failed attempts are suspicious, the account repeatedly locks after unlock, multiple users are affected, unexpected MFA prompts occur, or the lockout source cannot be identified.',
    'tags': ['account locked', 'lockout', 'failed login', 'sign-in', 'password', 'saved password', 'credentials', 'MFA', 'security'],
    'symptoms': [
        'Account locked or too many failed attempts message appears',
        'User cannot sign in even though they know the password',
        'User recently changed password and is now locked out',
        'Email, phone, VPN, or browser keeps prompting for credentials',
        'Account locks again shortly after IT unlocks it',
        'VPN or remote access reports authentication failed',
        'Unexpected MFA prompts or security alerts appear',
    ],
    'causes': [
        'Common: repeated wrong password attempts, recently changed password still saved on phone/email/VPN/browser, mapped drive using old credentials, wrong username/domain, Caps Lock or keyboard layout issue, or temporary security policy lockout.',
        'Advanced: scheduled task or service using old credentials, cached Windows credentials, remote desktop saved credentials, legacy authentication client, directory sync delay, password spray/brute-force attempt, risk-based sign-in policy, or shared workstation with stale credentials.',
    ],
    'user_steps': [
        'Stop retrying the password repeatedly.',
        'Confirm you are using the correct company username or email address.',
        'Check that Caps Lock is off and the keyboard layout is correct.',
        'If you recently changed your password, update it on mobile email, VPN, browser password manager, mapped drives, and remote desktop connections.',
        'Turn off or disconnect old phones, tablets, or laptops temporarily if they may still have the old password saved.',
        'Try signing in from a private/incognito browser window after IT confirms the account is unlocked.',
        'If the lockout happens again, tell IT which device or app you were using when it happened.',
        'Do not approve unexpected MFA prompts; report them to IT immediately.',
    ],
    'it_steps': [
        'Verify the user identity according to support policy before unlocking the account.',
        'Confirm the exact username/email and system the user is trying to access.',
        'Confirm whether the account is actually locked or whether the issue is password, MFA, disabled account, or access denial.',
        'Review failed sign-in logs for timestamps, source IP/location, device, application/client, and failure reason.',
        'Ask whether the user recently changed or reset their password.',
        'Check likely stale-credential sources: mobile email, VPN, mapped network drives, browser password manager, remote desktop, old laptops/tablets, and cached Windows credentials.',
        'If attempts appear legitimate, unlock the account and have the user update saved credentials before retrying.',
        'If lockout recurs, identify the source of repeated failed attempts using identity, VPN, email, domain controller, or application logs.',
        'Escalate to Security if attempts are suspicious, from unknown locations, or resemble brute-force/password spray activity.',
        'Escalate to Identity/Access Management if the lockout source cannot be identified or identity policy/sync issues are suspected.',
    ],
}

ACCOUNT_LOCKED_SOLUTIONS = [
    ('FIX_ACCOUNT_LOCKED_CHECK_ERROR_TYPE','Check Sign-In Error Type','The user may not be locked out; the issue may be password, MFA, disabled account, or application access.','Read the exact sign-in error. Confirm whether it says locked, disabled, password expired, MFA required, or access denied. Capture a screenshot if possible. Check account status and route to the correct process.',0,'Escalate if the error suggests disabled account, policy block, or suspicious sign-in activity.','medium'),
    ('FIX_UPDATE_SAVED_PASSWORDS_AFTER_CHANGE','Update Saved Passwords on Devices','Old saved credentials may keep retrying and locking the account after a password change.','Update or remove old passwords from phone, email apps, VPN, browser password manager, mapped drives, remote desktop, and cached credentials. Restart affected apps and retry after unlock.',0,'Escalate if the repeated failed-attempt source cannot be identified.','medium'),
    ('FIX_FIND_OLD_CREDENTIAL_SOURCE','Find Device or App Using Old Credentials','A device, app, service, or saved connection is repeatedly using an old password.','Review lockout timestamps and sign-in logs. Check mobile email, VPN, mapped drives, RDP, scheduled tasks, saved Windows credentials, and old devices. Clear or update stored credentials.',1,'Escalate to Identity/Access Management if the source cannot be identified.','medium'),
    ('FIX_UNLOCK_ACCOUNT_MONITOR','Unlock Account and Monitor','The account appears safely locked due to normal failed attempts and can be unlocked after identity verification.','Verify identity. Confirm failed attempts appear legitimate. Unlock the account. Ask the user to sign in once with the correct password and monitor whether the lockout returns.',0,'Escalate if lockout recurs or failed attempts look suspicious.','medium'),
    ('FIX_ESCALATE_POSSIBLE_ACCOUNT_ATTACK','Escalate Possible Account Attack','Suspicious failed attempts or unexpected MFA prompts may indicate an attempted account attack.','Do not repeatedly unlock without review. Capture failed sign-in timestamps, source IPs, locations, user agent, and MFA events. Check whether other users are affected and escalate to Security.',1,'Escalate immediately to Security when compromise, password spray, brute force, or unexpected MFA prompts are suspected.','high'),
    ('FIX_VERIFY_IDENTITY_BEFORE_UNLOCK','Verify Identity Before Unlock','IT must verify the user before unlocking an account or changing authentication settings.','Use the approved support identity-verification process. Do not disclose account details or unlock until verification passes. Escalate if identity cannot be verified.',0,'Follow company policy for identity verification and do not share passwords.','medium'),
    ('FIX_INVESTIGATE_RECURRING_LOCKOUT_SOURCE','Investigate Recurring Lockout Source','The account keeps locking after unlock, so the repeated failed-attempt source must be identified.','Compare lockout timestamps to device activity. Review domain controller, identity provider, VPN, email, and application logs. Identify and clear the stale credential source.',1,'Escalate if source cannot be identified or suspicious sign-in patterns are present.','high'),
]

ACCOUNT_LOCKED_SOLUTION_STEPS = {
    'FIX_ACCOUNT_LOCKED_CHECK_ERROR_TYPE': {
        'user': ['Read the exact sign-in error message.', 'Check whether the message says locked, disabled, password expired, MFA required, or access denied.', 'Take a screenshot if possible.', 'Submit a ticket with the exact message if you are unsure.'],
        'technician': ['Confirm the exact error message and affected system.', 'Check account status in the identity provider.', 'Route to password reset, MFA, access request, or disabled account process if the account is not locked.'],
        'admin': ['Review whether the issue is a true account lockout or another access-control state.', 'Escalate if policy, licensing, or disabled-account handling is required.'],
    },
    'FIX_UPDATE_SAVED_PASSWORDS_AFTER_CHANGE': {
        'user': ['Update the saved password on phone, tablet, email app, VPN, and browser password manager.', 'Remove old saved passwords if you are unsure which one is being used.', 'Restart affected apps after updating the password.', 'Try signing in again after IT unlocks the account.'],
        'technician': ['Ask which devices and apps are configured with company credentials.', 'Check failed sign-in logs for client or application hints.', 'Help remove old credentials from Credential Manager, browser, VPN, or email profile.', 'Unlock the account after old credentials are corrected.'],
        'admin': ['Confirm lockouts are caused by stale credentials before repeated unlocks.', 'Escalate recurring lockouts if the source is not obvious.'],
    },
    'FIX_FIND_OLD_CREDENTIAL_SOURCE': {
        'user': ['Think about devices where your old password may still be saved.', 'Turn off or disconnect old phones, tablets, or laptops temporarily.', 'Update passwords in email, VPN, remote desktop, mapped drives, and browsers.', 'Tell IT if lockouts happen only when a specific device is online.'],
        'technician': ['Review lockout logs for source workstation, IP, app, or protocol.', 'Check mobile email, VPN, mapped drives, RDP, scheduled tasks, and saved Windows credentials.', 'Clear cached credentials where appropriate.', 'If the source is unknown, escalate to Identity/Access Management.'],
        'admin': ['Review recurring lockout evidence and authorize deeper identity-log investigation if needed.'],
    },
    'FIX_UNLOCK_ACCOUNT_MONITOR': {
        'user': ['Wait for IT to confirm the account is unlocked.', 'Sign in one time using the correct password.', 'Avoid repeated attempts if sign-in fails.', 'Report immediately if the account locks again.'],
        'technician': ['Verify user identity.', 'Confirm failed attempts appear legitimate.', 'Unlock the account.', 'Monitor whether lockout recurs.', 'Document the action in the support ticket.'],
        'admin': ['Confirm unlock was appropriate and evidence does not suggest suspicious activity.'],
    },
    'FIX_ESCALATE_POSSIBLE_ACCOUNT_ATTACK': {
        'user': ['Do not approve unexpected MFA prompts.', 'Stop retrying sign-in.', 'Report unfamiliar locations, devices, emails, or security alerts.', 'Wait for IT or Security instructions.'],
        'technician': ['Do not unlock repeatedly without reviewing sign-in logs.', 'Capture failed sign-in timestamps, source IPs, locations, user agent, and MFA events.', 'Check whether other accounts are affected.', 'Escalate to Security.', 'Follow incident response guidance if compromise is suspected.'],
        'admin': ['Treat as security-sensitive until reviewed.', 'Prioritize as High when suspicious activity, password spray, or unexpected MFA prompts are present.'],
    },
    'FIX_VERIFY_IDENTITY_BEFORE_UNLOCK': {
        'user': ['Be ready to verify your identity using the approved support process.', 'Do not share your password with IT.', 'Use only official support channels.'],
        'technician': ['Verify identity according to policy.', 'Do not disclose account details before verification.', 'Continue with unlock only after verification passes.', 'Escalate if identity cannot be verified.'],
        'admin': ['Ensure the unlock process follows identity-verification policy.', 'Review exceptions or failed verification attempts.'],
    },
    'FIX_INVESTIGATE_RECURRING_LOCKOUT_SOURCE': {
        'user': ['Tell IT when the lockout happens again.', 'Note which device or app you were using at that moment.', 'Disconnect old devices if instructed.', 'Avoid repeated sign-in attempts.'],
        'technician': ['Compare lockout timestamps to user device activity.', 'Review domain controller, identity provider, VPN, email, and application logs.', 'Identify the source device, app, or protocol.', 'Remove or update stored credentials.', 'Escalate if the source cannot be identified.'],
        'admin': ['Escalate to Identity/Access Management for unresolved recurring lockouts.', 'Escalate to Security if patterns suggest attack or compromise.'],
    },
}

ACCOUNT_LOCKED_USER_DIAGNOSTIC_NODES = [
    ('ROOT_ACCOUNT_LOCKED_USER',None,'category','Account Locked - User Diagnostic','User-friendly path for account lockout, saved password, and suspicious prompt scenarios.',None,None,None,None,1),
    ('Q_LOCKED_MESSAGE_USER','ROOT_ACCOUNT_LOCKED_USER','question','Confirm Lockout Message','Check whether this is a true account lockout.','Do you see an account locked or too many attempts message?',None,None,None,1),
    ('S_CHECK_ERROR_TYPE_USER','Q_LOCKED_MESSAGE_USER','solution','Check Sign-In Error Type',None,None,'Do you see an account locked or too many attempts message?','No','FIX_ACCOUNT_LOCKED_CHECK_ERROR_TYPE',1),
    ('Q_RECENT_PASSWORD_CHANGE_USER','Q_LOCKED_MESSAGE_USER','question','Check Recent Password Change','Recent password changes often cause stale credentials on devices.','Did you recently change or reset your password?','Do you see an account locked or too many attempts message?','Yes',None,2),
    ('S_UPDATE_SAVED_PASSWORDS_USER','Q_RECENT_PASSWORD_CHANGE_USER','solution','Update Saved Passwords on Devices',None,None,'Did you recently change or reset your password?','Yes','FIX_UPDATE_SAVED_PASSWORDS_AFTER_CHANGE',1),
    ('Q_UNEXPECTED_MFA_USER','Q_RECENT_PASSWORD_CHANGE_USER','question','Check Security Prompts','Unexpected MFA prompts may indicate suspicious sign-in activity.','Are you receiving unexpected MFA prompts or security alerts?','Did you recently change or reset your password?','No',None,2),
    ('S_ESCALATE_ATTACK_USER','Q_UNEXPECTED_MFA_USER','solution','Report Possible Suspicious Sign-In',None,None,'Are you receiving unexpected MFA prompts or security alerts?','Yes','FIX_ESCALATE_POSSIBLE_ACCOUNT_ATTACK',1),
    ('Q_RELOCKS_USER','Q_UNEXPECTED_MFA_USER','question','Check Repeated Lockout','Recurring lockouts usually mean an old credential is still being used.','Does the account lock again shortly after being unlocked?','Are you receiving unexpected MFA prompts or security alerts?','No',None,2),
    ('S_FIND_OLD_CREDS_USER','Q_RELOCKS_USER','solution','Find Device or App Using Old Credentials',None,None,'Does the account lock again shortly after being unlocked?','Yes','FIX_FIND_OLD_CREDENTIAL_SOURCE',1),
    ('S_UNLOCK_MONITOR_USER','Q_RELOCKS_USER','solution','Wait or Contact IT to Unlock Account',None,None,'Does the account lock again shortly after being unlocked?','No','FIX_UNLOCK_ACCOUNT_MONITOR',2),
]

ACCOUNT_LOCKED_TECH_DIAGNOSTIC_NODES = [
    ('ROOT_ACCOUNT_LOCKED_TECH',None,'category','Account Locked - IT Support Specialist Diagnostic','IT Support Specialist path for identity verification, lockout validation, stale credentials, and security escalation.',None,None,None,None,1),
    ('Q_IDENTITY_VERIFIED_UNLOCK_TECH','ROOT_ACCOUNT_LOCKED_TECH','question','Verify User Identity','Unlocking an account requires identity verification.','Has the user identity been verified according to policy?',None,None,None,1),
    ('S_VERIFY_IDENTITY_UNLOCK_TECH','Q_IDENTITY_VERIFIED_UNLOCK_TECH','solution','Verify Identity Before Unlock',None,None,'Has the user identity been verified according to policy?','No','FIX_VERIFY_IDENTITY_BEFORE_UNLOCK',1),
    ('Q_ACCOUNT_ACTUALLY_LOCKED_TECH','Q_IDENTITY_VERIFIED_UNLOCK_TECH','question','Confirm Account Lockout','Differentiate lockout from password, MFA, disabled account, or access denial.','Is the account locked in the identity system?','Has the user identity been verified according to policy?','Yes',None,2),
    ('S_CHECK_ERROR_TYPE_TECH','Q_ACCOUNT_ACTUALLY_LOCKED_TECH','solution','Check Password, MFA, or Disabled Account Instead',None,None,'Is the account locked in the identity system?','No','FIX_ACCOUNT_LOCKED_CHECK_ERROR_TYPE',1),
    ('Q_KNOWN_DEVICE_ATTEMPTS_TECH','Q_ACCOUNT_ACTUALLY_LOCKED_TECH','question','Review Failed Attempt Source','Known device/app attempts usually indicate stale credentials.','Do failed sign-in logs show repeated attempts from a known user device or app?','Is the account locked in the identity system?','Yes',None,2),
    ('S_CLEAR_SAVED_CREDS_TECH','Q_KNOWN_DEVICE_ATTEMPTS_TECH','solution','Clear Saved Credentials and Unlock Account',None,None,'Do failed sign-in logs show repeated attempts from a known user device or app?','Yes','FIX_UPDATE_SAVED_PASSWORDS_AFTER_CHANGE',1),
    ('Q_SUSPICIOUS_ATTEMPTS_TECH','Q_KNOWN_DEVICE_ATTEMPTS_TECH','question','Check Suspicious Attempts','Unknown sources may indicate attack or compromise.','Are failed attempts suspicious or from unknown locations?','Do failed sign-in logs show repeated attempts from a known user device or app?','No',None,2),
    ('S_ESCALATE_ATTACK_TECH','Q_SUSPICIOUS_ATTEMPTS_TECH','solution','Escalate Possible Account Attack',None,None,'Are failed attempts suspicious or from unknown locations?','Yes','FIX_ESCALATE_POSSIBLE_ACCOUNT_ATTACK',1),
    ('Q_RECURS_AFTER_UNLOCK_TECH','Q_SUSPICIOUS_ATTEMPTS_TECH','question','Check Recurrence','Recurring lockouts require source investigation.','Does lockout recur after unlock?','Are failed attempts suspicious or from unknown locations?','No',None,2),
    ('S_INVESTIGATE_RECURRING_TECH','Q_RECURS_AFTER_UNLOCK_TECH','solution','Investigate Recurring Lockout Source',None,None,'Does lockout recur after unlock?','Yes','FIX_INVESTIGATE_RECURRING_LOCKOUT_SOURCE',1),
    ('S_UNLOCK_MONITOR_TECH','Q_RECURS_AFTER_UNLOCK_TECH','solution','Unlock Account and Monitor',None,None,'Does lockout recur after unlock?','No','FIX_UNLOCK_ACCOUNT_MONITOR',2),
]

def seed_account_locked_content(cursor):
    """Seed Account Locked KB article, solutions, role-specific steps, and diagnostic trees."""
    code_, title, category, severity, description = ACCOUNT_LOCKED_PROBLEM
    cursor.execute("""
        INSERT INTO problem (problem_code, title, category, severity, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(problem_code) DO UPDATE SET
            title=excluded.title, category=excluded.category, severity=excluded.severity,
            description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, ACCOUNT_LOCKED_PROBLEM)
    cursor.execute('SELECT problem_id FROM problem WHERE problem_code = ?', (code_,))
    row = cursor.fetchone()
    if not row:
        return
    problem_id = row['problem_id']
    cursor.execute("""
        INSERT INTO kb_article (problem_id, title, summary, difficulty, estimated_time, escalation_required, escalation_notes, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, difficulty=excluded.difficulty,
            estimated_time=excluded.estimated_time, escalation_required=excluded.escalation_required,
            escalation_notes=excluded.escalation_notes, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, ACCOUNT_LOCKED_KB['title'], ACCOUNT_LOCKED_KB['summary'], ACCOUNT_LOCKED_KB['difficulty'], ACCOUNT_LOCKED_KB['estimated_time'], ACCOUNT_LOCKED_KB['escalation_required'], ACCOUNT_LOCKED_KB['escalation_notes']))
    cursor.execute('SELECT kb_article_id FROM kb_article WHERE problem_id = ?', (problem_id,))
    article = cursor.fetchone()
    if article:
        kb_id = article['kb_article_id']
        delete_kb_child_rows(cursor, kb_id)
        insert_kb_child_rows(cursor, 'kb_article_tag', 'tag', kb_id, ACCOUNT_LOCKED_KB['tags'])
        insert_kb_child_rows(cursor, 'kb_article_symptom', 'symptom', kb_id, ACCOUNT_LOCKED_KB['symptoms'])
        insert_kb_child_rows(cursor, 'kb_article_cause', 'cause', kb_id, ACCOUNT_LOCKED_KB['causes'])
        insert_kb_child_rows(cursor, 'kb_article_user_step', 'step_text', kb_id, ACCOUNT_LOCKED_KB['user_steps'])
        insert_kb_child_rows(cursor, 'kb_article_it_step', 'step_text', kb_id, ACCOUNT_LOCKED_KB['it_steps'])
    cursor.executemany("""
        INSERT INTO solution (solution_code, title, summary, resolution_steps, escalation_required, escalation_notes, priority_recommendation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(solution_code) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, resolution_steps=excluded.resolution_steps,
            escalation_required=excluded.escalation_required, escalation_notes=excluded.escalation_notes,
            priority_recommendation=excluded.priority_recommendation, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, ACCOUNT_LOCKED_SOLUTIONS)
    for solution_code, audience_steps in ACCOUNT_LOCKED_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue
        for audience, steps in audience_steps.items():
            cursor.execute('DELETE FROM solution_step WHERE solution_id = ? AND audience = ?', (solution_id, audience))
            cursor.executemany('INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)', [(solution_id, audience, step, idx) for idx, step in enumerate(steps, start=1)])
    seed_account_locked_tree(cursor, 'user', 'ACCOUNT_LOCKED_USER', 'Account Locked - User Diagnostic', 'User-friendly diagnostic tree for account lockouts.', ACCOUNT_LOCKED_USER_DIAGNOSTIC_NODES)
    seed_account_locked_tree(cursor, 'technician', 'ACCOUNT_LOCKED_TECHNICIAN', 'Account Locked - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for account lockouts and recurring failed sign-ins.', ACCOUNT_LOCKED_TECH_DIAGNOSTIC_NODES)

def seed_account_locked_tree(cursor, audience, tree_code, title, description, nodes):
    problem_id = get_problem_id_for_tree_code(cursor, 'ACCOUNT_LOCKED')
    cursor.execute("""
        INSERT INTO diagnostic_tree (problem_id, diagnostic_tree_code, base_tree_code, audience, title, description, is_active, updated_at)
        VALUES (?, ?, 'ACCOUNT_LOCKED', ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(diagnostic_tree_code) DO UPDATE SET
            problem_id=excluded.problem_id, base_tree_code=excluded.base_tree_code, audience=excluded.audience,
            title=excluded.title, description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, tree_code, audience, title, description))
    tree_id = get_diagnostic_tree_id_by_code(cursor, tree_code)
    if not tree_id:
        return
    cursor.execute('UPDATE diagnostic_node SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE diagnostic_tree_id = ?', (tree_id,))
    for node_key, parent_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_code, sort_order in nodes:
        parent_id = get_diagnostic_node_id_by_tree_and_key(cursor, tree_id, parent_key) if parent_key else None
        solution_id = get_solution_id_by_code(cursor, solution_code) if solution_code else None
        cursor.execute("""
            INSERT INTO diagnostic_node (
                diagnostic_tree_id, parent_diagnostic_node_id, problem_id, diagnostic_tree_code,
                node_key, node_type, title, description, prompt_text,
                condition_label, condition_value, solution_id, sort_order, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(diagnostic_tree_code, node_key) DO UPDATE SET
                diagnostic_tree_id=excluded.diagnostic_tree_id,
                parent_diagnostic_node_id=excluded.parent_diagnostic_node_id,
                problem_id=excluded.problem_id,
                node_type=excluded.node_type,
                title=excluded.title,
                description=excluded.description,
                prompt_text=excluded.prompt_text,
                condition_label=excluded.condition_label,
                condition_value=excluded.condition_value,
                solution_id=excluded.solution_id,
                sort_order=excluded.sort_order,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (tree_id, parent_id, problem_id, tree_code, node_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_id, sort_order))



# -----------------------------
# MULTI-FACTOR AUTHENTICATION ISSUE RELATIONAL SEED DATA
# -----------------------------
MFA_ISSUE_PROBLEM = (
    'MULTI_FACTOR_AUTHENTICATION_ISSUE',
    'Multi-factor Authentication Issue',
    'Account & Access',
    'medium',
    'User cannot complete sign-in because the MFA prompt, code, authenticator app, phone call, or text message is not working.',
)

MFA_ISSUE_KB = {
    'title': 'Multi-factor Authentication Issue',
    'summary': 'Use this guide when MFA prompts, verification codes, authenticator apps, phone calls, or text messages prevent sign-in.',
    'difficulty': 'Beginner',
    'estimated_time': '5-15 minutes',
    'escalation_required': 0,
    'escalation_notes': 'Escalate if the user changed or lost their MFA device, cannot access any registered method, receives unexpected MFA prompts, is blocked by conditional access/device compliance, or suspicious sign-in activity is present.',
    'tags': ['MFA', 'multi-factor authentication', 'authenticator app', 'verification code', 'push notification', 'SMS code', 'phone call', 'sign-in', 'security'],
    'symptoms': [
        'MFA prompt, push notification, text message, or phone call does not arrive.',
        'Authenticator app code is incorrect, expired, or not accepted.',
        'User changed phones, changed phone numbers, or reinstalled the authenticator app.',
        'User lost access to the registered MFA device or method.',
        'Sign-in repeatedly asks for MFA but never completes.',
        'User receives MFA prompts they did not request.',
        'User cannot complete password reset because MFA is required.',
    ],
    'causes': [
        'Common: phone offline, poor cellular signal, authenticator notifications disabled, expired prompt, wrong authenticator account, recently changed phone, outdated registered phone number, no MFA method enrolled, stale browser session, or sign-in from a new device/location.',
        'Advanced: conditional access policy, device compliance block, MFA service degradation, disabled MFA method, stale push token, time-based code mismatch, risk-based sign-in policy, MFA fatigue attack, or account compromise indicators.',
    ],
    'user_steps': [
        'Confirm you are signing in to the correct company account.',
        'Check that your phone has internet access or cellular signal.',
        'Open the authenticator app manually and look for the approval prompt.',
        'Make sure notifications are enabled for the authenticator app.',
        'If using a code, confirm you are using the correct account in the authenticator app.',
        'Set your phone date and time to automatic if codes are failing.',
        'Retry sign-in from a private/incognito browser window.',
        'Contact IT if you changed phones, changed phone numbers, lost the device, or cannot access any registered method.',
        'Deny and report MFA prompts you did not request.',
    ],
    'it_steps': [
        'Verify the user identity according to support policy before changing MFA methods.',
        'Confirm the affected system: email, VPN, SSO portal, password reset portal, or business application.',
        'Review registered MFA methods and whether the user still has access to any of them.',
        'Check MFA logs for sent prompts, timeouts, denials, method used, location, IP, and device.',
        'Guide the user to use another valid method if available.',
        'If all methods are unavailable, follow the approved MFA reset or re-registration process.',
        'Escalate to Security for unexpected prompts, denied prompts, impossible travel, unknown locations, or suspected compromise.',
        'Escalate to Identity/Access Management or Endpoint if conditional access or device compliance blocks sign-in.',
    ],
}

MFA_ISSUE_SOLUTIONS = [
    ('FIX_MFA_DELIVERY_BASIC_CHECKS','Check Phone Signal, App Notifications, and Retry MFA','MFA prompts may fail because the phone is offline, notifications are disabled, or the prompt expired.','Confirm phone internet or cellular signal. Open the authenticator app manually. Enable app notifications. Retry sign-in and wait for a fresh prompt. Do not approve prompts the user did not request.',0,'Escalate if MFA challenges are sent but never delivered after basic checks.','medium'),
    ('FIX_MFA_CODE_TIME_SYNC','Fix Authenticator Code or Time Sync Issue','Authenticator codes may fail if the user selects the wrong account or the device time is out of sync.','Confirm the user is using the correct authenticator account. Wait for a new code. Set phone date and time to automatic. Restart the authenticator app and retry.',0,'Escalate if codes continue failing after time sync and correct account validation.','medium'),
    ('FIX_MFA_RESET_REREGISTRATION','Request MFA Method Reset or Re-registration','The user changed phones, lost a device, or lost access to the registered MFA method.','Verify identity. Reset MFA methods or require re-registration according to policy. Have the user register a new approved method and complete a test sign-in.',1,'Escalate if MFA reset requires Identity/Access Management approval or stronger identity verification.','medium'),
    ('FIX_REGISTER_MFA_METHOD','Register MFA Method','The user has no valid MFA method registered and must enroll.','Guide the user through the official MFA registration page. Add an approved method and backup method if allowed. Complete a test sign-in.',0,'Escalate if the user cannot access the registration page or policy blocks enrollment.','medium'),
    ('FIX_REPORT_SUSPICIOUS_MFA_PROMPT','Report Suspicious MFA Prompt','Unexpected MFA prompts may indicate someone else is trying to access the account.','Deny unexpected prompts. Capture time, location, user report, and sign-in log details. Escalate to Security and follow incident response guidance.',1,'Escalate immediately to Security for unexpected prompts, repeated prompts, unfamiliar locations, or suspected compromise.','high'),
    ('FIX_ESCALATE_MFA_CONDITIONAL_ACCESS','Escalate Conditional Access or Device Compliance Issue','Sign-in may be blocked because policy requires a compliant device, trusted location, or approved MFA method.','Review sign-in logs and conditional access result. Check device compliance and enrollment status. Escalate to Identity/Access Management or Endpoint team.',1,'Escalate when conditional access, device compliance, or MFA policy blocks sign-in.','high'),
    ('FIX_VERIFY_IDENTITY_BEFORE_MFA_CHANGE','Verify Identity Before MFA Changes','MFA changes require identity verification to protect the account.','Verify the user identity according to policy before resetting or changing MFA methods. Do not ask for passwords or MFA codes. Document verification.',0,'Escalate if the user cannot verify identity or the request appears suspicious.','medium'),
]

MFA_ISSUE_SOLUTION_STEPS = {
    'FIX_MFA_DELIVERY_BASIC_CHECKS': {
        'user': ['Confirm your phone has internet or cellular signal.', 'Open the authenticator app manually and check for the prompt.', 'Enable notifications for the authenticator app.', 'Retry sign-in and wait for a new prompt.', 'Do not approve prompts you did not request.'],
        'technician': ['Confirm whether the MFA challenge is being sent.', 'Ask the user to open the authenticator app manually.', 'Confirm notification settings and device connectivity.', 'Check MFA logs for timeout or delivery failure.', 'Escalate if prompts are sent but not delivered after basic checks.'],
        'admin': ['Review whether MFA delivery issues affect one user or multiple users.', 'Escalate if MFA service degradation or policy issue is suspected.'],
    },
    'FIX_MFA_CODE_TIME_SYNC': {
        'user': ['Confirm you are using the code for the correct company account.', 'Wait for the next code and enter it before it expires.', 'Set your phone date and time to automatic.', 'Restart the authenticator app and try again.', 'Contact IT if codes still fail.'],
        'technician': ['Confirm the user is selecting the correct authenticator account.', 'Check the failed MFA reason in logs.', 'Ask the user to enable automatic date and time.', 'Re-register the authenticator app if codes continue failing.'],
        'admin': ['Escalate repeated code failures if logs suggest policy or identity-provider issues.'],
    },
    'FIX_MFA_RESET_REREGISTRATION': {
        'user': ['Contact IT through an approved support channel.', 'Be ready to verify your identity.', 'Tell IT whether you changed phones, changed phone numbers, or lost the device.', 'Re-register MFA through the official company sign-in page.', 'Test sign-in after setup.'],
        'technician': ['Verify identity according to support policy.', 'Review existing MFA methods.', 'Reset MFA methods or require re-registration according to policy.', 'Do not add unverified phone numbers or devices.', 'Confirm successful MFA setup and sign-in.'],
        'admin': ['Require stronger verification for MFA reset if policy requires it.', 'Escalate suspicious reset requests to Security.'],
    },
    'FIX_REGISTER_MFA_METHOD': {
        'user': ['Open the official company MFA registration page.', 'Add the approved authentication method.', 'Add a backup method if your organization allows it.', 'Complete a test sign-in.'],
        'technician': ['Confirm the user is eligible and required to use MFA.', 'Guide the user through registration.', 'Confirm at least one primary and one backup method if policy allows.', 'Document completion in the ticket.'],
        'admin': ['Review enrollment policy if the user cannot register a method.'],
    },
    'FIX_REPORT_SUSPICIOUS_MFA_PROMPT': {
        'user': ['Deny the MFA prompt.', 'Do not approve prompts you did not initiate.', 'Report the time and details of the prompt.', 'Change your password only if instructed by IT or Security.', 'Wait for Security instructions.'],
        'technician': ['Capture prompt time, source IP/location, user agent, and sign-in logs.', 'Check for repeated prompts or denied attempts.', 'Escalate to Security.', 'Do not simply reset MFA without reviewing account risk.', 'Follow incident response guidance if compromise is suspected.'],
        'admin': ['Treat unexpected MFA prompts as security-sensitive.', 'Prioritize as High if prompts are repeated or location/device is unfamiliar.'],
    },
    'FIX_ESCALATE_MFA_CONDITIONAL_ACCESS': {
        'user': ['Record the exact error message.', 'Note the device and network you are using.', 'Try from an approved company device if available.', 'Submit screenshots with the ticket.'],
        'technician': ['Review sign-in logs and conditional access result.', 'Check device compliance and enrollment status.', 'Confirm whether the user is using an approved MFA method and location.', 'Escalate to Identity/Access Management or Endpoint team.'],
        'admin': ['Validate whether the block is expected policy behavior or a misconfiguration.', 'Escalate if multiple users are blocked unexpectedly.'],
    },
    'FIX_VERIFY_IDENTITY_BEFORE_MFA_CHANGE': {
        'user': ['Use only official IT support channels.', 'Be ready to verify your identity.', 'Do not share passwords or MFA codes with anyone.'],
        'technician': ['Verify identity according to policy.', 'Do not reset MFA before identity verification.', 'Escalate if the user cannot verify identity.', 'Document the verification method according to policy.'],
        'admin': ['Audit MFA reset requests if suspicious or repeated.', 'Require escalation for failed identity verification.'],
    },
}

MFA_USER_DIAGNOSTIC_NODES = [
    ('ROOT_MFA_USER',None,'category','Multi-factor Authentication Issue - User Diagnostic','User-friendly path for MFA delivery, code, phone change, and suspicious prompt issues.',None,None,None,None,1),
    ('Q_RECEIVING_MFA_USER','ROOT_MFA_USER','question','Check MFA Delivery','Determine whether the user receives a prompt, code, text, or call.','Are you receiving the MFA prompt, code, text, or phone call?',None,None,None,1),
    ('Q_CHANGED_PHONE_USER','Q_RECEIVING_MFA_USER','question','Check Phone or Method Change','Changed phones or numbers usually requires MFA reset/re-registration.','Did you recently change phones, phone numbers, or reinstall the authenticator app?','Are you receiving the MFA prompt, code, text, or phone call?','No',None,1),
    ('S_MFA_RESET_USER','Q_CHANGED_PHONE_USER','solution','Request MFA Method Reset or Re-registration',None,None,'Did you recently change phones, phone numbers, or reinstall the authenticator app?','Yes','FIX_MFA_RESET_REREGISTRATION',1),
    ('S_MFA_DELIVERY_USER','Q_CHANGED_PHONE_USER','solution','Check Phone Signal, App Notifications, and Retry MFA',None,None,'Did you recently change phones, phone numbers, or reinstall the authenticator app?','No','FIX_MFA_DELIVERY_BASIC_CHECKS',2),
    ('Q_CODE_FAILS_USER','Q_RECEIVING_MFA_USER','question','Check Code or Prompt Failure','Codes can fail because the wrong account is selected or the phone time is wrong.','Is the code incorrect, expired, or not accepted?','Are you receiving the MFA prompt, code, text, or phone call?','Yes',None,2),
    ('S_CODE_TIME_SYNC_USER','Q_CODE_FAILS_USER','solution','Fix Authenticator Code or Time Sync Issue',None,None,'Is the code incorrect, expired, or not accepted?','Yes','FIX_MFA_CODE_TIME_SYNC',1),
    ('Q_UNEXPECTED_PROMPTS_USER','Q_CODE_FAILS_USER','question','Check Unexpected MFA Prompts','Unexpected prompts may indicate account attack or compromise.','Are you receiving MFA prompts you did not request?','Is the code incorrect, expired, or not accepted?','No',None,2),
    ('S_SUSPICIOUS_MFA_USER','Q_UNEXPECTED_PROMPTS_USER','solution','Report Suspicious MFA Prompt',None,None,'Are you receiving MFA prompts you did not request?','Yes','FIX_REPORT_SUSPICIOUS_MFA_PROMPT',1),
    ('S_USE_METHOD_RETRY_USER','Q_UNEXPECTED_PROMPTS_USER','solution','Use Available MFA Method and Retry Sign-In',None,None,'Are you receiving MFA prompts you did not request?','No','FIX_MFA_DELIVERY_BASIC_CHECKS',2),
]

MFA_TECH_DIAGNOSTIC_NODES = [
    ('ROOT_MFA_TECH',None,'category','Multi-factor Authentication Issue - IT Support Specialist Diagnostic','IT Support Specialist path for identity verification, MFA registration, method availability, security risk, and policy blocks.',None,None,None,None,1),
    ('Q_IDENTITY_VERIFIED_MFA_TECH','ROOT_MFA_TECH','question','Verify User Identity','MFA changes must start with identity verification.','Has the user identity been verified according to policy?',None,None,None,1),
    ('S_VERIFY_IDENTITY_MFA_TECH','Q_IDENTITY_VERIFIED_MFA_TECH','solution','Verify Identity Before MFA Changes',None,None,'Has the user identity been verified according to policy?','No','FIX_VERIFY_IDENTITY_BEFORE_MFA_CHANGE',1),
    ('Q_REGISTERED_METHOD_TECH','Q_IDENTITY_VERIFIED_MFA_TECH','question','Check Registered MFA Method','Confirm whether the user has a registered method.','Does the user have at least one registered MFA method?','Has the user identity been verified according to policy?','Yes',None,2),
    ('S_REGISTER_MFA_TECH','Q_REGISTERED_METHOD_TECH','solution','Register MFA Method',None,None,'Does the user have at least one registered MFA method?','No','FIX_REGISTER_MFA_METHOD',1),
    ('Q_ACCESS_TO_METHOD_TECH','Q_REGISTERED_METHOD_TECH','question','Check Method Access','Determine if reset or re-registration is needed.','Does the user still have access to a registered MFA method?','Does the user have at least one registered MFA method?','Yes',None,2),
    ('S_RESET_MFA_TECH','Q_ACCESS_TO_METHOD_TECH','solution','Reset MFA Method and Require Re-registration',None,None,'Does the user still have access to a registered MFA method?','No','FIX_MFA_RESET_REREGISTRATION',1),
    ('Q_SUSPICIOUS_MFA_TECH','Q_ACCESS_TO_METHOD_TECH','question','Check Suspicious Prompts','Review MFA prompts and sign-in context for account attack indicators.','Are MFA prompts suspicious or from unfamiliar sign-ins?','Does the user still have access to a registered MFA method?','Yes',None,2),
    ('S_ESCALATE_MFA_ATTACK_TECH','Q_SUSPICIOUS_MFA_TECH','solution','Escalate Possible MFA Attack',None,None,'Are MFA prompts suspicious or from unfamiliar sign-ins?','Yes','FIX_REPORT_SUSPICIOUS_MFA_PROMPT',1),
    ('Q_CONDITIONAL_ACCESS_TECH','Q_SUSPICIOUS_MFA_TECH','question','Check Conditional Access or Device Compliance','Policy may require a compliant device, trusted location, or approved method.','Is conditional access or device compliance blocking sign-in?','Are MFA prompts suspicious or from unfamiliar sign-ins?','No',None,2),
    ('S_ESCALATE_CA_TECH','Q_CONDITIONAL_ACCESS_TECH','solution','Escalate Conditional Access or Device Compliance Issue',None,None,'Is conditional access or device compliance blocking sign-in?','Yes','FIX_ESCALATE_MFA_CONDITIONAL_ACCESS',1),
    ('S_TROUBLESHOOT_MFA_DELIVERY_TECH','Q_CONDITIONAL_ACCESS_TECH','solution','Troubleshoot MFA Delivery or Code Issue',None,None,'Is conditional access or device compliance blocking sign-in?','No','FIX_MFA_DELIVERY_BASIC_CHECKS',2),
]

def seed_mfa_issue_content(cursor):
    """Seed Multi-factor Authentication Issue KB article, solutions, role-specific steps, and diagnostic trees."""
    code_, title, category, severity, description = MFA_ISSUE_PROBLEM
    cursor.execute("""
        INSERT INTO problem (problem_code, title, category, severity, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(problem_code) DO UPDATE SET
            title=excluded.title, category=excluded.category, severity=excluded.severity,
            description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, MFA_ISSUE_PROBLEM)
    cursor.execute('SELECT problem_id FROM problem WHERE problem_code = ?', (code_,))
    row = cursor.fetchone()
    if not row:
        return
    problem_id = row['problem_id']
    cursor.execute("""
        INSERT INTO kb_article (problem_id, title, summary, difficulty, estimated_time, escalation_required, escalation_notes, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, difficulty=excluded.difficulty,
            estimated_time=excluded.estimated_time, escalation_required=excluded.escalation_required,
            escalation_notes=excluded.escalation_notes, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, MFA_ISSUE_KB['title'], MFA_ISSUE_KB['summary'], MFA_ISSUE_KB['difficulty'], MFA_ISSUE_KB['estimated_time'], MFA_ISSUE_KB['escalation_required'], MFA_ISSUE_KB['escalation_notes']))
    cursor.execute('SELECT kb_article_id FROM kb_article WHERE problem_id = ?', (problem_id,))
    article = cursor.fetchone()
    if article:
        kb_id = article['kb_article_id']
        delete_kb_child_rows(cursor, kb_id)
        insert_kb_child_rows(cursor, 'kb_article_tag', 'tag', kb_id, MFA_ISSUE_KB['tags'])
        insert_kb_child_rows(cursor, 'kb_article_symptom', 'symptom', kb_id, MFA_ISSUE_KB['symptoms'])
        insert_kb_child_rows(cursor, 'kb_article_cause', 'cause', kb_id, MFA_ISSUE_KB['causes'])
        insert_kb_child_rows(cursor, 'kb_article_user_step', 'step_text', kb_id, MFA_ISSUE_KB['user_steps'])
        insert_kb_child_rows(cursor, 'kb_article_it_step', 'step_text', kb_id, MFA_ISSUE_KB['it_steps'])
    cursor.executemany("""
        INSERT INTO solution (solution_code, title, summary, resolution_steps, escalation_required, escalation_notes, priority_recommendation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(solution_code) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, resolution_steps=excluded.resolution_steps,
            escalation_required=excluded.escalation_required, escalation_notes=excluded.escalation_notes,
            priority_recommendation=excluded.priority_recommendation, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, MFA_ISSUE_SOLUTIONS)
    for solution_code, audience_steps in MFA_ISSUE_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue
        for audience, steps in audience_steps.items():
            cursor.execute('DELETE FROM solution_step WHERE solution_id = ? AND audience = ?', (solution_id, audience))
            cursor.executemany('INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)', [(solution_id, audience, step, idx) for idx, step in enumerate(steps, start=1)])
    seed_mfa_issue_tree(cursor, 'user', 'MULTI_FACTOR_AUTHENTICATION_ISSUE_USER', 'Multi-factor Authentication Issue - User Diagnostic', 'User-friendly diagnostic tree for MFA delivery, phone change, code, and suspicious prompt issues.', MFA_USER_DIAGNOSTIC_NODES)
    seed_mfa_issue_tree(cursor, 'technician', 'MULTI_FACTOR_AUTHENTICATION_ISSUE_TECHNICIAN', 'Multi-factor Authentication Issue - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for MFA method, security, and policy root-cause analysis.', MFA_TECH_DIAGNOSTIC_NODES)

def seed_mfa_issue_tree(cursor, audience, tree_code, title, description, nodes):
    problem_id = get_problem_id_for_tree_code(cursor, 'MULTI_FACTOR_AUTHENTICATION_ISSUE')
    cursor.execute("""
        INSERT INTO diagnostic_tree (problem_id, diagnostic_tree_code, base_tree_code, audience, title, description, is_active, updated_at)
        VALUES (?, ?, 'MULTI_FACTOR_AUTHENTICATION_ISSUE', ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(diagnostic_tree_code) DO UPDATE SET
            problem_id=excluded.problem_id, base_tree_code=excluded.base_tree_code, audience=excluded.audience,
            title=excluded.title, description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, tree_code, audience, title, description))
    tree_id = get_diagnostic_tree_id_by_code(cursor, tree_code)
    if not tree_id:
        return
    cursor.execute('UPDATE diagnostic_node SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE diagnostic_tree_id = ?', (tree_id,))
    for node_key, parent_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_code, sort_order in nodes:
        parent_id = get_diagnostic_node_id_by_tree_and_key(cursor, tree_id, parent_key) if parent_key else None
        solution_id = get_solution_id_by_code(cursor, solution_code) if solution_code else None
        cursor.execute("""
            INSERT INTO diagnostic_node (
                diagnostic_tree_id, parent_diagnostic_node_id, problem_id, diagnostic_tree_code,
                node_key, node_type, title, description, prompt_text,
                condition_label, condition_value, solution_id, sort_order, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(diagnostic_tree_code, node_key) DO UPDATE SET
                diagnostic_tree_id=excluded.diagnostic_tree_id,
                parent_diagnostic_node_id=excluded.parent_diagnostic_node_id,
                problem_id=excluded.problem_id,
                node_type=excluded.node_type,
                title=excluded.title,
                description=excluded.description,
                prompt_text=excluded.prompt_text,
                condition_label=excluded.condition_label,
                condition_value=excluded.condition_value,
                solution_id=excluded.solution_id,
                sort_order=excluded.sort_order,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (tree_id, parent_id, problem_id, tree_code, node_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_id, sort_order))



# -----------------------------
# VPN CONNECTION FAILURE RELATIONAL SEED DATA
# -----------------------------
VPN_CONNECTION_FAILURE_PROBLEM = (
    'VPN_CONNECTION_FAILURE',
    'VPN Connection Failure',
    'Network, Remote Access & Storage',
    'high',
    'User cannot connect to the company VPN or loses VPN access after connecting.',
)

VPN_CONNECTION_FAILURE_KB = {
    'title': 'VPN Connection Failure',
    'summary': 'Use this guide when VPN will not connect, disconnects, or connects but internal resources such as shared drives, internal websites, or business applications do not work.',
    'difficulty': 'Intermediate',
    'estimated_time': '10-20 minutes',
    'escalation_required': 1,
    'escalation_notes': 'Escalate to Identity/Access Management for account, MFA, group, or conditional access issues; Network Team for gateway, routing, DNS, ACL, VPN pool, or multiple-user issues; Endpoint/Desktop Support for client, certificate, profile, or compliance issues; Security for suspicious login/MFA activity or risk blocks.',
    'tags': ['VPN', 'remote access', 'network', 'MFA', 'DNS', 'routing', 'firewall', 'ACL', 'VPN client', 'split tunnel', 'remote work'],
    'symptoms': [
        'VPN will not connect or gets stuck connecting.',
        'VPN says authentication failed, password expired, account locked, or MFA failed.',
        'VPN connects but shared drives, internal websites, or business applications do not work.',
        'VPN disconnects frequently or worked previously but stopped working.',
        'VPN works on a mobile hotspot but not on home Wi-Fi or public Wi-Fi.',
        'User receives a certificate, profile, compliance, or VPN client error.',
        'Multiple users cannot connect, suggesting possible VPN gateway, identity provider, DNS, or network outage.',
    ],
    'causes': [
        'Common: no internet connection before starting VPN, incorrect username/password, expired password, locked account, MFA prompt not approved, outdated VPN client, missing/corrupted VPN profile, unstable Wi-Fi, local network blocking VPN traffic, unavailable VPN service, wrong VPN profile/region, or incorrect device time/date.',
        'Advanced: VPN gateway DNS failure, local firewall/security software blocking the client, VPN protocol/port blocked by ACL/firewall, NAT traversal issue, expired or missing certificate, endpoint compliance failure, split-tunnel route problem, overlapping local subnet, exhausted VPN IP pool, gateway outage/high utilization, routing or ACL issue between VPN pool and internal resources, identity provider outage, or conditional access block.',
    ],
    'user_steps': [
        'Confirm your normal internet connection works without VPN.',
        'Restart the VPN client.',
        'Confirm you are using the correct company username and password.',
        'Approve the MFA prompt only if you initiated the VPN sign-in.',
        'Restart your computer and try VPN again.',
        'Try a different trusted network, such as a mobile hotspot.',
        'If VPN connects but internal apps do not work, write down which app, website, or shared drive fails.',
        'Take a screenshot of the VPN error message.',
        'Do not repeatedly retry if you see account lockout, MFA, or security warnings.',
        'Submit a support ticket if the issue continues.',
    ],
    'it_steps': [
        'Tier 1: Confirm the user, device name, location, network type, VPN client name/version, and exact error message.',
        'Tier 1: Confirm normal internet works before VPN and identify whether the issue is unable to connect, disconnecting, or connected with no internal access.',
        'Tier 1: Confirm whether MFA prompt is received/approved and whether the account is locked, password expired, or blocked by MFA.',
        'Tier 1: Confirm the user is selecting the correct VPN profile or region.',
        'Tier 1: Ask the user to restart the VPN client, reboot the device, and test from another trusted network or mobile hotspot.',
        'Tier 1: Check whether other users report similar VPN failures and capture screenshots, timestamps, and error codes.',
        'Tier 2: Verify local IP configuration including IP address, subnet mask, default gateway, and DNS servers.',
        'Tier 2: Test DNS resolution for the VPN gateway hostname and compare results across home Wi-Fi, office network, and mobile hotspot.',
        'Tier 2: Review VPN client logs for authentication, certificate, DNS, route, tunnel, or compliance errors.',
        'Tier 2: Confirm whether the VPN client receives a VPN adapter IP address after connecting.',
        'Tier 2: If connected but internal resources fail, test internal DNS lookup, allowed resource reachability, route table entries, and shared drive/internal app access.',
        'Tier 2: Check for local subnet overlap, local firewall/security software interference, routing symptoms, DNS symptoms, or ACL/resource-permission boundaries.',
        'Tier 2: Determine whether the likely root cause is identity/authentication, MFA, local network, VPN client, DNS, routing, firewall/ACL, endpoint compliance, or VPN gateway outage.',
        'Escalate with collected evidence if infrastructure, policy, gateway, certificate, or security-side changes are required.',
    ],
}

VPN_CONNECTION_FAILURE_SOLUTIONS = [
    ('FIX_VPN_RESTORE_BASE_INTERNET','Restore Internet Connection Before VPN','VPN cannot work until the device has normal internet access.','Disconnect VPN, confirm public websites open, reconnect Wi-Fi/Ethernet, restart the router if working remotely, and retry VPN after internet access works.',0,'Escalate only if the base internet issue appears to affect a company-managed network, multiple users, or a managed device configuration.','medium'),
    ('FIX_VPN_AUTH_MFA_DEPENDENCY','Resolve VPN Authentication or MFA Issue','VPN sign-in may fail because of password, account lockout, expired password, MFA, conditional access, or missing VPN group membership.','Confirm username/password, approve legitimate MFA, avoid repeated retries, and route to password reset, account locked, or MFA troubleshooting when needed.',1,'Escalate to Identity/Access Management if conditional access, group membership, risky sign-in, or identity policy blocks VPN access.','high'),
    ('FIX_VPN_LOCAL_NETWORK_BLOCK','Identify Local Network Blocking VPN','The current network may block or interfere with VPN traffic.','Test VPN from a trusted mobile hotspot or another safe network, compare behavior, and document which networks work and fail.',0,'Escalate if a company-managed firewall, ACL, or network path appears to block VPN. For unmanaged home/public networks, document likely local network or ISP restriction.','medium'),
    ('FIX_VPN_UPDATE_REINSTALL_CLIENT','Update or Reinstall VPN Client','The VPN client may be outdated, corrupted, missing its profile, or blocked by a local endpoint issue.','Restart the client and computer, check VPN client version/profile, review logs, repair/update/reinstall from the approved source, and escalate if admin rights, certificates, or managed deployment are required.',1,'Escalate to Endpoint/Desktop Support if the client, certificate, profile, or managed deployment requires elevated access or endpoint management.','medium'),
    ('FIX_VPN_DNS_GATEWAY_RESOLUTION','Troubleshoot DNS Resolution for VPN Gateway','The device cannot resolve the VPN gateway hostname.','Confirm internet access, perform DNS lookup for the VPN gateway, compare results on another trusted network, flush DNS cache if appropriate, and escalate if DNS records fail or multiple users are affected.',1,'Escalate to Network/DNS team if VPN gateway DNS resolution fails, DNS results are inconsistent, or multiple users are affected.','high'),
    ('FIX_VPN_CONNECTED_INTERNAL_ACCESS_FAILS','Troubleshoot VPN Routing, DNS, or ACL Access','VPN connects, but internal resources are unreachable due to routing, internal DNS, permissions, or ACL issues.','Confirm VPN adapter IP, test internal DNS, test allowed internal resources by hostname/IP where appropriate, review route table entries, check resource permissions, and escalate with evidence.',1,'Escalate to Network or Systems team with VPN IP, routes, DNS results, resource tested, screenshots, and timestamps.','high'),
    ('FIX_ESCALATE_VPN_CLIENT_CERT_GATEWAY','Escalate Possible VPN Client, Certificate, or Gateway Issue','VPN fails across multiple networks and may involve client certificate, profile, compliance, or gateway-side problem.','Confirm failure across multiple networks, check client version/profile/certificate status where visible, review VPN logs, check whether other users are affected, and escalate based on evidence.',1,'Escalate to Endpoint, Network, Identity, or Security depending on whether evidence points to certificate/profile/compliance, gateway/tunnel negotiation, identity policy, or suspicious activity.','high'),
    ('FIX_VPN_CONFIRM_RESTORED','Confirm VPN Restored','VPN is connected and required internal resources are reachable.','Confirm VPN shows connected, verify required internal app/shared drive/internal site access, document successful test, and close or resolve the ticket if applicable.',0,None,'low'),
]

VPN_CONNECTION_FAILURE_SOLUTION_STEPS = {
    'FIX_VPN_RESTORE_BASE_INTERNET': {
        'user': ['Disconnect VPN.', 'Confirm you can open public websites.', 'Restart Wi-Fi or reconnect Ethernet.', 'Restart your router if working from home.', 'Try VPN again after internet access works.'],
        'technician': ['Confirm whether the issue is internet access or VPN-specific.', 'Verify the user has a valid IP address, gateway, and DNS.', 'Test public website access and DNS resolution.', 'Guide the user through reconnecting Wi-Fi/Ethernet.', 'Continue VPN troubleshooting only after internet is restored.'],
        'admin': ['Escalation notes: escalate only if base connectivity fails on a company-managed network, multiple users are affected, or managed device network configuration appears incorrect.'],
    },
    'FIX_VPN_AUTH_MFA_DEPENDENCY': {
        'user': ['Confirm you are using the correct username and password.', 'Approve the MFA prompt only if you initiated the VPN sign-in.', 'Do not repeatedly retry if the account may be locked.', 'Reset your password or contact IT if authentication continues to fail.'],
        'technician': ['Check whether the user can sign in to the SSO portal or email.', 'Check account locked, password expired, and MFA status.', 'Review the VPN authentication error message.', 'If needed, route to Password Reset, Account Locked, or MFA troubleshooting flow.', 'Escalate if conditional access or VPN group membership is blocking access.'],
        'admin': ['Escalation notes: escalate to Identity/Access Management with username, error text, timestamp, MFA status, account state, and VPN group/conditional-access evidence.'],
    },
    'FIX_VPN_LOCAL_NETWORK_BLOCK': {
        'user': ['Try VPN from a trusted mobile hotspot or another safe network.', 'Restart your home router if working remotely.', 'Avoid public Wi-Fi that blocks VPN traffic.', 'Tell IT which networks work and which do not.'],
        'technician': ['Compare VPN behavior on home Wi-Fi, hotspot, and office network.', 'Confirm whether DNS resolves the VPN gateway on each network.', 'Check whether the issue is isolated to one network path.', 'Look for local subnet overlap with corporate networks.', 'Document network type, public IP if allowed by policy, error message, and test results.', 'Escalate if a company-managed firewall, ACL, or network path appears to block VPN.'],
        'admin': ['Escalation notes: provide Network Team with working/failing networks, DNS lookup results, public IP if policy allows, VPN error code, timestamps, and subnet-overlap findings.'],
    },
    'FIX_VPN_UPDATE_REINSTALL_CLIENT': {
        'user': ['Restart the VPN client.', 'Restart the computer.', 'Check whether the VPN profile is still listed.', 'Submit a ticket with the VPN client name and error message if it still fails.'],
        'technician': ['Check VPN client version and profile.', 'Review VPN client logs if available.', 'Repair or update the VPN client from the approved source.', 'Reinstall the VPN client or profile if policy allows.', 'Escalate to Endpoint/Desktop Support if admin rights, certificates, or managed deployment are required.'],
        'admin': ['Escalation notes: provide Endpoint/Desktop Support with client version, profile name, certificate/profile symptoms, device name, screenshots, and install/update attempts.'],
    },
    'FIX_VPN_DNS_GATEWAY_RESOLUTION': {
        'user': ['Confirm normal internet access works.', 'Try VPN again from a private/home network or trusted hotspot.', 'Submit a ticket with the VPN error screenshot.'],
        'technician': ['Run or guide DNS lookup for the VPN gateway hostname.', 'Compare DNS results on the current network and mobile hotspot.', 'Flush DNS cache if appropriate.', 'Try alternate trusted DNS only if company policy allows.', 'Escalate to Network/DNS team if gateway DNS records fail or multiple users are affected.'],
        'admin': ['Escalation notes: provide Network/DNS team with VPN gateway hostname, DNS server used, lookup output, affected network, affected users, and timestamps.'],
    },
    'FIX_VPN_CONNECTED_INTERNAL_ACCESS_FAILS': {
        'user': ['Confirm VPN shows connected.', 'Write down which internal website, application, or shared drive does not work.', 'Try another internal resource if available.', 'Submit a ticket with screenshots and affected resource names.'],
        'technician': ['Confirm VPN adapter has an assigned VPN IP address.', 'Test internal DNS resolution.', 'Test allowed internal resources by hostname and IP where appropriate.', 'Review route table for VPN routes.', 'Determine whether the issue affects one resource, one subnet, or all internal resources.', 'Check whether the user has permission to the resource.', 'Escalate to Network or Systems team with VPN IP, routes, DNS results, resource tested, and timestamps.'],
        'admin': ['Escalation notes: provide Network/Systems team with VPN-assigned IP, route table notes, DNS results, target resource names/IPs, permission findings, screenshots, and timestamps.'],
    },
    'FIX_ESCALATE_VPN_CLIENT_CERT_GATEWAY': {
        'user': ['Stop repeated VPN attempts if errors continue.', 'Take a screenshot of the VPN error.', 'Note whether VPN fails on home Wi-Fi and mobile hotspot.', 'Submit a ticket with device name and VPN client version if known.'],
        'technician': ['Confirm failure occurs across multiple networks.', 'Check VPN client version, profile, and certificate status where visible.', 'Review VPN client logs for certificate, profile, compliance, or tunnel negotiation errors.', 'Check whether other users are affected.', 'Escalate to Endpoint, Network, Identity, or Security based on evidence.'],
        'admin': ['Escalation notes: escalate with client logs, network comparison, client version, certificate/profile status, affected scope, compliance error text, and other-user impact.'],
    },
    'FIX_VPN_CONFIRM_RESTORED': {
        'user': ['Confirm VPN shows connected.', 'Open the needed internal app, website, or shared drive.', 'Continue working normally.', 'Report the issue again if VPN disconnects or access fails.'],
        'technician': ['Confirm tunnel is established.', 'Confirm the user can access required resources.', 'Document the successful test and close or resolve the ticket if applicable.'],
        'admin': ['Escalation notes: no escalation needed if VPN and required internal resources are working.'],
    },
}

VPN_USER_DIAGNOSTIC_NODES = [
    ('ROOT_VPN_USER', None, 'category', 'VPN Connection Failure', 'User-friendly diagnostic tree for VPN connection and internal access problems.', None, None, None, None, 1),
    ('Q_BASE_INTERNET_WORKS_USER','ROOT_VPN_USER','question','Check Internet Before VPN',None,'Does your normal internet connection work without VPN?',None,None,None,1),
    ('S_RESTORE_BASE_INTERNET_USER','Q_BASE_INTERNET_WORKS_USER','solution','Restore Internet Connection Before VPN',None,None,'Does your normal internet connection work without VPN?','No','FIX_VPN_RESTORE_BASE_INTERNET',1),
    ('Q_AUTH_MFA_ERROR_USER','Q_BASE_INTERNET_WORKS_USER','question','Check Authentication or MFA Error',None,'Are you receiving an authentication, password, account locked, or MFA error?','Does your normal internet connection work without VPN?','Yes',None,2),
    ('S_AUTH_MFA_DEPENDENCY_USER','Q_AUTH_MFA_ERROR_USER','solution','Resolve VPN Authentication or MFA Issue',None,None,'Are you receiving an authentication, password, account locked, or MFA error?','Yes','FIX_VPN_AUTH_MFA_DEPENDENCY',1),
    ('Q_VPN_CONNECTS_USER','Q_AUTH_MFA_ERROR_USER','question','Check Whether VPN Connects',None,'Does the VPN connect successfully?','Are you receiving an authentication, password, account locked, or MFA error?','No',None,2),
    ('Q_VPN_OTHER_NETWORK_USER','Q_VPN_CONNECTS_USER','question','Compare Another Trusted Network',None,'Does VPN work from another trusted network, such as a mobile hotspot?','Does the VPN connect successfully?','No',None,1),
    ('S_LOCAL_NETWORK_BLOCK_USER','Q_VPN_OTHER_NETWORK_USER','solution','Identify Local Network Blocking VPN',None,None,'Does VPN work from another trusted network, such as a mobile hotspot?','Yes','FIX_VPN_LOCAL_NETWORK_BLOCK',1),
    ('S_UPDATE_REINSTALL_CLIENT_USER','Q_VPN_OTHER_NETWORK_USER','solution','Update or Reinstall VPN Client',None,None,'Does VPN work from another trusted network, such as a mobile hotspot?','No','FIX_VPN_UPDATE_REINSTALL_CLIENT',2),
    ('Q_INTERNAL_RESOURCES_USER','Q_VPN_CONNECTS_USER','question','Check Internal Resource Access',None,'If VPN connects, can you access internal resources such as shared drives or internal websites?','Does the VPN connect successfully?','Yes',None,2),
    ('S_VPN_RESTORED_USER','Q_INTERNAL_RESOURCES_USER','solution','Confirm VPN Restored',None,None,'If VPN connects, can you access internal resources such as shared drives or internal websites?','Yes','FIX_VPN_CONFIRM_RESTORED',1),
    ('S_CONNECTED_INTERNAL_FAILS_USER','Q_INTERNAL_RESOURCES_USER','solution','Report Connected VPN But Internal Access Fails',None,None,'If VPN connects, can you access internal resources such as shared drives or internal websites?','No','FIX_VPN_CONNECTED_INTERNAL_ACCESS_FAILS',2),
]

VPN_TECH_DIAGNOSTIC_NODES = [
    ('ROOT_VPN_TECH', None, 'category', 'VPN Connection Failure - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for VPN authentication, DNS, routing, client, and network path failures.', None, None, None, None, 1),
    ('Q_BASE_INTERNET_WORKS_TECH','ROOT_VPN_TECH','question','Verify Base Internet',None,'Can the user access the internet before starting VPN?',None,None,None,1),
    ('S_RESTORE_BASE_INTERNET_TECH','Q_BASE_INTERNET_WORKS_TECH','solution','Restore Base Internet Connection',None,None,'Can the user access the internet before starting VPN?','No','FIX_VPN_RESTORE_BASE_INTERNET',1),
    ('Q_VPN_AUTH_DEPENDENCY_TECH','Q_BASE_INTERNET_WORKS_TECH','question','Check Authentication, Account, and MFA',None,'Is the failure related to credentials, account lockout, password expiration, or MFA?','Can the user access the internet before starting VPN?','Yes',None,2),
    ('S_VPN_AUTH_DEPENDENCY_TECH','Q_VPN_AUTH_DEPENDENCY_TECH','solution','Resolve VPN Authentication or MFA Dependency',None,None,'Is the failure related to credentials, account lockout, password expiration, or MFA?','Yes','FIX_VPN_AUTH_MFA_DEPENDENCY',1),
    ('Q_VPN_DNS_GATEWAY_TECH','Q_VPN_AUTH_DEPENDENCY_TECH','question','Check VPN Gateway DNS',None,'Does DNS resolve the VPN gateway hostname?','Is the failure related to credentials, account lockout, password expiration, or MFA?','No',None,2),
    ('S_VPN_DNS_GATEWAY_TECH','Q_VPN_DNS_GATEWAY_TECH','solution','Troubleshoot DNS Resolution for VPN Gateway',None,None,'Does DNS resolve the VPN gateway hostname?','No','FIX_VPN_DNS_GATEWAY_RESOLUTION',1),
    ('Q_VPN_TUNNEL_IP_TECH','Q_VPN_DNS_GATEWAY_TECH','question','Check Tunnel Establishment',None,'Does the VPN client establish a tunnel and receive a VPN adapter IP address?','Does DNS resolve the VPN gateway hostname?','Yes',None,2),
    ('Q_VPN_FAILS_MULTIPLE_NETWORKS_TECH','Q_VPN_TUNNEL_IP_TECH','question','Compare Network Paths',None,'Does VPN fail on multiple networks?','Does the VPN client establish a tunnel and receive a VPN adapter IP address?','No',None,1),
    ('S_ESCALATE_CLIENT_CERT_GATEWAY_TECH','Q_VPN_FAILS_MULTIPLE_NETWORKS_TECH','solution','Escalate Possible VPN Client, Certificate, or Gateway Issue',None,None,'Does VPN fail on multiple networks?','Yes','FIX_ESCALATE_VPN_CLIENT_CERT_GATEWAY',1),
    ('S_LOCAL_NETWORK_BLOCK_TECH','Q_VPN_FAILS_MULTIPLE_NETWORKS_TECH','solution','Identify Local Network Blocking VPN',None,None,'Does VPN fail on multiple networks?','No','FIX_VPN_LOCAL_NETWORK_BLOCK',2),
    ('Q_INTERNAL_REACHABILITY_TECH','Q_VPN_TUNNEL_IP_TECH','question','Check Internal Reachability',None,'After connection, can the user resolve and reach internal resources?','Does the VPN client establish a tunnel and receive a VPN adapter IP address?','Yes',None,2),
    ('S_VPN_RESTORED_TECH','Q_INTERNAL_REACHABILITY_TECH','solution','Confirm VPN Restored',None,None,'After connection, can the user resolve and reach internal resources?','Yes','FIX_VPN_CONFIRM_RESTORED',1),
    ('S_CONNECTED_INTERNAL_FAILS_TECH','Q_INTERNAL_REACHABILITY_TECH','solution','Troubleshoot VPN Routing, DNS, or ACL Access',None,None,'After connection, can the user resolve and reach internal resources?','No','FIX_VPN_CONNECTED_INTERNAL_ACCESS_FAILS',2),
]

def seed_vpn_connection_failure_content(cursor):
    """Seed VPN Connection Failure KB article, solutions, steps, and diagnostic trees."""
    code_, title, category, severity, description = VPN_CONNECTION_FAILURE_PROBLEM
    cursor.execute("""
        INSERT INTO problem (problem_code, title, category, severity, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(problem_code) DO UPDATE SET
            title=excluded.title, category=excluded.category, severity=excluded.severity,
            description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, VPN_CONNECTION_FAILURE_PROBLEM)
    cursor.execute('SELECT problem_id FROM problem WHERE problem_code = ?', (code_,))
    row = cursor.fetchone()
    if not row:
        return
    problem_id = row['problem_id']
    cursor.execute("""
        INSERT INTO kb_article (problem_id, title, summary, difficulty, estimated_time, escalation_required, escalation_notes, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, difficulty=excluded.difficulty,
            estimated_time=excluded.estimated_time, escalation_required=excluded.escalation_required,
            escalation_notes=excluded.escalation_notes, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, VPN_CONNECTION_FAILURE_KB['title'], VPN_CONNECTION_FAILURE_KB['summary'], VPN_CONNECTION_FAILURE_KB['difficulty'], VPN_CONNECTION_FAILURE_KB['estimated_time'], VPN_CONNECTION_FAILURE_KB['escalation_required'], VPN_CONNECTION_FAILURE_KB['escalation_notes']))
    cursor.execute('SELECT kb_article_id FROM kb_article WHERE problem_id = ?', (problem_id,))
    article = cursor.fetchone()
    if article:
        kb_id = article['kb_article_id']
        delete_kb_child_rows(cursor, kb_id)
        insert_kb_child_rows(cursor, 'kb_article_tag', 'tag', kb_id, VPN_CONNECTION_FAILURE_KB['tags'])
        insert_kb_child_rows(cursor, 'kb_article_symptom', 'symptom', kb_id, VPN_CONNECTION_FAILURE_KB['symptoms'])
        insert_kb_child_rows(cursor, 'kb_article_cause', 'cause', kb_id, VPN_CONNECTION_FAILURE_KB['causes'])
        insert_kb_child_rows(cursor, 'kb_article_user_step', 'step_text', kb_id, VPN_CONNECTION_FAILURE_KB['user_steps'])
        insert_kb_child_rows(cursor, 'kb_article_it_step', 'step_text', kb_id, VPN_CONNECTION_FAILURE_KB['it_steps'])
    cursor.executemany("""
        INSERT INTO solution (solution_code, title, summary, resolution_steps, escalation_required, escalation_notes, priority_recommendation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(solution_code) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, resolution_steps=excluded.resolution_steps,
            escalation_required=excluded.escalation_required, escalation_notes=excluded.escalation_notes,
            priority_recommendation=excluded.priority_recommendation, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, VPN_CONNECTION_FAILURE_SOLUTIONS)
    for solution_code, audience_steps in VPN_CONNECTION_FAILURE_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue
        for audience, steps in audience_steps.items():
            cursor.execute('DELETE FROM solution_step WHERE solution_id = ? AND audience = ?', (solution_id, audience))
            cursor.executemany('INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)', [(solution_id, audience, step, idx) for idx, step in enumerate(steps, start=1)])
    seed_vpn_connection_failure_tree(cursor, 'user', 'VPN_CONNECTION_FAILURE_USER', 'VPN Connection Failure - User Diagnostic', 'User-friendly diagnostic tree for VPN connection and internal access problems.', VPN_USER_DIAGNOSTIC_NODES)
    seed_vpn_connection_failure_tree(cursor, 'technician', 'VPN_CONNECTION_FAILURE_TECHNICIAN', 'VPN Connection Failure - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for VPN authentication, DNS, routing, client, and network path failures.', VPN_TECH_DIAGNOSTIC_NODES)

def seed_vpn_connection_failure_tree(cursor, audience, tree_code, title, description, nodes):
    problem_id = get_problem_id_for_tree_code(cursor, 'VPN_CONNECTION_FAILURE')
    cursor.execute("""
        INSERT INTO diagnostic_tree (problem_id, diagnostic_tree_code, base_tree_code, audience, title, description, is_active, updated_at)
        VALUES (?, ?, 'VPN_CONNECTION_FAILURE', ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(diagnostic_tree_code) DO UPDATE SET
            problem_id=excluded.problem_id, base_tree_code=excluded.base_tree_code, audience=excluded.audience,
            title=excluded.title, description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, tree_code, audience, title, description))
    tree_id = get_diagnostic_tree_id_by_code(cursor, tree_code)
    if not tree_id:
        return
    cursor.execute('UPDATE diagnostic_node SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE diagnostic_tree_id = ?', (tree_id,))
    for node_key, parent_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_code, sort_order in nodes:
        parent_id = get_diagnostic_node_id_by_tree_and_key(cursor, tree_id, parent_key) if parent_key else None
        solution_id = get_solution_id_by_code(cursor, solution_code) if solution_code else None
        cursor.execute("""
            INSERT INTO diagnostic_node (
                diagnostic_tree_id, parent_diagnostic_node_id, problem_id, diagnostic_tree_code,
                node_key, node_type, title, description, prompt_text,
                condition_label, condition_value, solution_id, sort_order, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(diagnostic_tree_code, node_key) DO UPDATE SET
                diagnostic_tree_id=excluded.diagnostic_tree_id,
                parent_diagnostic_node_id=excluded.parent_diagnostic_node_id,
                problem_id=excluded.problem_id,
                node_type=excluded.node_type,
                title=excluded.title,
                description=excluded.description,
                prompt_text=excluded.prompt_text,
                condition_label=excluded.condition_label,
                condition_value=excluded.condition_value,
                solution_id=excluded.solution_id,
                sort_order=excluded.sort_order,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (tree_id, parent_id, problem_id, tree_code, node_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_id, sort_order))


# -----------------------------
# SHARED DRIVE / NETWORK DRIVE ACCESS ISSUE RELATIONAL SEED DATA
# -----------------------------
SHARED_DRIVE_ACCESS_PROBLEM = (
    'SHARED_DRIVE_NETWORK_DRIVE_ACCESS_ISSUE',
    'Shared Drive / Network Drive Access Issue',
    'Network, Remote Access & Storage',
    'medium',
    'User cannot access a shared drive, mapped network drive, file server folder, or shared company location.',
)

SHARED_DRIVE_ACCESS_KB = {
    'title': 'Shared Drive / Network Drive Access Issue',
    'summary': 'Use this guide when a mapped drive is missing, a shared drive has a red X, a folder shows Access Denied, or a network path cannot be found.',
    'difficulty': 'Intermediate',
    'estimated_time': '10-20 minutes',
    'escalation_required': 1,
    'escalation_notes': 'Escalate to Access Management/Identity for missing folder permissions or group membership, Systems/Server Team for file server/share/DFS problems, Network Team for DNS/routing/firewall/ACL or VPN-to-file-server reachability issues, and Endpoint/Desktop Support for mapped-drive policy, cached credentials, offline files, or user-profile problems.',
    'tags': ['shared drive', 'network drive', 'mapped drive', 'file server', 'UNC path', 'SMB', 'VPN', 'DNS', 'access denied', 'permissions'],
    'symptoms': [
        'Shared drive is missing or shows a red X.',
        'User cannot open a department folder or mapped network drive.',
        'Access Denied appears for a specific folder or share.',
        'Network Path Not Found appears when opening the drive or UNC path.',
        'Shared drive works in the office but not from home or VPN.',
        'User can access some folders but not a specific protected folder.',
        'Files on the shared drive open slowly or repeatedly prompt for credentials.',
    ],
    'causes': [
        'Common: user is not connected to VPN, VPN internal DNS is not working, network drive mapping is disconnected, file server hostname cannot resolve, mapped path is outdated, user lacks folder permission, saved credentials are old, file server/share is temporarily unavailable, user is on guest/public network, group membership has not refreshed, or restart/sign-out is needed after an access change.',
        'Advanced: SMB traffic blocked by firewall or ACL, routing issue between VPN subnet and file server subnet, DNS suffix/search domain issue, DFS namespace referral issue, file server service down, NTFS/share permission mismatch, Group Policy drive mapping failure, Kerberos/authentication issue, time skew, offline files cache corruption, duplicate drive mapping using different credentials, file server quota/storage issue, or department share migration with old path still in use.',
    ],
    'user_steps': [
        'Confirm you are connected to the company network or VPN.',
        'Try opening another internal resource to confirm VPN or internal access works.',
        'Sign out and sign back in if your access was recently changed.',
        'Restart the computer if the shared drive still shows disconnected.',
        'Confirm the exact drive letter or folder path you are trying to open.',
        'Check whether coworkers can access the same shared location.',
        'If you see Access Denied, request access or contact IT.',
        'If you see Network Path Not Found, take a screenshot of the error.',
        'Do not delete or rename shared folders while troubleshooting.',
        'Submit a ticket with the folder path, error message, and whether VPN is connected.',
    ],
    'it_steps': [
        'Tier 1: Confirm the user, device name, location, network type, and whether the user is remote or onsite.',
        'Tier 1: Ask for the exact error message: Access Denied, Network Path Not Found, disconnected drive/red X, credential prompt, or slow access.',
        'Tier 1: Confirm whether the user is connected to VPN if remote and whether other internal resources work.',
        'Tier 1: Confirm the exact drive letter and UNC path if known.',
        'Tier 1: Ask whether other users can access the same share and whether the user recently changed team, role, department, or device.',
        'Tier 1: Have the user sign out/in or restart after recent permission changes.',
        'Tier 1: Determine whether the issue affects one folder, one share, or all network drives and capture screenshots and the exact path.',
        'Tier 2: Test the file server by hostname and FQDN.',
        'Tier 2: Test DNS resolution for the file server.',
        'Tier 2: Test reachability to the file server by IP address where allowed.',
        'Tier 2: Compare access by hostname versus IP to separate DNS from connectivity.',
        'Tier 2: Test the UNC path directly, for example \\\\server\\share.',
        'Tier 2: Confirm whether SMB/file-sharing traffic is reachable according to company tools and policy.',
        'Tier 2: Check whether the user VPN adapter has correct IP, DNS, and routes.',
        'Tier 2: Check whether the file server subnet is reachable from the user network or VPN segment.',
        'Tier 2: Check for local subnet overlap if the user is remote.',
        'Tier 2: Check mapped drive configuration and remove/re-map the drive if the path is outdated.',
        'Tier 2: Check whether cached credentials are being used.',
        'Tier 2: Confirm the user AD/security group membership or access group.',
        'Tier 2: Distinguish between connectivity, DNS, authentication, authorization/permission, file server/share outage, and client mapping/cache issues before escalation.',
    ],
}

SHARED_DRIVE_ACCESS_SOLUTIONS = [
    ('FIX_SHARED_DRIVE_CONNECT_VPN','Connect to VPN or Company Network','Shared drives usually require connection to the company network or VPN.','Connect to VPN or the company network, confirm internal access, and retry the shared drive before deeper troubleshooting.',0,'Escalate to VPN or Network support if the user cannot connect to VPN or internal resources remain unreachable.','medium'),
    ('FIX_SHARED_DRIVE_PERMISSION_REQUEST','Request or Verify Shared Folder Permission','User can reach the share but does not have permission to access the folder.','Confirm the exact folder path, verify access requirements, and route an access request if approval is required.',1,'Escalate to Access Management or the folder owner if required group membership or approval is missing.','medium'),
    ('FIX_SHARED_DRIVE_REMAP','Reconnect or Remap Network Drive','The mapped drive may be disconnected, stale, or pointing to an old path.','Test the UNC path, remove stale mappings if needed, and remap the drive to the correct path.',0,'Escalate if Group Policy or login script drive mapping is failing for multiple users.','medium'),
    ('FIX_SHARED_DRIVE_CLEAR_CACHED_CREDENTIALS','Clear Saved Credentials and Sign In Again','Old or incorrect saved credentials may block access to the shared drive.','Remove old saved credentials, have the user sign out/in, and retest the UNC path.',0,'Escalate if repeated credential prompts continue or account lockout occurs.','medium'),
    ('FIX_SHARED_DRIVE_DNS_RESOLUTION','Troubleshoot File Server DNS Resolution','The computer cannot resolve the file server hostname.','Test DNS resolution for the file server hostname/FQDN, compare VPN/onsite results, and flush DNS cache when appropriate.',1,'Escalate to Network/DNS team if DNS records, VPN DNS assignment, or multiple users are affected.','high'),
    ('FIX_SHARED_DRIVE_SERVER_REACHABILITY','Escalate File Server Network Reachability Issue','The file server or share cannot be reached from the user network path.','Confirm DNS, test approved reachability, compare affected scope, and escalate with path, network, VPN status, and timestamps.',1,'Escalate to Network or Systems team if the server/share is unreachable or a routing/firewall/ACL/server issue is suspected.','high'),
    ('FIX_SHARED_DRIVE_PERMISSION_CONFIG_ESCALATE','Escalate Permission or Share Configuration Issue','User appears to have access group membership, but folder access still fails.','Confirm group membership and path, compare with a known-good user if allowed, then escalate with evidence.',1,'Escalate to Systems or Access Management for NTFS/share permission mismatch, approval, or configuration review.','high'),
    ('FIX_SHARED_DRIVE_SLOW_PERFORMANCE','Report Slow Shared Drive Performance','Shared drive is accessible but slow due to network latency, VPN, server load, file size, or sync issues.','Identify whether slowness affects one file, one share, VPN only, onsite too, or multiple users, then escalate with timing and scope.',1,'Escalate to Network or Systems team if multiple users, server load, VPN latency, or storage issues are suspected.','medium'),
]

SHARED_DRIVE_ACCESS_SOLUTION_STEPS = {
    'FIX_SHARED_DRIVE_CONNECT_VPN': {
        'user': ['Connect to the company VPN if working remotely.','Wait until VPN shows connected.','Try opening the shared drive again.','If VPN will not connect, use the VPN troubleshooting flow.'],
        'technician': ['Confirm whether the user is remote or onsite.','Confirm VPN status and internal network access.','Check whether other internal resources work.','Continue shared-drive troubleshooting after network access is confirmed.'],
        'admin': ['Escalate to VPN or Network support if the user cannot establish VPN or cannot reach any internal resources after VPN connects.'],
    },
    'FIX_SHARED_DRIVE_PERMISSION_REQUEST': {
        'user': ['Confirm the folder path you need.','Ask your manager or folder owner to approve access if required.','Submit a ticket with the folder path and business reason.','Sign out and back in after access is granted.'],
        'technician': ['Confirm the exact folder/share path.','Confirm whether the error is Access Denied.','Check the required access group or folder owner if known.','Verify whether the user is in the correct group.','Submit or route an access request if approval is required.','Ask the user to sign out/in after group membership changes.'],
        'admin': ['Escalate to Access Management or the folder owner when approval, group membership, or protected-folder access is required.'],
    },
    'FIX_SHARED_DRIVE_REMAP': {
        'user': ['Restart your computer.','Try opening the shared location again.','If you know the folder path, try opening it directly.','Contact IT if the drive is still missing or disconnected.'],
        'technician': ['Confirm the drive letter and UNC path.','Test the UNC path directly.','Remove stale mappings if needed.','Re-map the drive to the correct path.','Check whether Group Policy or login script drive mapping should apply.'],
        'admin': ['Escalate if drive mappings fail for multiple users or managed Group Policy/login script deployment appears broken.'],
    },
    'FIX_SHARED_DRIVE_CLEAR_CACHED_CREDENTIALS': {
        'user': ['Sign out and sign back in.','If prompted, enter your current company username and password.','Do not repeatedly try old passwords.','Contact IT if the credential prompt returns.'],
        'technician': ['Check whether Windows Credential Manager or saved credentials are being used.','Remove old saved credentials for the file server if appropriate.','Have the user sign out/in.','Retest the UNC path.','Watch for account lockout caused by repeated old-password attempts.'],
        'admin': ['Escalate if credential prompts continue after cached credentials are cleared or if repeated lockouts suggest a wider authentication issue.'],
    },
    'FIX_SHARED_DRIVE_DNS_RESOLUTION': {
        'user': ['Confirm VPN is connected if remote.','Try again after reconnecting VPN.','Submit a ticket with the shared drive path and screenshot.'],
        'technician': ['Test DNS resolution for the file server hostname and FQDN.','Compare DNS results while connected to VPN and from onsite network if possible.','Confirm DNS servers assigned to the VPN or network adapter.','Flush DNS cache if appropriate.','Escalate to Network/DNS team if multiple users or DNS records are affected.'],
        'admin': ['Escalate to Network/DNS team with hostname, FQDN, DNS server used, VPN status, nslookup results, affected scope, and timestamps.'],
    },
    'FIX_SHARED_DRIVE_SERVER_REACHABILITY': {
        'user': ['Record the error message.','Note whether you are remote, onsite, or connected to VPN.','Ask whether coworkers have the same issue.','Submit a ticket with the folder path and screenshot.'],
        'technician': ['Confirm DNS resolves the file server.','Test approved reachability to the file server.','Check whether the issue affects one user, one network segment, or multiple users.','Compare onsite versus VPN behavior if possible.','Escalate to Network or Systems team with DNS results, path, user network, VPN status, timestamps, and affected scope.'],
        'admin': ['Escalate to Network or Systems team when the file server/share is unreachable, the VPN subnet cannot reach the server subnet, SMB appears blocked, or multiple users are affected.'],
    },
    'FIX_SHARED_DRIVE_PERMISSION_CONFIG_ESCALATE': {
        'user': ['Provide the exact folder path.','Provide the error screenshot.','Confirm whether coworkers with the same role can access it.','Wait for IT or the folder owner to verify access.'],
        'technician': ['Confirm the user group membership.','Confirm the folder/share path.','Compare access with another user in the same group if allowed.','Check whether sign-out/in or group token refresh is needed.','Escalate to Systems/Access Management with path, username, group membership, error, and approval details.'],
        'admin': ['Escalate to Systems or Access Management for NTFS/share permission mismatch, group membership mismatch, DFS/share configuration, or protected-folder approval review.'],
    },
    'FIX_SHARED_DRIVE_SLOW_PERFORMANCE': {
        'user': ['Try opening a smaller file from the same share.','Note whether the issue happens only on VPN or also onsite.','Record the time of the slowdown.','Submit a ticket if the issue continues.'],
        'technician': ['Confirm whether the issue is one file, one folder, one share, or all shares.','Compare VPN versus onsite performance if possible.','Check basic network latency to internal resources.','Ask whether multiple users are affected.','Escalate with timestamps, file path, file size, network type, and affected scope.'],
        'admin': ['Escalate to Network or Systems team if performance affects multiple users, a department share, VPN path, server load, or storage subsystem.'],
    },
}

SHARED_DRIVE_USER_DIAGNOSTIC_NODES = [
    ('ROOT_SHARED_DRIVE_USER',None,'category','Shared Drive / Network Drive Access Issue','User cannot access a shared drive, mapped network drive, file server folder, or shared company location.',None,None,None,None,1),
    ('Q_SHARED_VPN_CONNECTED_USER','ROOT_SHARED_DRIVE_USER','question','Check Company Network or VPN',None,'Are you connected to the company network or VPN?',None,None,None,1),
    ('S_SHARED_CONNECT_VPN_USER','Q_SHARED_VPN_CONNECTED_USER','solution','Connect to VPN or Company Network',None,None,'Are you connected to the company network or VPN?','No','FIX_SHARED_DRIVE_CONNECT_VPN',1),
    ('Q_SHARED_ERROR_TYPE_USER','Q_SHARED_VPN_CONNECTED_USER','question','Identify Shared Drive Error',None,'What error do you see?','Are you connected to the company network or VPN?','Yes',None,2),
    ('S_SHARED_PERMISSION_USER','Q_SHARED_ERROR_TYPE_USER','solution','Request or Verify Shared Folder Permission',None,None,'What error do you see?','Access denied','FIX_SHARED_DRIVE_PERMISSION_REQUEST',1),
    ('S_SHARED_SERVER_REACHABILITY_USER','Q_SHARED_ERROR_TYPE_USER','solution','Report Network Path or File Server Reachability Issue',None,None,'What error do you see?','Network path not found','FIX_SHARED_DRIVE_SERVER_REACHABILITY',2),
    ('S_SHARED_REMAP_USER','Q_SHARED_ERROR_TYPE_USER','solution','Reconnect or Remap Network Drive',None,None,'What error do you see?','Drive disconnected / red X','FIX_SHARED_DRIVE_REMAP',3),
    ('S_SHARED_CACHED_CREDS_USER','Q_SHARED_ERROR_TYPE_USER','solution','Clear Saved Credentials and Sign In Again',None,None,'What error do you see?','Credentials prompt','FIX_SHARED_DRIVE_CLEAR_CACHED_CREDENTIALS',4),
    ('S_SHARED_SLOW_USER','Q_SHARED_ERROR_TYPE_USER','solution','Report Slow Shared Drive Performance',None,None,'What error do you see?','Slow access','FIX_SHARED_DRIVE_SLOW_PERFORMANCE',5),
]

SHARED_DRIVE_TECH_DIAGNOSTIC_NODES = [
    ('ROOT_SHARED_DRIVE_TECH',None,'category','Shared Drive / Network Drive Access Issue - IT Support Specialist Diagnostic','IT Support Specialist diagnostic tree for shared drive permissions, DNS, reachability, VPN, and mapping issues.',None,None,None,None,1),
    ('Q_SHARED_REMOTE_VPN_TECH','ROOT_SHARED_DRIVE_TECH','question','Confirm VPN or Onsite Access',None,'Is the user remote and connected to VPN?',None,None,None,1),
    ('S_SHARED_CONNECT_VPN_TECH','Q_SHARED_REMOTE_VPN_TECH','solution','Connect User to VPN Before Testing Shared Drive',None,None,'Is the user remote and connected to VPN?','No','FIX_SHARED_DRIVE_CONNECT_VPN',1),
    ('Q_SHARED_DNS_TECH','Q_SHARED_REMOTE_VPN_TECH','question','Check File Server DNS',None,'Does DNS resolve the file server hostname?','Is the user remote and connected to VPN?','Yes / Onsite',None,2),
    ('S_SHARED_DNS_TECH','Q_SHARED_DNS_TECH','solution','Troubleshoot File Server DNS Resolution',None,None,'Does DNS resolve the file server hostname?','No','FIX_SHARED_DRIVE_DNS_RESOLUTION',1),
    ('Q_SHARED_REACHABILITY_TECH','Q_SHARED_DNS_TECH','question','Check File Server Reachability',None,'Can the file server be reached by approved connectivity test?','Does DNS resolve the file server hostname?','Yes',None,2),
    ('S_SHARED_REACHABILITY_TECH','Q_SHARED_REACHABILITY_TECH','solution','Escalate File Server Network Reachability Issue',None,None,'Can the file server be reached by approved connectivity test?','No','FIX_SHARED_DRIVE_SERVER_REACHABILITY',1),
    ('Q_SHARED_ACCESS_DENIED_TECH','Q_SHARED_REACHABILITY_TECH','question','Separate Permissions from Connectivity',None,'Is the error Access Denied?','Can the file server be reached by approved connectivity test?','Yes',None,2),
    ('Q_SHARED_GROUP_TECH','Q_SHARED_ACCESS_DENIED_TECH','question','Check Access Group',None,'Is the user in the required access group?','Is the error Access Denied?','Yes',None,1),
    ('S_SHARED_PERMISSION_REQUEST_TECH','Q_SHARED_GROUP_TECH','solution','Verify or Request Shared Folder Permission',None,None,'Is the user in the required access group?','No / Not sure','FIX_SHARED_DRIVE_PERMISSION_REQUEST',1),
    ('S_SHARED_PERMISSION_CONFIG_TECH','Q_SHARED_GROUP_TECH','solution','Escalate Permission or Share Configuration Issue',None,None,'Is the user in the required access group?','Yes','FIX_SHARED_DRIVE_PERMISSION_CONFIG_ESCALATE',2),
    ('S_SHARED_REMAP_TECH','Q_SHARED_ACCESS_DENIED_TECH','solution','Reconnect or Recreate Mapped Drive',None,None,'Is the error Access Denied?','No','FIX_SHARED_DRIVE_REMAP',2),
]

def seed_shared_drive_access_content(cursor):
    """Seed Shared Drive / Network Drive Access Issue KB article, solutions, steps, and diagnostic trees."""
    code_, title, category, severity, description = SHARED_DRIVE_ACCESS_PROBLEM
    cursor.execute("""
        INSERT INTO problem (problem_code, title, category, severity, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(problem_code) DO UPDATE SET
            title=excluded.title, category=excluded.category, severity=excluded.severity,
            description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, SHARED_DRIVE_ACCESS_PROBLEM)
    cursor.execute('SELECT problem_id FROM problem WHERE problem_code = ?', (code_,))
    row = cursor.fetchone()
    if not row:
        return
    problem_id = row['problem_id']
    cursor.execute("""
        INSERT INTO kb_article (problem_id, title, summary, difficulty, estimated_time, escalation_required, escalation_notes, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, difficulty=excluded.difficulty,
            estimated_time=excluded.estimated_time, escalation_required=excluded.escalation_required,
            escalation_notes=excluded.escalation_notes, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, SHARED_DRIVE_ACCESS_KB['title'], SHARED_DRIVE_ACCESS_KB['summary'], SHARED_DRIVE_ACCESS_KB['difficulty'], SHARED_DRIVE_ACCESS_KB['estimated_time'], SHARED_DRIVE_ACCESS_KB['escalation_required'], SHARED_DRIVE_ACCESS_KB['escalation_notes']))
    cursor.execute('SELECT kb_article_id FROM kb_article WHERE problem_id = ?', (problem_id,))
    article = cursor.fetchone()
    if article:
        kb_id = article['kb_article_id']
        delete_kb_child_rows(cursor, kb_id)
        insert_kb_child_rows(cursor, 'kb_article_tag', 'tag', kb_id, SHARED_DRIVE_ACCESS_KB['tags'])
        insert_kb_child_rows(cursor, 'kb_article_symptom', 'symptom', kb_id, SHARED_DRIVE_ACCESS_KB['symptoms'])
        insert_kb_child_rows(cursor, 'kb_article_cause', 'cause', kb_id, SHARED_DRIVE_ACCESS_KB['causes'])
        insert_kb_child_rows(cursor, 'kb_article_user_step', 'step_text', kb_id, SHARED_DRIVE_ACCESS_KB['user_steps'])
        insert_kb_child_rows(cursor, 'kb_article_it_step', 'step_text', kb_id, SHARED_DRIVE_ACCESS_KB['it_steps'])
    cursor.executemany("""
        INSERT INTO solution (solution_code, title, summary, resolution_steps, escalation_required, escalation_notes, priority_recommendation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(solution_code) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, resolution_steps=excluded.resolution_steps,
            escalation_required=excluded.escalation_required, escalation_notes=excluded.escalation_notes,
            priority_recommendation=excluded.priority_recommendation, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, SHARED_DRIVE_ACCESS_SOLUTIONS)
    for solution_code, audience_steps in SHARED_DRIVE_ACCESS_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue
        for audience, steps in audience_steps.items():
            cursor.execute('DELETE FROM solution_step WHERE solution_id = ? AND audience = ?', (solution_id, audience))
            cursor.executemany('INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)', [(solution_id, audience, step, idx) for idx, step in enumerate(steps, start=1)])
    seed_shared_drive_access_tree(cursor, 'user', 'SHARED_DRIVE_NETWORK_DRIVE_ACCESS_ISSUE_USER', 'Shared Drive / Network Drive Access Issue - User Diagnostic', 'User-friendly diagnostic tree for missing drives, Access Denied, Network Path Not Found, credentials, and slow shared drive access.', SHARED_DRIVE_USER_DIAGNOSTIC_NODES)
    seed_shared_drive_access_tree(cursor, 'technician', 'SHARED_DRIVE_NETWORK_DRIVE_ACCESS_ISSUE_TECHNICIAN', 'Shared Drive / Network Drive Access Issue - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for VPN, DNS, reachability, permissions, and mapped-drive root-cause isolation.', SHARED_DRIVE_TECH_DIAGNOSTIC_NODES)

def seed_shared_drive_access_tree(cursor, audience, tree_code, title, description, nodes):
    problem_id = get_problem_id_for_tree_code(cursor, 'SHARED_DRIVE_NETWORK_DRIVE_ACCESS_ISSUE')
    cursor.execute("""
        INSERT INTO diagnostic_tree (problem_id, diagnostic_tree_code, base_tree_code, audience, title, description, is_active, updated_at)
        VALUES (?, ?, 'SHARED_DRIVE_NETWORK_DRIVE_ACCESS_ISSUE', ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(diagnostic_tree_code) DO UPDATE SET
            problem_id=excluded.problem_id, base_tree_code=excluded.base_tree_code, audience=excluded.audience,
            title=excluded.title, description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, tree_code, audience, title, description))
    tree_id = get_diagnostic_tree_id_by_code(cursor, tree_code)
    if not tree_id:
        return
    cursor.execute('UPDATE diagnostic_node SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE diagnostic_tree_id = ?', (tree_id,))
    for node_key, parent_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_code, sort_order in nodes:
        parent_id = get_diagnostic_node_id_by_tree_and_key(cursor, tree_id, parent_key) if parent_key else None
        solution_id = get_solution_id_by_code(cursor, solution_code) if solution_code else None
        cursor.execute("""
            INSERT INTO diagnostic_node (
                diagnostic_tree_id, parent_diagnostic_node_id, problem_id, diagnostic_tree_code,
                node_key, node_type, title, description, prompt_text,
                condition_label, condition_value, solution_id, sort_order, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(diagnostic_tree_code, node_key) DO UPDATE SET
                diagnostic_tree_id=excluded.diagnostic_tree_id,
                parent_diagnostic_node_id=excluded.parent_diagnostic_node_id,
                problem_id=excluded.problem_id,
                node_type=excluded.node_type,
                title=excluded.title,
                description=excluded.description,
                prompt_text=excluded.prompt_text,
                condition_label=excluded.condition_label,
                condition_value=excluded.condition_value,
                solution_id=excluded.solution_id,
                sort_order=excluded.sort_order,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (tree_id, parent_id, problem_id, tree_code, node_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_id, sort_order))


# -----------------------------
# REMOTE DESKTOP CONNECTION ISSUE CONTENT
# -----------------------------
REMOTE_DESKTOP_CONNECTION_PROBLEM = (
    'REMOTE_DESKTOP_CONNECTION_ISSUE',
    'Remote Desktop Connection Issue',
    'Network, Remote Access & Storage',
    'medium',
    'User cannot connect to a remote computer, server, virtual desktop, or remote desktop session.',
)

REMOTE_DESKTOP_CONNECTION_KB = {
    'title': 'Remote Desktop Connection Issue',
    'summary': 'Use this guide when Remote Desktop cannot connect, credentials fail, access is denied, the session disconnects, or remote desktop performance is slow.',
    'difficulty': 'Intermediate',
    'estimated_time': '10-20 minutes',
    'escalation_required': 1,
    'escalation_notes': 'Escalate if VPN/internal access is broken, DNS or reachability fails, remote logon permission is missing, the RDP service or gateway is unavailable, or multiple users are affected.',
    'tags': ['remote desktop', 'RDP', 'remote access', 'VPN', 'DNS', 'firewall', 'ACL', 'credentials', 'remote host', 'gateway'],
    'symptoms': [
        'Remote Desktop will not connect or says the remote computer cannot be found.',
        'Credentials are rejected or the user is not allowed to log on remotely.',
        'The remote desktop session connects and then disconnects, shows a black screen, or is very slow.',
        'VPN is connected, but the user cannot reach the office computer, server, or virtual desktop.',
        'Remote Desktop works from one network but fails from another.',
        'The issue started after a password change, device change, VPN issue, or network update.',
        'Multiple users cannot connect to the same remote desktop gateway, server, or environment.',
    ],
    'causes': [
        'Common: missing VPN/internal access, incorrect remote computer name or IP, target computer powered off or asleep, account locked or password expired, old saved credentials, missing remote logon permission, Remote Desktop disabled, local or remote firewall block, or network path unavailable.',
        'Advanced: stale DNS record, DHCP/DNS mismatch, RDP service stopped, Remote Desktop Gateway issue, network ACL blocking RDP from VPN subnet, routing issue between VPN pool and endpoint subnet, endpoint compliance block, NLA/CredSSP issue, gateway certificate problem, duplicate IP, wrong VLAN, or security policy restricting remote logon rights.',
    ],
    'user_steps': [
        'Confirm you are connected to the company VPN if working remotely.',
        'Confirm the remote computer name or server name is correct.',
        'Check whether you can access other internal resources.',
        'Restart the Remote Desktop app and try again.',
        'Make sure your username is entered in the correct format if required.',
        'If prompted, use your current company password.',
        'Do not repeatedly retry old passwords if credentials fail.',
        'If connecting to your office computer, confirm it is powered on and connected to the network.',
        'Take a screenshot of the exact error message.',
        'Submit a ticket with the remote computer name, error message, and whether VPN is connected.',
    ],
    'it_steps': [
        'Tier 1: Confirm the user, device name, location, remote target name, VPN status, and exact error message.',
        'Tier 1: Identify whether the user is connecting directly to an office computer, through a Remote Desktop Gateway, to a virtual desktop, or to a server.',
        'Tier 1: Confirm normal internet and VPN are working before isolating Remote Desktop.',
        'Tier 1: Confirm whether the user can access other internal resources.',
        'Tier 1: Confirm the remote hostname/IP is correct and whether the target computer should be powered on.',
        'Tier 1: Check account status, including locked account, expired password, disabled account, MFA/conditional access issue, and recent password changes.',
        'Tier 1: Remove or update old saved RDP credentials if needed.',
        'Tier 1: Capture the error message, timestamp, target name, and source network.',
        'Tier 2: Test DNS resolution for the remote host and compare hostname vs FQDN resolution.',
        'Tier 2: Check whether the remote host responds to approved reachability tests.',
        'Tier 2: Confirm the user VPN adapter has valid IP, DNS, and routes.',
        'Tier 2: Check whether the remote host subnet is reachable from the user VPN segment.',
        'Tier 2: Test whether the RDP port/service is reachable according to company tools and policy.',
        'Tier 2: Determine whether the issue is DNS, device offline, authentication, authorization, firewall/ACL, routing, RDP service, or gateway/service outage.',
        'Tier 2: Check for local subnet overlap if the remote user is on a home network.',
        'Tier 2: If the remote computer is reachable but RDP fails, check whether Remote Desktop is enabled and the service is running.',
        'Tier 2: If multiple users are affected, check for gateway, VPN, firewall, or network outage.',
        'Escalate with target hostname, IP, VPN status, DNS result, reachability tests, error text, timestamp, and affected scope.',
    ],
}

REMOTE_DESKTOP_CONNECTION_SOLUTIONS = [
    ('FIX_RDP_CONNECT_VPN_FIRST','Connect to VPN Before Remote Desktop','Remote Desktop usually requires VPN or approved internal network access before connecting.','Connect to VPN or approved remote access, confirm internal access, and retry Remote Desktop.',0,'Escalate or route to VPN troubleshooting if VPN or approved remote access does not work.','medium'),
    ('FIX_RDP_INTERNAL_ACCESS_FIRST','Fix VPN/Internal Network Access First','Remote Desktop cannot be isolated until VPN/internal network access is working.','Confirm VPN adapter IP, DNS, routes, and access to another internal resource before continuing RDP troubleshooting.',1,'Escalate if VPN, DNS, routing, or internal access is broken for the user or multiple users.','high'),
    ('FIX_RDP_VERIFY_TARGET_REACHABILITY','Verify Remote Computer Name and Reachability','The remote computer may be offline, incorrectly named, or unreachable.','Confirm target hostname/FQDN/IP, test DNS and approved reachability, and determine whether the target is offline or blocked.',1,'Escalate if the target device or subnet is unreachable, DNS is incorrect, or the remote host appears offline.','medium'),
    ('FIX_RDP_ACCOUNT_SAVED_CREDENTIALS','Check Account, Password, and Saved RDP Credentials','Old saved credentials or account problems may prevent Remote Desktop sign-in.','Check account status, username format, saved credentials, and route to password/account troubleshooting if needed.',0,'Escalate if account policy, conditional access, or identity permissions block Remote Desktop access.','medium'),
    ('FIX_RDP_PERMISSION_REVIEW','Verify Remote Desktop Permission','The user may not have permission to log on remotely to the target system.','Confirm target, access purpose, group membership, and approval requirements for remote logon.',1,'Escalate to Identity/Access Management or system owner if group membership or remote logon rights are missing.','medium'),
    ('FIX_RDP_DNS_RESOLUTION','Troubleshoot Remote Host DNS Resolution','The remote host cannot be resolved by name.','Test DNS resolution for hostname and FQDN, compare expected IP when known, and flush DNS cache when appropriate.',1,'Escalate if DNS records are stale, missing, or multiple users are affected.','high'),
    ('FIX_RDP_REACHABILITY_ESCALATE','Escalate Remote Host or Network Reachability Issue','The remote host is not reachable from the user network path.','Confirm DNS resolution, test approved reachability, compare VPN/onsite access, and escalate with evidence.',1,'Escalate to Endpoint, Network, or Systems team depending on whether the host, subnet, firewall/ACL, or gateway is suspected.','high'),
    ('FIX_RDP_SERVICE_GATEWAY_SESSION','Troubleshoot RDP Service, Gateway, or Session Issue','The remote host is reachable, but Remote Desktop itself fails due to service, gateway, firewall, or session problems.','Confirm target reachability, RDP service/gateway status, firewall/security policy, and affected scope.',1,'Escalate to Endpoint, Systems, Network, or VDI/Gateway support with evidence.','high'),
    ('FIX_RDP_SLOW_PERFORMANCE','Report Slow Remote Desktop Performance','Remote Desktop connects but performs slowly due to network latency, VPN performance, remote host load, or gateway issue.','Determine scope, compare source networks, check basic latency/packet loss, and escalate with timestamps and affected scope.',1,'Escalate if multiple users, gateway performance, VPN latency, or remote host resource issues are suspected.','medium'),
]

REMOTE_DESKTOP_CONNECTION_SOLUTION_STEPS = {
    'FIX_RDP_CONNECT_VPN_FIRST': {
        'user': ['Connect to the company VPN or approved remote access service.', 'Wait until the connection shows connected.', 'Try Remote Desktop again.', 'If VPN fails, use the VPN troubleshooting flow.'],
        'technician': ['Confirm whether the user is remote or onsite.', 'Confirm VPN connection status.', 'Confirm internal resources are reachable before RDP testing.', 'Route to VPN troubleshooting if VPN does not work.'],
        'admin': ['Escalate if approved remote access is unavailable or multiple users cannot connect.'],
    },
    'FIX_RDP_INTERNAL_ACCESS_FIRST': {
        'user': ['Confirm VPN shows connected.', 'Try opening an internal website or shared drive.', 'If internal resources do not work, submit a ticket with VPN status and screenshots.'],
        'technician': ['Confirm VPN adapter IP, DNS, and routes.', 'Test access to another internal resource.', 'Determine whether issue is VPN, DNS, routing, or RDP-specific.', 'Continue RDP troubleshooting after internal network access is confirmed.'],
        'admin': ['Escalate to Network or VPN support if internal access fails across resources or multiple users are affected.'],
    },
    'FIX_RDP_VERIFY_TARGET_REACHABILITY': {
        'user': ['Confirm the remote computer name is typed correctly.', 'Confirm the computer should be powered on.', 'Try again after connecting to VPN.', 'Send IT the exact computer name and error message.'],
        'technician': ['Confirm target hostname, FQDN, or IP.', 'Test DNS resolution for the remote host.', 'Check approved reachability to the remote host.', 'Determine whether target is offline, DNS is wrong, or network path is blocked.', 'Escalate if the device or subnet is unreachable.'],
        'admin': ['Escalate with target hostname/IP, DNS result, reachability test, source network, VPN status, and timestamp.'],
    },
    'FIX_RDP_ACCOUNT_SAVED_CREDENTIALS': {
        'user': ['Confirm your username is entered correctly.', 'Use your current company password.', 'If you recently changed your password, remove old saved credentials.', 'Avoid repeated failed attempts to prevent account lockout.'],
        'technician': ['Check whether the account is locked, disabled, or password expired.', 'Confirm username format required for RDP.', 'Remove or update saved RDP credentials.', 'Retest login after credential cleanup.', 'Route to Password Reset or Account Locked troubleshooting if needed.'],
        'admin': ['Escalate if identity policy, conditional access, or remote gateway authentication blocks access.'],
    },
    'FIX_RDP_PERMISSION_REVIEW': {
        'user': ['Send IT the exact remote computer/server name.', 'Provide the access reason and manager approval if required.', 'Wait for confirmation before retrying.'],
        'technician': ['Confirm the target system and access purpose.', 'Check whether the user is allowed to use remote desktop for that device/system.', 'Verify group membership or Remote Desktop Users permission if accessible.', 'Route access request if approval is required.', 'Ask user to sign out/in after permission changes if needed.'],
        'admin': ['Escalate to Access Management or the system owner if remote logon rights or group membership must be changed.'],
    },
    'FIX_RDP_DNS_RESOLUTION': {
        'user': ['Confirm VPN is connected.', 'Confirm the remote computer name with IT.', 'Submit the exact error screenshot.'],
        'technician': ['Test DNS resolution for hostname and FQDN.', 'Compare DNS result with expected IP if known.', 'Flush DNS cache if appropriate.', 'Check whether the remote device recently changed networks.', 'Escalate if DNS records are stale, missing, or multiple users are affected.'],
        'admin': ['Escalate to Network/DNS or Endpoint team with hostname, FQDN, DNS output, expected IP if known, and affected scope.'],
    },
    'FIX_RDP_REACHABILITY_ESCALATE': {
        'user': ['Provide the remote computer/server name.', 'Confirm whether you are remote or onsite.', 'Provide the exact error screenshot.', 'Wait for IT to verify the device or network path.'],
        'technician': ['Confirm DNS resolves the remote host.', 'Test approved reachability to the target.', 'Check whether issue affects one user, one target, one subnet, or multiple users.', 'Compare VPN and onsite access if possible.', 'Escalate with source network, target hostname/IP, VPN status, timestamps, and test results.'],
        'admin': ['Route to Endpoint, Network, or Systems team based on whether the evidence points to host availability, routing/firewall/ACL, or server/gateway reachability.'],
    },
    'FIX_RDP_SERVICE_GATEWAY_SESSION': {
        'user': ['Take a screenshot of the error or black screen.', 'Note whether the connection fails immediately or after login.', 'Submit the target name and time of failure.'],
        'technician': ['Confirm target is reachable but RDP fails.', 'Check whether RDP service/gateway is available according to support tools.', 'Confirm firewall/security policy is not blocking the session.', 'Check whether multiple users are affected.', 'Escalate to Endpoint, Systems, or Network team with evidence.'],
        'admin': ['Escalate to Endpoint, Systems, Network, or VDI/Gateway support with the target, user, timestamp, error, and affected scope.'],
    },
    'FIX_RDP_SLOW_PERFORMANCE': {
        'user': ['Close unnecessary apps inside the remote session.', 'Try again from a stable network.', 'Record when the slowness happens.', 'Report whether other remote apps are also slow.'],
        'technician': ['Determine whether slowness affects one user, one remote host, or many users.', 'Compare performance from VPN, onsite, and alternate network if possible.', 'Check basic latency and packet loss to internal resources.', 'Ask whether remote host CPU/memory load is high if endpoint tools are available.', 'Escalate with timestamps, source network, target host, and affected scope.'],
        'admin': ['Escalate if slowness suggests VPN, gateway, remote host resource, or network path performance issues.'],
    },
}

REMOTE_DESKTOP_USER_DIAGNOSTIC_NODES = [
    ('ROOT_RDP_USER',None,'category','Remote Desktop Connection Issue','User cannot connect to a remote computer, server, virtual desktop, or remote desktop session.',None,None,None,None,1),
    ('Q_RDP_VPN_CONNECTED_USER','ROOT_RDP_USER','question','Check Remote Access Connection',None,'Are you connected to VPN or approved remote access?',None,None,None,1),
    ('S_RDP_CONNECT_VPN_USER','Q_RDP_VPN_CONNECTED_USER','solution','Connect to VPN Before Remote Desktop',None,None,'Are you connected to VPN or approved remote access?','No','FIX_RDP_CONNECT_VPN_FIRST',1),
    ('Q_RDP_INTERNAL_ACCESS_USER','Q_RDP_VPN_CONNECTED_USER','question','Check Internal Access',None,'Can you access other internal resources?', 'Are you connected to VPN or approved remote access?','Yes',None,2),
    ('S_RDP_INTERNAL_ACCESS_USER','Q_RDP_INTERNAL_ACCESS_USER','solution','Fix VPN/Internal Network Access First',None,None,'Can you access other internal resources?','No','FIX_RDP_INTERNAL_ACCESS_FIRST',1),
    ('Q_RDP_ERROR_TYPE_USER','Q_RDP_INTERNAL_ACCESS_USER','question','Identify Remote Desktop Error',None,'What error do you see?', 'Can you access other internal resources?','Yes',None,2),
    ('S_RDP_TARGET_USER','Q_RDP_ERROR_TYPE_USER','solution','Verify Remote Computer Name and Reachability',None,None,'What error do you see?','Remote computer not found','FIX_RDP_VERIFY_TARGET_REACHABILITY',1),
    ('S_RDP_CREDS_USER','Q_RDP_ERROR_TYPE_USER','solution','Check Account, Password, and Saved Credentials',None,None,'What error do you see?','Credentials did not work','FIX_RDP_ACCOUNT_SAVED_CREDENTIALS',2),
    ('S_RDP_PERMISSION_USER','Q_RDP_ERROR_TYPE_USER','solution','Request Remote Desktop Permission Review',None,None,'What error do you see?','Not allowed to log on remotely','FIX_RDP_PERMISSION_REVIEW',3),
    ('S_RDP_SESSION_USER','Q_RDP_ERROR_TYPE_USER','solution','Report Remote Session or Endpoint Issue',None,None,'What error do you see?','Black screen / disconnects','FIX_RDP_SERVICE_GATEWAY_SESSION',4),
    ('S_RDP_SLOW_USER','Q_RDP_ERROR_TYPE_USER','solution','Report Slow Remote Desktop Performance',None,None,'What error do you see?','Slow session','FIX_RDP_SLOW_PERFORMANCE',5),
]

REMOTE_DESKTOP_TECH_DIAGNOSTIC_NODES = [
    ('ROOT_RDP_TECH',None,'category','Remote Desktop Connection Issue - IT Support Specialist Diagnostic','IT Support Specialist diagnostic tree for VPN dependency, DNS, reachability, credentials, permissions, RDP service, and gateway issues.',None,None,None,None,1),
    ('Q_RDP_REMOTE_ACCESS_TECH','ROOT_RDP_TECH','question','Confirm VPN or Approved Remote Access',None,'Is VPN or approved remote access connected?',None,None,None,1),
    ('S_RDP_CONNECT_VPN_TECH','Q_RDP_REMOTE_ACCESS_TECH','solution','Connect User to VPN Before RDP Testing',None,None,'Is VPN or approved remote access connected?','No','FIX_RDP_CONNECT_VPN_FIRST',1),
    ('Q_RDP_DNS_TECH','Q_RDP_REMOTE_ACCESS_TECH','question','Check Remote Host DNS',None,'Does DNS resolve the remote host?', 'Is VPN or approved remote access connected?','Yes',None,2),
    ('S_RDP_DNS_TECH','Q_RDP_DNS_TECH','solution','Troubleshoot Remote Host DNS Resolution',None,None,'Does DNS resolve the remote host?','No','FIX_RDP_DNS_RESOLUTION',1),
    ('Q_RDP_REACHABLE_TECH','Q_RDP_DNS_TECH','question','Check Remote Host Reachability',None,'Is the remote host reachable?', 'Does DNS resolve the remote host?','Yes',None,2),
    ('S_RDP_REACHABILITY_TECH','Q_RDP_REACHABLE_TECH','solution','Escalate Remote Host or Network Reachability Issue',None,None,'Is the remote host reachable?','No','FIX_RDP_REACHABILITY_ESCALATE',1),
    ('Q_RDP_AUTH_TECH','Q_RDP_REACHABLE_TECH','question','Separate Authentication from Network',None,'Is the error authentication or credentials related?', 'Is the remote host reachable?','Yes',None,2),
    ('S_RDP_CREDS_TECH','Q_RDP_AUTH_TECH','solution','Check Account and Saved RDP Credentials',None,None,'Is the error authentication or credentials related?','Yes','FIX_RDP_ACCOUNT_SAVED_CREDENTIALS',1),
    ('Q_RDP_PERMISSION_TECH','Q_RDP_AUTH_TECH','question','Check Remote Logon Permission',None,'Does the user have remote logon permission?', 'Is the error authentication or credentials related?','No',None,2),
    ('S_RDP_PERMISSION_TECH','Q_RDP_PERMISSION_TECH','solution','Verify Remote Desktop Permission',None,None,'Does the user have remote logon permission?','No / Not sure','FIX_RDP_PERMISSION_REVIEW',1),
    ('S_RDP_SERVICE_TECH','Q_RDP_PERMISSION_TECH','solution','Troubleshoot RDP Service, Gateway, or Session Issue',None,None,'Does the user have remote logon permission?','Yes','FIX_RDP_SERVICE_GATEWAY_SESSION',2),
]

def seed_remote_desktop_connection_content(cursor):
    """Seed Remote Desktop Connection Issue KB article, solutions, steps, and diagnostic trees."""
    code_, title, category, severity, description = REMOTE_DESKTOP_CONNECTION_PROBLEM
    cursor.execute("""
        INSERT INTO problem (problem_code, title, category, severity, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(problem_code) DO UPDATE SET
            title=excluded.title, category=excluded.category, severity=excluded.severity,
            description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, REMOTE_DESKTOP_CONNECTION_PROBLEM)
    cursor.execute('SELECT problem_id FROM problem WHERE problem_code = ?', (code_,))
    row = cursor.fetchone()
    if not row:
        return
    problem_id = row['problem_id']
    cursor.execute("""
        INSERT INTO kb_article (problem_id, title, summary, difficulty, estimated_time, escalation_required, escalation_notes, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, difficulty=excluded.difficulty,
            estimated_time=excluded.estimated_time, escalation_required=excluded.escalation_required,
            escalation_notes=excluded.escalation_notes, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, REMOTE_DESKTOP_CONNECTION_KB['title'], REMOTE_DESKTOP_CONNECTION_KB['summary'], REMOTE_DESKTOP_CONNECTION_KB['difficulty'], REMOTE_DESKTOP_CONNECTION_KB['estimated_time'], REMOTE_DESKTOP_CONNECTION_KB['escalation_required'], REMOTE_DESKTOP_CONNECTION_KB['escalation_notes']))
    cursor.execute('SELECT kb_article_id FROM kb_article WHERE problem_id = ?', (problem_id,))
    article = cursor.fetchone()
    if article:
        kb_id = article['kb_article_id']
        delete_kb_child_rows(cursor, kb_id)
        insert_kb_child_rows(cursor, 'kb_article_tag', 'tag', kb_id, REMOTE_DESKTOP_CONNECTION_KB['tags'])
        insert_kb_child_rows(cursor, 'kb_article_symptom', 'symptom', kb_id, REMOTE_DESKTOP_CONNECTION_KB['symptoms'])
        insert_kb_child_rows(cursor, 'kb_article_cause', 'cause', kb_id, REMOTE_DESKTOP_CONNECTION_KB['causes'])
        insert_kb_child_rows(cursor, 'kb_article_user_step', 'step_text', kb_id, REMOTE_DESKTOP_CONNECTION_KB['user_steps'])
        insert_kb_child_rows(cursor, 'kb_article_it_step', 'step_text', kb_id, REMOTE_DESKTOP_CONNECTION_KB['it_steps'])
    cursor.executemany("""
        INSERT INTO solution (solution_code, title, summary, resolution_steps, escalation_required, escalation_notes, priority_recommendation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(solution_code) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, resolution_steps=excluded.resolution_steps,
            escalation_required=excluded.escalation_required, escalation_notes=excluded.escalation_notes,
            priority_recommendation=excluded.priority_recommendation, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, REMOTE_DESKTOP_CONNECTION_SOLUTIONS)
    for solution_code, audience_steps in REMOTE_DESKTOP_CONNECTION_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue
        for audience, steps in audience_steps.items():
            cursor.execute('DELETE FROM solution_step WHERE solution_id = ? AND audience = ?', (solution_id, audience))
            cursor.executemany('INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)', [(solution_id, audience, step, idx) for idx, step in enumerate(steps, start=1)])
    seed_remote_desktop_connection_tree(cursor, 'user', 'REMOTE_DESKTOP_CONNECTION_ISSUE_USER', 'Remote Desktop Connection Issue - User Diagnostic', 'User-friendly diagnostic tree for VPN dependency, internal access, common RDP errors, credentials, permissions, and performance.', REMOTE_DESKTOP_USER_DIAGNOSTIC_NODES)
    seed_remote_desktop_connection_tree(cursor, 'technician', 'REMOTE_DESKTOP_CONNECTION_ISSUE_TECHNICIAN', 'Remote Desktop Connection Issue - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for VPN, DNS, reachability, credentials, permissions, RDP service, and gateway root-cause isolation.', REMOTE_DESKTOP_TECH_DIAGNOSTIC_NODES)

def seed_remote_desktop_connection_tree(cursor, audience, tree_code, title, description, nodes):
    problem_id = get_problem_id_for_tree_code(cursor, 'REMOTE_DESKTOP_CONNECTION_ISSUE')
    cursor.execute("""
        INSERT INTO diagnostic_tree (problem_id, diagnostic_tree_code, base_tree_code, audience, title, description, is_active, updated_at)
        VALUES (?, ?, 'REMOTE_DESKTOP_CONNECTION_ISSUE', ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(diagnostic_tree_code) DO UPDATE SET
            problem_id=excluded.problem_id, base_tree_code=excluded.base_tree_code, audience=excluded.audience,
            title=excluded.title, description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, tree_code, audience, title, description))
    tree_id = get_diagnostic_tree_id_by_code(cursor, tree_code)
    if not tree_id:
        return
    cursor.execute('UPDATE diagnostic_node SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE diagnostic_tree_id = ?', (tree_id,))
    for node_key, parent_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_code, sort_order in nodes:
        parent_id = get_diagnostic_node_id_by_tree_and_key(cursor, tree_id, parent_key) if parent_key else None
        solution_id = get_solution_id_by_code(cursor, solution_code) if solution_code else None
        cursor.execute("""
            INSERT INTO diagnostic_node (
                diagnostic_tree_id, parent_diagnostic_node_id, problem_id, diagnostic_tree_code,
                node_key, node_type, title, description, prompt_text,
                condition_label, condition_value, solution_id, sort_order, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(diagnostic_tree_code, node_key) DO UPDATE SET
                diagnostic_tree_id=excluded.diagnostic_tree_id,
                parent_diagnostic_node_id=excluded.parent_diagnostic_node_id,
                problem_id=excluded.problem_id,
                node_type=excluded.node_type,
                title=excluded.title,
                description=excluded.description,
                prompt_text=excluded.prompt_text,
                condition_label=excluded.condition_label,
                condition_value=excluded.condition_value,
                solution_id=excluded.solution_id,
                sort_order=excluded.sort_order,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (tree_id, parent_id, problem_id, tree_code, node_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_id, sort_order))


# -----------------------------
# SLOW COMPUTER PERFORMANCE CONTENT
# -----------------------------
SLOW_COMPUTER_PERFORMANCE_PROBLEM = (
    'SLOW_COMPUTER_PERFORMANCE',
    'Slow Computer Performance',
    'Performance & Operating System',
    'medium',
    'Computer is slow, freezes, starts slowly, opens applications slowly, or responds slowly during normal work.',
)

SLOW_COMPUTER_PERFORMANCE_KB = {
    'title': 'Slow Computer Performance',
    'summary': 'Use this guide when the computer starts slowly, freezes, opens apps slowly, has loud fan noise, shows high resource usage, or becomes slow when using VPN, shared drives, browsers, or business applications.',
    'difficulty': 'Intermediate',
    'estimated_time': '10-20 minutes',
    'escalation_required': 0,
    'escalation_notes': 'Escalate if the device is unusable, multiple users are affected, malware or hardware failure is suspected, or slowness appears tied to network/VPN/internal-resource access.',
    'tags': ['slow computer', 'performance', 'CPU', 'memory', 'disk', 'startup apps', 'Windows updates', 'malware', 'storage', 'VPN performance'],
    'symptoms': [
        'Computer takes a long time to start or sign in.',
        'Applications take a long time to open or respond.',
        'Computer freezes or becomes unresponsive.',
        'Fan is loud, laptop is hot, or performance drops during normal use.',
        'Browser, shared drives, cloud files, or video calls are slow.',
        'Device became slow after an update, new software, or recent change.',
        'Computer is slow only when connected to VPN or accessing internal resources.',
    ],
    'causes': [
        'Common: long uptime, too many startup apps, many browser tabs, low disk space, pending updates, high CPU, high memory usage, cloud sync/backup/antivirus scans, browser cache/extensions, older hardware, malware, or slow network/VPN resource access.',
        'Advanced: failing HDD/SSD, disk health warnings, thermal throttling, driver issue after update, corrupted user profile or system files, endpoint security agent conflict, insufficient RAM, background indexing, domain/GPO/login delay, network latency, DNS issues, or VPN routing problems.',
    ],
    'user_steps': [
        'Save your work and restart the computer.',
        'Close unused applications and browser tabs.',
        'Check whether the issue happens in one application or the whole computer.',
        'Check whether the computer is low on storage.',
        'Pause large downloads, cloud sync, or backup if allowed by company policy.',
        'Try using the computer while disconnected from VPN if the task does not require VPN.',
        'Make sure the laptop is plugged in and not in battery saver mode.',
        'If the fan is very loud, place the laptop on a hard surface and avoid blocking vents.',
        'Take a screenshot of any error, update, storage, or security warning.',
        'Submit a ticket if the computer is still slow after restart or freezes repeatedly.',
    ],
    'it_steps': [
        'Confirm the user, device name, operating system, location, and when the slowness started.',
        'Determine whether the issue affects the whole computer, one application, browser only, network/shared resources only, or VPN only.',
        'Ask about recent changes such as Windows update, new software, password change, device change, or VPN/client update.',
        'Check uptime and whether a restart is pending.',
        'Check CPU, memory, disk, and network usage in Task Manager.',
        'Identify top resource-consuming processes.',
        'Check available disk space.',
        'Review startup apps and disable only approved non-essential items according to policy.',
        'Check whether Windows updates are pending or recently failed.',
        'Check for malware/security alerts or suspicious processes.',
        'Ask the user to test with fewer browser tabs or extensions.',
        'Review whether the bottleneck is local device performance or network/application access.',
        'For local device issues, check disk health indicators, event logs, driver/update history, endpoint/security agent status, and thermal symptoms if tools are available.',
        'For network-related slowness, compare local apps versus network apps, test DNS for affected internal resources, check VPN adapter IP/DNS/routes if remote, and compare wired/Wi-Fi/hotspot if possible.',
        'Check whether multiple users or devices are affected.',
        'Confirm whether the issue follows the user profile, device, network, or application.',
        'Escalate with evidence if storage failure, malware, endpoint policy conflict, network latency, or server-side performance is suspected.',
    ],
}

SLOW_COMPUTER_PERFORMANCE_SOLUTIONS = [
    ('FIX_SLOW_PC_RESTART_CHECK','Restart Computer and Check Performance','A restart can clear stuck processes, apply pending updates, and reset temporary performance issues.','Restart the computer, allow startup to finish, and retest the same task.',0,'Escalate if slowness remains after restart and resource usage, errors, malware, or hardware symptoms appear.','low'),
    ('FIX_SLOW_PC_STARTUP_BACKGROUND_LOAD','Reduce Startup and Background Load','Too many startup apps or background processes can slow the device.','Close unused apps, review startup items, and reduce approved non-essential background load.',0,'Escalate if managed startup policy, endpoint agent behavior, or business-critical apps require deeper review.','medium'),
    ('FIX_SLOW_PC_STORAGE_UPDATES_SECURITY_WARNING','Address Storage, Updates, or Security Warning','Low disk space, pending updates, or security warnings can degrade performance.','Check storage, updates, and security warnings, then address each issue according to policy.',0,'Escalate to Security for malware/suspicious activity, or Endpoint/Desktop Support for failed updates or recurring low storage.','medium'),
    ('FIX_SLOW_PC_HIGH_CPU_PROCESS','Identify High CPU Process','One process may be consuming excessive CPU and slowing the system.','Identify the top CPU process, determine whether it is known/safe, restart the app if appropriate, and escalate suspicious or recurring causes.',0,'Do not terminate security or system processes without approval; escalate unknown or suspicious processes.','medium'),
    ('FIX_SLOW_PC_MEMORY_PRESSURE','Reduce Memory Pressure','Low available memory can cause freezing, paging, and slow application response.','Close memory-heavy apps and browser tabs, restart, and evaluate whether the device is under-resourced.',0,'Escalate if workload exceeds installed RAM or repeated memory pressure affects productivity.','medium'),
    ('FIX_SLOW_PC_HIGH_DISK_LOW_STORAGE','Investigate High Disk Usage or Low Storage','Disk bottlenecks or low storage can make the computer appear frozen or slow.','Check disk usage, available storage, cleanup options, sync cache, update cleanup, and disk health indicators.',0,'Escalate if disk health warnings, recurring storage shortages, or storage hardware issues appear.','medium'),
    ('FIX_SLOW_PC_BANDWIDTH_SYNC_ACTIVITY','Identify Bandwidth or Sync Activity','Cloud sync, backup, downloads, or video calls may consume network or system resources.','Identify network-heavy apps or sync activity and compare performance after pausing or completing approved tasks.',0,'Escalate if bandwidth symptoms affect multiple users, VPN, Wi-Fi, or network resources.','medium'),
    ('FIX_SLOW_PC_APPLICATION_SPECIFIC','Troubleshoot Application-Specific Slowness','Slowness isolated to one application may be caused by app cache, update, profile, server, or database issue.','Check app version, cache/profile, recent changes, and whether other users/devices are affected.',0,'Escalate to Application/System team if multiple users are affected or server-side performance is suspected.','medium'),
    ('FIX_SLOW_PC_NETWORK_VPN_PERFORMANCE','Isolate Network or VPN Performance Issue','The computer may seem slow because network, VPN, shared drive, DNS, or internal app access is slow.','Compare local apps to internal resources, check VPN adapter IP/DNS/routes, test DNS and latency with approved tools, and document affected scope.',1,'Escalate to Network/System team with VPN status, DNS results, latency/packet loss, affected resources, timestamps, and scope.','high'),
    ('FIX_SLOW_PC_ENDPOINT_SECURITY_HEALTH_ESCALATE','Escalate Endpoint Health or Security Review','Performance symptoms may indicate malware, failing hardware, thermal issues, driver problems, or endpoint policy conflict.','Collect security alerts, suspicious process details, event/health signals, disk/thermal symptoms, and recent changes before escalation.',1,'Escalate to Security or Endpoint/Desktop Support when malware, failing hardware, thermal throttling, driver conflict, or endpoint policy issue is suspected.','high'),
]

SLOW_COMPUTER_PERFORMANCE_SOLUTION_STEPS = {
    'FIX_SLOW_PC_RESTART_CHECK': {
        'user': ['Save all work.','Restart the computer.','Sign back in and wait a few minutes for startup apps to finish loading.','Test the same task again.','Submit a ticket if the computer remains slow.'],
        'technician': ['Check uptime and pending restart state.','Ask the user to restart if uptime is high or updates are pending.','Check CPU, memory, disk, and network usage in Task Manager.','Document whether restart resolved the issue.'],
        'admin': ['Escalate if performance remains poor after restart and evidence points to hardware, malware, update, or wider infrastructure issues.'],
    },
    'FIX_SLOW_PC_STARTUP_BACKGROUND_LOAD': {
        'user': ['Close applications you are not using.','Close unnecessary browser tabs.','Wait for cloud sync or backup to finish if it is running.','Restart the computer and test again.'],
        'technician': ['Review startup apps and background processes.','Identify non-essential startup items according to company policy.','Disable or remove only approved non-essential startup items.','Check whether cloud sync, backup, or antivirus scan is consuming resources.','Retest performance after changes.'],
        'admin': ['Escalate if managed startup policies, endpoint agents, or required business apps appear to be causing recurring performance issues.'],
    },
    'FIX_SLOW_PC_STORAGE_UPDATES_SECURITY_WARNING': {
        'user': ['Take a screenshot of the warning.','Empty Recycle Bin/Trash if allowed.','Move large personal files to approved storage if appropriate.','Restart after updates complete.','Contact IT if a security warning appears.'],
        'technician': ['Check available disk space.','Use approved cleanup tools.','Check pending or failed updates.','Review security alerts.','Escalate to Security if malware or suspicious activity is suspected.'],
        'admin': ['Escalate to Endpoint/Desktop Support for failed update loops or recurring storage issues; escalate to Security for malware indicators.'],
    },
    'FIX_SLOW_PC_HIGH_CPU_PROCESS': {
        'user': ['Close unused applications.','Restart the affected app if safe.','Report if the fan is loud or the computer freezes.'],
        'technician': ['Use Task Manager or approved endpoint tools to identify the top CPU process.','Determine whether the process is a known app, system process, security tool, or unknown process.','Restart the application if safe.','Do not terminate security/system processes without approval.','Escalate if the process is suspicious or repeatedly causes high CPU.'],
        'admin': ['Escalate to Security for suspicious processes or to Application/Endpoint teams for recurring high CPU from known business or system processes.'],
    },
    'FIX_SLOW_PC_MEMORY_PRESSURE': {
        'user': ['Close unused applications and browser tabs.','Restart the computer.','Avoid opening many heavy applications at the same time.'],
        'technician': ['Check memory usage and top memory-consuming apps.','Compare installed RAM with workload needs.','Check whether browser tabs/extensions are consuming memory.','Retest after closing unnecessary apps.','Escalate if the device is under-resourced for the role.'],
        'admin': ['Escalate for hardware upgrade, replacement, or application review if the workload consistently exceeds available memory.'],
    },
    'FIX_SLOW_PC_HIGH_DISK_LOW_STORAGE': {
        'user': ['Close unnecessary apps.','Delete only files you know are safe to remove.','Move approved files to company cloud or network storage.','Contact IT if storage remains low.'],
        'technician': ['Check disk usage percentage and available free space.','Identify large folders or approved cleanup opportunities.','Check for Windows update cleanup, temp files, or sync cache.','Check disk health if tools are available.','Escalate if disk health warnings or recurring storage shortages appear.'],
        'admin': ['Escalate to Endpoint/Desktop Support for disk health warnings, storage expansion, replacement, or recurring capacity issues.'],
    },
    'FIX_SLOW_PC_BANDWIDTH_SYNC_ACTIVITY': {
        'user': ['Pause large downloads if allowed.','Let cloud sync finish if possible.','Close streaming or non-work network-heavy apps.','Test again on a stable network.'],
        'technician': ['Check network usage in Task Manager or approved tools.','Identify cloud sync, backup, video call, or update activity.','Compare performance on wired, Wi-Fi, and VPN if relevant.','Document whether slowness is network-related or local-device-related.'],
        'admin': ['Escalate if multiple users, VPN path, Wi-Fi segment, or business network resources show similar bandwidth symptoms.'],
    },
    'FIX_SLOW_PC_APPLICATION_SPECIFIC': {
        'user': ['Close and reopen the application.','Try the same task again.','Restart the computer.','Report the exact task that is slow.'],
        'technician': ['Confirm only one application is slow.','Check app version and recent updates.','Clear app cache or reset profile if supported.','Compare with another user/device if possible.','Escalate to Application/System team if multiple users are affected.'],
        'admin': ['Escalate to Application/System team with app name/version, task affected, screenshots, timestamps, and whether other users are affected.'],
    },
    'FIX_SLOW_PC_NETWORK_VPN_PERFORMANCE': {
        'user': ['Note whether slowness happens only on VPN or shared resources.','Try a public website and an internal resource.','Record which resources are slow.','Submit a ticket with screenshots and timing details.'],
        'technician': ['Compare local apps versus internal/network resources.','Check VPN status, adapter IP, DNS, and routes if remote.','Test DNS resolution for affected internal resources.','Check latency or packet loss using approved tools.','Compare Wi-Fi, wired, and hotspot if possible.','Escalate to Network/System team with results and affected scope.'],
        'admin': ['Escalate to Network/System team with VPN status, adapter IP/DNS/routes, DNS results, latency/packet loss, affected resources, timestamps, and scope.'],
    },
    'FIX_SLOW_PC_ENDPOINT_SECURITY_HEALTH_ESCALATE': {
        'user': ['Stop using the device for sensitive work if instructed.','Do not install cleanup tools from the internet.','Report pop-ups, security alerts, unusual fan noise, overheating, or repeated freezes.','Wait for IT instructions.'],
        'technician': ['Check for security alerts, suspicious processes, or unknown startup items.','Review event logs or endpoint health signals if available.','Check disk health, thermal symptoms, and recent driver/update changes.','Do not disable security tools without approval.','Escalate to Security or Endpoint/Desktop Support with evidence.'],
        'admin': ['Escalate to Security or Endpoint/Desktop Support with process names, screenshots, event/health signals, disk/thermal symptoms, recent changes, and business impact.'],
    },
}

SLOW_COMPUTER_USER_DIAGNOSTIC_NODES = [
    ('ROOT_SLOW_PC_USER',None,'category','Slow Computer Performance','Computer is slow, freezes, starts slowly, opens apps slowly, or responds slowly during work.',None,None,None,None,1),
    ('Q_SLOW_PC_RESTARTED_USER','ROOT_SLOW_PC_USER','question','Check Recent Restart',None,'Have you restarted the computer recently?',None,None,None,1),
    ('S_SLOW_PC_RESTART_USER','Q_SLOW_PC_RESTARTED_USER','solution','Restart Computer and Check Performance',None,None,'Have you restarted the computer recently?','No','FIX_SLOW_PC_RESTART_CHECK',1),
    ('Q_SLOW_PC_SCOPE_USER','Q_SLOW_PC_RESTARTED_USER','question','Identify What Is Slow',None,'Is everything slow, or only one application/browser/site?', 'Have you restarted the computer recently?','Yes',None,2),
    ('Q_SLOW_PC_WARNING_USER','Q_SLOW_PC_SCOPE_USER','question','Check Warnings',None,'Do you see low storage, update, security, or error warnings?', 'Is everything slow, or only one application/browser/site?','Everything is slow',None,1),
    ('S_SLOW_PC_WARNINGS_USER','Q_SLOW_PC_WARNING_USER','solution','Address Storage, Updates, or Security Warning',None,None,'Do you see low storage, update, security, or error warnings?','Yes','FIX_SLOW_PC_STORAGE_UPDATES_SECURITY_WARNING',1),
    ('S_SLOW_PC_BACKGROUND_USER','Q_SLOW_PC_WARNING_USER','solution','Reduce Startup and Background Load',None,None,'Do you see low storage, update, security, or error warnings?','No','FIX_SLOW_PC_STARTUP_BACKGROUND_LOAD',2),
    ('S_SLOW_PC_APP_USER','Q_SLOW_PC_SCOPE_USER','solution','Troubleshoot Slow Application',None,None,'Is everything slow, or only one application/browser/site?','One application is slow','FIX_SLOW_PC_APPLICATION_SPECIFIC',2),
    ('S_SLOW_PC_BROWSER_USER','Q_SLOW_PC_SCOPE_USER','solution','Troubleshoot Browser or Website Slowness',None,None,'Is everything slow, or only one application/browser/site?','Browser/websites are slow','FIX_SLOW_PC_APPLICATION_SPECIFIC',3),
    ('S_SLOW_PC_NETWORK_USER','Q_SLOW_PC_SCOPE_USER','solution','Report Network or VPN Resource Slowness',None,None,'Is everything slow, or only one application/browser/site?','Shared drive/internal resources are slow','FIX_SLOW_PC_NETWORK_VPN_PERFORMANCE',4),
]

SLOW_COMPUTER_TECH_DIAGNOSTIC_NODES = [
    ('ROOT_SLOW_PC_TECH',None,'category','Slow Computer Performance - IT Support Specialist Diagnostic','IT Support Specialist diagnostic tree for isolating endpoint, application, resource usage, security, and network/VPN causes.',None,None,None,None,1),
    ('Q_SLOW_PC_SCOPE_TECH','ROOT_SLOW_PC_TECH','question','Determine Scope of Slowness',None,'Is the issue local to the whole device or only one app/network resource?',None,None,None,1),
    ('S_SLOW_PC_APP_TECH','Q_SLOW_PC_SCOPE_TECH','solution','Troubleshoot Application-Specific Slowness',None,None,'Is the issue local to the whole device or only one app/network resource?','One application','FIX_SLOW_PC_APPLICATION_SPECIFIC',1),
    ('S_SLOW_PC_NETWORK_TECH','Q_SLOW_PC_SCOPE_TECH','solution','Isolate Network or VPN Performance Issue',None,None,'Is the issue local to the whole device or only one app/network resource?','Network/internal resource','FIX_SLOW_PC_NETWORK_VPN_PERFORMANCE',2),
    ('Q_SLOW_PC_RESOURCE_TECH','Q_SLOW_PC_SCOPE_TECH','question','Identify Resource Bottleneck',None,'Which resource is unusually high?', 'Is the issue local to the whole device or only one app/network resource?','Local device',None,3),
    ('S_SLOW_PC_CPU_TECH','Q_SLOW_PC_RESOURCE_TECH','solution','Identify High CPU Process',None,None,'Which resource is unusually high?','CPU','FIX_SLOW_PC_HIGH_CPU_PROCESS',1),
    ('S_SLOW_PC_MEMORY_TECH','Q_SLOW_PC_RESOURCE_TECH','solution','Reduce Memory Pressure',None,None,'Which resource is unusually high?','Memory','FIX_SLOW_PC_MEMORY_PRESSURE',2),
    ('S_SLOW_PC_DISK_TECH','Q_SLOW_PC_RESOURCE_TECH','solution','Investigate High Disk Usage or Low Storage',None,None,'Which resource is unusually high?','Disk','FIX_SLOW_PC_HIGH_DISK_LOW_STORAGE',3),
    ('S_SLOW_PC_BANDWIDTH_TECH','Q_SLOW_PC_RESOURCE_TECH','solution','Identify Bandwidth or Sync Activity',None,None,'Which resource is unusually high?','Network','FIX_SLOW_PC_BANDWIDTH_SYNC_ACTIVITY',4),
    ('Q_SLOW_PC_HEALTH_TECH','Q_SLOW_PC_RESOURCE_TECH','question','Check Endpoint Health Indicators',None,'Are malware, thermal, driver, or hardware symptoms present?', 'Which resource is unusually high?','No obvious spike',None,5),
    ('S_SLOW_PC_ENDPOINT_HEALTH_TECH','Q_SLOW_PC_HEALTH_TECH','solution','Escalate Endpoint Health or Security Review',None,None,'Are malware, thermal, driver, or hardware symptoms present?','Yes','FIX_SLOW_PC_ENDPOINT_SECURITY_HEALTH_ESCALATE',1),
    ('S_SLOW_PC_OPTIMIZE_TECH','Q_SLOW_PC_HEALTH_TECH','solution','Optimize Startup, Updates, and General Performance',None,None,'Are malware, thermal, driver, or hardware symptoms present?','No','FIX_SLOW_PC_STARTUP_BACKGROUND_LOAD',2),
]

def seed_slow_computer_performance_content(cursor):
    """Seed Slow Computer Performance KB article, solutions, steps, and diagnostic trees."""
    code_, title, category, severity, description = SLOW_COMPUTER_PERFORMANCE_PROBLEM
    cursor.execute("""
        INSERT INTO problem (problem_code, title, category, severity, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(problem_code) DO UPDATE SET
            title=excluded.title, category=excluded.category, severity=excluded.severity,
            description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, SLOW_COMPUTER_PERFORMANCE_PROBLEM)
    cursor.execute('SELECT problem_id FROM problem WHERE problem_code = ?', (code_,))
    row = cursor.fetchone()
    if not row:
        return
    problem_id = row['problem_id']
    cursor.execute("""
        INSERT INTO kb_article (problem_id, title, summary, difficulty, estimated_time, escalation_required, escalation_notes, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, difficulty=excluded.difficulty,
            estimated_time=excluded.estimated_time, escalation_required=excluded.escalation_required,
            escalation_notes=excluded.escalation_notes, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, SLOW_COMPUTER_PERFORMANCE_KB['title'], SLOW_COMPUTER_PERFORMANCE_KB['summary'], SLOW_COMPUTER_PERFORMANCE_KB['difficulty'], SLOW_COMPUTER_PERFORMANCE_KB['estimated_time'], SLOW_COMPUTER_PERFORMANCE_KB['escalation_required'], SLOW_COMPUTER_PERFORMANCE_KB['escalation_notes']))
    cursor.execute('SELECT kb_article_id FROM kb_article WHERE problem_id = ?', (problem_id,))
    article = cursor.fetchone()
    if article:
        kb_id = article['kb_article_id']
        delete_kb_child_rows(cursor, kb_id)
        insert_kb_child_rows(cursor, 'kb_article_tag', 'tag', kb_id, SLOW_COMPUTER_PERFORMANCE_KB['tags'])
        insert_kb_child_rows(cursor, 'kb_article_symptom', 'symptom', kb_id, SLOW_COMPUTER_PERFORMANCE_KB['symptoms'])
        insert_kb_child_rows(cursor, 'kb_article_cause', 'cause', kb_id, SLOW_COMPUTER_PERFORMANCE_KB['causes'])
        insert_kb_child_rows(cursor, 'kb_article_user_step', 'step_text', kb_id, SLOW_COMPUTER_PERFORMANCE_KB['user_steps'])
        insert_kb_child_rows(cursor, 'kb_article_it_step', 'step_text', kb_id, SLOW_COMPUTER_PERFORMANCE_KB['it_steps'])
    cursor.executemany("""
        INSERT INTO solution (solution_code, title, summary, resolution_steps, escalation_required, escalation_notes, priority_recommendation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(solution_code) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, resolution_steps=excluded.resolution_steps,
            escalation_required=excluded.escalation_required, escalation_notes=excluded.escalation_notes,
            priority_recommendation=excluded.priority_recommendation, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, SLOW_COMPUTER_PERFORMANCE_SOLUTIONS)
    for solution_code, audience_steps in SLOW_COMPUTER_PERFORMANCE_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue
        for audience, steps in audience_steps.items():
            cursor.execute('DELETE FROM solution_step WHERE solution_id = ? AND audience = ?', (solution_id, audience))
            cursor.executemany('INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)', [(solution_id, audience, step, idx) for idx, step in enumerate(steps, start=1)])
    seed_slow_computer_performance_tree(cursor, 'user', 'SLOW_COMPUTER_PERFORMANCE_USER', 'Slow Computer Performance - User Diagnostic', 'User-friendly diagnostic tree for restart, warning, application, browser, and network-resource slowness.', SLOW_COMPUTER_USER_DIAGNOSTIC_NODES)
    seed_slow_computer_performance_tree(cursor, 'technician', 'SLOW_COMPUTER_PERFORMANCE_TECHNICIAN', 'Slow Computer Performance - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for local endpoint, application, network/VPN, resource bottleneck, and security/health isolation.', SLOW_COMPUTER_TECH_DIAGNOSTIC_NODES)

def seed_slow_computer_performance_tree(cursor, audience, tree_code, title, description, nodes):
    problem_id = get_problem_id_for_tree_code(cursor, 'SLOW_COMPUTER_PERFORMANCE')
    cursor.execute("""
        INSERT INTO diagnostic_tree (problem_id, diagnostic_tree_code, base_tree_code, audience, title, description, is_active, updated_at)
        VALUES (?, ?, 'SLOW_COMPUTER_PERFORMANCE', ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(diagnostic_tree_code) DO UPDATE SET
            problem_id=excluded.problem_id, base_tree_code=excluded.base_tree_code, audience=excluded.audience,
            title=excluded.title, description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, tree_code, audience, title, description))
    tree_id = get_diagnostic_tree_id_by_code(cursor, tree_code)
    if not tree_id:
        return
    cursor.execute('UPDATE diagnostic_node SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE diagnostic_tree_id = ?', (tree_id,))
    for node_key, parent_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_code, sort_order in nodes:
        parent_id = get_diagnostic_node_id_by_tree_and_key(cursor, tree_id, parent_key) if parent_key else None
        solution_id = get_solution_id_by_code(cursor, solution_code) if solution_code else None
        cursor.execute("""
            INSERT INTO diagnostic_node (
                diagnostic_tree_id, parent_diagnostic_node_id, problem_id, diagnostic_tree_code,
                node_key, node_type, title, description, prompt_text,
                condition_label, condition_value, solution_id, sort_order, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(diagnostic_tree_code, node_key) DO UPDATE SET
                diagnostic_tree_id=excluded.diagnostic_tree_id,
                parent_diagnostic_node_id=excluded.parent_diagnostic_node_id,
                problem_id=excluded.problem_id,
                node_type=excluded.node_type,
                title=excluded.title,
                description=excluded.description,
                prompt_text=excluded.prompt_text,
                condition_label=excluded.condition_label,
                condition_value=excluded.condition_value,
                solution_id=excluded.solution_id,
                sort_order=excluded.sort_order,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (tree_id, parent_id, problem_id, tree_code, node_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_id, sort_order))


# -----------------------------
# APPLICATION NOT OPENING CONTENT
# -----------------------------
APPLICATION_NOT_OPENING_PROBLEM = (
    'APPLICATION_NOT_OPENING',
    'Application Not Opening',
    'Software & Applications',
    'medium',
    'Application does not open, closes immediately, gets stuck loading, or shows launch, sign-in, licensing, or access errors.',
)

APPLICATION_NOT_OPENING_KB = {
    'title': 'Application Not Opening',
    'summary': 'Use this guide when an application does not open, closes immediately, gets stuck loading, or shows a launch, sign-in, licensing, or access error.',
    'difficulty': 'Intermediate',
    'estimated_time': '10-20 minutes',
    'escalation_required': 0,
    'escalation_notes': 'Escalate if the application is business-critical, multiple users are affected, repair/reinstall fails, endpoint security blocks the app, or a backend/service outage is suspected.',
    'tags': ['application', 'app not opening', 'software', 'repair app', 'reset app', 'reinstall', 'license', 'endpoint security', 'Event Viewer', 'application support'],
    'symptoms': [
        'Nothing happens when the user clicks the application.',
        'Application opens and closes immediately.',
        'Application is stuck on the loading screen.',
        'Application shows a launch error, sign-in error, or licensing message.',
        'Application worked previously but does not open now.',
        'Only one user or one device is affected while others can open the app.',
        'Multiple users cannot open the same application, suggesting a service/backend issue.',
    ],
    'causes': [
        'Common: stuck application process, pending restart, outdated application, corrupted cache/profile, sign-in or license issue, damaged installation, missing dependency/runtime, endpoint security block, VPN/internal network dependency, unavailable backend service, or recent Windows/application update.',
        'Advanced: corrupted Windows user profile, damaged configuration files, package registration problem, Group Policy or endpoint-management block, certificate issue, stopped required service, database/backend connection failure, proxy/DNS issue, clean-boot software conflict, version mismatch, or plug-in/add-in conflict.',
    ],
    'user_steps': [
        'Close the application completely and try opening it again.',
        'Restart the computer and try again.',
        'Confirm whether other applications open normally.',
        'Check whether you see an error message and take a screenshot.',
        'If the app requires sign-in, confirm you are using the correct company account.',
        'If the app requires VPN or internal network access, connect to VPN and try again.',
        'Check whether coworkers can open the same application.',
        'Do not reinstall software from unapproved websites.',
        'Submit a ticket if the application still does not open after restart.',
    ],
    'it_steps': [
        'Tier 1: Confirm the user, device name, OS version, application name/version, and exact error message.',
        'Tier 1: Ask when the issue started and whether a Windows update, application update, password change, VPN/network change, or new installation happened recently.',
        'Tier 1: Determine scope: one user, one device, one application, multiple users, or multiple devices.',
        'Tier 1: Confirm whether the app fails immediately, hangs, shows a sign-in/licensing message, or crashes.',
        'Tier 1: Close stuck application processes in Task Manager if safe, then retest.',
        'Tier 1: Restart the computer and retest application launch.',
        'Tier 1: Confirm whether VPN/internal network access is required for the app.',
        'Tier 1: Confirm whether the user is licensed or authorized to use the application.',
        'Tier 1: Check for pending application or Windows updates.',
        'Tier 1: Use approved repair/reset options when available or reinstall only from approved company sources.',
        'Tier 2 / Desktop/Application Support: Check Event Viewer or application logs for launch errors.',
        'Tier 2 / Desktop/Application Support: Check whether local app cache/profile can be reset or renamed according to vendor/company guidance.',
        'Tier 2 / Desktop/Application Support: Check whether endpoint security quarantined or blocked application files.',
        'Tier 2 / Desktop/Application Support: Check whether required services, runtimes, dependencies, DNS, proxy, VPN, or backend services are available.',
        'Tier 2 / Desktop/Application Support: Compare affected user/device against a known-good user/device and determine whether the cause is install corruption, user profile/cache, licensing/access, endpoint security, network/backend dependency, or application-wide outage.',
        'Escalate with logs, screenshots, affected scope, version, timestamps, and test results when repair/reset does not resolve the issue.',
    ],
}

APPLICATION_NOT_OPENING_SOLUTIONS = [
    ('FIX_APP_NOT_OPENING_RESTART_RETRY','Restart Computer and Retry Application','A restart can clear stuck background processes and pending updates that prevent app launch.','Restart the computer, wait for startup to finish, then open the application again.',0,'Escalate if the application still fails after restart and other evidence points to install, license, security, or backend issues.','low'),
    ('FIX_APP_NOT_OPENING_CLOSE_STUCK_PROCESS','Close Stuck App Process and Retry','The application may already be running in the background or stuck during launch.','Close the stuck process if safe, restart the app, and confirm whether the app remains running.',0,'Escalate if the app repeatedly hangs or crashes at launch after the process is cleared.','medium'),
    ('FIX_APP_NOT_OPENING_REPAIR_RESET','Repair or Reset Application','The application installation, cache, or local profile may be damaged.','Use approved repair/reset options or reset local app cache according to company/vendor guidance.',0,'Escalate if repair/reset requires admin rights, fails, or data/configuration needs preservation.','medium'),
    ('FIX_APP_NOT_OPENING_SIGNIN_LICENSE_ACCESS','Check App Sign-In, License, or Access','The app may not open because the user is not signed in, not licensed, or lacks access.','Confirm company sign-in, license/entitlement, required access group, and SSO/MFA status.',0,'Escalate to Identity/App Support if entitlement appears correct but launch still fails.','medium'),
    ('FIX_APP_NOT_OPENING_SERVICE_OUTAGE','Report Possible Application Service Outage','Multiple users affected may indicate an application backend, server, database, cloud service, or deployment issue.','Confirm scope, collect errors/timestamps/versions, and escalate to Application/System support.',1,'Escalate as High if a business-critical application or multiple users are affected.','high'),
    ('FIX_APP_NOT_OPENING_LOGS_DEPENDENCIES_SECURITY','Troubleshoot Logs, Dependencies, or Security Block','App launch may fail due to missing dependency, app log error, endpoint security block, or configuration issue.','Review application/Event Viewer logs, dependencies, required services, and endpoint-security events.',1,'Escalate to Endpoint, Security, or Application Support with logs and evidence.','high'),
    ('FIX_APP_NOT_OPENING_APPROVED_REINSTALL','Perform Approved Repair, Reset, or Reinstall','If simpler fixes fail, the app may need approved repair, reset, or reinstall.','Repair, reset, or reinstall from approved software source while preserving required user configuration.',0,'Escalate if managed deployment, admin rights, licensing, or repeated install failure is involved.','medium'),
]

APPLICATION_NOT_OPENING_SOLUTION_STEPS = {
    'FIX_APP_NOT_OPENING_RESTART_RETRY': {
        'user': ['Save your work.', 'Restart the computer.', 'Wait a few minutes after signing in.', 'Open the application again.', 'Submit a ticket if the app still does not open.'],
        'technician': ['Tier 1: Check device uptime and pending restart status.', 'Tier 1: Ask the user to restart if uptime is high or updates are pending.', 'Tier 1: Retest application launch after restart.', 'Tier 1: Document whether restart resolved the issue.'],
        'admin': ['Escalation notes: escalate if restart does not help and the app is business-critical, multiple users are affected, or logs/security alerts show deeper failure.'],
    },
    'FIX_APP_NOT_OPENING_CLOSE_STUCK_PROCESS': {
        'user': ['Close the application if it appears open.', 'Restart the computer if you cannot close it.', 'Try opening the app again.', 'Report if nothing happens when launching.'],
        'technician': ['Tier 1: Check Task Manager for stuck application processes.', 'Tier 1: End only the affected user app process if safe.', 'Tier 1: Restart the application.', 'Tier 1: Confirm whether the process appears and remains running.', 'Tier 1: Continue to repair/reset if launch still fails.'],
        'admin': ['Escalation notes: escalate repeated stuck launch behavior to Application or Endpoint support with process name, user/device, time, and screenshots.'],
    },
    'FIX_APP_NOT_OPENING_REPAIR_RESET': {
        'user': ['Restart the computer first.', 'Do not uninstall or reinstall from unapproved websites.', 'Contact IT if the app still does not open.'],
        'technician': ['Tier 1: Use approved Windows repair/change option when available.', 'Tier 1: Use approved app repair/reset/reinstall guidance for Store or managed apps when applicable.', 'Tier 2 / Desktop/Application Support: Reset local app cache/profile only according to company/vendor guidance.', 'Tier 1: Retest after repair or reset.', 'Escalate if repair/reset requires admin rights or fails.'],
        'admin': ['Escalation notes: preserve required user settings/data before destructive reset; escalate managed app repair failures to Endpoint/Desktop Support.'],
    },
    'FIX_APP_NOT_OPENING_SIGNIN_LICENSE_ACCESS': {
        'user': ['Confirm you are signing in with your company account.', 'Take a screenshot of any sign-in, license, or access message.', 'Contact IT if you recently changed roles or need access.'],
        'technician': ['Tier 1: Confirm the user account and affected application.', 'Tier 1: Check whether the user has the required license, entitlement, or access group.', 'Tier 1: Check password/MFA status if the app uses SSO.', 'Tier 1: Route access request if approval is needed.', 'Escalate to Identity/App Support if entitlement appears correct but launch still fails.'],
        'admin': ['Escalation notes: route access/entitlement issues to Identity or application owner; include user, app, group/license, screenshots, and approval status.'],
    },
    'FIX_APP_NOT_OPENING_SERVICE_OUTAGE': {
        'user': ['Ask whether coworkers have the same issue.', 'Record the time the issue started.', 'Capture the error message.', 'Submit a ticket and avoid repeated reinstall attempts.'],
        'technician': ['Tier 1: Confirm scope across users, devices, and locations.', 'Tier 1: Check known service-status channels or internal outage notes if available.', 'Tier 1: Capture version, error messages, timestamps, and affected users.', 'Escalate to Application Support/System team.', 'Update the ticket with outage or incident details.'],
        'admin': ['Escalation notes: treat as High priority when multiple users or a business-critical app are affected; provide scope and timestamps.'],
    },
    'FIX_APP_NOT_OPENING_LOGS_DEPENDENCIES_SECURITY': {
        'user': ['Do not download missing files or fix tools from the internet.', 'Take a screenshot of the error.', 'Report whether the issue started after an update or installation.'],
        'technician': ['Tier 2 / Desktop/Application Support: Check Event Viewer or application logs for launch error.', 'Tier 2 / Desktop/Application Support: Check whether required services or dependencies are installed/running.', 'Tier 2 / Desktop/Application Support: Check endpoint security alerts or quarantine events.', 'Tier 2 / Desktop/Application Support: Compare with a known-good device if possible.', 'Escalate to Endpoint, Security, or Application Support with logs and evidence.'],
        'admin': ['Escalation notes: do not bypass endpoint protection; route security blocks or suspicious behavior to Security with evidence.'],
    },
    'FIX_APP_NOT_OPENING_APPROVED_REINSTALL': {
        'user': ['Save any app-related work if possible.', 'Do not uninstall unless IT instructs you.', 'Use only approved company software sources.'],
        'technician': ['Tier 1: Confirm install source and app version.', 'Tier 1: Back up or preserve required user configuration if applicable.', 'Tier 1: Uninstall/reinstall or redeploy from approved software portal.', 'Tier 1: Confirm license and access after reinstall.', 'Tier 1: Document the version installed and result.'],
        'admin': ['Escalation notes: escalate repeated reinstall failures, admin-rights requirements, or managed-deployment failures to Endpoint/Desktop Support.'],
    },
}

APPLICATION_NOT_OPENING_USER_DIAGNOSTIC_NODES = [
    ('ROOT_APP_NOT_OPEN_USER',None,'category','Application Not Opening','User-friendly diagnostic tree for application launch, restart, process, sign-in, licensing, and outage symptoms.',None,None,None,None,1),
    ('Q_APP_RESTARTED_USER','ROOT_APP_NOT_OPEN_USER','question','Check Restart State',None,'Have you restarted the computer since the issue started?',None,None,None,1),
    ('S_APP_RESTART_USER','Q_APP_RESTARTED_USER','solution','Restart Computer and Retry Application',None,None,'Have you restarted the computer since the issue started?','No','FIX_APP_NOT_OPENING_RESTART_RETRY',1),
    ('Q_APP_LAUNCH_BEHAVIOR_USER','Q_APP_RESTARTED_USER','question','Check Launch Behavior',None,'What happens when you open the app?','Have you restarted the computer since the issue started?','Yes',None,2),
    ('S_APP_STUCK_PROCESS_USER','Q_APP_LAUNCH_BEHAVIOR_USER','solution','Close Stuck App Process and Retry',None,None,'What happens when you open the app?','Nothing happens / stuck loading','FIX_APP_NOT_OPENING_CLOSE_STUCK_PROCESS',1),
    ('S_APP_REPAIR_USER','Q_APP_LAUNCH_BEHAVIOR_USER','solution','Repair or Reset Application',None,None,'What happens when you open the app?','Opens then closes','FIX_APP_NOT_OPENING_REPAIR_RESET',2),
    ('S_APP_SIGNIN_USER','Q_APP_LAUNCH_BEHAVIOR_USER','solution','Check App Sign-In, License, or Access',None,None,'What happens when you open the app?','Sign-in or license error','FIX_APP_NOT_OPENING_SIGNIN_LICENSE_ACCESS',3),
    ('Q_APP_OTHERS_AFFECTED_USER','Q_APP_LAUNCH_BEHAVIOR_USER','question','Check Scope',None,'Are other users affected?','What happens when you open the app?','Error message',None,4),
    ('S_APP_OUTAGE_USER','Q_APP_OTHERS_AFFECTED_USER','solution','Report Possible Application Service Outage',None,None,'Are other users affected?','Yes','FIX_APP_NOT_OPENING_SERVICE_OUTAGE',1),
    ('S_APP_TICKET_USER','Q_APP_OTHERS_AFFECTED_USER','solution','Submit Ticket with Error and App Details',None,None,'Are other users affected?','No / Not sure','FIX_APP_NOT_OPENING_LOGS_DEPENDENCIES_SECURITY',2),
]

APPLICATION_NOT_OPENING_TECH_DIAGNOSTIC_NODES = [
    ('ROOT_APP_NOT_OPEN_TECH',None,'category','Application Not Opening - IT Support Specialist Diagnostic','IT Support Specialist diagnostic tree for scope, launch behavior, access, logs, dependencies, security, and reinstall decisions.',None,None,None,None,1),
    ('Q_APP_SCOPE_TECH','ROOT_APP_NOT_OPEN_TECH','question','Check Application Scope',None,'Are multiple users or devices affected?',None,None,None,1),
    ('S_APP_OUTAGE_TECH','Q_APP_SCOPE_TECH','solution','Escalate Possible Application Service or Backend Issue',None,None,'Are multiple users or devices affected?','Yes','FIX_APP_NOT_OPENING_SERVICE_OUTAGE',1),
    ('Q_APP_PROCESS_TECH','Q_APP_SCOPE_TECH','question','Check Launch Process',None,'Is the app process stuck or failing immediately at launch?','Are multiple users or devices affected?','No',None,2),
    ('S_APP_PROCESS_REPAIR_TECH','Q_APP_PROCESS_TECH','solution','Close Stuck Process and Repair Application',None,None,'Is the app process stuck or failing immediately at launch?','Yes','FIX_APP_NOT_OPENING_CLOSE_STUCK_PROCESS',1),
    ('Q_APP_ACCESS_TECH','Q_APP_PROCESS_TECH','question','Check Access or License Error',None,'Is there a sign-in, license, permission, or access error?','Is the app process stuck or failing immediately at launch?','No',None,2),
    ('S_APP_ACCESS_TECH','Q_APP_ACCESS_TECH','solution','Verify App Access, License, and Authentication',None,None,'Is there a sign-in, license, permission, or access error?','Yes','FIX_APP_NOT_OPENING_SIGNIN_LICENSE_ACCESS',1),
    ('Q_APP_LOGS_TECH','Q_APP_ACCESS_TECH','question','Check Logs and Endpoint Tools',None,'Do logs or endpoint tools show app, dependency, or security errors?','Is there a sign-in, license, permission, or access error?','No',None,2),
    ('S_APP_LOGS_TECH','Q_APP_LOGS_TECH','solution','Troubleshoot Logs, Dependencies, or Security Block',None,None,'Do logs or endpoint tools show app, dependency, or security errors?','Yes','FIX_APP_NOT_OPENING_LOGS_DEPENDENCIES_SECURITY',1),
    ('S_APP_REINSTALL_TECH','Q_APP_LOGS_TECH','solution','Perform Approved Repair, Reset, or Reinstall',None,None,'Do logs or endpoint tools show app, dependency, or security errors?','No','FIX_APP_NOT_OPENING_APPROVED_REINSTALL',2),
]

def seed_application_not_opening_content(cursor):
    """Seed Application Not Opening KB article, solutions, steps, and diagnostic trees."""
    code_, title, category, severity, description = APPLICATION_NOT_OPENING_PROBLEM
    cursor.execute("""
        INSERT INTO problem (problem_code, title, category, severity, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(problem_code) DO UPDATE SET
            title=excluded.title, category=excluded.category, severity=excluded.severity,
            description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, APPLICATION_NOT_OPENING_PROBLEM)
    cursor.execute('SELECT problem_id FROM problem WHERE problem_code = ?', (code_,))
    row = cursor.fetchone()
    if not row:
        return
    problem_id = row['problem_id']
    cursor.execute("""
        INSERT INTO kb_article (problem_id, title, summary, difficulty, estimated_time, escalation_required, escalation_notes, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, difficulty=excluded.difficulty,
            estimated_time=excluded.estimated_time, escalation_required=excluded.escalation_required,
            escalation_notes=excluded.escalation_notes, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, APPLICATION_NOT_OPENING_KB['title'], APPLICATION_NOT_OPENING_KB['summary'], APPLICATION_NOT_OPENING_KB['difficulty'], APPLICATION_NOT_OPENING_KB['estimated_time'], APPLICATION_NOT_OPENING_KB['escalation_required'], APPLICATION_NOT_OPENING_KB['escalation_notes']))
    cursor.execute('SELECT kb_article_id FROM kb_article WHERE problem_id = ?', (problem_id,))
    article = cursor.fetchone()
    if article:
        kb_id = article['kb_article_id']
        delete_kb_child_rows(cursor, kb_id)
        insert_kb_child_rows(cursor, 'kb_article_tag', 'tag', kb_id, APPLICATION_NOT_OPENING_KB['tags'])
        insert_kb_child_rows(cursor, 'kb_article_symptom', 'symptom', kb_id, APPLICATION_NOT_OPENING_KB['symptoms'])
        insert_kb_child_rows(cursor, 'kb_article_cause', 'cause', kb_id, APPLICATION_NOT_OPENING_KB['causes'])
        insert_kb_child_rows(cursor, 'kb_article_user_step', 'step_text', kb_id, APPLICATION_NOT_OPENING_KB['user_steps'])
        insert_kb_child_rows(cursor, 'kb_article_it_step', 'step_text', kb_id, APPLICATION_NOT_OPENING_KB['it_steps'])
    cursor.executemany("""
        INSERT INTO solution (solution_code, title, summary, resolution_steps, escalation_required, escalation_notes, priority_recommendation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(solution_code) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, resolution_steps=excluded.resolution_steps,
            escalation_required=excluded.escalation_required, escalation_notes=excluded.escalation_notes,
            priority_recommendation=excluded.priority_recommendation, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, APPLICATION_NOT_OPENING_SOLUTIONS)
    for solution_code, audience_steps in APPLICATION_NOT_OPENING_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue
        for audience, steps in audience_steps.items():
            cursor.execute('DELETE FROM solution_step WHERE solution_id = ? AND audience = ?', (solution_id, audience))
            cursor.executemany('INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)', [(solution_id, audience, step, idx) for idx, step in enumerate(steps, start=1)])
    seed_application_not_opening_tree(cursor, 'user', 'APPLICATION_NOT_OPENING_USER', 'Application Not Opening - User Diagnostic', 'User-friendly diagnostic tree for restart, launch behavior, sign-in/license errors, and outage scope.', APPLICATION_NOT_OPENING_USER_DIAGNOSTIC_NODES)
    seed_application_not_opening_tree(cursor, 'technician', 'APPLICATION_NOT_OPENING_TECHNICIAN', 'Application Not Opening - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for application scope, process, access, logs, dependencies, and approved repair/reinstall.', APPLICATION_NOT_OPENING_TECH_DIAGNOSTIC_NODES)

def seed_application_not_opening_tree(cursor, audience, tree_code, title, description, nodes):
    problem_id = get_problem_id_for_tree_code(cursor, 'APPLICATION_NOT_OPENING')
    cursor.execute("""
        INSERT INTO diagnostic_tree (problem_id, diagnostic_tree_code, base_tree_code, audience, title, description, is_active, updated_at)
        VALUES (?, ?, 'APPLICATION_NOT_OPENING', ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(diagnostic_tree_code) DO UPDATE SET
            problem_id=excluded.problem_id, base_tree_code=excluded.base_tree_code, audience=excluded.audience,
            title=excluded.title, description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, tree_code, audience, title, description))
    tree_id = get_diagnostic_tree_id_by_code(cursor, tree_code)
    if not tree_id:
        return
    cursor.execute('UPDATE diagnostic_node SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE diagnostic_tree_id = ?', (tree_id,))
    for node_key, parent_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_code, sort_order in nodes:
        parent_id = get_diagnostic_node_id_by_tree_and_key(cursor, tree_id, parent_key) if parent_key else None
        solution_id = get_solution_id_by_code(cursor, solution_code) if solution_code else None
        cursor.execute("""
            INSERT INTO diagnostic_node (
                diagnostic_tree_id, parent_diagnostic_node_id, problem_id, diagnostic_tree_code,
                node_key, node_type, title, description, prompt_text,
                condition_label, condition_value, solution_id, sort_order, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(diagnostic_tree_code, node_key) DO UPDATE SET
                diagnostic_tree_id=excluded.diagnostic_tree_id,
                parent_diagnostic_node_id=excluded.parent_diagnostic_node_id,
                problem_id=excluded.problem_id,
                node_type=excluded.node_type,
                title=excluded.title,
                description=excluded.description,
                prompt_text=excluded.prompt_text,
                condition_label=excluded.condition_label,
                condition_value=excluded.condition_value,
                solution_id=excluded.solution_id,
                sort_order=excluded.sort_order,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (tree_id, parent_id, problem_id, tree_code, node_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_id, sort_order))


# -----------------------------
# APPLICATION CRASHING / FREEZING CONTENT
# -----------------------------
APPLICATION_CRASHING_FREEZING_PROBLEM = (
    'APPLICATION_CRASHING_FREEZING',
    'Application Crashing / Freezing',
    'Software & Applications',
    'medium',
    'Application opens but freezes, stops responding, closes unexpectedly, crashes during a task, or becomes unstable.',
)

APPLICATION_CRASHING_FREEZING_KB = {
    'title': 'Application Crashing / Freezing',
    'summary': 'Use this guide when an application opens but freezes, shows Not Responding, closes unexpectedly, crashes during a task, or becomes unstable.',
    'difficulty': 'Intermediate',
    'estimated_time': '10-25 minutes',
    'escalation_required': 0,
    'escalation_notes': 'Escalate if the app is business-critical, multiple users are affected, crashes cause data loss, endpoint security blocks the app, or backend/service dependency is suspected.',
    'tags': ['application crash', 'app freezing', 'not responding', 'Event Viewer', 'Reliability Monitor', 'app logs', 'repair app', 'add-in', 'plugin', 'endpoint security'],
    'symptoms': [
        'Application freezes or shows Not Responding.',
        'Application closes unexpectedly or crashes during work.',
        'Application crashes when opening a file, saving, printing, exporting, or signing in.',
        'Application works for a few minutes and then stops responding.',
        'Crash happens with one file, one task, or one user/device.',
        'Crash happens only on VPN, shared drives, or internal/backend access.',
        'Multiple users experience the same crash, suggesting app service/version/backend issue.',
    ],
    'causes': [
        'Common: app bug or unstable version, corrupted app cache/profile, high resource usage, outdated app, add-in/plugin conflict, damaged file, printer/export driver issue, endpoint security block, network/backend dependency, or local install corruption.',
        'Advanced: faulting DLL/runtime dependency, corrupted Windows user profile, display/GPU driver or hardware acceleration issue, database timeout, proxy/DNS/VPN/routing issue, permissions on app cache/workspace, certificate/authentication issue, version mismatch, memory leak, endpoint management/GPO conflict, or damaged deployment package.',
    ],
    'user_steps': [
        'Save your work frequently if the app is unstable.',
        'Close the application and reopen it.',
        'Restart the computer.',
        'Identify what action causes the crash, such as opening a file, saving, printing, exporting, or signing in.',
        'Check whether the crash happens with one file or all files.',
        'Check whether the crash happens only on VPN, shared drives, or internal resources.',
        'Take a screenshot of any error message.',
        'Ask whether coworkers using the same app have the same issue.',
        'Do not uninstall or reinstall the app from unapproved websites.',
        'Submit a ticket with the app name, task that causes the crash, screenshots, and time of failure.',
    ],
    'it_steps': [
        'Tier 1: Confirm the user, device name, OS version, application name/version, and exact crash or freezing behavior.',
        'Tier 1: Ask when the issue started and whether an application update, Windows update, driver update, password/MFA change, VPN/network change, new printer, new file/template, or plugin change happened recently.',
        'Tier 1: Determine scope: one user, one device, one file, one workflow, multiple users, or multiple devices.',
        'Tier 1: Reproduce the issue if possible and safe, especially the exact action before the crash.',
        'Tier 1: Confirm whether the app freezes, shows Not Responding, closes, or displays an error code.',
        'Tier 1: Restart the app and computer, then retest.',
        'Tier 1: Check Task Manager for high CPU, memory, disk, or network usage during the freeze.',
        'Tier 1: Test whether the issue happens with a different file or a basic test workflow.',
        'Tier 1: Disable app add-ins/plugins only if allowed and documented.',
        'Tier 2 / Desktop/Application Support: Check Reliability Monitor, Event Viewer, or app logs for crash details.',
        'Tier 2 / Desktop/Application Support: Record faulting application, faulting module, exception code, event ID, and crash timestamp.',
        'Tier 2 / Desktop/Application Support: Check whether app cache, temporary files, or local profile can be reset according to vendor/company guidance.',
        'Tier 2 / Desktop/Application Support: Check whether endpoint protection blocked or quarantined app components.',
        'Tier 2 / Desktop/Application Support: Test local file vs network/shared file behavior and check DNS/VPN/proxy connectivity if the app depends on backend services.',
        'Tier 2 / Desktop/Application Support: Compare affected user/device with a known-good user/device to isolate profile, install, network/backend, or app-wide causes.',
        'Escalate with logs, screenshots, reproduction steps, app version, affected scope, and tests already completed.',
    ],
}

APPLICATION_CRASHING_FREEZING_SOLUTIONS = [
    ('FIX_APP_CRASH_CONFIRM_AFTER_RESTART','Confirm App Stability After Restart','Restarting may clear temporary app hangs, stuck processes, or pending updates.','Restart the app/computer, reproduce the task, and confirm whether the app remains stable.',0,'Escalate if crashes return, affect a business-critical app, or multiple users are impacted.','low'),
    ('FIX_APP_CRASH_TEST_DIFFERENT_FILE','Test Different File or Document','The crash may be related to one corrupted file, template, or document.','Test with a different file or blank document and preserve the original file.',0,'Escalate if file corruption, permission, sync, or application bug is suspected.','medium'),
    ('FIX_APP_CRASH_PRINT_EXPORT','Report Print or Export Crash','Printing or exporting can crash an app due to printer driver, PDF export, add-in, or rendering issue.','Test a simple file and alternate printer/export path if allowed, then document the crash trigger.',0,'Escalate if printer driver, app rendering, or export component appears to be the cause.','medium'),
    ('FIX_APP_CRASH_SIGNIN_BACKEND_ACCESS','Check App Sign-In or Backend Access','The app may freeze or crash while connecting to authentication, cloud, database, or internal services.','Check VPN/internal access, authentication, and backend dependency indicators.',0,'Escalate if authentication, database, internal API, proxy, DNS, or backend service is suspected.','high'),
    ('FIX_APP_CRASH_CAPTURE_DETAILS','Capture Crash Details and Submit Ticket','Random or unclear crashes require evidence for support to reproduce and investigate.','Collect app name/version, timestamp, user action, file/path, screenshots, and repeatability.',0,'Escalate if crashes repeat, cause data loss, or show meaningful logs/security alerts.','medium'),
    ('FIX_APP_CRASH_ESCALATE_SERVICE_VERSION','Escalate Possible App Service or Version Issue','Multiple users affected may indicate application service, backend, deployment, or version problem.','Confirm affected users/devices/versions and escalate to Application/System support.',1,'Escalate as High when multiple users or a business-critical app are affected.','high'),
    ('FIX_APP_CRASH_LOGS_REPAIR','Analyze Crash Logs and Repair App','Crash logs may identify the faulting module, exception, dependency, or repair path.','Review Reliability Monitor, Event Viewer, or app logs and run approved repair/update when appropriate.',0,'Escalate if logs show security, dependency, driver, or vendor-specific issues.','high'),
    ('FIX_APP_CRASH_ISOLATE_FILE_ADDIN_PRINT','Isolate File, Add-in, or Print Driver Cause','Crashes may be caused by a specific file, add-in/plugin, template, printer, or export driver.','Test with blank file, disabled add-ins/plugins, alternate printer/export path, and known-good workflow where allowed.',0,'Escalate when the cause requires vendor/app-specific fix, driver remediation, or file recovery.','medium'),
    ('FIX_APP_CRASH_NETWORK_BACKEND_DEPENDENCY','Isolate Network or Backend Dependency','The app may freeze or crash when backend, database, VPN, DNS, proxy, or shared resource access fails.','Compare VPN/onsite/hotspot behavior and test relevant internal resources where appropriate.',1,'Escalate to Network/Application/System team with connectivity and scope evidence.','high'),
    ('FIX_APP_CRASH_REPAIR_RESET_REINSTALL','Repair, Reset, or Reinstall App from Approved Source','If evidence points to local app corruption, use approved repair, reset, or reinstall process.','Preserve required configuration, repair/reset/reinstall from approved source, and retest the crash scenario.',0,'Escalate if managed deployment, admin rights, licensing, or repeated repair failure is involved.','medium'),
]

APPLICATION_CRASHING_FREEZING_SOLUTION_STEPS = {
    'FIX_APP_CRASH_CONFIRM_AFTER_RESTART': {
        'user': ['Reopen the application.', 'Repeat the task that was failing.', 'Save your work frequently.', 'Submit a ticket if the app freezes or crashes again.'],
        'technician': ['Tier 1: Confirm the app works after restart.', 'Tier 1: Check whether updates or a long-running process caused the issue.', 'Tier 1: Document the result and close the issue if stable.'],
        'admin': ['Escalation notes: escalate if crashes return, cause data loss, or affect multiple users/business-critical work.'],
    },
    'FIX_APP_CRASH_TEST_DIFFERENT_FILE': {
        'user': ['Try opening a different file.', 'Try creating a new blank file.', 'Do not overwrite the original file.', 'Send IT the file name/path and error screenshot.'],
        'technician': ['Tier 1: Determine whether crash occurs with one file or all files.', 'Tier 1: Test a copy of the file if policy allows.', 'Tier 1: Check file location: local, shared drive, cloud, or email attachment.', 'Tier 2: Escalate if file corruption, permissions, sync, or application bug is suspected.'],
        'admin': ['Escalation notes: include file path, file type, storage location, user permissions, and whether a known-good file works.'],
    },
    'FIX_APP_CRASH_PRINT_EXPORT': {
        'user': ['Try printing/exporting a simple test file.', 'Try another printer or PDF export if available.', 'Record exactly when the crash happens.', 'Submit screenshots and the file type.'],
        'technician': ['Tier 1: Confirm whether crash happens with print, PDF export, or a specific printer.', 'Tier 1: Test with another printer or generic PDF printer if allowed.', 'Tier 2: Check printer driver/version and default printer.', 'Tier 2: Check whether crash occurs with one file or all files.', 'Tier 2: Escalate to Desktop/Application Support if driver or app rendering issue is suspected.'],
        'admin': ['Escalation notes: include app version, printer name/driver, file type, export path, and whether alternate printer/export works.'],
    },
    'FIX_APP_CRASH_SIGNIN_BACKEND_ACCESS': {
        'user': ['Confirm VPN is connected if the app requires internal access.', 'Try signing in again.', 'Capture the error or loading screen.', 'Report whether other internal apps work.'],
        'technician': ['Tier 1: Confirm whether app depends on SSO, VPN, proxy, database, or internal API.', 'Tier 1: Check whether user can access related internal resources.', 'Tier 2: Test DNS/connectivity to required services where appropriate.', 'Tier 2: Determine whether issue is authentication, network, or backend-related.', 'Tier 2: Escalate with timestamps, affected service, and connectivity results.'],
        'admin': ['Escalation notes: route to Identity, Network, Application, or Systems team based on whether authentication, DNS/routing/proxy, API, or database dependency fails.'],
    },
    'FIX_APP_CRASH_CAPTURE_DETAILS': {
        'user': ['Write down what you were doing before the crash.', 'Record the time of the crash.', 'Take a screenshot of any error message.', 'Note whether the issue happens repeatedly.', 'Submit a ticket with the app name and details.'],
        'technician': ['Tier 1: Collect app name/version, timestamp, user action, file/path, and screenshots.', 'Tier 1: Ask user to reproduce only if safe and no data-loss risk.', 'Tier 2: Check Event Viewer or Reliability Monitor for matching crash events.', 'Tier 2: Continue with app repair, logs, or escalation based on evidence.'],
        'admin': ['Escalation notes: include reproduction steps, timestamps, screenshots, app version, and whether crash is random or consistent.'],
    },
    'FIX_APP_CRASH_ESCALATE_SERVICE_VERSION': {
        'user': ['Ask whether coworkers see the same issue.', 'Stop repeated troubleshooting if many users are affected.', 'Submit the error message and time the issue started.'],
        'technician': ['Tier 1: Confirm affected users, devices, locations, and app versions.', 'Tier 1: Check known outage/status channels if available.', 'Tier 2: Compare affected and unaffected app versions.', 'Tier 2: Escalate to Application Support/System team with scope and evidence.'],
        'admin': ['Escalation notes: include affected scope, app version, backend/service status if known, timestamps, and business impact.'],
    },
    'FIX_APP_CRASH_LOGS_REPAIR': {
        'user': ['Keep a note of the time the crash happened.', 'Avoid reinstalling from unapproved sources.', 'Wait for IT to review the issue.'],
        'technician': ['Tier 2: Check Reliability Monitor, Event Viewer, or app logs for crash details.', 'Tier 2: Record faulting app/module, error code, and timestamp.', 'Tier 2: Run approved repair/reset if available.', 'Tier 2: Update the app from approved source.', 'Tier 2: Escalate if logs show security, dependency, driver, or vendor-specific issue.'],
        'admin': ['Escalation notes: include event ID, faulting module, exception code, app version, and repair/update result.'],
    },
    'FIX_APP_CRASH_ISOLATE_FILE_ADDIN_PRINT': {
        'user': ['Tell IT which file, printer, add-in, or action triggers the crash.', 'Try a different file or printer only if safe.', 'Do not delete business files while testing.'],
        'technician': ['Tier 1: Test with a blank/new file.', 'Tier 1: Test with another printer or export option if relevant.', 'Tier 2: Test with add-ins/plugins disabled if supported.', 'Tier 2: Check whether issue follows the file, user profile, device, or app version.', 'Tier 2: Escalate if vendor/app-specific fix is needed.'],
        'admin': ['Escalation notes: include plugin/add-in list, file/template path, printer driver, export type, and known-good comparison results.'],
    },
    'FIX_APP_CRASH_NETWORK_BACKEND_DEPENDENCY': {
        'user': ['Note whether the crash happens only on VPN or internal network.', 'Try again when connected to a stable company network if possible.', 'Report which resource or task causes the issue.'],
        'technician': ['Tier 1: Confirm whether the app depends on internal resources.', 'Tier 2: Test DNS/VPN/proxy connectivity where appropriate.', 'Tier 2: Compare behavior on VPN, onsite network, and hotspot if applicable.', 'Tier 2: Check whether related internal apps/resources are slow or unavailable.', 'Tier 2: Escalate to Network/Application/System team with results.'],
        'admin': ['Escalation notes: include VPN status, DNS/proxy tests, backend resource name, timestamps, affected users, and network path comparison.'],
    },
    'FIX_APP_CRASH_REPAIR_RESET_REINSTALL': {
        'user': ['Save or back up app-related work if instructed.', 'Do not download installers from unapproved websites.', 'Follow IT instructions for repair or reinstall.'],
        'technician': ['Tier 1: Confirm approved install source and version.', 'Tier 1: Preserve required configuration where applicable.', 'Tier 2: Repair/reset/reinstall using approved company process.', 'Tier 2: Retest the crash scenario.', 'Tier 2: Document version and result.'],
        'admin': ['Escalation notes: escalate if managed deployment, licensing, admin rights, profile preservation, or repeated repair failure is involved.'],
    },
}

APPLICATION_CRASHING_FREEZING_USER_DIAGNOSTIC_NODES = [
    ('ROOT_APP_CRASH_USER',None,'category','Application Crashing / Freezing','User-friendly diagnostic tree for application freezing, crashing, and Not Responding symptoms.',None,None,None,None,1),
    ('Q_APP_CRASH_RESTARTED_USER','ROOT_APP_CRASH_USER','question','Check Restart Result',None,'Did restarting the app and computer help?',None,None,None,1),
    ('S_APP_CRASH_STABLE_USER','Q_APP_CRASH_RESTARTED_USER','solution','Confirm App Stability After Restart',None,None,'Did restarting the app and computer help?','Yes','FIX_APP_CRASH_CONFIRM_AFTER_RESTART',1),
    ('Q_APP_CRASH_ACTION_USER','Q_APP_CRASH_RESTARTED_USER','question','Identify Crash Trigger',None,'Does the crash happen during a specific action?','Did restarting the app and computer help?','No / Not tried',None,2),
    ('S_APP_CRASH_FILE_USER','Q_APP_CRASH_ACTION_USER','solution','Test Different File or Document',None,None,'Does the crash happen during a specific action?','Opening one file','FIX_APP_CRASH_TEST_DIFFERENT_FILE',1),
    ('S_APP_CRASH_PRINT_USER','Q_APP_CRASH_ACTION_USER','solution','Report Print or Export Crash',None,None,'Does the crash happen during a specific action?','Printing/exporting','FIX_APP_CRASH_PRINT_EXPORT',2),
    ('S_APP_CRASH_SIGNIN_USER','Q_APP_CRASH_ACTION_USER','solution','Check App Sign-In or Backend Access',None,None,'Does the crash happen during a specific action?','Signing in','FIX_APP_CRASH_SIGNIN_BACKEND_ACCESS',3),
    ('S_APP_CRASH_RANDOM_USER','Q_APP_CRASH_ACTION_USER','solution','Capture Crash Details and Submit Ticket',None,None,'Does the crash happen during a specific action?','Randomly / freezes','FIX_APP_CRASH_CAPTURE_DETAILS',4),
    ('S_APP_CRASH_DOC_STEPS_USER','Q_APP_CRASH_ACTION_USER','solution','Document Reproduction Steps',None,None,'Does the crash happen during a specific action?','Not sure','FIX_APP_CRASH_CAPTURE_DETAILS',5),
]

APPLICATION_CRASHING_FREEZING_TECH_DIAGNOSTIC_NODES = [
    ('ROOT_APP_CRASH_TECH',None,'category','Application Crashing / Freezing - IT Support Specialist Diagnostic','IT Support Specialist diagnostic tree for app crashes, logs, add-ins, files, print/export, network/backend dependencies, and repair paths.',None,None,None,None,1),
    ('Q_APP_CRASH_SCOPE_TECH','ROOT_APP_CRASH_TECH','question','Check Crash Scope',None,'Are multiple users or devices affected?',None,None,None,1),
    ('S_APP_CRASH_SERVICE_TECH','Q_APP_CRASH_SCOPE_TECH','solution','Escalate Possible App Service or Version Issue',None,None,'Are multiple users or devices affected?','Yes','FIX_APP_CRASH_ESCALATE_SERVICE_VERSION',1),
    ('Q_APP_CRASH_REPRO_TECH','Q_APP_CRASH_SCOPE_TECH','question','Check Reproducibility',None,'Can the crash be reproduced with clear steps?','Are multiple users or devices affected?','No',None,2),
    ('S_APP_CRASH_EVIDENCE_TECH','Q_APP_CRASH_REPRO_TECH','solution','Collect Crash Evidence and Monitor',None,None,'Can the crash be reproduced with clear steps?','No','FIX_APP_CRASH_CAPTURE_DETAILS',1),
    ('Q_APP_CRASH_LOGS_TECH','Q_APP_CRASH_REPRO_TECH','question','Check Logs',None,'Do logs show a faulting app/module or exception?','Can the crash be reproduced with clear steps?','Yes',None,2),
    ('S_APP_CRASH_LOGS_TECH','Q_APP_CRASH_LOGS_TECH','solution','Analyze Crash Logs and Repair App',None,None,'Do logs show a faulting app/module or exception?','Yes','FIX_APP_CRASH_LOGS_REPAIR',1),
    ('Q_APP_CRASH_DEPENDENCY_TECH','Q_APP_CRASH_LOGS_TECH','question','Check Trigger or Dependency',None,'Is the crash tied to file, add-in, printer, or network/backend access?','Do logs show a faulting app/module or exception?','No / Not checked',None,2),
    ('S_APP_CRASH_FILE_ADDIN_PRINT_TECH','Q_APP_CRASH_DEPENDENCY_TECH','solution','Isolate File, Add-in, or Print Driver Cause',None,None,'Is the crash tied to file, add-in, printer, or network/backend access?','File/add-in/printer','FIX_APP_CRASH_ISOLATE_FILE_ADDIN_PRINT',1),
    ('S_APP_CRASH_NETWORK_BACKEND_TECH','Q_APP_CRASH_DEPENDENCY_TECH','solution','Isolate Network or Backend Dependency',None,None,'Is the crash tied to file, add-in, printer, or network/backend access?','Network/backend','FIX_APP_CRASH_NETWORK_BACKEND_DEPENDENCY',2),
    ('S_APP_CRASH_REINSTALL_TECH','Q_APP_CRASH_DEPENDENCY_TECH','solution','Repair, Reset, or Reinstall App from Approved Source',None,None,'Is the crash tied to file, add-in, printer, or network/backend access?','No / Not sure','FIX_APP_CRASH_REPAIR_RESET_REINSTALL',3),
]

def seed_application_crashing_freezing_content(cursor):
    """Seed Application Crashing / Freezing KB article, solutions, steps, and diagnostic trees."""
    code_, title, category, severity, description = APPLICATION_CRASHING_FREEZING_PROBLEM
    cursor.execute("""
        INSERT INTO problem (problem_code, title, category, severity, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(problem_code) DO UPDATE SET
            title=excluded.title, category=excluded.category, severity=excluded.severity,
            description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, APPLICATION_CRASHING_FREEZING_PROBLEM)
    cursor.execute('SELECT problem_id FROM problem WHERE problem_code = ?', (code_,))
    row = cursor.fetchone()
    if not row:
        return
    problem_id = row['problem_id']
    cursor.execute("""
        INSERT INTO kb_article (problem_id, title, summary, difficulty, estimated_time, escalation_required, escalation_notes, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, difficulty=excluded.difficulty,
            estimated_time=excluded.estimated_time, escalation_required=excluded.escalation_required,
            escalation_notes=excluded.escalation_notes, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, APPLICATION_CRASHING_FREEZING_KB['title'], APPLICATION_CRASHING_FREEZING_KB['summary'], APPLICATION_CRASHING_FREEZING_KB['difficulty'], APPLICATION_CRASHING_FREEZING_KB['estimated_time'], APPLICATION_CRASHING_FREEZING_KB['escalation_required'], APPLICATION_CRASHING_FREEZING_KB['escalation_notes']))
    cursor.execute('SELECT kb_article_id FROM kb_article WHERE problem_id = ?', (problem_id,))
    article = cursor.fetchone()
    if article:
        kb_id = article['kb_article_id']
        delete_kb_child_rows(cursor, kb_id)
        insert_kb_child_rows(cursor, 'kb_article_tag', 'tag', kb_id, APPLICATION_CRASHING_FREEZING_KB['tags'])
        insert_kb_child_rows(cursor, 'kb_article_symptom', 'symptom', kb_id, APPLICATION_CRASHING_FREEZING_KB['symptoms'])
        insert_kb_child_rows(cursor, 'kb_article_cause', 'cause', kb_id, APPLICATION_CRASHING_FREEZING_KB['causes'])
        insert_kb_child_rows(cursor, 'kb_article_user_step', 'step_text', kb_id, APPLICATION_CRASHING_FREEZING_KB['user_steps'])
        insert_kb_child_rows(cursor, 'kb_article_it_step', 'step_text', kb_id, APPLICATION_CRASHING_FREEZING_KB['it_steps'])
    cursor.executemany("""
        INSERT INTO solution (solution_code, title, summary, resolution_steps, escalation_required, escalation_notes, priority_recommendation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(solution_code) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, resolution_steps=excluded.resolution_steps,
            escalation_required=excluded.escalation_required, escalation_notes=excluded.escalation_notes,
            priority_recommendation=excluded.priority_recommendation, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, APPLICATION_CRASHING_FREEZING_SOLUTIONS)
    for solution_code, audience_steps in APPLICATION_CRASHING_FREEZING_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue
        for audience, steps in audience_steps.items():
            cursor.execute('DELETE FROM solution_step WHERE solution_id = ? AND audience = ?', (solution_id, audience))
            cursor.executemany('INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)', [(solution_id, audience, step, idx) for idx, step in enumerate(steps, start=1)])
    seed_application_crashing_freezing_tree(cursor, 'user', 'APPLICATION_CRASHING_FREEZING_USER', 'Application Crashing / Freezing - User Diagnostic', 'User-friendly diagnostic tree for app crashes, freezing, Not Responding symptoms, crash triggers, and ticket evidence.', APPLICATION_CRASHING_FREEZING_USER_DIAGNOSTIC_NODES)
    seed_application_crashing_freezing_tree(cursor, 'technician', 'APPLICATION_CRASHING_FREEZING_TECHNICIAN', 'Application Crashing / Freezing - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for crash scope, reproducibility, logs, file/add-in/print triggers, backend dependencies, and approved repair.', APPLICATION_CRASHING_FREEZING_TECH_DIAGNOSTIC_NODES)

def seed_application_crashing_freezing_tree(cursor, audience, tree_code, title, description, nodes):
    problem_id = get_problem_id_for_tree_code(cursor, 'APPLICATION_CRASHING_FREEZING')
    cursor.execute("""
        INSERT INTO diagnostic_tree (problem_id, diagnostic_tree_code, base_tree_code, audience, title, description, is_active, updated_at)
        VALUES (?, ?, 'APPLICATION_CRASHING_FREEZING', ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(diagnostic_tree_code) DO UPDATE SET
            problem_id=excluded.problem_id, base_tree_code=excluded.base_tree_code, audience=excluded.audience,
            title=excluded.title, description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, tree_code, audience, title, description))
    tree_id = get_diagnostic_tree_id_by_code(cursor, tree_code)
    if not tree_id:
        return
    cursor.execute('UPDATE diagnostic_node SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE diagnostic_tree_id = ?', (tree_id,))
    for node_key, parent_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_code, sort_order in nodes:
        parent_id = get_diagnostic_node_id_by_tree_and_key(cursor, tree_id, parent_key) if parent_key else None
        solution_id = get_solution_id_by_code(cursor, solution_code) if solution_code else None
        cursor.execute("""
            INSERT INTO diagnostic_node (
                diagnostic_tree_id, parent_diagnostic_node_id, problem_id, diagnostic_tree_code,
                node_key, node_type, title, description, prompt_text,
                condition_label, condition_value, solution_id, sort_order, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(diagnostic_tree_code, node_key) DO UPDATE SET
                diagnostic_tree_id=excluded.diagnostic_tree_id,
                parent_diagnostic_node_id=excluded.parent_diagnostic_node_id,
                problem_id=excluded.problem_id,
                node_type=excluded.node_type,
                title=excluded.title,
                description=excluded.description,
                prompt_text=excluded.prompt_text,
                condition_label=excluded.condition_label,
                condition_value=excluded.condition_value,
                solution_id=excluded.solution_id,
                sort_order=excluded.sort_order,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (tree_id, parent_id, problem_id, tree_code, node_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_id, sort_order))



# -----------------------------
# OPERATING SYSTEM UPDATE ISSUE CONTENT
# -----------------------------
OPERATING_SYSTEM_UPDATE_PROBLEM = (
    'OPERATING_SYSTEM_UPDATE_ISSUE',
    'Operating System Update Issue',
    'Performance & Operating System',
    'medium',
    'Computer cannot install operating system updates, gets stuck during updates, shows an update error, or repeatedly asks to restart.',
)

OPERATING_SYSTEM_UPDATE_KB = {
    'title': 'Operating System Update Issue',
    'summary': 'Use this guide when operating system updates fail, get stuck, repeatedly ask for restart, show error codes, or cannot install because of storage, network, service, or policy problems.',
    'difficulty': 'Intermediate',
    'estimated_time': '10-30 minutes',
    'escalation_required': 0,
    'escalation_notes': 'Escalate if updates repeatedly fail, security patches cannot install, the device is stuck in a boot/update loop, multiple devices are affected, or endpoint management policy/deployment issues are suspected.',
    'tags': ['Windows Update', 'operating system update', 'update error', 'restart loop', 'disk space', 'update services', 'endpoint management', 'patching', 'WSUS', 'Intune'],
    'symptoms': [
        'Operating system update fails to install or repeatedly downloads without installing.',
        'Computer repeatedly asks to restart or shows a pending restart state.',
        'Update is stuck at a percentage or appears to be in a restart loop.',
        'Windows Update shows an error code or something went wrong message.',
        'Update reports that there is not enough disk space.',
        'Update downloads but times out or fails during installation.',
        'Multiple devices fail the same update, suggesting endpoint management, policy, or deployment issue.',
    ],
    'causes': [
        'Common: not enough free disk space, pending restart, interrupted download, unstable internet, VPN/proxy/firewall block, Windows Update service stopped, another process blocking update, low battery, driver conflict, device outside maintenance window, or endpoint management policy controlling updates.',
        'Advanced: corrupted Windows Update cache, corrupted system files, component store corruption, third-party security software conflict, incompatible driver, BitLocker/Secure Boot/firmware prerequisite, WSUS/Intune/SCCM deployment issue, update applicability/supersedence problem, broken update agent, DNS/proxy/TLS inspection issue, storage hardware problem, or bad update deployment affecting multiple devices.',
    ],
    'user_steps': [
        'Save your work.',
        'Restart the computer and try the update again.',
        'Make sure the laptop is plugged into power.',
        'Confirm the internet connection is stable.',
        'Free up storage if Windows says there is not enough space.',
        'Leave the computer powered on while updates install.',
        'Do not force shut down unless the update has been stuck for a long time and IT instructs you.',
        'Take a screenshot or write down the update error code.',
        'Tell IT whether the computer restarted multiple times or is stuck in a loop.',
        'Submit a ticket if the update keeps failing.',
    ],
    'it_steps': [
        'Tier 1: Confirm the user, device name, operating system version/build, update name or KB number, and exact error code.',
        'Tier 1: Ask when the issue started and whether the device was interrupted during update.',
        'Tier 1: Confirm whether the computer is plugged into power and has stable internet access.',
        'Tier 1: Check available disk space and whether a restart is pending.',
        'Tier 1: Run Windows Update again and record the result.',
        'Tier 1: Run the Windows Update troubleshooter / Get Help diagnostic where appropriate.',
        'Tier 1: Confirm whether the issue affects one device or multiple devices.',
        'Tier 1: Check whether the device is managed by Intune, SCCM, WSUS, or another endpoint tool.',
        'Tier 1: Document screenshots, error codes, update history, and restart behavior.',
        'Tier 2: Review Windows Update history and failed update code.',
        'Tier 2: Check Windows Update-related services, such as Windows Update, BITS, and Cryptographic Services, according to company policy.',
        'Tier 2: Determine whether the update error points to insufficient disk space, corrupted/missing update files, stopped update service, another process blocking update, or timeout/interruption.',
        'Tier 2: Clear or reset Windows Update components only if allowed by support policy.',
        'Tier 2: Check system file health using approved tools if corruption is suspected.',
        'Tier 2: Review Event Viewer / Windows Update logs if available.',
        'Tier 2: Check whether security software or endpoint protection is blocking update files.',
        'Tier 2: Check the network path if updates fail only on a specific network: DNS resolution, proxy, firewall, VPN, or TLS inspection.',
        'Tier 2: Compare update behavior on office network, home network, and hotspot if appropriate.',
        'Tier 2: Check whether multiple devices in the same group, VLAN, site, or deployment ring are affected.',
        'Tier 2: Escalate with update KB, error code, device build, logs, management policy, network used, and troubleshooting completed.',
    ],
}

OPERATING_SYSTEM_UPDATE_SOLUTIONS = [
    ('FIX_OS_UPDATE_RESTART_RETRY', 'Restart and Retry OS Update', 'A restart can clear pending update state and allow installation to continue.', 'Restart the computer, plug in the laptop, check Windows Update again, and document whether the update succeeds.', 0, 'Escalate if the update repeatedly fails after restart or the device enters a restart/update loop.', 'low'),
    ('FIX_OS_UPDATE_FREE_DISK_SPACE', 'Free Up Space for Updates', 'OS updates can fail when there is not enough storage available.', 'Free approved space on the system drive, retry the update, and document the available space before and after cleanup.', 0, 'Escalate if storage remains critically low, disk health warnings appear, or cleanup requires elevated action.', 'medium'),
    ('FIX_OS_UPDATE_BASIC_TROUBLESHOOTING', 'Run Basic Update Troubleshooting', 'Windows update tools can detect and repair common update problems.', 'Confirm internet, run Windows Update/Get Help diagnostics where appropriate, check date/time and update pause status, then retry.', 0, 'Escalate if basic diagnostics do not resolve the issue or the same error returns.', 'medium'),
    ('FIX_OS_UPDATE_COLLECT_ERROR_CODE', 'Submit Update Error Code to IT', 'The update error code helps identify likely causes and next troubleshooting steps.', 'Capture the update name, KB number, error code, screenshot, and failure time for targeted troubleshooting.', 0, 'Escalate with exact KB/error code if the failure maps to policy, deployment, corruption, or driver issues.', 'medium'),
    ('FIX_OS_UPDATE_STUCK_RESTART_LOOP', 'Report Stuck Update or Restart Loop', 'A stuck update or repeated restart loop may require technician review before more user action.', 'Record how long the device has been stuck, avoid repeated force shutdowns unless instructed, and escalate if the device cannot boot normally.', 1, 'Escalate to Endpoint/Desktop Support if recovery, rollback, startup repair, repair install, reimage, or hardware review may be needed.', 'high'),
    ('FIX_OS_UPDATE_CHECK_SERVICES', 'Check Windows Update Services', 'Windows Update can fail when required services are stopped, disabled, or malfunctioning.', 'Check Windows Update-related services according to company policy and confirm endpoint management is not intentionally controlling update behavior.', 0, 'Escalate if services are blocked by policy, disabled by endpoint management, or repeatedly fail.', 'medium'),
    ('FIX_OS_UPDATE_NETWORK_PROXY_BLOCK', 'Investigate Network or Proxy Update Block', 'Updates may fail if the network, proxy, firewall, VPN, DNS, or TLS inspection path blocks update download or validation.', 'Compare update behavior across trusted networks and collect DNS/proxy/firewall/VPN indicators.', 1, 'Escalate to Network or Endpoint team if update endpoints are blocked or multiple devices on the same network are affected.', 'high'),
    ('FIX_OS_UPDATE_MANAGED_DEPLOYMENT_ESCALATE', 'Escalate Managed Update Deployment Issue', 'Multiple managed devices failing the same update may indicate deployment, policy, ring, or management-tool issue.', 'Confirm affected scope, update KB/build, endpoint management tool, policy/ring, and site/device group before escalation.', 1, 'Escalate to Endpoint Management/System team with affected devices, policy/ring, update KB/build, error codes, and timing.', 'high'),
    ('FIX_OS_UPDATE_REPAIR_COMPONENTS_ESCALATE', 'Repair Windows Update Components or Escalate', 'Persistent update failures may require deeper Windows Update component repair, system file repair, or endpoint escalation.', 'Review history/logs, check system file health, reset components only if allowed, and escalate if advanced endpoint repair is required.', 1, 'Escalate if component repair, repair install, reimage, disk health review, or endpoint engineering action is needed.', 'high'),
]

OPERATING_SYSTEM_UPDATE_SOLUTION_STEPS = {
    'FIX_OS_UPDATE_RESTART_RETRY': {
        'user': ['Save your work.', 'Restart the computer.', 'Plug the laptop into power.', 'Open Windows Update and check for updates again.', 'Wait for installation to complete.'],
        'technician': ['Check whether restart is pending.', 'Confirm device uptime.', 'Ask the user to restart and retry update.', 'Recheck update history after restart.', 'Document whether update succeeded.'],
        'admin': ['Escalation notes: If update fails again after restart, collect KB number, error code, update history, and device build before escalation.'],
    },
    'FIX_OS_UPDATE_FREE_DISK_SPACE': {
        'user': ['Empty Recycle Bin/Trash if allowed.', 'Remove unnecessary downloads.', 'Move approved files to company cloud or network storage.', 'Restart and try the update again.', 'Ask IT before deleting business files.'],
        'technician': ['Check free space on the system drive.', 'Use approved cleanup tools or Storage Sense.', 'Remove temporary files and update cleanup files where safe.', 'Confirm enough free space for the update.', 'Retry update and document result.'],
        'admin': ['Escalation notes: Escalate if storage remains critically low, cleanup requires elevated access, disk health warnings appear, or storage shortage is recurring.'],
    },
    'FIX_OS_UPDATE_BASIC_TROUBLESHOOTING': {
        'user': ['Make sure internet is stable.', 'Open Windows Update and check again.', 'Restart when prompted.', 'Submit a ticket if the update still fails.'],
        'technician': ['Run Windows Update troubleshooter/Get Help diagnostic where appropriate.', 'Check update history for the failed update.', 'Check that date/time are correct.', 'Confirm Windows Update is not paused.', 'Retry update and record any error code.'],
        'admin': ['Escalation notes: Escalate if basic troubleshooting repeats the same error, update policy blocks troubleshooting, or the device remains noncompliant.'],
    },
    'FIX_OS_UPDATE_COLLECT_ERROR_CODE': {
        'user': ['Take a screenshot of the update error.', 'Write down the error code.', 'Note when the update failed.', 'Submit a ticket with the screenshot and error code.'],
        'technician': ['Record the KB/update name and error code.', 'Match the error to likely cause.', 'Check Microsoft guidance or internal support notes for that code.', 'Continue targeted troubleshooting based on error type.'],
        'admin': ['Escalation notes: Include KB/update name, error code, OS build, update history, screenshots, and troubleshooting already completed.'],
    },
    'FIX_OS_UPDATE_STUCK_RESTART_LOOP': {
        'user': ['Do not repeatedly force power off unless instructed by IT.', 'Note how long the update has been stuck.', 'Record any percentage or message shown.', 'Contact IT if the device cannot reach the login screen.'],
        'technician': ['Determine whether update is genuinely stuck or still progressing.', 'Ask how long the device has been at the same screen/percentage.', 'Check whether the device can boot normally.', 'Escalate if recovery, rollback, startup repair, or reimage may be needed.'],
        'admin': ['Escalation notes: Prioritize as High if the device cannot boot, security updates are involved, or business-critical work is blocked.'],
    },
    'FIX_OS_UPDATE_CHECK_SERVICES': {
        'user': ['Restart the computer.', 'Try Windows Update again.', 'Submit the error screenshot if it fails.'],
        'technician': ['Check Windows Update-related services according to policy.', 'Confirm services are not disabled by policy.', 'Restart services only if allowed.', 'Check whether endpoint management controls update behavior.', 'Escalate if services are blocked by policy or repeatedly fail.'],
        'admin': ['Escalation notes: Escalate to Endpoint Management/System team if services are disabled by policy, repeatedly stop, or update control is managed centrally.'],
    },
    'FIX_OS_UPDATE_NETWORK_PROXY_BLOCK': {
        'user': ['Confirm internet works.', 'Try again on a stable trusted network if allowed.', 'Tell IT whether you are on home Wi-Fi, office network, VPN, or public Wi-Fi.'],
        'technician': ['Confirm DNS and internet access.', 'Compare update behavior on office network, home network, and hotspot if appropriate.', 'Check whether proxy, firewall, VPN, or content filtering may block update endpoints.', 'Determine whether multiple devices on the same network are affected.', 'Escalate to Network/Endpoint team with network path, error code, and affected scope.'],
        'admin': ['Escalation notes: Escalate to Network Team if updates fail only on one site, VLAN, VPN, proxy path, or managed network segment.'],
    },
    'FIX_OS_UPDATE_MANAGED_DEPLOYMENT_ESCALATE': {
        'user': ['Keep the device powered on.', 'Do not manually install random update files unless IT instructs you.', 'Provide the update error screenshot and device name.'],
        'technician': ['Confirm whether multiple devices are affected.', 'Identify update KB/build and endpoint management policy/ring.', 'Check whether issue is limited to site, device group, or deployment ring.', 'Escalate to Endpoint Management/System team with affected scope and evidence.'],
        'admin': ['Escalation notes: Include update KB, error code, device build, device group, deployment ring, affected site/VLAN if relevant, and timing of failures.'],
    },
    'FIX_OS_UPDATE_REPAIR_COMPONENTS_ESCALATE': {
        'user': ['Keep the device available for IT troubleshooting.', 'Back up important files if instructed.', 'Do not interrupt repair steps once started.'],
        'technician': ['Review update history, error code, and logs.', 'Check system file health using approved tools if corruption is suspected.', 'Reset update components only if company policy allows.', 'Check disk health if failures repeat.', 'Escalate if repair install, reimage, or advanced endpoint action is needed.'],
        'admin': ['Escalation notes: Escalate to Endpoint/Desktop Support if component store repair, repair install, reimage, or hardware/storage review is needed.'],
    },
}

OPERATING_SYSTEM_UPDATE_USER_DIAGNOSTIC_NODES = [
    ('ROOT_OS_UPDATE_USER', None, 'category', 'Operating System Update Issue', 'User-friendly diagnostic tree for failed OS updates, low storage, stuck updates, error codes, and restart loops.', None, None, None, None, 1),
    ('Q_OS_UPDATE_RESTARTED_USER', 'ROOT_OS_UPDATE_USER', 'question', 'Restart and Retry', None, 'Have you restarted the computer and tried the update again?', None, None, None, 1),
    ('S_OS_UPDATE_RESTART_USER', 'Q_OS_UPDATE_RESTARTED_USER', 'solution', 'Restart and Retry OS Update', None, None, 'Have you restarted the computer and tried the update again?', 'No', 'FIX_OS_UPDATE_RESTART_RETRY', 1),
    ('Q_OS_UPDATE_LOW_SPACE_USER', 'Q_OS_UPDATE_RESTARTED_USER', 'question', 'Check Disk Space Message', None, 'Does the update show not enough disk space?', 'Have you restarted the computer and tried the update again?', 'Yes', None, 2),
    ('S_OS_UPDATE_FREE_SPACE_USER', 'Q_OS_UPDATE_LOW_SPACE_USER', 'solution', 'Free Up Space for Updates', None, None, 'Does the update show not enough disk space?', 'Yes', 'FIX_OS_UPDATE_FREE_DISK_SPACE', 1),
    ('Q_OS_UPDATE_STUCK_USER', 'Q_OS_UPDATE_LOW_SPACE_USER', 'question', 'Check Stuck Update or Restart Loop', None, 'Is the update stuck, looping, or repeatedly asking to restart?', 'Does the update show not enough disk space?', 'No', None, 2),
    ('S_OS_UPDATE_STUCK_USER', 'Q_OS_UPDATE_STUCK_USER', 'solution', 'Report Stuck Update or Restart Loop', None, None, 'Is the update stuck, looping, or repeatedly asking to restart?', 'Yes', 'FIX_OS_UPDATE_STUCK_RESTART_LOOP', 1),
    ('Q_OS_UPDATE_ERROR_CODE_USER', 'Q_OS_UPDATE_STUCK_USER', 'question', 'Check Error Code', None, 'Do you see an error code?', 'Is the update stuck, looping, or repeatedly asking to restart?', 'No', None, 2),
    ('S_OS_UPDATE_ERROR_CODE_USER', 'Q_OS_UPDATE_ERROR_CODE_USER', 'solution', 'Submit Update Error Code to IT', None, None, 'Do you see an error code?', 'Yes', 'FIX_OS_UPDATE_COLLECT_ERROR_CODE', 1),
    ('S_OS_UPDATE_BASIC_USER', 'Q_OS_UPDATE_ERROR_CODE_USER', 'solution', 'Run Basic Update Troubleshooting', None, None, 'Do you see an error code?', 'No', 'FIX_OS_UPDATE_BASIC_TROUBLESHOOTING', 2),
]

OPERATING_SYSTEM_UPDATE_TECH_DIAGNOSTIC_NODES = [
    ('ROOT_OS_UPDATE_TECH', None, 'category', 'Operating System Update Issue - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for OS update errors, disk space, services, managed deployment, network/proxy blocks, and repair/escalation.', None, None, None, None, 1),
    ('Q_OS_UPDATE_ERROR_CODE_TECH', 'ROOT_OS_UPDATE_TECH', 'question', 'Check Failed KB or Error Code', None, 'Is there a failed KB number or update error code?', None, None, None, 1),
    ('S_OS_UPDATE_COLLECT_HISTORY_TECH', 'Q_OS_UPDATE_ERROR_CODE_TECH', 'solution', 'Collect Update History and Reproduce Failure', None, None, 'Is there a failed KB number or update error code?', 'No', 'FIX_OS_UPDATE_COLLECT_ERROR_CODE', 1),
    ('Q_OS_UPDATE_LOW_SPACE_TECH', 'Q_OS_UPDATE_ERROR_CODE_TECH', 'question', 'Check Disk Space', None, 'Is available disk space low?', 'Is there a failed KB number or update error code?', 'Yes', None, 2),
    ('S_OS_UPDATE_FREE_SPACE_TECH', 'Q_OS_UPDATE_LOW_SPACE_TECH', 'solution', 'Resolve Low Disk Space Blocking Update', None, None, 'Is available disk space low?', 'Yes', 'FIX_OS_UPDATE_FREE_DISK_SPACE', 1),
    ('Q_OS_UPDATE_SERVICES_TECH', 'Q_OS_UPDATE_LOW_SPACE_TECH', 'question', 'Check Update Services', None, 'Are Windows Update services running?', 'Is available disk space low?', 'No', None, 2),
    ('S_OS_UPDATE_SERVICES_TECH', 'Q_OS_UPDATE_SERVICES_TECH', 'solution', 'Check Windows Update Services', None, None, 'Are Windows Update services running?', 'No / Not checked', 'FIX_OS_UPDATE_CHECK_SERVICES', 1),
    ('Q_OS_UPDATE_MANAGED_SCOPE_TECH', 'Q_OS_UPDATE_SERVICES_TECH', 'question', 'Check Managed Device Scope', None, 'Are multiple managed devices affected?', 'Are Windows Update services running?', 'Yes', None, 2),
    ('S_OS_UPDATE_MANAGED_TECH', 'Q_OS_UPDATE_MANAGED_SCOPE_TECH', 'solution', 'Escalate Managed Update Deployment Issue', None, None, 'Are multiple managed devices affected?', 'Yes', 'FIX_OS_UPDATE_MANAGED_DEPLOYMENT_ESCALATE', 1),
    ('Q_OS_UPDATE_NETWORK_TECH', 'Q_OS_UPDATE_MANAGED_SCOPE_TECH', 'question', 'Check Network or Proxy Path', None, 'Does update fail only on one network or VPN?', 'Are multiple managed devices affected?', 'No', None, 2),
    ('S_OS_UPDATE_NETWORK_TECH', 'Q_OS_UPDATE_NETWORK_TECH', 'solution', 'Investigate Network or Proxy Update Block', None, None, 'Does update fail only on one network or VPN?', 'Yes', 'FIX_OS_UPDATE_NETWORK_PROXY_BLOCK', 1),
    ('S_OS_UPDATE_REPAIR_TECH', 'Q_OS_UPDATE_NETWORK_TECH', 'solution', 'Repair Windows Update Components or Escalate', None, None, 'Does update fail only on one network or VPN?', 'No', 'FIX_OS_UPDATE_REPAIR_COMPONENTS_ESCALATE', 2),
]

def seed_operating_system_update_issue_content(cursor):
    """Seed Operating System Update Issue KB article, solutions, steps, and diagnostic trees."""
    code_, title, category, severity, description = OPERATING_SYSTEM_UPDATE_PROBLEM
    cursor.execute("""
        INSERT INTO problem (problem_code, title, category, severity, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(problem_code) DO UPDATE SET
            title=excluded.title, category=excluded.category, severity=excluded.severity,
            description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, OPERATING_SYSTEM_UPDATE_PROBLEM)
    cursor.execute('SELECT problem_id FROM problem WHERE problem_code = ?', (code_,))
    row = cursor.fetchone()
    if not row:
        return
    problem_id = row['problem_id']
    cursor.execute("""
        INSERT INTO kb_article (problem_id, title, summary, difficulty, estimated_time, escalation_required, escalation_notes, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, difficulty=excluded.difficulty,
            estimated_time=excluded.estimated_time, escalation_required=excluded.escalation_required,
            escalation_notes=excluded.escalation_notes, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, OPERATING_SYSTEM_UPDATE_KB['title'], OPERATING_SYSTEM_UPDATE_KB['summary'], OPERATING_SYSTEM_UPDATE_KB['difficulty'], OPERATING_SYSTEM_UPDATE_KB['estimated_time'], OPERATING_SYSTEM_UPDATE_KB['escalation_required'], OPERATING_SYSTEM_UPDATE_KB['escalation_notes']))
    cursor.execute('SELECT kb_article_id FROM kb_article WHERE problem_id = ?', (problem_id,))
    article = cursor.fetchone()
    if article:
        kb_id = article['kb_article_id']
        delete_kb_child_rows(cursor, kb_id)
        insert_kb_child_rows(cursor, 'kb_article_tag', 'tag', kb_id, OPERATING_SYSTEM_UPDATE_KB['tags'])
        insert_kb_child_rows(cursor, 'kb_article_symptom', 'symptom', kb_id, OPERATING_SYSTEM_UPDATE_KB['symptoms'])
        insert_kb_child_rows(cursor, 'kb_article_cause', 'cause', kb_id, OPERATING_SYSTEM_UPDATE_KB['causes'])
        insert_kb_child_rows(cursor, 'kb_article_user_step', 'step_text', kb_id, OPERATING_SYSTEM_UPDATE_KB['user_steps'])
        insert_kb_child_rows(cursor, 'kb_article_it_step', 'step_text', kb_id, OPERATING_SYSTEM_UPDATE_KB['it_steps'])
    cursor.executemany("""
        INSERT INTO solution (solution_code, title, summary, resolution_steps, escalation_required, escalation_notes, priority_recommendation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(solution_code) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, resolution_steps=excluded.resolution_steps,
            escalation_required=excluded.escalation_required, escalation_notes=excluded.escalation_notes,
            priority_recommendation=excluded.priority_recommendation, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, OPERATING_SYSTEM_UPDATE_SOLUTIONS)
    for solution_code, audience_steps in OPERATING_SYSTEM_UPDATE_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue
        for audience, steps in audience_steps.items():
            cursor.execute('DELETE FROM solution_step WHERE solution_id = ? AND audience = ?', (solution_id, audience))
            cursor.executemany('INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)', [(solution_id, audience, step, idx) for idx, step in enumerate(steps, start=1)])
    seed_operating_system_update_issue_tree(cursor, 'user', 'OPERATING_SYSTEM_UPDATE_ISSUE_USER', 'Operating System Update Issue - User Diagnostic', 'User-friendly diagnostic tree for failed OS updates, low storage, stuck updates, error codes, and restart loops.', OPERATING_SYSTEM_UPDATE_USER_DIAGNOSTIC_NODES)
    seed_operating_system_update_issue_tree(cursor, 'technician', 'OPERATING_SYSTEM_UPDATE_ISSUE_TECHNICIAN', 'Operating System Update Issue - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for OS update errors, disk space, services, managed deployment, network/proxy blocks, and repair/escalation.', OPERATING_SYSTEM_UPDATE_TECH_DIAGNOSTIC_NODES)

def seed_operating_system_update_issue_tree(cursor, audience, tree_code, title, description, nodes):
    problem_id = get_problem_id_for_tree_code(cursor, 'OPERATING_SYSTEM_UPDATE_ISSUE')
    cursor.execute("""
        INSERT INTO diagnostic_tree (problem_id, diagnostic_tree_code, base_tree_code, audience, title, description, is_active, updated_at)
        VALUES (?, ?, 'OPERATING_SYSTEM_UPDATE_ISSUE', ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(diagnostic_tree_code) DO UPDATE SET
            problem_id=excluded.problem_id, base_tree_code=excluded.base_tree_code, audience=excluded.audience,
            title=excluded.title, description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, tree_code, audience, title, description))
    tree_id = get_diagnostic_tree_id_by_code(cursor, tree_code)
    if not tree_id:
        return
    cursor.execute('UPDATE diagnostic_node SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE diagnostic_tree_id = ?', (tree_id,))
    for node_key, parent_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_code, sort_order in nodes:
        parent_id = get_diagnostic_node_id_by_tree_and_key(cursor, tree_id, parent_key) if parent_key else None
        solution_id = get_solution_id_by_code(cursor, solution_code) if solution_code else None
        cursor.execute("""
            INSERT INTO diagnostic_node (
                diagnostic_tree_id, parent_diagnostic_node_id, problem_id, diagnostic_tree_code,
                node_key, node_type, title, description, prompt_text,
                condition_label, condition_value, solution_id, sort_order, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(diagnostic_tree_code, node_key) DO UPDATE SET
                diagnostic_tree_id=excluded.diagnostic_tree_id,
                parent_diagnostic_node_id=excluded.parent_diagnostic_node_id,
                problem_id=excluded.problem_id,
                node_type=excluded.node_type,
                title=excluded.title,
                description=excluded.description,
                prompt_text=excluded.prompt_text,
                condition_label=excluded.condition_label,
                condition_value=excluded.condition_value,
                solution_id=excluded.solution_id,
                sort_order=excluded.sort_order,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (tree_id, parent_id, problem_id, tree_code, node_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_id, sort_order))


# -----------------------------
# DEVICE RUNNING OUT OF STORAGE CONTENT
# -----------------------------
DEVICE_STORAGE_PROBLEM = (
    'DEVICE_RUNNING_OUT_OF_STORAGE',
    'Device Running Out of Storage',
    'Performance & Operating System',
    'medium',
    'Computer is low on storage space, cannot save files, cannot install updates, or shows disk-full warnings.',
)

DEVICE_STORAGE_KB = {
    'title': 'Device Running Out of Storage',
    'summary': 'Troubleshooting article for low disk space, failed saves, failed updates, app install issues, cloud sync storage, temporary files, and recurring storage growth.',
    'difficulty': 'Intermediate',
    'estimated_time': '10-25 minutes',
    'escalation_required': 0,
    'escalation_notes': 'Escalate if storage remains critically low, security updates cannot install, the device cannot save business files, storage fills again quickly, disk health is suspect, or suspicious files/processes are present.',
    'tags': ['storage', 'disk space', 'C drive full', 'low disk space', 'Storage Sense', 'temporary files', 'Windows Update cleanup', 'cloud sync', 'Recycle Bin', 'endpoint support'],
    'symptoms': [
        'Low disk space or storage full warning appears.',
        'User cannot save files or downloads fail.',
        'Operating system updates fail because there is not enough space.',
        'Applications cannot install or update.',
        'Computer is slow and the system drive is nearly full.',
        'Cloud sync appears stuck or stores too many files locally.',
        'Storage becomes low again shortly after cleanup.',
    ],
    'causes': [
        'Common: large files in Downloads/Desktop/Documents/Videos, full Recycle Bin, temporary files, Windows update cleanup files, cloud/offline sync cache, local mailbox cache, duplicate files, leftover installers, application logs, crash dumps, too many installed apps, or insufficient drive capacity.',
        'Advanced: runaway application logs, corrupted update cache, user profile bloat, shadow copies/restore points, hibernation/page file growth, endpoint backup or management cache, virtual machines/development environments, malware or unwanted software, file-system reporting issue, disk quota, or storage device health issue.',
    ],
    'user_steps': [
        'Save your work before deleting anything.',
        'Empty the Recycle Bin or Trash.',
        'Review Downloads and remove files you no longer need.',
        'Move approved business files to company cloud or network storage.',
        'Remove duplicate personal files if company policy allows.',
        'Do not delete system folders such as Windows, Program Files, or hidden folders.',
        'Restart the computer after cleanup.',
        'Try saving files or running updates again.',
        'Take a screenshot of the low-storage warning.',
        'Contact IT if storage is still low or you are unsure what can be deleted.',
    ],
    'it_steps': [
        'Tier 1: Confirm the user, device name, operating system, disk size, and available free space.',
        'Tier 1: Confirm which drive is full, usually C:.',
        'Tier 1: Ask what symptom triggered the issue: cannot save files, update failure, app install failure, slow performance, or cloud sync warning.',
        'Tier 1: Check common user folders such as Downloads, Desktop, Documents, Pictures, and Videos.',
        'Tier 1: Check Recycle Bin size.',
        'Tier 1: Use approved Windows storage settings or cleanup tools.',
        'Tier 1: Confirm whether cloud files are stored locally instead of online-only.',
        'Tier 1: Confirm whether large files can be moved to approved company storage.',
        'Tier 1: Avoid deleting business files without user confirmation.',
        'Tier 1: Document before and after free space.',
        'Tier 2 / Endpoint Support: Review storage usage categories in Windows Storage settings.',
        'Tier 2 / Endpoint Support: Check temporary files and Windows Update cleanup files.',
        'Tier 2 / Endpoint Support: Check whether Storage Sense can be enabled or configured according to company policy.',
        'Tier 2 / Endpoint Support: Check for large application logs, crash dumps, installer folders, and cache directories.',
        'Tier 2 / Endpoint Support: Check cloud sync and offline file cache behavior.',
        'Tier 2 / Endpoint Support: Check whether the storage issue returns quickly after cleanup.',
        'Tier 2 / Endpoint Support: Check endpoint backup or management tool cache if present.',
        'Tier 2 / Endpoint Support: Check disk health if low-space warnings come with disk errors or performance problems.',
        'Tier 2 / Endpoint Support: Determine whether the issue is user file accumulation, temporary/update files, sync/cache issue, application log growth, insufficient capacity, or possible malware/unwanted software.',
        'Escalate with disk size, free space, largest categories, cleanup performed, recurrence pattern, and business impact.',
    ],
}

DEVICE_STORAGE_SOLUTIONS = [
    ('FIX_STORAGE_CHECK_USAGE_DETAILS', 'Check Storage Usage and Capture Details', 'Confirm which drive is low and what symptom the user is seeing.', 'Check affected drive, available space, warning message, and storage categories before deciding whether cleanup or escalation is needed.', 0, 'Escalate if the warning is tied to update failure, inability to save work, or unknown recurring storage growth.', 'medium'),
    ('FIX_STORAGE_REMOVE_OBVIOUS_FILES', 'Remove Obvious Unneeded Files Safely', 'Downloads, Recycle Bin contents, and duplicate personal files often consume space.', 'Remove obvious unneeded files only with user approval and avoid system folders or business data without confirmation.', 0, 'Escalate if user files cannot be removed or storage remains critically low after safe cleanup.', 'medium'),
    ('FIX_STORAGE_CLEAN_TEMP_UPDATE_FILES', 'Clean Temporary and Update Files', 'Temporary files and update cleanup files may consume significant space.', 'Use approved cleanup tools, review temporary/update cleanup files, restart, and verify recovered space.', 0, 'Escalate if update cache is corrupted, cleanup requires elevated action, or updates still fail.', 'medium'),
    ('FIX_STORAGE_CLOUD_SYNC_LOCAL_FILES', 'Review Cloud Sync Local Storage', 'Cloud files or offline files may be stored locally and consume disk space.', 'Review sync status, online-only settings, local cache, and required file availability according to company policy.', 0, 'Escalate if sync client cache is corrupted or policy-managed sync settings require endpoint/admin action.', 'medium'),
    ('FIX_STORAGE_BLOCKING_WORK', 'Contact IT for Low Storage Blocking Work', 'Low storage is affecting updates, installs, or the ability to save work.', 'Prioritize cleanup and evidence collection when storage blocks work, security updates, or app installs.', 1, 'Escalate if capacity upgrade, reimage, replacement, or urgent update compliance work is needed.', 'high'),
    ('FIX_STORAGE_APP_LOGS_CRASH_DUMPS', 'Investigate Application Logs or Crash Dumps', 'Logs, crash dumps, or application caches may grow abnormally.', 'Identify large logs/dumps/caches, connect them to app crashes if applicable, and clean only approved locations.', 1, 'Escalate if logs grow again, indicate application failure, or require vendor/application support.', 'high'),
    ('FIX_STORAGE_RECURRING_UNKNOWN_GROWTH', 'Escalate Recurring or Unknown Storage Growth', 'Storage fills again after cleanup or the source is unclear.', 'Document growth timeline and investigate sync cache, logs, update cache, backup cache, suspicious files, and disk health.', 1, 'Escalate to Endpoint, Systems, or Security based on evidence of recurring growth, disk health issues, or suspicious activity.', 'high'),
]

DEVICE_STORAGE_SOLUTION_STEPS = {
    'FIX_STORAGE_CHECK_USAGE_DETAILS': {
        'user': ['Take a screenshot of the storage warning.', 'Note whether you cannot save files, install apps, or run updates.', 'Submit the screenshot and device name if you need help.'],
        'technician': ['Check the affected drive and available free space.', 'Record disk size, free space, and warning message.', 'Check Windows Storage categories.', 'Determine whether the issue is urgent or preventive.'],
        'admin': ['Escalation notes: Escalate if free space is critically low, storage blocks work/security updates, or the source is unknown.'],
    },
    'FIX_STORAGE_REMOVE_OBVIOUS_FILES': {
        'user': ['Empty the Recycle Bin.', 'Review Downloads for files you no longer need.', 'Move approved files to company cloud or network storage.', 'Do not delete system folders.'],
        'technician': ['Review common user folders with user approval.', 'Empty Recycle Bin if approved.', 'Remove unnecessary installers or duplicate files if safe.', 'Confirm free space after cleanup.'],
        'admin': ['Escalation notes: Escalate if user files cannot be removed safely or the device remains below safe free-space thresholds.'],
    },
    'FIX_STORAGE_CLEAN_TEMP_UPDATE_FILES': {
        'user': ['Restart the computer.', 'Contact IT before deleting unfamiliar files.', 'Try updates again after IT confirms cleanup.'],
        'technician': ['Use approved Windows cleanup tools.', 'Review temporary files and Windows Update cleanup files.', 'Use Storage Sense if allowed by company policy.', 'Restart after cleanup and verify free space.'],
        'admin': ['Escalation notes: Escalate if cleanup requires elevated action, update cache appears corrupted, or OS updates still fail.'],
    },
    'FIX_STORAGE_CLOUD_SYNC_LOCAL_FILES': {
        'user': ['Identify large synced folders if possible.', 'Do not delete shared cloud files unless you understand the impact.', 'Ask IT before changing sync settings.'],
        'technician': ['Check cloud sync status and local file availability settings.', 'Identify folders stored locally.', 'Use online-only or free-up-space features if company policy allows.', 'Confirm the user can still access required files.'],
        'admin': ['Escalation notes: Escalate if sync client cache is corrupted, policy-managed settings are required, or shared data could be affected.'],
    },
    'FIX_STORAGE_BLOCKING_WORK': {
        'user': ['Stop deleting files if you are unsure what is safe.', 'Submit a ticket with the warning screenshot.', 'Include whether updates, installs, or saving files are blocked.'],
        'technician': ['Prioritize cleanup if work or security updates are blocked.', 'Check free space and update/install failure messages.', 'Perform approved cleanup.', 'Escalate if capacity upgrade, reimage, or replacement is needed.'],
        'admin': ['Escalation notes: Treat as High if security updates cannot install, business files cannot be saved, or less than 5 percent free space remains.'],
    },
    'FIX_STORAGE_APP_LOGS_CRASH_DUMPS': {
        'user': ['Report whether an application has been crashing.', 'Do not delete unfamiliar log or system files.', 'Provide screenshots of storage warnings.'],
        'technician': ['Identify unusually large logs, dumps, or application cache folders.', 'Check whether a specific app is repeatedly crashing.', 'Clean only approved locations.', 'Escalate if logs grow again or indicate application failure.'],
        'admin': ['Escalation notes: Escalate to Application/Endpoint Support if logs or dumps point to recurring app crashes or vendor-specific failure.'],
    },
    'FIX_STORAGE_RECURRING_UNKNOWN_GROWTH': {
        'user': ['Report when the storage warning returns.', 'Note any app, sync, or update activity around that time.', 'Avoid installing cleanup utilities from the internet.'],
        'technician': ['Document before and after free space and growth timeline.', 'Check for sync cache, logs, update cache, backup cache, or suspicious files.', 'Check disk health if performance or errors are present.', 'Escalate to Endpoint, Systems, or Security based on evidence.'],
        'admin': ['Escalation notes: Escalate recurring/unknown growth with screenshots, free-space trend, largest folders/categories, cleanup actions, disk health indicators, and suspicious-process evidence if present.'],
    },
}

DEVICE_STORAGE_USER_DIAGNOSTIC_NODES = [
    ('ROOT_STORAGE_USER', None, 'category', 'Device Running Out of Storage', 'User-friendly diagnostic tree for low disk space, failed saves, update/install blockers, cloud sync storage, and recurring storage growth.', None, None, None, None, 1),
    ('Q_STORAGE_WARNING_USER', 'ROOT_STORAGE_USER', 'question', 'Check Storage Warning', None, 'Are you seeing a low disk space or storage full warning?', None, None, None, 1),
    ('S_STORAGE_CHECK_DETAILS_USER', 'Q_STORAGE_WARNING_USER', 'solution', 'Check Storage Usage and Capture Details', None, None, 'Are you seeing a low disk space or storage full warning?', 'No', 'FIX_STORAGE_CHECK_USAGE_DETAILS', 1),
    ('Q_STORAGE_RECYCLE_DOWNLOADS_USER', 'Q_STORAGE_WARNING_USER', 'question', 'Check Recycle Bin and Downloads', None, 'Have you emptied Recycle Bin and checked Downloads?', 'Are you seeing a low disk space or storage full warning?', 'Yes', None, 2),
    ('S_STORAGE_REMOVE_FILES_USER', 'Q_STORAGE_RECYCLE_DOWNLOADS_USER', 'solution', 'Remove Obvious Unneeded Files Safely', None, None, 'Have you emptied Recycle Bin and checked Downloads?', 'No', 'FIX_STORAGE_REMOVE_OBVIOUS_FILES', 1),
    ('Q_STORAGE_BLOCKING_WORK_USER', 'Q_STORAGE_RECYCLE_DOWNLOADS_USER', 'question', 'Check Work Blocker', None, 'Is the issue blocking updates, installs, or saving files?', 'Have you emptied Recycle Bin and checked Downloads?', 'Yes', None, 2),
    ('S_STORAGE_BLOCKING_USER', 'Q_STORAGE_BLOCKING_WORK_USER', 'solution', 'Contact IT for Low Storage Blocking Work', None, None, 'Is the issue blocking updates, installs, or saving files?', 'Yes', 'FIX_STORAGE_BLOCKING_WORK', 1),
    ('Q_STORAGE_CLOUD_SYNC_USER', 'Q_STORAGE_BLOCKING_WORK_USER', 'question', 'Check Cloud or Offline Files', None, 'Do you use cloud or offline files stored locally?', 'Is the issue blocking updates, installs, or saving files?', 'No', None, 2),
    ('S_STORAGE_CLOUD_SYNC_USER', 'Q_STORAGE_CLOUD_SYNC_USER', 'solution', 'Review Cloud Sync Local Storage', None, None, 'Do you use cloud or offline files stored locally?', 'Yes / Not sure', 'FIX_STORAGE_CLOUD_SYNC_LOCAL_FILES', 1),
    ('S_STORAGE_REVIEW_TICKET_USER', 'Q_STORAGE_CLOUD_SYNC_USER', 'solution', 'Submit Storage Review Ticket', None, None, 'Do you use cloud or offline files stored locally?', 'No', 'FIX_STORAGE_CHECK_USAGE_DETAILS', 2),
]

DEVICE_STORAGE_TECH_DIAGNOSTIC_NODES = [
    ('ROOT_STORAGE_TECH', None, 'category', 'Device Running Out of Storage - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for low storage, cleanup categories, sync/cache, logs, update blockers, and recurring storage growth.', None, None, None, None, 1),
    ('Q_STORAGE_SAFE_THRESHOLD_TECH', 'ROOT_STORAGE_TECH', 'question', 'Check Free-Space Threshold', None, 'Is the system drive below a safe free-space threshold?', None, None, None, 1),
    ('S_STORAGE_USAGE_SYMPTOM_TECH', 'Q_STORAGE_SAFE_THRESHOLD_TECH', 'solution', 'Check Storage Usage and User-Reported Symptom', None, None, 'Is the system drive below a safe free-space threshold?', 'No', 'FIX_STORAGE_CHECK_USAGE_DETAILS', 1),
    ('Q_STORAGE_CATEGORY_TECH', 'Q_STORAGE_SAFE_THRESHOLD_TECH', 'question', 'Identify Largest Storage Category', None, 'What category is using most space?', 'Is the system drive below a safe free-space threshold?', 'Yes', None, 2),
    ('S_STORAGE_USER_FILES_TECH', 'Q_STORAGE_CATEGORY_TECH', 'solution', 'Clean User Files with Approval', None, None, 'What category is using most space?', 'User files', 'FIX_STORAGE_REMOVE_OBVIOUS_FILES', 1),
    ('S_STORAGE_TEMP_TECH', 'Q_STORAGE_CATEGORY_TECH', 'solution', 'Clean Temporary and Update Files', None, None, 'What category is using most space?', 'Temporary/update files', 'FIX_STORAGE_CLEAN_TEMP_UPDATE_FILES', 2),
    ('S_STORAGE_SYNC_TECH', 'Q_STORAGE_CATEGORY_TECH', 'solution', 'Review Cloud Sync and Offline Files', None, None, 'What category is using most space?', 'Cloud/offline cache', 'FIX_STORAGE_CLOUD_SYNC_LOCAL_FILES', 3),
    ('S_STORAGE_LOGS_TECH', 'Q_STORAGE_CATEGORY_TECH', 'solution', 'Investigate Application Logs or Crash Dumps', None, None, 'What category is using most space?', 'Logs/crash dumps', 'FIX_STORAGE_APP_LOGS_CRASH_DUMPS', 4),
    ('S_STORAGE_UNKNOWN_TECH', 'Q_STORAGE_CATEGORY_TECH', 'solution', 'Escalate Recurring or Unknown Storage Growth', None, None, 'What category is using most space?', 'Unknown / recurring', 'FIX_STORAGE_RECURRING_UNKNOWN_GROWTH', 5),
]

def seed_device_storage_content(cursor):
    """Seed Device Running Out of Storage KB article, solutions, steps, and diagnostic trees."""
    code_, title, category, severity, description = DEVICE_STORAGE_PROBLEM
    cursor.execute("""
        INSERT INTO problem (problem_code, title, category, severity, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(problem_code) DO UPDATE SET
            title=excluded.title, category=excluded.category, severity=excluded.severity,
            description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, DEVICE_STORAGE_PROBLEM)
    cursor.execute('SELECT problem_id FROM problem WHERE problem_code = ?', (code_,))
    row = cursor.fetchone()
    if not row:
        return
    problem_id = row['problem_id']
    cursor.execute("""
        INSERT INTO kb_article (problem_id, title, summary, difficulty, estimated_time, escalation_required, escalation_notes, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, difficulty=excluded.difficulty,
            estimated_time=excluded.estimated_time, escalation_required=excluded.escalation_required,
            escalation_notes=excluded.escalation_notes, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, DEVICE_STORAGE_KB['title'], DEVICE_STORAGE_KB['summary'], DEVICE_STORAGE_KB['difficulty'], DEVICE_STORAGE_KB['estimated_time'], DEVICE_STORAGE_KB['escalation_required'], DEVICE_STORAGE_KB['escalation_notes']))
    cursor.execute('SELECT kb_article_id FROM kb_article WHERE problem_id = ?', (problem_id,))
    article = cursor.fetchone()
    if article:
        kb_id = article['kb_article_id']
        delete_kb_child_rows(cursor, kb_id)
        insert_kb_child_rows(cursor, 'kb_article_tag', 'tag', kb_id, DEVICE_STORAGE_KB['tags'])
        insert_kb_child_rows(cursor, 'kb_article_symptom', 'symptom', kb_id, DEVICE_STORAGE_KB['symptoms'])
        insert_kb_child_rows(cursor, 'kb_article_cause', 'cause', kb_id, DEVICE_STORAGE_KB['causes'])
        insert_kb_child_rows(cursor, 'kb_article_user_step', 'step_text', kb_id, DEVICE_STORAGE_KB['user_steps'])
        insert_kb_child_rows(cursor, 'kb_article_it_step', 'step_text', kb_id, DEVICE_STORAGE_KB['it_steps'])
    cursor.executemany("""
        INSERT INTO solution (solution_code, title, summary, resolution_steps, escalation_required, escalation_notes, priority_recommendation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(solution_code) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, resolution_steps=excluded.resolution_steps,
            escalation_required=excluded.escalation_required, escalation_notes=excluded.escalation_notes,
            priority_recommendation=excluded.priority_recommendation, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, DEVICE_STORAGE_SOLUTIONS)
    for solution_code, audience_steps in DEVICE_STORAGE_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue
        for audience, steps in audience_steps.items():
            cursor.execute('DELETE FROM solution_step WHERE solution_id = ? AND audience = ?', (solution_id, audience))
            cursor.executemany('INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)', [(solution_id, audience, step, idx) for idx, step in enumerate(steps, start=1)])
    seed_device_storage_tree(cursor, 'user', 'DEVICE_RUNNING_OUT_OF_STORAGE_USER', 'Device Running Out of Storage - User Diagnostic', 'User-friendly diagnostic tree for low disk space, cleanup, cloud sync, update/install blockers, and storage review.', DEVICE_STORAGE_USER_DIAGNOSTIC_NODES)
    seed_device_storage_tree(cursor, 'technician', 'DEVICE_RUNNING_OUT_OF_STORAGE_TECHNICIAN', 'Device Running Out of Storage - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for low storage categories, cleanup paths, recurring growth, and escalation.', DEVICE_STORAGE_TECH_DIAGNOSTIC_NODES)

def seed_device_storage_tree(cursor, audience, tree_code, title, description, nodes):
    problem_id = get_problem_id_for_tree_code(cursor, 'DEVICE_RUNNING_OUT_OF_STORAGE')
    cursor.execute("""
        INSERT INTO diagnostic_tree (problem_id, diagnostic_tree_code, base_tree_code, audience, title, description, is_active, updated_at)
        VALUES (?, ?, 'DEVICE_RUNNING_OUT_OF_STORAGE', ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(diagnostic_tree_code) DO UPDATE SET
            problem_id=excluded.problem_id, base_tree_code=excluded.base_tree_code, audience=excluded.audience,
            title=excluded.title, description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, tree_code, audience, title, description))
    tree_id = get_diagnostic_tree_id_by_code(cursor, tree_code)
    if not tree_id:
        return
    cursor.execute('UPDATE diagnostic_node SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE diagnostic_tree_id = ?', (tree_id,))
    for node_key, parent_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_code, sort_order in nodes:
        parent_id = get_diagnostic_node_id_by_tree_and_key(cursor, tree_id, parent_key) if parent_key else None
        solution_id = get_solution_id_by_code(cursor, solution_code) if solution_code else None
        cursor.execute("""
            INSERT INTO diagnostic_node (
                diagnostic_tree_id, parent_diagnostic_node_id, problem_id, diagnostic_tree_code,
                node_key, node_type, title, description, prompt_text,
                condition_label, condition_value, solution_id, sort_order, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(diagnostic_tree_code, node_key) DO UPDATE SET
                diagnostic_tree_id=excluded.diagnostic_tree_id,
                parent_diagnostic_node_id=excluded.parent_diagnostic_node_id,
                problem_id=excluded.problem_id,
                node_type=excluded.node_type,
                title=excluded.title,
                description=excluded.description,
                prompt_text=excluded.prompt_text,
                condition_label=excluded.condition_label,
                condition_value=excluded.condition_value,
                solution_id=excluded.solution_id,
                sort_order=excluded.sort_order,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (tree_id, parent_id, problem_id, tree_code, node_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_id, sort_order))


# -----------------------------
# PHISHING EMAIL REPORTED CONTENT
# -----------------------------
PHISHING_EMAIL_PROBLEM = (
    'PHISHING_EMAIL_REPORTED',
    'Phishing Email Reported',
    'Security',
    'medium',
    'User received a suspicious email, link, attachment, QR code, or message that may be attempting credential theft, malware delivery, impersonation, or fraud.',
)

PHISHING_EMAIL_KB = {
    'title': 'Phishing Email Reported',
    'summary': 'Use this guide when you receive a suspicious email, link, attachment, QR code, password reset request, payment request, or message asking for urgent action.',
    'difficulty': 'Intermediate',
    'estimated_time': '5-15 minutes',
    'escalation_required': 1,
    'escalation_notes': 'Escalate immediately if the user clicked a link, opened an attachment, entered credentials, approved MFA, shared sensitive data, sent payment, or if multiple users received the same message.',
    'tags': ['phishing', 'suspicious email', 'security', 'malicious link', 'attachment', 'MFA prompt', 'credential theft', 'spoofing', 'QR phishing', 'email security'],
    'symptoms': [
        'Suspicious email asks the user to click a link, reset a password, open an attachment, scan a QR code, or take urgent action.',
        'Sender address, reply-to address, display name, or domain looks unusual or impersonates a trusted person or company.',
        'Message requests gift cards, payment, payroll changes, bank changes, personal information, or credentials.',
        'User clicked a suspicious link or scanned a QR code but may not have entered information.',
        'User entered credentials, MFA code, payment information, personal information, or approved an unexpected MFA prompt.',
        'User opened or downloaded a suspicious attachment and endpoint review may be needed.',
        'Multiple users received similar messages, suggesting an active phishing campaign.',
    ],
    'causes': [
        'Common: mass phishing campaign, spoofed sender display name, compromised external sender account, fake password reset or sign-in page, malicious attachment, fake invoice, QR phishing, urgent pressure tactic, business email compromise attempt, user clicking a suspicious link, user entering credentials, or user approving unexpected MFA.',
        'Advanced: internal account compromise sending phishing to coworkers, adversary-in-the-middle phishing stealing session tokens, OAuth consent phishing, attacker-created mailbox rule, lookalike domain or typosquatting, macro/script/dropper attachment, redirect chains or CAPTCHA evasion, security-filter bypass through trusted sending platforms, or credential reuse from a prior breach.',
    ],
    'user_steps': [
        'Do not click links or open attachments in the suspicious email.',
        'Do not reply to the sender.',
        'Do not forward the email to coworkers.',
        'Use the company phishing-report button if available.',
        'If there is no report button, contact IT and keep the message available.',
        'If you clicked a link, tell IT immediately.',
        'If you entered your password, MFA code, payment information, or personal information, tell IT immediately.',
        'If you approved an MFA prompt you did not expect, report it immediately.',
        'If you downloaded or opened an attachment, stop using the device for sensitive work until IT reviews it.',
        'Note the sender, subject, time received, and any action you took.',
    ],
    'it_steps': [
        'Tier 1: Thank the user and instruct them not to click, reply, forward, or delete the message until reporting/preservation steps are complete.',
        'Tier 1: Ask what action the user took: only received, clicked link, scanned QR code, opened/downloaded attachment, entered credentials, approved MFA, replied, shared data, or sent payment.',
        'Tier 1: Collect sender, subject, received time, screenshot, original message, and message headers if available.',
        'Tier 1: Ask whether coworkers received the same or similar email.',
        'Tier 1: Confirm whether the email is still in the mailbox and route it through the approved phishing-report process.',
        'Tier 1: If the user clicked or entered credentials, route to password reset, account security, and Security escalation according to policy.',
        'Tier 1: If an attachment was opened or downloaded, route to endpoint/security review.',
        'Tier 1: Escalate urgently if payment, payroll, gift card, invoice, executive impersonation, or banking change is involved.',
        'Tier 1: Document user action, affected account, device name, timestamps, and business impact.',
        'Tier 2 / Security-aware support: Review the message safely using approved tools; do not click links directly.',
        'Tier 2 / Security-aware support: Check sender address, reply-to address, display name, and domain similarity.',
        'Tier 2 / Security-aware support: Inspect URLs, attachments, and QR targets only through approved security tools or sandbox processes.',
        'Tier 2 / Security-aware support: Check email authentication results such as SPF, DKIM, or DMARC if available.',
        'Tier 2 / Security-aware support: Search for similar messages by sender, subject, URL, attachment name/hash, or campaign indicators if tools are available.',
        'Tier 2 / Security-aware support: Check whether the user submitted credentials or approved MFA and review sign-in logs if access is available.',
        'Tier 2 / Security-aware support: Check for suspicious mailbox forwarding rules, inbox rules, or unusual activity when compromise is suspected.',
        'Tier 2 / Security-aware support: Escalate to Security with indicators, user actions, message sample/header, affected users, timestamps, and containment status.',
    ],
}

PHISHING_EMAIL_SOLUTIONS = [
    ('FIX_PHISHING_REPORT_EMAIL_SAFELY', 'Report Suspicious Email Safely', 'The user received a suspicious message but did not interact with it.', 'Do not interact with the message. Report it using the approved phishing-report process and preserve evidence until IT or Security confirms next steps.', 0, 'Escalate if message indicators appear malicious, many users received it, or it impersonates high-risk business functions.', 'medium'),
    ('FIX_PHISHING_LINK_CLICKED_NO_DATA', 'Report Link Clicked Without Data Entry', 'User clicked a suspicious link or scanned a QR code but did not submit credentials or information.', 'Record click time, close the page, avoid further interaction, and report the message for Security review.', 1, 'Escalate if URL is confirmed malicious, multiple users clicked, or suspicious prompts/sign-ins follow.', 'high'),
    ('FIX_PHISHING_CREDENTIAL_DATA_EXPOSURE', 'Report Possible Credential or Data Exposure', 'User entered credentials, MFA code, payment information, or sensitive data into a suspicious site.', 'Treat as possible account compromise and initiate password reset/account protection and Security escalation according to policy.', 1, 'Escalate immediately to Security and Identity for password reset, session revocation, MFA review, and sign-in investigation.', 'high'),
    ('FIX_PHISHING_ATTACHMENT_OPENED', 'Report Suspicious Attachment Opened', 'User opened or downloaded a suspicious attachment and the endpoint may need review.', 'Record attachment details and escalate for endpoint/security review without opening or executing the file.', 1, 'Escalate to Security/Endpoint for malware review, scan, isolation decision, and containment guidance.', 'high'),
    ('FIX_PHISHING_TRIAGE_REPORT', 'Triage and Report Suspicious Email', 'IT Support Specialist reviews the report safely and routes it through the approved security process.', 'Review message indicators using approved tools, preserve headers/original message when possible, and route to Security/email protection workflow.', 1, 'Escalate if indicators are suspicious, campaign scope is unclear, or containment actions such as purge/blocking may be needed.', 'medium'),
    ('FIX_PHISHING_ESCALATE_ACCOUNT_COMPROMISE', 'Escalate Possible Account Compromise', 'Credentials or MFA interaction may indicate account compromise risk.', 'Escalate immediately and collect user, timestamp, URL, message subject, submitted data type, sign-in activity, and containment actions.', 1, 'Security/Identity should review sign-ins, reset password, revoke sessions, review MFA, and check mailbox rules according to policy.', 'high'),
    ('FIX_PHISHING_ESCALATE_ENDPOINT_REVIEW', 'Escalate Endpoint Malware Review', 'Suspicious attachment or download may require endpoint scan, isolation, or Security review.', 'Collect device name, file name, sender, and time opened/downloaded, then escalate through endpoint/security process.', 1, 'Security/Endpoint should assess detection, scan/isolate if needed, and determine malware containment actions.', 'high'),
    ('FIX_PHISHING_ESCALATE_CAMPAIGN', 'Escalate Possible Phishing Campaign', 'Multiple users or high-risk themes may indicate an active phishing campaign.', 'Identify affected users and message indicators, then escalate for blocking, purge, and wider communication if needed.', 1, 'Security/email administration should search, purge, block sender/URL/attachment, and monitor additional reports.', 'high'),
    ('FIX_PHISHING_DOCUMENT_MONITOR', 'Document and Monitor Reported Phish', 'Low-impact phishing report is documented and monitored after safe reporting.', 'Document the report, confirm no interaction occurred, and advise the user to report future similar messages.', 0, 'Escalate if new evidence appears, more users report it, or the user later remembers interaction.', 'low'),
]

PHISHING_EMAIL_SOLUTION_STEPS = {
    'FIX_PHISHING_REPORT_EMAIL_SAFELY': {
        'user': [
            'Do not click links or open attachments.',
            'Do not reply to the sender.',
            'Use the company phishing-report button if available.',
            'Keep the message available until IT confirms next steps.',
            'Delete the email only after reporting if instructed.',
        ],
        'technician': [
            'Confirm the user did not click, open, reply, forward, or enter information.',
            'Collect sender, subject, timestamp, and screenshot/header if available.',
            'Submit or route the message through the approved phishing-report workflow.',
            'Search for similar reports if tools are available.',
            'Document the ticket and advise the user not to interact.',
        ],
        'admin': [
            'Escalate to Security if the message appears malicious, high-risk, or part of a wider campaign.',
            'Provide sender, subject, timestamps, URLs, attachment details, and affected user information if available.',
        ],
    },
    'FIX_PHISHING_LINK_CLICKED_NO_DATA': {
        'user': [
            'Close the browser tab.',
            'Do not enter any information.',
            'Report the message to IT.',
            'Tell IT the approximate time you clicked.',
            'Watch for unexpected MFA prompts or login alerts.',
        ],
        'technician': [
            'Record the click time, URL if safely available, browser used, and device name.',
            'Do not manually browse to the link outside approved security tools.',
            'Check whether credentials were entered or MFA was approved.',
            'Escalate to Security if the URL is confirmed malicious or multiple users clicked.',
            'Advise user to report any follow-up prompts or alerts.',
        ],
        'admin': [
            'Escalate if the URL is malicious, the user sees unexpected MFA prompts, or similar reports are received.',
            'Security may need to block the URL/domain and review sign-in activity.',
        ],
    },
    'FIX_PHISHING_CREDENTIAL_DATA_EXPOSURE': {
        'user': [
            'Stop using the suspicious website immediately.',
            'Do not approve additional MFA prompts.',
            'Contact IT or Security immediately.',
            'Be ready to reset your password using the official company process.',
            'Tell IT exactly what information was entered.',
        ],
        'technician': [
            'Treat as possible account compromise.',
            'Verify what information was submitted and when.',
            'Initiate password reset/account protection process according to policy.',
            'Check for unexpected MFA prompts or successful suspicious sign-ins if access is available.',
            'Escalate to Security/Identity with user, timestamp, URL, and actions taken.',
        ],
        'admin': [
            'Escalate immediately for password reset, token/session revocation, MFA review, sign-in log review, and mailbox rule review according to policy.',
            'Prioritize as High because credentials, MFA, payment, or sensitive data may be exposed.',
        ],
    },
    'FIX_PHISHING_ATTACHMENT_OPENED': {
        'user': [
            'Stop opening the attachment.',
            'Do not forward the file.',
            'Tell IT what file was opened and when.',
            'Leave the device powered on unless IT instructs otherwise.',
            'Report any pop-ups, warnings, or unusual behavior.',
        ],
        'technician': [
            'Record attachment name, file type, sender, and time opened.',
            'Check whether endpoint protection generated alerts if tools are available.',
            'Do not execute or open the attachment manually.',
            'Escalate to Security/Endpoint for scan, isolation, or forensic review if needed.',
            'Document device name and user actions.',
        ],
        'admin': [
            'Escalate to Security/Endpoint for malware review and containment decisions.',
            'Follow company policy before isolating the device or deleting files.',
        ],
    },
    'FIX_PHISHING_TRIAGE_REPORT': {
        'user': [
            'Wait for IT confirmation.',
            'Do not interact with the message.',
            'Report any similar messages received later.',
        ],
        'technician': [
            'Review sender, reply-to, domain, subject, links, and attachment metadata using approved tools.',
            'Preserve headers or original message according to policy.',
            'Check if the email was reported by other users.',
            'Submit to Security or email protection workflow.',
            'Update the ticket with triage results.',
        ],
        'admin': [
            'Escalate if sender/domain/URL/attachment indicators are suspicious or if additional users are affected.',
            'Security/email administration may need to purge messages or block indicators.',
        ],
    },
    'FIX_PHISHING_ESCALATE_ACCOUNT_COMPROMISE': {
        'user': [
            'Stop signing in from the suspicious page.',
            'Do not approve unexpected MFA prompts.',
            'Follow IT instructions for password reset and account review.',
            'Report any unusual mailbox or account activity.',
        ],
        'technician': [
            'Escalate immediately to Security/Identity.',
            'Capture user, timestamp, URL, message subject, and submitted data type.',
            'Check for suspicious sign-ins if access is available.',
            'Request password reset, session revocation, MFA review, and mailbox-rule review according to policy.',
            'Document containment steps.',
        ],
        'admin': [
            'Security/Identity should handle account compromise review, session revocation, mailbox rule review, and risk-based containment.',
            'Do not close the ticket until containment and user communication are documented.',
        ],
    },
    'FIX_PHISHING_ESCALATE_ENDPOINT_REVIEW': {
        'user': [
            'Stop interacting with the file.',
            'Keep the device connected and available for IT unless instructed otherwise.',
            'Report any pop-ups, slowness, or unusual behavior.',
        ],
        'technician': [
            'Record device name, file name, sender, and time opened/downloaded.',
            'Check endpoint protection status if available.',
            'Escalate to Security/Endpoint team for malware review.',
            'Follow company policy before isolating device or deleting files.',
            'Document actions and user impact.',
        ],
        'admin': [
            'Security/Endpoint should decide whether scan, isolation, containment, or forensic review is needed.',
            'Escalate priority if the device shows suspicious behavior or sensitive work may be exposed.',
        ],
    },
    'FIX_PHISHING_ESCALATE_CAMPAIGN': {
        'user': [
            'Do not forward the email to coworkers.',
            'Tell IT if coworkers received similar messages.',
            'Report any interaction with the message.',
        ],
        'technician': [
            'Identify affected users and message indicators.',
            'Search for similar reports if tools are available.',
            'Escalate to Security/email administration for message purge/blocking.',
            'Provide sender, subject, URLs, attachment details, timestamps, and affected user list.',
            'Monitor for follow-up reports.',
        ],
        'admin': [
            'Security/email administration should search for the campaign, purge messages if appropriate, block indicators, and prepare user communication if needed.',
            'Treat as High priority if multiple users or high-risk business themes are involved.',
        ],
    },
    'FIX_PHISHING_DOCUMENT_MONITOR': {
        'user': [
            'Delete the message only after IT confirms it is safe or handled.',
            'Report any future similar messages.',
            'Continue not interacting with suspicious links or attachments.',
        ],
        'technician': [
            'Document the report and user action.',
            'Confirm no credentials or files were submitted/opened.',
            'Confirm phishing-report workflow was completed.',
            'Close or monitor the ticket based on policy.',
        ],
        'admin': [
            'Escalate if new evidence appears, more users report similar messages, or the user later remembers interaction.',
        ],
    },
}

PHISHING_USER_DIAGNOSTIC_NODES = [
    ('ROOT_PHISHING_USER', None, 'category', 'Phishing Email Reported', 'User-friendly diagnostic path for suspicious email reports.', None, None, None, None, 1),
    ('Q_PHISHING_CLICK_OPEN_USER', 'ROOT_PHISHING_USER', 'question', 'Check Interaction', None, 'Did you click a link, scan a QR code, or open an attachment?', None, None, None, 1),
    ('S_PHISHING_REPORT_SAFE_USER', 'Q_PHISHING_CLICK_OPEN_USER', 'solution', 'Report Suspicious Email Safely', None, None, 'Did you click a link, scan a QR code, or open an attachment?', 'No', 'FIX_PHISHING_REPORT_EMAIL_SAFELY', 1),
    ('Q_PHISHING_ENTERED_DATA_USER', 'Q_PHISHING_CLICK_OPEN_USER', 'question', 'Check Data Exposure', None, 'Did you enter credentials, MFA code, payment information, or personal information?', 'Did you click a link, scan a QR code, or open an attachment?', 'Yes', None, 2),
    ('S_PHISHING_DATA_EXPOSURE_USER', 'Q_PHISHING_ENTERED_DATA_USER', 'solution', 'Report Possible Credential or Data Exposure', None, None, 'Did you enter credentials, MFA code, payment information, or personal information?', 'Yes', 'FIX_PHISHING_CREDENTIAL_DATA_EXPOSURE', 1),
    ('Q_PHISHING_ATTACHMENT_USER', 'Q_PHISHING_ENTERED_DATA_USER', 'question', 'Check Attachment Opened', None, 'Did you open or download an attachment?', 'Did you enter credentials, MFA code, payment information, or personal information?', 'No', None, 2),
    ('S_PHISHING_ATTACHMENT_USER', 'Q_PHISHING_ATTACHMENT_USER', 'solution', 'Report Suspicious Attachment Opened', None, None, 'Did you open or download an attachment?', 'Yes', 'FIX_PHISHING_ATTACHMENT_OPENED', 1),
    ('S_PHISHING_LINK_CLICKED_USER', 'Q_PHISHING_ATTACHMENT_USER', 'solution', 'Report Link Clicked Without Data Entry', None, None, 'Did you open or download an attachment?', 'No', 'FIX_PHISHING_LINK_CLICKED_NO_DATA', 2),
]

PHISHING_TECH_DIAGNOSTIC_NODES = [
    ('ROOT_PHISHING_TECH', None, 'category', 'Phishing Email Reported - IT Support Specialist', 'IT Support Specialist diagnostic path for suspicious email triage and escalation.', None, None, None, None, 1),
    ('Q_PHISHING_INTERACTION_TECH', 'ROOT_PHISHING_TECH', 'question', 'Determine User Interaction', None, 'Did the user interact with the message?', None, None, None, 1),
    ('S_PHISHING_TRIAGE_TECH', 'Q_PHISHING_INTERACTION_TECH', 'solution', 'Triage and Report Suspicious Email', None, None, 'Did the user interact with the message?', 'No interaction', 'FIX_PHISHING_TRIAGE_REPORT', 1),
    ('Q_PHISHING_CREDENTIALS_TECH', 'Q_PHISHING_INTERACTION_TECH', 'question', 'Check Credential or MFA Exposure', None, 'Did the user enter credentials or approve MFA?', 'Did the user interact with the message?', 'Interaction occurred', None, 2),
    ('S_PHISHING_COMPROMISE_TECH', 'Q_PHISHING_CREDENTIALS_TECH', 'solution', 'Escalate Possible Account Compromise', None, None, 'Did the user enter credentials or approve MFA?', 'Yes', 'FIX_PHISHING_ESCALATE_ACCOUNT_COMPROMISE', 1),
    ('Q_PHISHING_ATTACHMENT_TECH', 'Q_PHISHING_CREDENTIALS_TECH', 'question', 'Check Attachment or Download', None, 'Did the user open or download an attachment?', 'Did the user enter credentials or approve MFA?', 'No', None, 2),
    ('S_PHISHING_ENDPOINT_REVIEW_TECH', 'Q_PHISHING_ATTACHMENT_TECH', 'solution', 'Escalate Endpoint Malware Review', None, None, 'Did the user open or download an attachment?', 'Yes', 'FIX_PHISHING_ESCALATE_ENDPOINT_REVIEW', 1),
    ('Q_PHISHING_CAMPAIGN_TECH', 'Q_PHISHING_ATTACHMENT_TECH', 'question', 'Check Campaign Scope', None, 'Are multiple users or high-risk themes involved?', 'Did the user open or download an attachment?', 'No', None, 2),
    ('S_PHISHING_CAMPAIGN_TECH', 'Q_PHISHING_CAMPAIGN_TECH', 'solution', 'Escalate Possible Phishing Campaign', None, None, 'Are multiple users or high-risk themes involved?', 'Yes', 'FIX_PHISHING_ESCALATE_CAMPAIGN', 1),
    ('S_PHISHING_MONITOR_TECH', 'Q_PHISHING_CAMPAIGN_TECH', 'solution', 'Document and Monitor Reported Phish', None, None, 'Are multiple users or high-risk themes involved?', 'No', 'FIX_PHISHING_DOCUMENT_MONITOR', 2),
]

def seed_phishing_email_reported_content(cursor):
    """Seed Phishing Email Reported KB article, solutions, steps, and diagnostic trees."""
    code_, title, category, severity, description = PHISHING_EMAIL_PROBLEM
    cursor.execute("""
        INSERT INTO problem (problem_code, title, category, severity, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(problem_code) DO UPDATE SET
            title=excluded.title, category=excluded.category, severity=excluded.severity,
            description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, PHISHING_EMAIL_PROBLEM)
    cursor.execute('SELECT problem_id FROM problem WHERE problem_code = ?', (code_,))
    row = cursor.fetchone()
    if not row:
        return
    problem_id = row['problem_id']
    cursor.execute("""
        INSERT INTO kb_article (problem_id, title, summary, difficulty, estimated_time, escalation_required, escalation_notes, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, difficulty=excluded.difficulty,
            estimated_time=excluded.estimated_time, escalation_required=excluded.escalation_required,
            escalation_notes=excluded.escalation_notes, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, PHISHING_EMAIL_KB['title'], PHISHING_EMAIL_KB['summary'], PHISHING_EMAIL_KB['difficulty'], PHISHING_EMAIL_KB['estimated_time'], PHISHING_EMAIL_KB['escalation_required'], PHISHING_EMAIL_KB['escalation_notes']))
    cursor.execute('SELECT kb_article_id FROM kb_article WHERE problem_id = ?', (problem_id,))
    article = cursor.fetchone()
    if article:
        kb_id = article['kb_article_id']
        delete_kb_child_rows(cursor, kb_id)
        insert_kb_child_rows(cursor, 'kb_article_tag', 'tag', kb_id, PHISHING_EMAIL_KB['tags'])
        insert_kb_child_rows(cursor, 'kb_article_symptom', 'symptom', kb_id, PHISHING_EMAIL_KB['symptoms'])
        insert_kb_child_rows(cursor, 'kb_article_cause', 'cause', kb_id, PHISHING_EMAIL_KB['causes'])
        insert_kb_child_rows(cursor, 'kb_article_user_step', 'step_text', kb_id, PHISHING_EMAIL_KB['user_steps'])
        insert_kb_child_rows(cursor, 'kb_article_it_step', 'step_text', kb_id, PHISHING_EMAIL_KB['it_steps'])
    cursor.executemany("""
        INSERT INTO solution (solution_code, title, summary, resolution_steps, escalation_required, escalation_notes, priority_recommendation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(solution_code) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, resolution_steps=excluded.resolution_steps,
            escalation_required=excluded.escalation_required, escalation_notes=excluded.escalation_notes,
            priority_recommendation=excluded.priority_recommendation, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, PHISHING_EMAIL_SOLUTIONS)
    for solution_code, audience_steps in PHISHING_EMAIL_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue
        for audience, steps in audience_steps.items():
            cursor.execute('DELETE FROM solution_step WHERE solution_id = ? AND audience = ?', (solution_id, audience))
            cursor.executemany('INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)', [(solution_id, audience, step, idx) for idx, step in enumerate(steps, start=1)])
    seed_phishing_email_tree(cursor, 'user', 'PHISHING_EMAIL_REPORTED_USER', 'Phishing Email Reported - User Diagnostic', 'User-friendly diagnostic tree for suspicious emails, clicked links, credential exposure, and attachment handling.', PHISHING_USER_DIAGNOSTIC_NODES)
    seed_phishing_email_tree(cursor, 'technician', 'PHISHING_EMAIL_REPORTED_TECHNICIAN', 'Phishing Email Reported - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for phishing triage, endpoint review, account compromise, and campaign escalation.', PHISHING_TECH_DIAGNOSTIC_NODES)

def seed_phishing_email_tree(cursor, audience, tree_code, title, description, nodes):
    problem_id = get_problem_id_for_tree_code(cursor, 'PHISHING_EMAIL_REPORTED')
    cursor.execute("""
        INSERT INTO diagnostic_tree (problem_id, diagnostic_tree_code, base_tree_code, audience, title, description, is_active, updated_at)
        VALUES (?, ?, 'PHISHING_EMAIL_REPORTED', ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(diagnostic_tree_code) DO UPDATE SET
            problem_id=excluded.problem_id, base_tree_code=excluded.base_tree_code, audience=excluded.audience,
            title=excluded.title, description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, tree_code, audience, title, description))
    tree_id = get_diagnostic_tree_id_by_code(cursor, tree_code)
    if not tree_id:
        return
    cursor.execute('UPDATE diagnostic_node SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE diagnostic_tree_id = ?', (tree_id,))
    for node_key, parent_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_code, sort_order in nodes:
        parent_id = get_diagnostic_node_id_by_tree_and_key(cursor, tree_id, parent_key) if parent_key else None
        solution_id = get_solution_id_by_code(cursor, solution_code) if solution_code else None
        cursor.execute("""
            INSERT INTO diagnostic_node (
                diagnostic_tree_id, parent_diagnostic_node_id, problem_id, diagnostic_tree_code,
                node_key, node_type, title, description, prompt_text,
                condition_label, condition_value, solution_id, sort_order, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(diagnostic_tree_code, node_key) DO UPDATE SET
                diagnostic_tree_id=excluded.diagnostic_tree_id,
                parent_diagnostic_node_id=excluded.parent_diagnostic_node_id,
                problem_id=excluded.problem_id,
                node_type=excluded.node_type,
                title=excluded.title,
                description=excluded.description,
                prompt_text=excluded.prompt_text,
                condition_label=excluded.condition_label,
                condition_value=excluded.condition_value,
                solution_id=excluded.solution_id,
                sort_order=excluded.sort_order,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (tree_id, parent_id, problem_id, tree_code, node_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_id, sort_order))


# -----------------------------
# MALWARE OR VIRUS SUSPECTED CONTENT
# -----------------------------
MALWARE_PROBLEM = (
    'MALWARE_OR_VIRUS_SUSPECTED',
    'Malware or Virus Suspected',
    'Security',
    'high',
    'User suspects the device may be infected because of endpoint alerts, pop-ups, unusual behavior, suspicious downloads, ransomware messages, or activity after a link, attachment, or file download.',
)

MALWARE_KB = {
    'title': 'Malware or Virus Suspected',
    'summary': 'Use this guide when a computer shows antivirus alerts, suspicious pop-ups, browser redirects, unknown software, strange behavior, ransomware messages, or unusual activity after clicking a link, opening an attachment, or downloading a file.',
    'difficulty': 'Intermediate',
    'estimated_time': '10-30 minutes',
    'escalation_required': 1,
    'escalation_notes': 'Escalate immediately if ransomware is suspected, endpoint protection reports active malware, credentials were entered, MFA was approved unexpectedly, multiple devices are affected, or sensitive data may be exposed.',
    'tags': ['malware', 'virus', 'ransomware', 'endpoint security', 'antivirus alert', 'suspicious pop-up', 'browser hijack', 'unwanted software', 'phishing', 'security incident'],
    'symptoms': [
        'Endpoint protection or antivirus shows a malware, virus, or suspicious activity alert.',
        'User sees repeated pop-ups, fake security warnings, browser redirects, or changed homepage/search engine.',
        'Computer becomes unusually slow, apps open or close unexpectedly, or unexpected reboots occur.',
        'User recently clicked a suspicious link, opened an attachment, downloaded software, installed an extension, or used a USB device.',
        'Files are missing, renamed, encrypted, or a ransom message appears.',
        'Unknown applications, browser extensions, startup items, or remote access tools appear on the device.',
        'User entered credentials or approved MFA after suspicious activity, creating account compromise risk.',
    ],
    'causes': [
        'Common: phishing link, malicious attachment, untrusted download, browser hijacker, fake security warning, unwanted software, outdated browser/app/OS, suspicious USB device, endpoint protection detection, or user approval of a suspicious download or macro.',
        'Advanced: compromised account delivering malware, drive-by download, malicious script or PowerShell execution, unauthorized remote access tool, credential-stealing malware, ransomware, command-and-control traffic, persistence through startup/service/scheduled task, disabled security tool, false positive, or lateral movement attempt.',
    ],
    'user_steps': [
        'Stop interacting with suspicious pop-ups, files, links, or warning messages.',
        'Do not call phone numbers shown in pop-up security warnings.',
        'Do not install cleanup tools from the internet.',
        'Do not restore quarantined files or click Allow on security alerts.',
        'Disconnect from VPN and stop accessing sensitive company systems if instructed by IT.',
        'Leave the computer powered on unless IT or Security tells you otherwise.',
        'Take a screenshot or photo of the warning if safe.',
        'Tell IT what happened before the issue started, such as a clicked link, opened attachment, downloaded software, USB device, or MFA prompt.',
        'If you entered a password or approved MFA, report that immediately.',
        'Do not delete files or clear browser history before IT reviews if malware is suspected.',
    ],
    'it_steps': [
        'Tier 1: Instruct the user not to click, download, call, pay, approve MFA, restore quarantined files, or interact further with suspicious prompts.',
        'Tier 1: Confirm user, device name, location, network state, VPN status, and exact symptom.',
        'Tier 1: Ask what action occurred before the alert: clicked link, opened attachment, downloaded file, installed software, plugged in USB, entered credentials, or approved MFA.',
        'Tier 1: Ask whether endpoint protection displayed an alert and collect the detection name, file path, and action taken if visible.',
        'Tier 1: Capture screenshots/photos, timestamps, file names, sender/URL if related to email, and user actions.',
        'Tier 1: Determine whether the device is currently connected to VPN or sensitive systems and follow company isolation policy.',
        'Tier 1: Check whether the issue is one device, multiple devices, or related to a known phishing report.',
        'Tier 1: If credentials were entered or MFA was approved, route to Identity/Security response immediately.',
        'Tier 1: Escalate promptly if ransomware, credential theft, endpoint alert, unknown remote access, or suspicious network activity is suspected.',
        'Tier 2 / Security-aware support: Check endpoint protection status, alert details, detection name, remediation action, and security-agent health if tools are available.',
        'Tier 2 / Security-aware support: Confirm whether the detection was blocked, quarantined, allowed, remediated, or still active.',
        'Tier 2 / Security-aware support: Run an approved full scan or offline scan only according to company policy.',
        'Tier 2 / Security-aware support: Check for suspicious installed applications, browser extensions, startup items, scheduled tasks, or unauthorized remote access tools.',
        'Tier 2 / Security-aware support: Review recent downloads and user-reported file names without opening suspicious files.',
        'Tier 2 / Security-aware support: Check event/security logs and suspicious sign-in or MFA activity when applicable.',
        'Tier 2 / Security-aware support: Determine whether this appears to be a false positive, unwanted software/adware, browser hijack, malicious download, credential theft, ransomware, or active compromise.',
        'Tier 2 / Security-aware support: Escalate with detection name, file path/hash if available, device name, user actions, timeline, screenshots, network status, and containment status.',
    ],
}

MALWARE_SOLUTIONS = [
    ('FIX_MALWARE_REPORT_RANSOMWARE', 'Report Possible Ransomware Immediately', 'Missing, renamed, encrypted files or ransom messages require urgent Security response.', 'Stop work on the affected device, preserve evidence, follow isolation policy, and escalate immediately to Security/Endpoint/Incident Response.', 1, 'Critical escalation if ransomware indicators, encrypted files, ransom note, or multiple affected devices appear.', 'critical'),
    ('FIX_MALWARE_CREDENTIAL_EXPOSURE', 'Report Possible Credential Exposure', 'User entered credentials or approved MFA after suspicious activity.', 'Treat as possible account compromise and route to Security/Identity for account protection and sign-in review.', 1, 'Escalate immediately for password reset, session/token revocation, MFA review, and suspicious sign-in investigation.', 'high'),
    ('FIX_MALWARE_REPORT_ENDPOINT_ALERT', 'Report Endpoint Security Alert', 'Endpoint protection reported malware or suspicious activity.', 'Record detection details, verify remediation status, and follow approved endpoint security workflow.', 1, 'Escalate if active, repeated, high-severity, unclear, or not fully remediated.', 'high'),
    ('FIX_MALWARE_POPUPS_UNKNOWN_SOFTWARE', 'Report Suspicious Pop-Ups or Unknown Software', 'Pop-ups, browser redirects, and unknown software may indicate adware, browser hijack, scam page, or unwanted software.', 'Avoid interaction with scam prompts, check browser/software state, and use approved cleanup or escalation workflow.', 0, 'Escalate if behavior persists, involves payment/credentials, or endpoint alerts appear.', 'medium'),
    ('FIX_MALWARE_SUBMIT_DETAILS', 'Submit Malware Suspicion Details', 'The user suspects malware but there is no obvious alert or confirmed compromise.', 'Collect symptoms, timeline, recent user actions, and endpoint status to determine malware, unwanted software, performance issue, or false alarm.', 0, 'Escalate if evidence is unclear, symptoms worsen, or suspicious activity is identified.', 'medium'),
    ('FIX_MALWARE_ESCALATE_RANSOMWARE', 'Escalate Possible Ransomware Incident', 'Ransomware indicators require immediate escalation and containment.', 'Follow incident escalation policy, preserve evidence, and coordinate containment with Security/Endpoint teams.', 1, 'Critical escalation to Security/Incident Response and Endpoint teams.', 'critical'),
    ('FIX_MALWARE_VERIFY_REMEDIATION_MONITOR', 'Verify Endpoint Remediation and Monitor', 'Endpoint protection blocked or quarantined the threat, but IT should verify remediation.', 'Confirm endpoint remediation, run approved follow-up checks, and monitor for repeated detections.', 0, 'Escalate if detections repeat, endpoint protection is unhealthy, or source is unknown.', 'medium'),
    ('FIX_MALWARE_ESCALATE_ACTIVE_DETECTION', 'Escalate Active Malware Detection', 'Malware appears active, unremediated, repeated, or unclear.', 'Capture detection and endpoint details, follow containment policy, and escalate to Security/Endpoint.', 1, 'High escalation for active or unresolved malware detection.', 'high'),
    ('FIX_MALWARE_ESCALATE_SUSPICIOUS_INTERACTION', 'Escalate Suspicious Interaction for Security Review', 'User interacted with a suspicious link, file, USB device, or download and device risk is uncertain.', 'Capture suspicious source details, check endpoint status, and escalate if risk cannot be ruled out.', 1, 'Escalate if file/link/source is suspicious, credentials/MFA were involved, or endpoint evidence is unclear.', 'high'),
    ('FIX_MALWARE_UNWANTED_SOFTWARE_FALSE_ALARM', 'Investigate Possible Unwanted Software or False Alarm', 'Symptoms may be unwanted software, browser scam, performance issue, or false positive rather than confirmed malware.', 'Check installed apps, browser extensions, startup items, endpoint status, and remove unwanted software only through approved process.', 0, 'Escalate if behavior persists, false positive cannot be confirmed, or evidence suggests active compromise.', 'medium'),
]

MALWARE_SOLUTION_STEPS = {
    'FIX_MALWARE_REPORT_RANSOMWARE': {
        'user': ['Stop using the device for work immediately.', 'Do not pay, reply, or click anything in the ransom message.', 'Leave the device powered on unless IT or Security says otherwise.', 'Disconnect from VPN if instructed by IT.', 'Contact IT or Security immediately and report the exact message.'],
        'technician': ['Treat as a potential critical incident.', 'Record user, device name, time observed, screenshots, ransom message, and affected files.', 'Follow company isolation/escalation policy.', 'Do not attempt ad-hoc cleanup or deletion.', 'Escalate immediately to Security, Endpoint, or Incident Response.'],
        'admin': ['Escalation notes: Treat ransomware indicators as critical and preserve evidence.', 'Escalation notes: Provide screenshots, affected paths, device name, network status, and containment status.'],
    },
    'FIX_MALWARE_CREDENTIAL_EXPOSURE': {
        'user': ['Stop using the suspicious page or app.', 'Do not approve additional MFA prompts.', 'Contact IT or Security immediately.', 'Be ready to reset your password using the official process.', 'Tell IT exactly what information was entered.'],
        'technician': ['Treat as possible account compromise.', 'Capture timeline, account, URL/file/source, and user actions.', 'Escalate to Security/Identity for password reset, session revocation, MFA review, and sign-in review.', 'Check whether malware or phishing caused the exposure.', 'Document containment actions.'],
        'admin': ['Escalation notes: Identity/Security should review sign-ins, tokens/sessions, MFA methods, and mailbox/account activity.', 'Escalation notes: Prioritize if MFA was approved or privileged/sensitive access is involved.'],
    },
    'FIX_MALWARE_REPORT_ENDPOINT_ALERT': {
        'user': ['Do not ignore the alert.', 'Do not click Allow or restore a quarantined item.', 'Take a screenshot or note the threat name.', 'Contact IT with the alert details.'],
        'technician': ['Record detection name, file path, action taken, and timestamp.', 'Check whether the threat was blocked, quarantined, remediated, or active.', 'Verify endpoint protection is healthy and up to date.', 'Run approved scan/remediation workflow if allowed.', 'Escalate if active, repeated, high-severity, or unclear.'],
        'admin': ['Escalation notes: Provide detection name, severity, file path/hash if available, device name, and remediation status.', 'Escalation notes: Escalate repeated or active detections to Security/Endpoint.'],
    },
    'FIX_MALWARE_POPUPS_UNKNOWN_SOFTWARE': {
        'user': ['Do not call phone numbers in pop-ups.', 'Do not install suggested cleanup tools.', 'Close the browser if safe.', 'Take a screenshot if possible.', 'Contact IT if pop-ups return.'],
        'technician': ['Identify whether the pop-up is a browser-based scam, adware, or endpoint alert.', 'Check browser extensions and recently installed applications.', 'Use approved browser reset/cleanup steps if allowed.', 'Check endpoint protection status.', 'Escalate if behavior persists or includes credential/payment prompts.'],
        'admin': ['Escalation notes: Security/Endpoint should review persistent browser hijack, payment prompts, credential prompts, or repeated unwanted software.', 'Escalation notes: Do not use unapproved third-party cleanup utilities.'],
    },
    'FIX_MALWARE_SUBMIT_DETAILS': {
        'user': ['Describe what changed on the device.', 'Note when the issue started.', 'Mention recent downloads, links, attachments, or USB devices.', 'Submit screenshots if available.'],
        'technician': ['Collect symptoms, timeline, user actions, and device name.', 'Check for endpoint alerts, suspicious installs, browser changes, or performance symptoms.', 'Run approved checks based on company policy.', 'Determine whether this is malware, unwanted software, performance issue, or false alarm.', 'Document findings and next action.'],
        'admin': ['Escalation notes: Escalate if risk cannot be ruled out or evidence suggests suspicious software/activity.', 'Escalation notes: Include user timeline, device name, screenshots, and suspected source.'],
    },
    'FIX_MALWARE_ESCALATE_RANSOMWARE': {
        'user': ['Stop working on the affected device.', 'Do not connect external drives.', 'Do not move or rename affected files.', 'Wait for Security instructions.'],
        'technician': ['Follow incident escalation policy immediately.', 'Capture screenshots, device name, username, network status, and affected file paths.', 'Coordinate isolation according to policy.', 'Notify Security/Incident Response with urgency.', 'Do not perform unapproved remediation.'],
        'admin': ['Escalation notes: Critical handoff to Security/Incident Response for containment and recovery coordination.', 'Escalation notes: Include scope, affected data, device/network status, and whether other devices are affected.'],
    },
    'FIX_MALWARE_VERIFY_REMEDIATION_MONITOR': {
        'user': ['Do not restore quarantined files.', 'Continue normal work only after IT confirms.', 'Report if alerts return.'],
        'technician': ['Confirm the detection status and remediation action.', 'Run approved follow-up scan if policy allows.', 'Verify endpoint protection health.', 'Check whether related phishing/email/download source needs review.', 'Monitor for repeated detections.'],
        'admin': ['Escalation notes: Escalate repeated detections, unhealthy security agent, or unknown infection source.', 'Escalation notes: Attach remediation status and follow-up scan result.'],
    },
    'FIX_MALWARE_ESCALATE_ACTIVE_DETECTION': {
        'user': ['Stop using the device for sensitive work.', 'Keep the device available for IT or Security.', 'Do not attempt cleanup tools yourself.'],
        'technician': ['Capture detection details and endpoint status.', 'Follow containment policy.', 'Escalate to Security/Endpoint team.', 'Provide detection name, file path, user actions, device name, network status, and timestamps.', 'Document whether the device was isolated or still online.'],
        'admin': ['Escalation notes: Security/Endpoint should determine containment and remediation plan.', 'Escalation notes: Include detection details, endpoint health, network status, and user actions.'],
    },
    'FIX_MALWARE_ESCALATE_SUSPICIOUS_INTERACTION': {
        'user': ['Stop interacting with the suspicious item.', 'Do not delete evidence unless IT says so.', 'Tell IT exactly what you clicked, opened, or downloaded.', 'Report any pop-ups, MFA prompts, or security alerts.'],
        'technician': ['Capture the suspicious source, file name, URL, sender, device, and timeline.', 'Check endpoint protection and recent downloads.', 'Check whether credentials or MFA were involved.', 'Escalate to Security/Endpoint if risk cannot be ruled out.', 'Document containment and user guidance.'],
        'admin': ['Escalation notes: Escalate when file/link risk is unknown or user interaction could have exposed the endpoint/account.', 'Escalation notes: Include source indicators, timestamps, and whether credentials/MFA were involved.'],
    },
    'FIX_MALWARE_UNWANTED_SOFTWARE_FALSE_ALARM': {
        'user': ['Report the exact symptom.', 'Do not install cleanup tools.', 'Send screenshots if available.', 'Wait for IT instructions.'],
        'technician': ['Check installed applications, browser extensions, startup items, and endpoint status.', 'Determine whether this is adware/unwanted software, browser scam, legitimate alert, or false positive.', 'Remove unwanted software only through approved tools/process.', 'Escalate if behavior persists or evidence is unclear.', 'Document findings and prevention advice.'],
        'admin': ['Escalation notes: Escalate persistent or unclear symptoms to Endpoint/Security.', 'Escalation notes: If false positive is likely, document detection source and reason.'],
    },
}

MALWARE_USER_DIAGNOSTIC_NODES = [
    ('ROOT_MALWARE_USER', None, 'category', 'Malware or Virus Suspected', 'User-friendly diagnostic path for possible malware, endpoint alerts, suspicious pop-ups, credential exposure, and ransomware indicators.', None, None, None, None, 1),
    ('Q_MALWARE_RANSOMWARE_USER', 'ROOT_MALWARE_USER', 'question', 'Check Ransomware Indicators', None, 'Are files missing, renamed, encrypted, or showing a ransom message?', None, None, None, 1),
    ('S_MALWARE_RANSOMWARE_USER', 'Q_MALWARE_RANSOMWARE_USER', 'solution', 'Report Possible Ransomware Immediately', None, None, 'Are files missing, renamed, encrypted, or showing a ransom message?', 'Yes', 'FIX_MALWARE_REPORT_RANSOMWARE', 1),
    ('Q_MALWARE_CREDENTIALS_USER', 'Q_MALWARE_RANSOMWARE_USER', 'question', 'Check Credential or MFA Exposure', None, 'Did you enter credentials, approve MFA, or provide sensitive information?', 'Are files missing, renamed, encrypted, or showing a ransom message?', 'No', None, 2),
    ('S_MALWARE_CREDENTIALS_USER', 'Q_MALWARE_CREDENTIALS_USER', 'solution', 'Report Possible Credential Exposure', None, None, 'Did you enter credentials, approve MFA, or provide sensitive information?', 'Yes', 'FIX_MALWARE_CREDENTIAL_EXPOSURE', 1),
    ('Q_MALWARE_ENDPOINT_ALERT_USER', 'Q_MALWARE_CREDENTIALS_USER', 'question', 'Check Endpoint Security Alert', None, 'Did antivirus or endpoint protection show an alert?', 'Did you enter credentials, approve MFA, or provide sensitive information?', 'No', None, 2),
    ('S_MALWARE_ENDPOINT_ALERT_USER', 'Q_MALWARE_ENDPOINT_ALERT_USER', 'solution', 'Report Endpoint Security Alert', None, None, 'Did antivirus or endpoint protection show an alert?', 'Yes', 'FIX_MALWARE_REPORT_ENDPOINT_ALERT', 1),
    ('Q_MALWARE_POPUPS_USER', 'Q_MALWARE_ENDPOINT_ALERT_USER', 'question', 'Check Pop-Ups or Unknown Software', None, 'Are you seeing pop-ups, redirects, or unknown programs?', 'Did antivirus or endpoint protection show an alert?', 'No', None, 2),
    ('S_MALWARE_POPUPS_USER', 'Q_MALWARE_POPUPS_USER', 'solution', 'Report Suspicious Pop-Ups or Unknown Software', None, None, 'Are you seeing pop-ups, redirects, or unknown programs?', 'Yes', 'FIX_MALWARE_POPUPS_UNKNOWN_SOFTWARE', 1),
    ('S_MALWARE_DETAILS_USER', 'Q_MALWARE_POPUPS_USER', 'solution', 'Submit Malware Suspicion Details', None, None, 'Are you seeing pop-ups, redirects, or unknown programs?', 'No', 'FIX_MALWARE_SUBMIT_DETAILS', 2),
]

MALWARE_TECH_DIAGNOSTIC_NODES = [
    ('ROOT_MALWARE_TECH', None, 'category', 'Malware or Virus Suspected - IT Support Specialist', 'IT Support Specialist diagnostic path for malware suspicion, endpoint detections, ransomware indicators, and escalation.', None, None, None, None, 1),
    ('Q_MALWARE_RANSOMWARE_TECH', 'ROOT_MALWARE_TECH', 'question', 'Check Ransomware Indicators', None, 'Are ransomware indicators present?', None, None, None, 1),
    ('S_MALWARE_ESCALATE_RANSOMWARE_TECH', 'Q_MALWARE_RANSOMWARE_TECH', 'solution', 'Escalate Possible Ransomware Incident', None, None, 'Are ransomware indicators present?', 'Yes', 'FIX_MALWARE_ESCALATE_RANSOMWARE', 1),
    ('Q_MALWARE_ENDPOINT_ALERT_TECH', 'Q_MALWARE_RANSOMWARE_TECH', 'question', 'Check Endpoint Detection', None, 'Is there an endpoint protection alert or detection name?', 'Are ransomware indicators present?', 'No', None, 2),
    ('Q_MALWARE_BLOCKED_TECH', 'Q_MALWARE_ENDPOINT_ALERT_TECH', 'question', 'Check Remediation Status', None, 'Was the threat blocked or quarantined?', 'Is there an endpoint protection alert or detection name?', 'Yes', None, 1),
    ('S_MALWARE_REMEDIATION_TECH', 'Q_MALWARE_BLOCKED_TECH', 'solution', 'Verify Endpoint Remediation and Monitor', None, None, 'Was the threat blocked or quarantined?', 'Yes', 'FIX_MALWARE_VERIFY_REMEDIATION_MONITOR', 1),
    ('S_MALWARE_ACTIVE_DETECTION_TECH', 'Q_MALWARE_BLOCKED_TECH', 'solution', 'Escalate Active Malware Detection', None, None, 'Was the threat blocked or quarantined?', 'No / Unknown', 'FIX_MALWARE_ESCALATE_ACTIVE_DETECTION', 2),
    ('Q_MALWARE_INTERACTION_TECH', 'Q_MALWARE_ENDPOINT_ALERT_TECH', 'question', 'Check Suspicious Interaction', None, 'Did the user interact with a suspicious link, file, USB device, or download?', 'Is there an endpoint protection alert or detection name?', 'No', None, 2),
    ('S_MALWARE_SUSPICIOUS_INTERACTION_TECH', 'Q_MALWARE_INTERACTION_TECH', 'solution', 'Escalate Suspicious Interaction for Security Review', None, None, 'Did the user interact with a suspicious link, file, USB device, or download?', 'Yes', 'FIX_MALWARE_ESCALATE_SUSPICIOUS_INTERACTION', 1),
    ('S_MALWARE_FALSE_ALARM_TECH', 'Q_MALWARE_INTERACTION_TECH', 'solution', 'Investigate Possible Unwanted Software or False Alarm', None, None, 'Did the user interact with a suspicious link, file, USB device, or download?', 'No', 'FIX_MALWARE_UNWANTED_SOFTWARE_FALSE_ALARM', 2),
]

def seed_malware_or_virus_suspected_content(cursor):
    """Seed Malware or Virus Suspected KB article, solutions, steps, and diagnostic trees."""
    code_, title, category, severity, description = MALWARE_PROBLEM
    cursor.execute("""
        INSERT INTO problem (problem_code, title, category, severity, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(problem_code) DO UPDATE SET
            title=excluded.title, category=excluded.category, severity=excluded.severity,
            description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, MALWARE_PROBLEM)
    cursor.execute('SELECT problem_id FROM problem WHERE problem_code = ?', (code_,))
    row = cursor.fetchone()
    if not row:
        return
    problem_id = row['problem_id']
    cursor.execute("""
        INSERT INTO kb_article (problem_id, title, summary, difficulty, estimated_time, escalation_required, escalation_notes, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, difficulty=excluded.difficulty,
            estimated_time=excluded.estimated_time, escalation_required=excluded.escalation_required,
            escalation_notes=excluded.escalation_notes, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, MALWARE_KB['title'], MALWARE_KB['summary'], MALWARE_KB['difficulty'], MALWARE_KB['estimated_time'], MALWARE_KB['escalation_required'], MALWARE_KB['escalation_notes']))
    cursor.execute('SELECT kb_article_id FROM kb_article WHERE problem_id = ?', (problem_id,))
    article = cursor.fetchone()
    if article:
        kb_id = article['kb_article_id']
        delete_kb_child_rows(cursor, kb_id)
        insert_kb_child_rows(cursor, 'kb_article_tag', 'tag', kb_id, MALWARE_KB['tags'])
        insert_kb_child_rows(cursor, 'kb_article_symptom', 'symptom', kb_id, MALWARE_KB['symptoms'])
        insert_kb_child_rows(cursor, 'kb_article_cause', 'cause', kb_id, MALWARE_KB['causes'])
        insert_kb_child_rows(cursor, 'kb_article_user_step', 'step_text', kb_id, MALWARE_KB['user_steps'])
        insert_kb_child_rows(cursor, 'kb_article_it_step', 'step_text', kb_id, MALWARE_KB['it_steps'])
    cursor.executemany("""
        INSERT INTO solution (solution_code, title, summary, resolution_steps, escalation_required, escalation_notes, priority_recommendation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(solution_code) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, resolution_steps=excluded.resolution_steps,
            escalation_required=excluded.escalation_required, escalation_notes=excluded.escalation_notes,
            priority_recommendation=excluded.priority_recommendation, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, MALWARE_SOLUTIONS)
    for solution_code, audience_steps in MALWARE_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue
        for audience, steps in audience_steps.items():
            cursor.execute('DELETE FROM solution_step WHERE solution_id = ? AND audience = ?', (solution_id, audience))
            cursor.executemany('INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)', [(solution_id, audience, step, idx) for idx, step in enumerate(steps, start=1)])
    seed_malware_tree(cursor, 'user', 'MALWARE_OR_VIRUS_SUSPECTED_USER', 'Malware or Virus Suspected - User Diagnostic', 'User-friendly diagnostic tree for possible malware, endpoint alerts, suspicious pop-ups, credential exposure, and ransomware indicators.', MALWARE_USER_DIAGNOSTIC_NODES)
    seed_malware_tree(cursor, 'technician', 'MALWARE_OR_VIRUS_SUSPECTED_TECHNICIAN', 'Malware or Virus Suspected - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for malware suspicion, endpoint detections, ransomware indicators, and escalation.', MALWARE_TECH_DIAGNOSTIC_NODES)

def seed_malware_tree(cursor, audience, tree_code, title, description, nodes):
    problem_id = get_problem_id_for_tree_code(cursor, 'MALWARE_OR_VIRUS_SUSPECTED')
    cursor.execute("""
        INSERT INTO diagnostic_tree (problem_id, diagnostic_tree_code, base_tree_code, audience, title, description, is_active, updated_at)
        VALUES (?, ?, 'MALWARE_OR_VIRUS_SUSPECTED', ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(diagnostic_tree_code) DO UPDATE SET
            problem_id=excluded.problem_id, base_tree_code=excluded.base_tree_code, audience=excluded.audience,
            title=excluded.title, description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, tree_code, audience, title, description))
    tree_id = get_diagnostic_tree_id_by_code(cursor, tree_code)
    if not tree_id:
        return
    cursor.execute('UPDATE diagnostic_node SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE diagnostic_tree_id = ?', (tree_id,))
    for node_key, parent_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_code, sort_order in nodes:
        parent_id = get_diagnostic_node_id_by_tree_and_key(cursor, tree_id, parent_key) if parent_key else None
        solution_id = get_solution_id_by_code(cursor, solution_code) if solution_code else None
        cursor.execute("""
            INSERT INTO diagnostic_node (
                diagnostic_tree_id, parent_diagnostic_node_id, problem_id, diagnostic_tree_code,
                node_key, node_type, title, description, prompt_text,
                condition_label, condition_value, solution_id, sort_order, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(diagnostic_tree_code, node_key) DO UPDATE SET
                diagnostic_tree_id=excluded.diagnostic_tree_id,
                parent_diagnostic_node_id=excluded.parent_diagnostic_node_id,
                problem_id=excluded.problem_id,
                node_type=excluded.node_type,
                title=excluded.title,
                description=excluded.description,
                prompt_text=excluded.prompt_text,
                condition_label=excluded.condition_label,
                condition_value=excluded.condition_value,
                solution_id=excluded.solution_id,
                sort_order=excluded.sort_order,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (tree_id, parent_id, problem_id, tree_code, node_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_id, sort_order))


# -----------------------------
# EMAIL ATTACHMENT NOT OPENING CONTENT
# -----------------------------
EMAIL_ATTACHMENT_PROBLEM = (
    'EMAIL_ATTACHMENT_NOT_OPENING',
    'Email Attachment Not Opening',
    'Email, Calendar & Collaboration',
    'medium',
    'User cannot open, preview, download, or save an email attachment.',
)

EMAIL_ATTACHMENT_KB = {
    'title': 'Email Attachment Not Opening',
    'summary': 'Use this guide when an email attachment is blocked, will not preview, will not download, opens in the wrong app, appears corrupted, or looks suspicious.',
    'difficulty': 'Intermediate',
    'estimated_time': '5-20 minutes',
    'escalation_required': 0,
    'escalation_notes': 'Escalate if the attachment is suspicious, blocked by security, asks to enable macros, requires an unavailable app, is business-critical, or affects multiple users.',
    'tags': ['email attachment', 'Outlook attachment', 'blocked attachment', 'file association', 'preview handler', 'phishing', 'malware', 'secure sharing', 'OneDrive', 'SharePoint'],
    'symptoms': [
        'Attachment is blocked by the email client or security policy.',
        'Attachment preview does not work.',
        'Attachment downloads but does not open.',
        'File opens in the wrong application or no application is available.',
        'File appears corrupted or incomplete.',
        'Desktop email client fails but webmail works.',
        'Attachment asks the user to enable macros, bypass warnings, or looks suspicious.',
    ],
    'causes': [
        'Common: blocked file type, unsafe attachment, missing required application, broken file association, corrupted file, incomplete download, Outlook/email client cache issue, endpoint security block, permission-protected file, or phishing/malware risk.',
        'Advanced: mail gateway/DLP stripping, attachment size or policy limits, encrypted or sensitivity-labeled content, OneDrive/SharePoint link permissions, corrupt Outlook profile/OST cache, preview-handler/add-in issue, Protected View or Trust Center restriction, endpoint quarantine, or phishing campaign using malicious attachments.',
    ],
    'user_steps': [
        'Do not open the attachment if the email is unexpected or suspicious.',
        'Do not enable macros or bypass security warnings unless IT confirms it is safe.',
        'Confirm you recognize the sender and expected the attachment.',
        'Try opening the attachment from webmail if you are using the desktop email app.',
        'Restart the email application and try again.',
        'Save the attachment to a known location and open it from there only if it is trusted.',
        'Confirm you have the right application to open the file type.',
        'Ask the sender to resend the file or share it through an approved company storage link if the file may be blocked.',
        'Take a screenshot of the exact error message.',
        'Report the email to IT/Security if the attachment looks suspicious.',
    ],
    'it_steps': [
        'Tier 1: Confirm the user, device name, email client, operating system, attachment file name/type, sender, and exact error message.',
        'Tier 1: Ask whether the user expected the attachment and recognizes the sender.',
        'Tier 1: Determine whether the issue affects one attachment, one sender, one file type, one user/device, or multiple users.',
        'Tier 1: Confirm whether the attachment is blocked, corrupted, missing, not downloading, or not previewing.',
        'Tier 1: Check whether the attachment opens in webmail versus the desktop email client.',
        'Tier 1: Confirm the required application is installed and the file association is correct.',
        'Tier 1: Restart the email client and retest.',
        'Tier 1: Ask the sender to resend the file or provide it through approved OneDrive, SharePoint, or company storage if safe.',
        'Tier 1: If the file type is blocked by policy, do not bypass controls.',
        'Tier 1: If suspicious, route to phishing/malware process and preserve the message.',
        'Tier 2 / Email, Endpoint, and Security-aware checks: Check whether the file extension is blocked by Outlook, mail gateway, DLP, or endpoint security policy.',
        'Tier 2 / Email, Endpoint, and Security-aware checks: Review whether endpoint protection quarantined or blocked the file.',
        'Tier 2 / Email, Endpoint, and Security-aware checks: Check if the attachment contains risky content such as macros, scripts, executable files, password-protected archives, or unusual compressed files.',
        'Tier 2 / Email, Endpoint, and Security-aware checks: Compare webmail, desktop client, another device, or test mailbox behavior where policy allows.',
        'Tier 2 / Email, Endpoint, and Security-aware checks: Check email client cache/profile if desktop client fails but webmail works.',
        'Tier 2 / Email, Endpoint, and Security-aware checks: Check Outlook add-ins or preview handlers if preview fails but download works.',
        'Tier 2 / Email, Endpoint, and Security-aware checks: Check whether the file is encrypted, sensitivity-labeled, permission-protected, or actually a cloud link with permission restrictions.',
        'Determine whether root cause is security policy block, missing app/file association, corrupted file, email client/profile issue, permission-protected file, or phishing/malware risk.',
        'Escalate with sender, subject, file name/type, error message, screenshots, affected users, and security indicators.',
    ],
}

EMAIL_ATTACHMENT_SOLUTIONS = [
    ('FIX_EMAIL_ATTACHMENT_REPORT_SUSPICIOUS', 'Report Suspicious Attachment Safely', 'The attachment may be phishing or malware-related and should not be opened.', 'Do not open or download the attachment. Report it through the approved phishing/security process and preserve the message.', 1, 'Escalate to Security if the attachment was opened, downloaded, or delivered to multiple users.', 'high'),
    ('FIX_EMAIL_ATTACHMENT_MACRO_WARNING', 'Do Not Enable Macros or Bypass Security Warning', 'Macro/content warnings or bypass prompts can indicate security risk.', 'Do not enable macros, active content, or bypass warnings. Capture the warning and route the file through approved review.', 1, 'Escalate to Security if macro/script content is unexpected or suspicious.', 'high'),
    ('FIX_EMAIL_ATTACHMENT_SECURE_SHARING', 'Use Approved Secure File Sharing Method', 'Blocked attachment types should be shared through approved company storage instead of bypassing email security.', 'Ask the sender to use approved storage such as OneDrive, SharePoint, or company file sharing with proper permissions.', 0, 'Escalate to Email/Security only if a legitimate business exception is required.', 'medium'),
    ('FIX_EMAIL_ATTACHMENT_REQUIRED_APP', 'Install or Select the Correct Application', 'The user may not have the correct app installed or the file association may be wrong.', 'Confirm file type, install the approved required application if needed, or correct the file association.', 0, 'Escalate if software installation requires admin rights or endpoint deployment.', 'medium'),
    ('FIX_EMAIL_ATTACHMENT_RESEND_CLEAN_COPY', 'Ask Sender to Resend or Share Clean Copy', 'The attachment may be corrupted, incomplete, or damaged during sending/download.', 'Ask the sender to resend the file or share it through approved company storage, then retest with the clean copy.', 0, 'Escalate if mail gateway modification, stripping, or size-policy issue is suspected.', 'medium'),
    ('FIX_EMAIL_ATTACHMENT_WEBMAIL_CLIENT_TEST', 'Try Webmail and Report Email Client Issue', 'If webmail works but desktop client fails, the issue may be local email client cache/profile/preview handler.', 'Compare webmail and desktop client behavior, restart the email client, and troubleshoot local cache/profile/preview handler if needed.', 0, 'Escalate if local email profile/client repair is required or multiple users are affected.', 'medium'),
    ('FIX_EMAIL_ATTACHMENT_SECURITY_REVIEW', 'Escalate Suspicious Attachment for Security Review', 'Suspicious or high-risk attachment requires Security review.', 'Collect message details and escalate without opening the file manually.', 1, 'Security should review indicators, attachment risk, user interaction, and message scope.', 'high'),
    ('FIX_EMAIL_ATTACHMENT_OUTLOOK_CLIENT_CACHE', 'Troubleshoot Outlook Client, Cache, or Preview Handler', 'Desktop email client may have local cache, profile, preview, or add-in issue.', 'Compare webmail versus desktop behavior and repair the email client/profile or preview handler if needed.', 0, 'Escalate to Endpoint/Email support if mailbox profile or client repair is required.', 'medium'),
    ('FIX_EMAIL_ATTACHMENT_FILE_INTEGRITY_PERMISSION', 'Verify File Integrity, Permissions, or Sender Copy', 'The file may be corrupted, permission-protected, encrypted, or incomplete.', 'Confirm sender copy, permissions, encryption/sensitivity labels, and whether other users can open the same file.', 0, 'Escalate to Email/Collaboration or sender IT if permissions or mail handling are involved.', 'medium'),
]

EMAIL_ATTACHMENT_SOLUTION_STEPS = {
    'FIX_EMAIL_ATTACHMENT_REPORT_SUSPICIOUS': {
        'user': ['Do not open or download the attachment.', 'Do not reply to the sender.', 'Use the company phishing-report button if available.', 'Tell IT whether you clicked, opened, or downloaded anything.', 'Keep the message available until IT/Security confirms next steps.'],
        'technician': ['Confirm whether the user interacted with the attachment.', 'Collect sender, subject, received time, file name/type, and screenshot.', 'Preserve the email according to company process.', 'Route to phishing/malware workflow if suspicious.', 'Escalate to Security if the attachment was opened or delivered to multiple users.'],
        'admin': ['Security should analyze the message and attachment using approved tools, not by opening the file manually.', 'Escalate priority if the user opened the attachment or similar messages reached multiple users.'],
    },
    'FIX_EMAIL_ATTACHMENT_MACRO_WARNING': {
        'user': ['Do not enable macros or active content.', 'Do not bypass security warnings.', 'Contact IT with a screenshot of the warning.', 'Ask the sender to provide the file through an approved safe method if needed.'],
        'technician': ['Confirm file type and warning message.', 'Check whether the attachment is expected and business-related.', 'Do not bypass security controls for the user.', 'Escalate to Security if macro/script content is unexpected or suspicious.', 'Route legitimate business needs through approved secure file sharing.'],
        'admin': ['Security should review macro/script content and decide whether it is malicious, blocked by policy, or requires an approved exception.'],
    },
    'FIX_EMAIL_ATTACHMENT_SECURE_SHARING': {
        'user': ['Ask the sender to upload the file to approved company storage.', 'Ask the sender to share a link with correct permissions.', 'Do not ask the sender to rename risky file extensions to bypass security.', 'Contact IT if the file is business-critical.'],
        'technician': ['Confirm the attachment is blocked by policy.', 'Explain that blocked files are restricted for security reasons.', 'Recommend approved OneDrive, SharePoint, or company file-sharing method.', 'Confirm the user has permission to the shared link.', 'Escalate to Email/Security only if a legitimate business exception is required.'],
        'admin': ['Email/Security should review any requested exception and avoid weakening attachment controls without business approval.'],
    },
    'FIX_EMAIL_ATTACHMENT_REQUIRED_APP': {
        'user': ['Note the file extension, such as PDF, DOCX, XLSX, CSV, or ZIP.', 'Do not install software from unknown websites.', 'Contact IT if the file opens in the wrong app or no app is available.'],
        'technician': ['Confirm the file type and required application.', 'Check whether the correct approved application is installed.', 'Fix file association if appropriate.', 'Install from approved software source if needed.', 'Retest opening the attachment.'],
        'admin': ['Endpoint/Desktop Support should handle application deployment if install requires admin rights, licensing, or managed software distribution.'],
    },
    'FIX_EMAIL_ATTACHMENT_RESEND_CLEAN_COPY': {
        'user': ['Ask the sender to resend the file.', 'Ask the sender to share it through approved company storage if possible.', 'Try opening the new copy.', 'Report if multiple people cannot open the same file.'],
        'technician': ['Confirm whether the same file fails for other users.', 'Check whether file size or attachment limit may have affected delivery.', 'Ask sender to resend or share clean copy through approved storage.', 'Escalate if mail gateway is modifying or stripping attachments.'],
        'admin': ['Email/Collaboration should review mail gateway, DLP, attachment size, or transport rules if clean copies fail for multiple users.'],
    },
    'FIX_EMAIL_ATTACHMENT_WEBMAIL_CLIENT_TEST': {
        'user': ['Try opening the attachment from webmail/browser.', 'Restart the desktop email app.', 'Report whether the attachment works in webmail but not desktop app.', 'Send IT a screenshot of the desktop app error.'],
        'technician': ['Compare webmail versus desktop client behavior.', 'Restart email client and retest.', 'Check attachment preview handler and file association.', 'Check Outlook cache/profile if needed.', 'Escalate to Endpoint/Email support if local client repair is required.'],
        'admin': ['Endpoint/Email support should repair profile/client issues or investigate mailbox sync if desktop behavior differs from webmail.'],
    },
    'FIX_EMAIL_ATTACHMENT_SECURITY_REVIEW': {
        'user': ['Do not open or forward the attachment.', 'Report whether you interacted with it.', 'Wait for IT/Security instructions.'],
        'technician': ['Collect sender, subject, file name/type, received time, and user actions.', 'Do not open the file manually.', 'Check email/endpoint security alerts if available.', 'Escalate to Security with message details and indicators.', 'If user opened it, route to malware/endpoint review.'],
        'admin': ['Security should review the attachment safely, check campaign scope, and coordinate containment if the file is malicious.'],
    },
    'FIX_EMAIL_ATTACHMENT_OUTLOOK_CLIENT_CACHE': {
        'user': ['Restart Outlook or the email client.', 'Try opening the attachment in webmail.', 'Restart the computer if instructed.', 'Report if the issue affects all attachments or only one.'],
        'technician': ['Confirm attachment works in webmail.', 'Check whether preview or download fails.', 'Disable problematic add-ins only if allowed.', 'Repair email client/profile if needed.', 'Escalate if mailbox profile or endpoint repair is required.'],
        'admin': ['Endpoint/Email support should investigate persistent cache, OST/profile, add-in, or preview-handler issues.'],
    },
    'FIX_EMAIL_ATTACHMENT_FILE_INTEGRITY_PERMISSION': {
        'user': ['Ask sender to confirm the file opens on their side.', 'Ask whether the file is password-protected or restricted.', 'Request a clean copy or approved sharing link.', 'Submit the error screenshot to IT.'],
        'technician': ['Confirm whether file is encrypted, sensitivity-labeled, password-protected, or permission-restricted.', 'Check whether other users can open the same attachment.', 'Confirm whether sender sent a complete valid file.', 'Escalate to Email/Collaboration or sender IT if file permissions or mail handling are involved.'],
        'admin': ['Email/Collaboration should verify labeling, encryption, sharing permissions, and mail transport handling when local troubleshooting does not explain the failure.'],
    },
}

EMAIL_ATTACHMENT_USER_DIAGNOSTIC_NODES = [
    ('ROOT_EMAIL_ATTACHMENT_USER', None, 'category', 'Email Attachment Not Opening', 'User-friendly diagnostic path for blocked, suspicious, corrupted, or client-specific email attachment issues.', None, None, None, None, 1),
    ('Q_EMAIL_ATTACHMENT_EXPECTED_USER', 'ROOT_EMAIL_ATTACHMENT_USER', 'question', 'Check Sender and Expected Attachment', None, 'Were you expecting this attachment and do you recognize the sender?', None, None, None, 1),
    ('S_EMAIL_ATTACHMENT_SUSPICIOUS_USER', 'Q_EMAIL_ATTACHMENT_EXPECTED_USER', 'solution', 'Report Suspicious Attachment Safely', None, None, 'Were you expecting this attachment and do you recognize the sender?', 'No / Not sure', 'FIX_EMAIL_ATTACHMENT_REPORT_SUSPICIOUS', 1),
    ('Q_EMAIL_ATTACHMENT_MACRO_USER', 'Q_EMAIL_ATTACHMENT_EXPECTED_USER', 'question', 'Check Macro or Warning Prompt', None, 'Does it ask you to enable macros/content or bypass a warning?', 'Were you expecting this attachment and do you recognize the sender?', 'Yes', None, 2),
    ('S_EMAIL_ATTACHMENT_MACRO_USER', 'Q_EMAIL_ATTACHMENT_MACRO_USER', 'solution', 'Do Not Enable Macros or Bypass Security Warning', None, None, 'Does it ask you to enable macros/content or bypass a warning?', 'Yes', 'FIX_EMAIL_ATTACHMENT_MACRO_WARNING', 1),
    ('Q_EMAIL_ATTACHMENT_BEHAVIOR_USER', 'Q_EMAIL_ATTACHMENT_MACRO_USER', 'question', 'Check Attachment Behavior', None, 'What happens when you open it?', 'Does it ask you to enable macros/content or bypass a warning?', 'No', None, 2),
    ('S_EMAIL_ATTACHMENT_BLOCKED_USER', 'Q_EMAIL_ATTACHMENT_BEHAVIOR_USER', 'solution', 'Use Approved Secure File Sharing Method', None, None, 'What happens when you open it?', 'Blocked by email/security', 'FIX_EMAIL_ATTACHMENT_SECURE_SHARING', 1),
    ('S_EMAIL_ATTACHMENT_APP_USER', 'Q_EMAIL_ATTACHMENT_BEHAVIOR_USER', 'solution', 'Install or Select the Correct Application', None, None, 'What happens when you open it?', 'Missing app / wrong app', 'FIX_EMAIL_ATTACHMENT_REQUIRED_APP', 2),
    ('S_EMAIL_ATTACHMENT_CORRUPT_USER', 'Q_EMAIL_ATTACHMENT_BEHAVIOR_USER', 'solution', 'Ask Sender to Resend or Share Clean Copy', None, None, 'What happens when you open it?', 'Error/corrupted file', 'FIX_EMAIL_ATTACHMENT_RESEND_CLEAN_COPY', 3),
    ('S_EMAIL_ATTACHMENT_CLIENT_USER', 'Q_EMAIL_ATTACHMENT_BEHAVIOR_USER', 'solution', 'Try Webmail and Report Email Client Issue', None, None, 'What happens when you open it?', 'Desktop client only', 'FIX_EMAIL_ATTACHMENT_WEBMAIL_CLIENT_TEST', 4),
]

EMAIL_ATTACHMENT_TECH_DIAGNOSTIC_NODES = [
    ('ROOT_EMAIL_ATTACHMENT_TECH', None, 'category', 'Email Attachment Not Opening - IT Support Specialist', 'IT Support Specialist diagnostic path for attachment security, blocked file types, required apps, and email-client issues.', None, None, None, None, 1),
    ('Q_EMAIL_ATTACHMENT_RISK_TECH', 'ROOT_EMAIL_ATTACHMENT_TECH', 'question', 'Check Attachment Risk', None, 'Is the attachment suspicious, unexpected, or high-risk?', None, None, None, 1),
    ('S_EMAIL_ATTACHMENT_SECURITY_TECH', 'Q_EMAIL_ATTACHMENT_RISK_TECH', 'solution', 'Escalate Suspicious Attachment for Security Review', None, None, 'Is the attachment suspicious, unexpected, or high-risk?', 'Yes', 'FIX_EMAIL_ATTACHMENT_SECURITY_REVIEW', 1),
    ('Q_EMAIL_ATTACHMENT_BLOCKED_TECH', 'Q_EMAIL_ATTACHMENT_RISK_TECH', 'question', 'Check Policy Block', None, 'Is the file type blocked by policy?', 'Is the attachment suspicious, unexpected, or high-risk?', 'No', None, 2),
    ('S_EMAIL_ATTACHMENT_SECURE_SHARE_TECH', 'Q_EMAIL_ATTACHMENT_BLOCKED_TECH', 'solution', 'Use Approved Secure File Sharing Method', None, None, 'Is the file type blocked by policy?', 'Yes', 'FIX_EMAIL_ATTACHMENT_SECURE_SHARING', 1),
    ('Q_EMAIL_ATTACHMENT_WEBMAIL_TECH', 'Q_EMAIL_ATTACHMENT_BLOCKED_TECH', 'question', 'Compare Webmail and Desktop Client', None, 'Does it work in webmail but fail in the desktop client?', 'Is the file type blocked by policy?', 'No', None, 2),
    ('S_EMAIL_ATTACHMENT_OUTLOOK_TECH', 'Q_EMAIL_ATTACHMENT_WEBMAIL_TECH', 'solution', 'Troubleshoot Outlook Client, Cache, or Preview Handler', None, None, 'Does it work in webmail but fail in the desktop client?', 'Yes', 'FIX_EMAIL_ATTACHMENT_OUTLOOK_CLIENT_CACHE', 1),
    ('Q_EMAIL_ATTACHMENT_APP_TECH', 'Q_EMAIL_ATTACHMENT_WEBMAIL_TECH', 'question', 'Check Required Application', None, 'Is the required application installed and file association correct?', 'Does it work in webmail but fail in the desktop client?', 'No', None, 2),
    ('S_EMAIL_ATTACHMENT_REQUIRED_APP_TECH', 'Q_EMAIL_ATTACHMENT_APP_TECH', 'solution', 'Install Required App or Fix File Association', None, None, 'Is the required application installed and file association correct?', 'No', 'FIX_EMAIL_ATTACHMENT_REQUIRED_APP', 1),
    ('S_EMAIL_ATTACHMENT_INTEGRITY_TECH', 'Q_EMAIL_ATTACHMENT_APP_TECH', 'solution', 'Verify File Integrity, Permissions, or Sender Copy', None, None, 'Is the required application installed and file association correct?', 'Yes', 'FIX_EMAIL_ATTACHMENT_FILE_INTEGRITY_PERMISSION', 2),
]

def seed_email_attachment_not_opening_content(cursor):
    """Seed Email Attachment Not Opening KB article, solutions, steps, and diagnostic trees."""
    code_, title, category, severity, description = EMAIL_ATTACHMENT_PROBLEM
    cursor.execute("""
        INSERT INTO problem (problem_code, title, category, severity, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(problem_code) DO UPDATE SET
            title=excluded.title, category=excluded.category, severity=excluded.severity,
            description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, EMAIL_ATTACHMENT_PROBLEM)
    cursor.execute('SELECT problem_id FROM problem WHERE problem_code = ?', (code_,))
    row = cursor.fetchone()
    if not row:
        return
    problem_id = row['problem_id']
    cursor.execute("""
        INSERT INTO kb_article (problem_id, title, summary, difficulty, estimated_time, escalation_required, escalation_notes, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, difficulty=excluded.difficulty,
            estimated_time=excluded.estimated_time, escalation_required=excluded.escalation_required,
            escalation_notes=excluded.escalation_notes, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, EMAIL_ATTACHMENT_KB['title'], EMAIL_ATTACHMENT_KB['summary'], EMAIL_ATTACHMENT_KB['difficulty'], EMAIL_ATTACHMENT_KB['estimated_time'], EMAIL_ATTACHMENT_KB['escalation_required'], EMAIL_ATTACHMENT_KB['escalation_notes']))
    cursor.execute('SELECT kb_article_id FROM kb_article WHERE problem_id = ?', (problem_id,))
    article = cursor.fetchone()
    if article:
        kb_id = article['kb_article_id']
        delete_kb_child_rows(cursor, kb_id)
        insert_kb_child_rows(cursor, 'kb_article_tag', 'tag', kb_id, EMAIL_ATTACHMENT_KB['tags'])
        insert_kb_child_rows(cursor, 'kb_article_symptom', 'symptom', kb_id, EMAIL_ATTACHMENT_KB['symptoms'])
        insert_kb_child_rows(cursor, 'kb_article_cause', 'cause', kb_id, EMAIL_ATTACHMENT_KB['causes'])
        insert_kb_child_rows(cursor, 'kb_article_user_step', 'step_text', kb_id, EMAIL_ATTACHMENT_KB['user_steps'])
        insert_kb_child_rows(cursor, 'kb_article_it_step', 'step_text', kb_id, EMAIL_ATTACHMENT_KB['it_steps'])
    cursor.executemany("""
        INSERT INTO solution (solution_code, title, summary, resolution_steps, escalation_required, escalation_notes, priority_recommendation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(solution_code) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, resolution_steps=excluded.resolution_steps,
            escalation_required=excluded.escalation_required, escalation_notes=excluded.escalation_notes,
            priority_recommendation=excluded.priority_recommendation, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, EMAIL_ATTACHMENT_SOLUTIONS)
    for solution_code, audience_steps in EMAIL_ATTACHMENT_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue
        for audience, steps in audience_steps.items():
            cursor.execute('DELETE FROM solution_step WHERE solution_id = ? AND audience = ?', (solution_id, audience))
            cursor.executemany('INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)', [(solution_id, audience, step, idx) for idx, step in enumerate(steps, start=1)])
    seed_email_attachment_tree(cursor, 'user', 'EMAIL_ATTACHMENT_NOT_OPENING_USER', 'Email Attachment Not Opening - User Diagnostic', 'User-friendly diagnostic tree for attachment opening, security, and app/client issues.', EMAIL_ATTACHMENT_USER_DIAGNOSTIC_NODES)
    seed_email_attachment_tree(cursor, 'technician', 'EMAIL_ATTACHMENT_NOT_OPENING_TECHNICIAN', 'Email Attachment Not Opening - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for attachment security, policy, file integrity, and email-client issues.', EMAIL_ATTACHMENT_TECH_DIAGNOSTIC_NODES)

def seed_email_attachment_tree(cursor, audience, tree_code, title, description, nodes):
    problem_id = get_problem_id_for_tree_code(cursor, 'EMAIL_ATTACHMENT_NOT_OPENING')
    cursor.execute("""
        INSERT INTO diagnostic_tree (problem_id, diagnostic_tree_code, base_tree_code, audience, title, description, is_active, updated_at)
        VALUES (?, ?, 'EMAIL_ATTACHMENT_NOT_OPENING', ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(diagnostic_tree_code) DO UPDATE SET
            problem_id=excluded.problem_id, base_tree_code=excluded.base_tree_code, audience=excluded.audience,
            title=excluded.title, description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, tree_code, audience, title, description))
    tree_id = get_diagnostic_tree_id_by_code(cursor, tree_code)
    if not tree_id:
        return
    cursor.execute('UPDATE diagnostic_node SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE diagnostic_tree_id = ?', (tree_id,))
    for node_key, parent_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_code, sort_order in nodes:
        parent_id = get_diagnostic_node_id_by_tree_and_key(cursor, tree_id, parent_key) if parent_key else None
        solution_id = get_solution_id_by_code(cursor, solution_code) if solution_code else None
        cursor.execute("""
            INSERT INTO diagnostic_node (
                diagnostic_tree_id, parent_diagnostic_node_id, problem_id, diagnostic_tree_code,
                node_key, node_type, title, description, prompt_text,
                condition_label, condition_value, solution_id, sort_order, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(diagnostic_tree_code, node_key) DO UPDATE SET
                diagnostic_tree_id=excluded.diagnostic_tree_id,
                parent_diagnostic_node_id=excluded.parent_diagnostic_node_id,
                problem_id=excluded.problem_id,
                node_type=excluded.node_type,
                title=excluded.title,
                description=excluded.description,
                prompt_text=excluded.prompt_text,
                condition_label=excluded.condition_label,
                condition_value=excluded.condition_value,
                solution_id=excluded.solution_id,
                sort_order=excluded.sort_order,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (tree_id, parent_id, problem_id, tree_code, node_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_id, sort_order))



# -----------------------------
# CALENDAR SYNC ISSUE CONTENT
# -----------------------------
CALENDAR_SYNC_PROBLEM = (
    'CALENDAR_SYNC_ISSUE',
    'Calendar Sync Issue',
    'Email, Calendar & Collaboration',
    'medium',
    'Calendar events are missing, delayed, duplicated, or inconsistent between Outlook desktop, Outlook web, and mobile devices.',
)

CALENDAR_SYNC_KB = {
    'title': 'Calendar Sync Issue',
    'summary': 'Use this guide when calendar events are missing, delayed, duplicated, not updating, or appear on one device but not another.',
    'difficulty': 'Intermediate',
    'estimated_time': '10-25 minutes',
    'escalation_required': 0,
    'escalation_notes': 'Escalate if Outlook web is also incorrect, shared/delegated calendar permissions are inconsistent, mobile/managed device policy blocks sync, multiple users are affected, or a Microsoft 365/Exchange service issue is suspected.',
    'tags': ['calendar sync', 'Outlook calendar', 'Microsoft 365', 'mobile calendar', 'shared calendar', 'delegate calendar', 'Outlook web', 'Exchange', 'sync issue', 'collaboration'],
    'symptoms': [
        'Calendar events are missing, delayed, duplicated, or not updating.',
        'Meetings appear on one device but not another.',
        'Outlook desktop does not match Outlook on the web.',
        'Mobile calendar stopped syncing or does not show work events.',
        'Shared or delegated calendar updates are not visible.',
        'Accepted meetings do not appear or reminders are wrong.',
        'Events disappear and reappear or updates arrive late.',
    ],
    'causes': [
        'Common: Outlook offline/disconnected state, hidden calendar, stale local cache, mobile app permissions disabled, wrong account type, shared/delegate permission issue, poor connectivity, incorrect date/time/time zone, or app needing restart/update.',
        'Advanced: corrupted Outlook profile or OST cache, Exchange ActiveSync/mobile sync issue, Microsoft 365/Exchange service degradation, delegate permission corruption, third-party calendar integration conflict, conditional access/device compliance issue, mailbox throttling, add-in conflict, DNS/proxy/VPN issue, calendar item corruption, or recurring meeting corruption.',
    ],
    'user_steps': [
        'Confirm your internet connection is working.',
        'Check whether the correct calendar is visible or selected in Outlook or the calendar app.',
        'Restart Outlook or the calendar app.',
        'Check Outlook on the web to see whether the calendar is correct there.',
        'If using a phone, confirm the app has permission to access calendar data.',
        'Confirm you are signed in with the correct work account.',
        'Check whether the issue affects your main calendar or a shared/delegated calendar.',
        'Confirm the device date, time, and time zone are correct.',
        'Update Outlook or the mobile app if updates are available.',
        'Submit a ticket if events are still missing or sync is inconsistent.',
    ],
    'it_steps': [
        'Tier 1: Confirm the user, device, email/calendar client, account type, and affected calendar.',
        'Tier 1: Ask where the calendar is correct: Outlook desktop, Outlook on the web, Outlook mobile, native mobile calendar, another device, or nowhere.',
        'Tier 1: Determine whether the issue affects one user, one device, one calendar, a shared calendar, or multiple users.',
        'Tier 1: Confirm the user is signed in with the correct work account.',
        'Tier 1: Check internet connectivity and whether Outlook is offline or disconnected.',
        'Tier 1: Confirm the calendar is selected/visible.',
        'Tier 1: Restart Outlook or the mobile app and retest.',
        'Tier 1: Check whether the issue occurs in Outlook on the web.',
        'Tier 1: Confirm device date, time, and time zone.',
        'Tier 1: Check whether the app has calendar/contact permissions on mobile.',
        'Tier 1: Document screenshots, affected calendar, missing event examples, and last successful sync time.',
        'Tier 2 / Collaboration and Endpoint checks: Compare Outlook desktop, Outlook web, and mobile behavior to isolate local-client versus mailbox/service issue.',
        'Tier 2 / Collaboration and Endpoint checks: Confirm the account is configured as Microsoft 365/Exchange rather than IMAP/POP where calendar sync is required.',
        'Tier 2 / Collaboration and Endpoint checks: Update Outlook/mobile app and retest.',
        'Tier 2 / Collaboration and Endpoint checks: Check Outlook profile health and recreate the profile only if simpler steps fail and company policy allows.',
        'Tier 2 / Collaboration and Endpoint checks: Check shared/delegate calendar permissions if a shared calendar is affected.',
        'Tier 2 / Collaboration and Endpoint checks: Check whether the issue follows the user account or a specific device.',
        'Tier 2 / Collaboration and Endpoint checks: Check whether add-ins or third-party calendar sync tools are involved.',
        'Tier 2 / Collaboration and Endpoint checks: Check mailbox/service health if multiple users are affected.',
        'Tier 2 / Collaboration and Endpoint checks: Check network/proxy/VPN restrictions if sync fails only on a specific network.',
        'Escalate with affected calendar, client versions, account type, sync comparison results, missing event examples, and timestamps.',
    ],
}

CALENDAR_SYNC_SOLUTIONS = [
    ('FIX_CALENDAR_ACCOUNT_VISIBILITY_SYNC', 'Check Account, Calendar Visibility, and App Sync', 'Calendar may not appear because the wrong account/calendar is selected or sync is paused.', 'Confirm the correct work account, visible calendar, app connection, and sync state before deeper troubleshooting.', 0, 'Escalate if mailbox/web calendar is also incorrect or sync remains inconsistent across devices.', 'medium'),
    ('FIX_CALENDAR_LOCAL_CLIENT_SYNC', 'Fix Local Outlook or Mobile Calendar Sync', 'Calendar is correct in Outlook web but not syncing to one local client or mobile device.', 'Restart/update the affected client, check permissions, account type, and sync settings, then re-add account/profile only if policy allows.', 0, 'Escalate to Endpoint/Mobile support if managed-device policy or client repair is needed.', 'medium'),
    ('FIX_CALENDAR_COMPARE_WEB_DESKTOP', 'Compare Outlook Web and Desktop Sync', 'Comparing clients helps determine whether the issue is local, mobile, or mailbox-side.', 'Compare web, desktop, and mobile calendar state and route to the correct local-client, mobile, shared-calendar, or service-side path.', 0, 'Escalate if Outlook web and all clients disagree or mailbox-side data is incorrect.', 'medium'),
    ('FIX_CALENDAR_SHARED_VISIBILITY_PERMISSIONS', 'Check Shared Calendar Visibility and Permissions', 'Shared or delegated calendars may fail because permissions changed or the calendar is hidden.', 'Verify owner, delegate/shared access, visibility, and whether the calendar should still be available.', 0, 'Escalate if delegate/shared calendar permissions appear inconsistent or cannot be corrected by support.', 'medium'),
    ('FIX_CALENDAR_CLIENT_MOBILE_TROUBLESHOOT', 'Troubleshoot Local Client or Mobile Sync', 'One device/client has stale calendar data while the mailbox calendar is correct.', 'Check app version, permissions, disconnected state, account configuration, and local profile/mobile policy.', 0, 'Escalate to Endpoint/Mobile support if managed-device policy, app protection, or client repair is involved.', 'medium'),
    ('FIX_CALENDAR_ACCOUNT_CONFIG_SCOPE', 'Check Account Configuration and Calendar Sync Scope', 'Calendar sync may fail if the account is configured incorrectly or sync scope is limited.', 'Confirm Microsoft 365/Exchange account configuration, calendar/contact sync scope, and mobile/native calendar permissions.', 0, 'Escalate if policy or device management prevents correct account setup or sync.', 'medium'),
    ('FIX_CALENDAR_VERIFY_SHARED_PERMISSIONS', 'Verify Shared Calendar Permissions', 'Shared/delegated calendar sync may fail because the user lacks permission or delegate access is broken.', 'Verify owner, delegate, permission level, affected users, and whether permissions need to be re-applied.', 1, 'Escalate to Email/Collaboration Admin if shared/delegate calendar permission behavior is inconsistent.', 'high'),
    ('FIX_CALENDAR_ESCALATE_SERVICE_ISSUE', 'Escalate Possible Calendar Service Issue', 'Multiple users or Outlook web issues may indicate a mailbox or Microsoft 365/Exchange service problem.', 'Confirm affected scope, check service health/status channels, and escalate with user/event/client evidence.', 1, 'Email/Collaboration Admin or Microsoft 365 support path should review service health, mailbox, and tenant-side issues.', 'high'),
    ('FIX_CALENDAR_ESCALATE_MAILBOX_DATA', 'Escalate Mailbox Calendar Data Issue', 'Calendar data appears wrong at the mailbox/web level for one user.', 'Collect event examples, organizers, timestamps, invite status, recurring-series details, and screenshots for mailbox investigation.', 1, 'Escalate to Email/Collaboration Admin for mailbox/calendar data investigation.', 'high'),
]

CALENDAR_SYNC_SOLUTION_STEPS = {
    'FIX_CALENDAR_ACCOUNT_VISIBILITY_SYNC': {
        'user': ['Confirm you are signed in with your work account.', 'Check that the correct calendar is selected or visible.', 'Restart Outlook or the calendar app.', 'Confirm internet access works.', 'Check Outlook on the web if available.'],
        'technician': ['Confirm the account and affected calendar.', 'Check calendar visibility/selection.', 'Confirm client connection and sync status.', 'Compare Outlook desktop, web, and mobile.', 'Document where the calendar is correct.'],
        'admin': ['Escalate if the calendar is missing or incorrect in Outlook web or multiple devices after basic checks.'],
    },
    'FIX_CALENDAR_LOCAL_CLIENT_SYNC': {
        'user': ['Restart the affected app.', 'Check app permissions for calendar access.', 'Confirm the device has internet access.', 'Update the app if available.', 'Submit a ticket if sync still fails.'],
        'technician': ['Verify Outlook web shows correct data.', 'Restart and update the affected client.', 'Confirm mobile app calendar permissions.', 'Check account type and sync settings.', 'Re-add account or recreate profile only if policy allows and simpler steps fail.'],
        'admin': ['Escalate to Endpoint/Mobile support if local profile repair or managed-device policy is involved.'],
    },
    'FIX_CALENDAR_COMPARE_WEB_DESKTOP': {
        'user': ['Open Outlook on the web.', 'Check if the missing event appears there.', 'Compare with desktop or mobile calendar.', 'Tell IT where the event appears and where it is missing.'],
        'technician': ['Compare calendar state across web, desktop, and mobile.', 'Identify whether the problem follows the user account or a specific device.', 'Check sync errors or disconnected status.', 'Continue with local-client, mobile, shared-calendar, or service-side path.'],
        'admin': ['Escalate based on whether the source of truth appears local-client, mobile, shared-calendar, or mailbox/service-side.'],
    },
    'FIX_CALENDAR_SHARED_VISIBILITY_PERMISSIONS': {
        'user': ['Confirm which shared calendar is affected.', 'Check if the calendar is selected or visible.', 'Ask the calendar owner to confirm you still need access.', 'Submit a ticket if access is missing or updates do not appear.'],
        'technician': ['Confirm calendar owner and affected user.', 'Check whether the shared calendar is selected/visible.', 'Verify permission level or group membership if accessible.', 'Ask user to remove and re-add shared calendar if appropriate.', 'Escalate if delegate/shared calendar permissions appear inconsistent.'],
        'admin': ['Email/Collaboration Admin should review delegate/shared calendar permissions when support cannot confirm or correct them.'],
    },
    'FIX_CALENDAR_CLIENT_MOBILE_TROUBLESHOOT': {
        'user': ['Restart the device or app.', 'Update the Outlook/calendar app.', 'Check calendar permissions on mobile.', 'Confirm internet connectivity.', 'Report whether other devices show the correct calendar.'],
        'technician': ['Confirm the problem is isolated to one client/device.', 'Check app version, permissions, and account configuration.', 'Check for offline or disconnected state.', 'Re-add account or recreate Outlook profile if policy allows.', 'Escalate to Endpoint/Mobile support if managed-device policy is involved.'],
        'admin': ['Escalate if app protection, conditional access, or mobile device management appears to block calendar sync.'],
    },
    'FIX_CALENDAR_ACCOUNT_CONFIG_SCOPE': {
        'user': ['Confirm the account shown in the app is your work account.', 'Do not remove accounts unless IT instructs you.', 'Report whether email sync works but calendar does not.'],
        'technician': ['Confirm whether account is configured as Microsoft 365/Exchange where required.', 'Check whether only email syncs or calendar/contact sync is also enabled.', 'Confirm mobile/native calendar permissions.', 'Correct account setup through approved process.', 'Escalate if policy or device management prevents sync.'],
        'admin': ['Escalate to Collaboration or Mobile/Endpoint teams if correct account type or sync scope cannot be applied due to policy.'],
    },
    'FIX_CALENDAR_VERIFY_SHARED_PERMISSIONS': {
        'user': ['Confirm the shared calendar name and owner.', 'Ask the owner/manager to confirm access should still be granted.', 'Submit a ticket with the calendar name and what is missing.'],
        'technician': ['Verify owner, delegate, and permission level.', 'Check whether issue affects one delegate or many.', 'Re-add sharing/delegate permission if policy allows.', 'Escalate to Email/Collaboration Admin if permission behavior is inconsistent.'],
        'admin': ['Email/Collaboration Admin should validate mailbox/delegate permissions, sharing configuration, and calendar-owner settings.'],
    },
    'FIX_CALENDAR_ESCALATE_SERVICE_ISSUE': {
        'user': ['Record examples of missing or delayed events.', 'Note when the issue started.', 'Avoid repeatedly deleting/recreating meetings unless IT instructs you.'],
        'technician': ['Confirm multiple users or Outlook web are affected.', 'Check service health/status channels if available.', 'Collect affected users, event examples, timestamps, clients, and screenshots.', 'Escalate to Email/Collaboration Admin or Microsoft 365 support path.'],
        'admin': ['Email/Collaboration Admin should review service health, tenant advisories, mailbox status, and broader incident scope.'],
    },
    'FIX_CALENDAR_ESCALATE_MAILBOX_DATA': {
        'user': ['Provide examples of missing or incorrect events.', 'Do not delete or recreate meetings unless instructed.', 'Submit screenshots from Outlook web and desktop if possible.'],
        'technician': ['Confirm Outlook web is also incorrect.', 'Collect event titles, organizers, timestamps, invite status, and screenshots.', 'Check whether issue involves recurring meetings or delegate changes.', 'Escalate to Email/Collaboration Admin for mailbox/calendar investigation.'],
        'admin': ['Email/Collaboration Admin should review mailbox/calendar data, recurring meeting health, delegate changes, and service-side traces where available.'],
    },
}

CALENDAR_SYNC_USER_DIAGNOSTIC_NODES = [
    ('ROOT_CALENDAR_SYNC_USER', None, 'category', 'Calendar Sync Issue', 'User-friendly diagnostic path for missing, delayed, duplicated, or device-specific calendar sync issues.', None, None, None, None, 1),
    ('Q_CALENDAR_WHERE_CORRECT_USER', 'ROOT_CALENDAR_SYNC_USER', 'question', 'Compare Calendar Locations', None, 'Where is the calendar correct?', None, None, None, 1),
    ('S_CALENDAR_LOCAL_SYNC_USER', 'Q_CALENDAR_WHERE_CORRECT_USER', 'solution', 'Fix Local Outlook or Mobile Calendar Sync', None, None, 'Where is the calendar correct?', 'Outlook web/browser', 'FIX_CALENDAR_LOCAL_CLIENT_SYNC', 1),
    ('S_CALENDAR_COMPARE_USER', 'Q_CALENDAR_WHERE_CORRECT_USER', 'solution', 'Compare Outlook Web and Desktop Sync', None, None, 'Where is the calendar correct?', 'Mobile app only', 'FIX_CALENDAR_COMPARE_WEB_DESKTOP', 2),
    ('S_CALENDAR_SERVICE_USER', 'Q_CALENDAR_WHERE_CORRECT_USER', 'solution', 'Report Mailbox or Calendar Service Issue', None, None, 'Where is the calendar correct?', 'Nowhere', 'FIX_CALENDAR_ESCALATE_SERVICE_ISSUE', 3),
    ('Q_CALENDAR_SCOPE_USER', 'Q_CALENDAR_WHERE_CORRECT_USER', 'question', 'Check Calendar Type', None, 'Is this your main calendar or a shared/delegated calendar?', 'Where is the calendar correct?', 'Not sure', None, 4),
    ('S_CALENDAR_SHARED_USER', 'Q_CALENDAR_SCOPE_USER', 'solution', 'Check Shared Calendar Visibility and Permissions', None, None, 'Is this your main calendar or a shared/delegated calendar?', 'Shared/delegated calendar', 'FIX_CALENDAR_SHARED_VISIBILITY_PERMISSIONS', 1),
    ('S_CALENDAR_ACCOUNT_USER', 'Q_CALENDAR_SCOPE_USER', 'solution', 'Check Account, Calendar Visibility, and App Sync', None, None, 'Is this your main calendar or a shared/delegated calendar?', 'My calendar', 'FIX_CALENDAR_ACCOUNT_VISIBILITY_SYNC', 2),
]

CALENDAR_SYNC_TECH_DIAGNOSTIC_NODES = [
    ('ROOT_CALENDAR_SYNC_TECH', None, 'category', 'Calendar Sync Issue - IT Support Specialist', 'IT Support Specialist diagnostic path for Outlook, mobile, shared-calendar, and mailbox/service calendar sync issues.', None, None, None, None, 1),
    ('Q_CALENDAR_WEB_CORRECT_TECH', 'ROOT_CALENDAR_SYNC_TECH', 'question', 'Check Outlook Web Source of Truth', None, 'Does Outlook on the web show the correct calendar data?', None, None, None, 1),
    ('Q_CALENDAR_ISOLATED_TECH', 'Q_CALENDAR_WEB_CORRECT_TECH', 'question', 'Check Client Scope', None, 'Is the issue isolated to one client/device?', 'Does Outlook on the web show the correct calendar data?', 'Yes', None, 1),
    ('S_CALENDAR_CLIENT_TECH', 'Q_CALENDAR_ISOLATED_TECH', 'solution', 'Troubleshoot Local Client or Mobile Sync', None, None, 'Is the issue isolated to one client/device?', 'Yes', 'FIX_CALENDAR_CLIENT_MOBILE_TROUBLESHOOT', 1),
    ('S_CALENDAR_CONFIG_TECH', 'Q_CALENDAR_ISOLATED_TECH', 'solution', 'Check Account Configuration and Calendar Sync Scope', None, None, 'Is the issue isolated to one client/device?', 'No', 'FIX_CALENDAR_ACCOUNT_CONFIG_SCOPE', 2),
    ('Q_CALENDAR_MULTI_TECH', 'Q_CALENDAR_WEB_CORRECT_TECH', 'question', 'Check Multiple Users', None, 'Are multiple users affected?', 'Does Outlook on the web show the correct calendar data?', 'No', None, 2),
    ('S_CALENDAR_SERVICE_TECH', 'Q_CALENDAR_MULTI_TECH', 'solution', 'Escalate Possible Calendar Service Issue', None, None, 'Are multiple users affected?', 'Yes', 'FIX_CALENDAR_ESCALATE_SERVICE_ISSUE', 1),
    ('Q_CALENDAR_SHARED_TECH', 'Q_CALENDAR_MULTI_TECH', 'question', 'Check Shared Calendar', None, 'Is this a shared/delegated calendar?', 'Are multiple users affected?', 'No', None, 2),
    ('S_CALENDAR_SHARED_TECH', 'Q_CALENDAR_SHARED_TECH', 'solution', 'Verify Shared Calendar Permissions', None, None, 'Is this a shared/delegated calendar?', 'Yes', 'FIX_CALENDAR_VERIFY_SHARED_PERMISSIONS', 1),
    ('S_CALENDAR_MAILBOX_TECH', 'Q_CALENDAR_SHARED_TECH', 'solution', 'Escalate Mailbox Calendar Data Issue', None, None, 'Is this a shared/delegated calendar?', 'No', 'FIX_CALENDAR_ESCALATE_MAILBOX_DATA', 2),
]

def seed_calendar_sync_issue_content(cursor):
    """Seed Calendar Sync Issue KB article, solutions, steps, and diagnostic trees."""
    code_, title, category, severity, description = CALENDAR_SYNC_PROBLEM
    cursor.execute("""
        INSERT INTO problem (problem_code, title, category, severity, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(problem_code) DO UPDATE SET
            title=excluded.title, category=excluded.category, severity=excluded.severity,
            description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, CALENDAR_SYNC_PROBLEM)
    cursor.execute('SELECT problem_id FROM problem WHERE problem_code = ?', (code_,))
    row = cursor.fetchone()
    if not row:
        return
    problem_id = row['problem_id']
    cursor.execute("""
        INSERT INTO kb_article (problem_id, title, summary, difficulty, estimated_time, escalation_required, escalation_notes, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, difficulty=excluded.difficulty,
            estimated_time=excluded.estimated_time, escalation_required=excluded.escalation_required,
            escalation_notes=excluded.escalation_notes, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, CALENDAR_SYNC_KB['title'], CALENDAR_SYNC_KB['summary'], CALENDAR_SYNC_KB['difficulty'], CALENDAR_SYNC_KB['estimated_time'], CALENDAR_SYNC_KB['escalation_required'], CALENDAR_SYNC_KB['escalation_notes']))
    cursor.execute('SELECT kb_article_id FROM kb_article WHERE problem_id = ?', (problem_id,))
    article = cursor.fetchone()
    if article:
        kb_id = article['kb_article_id']
        delete_kb_child_rows(cursor, kb_id)
        insert_kb_child_rows(cursor, 'kb_article_tag', 'tag', kb_id, CALENDAR_SYNC_KB['tags'])
        insert_kb_child_rows(cursor, 'kb_article_symptom', 'symptom', kb_id, CALENDAR_SYNC_KB['symptoms'])
        insert_kb_child_rows(cursor, 'kb_article_cause', 'cause', kb_id, CALENDAR_SYNC_KB['causes'])
        insert_kb_child_rows(cursor, 'kb_article_user_step', 'step_text', kb_id, CALENDAR_SYNC_KB['user_steps'])
        insert_kb_child_rows(cursor, 'kb_article_it_step', 'step_text', kb_id, CALENDAR_SYNC_KB['it_steps'])
    cursor.executemany("""
        INSERT INTO solution (solution_code, title, summary, resolution_steps, escalation_required, escalation_notes, priority_recommendation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(solution_code) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, resolution_steps=excluded.resolution_steps,
            escalation_required=excluded.escalation_required, escalation_notes=excluded.escalation_notes,
            priority_recommendation=excluded.priority_recommendation, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, CALENDAR_SYNC_SOLUTIONS)
    for solution_code, audience_steps in CALENDAR_SYNC_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue
        for audience, steps in audience_steps.items():
            cursor.execute('DELETE FROM solution_step WHERE solution_id = ? AND audience = ?', (solution_id, audience))
            cursor.executemany('INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)', [(solution_id, audience, step, idx) for idx, step in enumerate(steps, start=1)])
    seed_calendar_sync_tree(cursor, 'user', 'CALENDAR_SYNC_ISSUE_USER', 'Calendar Sync Issue - User Diagnostic', 'User-friendly diagnostic tree for calendar sync, visibility, and client differences.', CALENDAR_SYNC_USER_DIAGNOSTIC_NODES)
    seed_calendar_sync_tree(cursor, 'technician', 'CALENDAR_SYNC_ISSUE_TECHNICIAN', 'Calendar Sync Issue - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for Outlook, mobile, shared-calendar, and mailbox/service issues.', CALENDAR_SYNC_TECH_DIAGNOSTIC_NODES)

def seed_calendar_sync_tree(cursor, audience, tree_code, title, description, nodes):
    problem_id = get_problem_id_for_tree_code(cursor, 'CALENDAR_SYNC_ISSUE')
    cursor.execute("""
        INSERT INTO diagnostic_tree (problem_id, diagnostic_tree_code, base_tree_code, audience, title, description, is_active, updated_at)
        VALUES (?, ?, 'CALENDAR_SYNC_ISSUE', ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(diagnostic_tree_code) DO UPDATE SET
            problem_id=excluded.problem_id, base_tree_code=excluded.base_tree_code, audience=excluded.audience,
            title=excluded.title, description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, tree_code, audience, title, description))
    tree_id = get_diagnostic_tree_id_by_code(cursor, tree_code)
    if not tree_id:
        return
    cursor.execute('UPDATE diagnostic_node SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE diagnostic_tree_id = ?', (tree_id,))
    for node_key, parent_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_code, sort_order in nodes:
        parent_id = get_diagnostic_node_id_by_tree_and_key(cursor, tree_id, parent_key) if parent_key else None
        solution_id = get_solution_id_by_code(cursor, solution_code) if solution_code else None
        cursor.execute("""
            INSERT INTO diagnostic_node (
                diagnostic_tree_id, parent_diagnostic_node_id, problem_id, diagnostic_tree_code,
                node_key, node_type, title, description, prompt_text,
                condition_label, condition_value, solution_id, sort_order, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(diagnostic_tree_code, node_key) DO UPDATE SET
                diagnostic_tree_id=excluded.diagnostic_tree_id,
                parent_diagnostic_node_id=excluded.parent_diagnostic_node_id,
                problem_id=excluded.problem_id,
                node_type=excluded.node_type,
                title=excluded.title,
                description=excluded.description,
                prompt_text=excluded.prompt_text,
                condition_label=excluded.condition_label,
                condition_value=excluded.condition_value,
                solution_id=excluded.solution_id,
                sort_order=excluded.sort_order,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (tree_id, parent_id, problem_id, tree_code, node_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_id, sort_order))


# -----------------------------
# SOFTWARE INSTALLATION REQUEST CONTENT
# -----------------------------
SOFTWARE_INSTALLATION_PROBLEM = (
    'SOFTWARE_INSTALLATION_REQUEST',
    'Software Installation Request',
    'Software & Applications',
    'Low to Medium',
    'The user needs approved software installed, updated, or made available on their work device.'
)

SOFTWARE_INSTALLATION_KB = {
    'title': 'Software Installation Request',
    'summary': 'Use this guide when you need approved software installed, the installer is blocked, the software is missing from your device, or installation fails.',
    'difficulty': 'Intermediate',
    'estimated_time': '10-30 minutes, depending on approval/licensing',
    'escalation_required': 1,
    'escalation_notes': 'Escalate when approval, licensing, security review, endpoint deployment, packaging, or vendor support is required.',
    'tags': ['software installation', 'app install', 'software portal', 'admin rights', 'license', 'endpoint management', 'approved software', 'installer error', 'security block', 'least privilege'],
    'symptoms': [
        'User needs software installed or made available on a work device.',
        'User does not have admin rights to install software.',
        'Installer shows access denied, blocked, or security warning.',
        'Software is not available in the company software portal.',
        'Installation fails or asks for a license.',
        'Previous version conflicts with the new installation.',
        'Software portal or endpoint deployment fails.',
    ],
    'causes': [
        'Software installation problems are commonly caused by missing approval, license assignment, lack of admin rights, unapproved installer source, endpoint security blocks, old version conflicts, missing prerequisites, low disk space, pending restart, OS incompatibility, or endpoint management deployment issues.',
        'Advanced causes include corrupted installer metadata, broken uninstall/repair state, package detection-rule problems, missing runtimes, certificate/signature validation failure, proxy/firewall download blocks, vendor installer limitations, and licensing or activation service reachability issues.',
    ],
    'user_steps': [
        'Do not install software from unapproved websites.',
        'Check whether the software is available in the company software portal.',
        'Confirm the software name, vendor, version, and business reason.',
        'Ask your manager or application owner for approval if required.',
        'Check whether you already have a similar approved tool installed.',
        'Take a screenshot of any install error.',
        'Do not try to bypass security warnings or admin restrictions.',
        'Submit a ticket with the software name, vendor, version, purpose, and deadline.',
        'If you downloaded an installer from the internet, do not run it until IT confirms it is safe.',
        'Wait for IT to install or deploy the approved software.',
    ],
    'it_steps': [
        'Tier 1: Confirm the user, device name, operating system, software name, vendor, version, and business need.',
        'Tier 1: Confirm whether the software is already available in the approved software portal.',
        'Tier 1: Check whether the user already has the app installed.',
        'Tier 1: Confirm whether manager, application-owner, security, or licensing approval is required.',
        'Tier 1: Confirm whether a license is available or assigned.',
        'Tier 1: Verify the installer source is approved and trusted.',
        'Tier 1: Do not grant broad local admin rights just to complete the install.',
        'Tier 1: Check install error message or screenshot.',
        'Tier 1: Check basic blockers such as low disk space, pending restart, existing old version, missing prerequisite, or unsupported OS version.',
        'Tier 1: Install or deploy the software through approved company process if authorized.',
        'Tier 1: Verify the application launches successfully after installation.',
        'Tier 1: Document software name, version, approval, install source, and result.',
        'Tier 2 / Endpoint Support: Review installation logs if available.',
        'Tier 2 / Endpoint Support: Check whether the installer is MSI, EXE, Store app, or company-packaged app.',
        'Tier 2 / Endpoint Support: Check whether previous installation remnants or registry data block install/uninstall.',
        'Tier 2 / Endpoint Support: Use approved Microsoft install/uninstall troubleshooting tools when appropriate for blocked installs/removals.',
        'Tier 2 / Endpoint Support: Check endpoint management deployment status if the app is deployed through Intune, SCCM, MDM, or RMM.',
        'Tier 2 / Endpoint Support: Check detection rules, assignment group, device compliance, and deployment error where available.',
        'Tier 2 / Endpoint Support: Check endpoint security alerts/quarantine if installer is blocked.',
        'Tier 2 / Endpoint Support: Check prerequisites, dependencies, licensing, activation path, and vendor requirements.',
        'Tier 2 / Network Support: Check network, proxy, DNS, or firewall path if installer download or activation service cannot be reached.',
        'Determine whether the issue is approval/licensing, missing package, local install failure, endpoint management deployment failure, security block, compatibility issue, or vendor/application issue.',
        'Escalate with installer name/version, source, error code, logs, approval status, device details, and business impact.',
    ],
}

SOFTWARE_INSTALLATION_SOLUTIONS = [
    ('FIX_SOFTWARE_INSTALL_APPROVED_PORTAL', 'Install from Approved Software Portal', 'The software is already approved and available through the company software portal.', 'Install from the approved company portal and verify launch.', 0, 'Escalate only if portal access, deployment group, or install status fails.', 'low'),
    ('FIX_SOFTWARE_INSTALL_REQUEST_APPROVAL', 'Request Approval for Software Installation', 'The software needs business, manager, licensing, or application-owner approval before installation.', 'Collect business reason and route approval before installation.', 1, 'Escalate to manager, application owner, licensing, or procurement as required.', 'medium'),
    ('FIX_SOFTWARE_INSTALL_SECURITY_BLOCK', 'Do Not Bypass Security Block', 'Security controls blocked the installer or warned that the app may be unsafe.', 'Do not bypass security; collect details and route for review.', 1, 'Escalate to Security if source is unknown, suspicious, high-risk, or blocked by endpoint protection.', 'high'),
    ('FIX_SOFTWARE_INSTALL_SUBMIT_ERROR_DETAILS', 'Submit Installer Error Details', 'The installation failed and IT needs the exact error, version, and device details.', 'Capture error details and continue with targeted install troubleshooting.', 0, 'Escalate if error indicates packaging, security, corruption, or vendor issue.', 'medium'),
    ('FIX_SOFTWARE_INSTALL_SUBMIT_TICKET', 'Submit Software Installation Ticket', 'IT needs to review the request and install or deploy the software through approved process.', 'Submit complete installation request with software, business need, approval, and device details.', 0, 'Escalate if approval, licensing, or deployment ownership is unclear.', 'medium'),
    ('FIX_SOFTWARE_INSTALL_APPROVAL_SECURITY_REVIEW', 'Escalate Software Approval or Security Review', 'Software is not clearly approved, trusted, licensed, or safe.', 'Route unapproved or unclear software request through approval/security process.', 1, 'Escalate to Security, application owner, procurement, or manager before installation.', 'high'),
    ('FIX_SOFTWARE_INSTALL_LICENSE_APPROVAL', 'Verify Approval and License Assignment', 'Installation cannot proceed until approval and licensing are confirmed.', 'Confirm approval and license assignment before installation.', 1, 'Escalate if license availability or application-owner approval is required.', 'medium'),
    ('FIX_SOFTWARE_INSTALL_DEPLOY_PORTAL', 'Deploy from Approved Software Portal', 'IT deploys or makes available the software through company endpoint management/software portal.', 'Assign, deploy, monitor, and verify app install through approved endpoint process.', 0, 'Escalate to Endpoint Management if deployment or assignment fails.', 'medium'),
    ('FIX_SOFTWARE_INSTALL_LOCAL_FAILURE', 'Troubleshoot Local Installation Failure', 'Approved software fails to install locally because of prerequisites, old version, disk space, pending restart, or installer issue.', 'Review logs and local blockers, then repair or escalate.', 1, 'Escalate if corruption, packaging, endpoint management, or vendor issue is suspected.', 'high'),
    ('FIX_SOFTWARE_INSTALL_PACKAGE_DEPLOYMENT', 'Package or Escalate Software Deployment Request', 'Software is approved but not yet packaged or available for managed deployment.', 'Collect deployment details and route to packaging/endpoint management.', 1, 'Escalate to Endpoint Management/Application Packaging team.', 'medium'),
]

SOFTWARE_INSTALLATION_SOLUTION_STEPS = {
    'FIX_SOFTWARE_INSTALL_APPROVED_PORTAL': {
        'user': ['Open the company software portal.', 'Search for the software name.', 'Select the approved version.', 'Start the installation.', 'Restart the computer if prompted.'],
        'technician': ['Confirm the software is available to the user/device.', 'Confirm the user is in the correct deployment group if needed.', 'Guide the user through installation.', 'Verify the app launches after install.', 'Document the installed version.'],
        'admin': ['Escalate only if software portal availability, assignment group, or device check-in is not working.'],
    },
    'FIX_SOFTWARE_INSTALL_REQUEST_APPROVAL': {
        'user': ['Provide the software name and vendor.', 'Explain the business reason.', 'Include project/team need and deadline.', 'Wait for approval before installation.'],
        'technician': ['Confirm whether approval is required.', 'Route request to manager, application owner, licensing, or procurement.', 'Confirm whether an approved alternative already exists.', 'Do not install until approval is documented.', 'Update the ticket with approval status.'],
        'admin': ['Escalate to application owner, manager, procurement, or licensing owner when approval or funding is required.'],
    },
    'FIX_SOFTWARE_INSTALL_SECURITY_BLOCK': {
        'user': ['Do not bypass the warning.', 'Do not run the installer again.', 'Send IT the software name, source link, and screenshot.', 'Wait for IT/Security review.'],
        'technician': ['Verify installer source and digital trust where appropriate.', 'Check endpoint security alert or block reason.', 'Do not whitelist or allow the installer without approval.', 'Escalate to Security if the source is unknown, suspicious, or high-risk.', 'Recommend approved alternative if available.'],
        'admin': ['Escalate to Security with installer source, hash/signature if available, vendor, business need, screenshot, and endpoint block details.'],
    },
    'FIX_SOFTWARE_INSTALL_SUBMIT_ERROR_DETAILS': {
        'user': ['Take a screenshot of the error.', 'Note the software name and version.', 'Tell IT where the installer came from.', 'Submit a ticket with the screenshot.'],
        'technician': ['Record error message/code and install source.', 'Check disk space, pending restart, OS version, and existing installed version.', 'Check whether prerequisites are missing.', 'Review installer logs if available.', 'Continue with local installation troubleshooting.'],
        'admin': ['Escalate if logs suggest package corruption, endpoint management failure, missing dependencies, or vendor-specific installer error.'],
    },
    'FIX_SOFTWARE_INSTALL_SUBMIT_TICKET': {
        'user': ['Provide software name, vendor, version, and business reason.', 'Include any approval or license information.', 'Include your device name and deadline.', 'Wait for IT confirmation.'],
        'technician': ['Confirm request completeness.', 'Check approval/licensing/source.', 'Determine whether install is manual, portal-based, or managed deployment.', 'Schedule install if needed.', 'Document result after installation.'],
        'admin': ['Escalate request ownership if software approval, licensing, or deployment method is unclear.'],
    },
    'FIX_SOFTWARE_INSTALL_APPROVAL_SECURITY_REVIEW': {
        'user': ['Do not install the software.', 'Provide the business reason and vendor/source link.', 'Wait for IT/Security or manager approval.'],
        'technician': ['Confirm business need and approved alternatives.', 'Check vendor reputation/source and software category.', 'Route to Security, App Owner, Procurement, or Manager as required.', 'Document approval decision.', 'Proceed only after approval.'],
        'admin': ['Escalate with business need, vendor/source, risk notes, licensing/cost impact, and requested user/device scope.'],
    },
    'FIX_SOFTWARE_INSTALL_LICENSE_APPROVAL': {
        'user': ['Provide approval details if already granted.', 'Confirm whether this is new access or replacement software.', 'Wait for license assignment if needed.'],
        'technician': ['Confirm manager/application-owner approval.', 'Check license availability.', 'Assign license or route request if authorized.', 'Confirm user/device is eligible.', 'Document license and approval status.'],
        'admin': ['Escalate to licensing, procurement, or app owner when license availability, entitlement, or approval is unresolved.'],
    },
    'FIX_SOFTWARE_INSTALL_DEPLOY_PORTAL': {
        'user': ['Keep the device online.', 'Connect to VPN if required by company policy.', 'Restart when prompted.', 'Tell IT if installation does not appear.'],
        'technician': ['Assign app to user/device group.', 'Check endpoint management deployment status.', 'Confirm device is online and checking in.', 'Review deployment error if install fails.', 'Verify successful installation and launch.'],
        'admin': ['Escalate to Endpoint Management with app assignment, device/user group, management status, deployment error, and check-in time.'],
    },
    'FIX_SOFTWARE_INSTALL_LOCAL_FAILURE': {
        'user': ['Restart the computer if IT asks.', 'Keep the installer error visible or screenshot it.', 'Do not repeatedly run the installer.'],
        'technician': ['Check install logs and error code.', 'Check pending restart and disk space.', 'Check existing installed version and uninstall/repair state.', 'Check prerequisites/dependencies.', 'Use approved install/uninstall repair tools when appropriate.', 'Escalate if corruption, packaging, or vendor issue is suspected.'],
        'admin': ['Escalate with install log, error code, package type, source, current version, prerequisites checked, and remediation attempted.'],
    },
    'FIX_SOFTWARE_INSTALL_PACKAGE_DEPLOYMENT': {
        'user': ['Provide business need and deadline.', 'Wait for IT to confirm deployment timeline.', 'Use approved alternative if offered.'],
        'technician': ['Confirm software is approved and licensed.', 'Collect installer, silent install options, license details, and vendor documentation.', 'Escalate to Endpoint Management/Application Packaging team.', 'Provide user/device group, urgency, and business impact.', 'Document deployment request status.'],
        'admin': ['Escalate to packaging team with installer, vendor documentation, silent switches if known, licensing details, assignment scope, and business deadline.'],
    },
}

SOFTWARE_INSTALLATION_USER_DIAGNOSTIC_NODES = [
    ('ROOT_SOFTWARE_INSTALL_USER', None, 'category', 'Software Installation Request', 'User-friendly diagnostic path for approved software installation requests.', None, None, None, None, 1),
    ('Q_SOFTWARE_PORTAL_USER', 'ROOT_SOFTWARE_INSTALL_USER', 'question', 'Check Software Portal', None, 'Is the software available in the company software portal?', None, None, None, 1),
    ('S_SOFTWARE_PORTAL_USER', 'Q_SOFTWARE_PORTAL_USER', 'solution', 'Install from Approved Software Portal', None, None, 'Yes', 'Yes', 'FIX_SOFTWARE_INSTALL_APPROVED_PORTAL', 1),
    ('Q_SOFTWARE_APPROVAL_USER', 'Q_SOFTWARE_PORTAL_USER', 'question', 'Check Approval or Business Reason', None, 'Do you have approval or a business reason?', 'No / Not sure', 'No / Not sure', None, 2),
    ('S_SOFTWARE_APPROVAL_USER', 'Q_SOFTWARE_APPROVAL_USER', 'solution', 'Request Approval for Software Installation', None, None, 'No / Not sure', 'No / Not sure', 'FIX_SOFTWARE_INSTALL_REQUEST_APPROVAL', 1),
    ('Q_SOFTWARE_ERROR_USER', 'Q_SOFTWARE_APPROVAL_USER', 'question', 'Check Installation or Security Error', None, 'Do you see an installation or security error?', 'Yes', 'Yes', None, 2),
    ('S_SOFTWARE_SECURITY_USER', 'Q_SOFTWARE_ERROR_USER', 'solution', 'Do Not Bypass Security Block', None, None, 'Security blocked / warning', 'Security blocked / warning', 'FIX_SOFTWARE_INSTALL_SECURITY_BLOCK', 1),
    ('S_SOFTWARE_INSTALL_FAILED_USER', 'Q_SOFTWARE_ERROR_USER', 'solution', 'Submit Installer Error Details', None, None, 'Install failed', 'Install failed', 'FIX_SOFTWARE_INSTALL_SUBMIT_ERROR_DETAILS', 2),
    ('S_SOFTWARE_TICKET_USER', 'Q_SOFTWARE_ERROR_USER', 'solution', 'Submit Software Installation Ticket', None, None, 'No error', 'No error', 'FIX_SOFTWARE_INSTALL_SUBMIT_TICKET', 3),
]

SOFTWARE_INSTALLATION_TECH_DIAGNOSTIC_NODES = [
    ('ROOT_SOFTWARE_INSTALL_TECH', None, 'category', 'Software Installation Request - IT Support Specialist', 'IT Support Specialist diagnostic path for approval, licensing, endpoint deployment, and installation failures.', None, None, None, None, 1),
    ('Q_SOFTWARE_APPROVED_TECH', 'ROOT_SOFTWARE_INSTALL_TECH', 'question', 'Validate Approved Source', None, 'Is the software approved and from a trusted source?', None, None, None, 1),
    ('S_SOFTWARE_SECURITY_REVIEW_TECH', 'Q_SOFTWARE_APPROVED_TECH', 'solution', 'Escalate Software Approval or Security Review', None, None, 'No / Not sure', 'No / Not sure', 'FIX_SOFTWARE_INSTALL_APPROVAL_SECURITY_REVIEW', 1),
    ('Q_SOFTWARE_LICENSE_TECH', 'Q_SOFTWARE_APPROVED_TECH', 'question', 'Check Approval and Licensing', None, 'Is licensing or application-owner approval required?', 'Yes', 'Yes', None, 2),
    ('S_SOFTWARE_LICENSE_TECH', 'Q_SOFTWARE_LICENSE_TECH', 'solution', 'Verify Approval and License Assignment', None, None, 'Yes', 'Yes', 'FIX_SOFTWARE_INSTALL_LICENSE_APPROVAL', 1),
    ('Q_SOFTWARE_PORTAL_TECH', 'Q_SOFTWARE_LICENSE_TECH', 'question', 'Check Software Portal or Endpoint Management', None, 'Is the app available through software portal or endpoint management?', 'No', 'No', None, 2),
    ('S_SOFTWARE_DEPLOY_TECH', 'Q_SOFTWARE_PORTAL_TECH', 'solution', 'Deploy from Approved Software Portal', None, None, 'Yes', 'Yes', 'FIX_SOFTWARE_INSTALL_DEPLOY_PORTAL', 1),
    ('Q_SOFTWARE_LOCAL_FAIL_TECH', 'Q_SOFTWARE_PORTAL_TECH', 'question', 'Check Local Install Error', None, 'Is local install failing with an error?', 'No', 'No', None, 2),
    ('S_SOFTWARE_LOCAL_FAIL_TECH', 'Q_SOFTWARE_LOCAL_FAIL_TECH', 'solution', 'Troubleshoot Local Installation Failure', None, None, 'Yes', 'Yes', 'FIX_SOFTWARE_INSTALL_LOCAL_FAILURE', 1),
    ('S_SOFTWARE_PACKAGE_TECH', 'Q_SOFTWARE_LOCAL_FAIL_TECH', 'solution', 'Package or Escalate Software Deployment Request', None, None, 'No', 'No', 'FIX_SOFTWARE_INSTALL_PACKAGE_DEPLOYMENT', 2),
]

def seed_software_installation_request_content(cursor):
    code_, title, category, severity, description = SOFTWARE_INSTALLATION_PROBLEM
    cursor.execute("""
        INSERT INTO problem (problem_code, title, category, severity, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(problem_code) DO UPDATE SET
            title=excluded.title, category=excluded.category, severity=excluded.severity,
            description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, SOFTWARE_INSTALLATION_PROBLEM)
    cursor.execute('SELECT problem_id FROM problem WHERE problem_code = ?', (code_,))
    row = cursor.fetchone()
    if not row:
        return
    problem_id = row['problem_id']
    cursor.execute("""
        INSERT INTO kb_article (problem_id, title, summary, difficulty, estimated_time, escalation_required, escalation_notes, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, difficulty=excluded.difficulty,
            estimated_time=excluded.estimated_time, escalation_required=excluded.escalation_required,
            escalation_notes=excluded.escalation_notes, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, SOFTWARE_INSTALLATION_KB['title'], SOFTWARE_INSTALLATION_KB['summary'], SOFTWARE_INSTALLATION_KB['difficulty'], SOFTWARE_INSTALLATION_KB['estimated_time'], SOFTWARE_INSTALLATION_KB['escalation_required'], SOFTWARE_INSTALLATION_KB['escalation_notes']))
    cursor.execute('SELECT kb_article_id FROM kb_article WHERE problem_id = ?', (problem_id,))
    article = cursor.fetchone()
    if article:
        kb_id = article['kb_article_id']
        delete_kb_child_rows(cursor, kb_id)
        insert_kb_child_rows(cursor, 'kb_article_tag', 'tag', kb_id, SOFTWARE_INSTALLATION_KB['tags'])
        insert_kb_child_rows(cursor, 'kb_article_symptom', 'symptom', kb_id, SOFTWARE_INSTALLATION_KB['symptoms'])
        insert_kb_child_rows(cursor, 'kb_article_cause', 'cause', kb_id, SOFTWARE_INSTALLATION_KB['causes'])
        insert_kb_child_rows(cursor, 'kb_article_user_step', 'step_text', kb_id, SOFTWARE_INSTALLATION_KB['user_steps'])
        insert_kb_child_rows(cursor, 'kb_article_it_step', 'step_text', kb_id, SOFTWARE_INSTALLATION_KB['it_steps'])
    cursor.executemany("""
        INSERT INTO solution (solution_code, title, summary, resolution_steps, escalation_required, escalation_notes, priority_recommendation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(solution_code) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, resolution_steps=excluded.resolution_steps,
            escalation_required=excluded.escalation_required, escalation_notes=excluded.escalation_notes,
            priority_recommendation=excluded.priority_recommendation, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, SOFTWARE_INSTALLATION_SOLUTIONS)
    for solution_code, audience_steps in SOFTWARE_INSTALLATION_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue
        for audience, steps in audience_steps.items():
            cursor.execute('DELETE FROM solution_step WHERE solution_id = ? AND audience = ?', (solution_id, audience))
            cursor.executemany('INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)', [(solution_id, audience, step, idx) for idx, step in enumerate(steps, start=1)])
    seed_software_installation_tree(cursor, 'user', 'SOFTWARE_INSTALLATION_REQUEST_USER', 'Software Installation Request - User Diagnostic', 'User-friendly diagnostic tree for software installation requests, approval, and installer errors.', SOFTWARE_INSTALLATION_USER_DIAGNOSTIC_NODES)
    seed_software_installation_tree(cursor, 'technician', 'SOFTWARE_INSTALLATION_REQUEST_TECHNICIAN', 'Software Installation Request - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for approval, licensing, deployment, and installation failure handling.', SOFTWARE_INSTALLATION_TECH_DIAGNOSTIC_NODES)

def seed_software_installation_tree(cursor, audience, tree_code, title, description, nodes):
    problem_id = get_problem_id_for_tree_code(cursor, 'SOFTWARE_INSTALLATION_REQUEST')
    cursor.execute("""
        INSERT INTO diagnostic_tree (problem_id, diagnostic_tree_code, base_tree_code, audience, title, description, is_active, updated_at)
        VALUES (?, ?, 'SOFTWARE_INSTALLATION_REQUEST', ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(diagnostic_tree_code) DO UPDATE SET
            problem_id=excluded.problem_id, base_tree_code=excluded.base_tree_code, audience=excluded.audience,
            title=excluded.title, description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, tree_code, audience, title, description))
    tree_id = get_diagnostic_tree_id_by_code(cursor, tree_code)
    if not tree_id:
        return
    cursor.execute('UPDATE diagnostic_node SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE diagnostic_tree_id = ?', (tree_id,))
    for node_key, parent_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_code, sort_order in nodes:
        parent_id = get_diagnostic_node_id_by_tree_and_key(cursor, tree_id, parent_key) if parent_key else None
        solution_id = get_solution_id_by_code(cursor, solution_code) if solution_code else None
        cursor.execute("""
            INSERT INTO diagnostic_node (
                diagnostic_tree_id, parent_diagnostic_node_id, problem_id, diagnostic_tree_code,
                node_key, node_type, title, description, prompt_text,
                condition_label, condition_value, solution_id, sort_order, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(diagnostic_tree_code, node_key) DO UPDATE SET
                diagnostic_tree_id=excluded.diagnostic_tree_id,
                parent_diagnostic_node_id=excluded.parent_diagnostic_node_id,
                problem_id=excluded.problem_id,
                node_type=excluded.node_type,
                title=excluded.title,
                description=excluded.description,
                prompt_text=excluded.prompt_text,
                condition_label=excluded.condition_label,
                condition_value=excluded.condition_value,
                solution_id=excluded.solution_id,
                sort_order=excluded.sort_order,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (tree_id, parent_id, problem_id, tree_code, node_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_id, sort_order))

# -----------------------------
# EXISTING ISSUE ROLE ALIGNMENT PATCH
# -----------------------------
# This patch keeps the current two working audiences clear:
# - regular users see safe self-service steps
# - support-side users see IT Support Specialist steps suitable for Tier 1 / junior Tier 2 work
# The stored audience value "admin" is retained only for escalation notes / Tier 2-3 handoff.
EXISTING_ISSUE_ALIGNMENT_KB_IT_STEPS = {
    'PRINTER_FAILURE': [
        'Tier 1: Confirm printer name, model, location, connection type, affected user/device, and exact error message.',
        'Tier 1: Determine whether the issue affects one user, one workstation, one printer, or multiple users.',
        'Tier 1: Check printer power, display panel, paper/toner/tray/door warnings, and visible hardware errors.',
        'Tier 1: Confirm the user selected the correct printer and test printing from a simple application.',
        'Tier 1: Check the local print queue and clear stuck jobs when appropriate.',
        'Tier 1: Restart the printer and, when appropriate, restart the Print Spooler service.',
        'Tier 1: For USB printers, test cable, USB port, detection in Windows, and a known-good cable if available.',
        'Tier 2 / Network Support: For network printers, verify printer IP address, subnet mask, gateway, and network status page.',
        'Tier 2 / Network Support: Ping or otherwise test approved reachability from the user device and/or print server.',
        'Tier 2 / Network Support: Compare configured printer port/IP with the printer current IP address.',
        'Tier 2 / Network Support: Check whether printer hostname/DNS resolves to the expected IP if hostname-based printing is used.',
        'Tier 2 / Network Support: Check for DHCP reservation, static IP conflict, VLAN/subnet mismatch, or wireless signal issues when evidence points there.',
        'Tier 2 / Network Support: Check print server queue, printer port, driver, spooler, and Group Policy deployment for shared printers.',
        'Document root cause, test page result, affected scope, printer IP/name/location, and escalation evidence.',
    ],
    'PASSWORD_RESET_REQUEST': [
        'Tier 1: Verify the user identity according to support policy before discussing or changing account credentials.',
        'Tier 1: Confirm the exact username/email address and the system the user is trying to access.',
        'Tier 1: Confirm whether the user forgot the password, the password expired, or self-service reset failed.',
        'Tier 1: Check basic causes such as wrong username, Caps Lock, keyboard layout, saved browser password, or stale session.',
        'Tier 1: Guide the user to the approved password reset portal when self-service reset is allowed.',
        'Tier 1: Check whether recovery email, recovery phone, or MFA prompt is available to complete reset.',
        'Tier 1: Confirm account state when available: active/disabled, locked/unlocked, password expired, and must-change-password flag.',
        'Tier 1: After reset, ask the user to update saved passwords on mobile email, VPN, browser password manager, mapped drives, and remote desktop.',
        'Tier 2 / Identity Support: Review sign-in or identity logs when reset succeeds but sign-in still fails.',
        'Tier 2 / Identity Support: Identify whether failure affects one application, SSO, VPN, email, or all services.',
        'Escalate to Identity/Access Management if sync, writeback, conditional access, disabled account, group/license, or MFA recovery issues are suspected.',
        'Escalate to Security if reset request, failed attempts, or MFA prompts suggest possible compromise.',
    ],
    'ACCOUNT_LOCKED': [
        'Tier 1: Verify the user identity before unlocking or changing account settings.',
        'Tier 1: Confirm the exact lockout/error message and affected system: Windows, email, VPN, SSO, app, or remote desktop.',
        'Tier 1: Check whether the account is actually locked or whether the issue is password, MFA, disabled account, or access denied.',
        'Tier 1: Ask whether the user recently changed or reset the password.',
        'Tier 1: Ask about old saved credentials on mobile email, VPN client, browser password manager, mapped drives, remote desktop, Wi-Fi, and old devices.',
        'Tier 1: Stop repeated retries and unlock only after verification and basic review.',
        'Tier 2 / Support: Review failed sign-in source when available: timestamp, device, app/client, IP/location, and failure reason.',
        'Tier 2 / Support: Correlate recurring lockout timestamps with user devices, VPN, email apps, RDP, mapped drives, scheduled tasks, or cached Windows credentials.',
        'Tier 2 / Support: Clear or update cached credentials when the source is a known user device/app.',
        'Tier 2 / Support: Determine whether lockout is caused by stale credentials, unknown source, password spray, brute force, or policy behavior.',
        'Escalate to Security for suspicious locations, impossible travel, unexpected MFA prompts, many affected accounts, or password-spray indicators.',
        'Escalate to Identity/Access Management when recurring lockout source cannot be identified or policy/log review is required.',
    ],
    'MULTI_FACTOR_AUTHENTICATION_ISSUE': [
        'Tier 1: Verify user identity before changing MFA methods or recovery information.',
        'Tier 1: Confirm the affected sign-in target: email, VPN, SSO portal, password reset portal, or business application.',
        'Tier 1: Confirm whether the user receives a push prompt, SMS, phone call, code, or no prompt at all.',
        'Tier 1: Check phone signal, internet connectivity, app notification permissions, and whether the authenticator app is opened manually.',
        'Tier 1: Ask whether the user changed phones, changed phone numbers, lost the device, or reinstalled the authenticator app.',
        'Tier 1: For code failures, confirm correct account selection and automatic date/time on the phone.',
        'Tier 2 / Identity Support: Review MFA logs for sent prompts, timeouts, denials, method used, location, IP, and device when available.',
        'Tier 2 / Identity Support: Guide re-registration only after identity verification and according to policy.',
        'Tier 2 / Identity Support: Check conditional access or device compliance result if sign-in is blocked despite valid MFA.',
        'Escalate to Security for unexpected MFA prompts, repeated denied prompts, unfamiliar location/device, MFA fatigue indicators, or suspected compromise.',
        'Escalate to Identity/Access Management or Endpoint when MFA policy, conditional access, device compliance, or enrollment blocks sign-in.',
    ],
}

EXISTING_ISSUE_ALIGNMENT_SOLUTION_STEPS = {
    # Printer Failure
    'FIX_PRINTER_NETWORK_CONNECTION': {
        'technician': [
            'Tier 1: Confirm printer name, location, model, connection type, and whether one or multiple users are affected.',
            'Tier 1: Print or view the printer network configuration page if available.',
            'Tier 2 / Network Support: Verify printer IP address, subnet mask, default gateway, and network status.',
            'Tier 2 / Network Support: Ping or otherwise test approved reachability from the affected client and, if relevant, the print server.',
            'Tier 2 / Network Support: Compare the printer current IP with the configured printer port/IP on the workstation or print server.',
            'Tier 2 / Network Support: Check for DHCP reservation/static IP conflict, VLAN/subnet mismatch, or Wi-Fi/Ethernet link issue if reachability fails.',
        ],
        'admin': [
            'Escalation notes: send printer name, location, current IP, configured port/IP, ping/reachability result, affected scope, and screenshots to Network or Endpoint/Server team.',
        ],
    },
    'FIX_PRINTER_OFFLINE_REACHABLE': {
        'technician': [
            'Tier 1: Confirm the printer is reachable but marked Offline locally or on the print server.',
            'Tier 1: Disable Use Printer Offline if enabled and clear stuck local jobs.',
            'Tier 1: Restart the Print Spooler service when appropriate.',
            'Tier 2 / Support: Validate printer port/IP and confirm the port still matches the printer current network address.',
            'Tier 2 / Support: Remove and re-add the printer or refresh the print server connection if offline state persists.',
        ],
        'admin': [
            'Escalation notes: investigate print server, stale printer port, DNS/IP change, driver, or recurring offline state if the issue repeats or affects multiple users.',
        ],
    },
    'FIX_PRINTER_UNREACHABLE': {
        'technician': [
            'Tier 1: Confirm printer power, panel network status, cable/Wi-Fi status, and whether nearby users can print.',
            'Tier 2 / Network Support: Ping or otherwise test approved reachability to the printer IP from the client and print server.',
            'Tier 2 / Network Support: Compare the configured printer port/IP with the current printer IP.',
            'Tier 2 / Network Support: Check signs of IP conflict, missing DHCP lease/reservation, wrong VLAN/subnet, switch port issue, or weak Wi-Fi signal.',
            'Document printer name, IP, MAC if available, location, affected users, and test results.',
        ],
        'admin': [
            'Escalation notes: escalate to Network Team when multiple devices cannot reach the printer, an IP conflict/VLAN/DHCP/ACL issue is suspected, or switch/Wi-Fi troubleshooting is required.',
        ],
    },
    'FIX_PRINT_SERVER_OR_PERMISSION': {
        'technician': [
            'Tier 1: Check whether other users can print to the same shared printer.',
            'Tier 1: Confirm whether the user sees access denied, printer missing, or jobs stuck on the shared queue.',
            'Tier 2 / Support: Verify printer permissions, AD/security group membership, and print server queue status if accessible.',
            'Tier 2 / Support: Check print server printer port, driver, spooler status, and Group Policy printer deployment evidence.',
            'Document affected users, queue state, printer name, server/share path, group membership, and deployment method.',
        ],
        'admin': [
            'Escalation notes: escalate to Server/Endpoint for print server, driver, spooler, or GPO deployment issues; escalate to Access Management for permission/security group issues.',
        ],
    },
    # Password Reset Request
    'FIX_USE_PASSWORD_RESET_PORTAL': {
        'technician': [
            'Tier 1: Verify the user is using the approved password reset portal and correct username/email.',
            'Tier 1: Confirm the user can access the registered recovery email, phone, or MFA method.',
            'Tier 1: Have the user retry in private/incognito mode to avoid stale browser sessions.',
            'Tier 2 / Identity Support: Check sign-in or reset logs when the portal fails or reset completes but sign-in still fails.',
            'Document portal used, error message, recovery method status, and timestamp.',
        ],
        'admin': [
            'Escalation notes: escalate to Identity/Access Management if self-service reset is unavailable, recovery methods are outdated, or reset/writeback/policy errors are suspected.',
        ],
    },
    'FIX_RESET_EXPIRED_PASSWORD': {
        'technician': [
            'Tier 1: Confirm password expiration or must-change-password state.',
            'Tier 1: Guide the user through the normal expired-password change flow when available.',
            'Tier 1: Confirm successful sign-in after password change.',
            'Tier 1: Ask the user to update saved passwords on mobile email, VPN, browser password manager, mapped drives, and remote desktop.',
            'Tier 2 / Support: If lockouts continue, look for stale credentials repeatedly trying the old password.',
        ],
        'admin': [
            'Escalation notes: escalate if password policy, sync, or application-specific authentication prevents completion after normal reset.',
        ],
    },
    'FIX_ADMIN_PASSWORD_RESET': {
        'technician': [
            'Tier 1: Verify identity according to support policy before resetting the password.',
            'Tier 1: Reset the password only through the approved admin console or process.',
            'Tier 1: Require password change at next sign-in when policy allows.',
            'Tier 1: Avoid sending temporary passwords through insecure channels.',
            'Tier 1: Confirm the user can sign in and update saved credentials after reset.',
            'Document identity verification, reset time, affected system, and successful sign-in test.',
        ],
        'admin': [
            'Escalation notes: escalate exceptions, high-risk resets, disabled accounts, or suspected compromise to Identity/Access Management or Security.',
        ],
    },
    'FIX_ESCALATE_IDENTITY_SYNC_POLICY': {
        'technician': [
            'Tier 2 / Identity Support: Confirm password reset succeeded in the identity provider.',
            'Tier 2 / Identity Support: Determine whether sign-in fails for one app, SSO, VPN, email, or all services.',
            'Tier 2 / Identity Support: Collect timestamps, error messages, sign-in result, user account state, and affected application.',
            'Tier 2 / Identity Support: Check visible evidence for group/license, conditional access, password writeback, or sync-related failure when available.',
            'Prepare escalation notes with all evidence gathered.',
        ],
        'admin': [
            'Escalation notes: route to Identity/Access Management for sync, writeback, conditional access, licensing/group membership, or app identity integration issues.',
        ],
    },
    # Account Locked
    'FIX_UPDATE_SAVED_PASSWORDS_AFTER_CHANGE': {
        'technician': [
            'Tier 1: Ask which devices and apps store company credentials: phone, tablet, email, VPN, browser, mapped drives, RDP, and old laptops.',
            'Tier 1: Help the user update or remove old saved passwords from common locations such as browser password manager, VPN client, email profile, or Credential Manager.',
            'Tier 2 / Support: Review failed sign-in source hints if available to identify the app/client/device causing lockout.',
            'Unlock the account only after the likely stale credential source is corrected.',
            'Document the source found, credentials cleaned, and whether lockout recurred.',
        ],
        'admin': [
            'Escalation notes: escalate recurring lockouts if stale credential source is not obvious or logs require Identity team review.',
        ],
    },
    'FIX_FIND_OLD_CREDENTIAL_SOURCE': {
        'technician': [
            'Tier 1: Ask the user to identify all devices and apps that may still use the old password.',
            'Tier 2 / Support: Compare lockout timestamps with device activity and failed sign-in logs where available.',
            'Tier 2 / Support: Check mobile email, VPN, mapped drives, RDP, scheduled tasks, cached Windows credentials, and old devices.',
            'Tier 2 / Support: Clear or update saved credentials from the suspected source and monitor for recurrence.',
            'Document source workstation/app/IP/client if identified.',
        ],
        'admin': [
            'Escalation notes: escalate to Identity/Access Management if the lockout source cannot be identified with frontline tools.',
        ],
    },
    'FIX_UNLOCK_ACCOUNT_MONITOR': {
        'technician': [
            'Tier 1: Verify user identity before unlock.',
            'Tier 1: Confirm failed attempts appear legitimate and not obviously suspicious.',
            'Tier 1: Unlock the account and ask the user to sign in once using the correct current password.',
            'Tier 1: Ask the user to stop repeated retries and report if the account locks again.',
            'Tier 2 / Support: If lockout recurs, move to stale credential source investigation.',
        ],
        'admin': [
            'Escalation notes: escalate if lockout recurs quickly, source is unknown, or sign-in logs suggest attack/compromise.',
        ],
    },
    'FIX_ESCALATE_POSSIBLE_ACCOUNT_ATTACK': {
        'technician': [
            'Tier 1: Instruct the user not to approve unexpected MFA prompts and to stop repeated sign-in attempts.',
            'Tier 2 / Security Support: Capture failed sign-in timestamps, source IPs/locations, user agent/client, MFA events, and whether other accounts are affected.',
            'Tier 2 / Security Support: Do not repeatedly unlock until suspicious activity is reviewed.',
            'Escalate to Security with evidence and follow incident response guidance.',
        ],
        'admin': [
            'Escalation notes: treat as High priority for unfamiliar location, password spray indicators, repeated prompts, or suspected compromise.',
        ],
    },
    'FIX_INVESTIGATE_RECURRING_LOCKOUT_SOURCE': {
        'technician': [
            'Tier 1: Ask when the account locks again and what device/app the user was using.',
            'Tier 2 / Support: Compare lockout timestamps to user device, VPN, email, RDP, mapped drive, and application activity.',
            'Tier 2 / Support: Review domain controller, identity provider, VPN, email, and application logs if available to frontline support.',
            'Tier 2 / Support: Remove or update stored credentials from the suspected source.',
            'Escalate if the source remains unknown after common credential locations are checked.',
        ],
        'admin': [
            'Escalation notes: route unresolved recurring lockouts to Identity/Access Management; route suspicious patterns to Security.',
        ],
    },
    # MFA
    'FIX_REGISTER_MFA_METHOD': {
        'technician': [
            'Tier 1: Verify the user identity before guiding MFA enrollment.',
            'Tier 1: Confirm the user is eligible and required to use MFA.',
            'Tier 1: Guide the user through the official company MFA registration page.',
            'Tier 1: Confirm at least one primary and one backup method if policy allows.',
            'Tier 1: Complete a test sign-in and document completion in the ticket.',
        ],
        'admin': [
            'Escalation notes: escalate if enrollment policy, conditional access, missing license/group, or registration page access blocks enrollment.',
        ],
    },
    'FIX_MFA_RESET_REREGISTRATION': {
        'technician': [
            'Tier 1: Verify identity according to support policy before resetting MFA methods.',
            'Tier 1: Confirm whether the user changed phones, changed numbers, lost the device, or reinstalled the authenticator app.',
            'Tier 1: Review existing registered MFA methods and whether any valid method remains available.',
            'Tier 2 / Identity Support: Reset MFA or require re-registration according to approved policy.',
            'Tier 1: Confirm successful re-registration and test sign-in.',
        ],
        'admin': [
            'Escalation notes: require stronger verification for high-risk MFA resets; escalate suspicious reset requests to Security or Identity/Access Management.',
        ],
    },
    'FIX_MFA_DELIVERY_BASIC_CHECKS': {
        'technician': [
            'Tier 1: Confirm whether the MFA challenge is being sent.',
            'Tier 1: Ask the user to open the authenticator app manually and check notification permissions.',
            'Tier 1: Confirm phone internet/cellular signal and that the prompt has not expired.',
            'Tier 2 / Identity Support: Check MFA logs for sent prompts, timeouts, denied prompts, method used, IP/location, and device if available.',
            'Escalate if prompts are sent but not delivered after basic checks.',
        ],
        'admin': [
            'Escalation notes: escalate if MFA service degradation, policy issue, or multi-user MFA delivery failure is suspected.',
        ],
    },
    'FIX_MFA_CODE_TIME_SYNC': {
        'technician': [
            'Tier 1: Confirm the user selected the correct authenticator account.',
            'Tier 1: Have the user wait for the next code and enter it before expiration.',
            'Tier 1: Confirm the phone date/time is set automatically.',
            'Tier 2 / Identity Support: Check failed MFA reason in logs if codes continue failing.',
            'Re-register the authenticator app if policy allows and code failures persist.',
        ],
        'admin': [
            'Escalation notes: escalate repeated code failures when logs suggest identity-provider, policy, or device compliance issues.',
        ],
    },
    'FIX_REPORT_SUSPICIOUS_MFA_PROMPT': {
        'technician': [
            'Tier 1: Tell the user to deny unexpected prompts and not approve sign-ins they did not initiate.',
            'Tier 2 / Security Support: Capture prompt time, source IP/location, device/user agent, MFA result, and whether prompts repeated.',
            'Tier 2 / Security Support: Check whether other accounts show similar suspicious MFA activity if visible.',
            'Do not simply reset MFA without reviewing account risk.',
            'Escalate to Security and follow incident response guidance.',
        ],
        'admin': [
            'Escalation notes: treat unexpected MFA prompts, MFA fatigue indicators, or unfamiliar sign-ins as security-sensitive.',
        ],
    },
}


def _replace_kb_it_steps_for_problem(cursor, problem_code, steps):
    cursor.execute(
        """
        SELECT ka.kb_article_id
        FROM kb_article ka
        JOIN problem p ON p.problem_id = ka.problem_id
        WHERE p.problem_code = ?
        """,
        (problem_code,),
    )
    row = cursor.fetchone()
    if not row:
        return
    kb_id = row['kb_article_id']
    cursor.execute('DELETE FROM kb_article_it_step WHERE kb_article_id = ?', (kb_id,))
    cursor.executemany(
        'INSERT INTO kb_article_it_step (kb_article_id, step_text, sort_order) VALUES (?, ?, ?)',
        [(kb_id, step, index) for index, step in enumerate(steps, start=1)],
    )


def _replace_solution_audience_steps(cursor, solution_code, audience, steps):
    solution_id = get_solution_id_by_code(cursor, solution_code)
    if not solution_id:
        return
    cursor.execute(
        'DELETE FROM solution_step WHERE solution_id = ? AND audience = ?',
        (solution_id, audience),
    )
    cursor.executemany(
        'INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)',
        [(solution_id, audience, step, index) for index, step in enumerate(steps, start=1)],
    )


def seed_existing_issue_role_alignment(cursor):
    """Align early polished issues with the final portfolio role model.

    Regular users keep safe self-service steps. Support-side users see
    IT Support Specialist steps suitable for Tier 1 / junior Tier 2 work.
    The stored 'admin' audience is used as escalation notes / Tier 2-3 handoff,
    not as a separate company-admin troubleshooting role.
    """
    for problem_code, steps in EXISTING_ISSUE_ALIGNMENT_KB_IT_STEPS.items():
        _replace_kb_it_steps_for_problem(cursor, problem_code, steps)

    for solution_code, audience_map in EXISTING_ISSUE_ALIGNMENT_SOLUTION_STEPS.items():
        for audience, steps in audience_map.items():
            _replace_solution_audience_steps(cursor, solution_code, audience, steps)


# -----------------------------
# BROWSER ISSUE CONTENT
# -----------------------------
BROWSER_ISSUE_PROBLEM = (
    'BROWSER_ISSUE',
    'Browser Issue',
    'Software & Applications',
    'Medium',
    'The user cannot open the browser, load a website, sign in to a web app, download files, or use a browser-based business application correctly.'
)

BROWSER_ISSUE_KB = {
    'title': 'Browser Issue',
    'summary': 'Use this guide when a browser will not open, websites will not load, a web app behaves incorrectly, login loops occur, downloads are blocked, or browser security warnings appear.',
    'difficulty': 'Intermediate',
    'estimated_time': '10-25 minutes',
    'escalation_required': 0,
    'escalation_notes': 'Escalate when a business-critical web app is unavailable, multiple users are affected, network/proxy/DNS/firewall issues are suspected, or suspicious browser behavior/security warnings appear.',
    'tags': ['browser', 'website not loading', 'cache', 'cookies', 'extensions', 'Microsoft Edge', 'Chrome', 'VPN', 'DNS', 'proxy', 'certificate warning', 'web app'],
    'symptoms': [
        'Pages do not load or stay spinning.',
        'The browser is slow, crashes, opens and closes immediately, or does not respond.',
        'One website or business web app fails while other sites work.',
        'Login loops, sign-in errors, or web app buttons do not work.',
        'Downloads, pop-ups, camera, microphone, cookies, or other site permissions are blocked.',
        'Certificate warnings, security warnings, blocked pages, or download warnings appear.',
        'Unexpected pop-ups, redirects, homepage/search changes, or suspicious extensions appear.',
    ],
    'causes': [
        'Common causes include stale cache/cookies, browser extensions, outdated browser version, corrupted profile, wrong account/session, blocked permissions, DNS or network problems, VPN/proxy/firewall restrictions, endpoint security tools, certificate warnings, or web app outage.',
        'Advanced causes include certificate chain/TLS inspection issues, incorrect system date/time, DNS cache or hosts-file problems, managed browser policy, malicious extension/browser hijacker, SSO or conditional access issue, proxy misconfiguration, web app backend/API outage, or captive portal/public Wi-Fi interference.',
    ],
    'user_steps': [
        'Confirm whether other websites work.',
        'Refresh the page, then close and reopen the browser.',
        'Try a private/incognito window.',
        'Try another approved browser.',
        'Confirm you are signed in with the correct work account.',
        'Connect to VPN if the site is internal or company-only.',
        'Do not bypass certificate or security warnings unless IT confirms it is safe.',
        'Do not install browser extensions from unapproved sources.',
        'Take a screenshot of the error, warning, or blocked page.',
        'Contact IT if the issue blocks business work, affects internal resources, or looks suspicious.',
    ],
    'it_steps': [
        'Confirm the user, device name, browser name/version, website URL, network type, VPN status, and exact error.',
        'Determine scope: one website, all websites, one browser, all browsers, one user/device, or multiple users.',
        'Test whether the site works in private/incognito mode.',
        'Test another approved browser.',
        'Restart browser and device if needed.',
        'Check browser update status.',
        'Clear cache/cookies for the affected site or browser if appropriate.',
        'Temporarily disable extensions only if company policy allows.',
        'Confirm whether the user is signed in with the correct account.',
        'Check whether VPN is required for the site.',
        'Check whether endpoint, web filtering, proxy, or security tools are blocking the site or download.',
        'Test DNS resolution for the affected website or internal host.',
        'Compare behavior on VPN, office network, home network, and hotspot if appropriate.',
        'Check proxy settings and whether a proxy or web filter is involved.',
        'Check certificate details and system date/time if a certificate warning appears.',
        'Check site permissions such as pop-ups, cookies, camera, microphone, location, notifications, and downloads.',
        'Review suspicious extensions, homepage/search changes, redirects, or pop-ups as possible malware/browser hijack.',
        'Check whether multiple users are affected, suggesting web app, DNS, proxy, or service outage.',
        'Escalate with URL, DNS results, browser/version, network path, screenshots, certificate details, and affected scope.',
    ],
}

BROWSER_ISSUE_SOLUTIONS = [
    ('FIX_BROWSER_CHECK_NETWORK_ACCESS', 'Check Internet, DNS, or Network Access', 'If all websites fail, the issue may be internet, DNS, proxy, or network connectivity rather than the browser.', 'Confirm network access before browser-specific troubleshooting.', 0, 'Escalate to Network team if DNS, proxy, routing, or connectivity issue is suspected.', 'medium'),
    ('FIX_BROWSER_CACHE_COOKIES_EXTENSION', 'Clear Cache/Cookies or Disable Problem Extension', 'Cached data, cookies, or extensions can cause login loops, stale pages, or broken web app behavior.', 'Test private mode, clear site data, and isolate extensions according to policy.', 0, 'Escalate if managed extension or browser policy causes the issue.', 'medium'),
    ('FIX_BROWSER_CONNECT_VPN_INTERNAL_SITE', 'Connect to VPN and Test Internal Site', 'Internal company websites may require VPN or corporate network access.', 'Connect to VPN and confirm internal access.', 0, 'Escalate if VPN, internal DNS, routing, or web app access fails.', 'medium'),
    ('FIX_BROWSER_SECURITY_WARNING_SUSPICIOUS', 'Report Browser Security Warning or Suspicious Behavior', 'Security warnings, redirects, pop-ups, and unknown extensions may indicate unsafe site, malware, or browser hijack.', 'Do not bypass warnings; collect evidence and report safely.', 1, 'Escalate to Security if malicious site, browser hijack, suspicious extension, or malware is suspected.', 'high'),
    ('FIX_BROWSER_WEB_APP_ACCESS_ISSUE', 'Report Website or Web App Access Issue', 'One website or web app fails even after browser-local checks.', 'Collect URL, screenshots, and affected scope for support.', 1, 'Escalate to App Support, Network, or Identity based on evidence.', 'medium'),
    ('FIX_BROWSER_PROFILE_EXTENSIONS', 'Troubleshoot Browser Cache, Profile, or Extensions', 'Browser-specific failures often come from corrupted profile, cached data, or extensions.', 'Isolate browser profile, cache, and extension behavior.', 0, 'Escalate to Endpoint/Desktop if browser repair, managed policy, or profile rebuild is needed.', 'medium'),
    ('FIX_BROWSER_DNS_NETWORK_PATH', 'Troubleshoot Browser-Related DNS or Network Path', 'The browser may fail because the site hostname does not resolve or the network path is blocked.', 'Test DNS and compare network paths.', 1, 'Escalate to Network with DNS results, URL, network path, and affected scope.', 'high'),
    ('FIX_BROWSER_PROXY_VPN_WEB_FILTER', 'Investigate Proxy, VPN, Firewall, or Web Filter', 'Browser traffic may be blocked or modified by proxy, VPN, firewall, web filter, or TLS inspection.', 'Check network path and security filtering.', 1, 'Escalate to Network/Security with URL, category, block reason, and business need.', 'high'),
    ('FIX_BROWSER_ESCALATE_WEB_APP_SERVICE', 'Escalate Web App or Service Issue', 'Multiple users affected may indicate application, backend, identity, or service outage.', 'Confirm scope and escalate to app/service owner.', 1, 'Escalate to Web App/Application Support or Systems team with incident details.', 'high'),
    ('FIX_BROWSER_POLICIES_PERMISSIONS_SECURITY', 'Check Browser Policies, Permissions, and Security Tools', 'Managed browser policies, permissions, endpoint tools, or site settings may block required functionality.', 'Review permissions, policy, and endpoint/security controls.', 1, 'Escalate to Endpoint/Security/App Support if policy change is required.', 'medium'),
]

BROWSER_ISSUE_SOLUTION_STEPS = {
    'FIX_BROWSER_CHECK_NETWORK_ACCESS': {
        'user': ['Confirm Wi-Fi or Ethernet is connected.', 'Try another website.', 'Restart the browser.', 'Restart the computer if needed.', 'Contact IT if no websites work.'],
        'technician': ['Confirm IP address, gateway, DNS, and network status.', 'Test public website access and DNS resolution.', 'Compare browser behavior with other network applications.', 'Check proxy and VPN status if applicable.', 'Escalate if network outage or DNS issue is suspected.'],
        'admin': ['Escalate to Network with device name, network type, IP/DNS/gateway details, affected websites, DNS results, and affected scope.'],
    },
    'FIX_BROWSER_CACHE_COOKIES_EXTENSION': {
        'user': ['Try a private/incognito window.', 'If it works there, tell IT.', 'Clear cache/cookies only for the affected site if instructed.', 'Do not install or remove extensions unless IT instructs you.'],
        'technician': ['Test private/incognito mode.', 'Clear site-specific cache and cookies first when possible.', 'Disable extensions one at a time if allowed by policy.', 'Update browser and extensions.', 'Document which change resolved the issue.'],
        'admin': ['Escalate if a managed extension, browser policy, or business web app cookie/session requirement needs review.'],
    },
    'FIX_BROWSER_CONNECT_VPN_INTERNAL_SITE': {
        'user': ['Connect to the company VPN.', 'Wait until VPN shows connected.', 'Refresh the internal site.', 'If VPN fails, use the VPN troubleshooting flow.'],
        'technician': ['Confirm whether the site is internal-only.', 'Confirm VPN status and internal resource access.', 'Test DNS resolution for the internal site.', 'Determine whether this is VPN, DNS, routing, or web app access issue.', 'Escalate with URL, VPN status, DNS result, and error screenshot.'],
        'admin': ['Escalate to Network or Application Support if VPN is connected but internal DNS/routing/web access still fails.'],
    },
    'FIX_BROWSER_SECURITY_WARNING_SUSPICIOUS': {
        'user': ['Do not bypass certificate or security warnings.', 'Do not enter passwords on suspicious pages.', 'Take a screenshot of the warning if safe.', 'Report unexpected redirects, pop-ups, or homepage changes to IT.'],
        'technician': ['Capture URL, screenshot, warning text, and browser version.', 'Check certificate details if appropriate.', 'Check for suspicious extensions or homepage/search changes.', 'Check endpoint/web filtering alerts.', 'Escalate to Security if malicious site, browser hijack, or malware is suspected.'],
        'admin': ['Escalate to Security with URL, certificate warning details, screenshots, extensions found, endpoint alerts, and user actions.'],
    },
    'FIX_BROWSER_WEB_APP_ACCESS_ISSUE': {
        'user': ['Record the website URL.', 'Take a screenshot of the error.', 'Note whether coworkers can access it.', 'Submit a ticket with the time the issue started.'],
        'technician': ['Confirm affected URL and user action.', 'Check whether multiple users are affected.', 'Compare different browsers, devices, and networks.', 'Check whether user has permission to the web app.', 'Escalate to App Support, Network, or Identity based on evidence.'],
        'admin': ['Escalate with URL, screenshots, user/account, affected users, browsers tested, network paths tested, and business impact.'],
    },
    'FIX_BROWSER_PROFILE_EXTENSIONS': {
        'user': ['Try another approved browser.', 'Try private/incognito mode.', 'Report whether the issue happens only in one browser.'],
        'technician': ['Confirm issue is browser/profile-specific.', 'Clear site data or browser cache as appropriate.', 'Test with extensions disabled.', 'Create a temporary clean browser profile if policy allows.', 'Repair or reset browser only after preserving needed bookmarks/settings according to policy.'],
        'admin': ['Escalate to Endpoint/Desktop if managed browser settings, profile corruption, or repair/reinstall is required.'],
    },
    'FIX_BROWSER_DNS_NETWORK_PATH': {
        'user': ['Confirm internet or VPN is connected.', 'Try the site again later if IT confirms outage.', 'Provide the exact URL and screenshot.'],
        'technician': ['Test DNS resolution for the site or internal host.', 'Compare behavior on VPN, office network, home network, and hotspot.', 'Check proxy and DNS settings.', 'Determine whether issue is DNS, routing, firewall, proxy, or site outage.', 'Escalate with DNS results, URL, network path, and affected scope.'],
        'admin': ['Escalate to Network with DNS results, tested networks, URL/hostname, error screenshot, timestamp, and affected scope.'],
    },
    'FIX_BROWSER_PROXY_VPN_WEB_FILTER': {
        'user': ['Tell IT whether you are on VPN, office network, home Wi-Fi, or public Wi-Fi.', 'Take a screenshot of the blocked page.', 'Do not try to bypass company filtering.'],
        'technician': ['Confirm network path and proxy status.', 'Check whether web filtering/security tool blocked the site.', 'Check whether issue affects one user or network segment.', 'Compare on alternate trusted network if allowed.', 'Escalate to Network/Security with URL, category, block reason, and business need.'],
        'admin': ['Escalate to Network/Security with URL, block reason/category, proxy/VPN path, affected users, and business justification.'],
    },
    'FIX_BROWSER_ESCALATE_WEB_APP_SERVICE': {
        'user': ['Record the error message and time.', 'Ask whether coworkers see the same issue.', 'Avoid repeated login attempts if errors continue.'],
        'technician': ['Confirm affected users, browsers, devices, and locations.', 'Check service status or internal outage notes if available.', 'Capture URL, error, timestamp, and steps to reproduce.', 'Escalate to Web App/Application Support or Systems team.', 'Update the ticket with incident details.'],
        'admin': ['Escalate as a possible app/service incident with affected scope, URL, screenshots, timestamps, user groups, and reproduction steps.'],
    },
    'FIX_BROWSER_POLICIES_PERMISSIONS_SECURITY': {
        'user': ['Tell IT what action is blocked, such as camera, microphone, pop-up, download, or sign-in.', 'Do not change security settings unless IT instructs you.', 'Provide a screenshot of the blocked action.'],
        'technician': ['Check site permissions for pop-ups, cookies, camera, microphone, notifications, location, and downloads.', 'Check managed browser policies if available.', 'Check endpoint, web filtering, and security events.', 'Confirm whether the setting should be allowed for business use.', 'Escalate to Endpoint/Security/App Support if policy change is required.'],
        'admin': ['Escalate with required permission/policy, business need, URL, affected browser, current policy behavior, and security impact.'],
    },
}

BROWSER_ISSUE_USER_DIAGNOSTIC_NODES = [
    ('ROOT_BROWSER_USER', None, 'category', 'Browser Issue', 'User-friendly diagnostic path for browser, website, internal site, and security-warning issues.', None, None, None, None, 1),
    ('Q_BROWSER_SCOPE_USER', 'ROOT_BROWSER_USER', 'question', 'Check Website Scope', None, 'Is the issue with one website or all websites?', None, None, None, 1),
    ('S_BROWSER_NETWORK_USER', 'Q_BROWSER_SCOPE_USER', 'solution', 'Check Internet, DNS, or Network Access', None, None, 'All websites', 'All websites', 'FIX_BROWSER_CHECK_NETWORK_ACCESS', 1),
    ('Q_BROWSER_PRIVATE_USER', 'Q_BROWSER_SCOPE_USER', 'question', 'Try Private or Another Browser', None, 'Does it work in private/incognito or another approved browser?', 'One website', 'One website', None, 2),
    ('S_BROWSER_CACHE_USER', 'Q_BROWSER_PRIVATE_USER', 'solution', 'Clear Cache/Cookies or Disable Problem Extension', None, None, 'Yes', 'Yes', 'FIX_BROWSER_CACHE_COOKIES_EXTENSION', 1),
    ('Q_BROWSER_INTERNAL_USER', 'Q_BROWSER_PRIVATE_USER', 'question', 'Check Internal Site Requirement', None, 'Is it an internal company site requiring VPN?', 'No', 'No', None, 2),
    ('S_BROWSER_VPN_USER', 'Q_BROWSER_INTERNAL_USER', 'solution', 'Connect to VPN and Test Internal Site', None, None, 'Yes', 'Yes', 'FIX_BROWSER_CONNECT_VPN_INTERNAL_SITE', 1),
    ('Q_BROWSER_SECURITY_USER', 'Q_BROWSER_INTERNAL_USER', 'question', 'Check Warning or Suspicious Behavior', None, 'Is there a security warning, blocked page, pop-up, or redirect?', 'No', 'No', None, 2),
    ('S_BROWSER_SECURITY_USER', 'Q_BROWSER_SECURITY_USER', 'solution', 'Report Browser Security Warning or Suspicious Behavior', None, None, 'Yes', 'Yes', 'FIX_BROWSER_SECURITY_WARNING_SUSPICIOUS', 1),
    ('S_BROWSER_WEBAPP_USER', 'Q_BROWSER_SECURITY_USER', 'solution', 'Report Website or Web App Access Issue', None, None, 'No', 'No', 'FIX_BROWSER_WEB_APP_ACCESS_ISSUE', 2),
]

BROWSER_ISSUE_TECH_DIAGNOSTIC_NODES = [
    ('ROOT_BROWSER_TECH', None, 'category', 'Browser Issue - IT Support Specialist', 'IT Support Specialist diagnostic path for browser profile, DNS, proxy, VPN, web app, and security-tool issues.', None, None, None, None, 1),
    ('Q_BROWSER_PROFILE_TECH', 'ROOT_BROWSER_TECH', 'question', 'Check Browser/Profile Scope', None, 'Is the issue one browser/profile or all browsers?', None, None, None, 1),
    ('S_BROWSER_PROFILE_TECH', 'Q_BROWSER_PROFILE_TECH', 'solution', 'Troubleshoot Browser Cache, Profile, or Extensions', None, None, 'One browser/profile', 'One browser/profile', 'FIX_BROWSER_PROFILE_EXTENSIONS', 1),
    ('Q_BROWSER_DNS_TECH', 'Q_BROWSER_PROFILE_TECH', 'question', 'Check DNS Resolution', None, 'Does DNS resolve the affected site/internal host?', 'All browsers', 'All browsers', None, 2),
    ('S_BROWSER_DNS_TECH', 'Q_BROWSER_DNS_TECH', 'solution', 'Troubleshoot Browser-Related DNS or Network Path', None, None, 'No', 'No', 'FIX_BROWSER_DNS_NETWORK_PATH', 1),
    ('Q_BROWSER_NETWORKPATH_TECH', 'Q_BROWSER_DNS_TECH', 'question', 'Check VPN/Proxy/Network Path', None, 'Does issue depend on VPN, proxy, or network path?', 'Yes', 'Yes', None, 2),
    ('S_BROWSER_PROXY_TECH', 'Q_BROWSER_NETWORKPATH_TECH', 'solution', 'Investigate Proxy, VPN, Firewall, or Web Filter', None, None, 'Yes', 'Yes', 'FIX_BROWSER_PROXY_VPN_WEB_FILTER', 1),
    ('Q_BROWSER_MULTI_TECH', 'Q_BROWSER_NETWORKPATH_TECH', 'question', 'Check Multiple Users', None, 'Are multiple users affected?', 'No', 'No', None, 2),
    ('S_BROWSER_WEBAPP_TECH', 'Q_BROWSER_MULTI_TECH', 'solution', 'Escalate Web App or Service Issue', None, None, 'Yes', 'Yes', 'FIX_BROWSER_ESCALATE_WEB_APP_SERVICE', 1),
    ('S_BROWSER_POLICY_TECH', 'Q_BROWSER_MULTI_TECH', 'solution', 'Check Browser Policies, Permissions, and Security Tools', None, None, 'No', 'No', 'FIX_BROWSER_POLICIES_PERMISSIONS_SECURITY', 2),
]

def seed_browser_issue_content(cursor):
    """Seed Browser Issue KB article, solutions, steps, and diagnostic trees."""
    code_, title, category, severity, description = BROWSER_ISSUE_PROBLEM
    cursor.execute("""
        INSERT INTO problem (problem_code, title, category, severity, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(problem_code) DO UPDATE SET
            title=excluded.title, category=excluded.category, severity=excluded.severity,
            description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, BROWSER_ISSUE_PROBLEM)
    cursor.execute('SELECT problem_id FROM problem WHERE problem_code = ?', (code_,))
    row = cursor.fetchone()
    if not row:
        return
    problem_id = row['problem_id']
    cursor.execute("""
        INSERT INTO kb_article (problem_id, title, summary, difficulty, estimated_time, escalation_required, escalation_notes, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, difficulty=excluded.difficulty,
            estimated_time=excluded.estimated_time, escalation_required=excluded.escalation_required,
            escalation_notes=excluded.escalation_notes, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, BROWSER_ISSUE_KB['title'], BROWSER_ISSUE_KB['summary'], BROWSER_ISSUE_KB['difficulty'], BROWSER_ISSUE_KB['estimated_time'], BROWSER_ISSUE_KB['escalation_required'], BROWSER_ISSUE_KB['escalation_notes']))
    cursor.execute('SELECT kb_article_id FROM kb_article WHERE problem_id = ?', (problem_id,))
    article = cursor.fetchone()
    if article:
        kb_id = article['kb_article_id']
        delete_kb_child_rows(cursor, kb_id)
        insert_kb_child_rows(cursor, 'kb_article_tag', 'tag', kb_id, BROWSER_ISSUE_KB['tags'])
        insert_kb_child_rows(cursor, 'kb_article_symptom', 'symptom', kb_id, BROWSER_ISSUE_KB['symptoms'])
        insert_kb_child_rows(cursor, 'kb_article_cause', 'cause', kb_id, BROWSER_ISSUE_KB['causes'])
        insert_kb_child_rows(cursor, 'kb_article_user_step', 'step_text', kb_id, BROWSER_ISSUE_KB['user_steps'])
        insert_kb_child_rows(cursor, 'kb_article_it_step', 'step_text', kb_id, BROWSER_ISSUE_KB['it_steps'])
    cursor.executemany("""
        INSERT INTO solution (solution_code, title, summary, resolution_steps, escalation_required, escalation_notes, priority_recommendation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(solution_code) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, resolution_steps=excluded.resolution_steps,
            escalation_required=excluded.escalation_required, escalation_notes=excluded.escalation_notes,
            priority_recommendation=excluded.priority_recommendation, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, BROWSER_ISSUE_SOLUTIONS)
    for solution_code, audience_steps in BROWSER_ISSUE_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue
        for audience, steps in audience_steps.items():
            cursor.execute('DELETE FROM solution_step WHERE solution_id = ? AND audience = ?', (solution_id, audience))
            cursor.executemany('INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)', [(solution_id, audience, step, idx) for idx, step in enumerate(steps, start=1)])
    seed_browser_issue_tree(cursor, 'user', 'BROWSER_ISSUE_USER', 'Browser Issue - User Diagnostic', 'User-friendly diagnostic tree for browser, website, internal-site, and security-warning issues.', BROWSER_ISSUE_USER_DIAGNOSTIC_NODES)
    seed_browser_issue_tree(cursor, 'technician', 'BROWSER_ISSUE_TECHNICIAN', 'Browser Issue - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for browser profile, DNS, proxy, VPN, web app, and security-tool issues.', BROWSER_ISSUE_TECH_DIAGNOSTIC_NODES)

def seed_browser_issue_tree(cursor, audience, tree_code, title, description, nodes):
    problem_id = get_problem_id_for_tree_code(cursor, 'BROWSER_ISSUE')
    cursor.execute("""
        INSERT INTO diagnostic_tree (problem_id, diagnostic_tree_code, base_tree_code, audience, title, description, is_active, updated_at)
        VALUES (?, ?, 'BROWSER_ISSUE', ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(diagnostic_tree_code) DO UPDATE SET
            problem_id=excluded.problem_id, base_tree_code=excluded.base_tree_code, audience=excluded.audience,
            title=excluded.title, description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, tree_code, audience, title, description))
    tree_id = get_diagnostic_tree_id_by_code(cursor, tree_code)
    if not tree_id:
        return
    cursor.execute('UPDATE diagnostic_node SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE diagnostic_tree_id = ?', (tree_id,))
    for node_key, parent_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_code, sort_order in nodes:
        parent_id = get_diagnostic_node_id_by_tree_and_key(cursor, tree_id, parent_key) if parent_key else None
        solution_id = get_solution_id_by_code(cursor, solution_code) if solution_code else None
        cursor.execute("""
            INSERT INTO diagnostic_node (
                diagnostic_tree_id, parent_diagnostic_node_id, problem_id, diagnostic_tree_code,
                node_key, node_type, title, description, prompt_text,
                condition_label, condition_value, solution_id, sort_order, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(diagnostic_tree_code, node_key) DO UPDATE SET
                diagnostic_tree_id=excluded.diagnostic_tree_id,
                parent_diagnostic_node_id=excluded.parent_diagnostic_node_id,
                problem_id=excluded.problem_id,
                node_type=excluded.node_type,
                title=excluded.title,
                description=excluded.description,
                prompt_text=excluded.prompt_text,
                condition_label=excluded.condition_label,
                condition_value=excluded.condition_value,
                solution_id=excluded.solution_id,
                sort_order=excluded.sort_order,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (tree_id, parent_id, problem_id, tree_code, node_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_id, sort_order))


CERTIFICATE_SECURITY_WARNING_PROBLEM = (
    'CERTIFICATE_SECURITY_WARNING',
    'Certificate / Security Warning',
    'Software & Applications / Security',
    'Medium',
    'The user sees a browser or application warning that a website, certificate, or connection may not be secure.'
)

CERTIFICATE_SECURITY_WARNING_KB = {
    'title': 'Certificate / Security Warning',
    'summary': 'Use this guide when a browser or application warns that a website connection is not private, not secure, expired, mismatched, or untrusted.',
    'difficulty': 'Intermediate',
    'estimated_time': '10-25 minutes',
    'escalation_required': 1,
    'escalation_notes': 'Escalate when credentials may have been entered, a company site is affected, multiple users see the warning, DNS/proxy/VPN/TLS inspection is suspected, or phishing/interception risk exists.',
    'tags': ['certificate warning', 'security warning', 'HTTPS', 'TLS', 'SSL', 'browser security', 'certificate expired', 'untrusted certificate', 'DNS', 'proxy', 'VPN'],
    'symptoms': [
        'Browser says the site is not secure or the connection is not private.',
        'The certificate is expired, not trusted, or does not match the website name.',
        'Secure connection failed or certificate authority not trusted message appears.',
        'Warning appears only on VPN, public Wi-Fi, office network, or one specific browser/device.',
        'The site worked previously but now shows a security warning.',
        'Coworkers can access the site but the user cannot, or multiple users see the same warning.',
        'The warning appeared after clicking a link from email, chat, or an unexpected message.',
    ],
    'causes': [
        'Common causes include expired or mismatched certificates, incorrect device date/time, untrusted certificate authority, captive portal/public Wi-Fi, internal certificate trust issue, DNS misdirection, proxy/TLS inspection, endpoint security inspection, or phishing/lookalike websites.',
        'Advanced causes include missing intermediate certificate, certificate chain misconfiguration, DNS poisoning or wrong DNS record, TLS inspection appliance issue, revocation-check failure, split-horizon DNS problem, old browser/OS trust store, incorrect SNI/load balancer certificate, or incomplete certificate renewal deployment.',
    ],
    'user_steps': [
        'Do not bypass the warning or continue to the site unless IT confirms it is safe.',
        'Check that the website address is typed correctly.',
        'Do not enter passwords, MFA codes, payment information, or sensitive data on a site with a warning.',
        'If the site was opened from an email or chat link, stop and report the message/link to IT.',
        'Check whether the warning appears in another approved browser.',
        'Check whether the device date and time look correct.',
        'If on public Wi-Fi, complete the Wi-Fi sign-in page first or switch to a trusted network.',
        'Take a screenshot of the warning and visible website address.',
        'Note whether coworkers see the same warning.',
        'Submit a ticket with the URL, screenshot, network type, and VPN status.',
    ],
    'it_steps': [
        'Confirm the user, device name, browser/application, URL, network type, VPN status, and exact warning message.',
        'Ask whether the user typed the address manually or clicked a link from email/chat.',
        'Instruct the user not to bypass the warning or enter credentials until reviewed.',
        'Determine scope: one site or many sites, one browser or all browsers, one device or multiple devices, one network/VPN/proxy path or all paths.',
        'Check system date, time, and time zone.',
        'Check whether the URL is spelled correctly and matches the expected company domain.',
        'Test in another approved browser if appropriate.',
        'Ask whether coworkers can access the same site.',
        'Capture screenshot, URL, certificate warning text, timestamp, and network path.',
        'If the link came from suspicious email/chat, route to phishing process.',
        'Inspect certificate details safely: subject, SAN, issuer, expiration dates, chain/path, and trust status.',
        'Check whether the certificate hostname matches the URL.',
        'Test DNS resolution for the hostname and compare with expected IP/path.',
        'Compare behavior on office network, VPN, home network, and hotspot where appropriate.',
        'Check whether proxy, TLS inspection, web filtering, or endpoint security is presenting a replacement certificate.',
        'Check whether required internal CA/root/intermediate certificate is missing from the device.',
        'Check whether multiple users or devices are affected.',
        'For internal sites, check whether certificate renewal/deployment may be incomplete.',
        'Escalate with URL, certificate details, DNS result, network path, screenshots, affected scope, and risk assessment.',
    ],
}

CERTIFICATE_SECURITY_WARNING_SOLUTIONS = [
    ('FIX_CERT_WARNING_REPORT_PHISHING_LINK', 'Report Possible Phishing or Unsafe Link', 'The warning appeared after opening a suspicious or unexpected link.', 'Stop, do not continue, and report the source message/link.', 1, 'Escalate to Security if the link/domain is suspicious or multiple users received it.', 'high'),
    ('FIX_CERT_WARNING_CREDENTIAL_EXPOSURE', 'Report Possible Credential Exposure', 'User entered credentials or sensitive information on a site that showed a certificate/security warning.', 'Treat as possible account compromise and escalate immediately.', 1, 'Escalate to Security/Identity for password reset, session revocation, MFA review, and sign-in review.', 'high'),
    ('FIX_CERT_WARNING_DEVICE_TIME_TRUST', 'Check Device Time, Network, or Trust Issue', 'Certificate warnings on many sites often indicate device time, captive portal, proxy, or trust-store issue.', 'Check date/time, network path, captive portal, and trust store.', 0, 'Escalate if internal CA or TLS inspection trust deployment appears misconfigured.', 'medium'),
    ('FIX_CERT_WARNING_INTERNAL_SITE', 'Report Internal Site Certificate Warning', 'An internal company site may have an expired, mismatched, or untrusted certificate.', 'Collect URL/certificate details and route to site owner.', 1, 'Escalate to Systems/Web App/Network team based on certificate or path issue.', 'high'),
    ('FIX_CERT_WARNING_DO_NOT_BYPASS', 'Do Not Bypass Browser Security Warning', 'The safest action is to stop and verify before continuing.', 'Do not continue until IT validates the site and certificate.', 0, 'Escalate if site ownership, certificate validity, or safety is unclear.', 'medium'),
    ('FIX_CERT_WARNING_ESCALATE_SECURITY', 'Escalate Suspicious Certificate Warning to Security', 'Suspicious certificate warning may indicate phishing, unsafe domain, or interception.', 'Escalate with indicators and user actions.', 1, 'Escalate to Security with URL, screenshot, source link, user actions, and affected users.', 'high'),
    ('FIX_CERT_WARNING_VALIDATE_CERT_ROUTE_OWNER', 'Validate Certificate Details and Route Owner', 'Certificate appears expired, mismatched, untrusted, or incorrectly chained.', 'Inspect certificate fields and route to responsible owner.', 1, 'Escalate to Systems/Web App or vendor owner with certificate subject/SAN, issuer, dates, chain, and affected scope.', 'high'),
    ('FIX_CERT_WARNING_DNS_NETWORK_PATH', 'Troubleshoot DNS or Network Path', 'DNS or network path may send the user to the wrong server or certificate.', 'Compare DNS and network path across trusted paths.', 1, 'Escalate to Network if DNS, routing, split-DNS, proxy, or path is wrong.', 'high'),
    ('FIX_CERT_WARNING_TRUST_TLS_INSPECTION', 'Investigate Device Trust Store or TLS Inspection', 'One device or network path may lack the required trusted CA or may be affected by TLS inspection.', 'Check internal CA trust and TLS inspection behavior.', 1, 'Escalate to Endpoint/Network/Security if trust deployment or TLS inspection is misconfigured.', 'high'),
    ('FIX_CERT_WARNING_CERT_DEPLOYMENT_ESCALATE', 'Escalate Internal Site or Certificate Deployment Issue', 'Multiple users or a legitimate internal site may have server/load-balancer certificate deployment issue.', 'Collect evidence and escalate to the certificate/site owner.', 1, 'Escalate to Systems/Web App/Network team with URL, certificate details, network path, screenshots, and affected scope.', 'high'),
]

CERTIFICATE_SECURITY_WARNING_SOLUTION_STEPS = {
    'FIX_CERT_WARNING_REPORT_PHISHING_LINK': {
        'user': ['Do not continue to the site.', 'Do not enter credentials, MFA codes, or sensitive information.', 'Close the page.', 'Report the email, chat, or link to IT or Security.', 'Tell IT whether you clicked or entered anything.'],
        'technician': ['Capture the URL, source message, screenshot, and user action.', 'Route the report to the phishing workflow.', 'Check whether credentials or MFA were entered.', 'Escalate to Security if the domain is suspicious or multiple users received it.'],
        'admin': ['Escalate to Security with source message, URL, domain, screenshot, user action, timestamp, and affected-user scope.'],
    },
    'FIX_CERT_WARNING_CREDENTIAL_EXPOSURE': {
        'user': ['Stop using the site immediately.', 'Do not approve unexpected MFA prompts.', 'Contact IT/Security immediately.', 'Be ready to reset your password through the official process.'],
        'technician': ['Treat as possible account compromise.', 'Capture timeline, URL, account, information entered, and whether MFA was approved.', 'Escalate to Security/Identity for password reset, session revocation, and sign-in review.', 'Document containment actions.'],
        'admin': ['Escalate immediately to Security/Identity with account, URL, timestamps, submitted information, MFA status, and requested containment actions.'],
    },
    'FIX_CERT_WARNING_DEVICE_TIME_TRUST': {
        'user': ['Check whether the date and time look correct.', 'If on public Wi-Fi, complete the Wi-Fi sign-in page first.', 'Try a trusted network if available.', 'Do not bypass warnings.'],
        'technician': ['Confirm system date, time, and time zone.', 'Check whether the warning occurs on many HTTPS sites.', 'Check network type and captive portal status.', 'Compare another approved browser.', 'Check internal CA/trust store if using managed TLS inspection.'],
        'admin': ['Escalate if managed certificate trust, captive portal, proxy, TLS inspection, or internal CA deployment appears misconfigured.'],
    },
    'FIX_CERT_WARNING_INTERNAL_SITE': {
        'user': ['Do not bypass the warning.', 'Capture the URL and screenshot.', 'Tell IT whether VPN is connected.', 'Ask coworkers whether they see the same warning.'],
        'technician': ['Confirm the internal URL and VPN/network path.', 'Inspect certificate subject, issuer, validity dates, SAN, and chain.', 'Check whether multiple users are affected.', 'Route to Systems/Web App/Network team based on certificate or path issue.'],
        'admin': ['Escalate with internal URL, certificate details, VPN/network path, affected users, screenshots, and business impact.'],
    },
    'FIX_CERT_WARNING_DO_NOT_BYPASS': {
        'user': ['Do not continue past the browser warning.', 'Do not enter passwords or personal information.', 'Take a screenshot.', 'Submit a ticket with the website address.'],
        'technician': ['Review screenshot and URL.', 'Confirm whether the site is expected and business-related.', 'Check certificate details before advising next steps.', 'Escalate if site ownership, certificate validity, or safety is unclear.'],
        'admin': ['Escalate for validation when site owner, certificate state, or safe workaround cannot be confirmed.'],
    },
    'FIX_CERT_WARNING_ESCALATE_SECURITY': {
        'user': ['Stop using the site.', 'Report the message or link.', 'Tell IT if you entered information.'],
        'technician': ['Capture URL, screenshot, source link, and user actions.', 'Check domain similarity and reported phishing context.', 'Escalate to Security with indicators and affected users.', 'Route to credential-exposure workflow if needed.'],
        'admin': ['Escalate as a possible phishing/interception event with URL, source, screenshot, user action, and affected-user list.'],
    },
    'FIX_CERT_WARNING_VALIDATE_CERT_ROUTE_OWNER': {
        'user': ['Wait for IT confirmation.', 'Use an approved alternate site or application if provided.', 'Do not bypass the warning unless IT confirms a safe workaround.'],
        'technician': ['Inspect subject/SAN, issuer, validity dates, and certificate chain.', 'Confirm whether hostname matches certificate.', 'Identify site/application owner.', 'Escalate to Systems/Web App or vendor owner with details.', 'Document affected scope and risk.'],
        'admin': ['Escalate to the certificate/site owner with certificate fields, mismatch/expiration evidence, chain status, affected users, and required renewal/deployment action.'],
    },
    'FIX_CERT_WARNING_DNS_NETWORK_PATH': {
        'user': ['Provide the exact URL.', 'Note whether VPN is connected.', 'Tell IT what network you are using.'],
        'technician': ['Test DNS resolution for the hostname.', 'Compare expected IP/path across VPN, office, and trusted network.', 'Check split-DNS or proxy path if an internal site is involved.', 'Escalate to Network if DNS, routing, or proxy path is wrong.'],
        'admin': ['Escalate to Network with URL, DNS results, expected vs observed IP/path, VPN/proxy status, network type, and affected scope.'],
    },
    'FIX_CERT_WARNING_TRUST_TLS_INSPECTION': {
        'user': ['Do not change certificate settings yourself.', 'Tell IT whether the issue happens only on one device or network.', 'Wait for IT to confirm the correct trust configuration.'],
        'technician': ['Check whether the device trusts the required internal CA.', 'Compare another managed device.', 'Check browser/OS certificate store where appropriate.', 'Check TLS inspection/proxy certificate if used.', 'Escalate to Endpoint/Network/Security if trust deployment is misconfigured.'],
        'admin': ['Escalate with device comparison, internal CA/trust-store status, proxy/TLS inspection certificate details, and affected network path.'],
    },
    'FIX_CERT_WARNING_CERT_DEPLOYMENT_ESCALATE': {
        'user': ['Use an approved alternate service path if provided.', 'Do not bypass the warning.', 'Wait for IT update.'],
        'technician': ['Confirm multiple users or devices are affected.', 'Collect URL, certificate details, network path, and screenshots.', 'Check whether certificate renewal or deployment recently occurred.', 'Escalate to Systems/Web App/Network team.', 'Track resolution and notify users when safe.'],
        'admin': ['Escalate as certificate deployment issue with load balancer/server path, certificate details, affected scope, business impact, and renewal/deployment history if known.'],
    },
}

CERTIFICATE_SECURITY_WARNING_USER_DIAGNOSTIC_NODES = [
    ('ROOT_CERT_USER', None, 'category', 'Certificate / Security Warning', 'User-friendly diagnostic path for browser/application certificate and security warnings.', None, None, None, None, 1),
    ('Q_CERT_LINK_USER', 'ROOT_CERT_USER', 'question', 'Check Link Source', None, 'Did you open the site from an email, chat, or unexpected link?', None, None, None, 1),
    ('S_CERT_PHISH_USER', 'Q_CERT_LINK_USER', 'solution', 'Report Possible Phishing or Unsafe Link', None, None, 'Yes', 'Yes', 'FIX_CERT_WARNING_REPORT_PHISHING_LINK', 1),
    ('Q_CERT_CREDENTIALS_USER', 'Q_CERT_LINK_USER', 'question', 'Check Credential Exposure', None, 'Did you enter credentials or sensitive information?', 'No', 'No', None, 2),
    ('S_CERT_CREDS_USER', 'Q_CERT_CREDENTIALS_USER', 'solution', 'Report Possible Credential Exposure', None, None, 'Yes', 'Yes', 'FIX_CERT_WARNING_CREDENTIAL_EXPOSURE', 1),
    ('Q_CERT_SCOPE_USER', 'Q_CERT_CREDENTIALS_USER', 'question', 'Check Warning Scope', None, 'Is the warning for one site or many sites?', 'No', 'No', None, 2),
    ('S_CERT_TIME_USER', 'Q_CERT_SCOPE_USER', 'solution', 'Check Device Time, Network, or Trust Issue', None, None, 'Many sites', 'Many sites', 'FIX_CERT_WARNING_DEVICE_TIME_TRUST', 1),
    ('Q_CERT_INTERNAL_USER', 'Q_CERT_SCOPE_USER', 'question', 'Check Internal Site', None, 'Is this a company/internal site?', 'One site', 'One site', None, 2),
    ('S_CERT_INTERNAL_USER', 'Q_CERT_INTERNAL_USER', 'solution', 'Report Internal Site Certificate Warning', None, None, 'Yes', 'Yes', 'FIX_CERT_WARNING_INTERNAL_SITE', 1),
    ('S_CERT_DONT_BYPASS_USER', 'Q_CERT_INTERNAL_USER', 'solution', 'Do Not Bypass Browser Security Warning', None, None, 'No / Not sure', 'No / Not sure', 'FIX_CERT_WARNING_DO_NOT_BYPASS', 2),
]

CERTIFICATE_SECURITY_WARNING_TECH_DIAGNOSTIC_NODES = [
    ('ROOT_CERT_TECH', None, 'category', 'Certificate / Security Warning - IT Support Specialist', 'IT Support Specialist diagnostic path for certificate, DNS, trust-store, proxy/TLS inspection, and security-risk issues.', None, None, None, None, 1),
    ('Q_CERT_SUSPICIOUS_TECH', 'ROOT_CERT_TECH', 'question', 'Check Suspicious Link Context', None, 'Is the link suspicious or phishing-related?', None, None, None, 1),
    ('S_CERT_SECURITY_TECH', 'Q_CERT_SUSPICIOUS_TECH', 'solution', 'Escalate Suspicious Certificate Warning to Security', None, None, 'Yes', 'Yes', 'FIX_CERT_WARNING_ESCALATE_SECURITY', 1),
    ('Q_CERT_DETAILS_TECH', 'Q_CERT_SUSPICIOUS_TECH', 'question', 'Check Certificate Details', None, 'Is the certificate expired, mismatched, or untrusted?', 'No', 'No', None, 2),
    ('S_CERT_VALIDATE_TECH', 'Q_CERT_DETAILS_TECH', 'solution', 'Validate Certificate Details and Route Owner', None, None, 'Yes', 'Yes', 'FIX_CERT_WARNING_VALIDATE_CERT_ROUTE_OWNER', 1),
    ('Q_CERT_DNS_TECH', 'Q_CERT_DETAILS_TECH', 'question', 'Check DNS Path', None, 'Does DNS resolve to expected address/path?', 'No / Not checked', 'No / Not checked', None, 2),
    ('S_CERT_DNS_TECH', 'Q_CERT_DNS_TECH', 'solution', 'Troubleshoot DNS or Network Path', None, None, 'No', 'No', 'FIX_CERT_WARNING_DNS_NETWORK_PATH', 1),
    ('Q_CERT_TRUST_TECH', 'Q_CERT_DNS_TECH', 'question', 'Check Device or Network Path', None, 'Does it happen only on one device/network/VPN/proxy?', 'Yes', 'Yes', None, 2),
    ('S_CERT_TLS_TECH', 'Q_CERT_TRUST_TECH', 'solution', 'Investigate Device Trust Store or TLS Inspection', None, None, 'Yes', 'Yes', 'FIX_CERT_WARNING_TRUST_TLS_INSPECTION', 1),
    ('S_CERT_DEPLOY_TECH', 'Q_CERT_TRUST_TECH', 'solution', 'Escalate Internal Site or Certificate Deployment Issue', None, None, 'No', 'No', 'FIX_CERT_WARNING_CERT_DEPLOYMENT_ESCALATE', 2),
]

def seed_certificate_security_warning_content(cursor):
    """Seed Certificate / Security Warning KB article, solutions, steps, and diagnostic trees."""
    code_, title, category, severity, description = CERTIFICATE_SECURITY_WARNING_PROBLEM
    cursor.execute("""
        INSERT INTO problem (problem_code, title, category, severity, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(problem_code) DO UPDATE SET
            title=excluded.title, category=excluded.category, severity=excluded.severity,
            description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, CERTIFICATE_SECURITY_WARNING_PROBLEM)
    cursor.execute('SELECT problem_id FROM problem WHERE problem_code = ?', (code_,))
    row = cursor.fetchone()
    if not row:
        return
    problem_id = row['problem_id']
    cursor.execute("""
        INSERT INTO kb_article (problem_id, title, summary, difficulty, estimated_time, escalation_required, escalation_notes, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, difficulty=excluded.difficulty,
            estimated_time=excluded.estimated_time, escalation_required=excluded.escalation_required,
            escalation_notes=excluded.escalation_notes, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, CERTIFICATE_SECURITY_WARNING_KB['title'], CERTIFICATE_SECURITY_WARNING_KB['summary'], CERTIFICATE_SECURITY_WARNING_KB['difficulty'], CERTIFICATE_SECURITY_WARNING_KB['estimated_time'], CERTIFICATE_SECURITY_WARNING_KB['escalation_required'], CERTIFICATE_SECURITY_WARNING_KB['escalation_notes']))
    cursor.execute('SELECT kb_article_id FROM kb_article WHERE problem_id = ?', (problem_id,))
    article = cursor.fetchone()
    if article:
        kb_id = article['kb_article_id']
        delete_kb_child_rows(cursor, kb_id)
        insert_kb_child_rows(cursor, 'kb_article_tag', 'tag', kb_id, CERTIFICATE_SECURITY_WARNING_KB['tags'])
        insert_kb_child_rows(cursor, 'kb_article_symptom', 'symptom', kb_id, CERTIFICATE_SECURITY_WARNING_KB['symptoms'])
        insert_kb_child_rows(cursor, 'kb_article_cause', 'cause', kb_id, CERTIFICATE_SECURITY_WARNING_KB['causes'])
        insert_kb_child_rows(cursor, 'kb_article_user_step', 'step_text', kb_id, CERTIFICATE_SECURITY_WARNING_KB['user_steps'])
        insert_kb_child_rows(cursor, 'kb_article_it_step', 'step_text', kb_id, CERTIFICATE_SECURITY_WARNING_KB['it_steps'])
    cursor.executemany("""
        INSERT INTO solution (solution_code, title, summary, resolution_steps, escalation_required, escalation_notes, priority_recommendation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(solution_code) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, resolution_steps=excluded.resolution_steps,
            escalation_required=excluded.escalation_required, escalation_notes=excluded.escalation_notes,
            priority_recommendation=excluded.priority_recommendation, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, CERTIFICATE_SECURITY_WARNING_SOLUTIONS)
    for solution_code, audience_steps in CERTIFICATE_SECURITY_WARNING_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue
        for audience, steps in audience_steps.items():
            cursor.execute('DELETE FROM solution_step WHERE solution_id = ? AND audience = ?', (solution_id, audience))
            cursor.executemany('INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)', [(solution_id, audience, step, idx) for idx, step in enumerate(steps, start=1)])
    seed_certificate_security_warning_tree(cursor, 'user', 'CERTIFICATE_SECURITY_WARNING_USER', 'Certificate / Security Warning - User Diagnostic', 'User-friendly diagnostic tree for certificate/security warnings, phishing-link context, and safe reporting.', CERTIFICATE_SECURITY_WARNING_USER_DIAGNOSTIC_NODES)
    seed_certificate_security_warning_tree(cursor, 'technician', 'CERTIFICATE_SECURITY_WARNING_TECHNICIAN', 'Certificate / Security Warning - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for certificate details, DNS, TLS inspection, and security escalation.', CERTIFICATE_SECURITY_WARNING_TECH_DIAGNOSTIC_NODES)

def seed_certificate_security_warning_tree(cursor, audience, tree_code, title, description, nodes):
    problem_id = get_problem_id_for_tree_code(cursor, 'CERTIFICATE_SECURITY_WARNING')
    cursor.execute("""
        INSERT INTO diagnostic_tree (problem_id, diagnostic_tree_code, base_tree_code, audience, title, description, is_active, updated_at)
        VALUES (?, ?, 'CERTIFICATE_SECURITY_WARNING', ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(diagnostic_tree_code) DO UPDATE SET
            problem_id=excluded.problem_id, base_tree_code=excluded.base_tree_code, audience=excluded.audience,
            title=excluded.title, description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, tree_code, audience, title, description))
    tree_id = get_diagnostic_tree_id_by_code(cursor, tree_code)
    if not tree_id:
        return
    cursor.execute('UPDATE diagnostic_node SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE diagnostic_tree_id = ?', (tree_id,))
    for node_key, parent_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_code, sort_order in nodes:
        parent_id = get_diagnostic_node_id_by_tree_and_key(cursor, tree_id, parent_key) if parent_key else None
        solution_id = get_solution_id_by_code(cursor, solution_code) if solution_code else None
        cursor.execute("""
            INSERT INTO diagnostic_node (
                diagnostic_tree_id, parent_diagnostic_node_id, problem_id, diagnostic_tree_code,
                node_key, node_type, title, description, prompt_text,
                condition_label, condition_value, solution_id, sort_order, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(diagnostic_tree_code, node_key) DO UPDATE SET
                diagnostic_tree_id=excluded.diagnostic_tree_id,
                parent_diagnostic_node_id=excluded.parent_diagnostic_node_id,
                problem_id=excluded.problem_id,
                node_type=excluded.node_type,
                title=excluded.title,
                description=excluded.description,
                prompt_text=excluded.prompt_text,
                condition_label=excluded.condition_label,
                condition_value=excluded.condition_value,
                solution_id=excluded.solution_id,
                sort_order=excluded.sort_order,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (tree_id, parent_id, problem_id, tree_code, node_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_id, sort_order))


# -----------------------------
# MOBILE EMAIL SETUP ISSUE CONTENT
# -----------------------------
MOBILE_EMAIL_SETUP_ISSUE_PROBLEM = (
    'MOBILE_EMAIL_SETUP_ISSUE',
    'Mobile Email Setup Issue',
    'Email, Calendar & Collaboration',
    'Medium',
    'The user cannot add or use their work email on a mobile phone or tablet.'
)

MOBILE_EMAIL_SETUP_ISSUE_KB = {
    'title': 'Mobile Email Setup Issue',
    'summary': 'Use this guide when work email cannot be added to a phone or tablet, mobile email keeps asking for sign-in, MFA does not complete, or email/calendar/contacts do not sync on mobile.',
    'difficulty': 'Intermediate',
    'estimated_time': '10-25 minutes',
    'escalation_required': 1,
    'escalation_notes': 'Escalate to Identity, Endpoint/Mobile Device Management, Email/Collaboration, or Security depending on whether the blocker is MFA, conditional access, device compliance, mailbox access, or suspicious sign-in activity.',
    'tags': ['mobile email', 'Outlook mobile', 'iOS email', 'Android email', 'MFA', 'device compliance', 'MDM', 'Intune', 'Exchange', 'Microsoft 365', 'calendar sync'],
    'symptoms': [
        'Cannot add work email to phone or tablet.',
        'Outlook mobile or email app repeatedly asks for sign-in.',
        'MFA prompt does not appear or cannot be completed during setup.',
        'Device shows compliance, management, enrollment, or organization-required message.',
        'Email works on desktop or web but not on mobile.',
        'Email syncs but calendar or contacts do not sync.',
        'Mobile email stopped working after password change, phone change, or app update.'
    ],
    'causes': [
        'Common causes include wrong account type, incorrect username, password or MFA failure, outdated app, missing app permissions, unsupported native mail app, device compliance requirements, MDM enrollment, conditional access policy, or mailbox/mobile sync settings.',
        'Advanced causes include conditional access failure, app protection policy issue, MDM/Intune enrollment failure, unsupported or non-compliant mobile OS, disabled mobile access, stale device partnership, token/session issue, mailbox license problem, or Microsoft 365/Exchange service issue.'
    ],
    'user_steps': [
        'Confirm the phone has internet access.',
        'Install or open the approved company email app, usually Outlook mobile if required.',
        'Enter your full company email address.',
        'Sign in with your current company password.',
        'Approve the MFA prompt only if you initiated the sign-in.',
        'Allow required app permissions for email, calendar, contacts, and notifications if company policy allows.',
        'If prompted, complete device enrollment or compliance steps.',
        'Restart the mobile app and try again.',
        'If you recently changed your password, update the password or remove/re-add the account only if IT instructs you.',
        'Submit a ticket with the phone type, app name, error message, and screenshot.'
    ],
    'it_steps': [
        'Confirm the user, phone type, mobile OS version, email app, account, and exact error message.',
        'Confirm whether email works in Outlook web or desktop Outlook.',
        'Identify whether this is first-time setup, new phone migration, password change, MFA issue, calendar/contact sync issue, or compliance/enrollment issue.',
        'Confirm the user is using the approved app and correct account type.',
        'Confirm internet connectivity on the phone.',
        'Check whether the user receives and approves MFA.',
        'Check for account locked, password expired, or MFA problem.',
        'Confirm app permissions for mail, calendar, contacts, and notifications as appropriate.',
        'Ask the user to update the mobile app and restart it.',
        'Capture screenshots, phone model, OS version, app version, error text, and time of failure.',
        'Check sign-in logs or authentication failure reason if available.',
        'Check whether conditional access, device compliance, or app protection policy blocked the sign-in.',
        'Check whether the device is enrolled if company policy requires enrollment.',
        'Check MDM/Intune compliance state where applicable.',
        'Check whether the user has required mailbox, license, or service access.',
        'Check whether mobile access or Exchange ActiveSync is disabled for the mailbox if applicable.',
        'Check whether stale mobile device partnerships or tokens need cleanup according to policy.',
        'Compare Outlook mobile versus native mail app behavior if policy allows.',
        'Check whether the issue follows the user, device, app, or network.',
        'Escalate with username, device model, OS/app version, error screenshot, sign-in result, policy result, compliance state, and steps already completed.'
    ]
}

MOBILE_EMAIL_SETUP_ISSUE_SOLUTIONS = [
    ('FIX_MOBILE_EMAIL_APPROVED_APP', 'Use Approved Mobile Email App', 'The organization may require a specific app, such as Outlook mobile, for work email.', 'Use the approved mobile email app and correct work account.', 0, 'Escalate only if approved app install or access is blocked by policy.', 'medium'),
    ('FIX_MOBILE_EMAIL_MFA_SETUP', 'Resolve MFA During Mobile Email Setup', 'Mobile email setup may fail if MFA prompt is missed, blocked, or unavailable.', 'Confirm MFA works and route to MFA troubleshooting if needed.', 1, 'Escalate to Identity if MFA method is unavailable or conditional access blocks setup.', 'medium'),
    ('FIX_MOBILE_EMAIL_DEVICE_ENROLLMENT', 'Complete Device Enrollment or Compliance Steps', 'Company policy may require the phone to be enrolled, managed, or compliant before email access is allowed.', 'Complete approved enrollment and compliance requirements.', 1, 'Escalate to Endpoint/Mobile Device Management if compliance or enrollment does not update.', 'medium'),
    ('FIX_MOBILE_EMAIL_SYNC_PERMISSIONS', 'Troubleshoot Mobile App Sync or Permissions', 'Email works elsewhere but mobile app permissions, cache, or sync settings may be blocking mobile access.', 'Check app permissions, sync settings, update state, and mobile app behavior.', 0, 'Escalate if app policy or mobile management controls sync.', 'medium'),
    ('FIX_MOBILE_EMAIL_ACCOUNT_MAILBOX_ACCESS', 'Check Account, Password, or Mailbox Access', 'Mobile setup may fail because the account, password, license, or mailbox access has a problem.', 'Check account state, password, MFA, and mailbox access.', 1, 'Escalate to Identity or Email/Collaboration if account or mailbox access is blocked.', 'high'),
    ('FIX_MOBILE_EMAIL_AUTH_ACCOUNT_STATE', 'Troubleshoot Mobile Sign-In, MFA, or Account State', 'Authentication failure may be caused by password, account lockout, MFA, conditional access, or risk policy.', 'Review authentication failure reason and account state.', 1, 'Escalate to Identity/Security if blocked by policy or suspicious activity.', 'high'),
    ('FIX_MOBILE_EMAIL_ENROLLMENT_COMPLIANCE', 'Troubleshoot Mobile Device Enrollment or Compliance', 'Mobile access is blocked because device management or compliance requirements are not met.', 'Review enrollment and compliance state.', 1, 'Escalate to Endpoint/MDM team if compliance remains blocked.', 'high'),
    ('FIX_MOBILE_EMAIL_APP_CACHE_SYNC', 'Troubleshoot Mobile App Sync, Permissions, or Cache', 'Mobile app setup completes, but mail/calendar/contacts do not sync correctly.', 'Compare mobile, web, and desktop behavior and verify permissions/sync scope.', 1, 'Escalate if mailbox or mobile policy issue is suspected.', 'medium'),
    ('FIX_MOBILE_EMAIL_MAILBOX_SERVICE_ESCALATE', 'Escalate Mailbox or Service Access Issue', 'Email does not work on web/desktop either, so the issue is not mobile-specific.', 'Confirm broader mailbox/service problem and escalate with evidence.', 1, 'Escalate to Email/Collaboration Admin or Microsoft 365 support path with evidence.', 'high'),
]

MOBILE_EMAIL_SETUP_ISSUE_SOLUTION_STEPS = {
    'FIX_MOBILE_EMAIL_APPROVED_APP': {
        'user': ['Install or open the approved company email app.', 'Enter your full company email address.', 'Sign in with your work account.', 'Approve MFA only if you initiated setup.', 'Allow required permissions if prompted.'],
        'technician': ['Confirm the company-approved mobile email app.', 'Confirm the user is using the correct account type.', 'Guide the user through setup.', 'Document phone type, app version, and setup result.'],
        'admin': ['Escalate only if app availability, policy assignment, or approved app deployment is blocked.']
    },
    'FIX_MOBILE_EMAIL_MFA_SETUP': {
        'user': ['Keep the authenticator app or phone available.', 'Retry setup and watch for the MFA prompt.', 'Do not approve prompts you did not initiate.', 'Contact IT if your MFA method is unavailable.'],
        'technician': ['Confirm whether MFA prompt is sent and completed.', 'Check whether the user can complete MFA elsewhere.', 'Route to MFA troubleshooting if method is unavailable.', 'Escalate if conditional access or MFA policy blocks setup.'],
        'admin': ['Identity handoff: include user, sign-in timestamp, MFA method, failure message, and whether other sign-ins work.']
    },
    'FIX_MOBILE_EMAIL_DEVICE_ENROLLMENT': {
        'user': ['Follow the company enrollment instructions.', 'Keep the device connected to the internet.', 'Set required passcode, encryption, or security settings if prompted.', 'Contact IT if enrollment fails.'],
        'technician': ['Confirm whether device enrollment/compliance is required.', 'Check enrollment status if available.', 'Confirm required OS version, passcode, encryption, and app protection settings.', 'Escalate to MDM/Endpoint team if compliance does not update.'],
        'admin': ['Endpoint/MDM handoff: include device model, OS version, enrollment state, compliance error, assigned policies, and user impact.']
    },
    'FIX_MOBILE_EMAIL_SYNC_PERMISSIONS': {
        'user': ['Confirm the phone has internet access.', 'Restart the mobile email app.', 'Check that notifications, calendar, and contacts permissions are enabled if needed.', 'Update the app.', 'Report whether only email or also calendar/contacts fail.'],
        'technician': ['Confirm web/desktop email works.', 'Check mobile app version and permissions.', 'Check whether sync is enabled for mail/calendar/contacts.', 'Remove/re-add account only if policy allows.', 'Escalate if app policy or mobile management controls sync.'],
        'admin': ['Mobile/Endpoint handoff: include app version, sync scope, permission state, and whether web/desktop email works.']
    },
    'FIX_MOBILE_EMAIL_ACCOUNT_MAILBOX_ACCESS': {
        'user': ['Confirm you can sign in to Outlook web or your computer.', 'Use your current company password.', 'Tell IT if you recently changed your password or got locked out.', 'Avoid repeated failed attempts.'],
        'technician': ['Check account locked, password expired, disabled, or MFA issue.', 'Confirm mailbox/license/service access.', 'Confirm the user can sign in to web/desktop email.', 'Route to Password Reset, Account Locked, MFA, or mailbox support as needed.'],
        'admin': ['Identity/Email handoff: include account state, license/mailbox status, sign-in result, and whether web/desktop access works.']
    },
    'FIX_MOBILE_EMAIL_AUTH_ACCOUNT_STATE': {
        'user': ['Stop retrying if sign-in keeps failing.', 'Report the exact error message.', 'Do not approve unexpected MFA prompts.', 'Follow IT instructions for password or MFA reset if needed.'],
        'technician': ['Check sign-in logs or authentication failure reason if available.', 'Check account status, password expiration, and MFA state.', 'Check conditional access or risk policy result.', 'Escalate to Identity/Security if blocked by policy or suspicious activity.'],
        'admin': ['Escalate to Identity/Security with sign-in log result, conditional access result, risk status, MFA status, and timestamp.']
    },
    'FIX_MOBILE_EMAIL_ENROLLMENT_COMPLIANCE': {
        'user': ['Follow company device enrollment prompts.', 'Apply required security settings.', 'Keep the device online.', 'Send IT the compliance/enrollment error screenshot.'],
        'technician': ['Check device enrollment state.', 'Check MDM/Intune compliance state where applicable.', 'Check compliance errors such as OS version, passcode, encryption, jailbreak/root detection, or app protection policy.', 'Confirm the user/device is assigned to the correct policy.', 'Escalate to Endpoint/MDM team if compliance remains blocked.'],
        'admin': ['Endpoint/MDM handoff: include compliance state, policy assignment, enrollment error, OS version, and remediation attempted.']
    },
    'FIX_MOBILE_EMAIL_APP_CACHE_SYNC': {
        'user': ['Confirm internet works.', 'Restart the app and phone.', 'Update the email app.', 'Check calendar/contact permissions.', 'Tell IT whether web/desktop email works.'],
        'technician': ['Compare mobile, web, and desktop behavior.', 'Check app permissions and sync scope.', 'Clear app cache or re-add account only if policy allows.', 'Check mobile app protection/management policy.', 'Escalate if mailbox or mobile policy issue is suspected.'],
        'admin': ['Email/Mobile handoff: include client comparison, app version, permission state, policy result, and affected sync type.']
    },
    'FIX_MOBILE_EMAIL_MAILBOX_SERVICE_ESCALATE': {
        'user': ['Report whether email fails on all devices.', 'Provide screenshots from web/desktop/mobile.', 'Wait for IT to verify mailbox access.'],
        'technician': ['Confirm issue affects web/desktop/mobile.', 'Check mailbox/license/service status.', 'Check whether multiple users are affected.', 'Escalate to Email/Collaboration Admin or Microsoft 365 support path with evidence.'],
        'admin': ['Email/Collaboration handoff: include mailbox status, service health, affected users, screenshots, and client comparison.']
    }
}

MOBILE_EMAIL_SETUP_ISSUE_USER_DIAGNOSTIC_NODES = [
    ('ROOT', None, 'question', 'Mobile Email Setup Issue', 'Start here when work email cannot be added or used on a phone/tablet.', 'Are you using the approved company email app?', None, None, None, 1),
    ('APP_NO', 'ROOT', 'solution', 'Use Approved Mobile Email App', 'Use the approved company mobile email application and account type.', None, 'No / Not sure', 'no', 'FIX_MOBILE_EMAIL_APPROVED_APP', 1),
    ('MFA_Q', 'ROOT', 'question', 'MFA During Setup', 'Check whether MFA prompt is being received and approved.', 'Do you receive and approve the MFA prompt during setup?', 'Yes', 'yes', None, 2),
    ('MFA_NO', 'MFA_Q', 'solution', 'Resolve MFA During Mobile Email Setup', 'MFA may be unavailable, missed, or blocked.', None, 'No', 'no', 'FIX_MOBILE_EMAIL_MFA_SETUP', 1),
    ('ENROLL_Q', 'MFA_Q', 'question', 'Enrollment or Compliance Prompt', 'Check for device management or compliance requirement.', 'Does setup mention device compliance, management, or enrollment?', 'Yes', 'yes', None, 2),
    ('ENROLL_YES', 'ENROLL_Q', 'solution', 'Complete Device Enrollment or Compliance Steps', 'Device must meet company policy before mobile email works.', None, 'Yes', 'yes', 'FIX_MOBILE_EMAIL_DEVICE_ENROLLMENT', 1),
    ('WEB_Q', 'ENROLL_Q', 'question', 'Web or Desktop Email Works', 'Determine whether the problem is mobile-specific.', 'Does email work on Outlook web or your computer?', 'No', 'no', None, 2),
    ('WEB_YES', 'WEB_Q', 'solution', 'Troubleshoot Mobile App Sync or Permissions', 'Web/desktop works, so focus on mobile app sync and permissions.', None, 'Yes', 'yes', 'FIX_MOBILE_EMAIL_SYNC_PERMISSIONS', 1),
    ('WEB_NO', 'WEB_Q', 'solution', 'Check Account, Password, or Mailbox Access', 'Email fails beyond mobile, so account or mailbox access may be affected.', None, 'No / Not sure', 'no', 'FIX_MOBILE_EMAIL_ACCOUNT_MAILBOX_ACCESS', 2),
]

MOBILE_EMAIL_SETUP_ISSUE_TECH_DIAGNOSTIC_NODES = [
    ('ROOT', None, 'question', 'Mobile Email Setup Issue - IT Support Specialist', 'Start here for mobile email setup, MFA, enrollment, compliance, and mailbox access.', 'Is the failure authentication or MFA-related?', None, None, None, 1),
    ('AUTH_YES', 'ROOT', 'solution', 'Troubleshoot Mobile Sign-In, MFA, or Account State', 'Authentication, MFA, conditional access, or account state may block setup.', None, 'Yes', 'yes', 'FIX_MOBILE_EMAIL_AUTH_ACCOUNT_STATE', 1),
    ('ENROLL_Q', 'ROOT', 'question', 'Enrollment or Compliance Required', 'Check whether device management or compliance is required.', 'Is device enrollment or compliance required?', 'No', 'no', None, 2),
    ('ENROLL_YES', 'ENROLL_Q', 'solution', 'Troubleshoot Mobile Device Enrollment or Compliance', 'Mobile access is blocked by enrollment or compliance requirements.', None, 'Yes', 'yes', 'FIX_MOBILE_EMAIL_ENROLLMENT_COMPLIANCE', 1),
    ('WEB_Q', 'ENROLL_Q', 'question', 'Web/Desktop Email Works', 'Determine whether issue is mobile-only or mailbox-wide.', 'Does Outlook web or desktop work for the user?', 'No / Not sure', 'no', None, 2),
    ('WEB_YES', 'WEB_Q', 'solution', 'Troubleshoot Mobile App Sync, Permissions, or Cache', 'Mailbox works elsewhere, so isolate mobile app sync, cache, or permission problem.', None, 'Yes', 'yes', 'FIX_MOBILE_EMAIL_APP_CACHE_SYNC', 1),
    ('WEB_NO', 'WEB_Q', 'solution', 'Escalate Mailbox or Service Access Issue', 'Email fails beyond mobile, indicating mailbox/service/account issue.', None, 'No', 'no', 'FIX_MOBILE_EMAIL_MAILBOX_SERVICE_ESCALATE', 2),
]

def seed_mobile_email_setup_issue_content(cursor):
    """Seed Mobile Email Setup Issue KB article, solutions, steps, and diagnostic trees."""
    code_, title, category, severity, description = MOBILE_EMAIL_SETUP_ISSUE_PROBLEM
    cursor.execute("""
        INSERT INTO problem (problem_code, title, category, severity, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(problem_code) DO UPDATE SET
            title=excluded.title, category=excluded.category, severity=excluded.severity,
            description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, MOBILE_EMAIL_SETUP_ISSUE_PROBLEM)
    cursor.execute('SELECT problem_id FROM problem WHERE problem_code = ?', (code_,))
    row = cursor.fetchone()
    if not row:
        return
    problem_id = row['problem_id']
    cursor.execute("""
        INSERT INTO kb_article (problem_id, title, summary, difficulty, estimated_time, escalation_required, escalation_notes, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, difficulty=excluded.difficulty,
            estimated_time=excluded.estimated_time, escalation_required=excluded.escalation_required,
            escalation_notes=excluded.escalation_notes, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, MOBILE_EMAIL_SETUP_ISSUE_KB['title'], MOBILE_EMAIL_SETUP_ISSUE_KB['summary'], MOBILE_EMAIL_SETUP_ISSUE_KB['difficulty'], MOBILE_EMAIL_SETUP_ISSUE_KB['estimated_time'], MOBILE_EMAIL_SETUP_ISSUE_KB['escalation_required'], MOBILE_EMAIL_SETUP_ISSUE_KB['escalation_notes']))
    cursor.execute('SELECT kb_article_id FROM kb_article WHERE problem_id = ?', (problem_id,))
    article = cursor.fetchone()
    if article:
        kb_id = article['kb_article_id']
        delete_kb_child_rows(cursor, kb_id)
        insert_kb_child_rows(cursor, 'kb_article_tag', 'tag', kb_id, MOBILE_EMAIL_SETUP_ISSUE_KB['tags'])
        insert_kb_child_rows(cursor, 'kb_article_symptom', 'symptom', kb_id, MOBILE_EMAIL_SETUP_ISSUE_KB['symptoms'])
        insert_kb_child_rows(cursor, 'kb_article_cause', 'cause', kb_id, MOBILE_EMAIL_SETUP_ISSUE_KB['causes'])
        insert_kb_child_rows(cursor, 'kb_article_user_step', 'step_text', kb_id, MOBILE_EMAIL_SETUP_ISSUE_KB['user_steps'])
        insert_kb_child_rows(cursor, 'kb_article_it_step', 'step_text', kb_id, MOBILE_EMAIL_SETUP_ISSUE_KB['it_steps'])
    cursor.executemany("""
        INSERT INTO solution (solution_code, title, summary, resolution_steps, escalation_required, escalation_notes, priority_recommendation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(solution_code) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, resolution_steps=excluded.resolution_steps,
            escalation_required=excluded.escalation_required, escalation_notes=excluded.escalation_notes,
            priority_recommendation=excluded.priority_recommendation, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, MOBILE_EMAIL_SETUP_ISSUE_SOLUTIONS)
    for solution_code, audience_steps in MOBILE_EMAIL_SETUP_ISSUE_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue
        for audience, steps in audience_steps.items():
            cursor.execute('DELETE FROM solution_step WHERE solution_id = ? AND audience = ?', (solution_id, audience))
            cursor.executemany('INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)', [(solution_id, audience, step, idx) for idx, step in enumerate(steps, start=1)])
    seed_mobile_email_setup_tree(cursor, 'user', 'MOBILE_EMAIL_SETUP_ISSUE_USER', 'Mobile Email Setup Issue - User Diagnostic', 'User-friendly diagnostic tree for mobile email setup, MFA, app, and compliance issues.', MOBILE_EMAIL_SETUP_ISSUE_USER_DIAGNOSTIC_NODES)
    seed_mobile_email_setup_tree(cursor, 'technician', 'MOBILE_EMAIL_SETUP_ISSUE_TECHNICIAN', 'Mobile Email Setup Issue - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for mobile sign-in, MFA, enrollment, compliance, and mailbox access issues.', MOBILE_EMAIL_SETUP_ISSUE_TECH_DIAGNOSTIC_NODES)

def seed_mobile_email_setup_tree(cursor, audience, tree_code, title, description, nodes):
    problem_id = get_problem_id_for_tree_code(cursor, 'MOBILE_EMAIL_SETUP_ISSUE')
    cursor.execute("""
        INSERT INTO diagnostic_tree (problem_id, diagnostic_tree_code, base_tree_code, audience, title, description, is_active, updated_at)
        VALUES (?, ?, 'MOBILE_EMAIL_SETUP_ISSUE', ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(diagnostic_tree_code) DO UPDATE SET
            problem_id=excluded.problem_id, base_tree_code=excluded.base_tree_code, audience=excluded.audience,
            title=excluded.title, description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, tree_code, audience, title, description))
    tree_id = get_diagnostic_tree_id_by_code(cursor, tree_code)
    if not tree_id:
        return
    cursor.execute('UPDATE diagnostic_node SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE diagnostic_tree_id = ?', (tree_id,))
    for node_key, parent_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_code, sort_order in nodes:
        parent_id = get_diagnostic_node_id_by_tree_and_key(cursor, tree_id, parent_key) if parent_key else None
        solution_id = get_solution_id_by_code(cursor, solution_code) if solution_code else None
        cursor.execute("""
            INSERT INTO diagnostic_node (
                diagnostic_tree_id, parent_diagnostic_node_id, problem_id, diagnostic_tree_code,
                node_key, node_type, title, description, prompt_text,
                condition_label, condition_value, solution_id, sort_order, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(diagnostic_tree_code, node_key) DO UPDATE SET
                diagnostic_tree_id=excluded.diagnostic_tree_id,
                parent_diagnostic_node_id=excluded.parent_diagnostic_node_id,
                problem_id=excluded.problem_id,
                node_type=excluded.node_type,
                title=excluded.title,
                description=excluded.description,
                prompt_text=excluded.prompt_text,
                condition_label=excluded.condition_label,
                condition_value=excluded.condition_value,
                solution_id=excluded.solution_id,
                sort_order=excluded.sort_order,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (tree_id, parent_id, problem_id, tree_code, node_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_id, sort_order))



# -----------------------------
# VIDEO CONFERENCING ISSUE CONTENT
# -----------------------------
VIDEO_CONFERENCING_ISSUE_PROBLEM = (
    'VIDEO_CONFERENCING_ISSUE',
    'Video Conferencing Issue',
    'Email, Calendar & Collaboration',
    'Medium',
    'The user has trouble joining, hearing, speaking, using camera, sharing screen, or staying connected during a video meeting.'
)

VIDEO_CONFERENCING_ISSUE_KB = {
    'title': 'Video Conferencing Issue',
    'summary': 'Use this guide when Teams, Zoom, Google Meet, or another meeting app has microphone, speaker, camera, screen sharing, join, lag, or disconnect problems.',
    'difficulty': 'Intermediate',
    'estimated_time': '5-20 minutes',
    'escalation_required': 1,
    'escalation_notes': 'Escalate to Endpoint/Desktop, Network, Collaboration/Microsoft 365/Zoom Admin, or Security depending on whether the issue is device detection, network quality, meeting policy, service health, or suspicious meeting-link behavior.',
    'tags': ['video conferencing', 'Teams', 'Zoom', 'Google Meet', 'microphone', 'camera', 'speaker', 'screen sharing', 'meeting lag', 'Wi-Fi', 'VPN'],
    'symptoms': [
        'Cannot join a video meeting or meeting link fails.',
        'No microphone input, no speaker audio, echo, or others cannot hear the user.',
        'Camera is not detected, blocked, physically covered, or selected incorrectly.',
        'Screen sharing does not work or is blocked by app, browser, operating system, or meeting policy.',
        'Meeting lags, freezes, disconnects, or has poor audio/video quality.',
        'Issue works in one meeting app, browser, or device but not another.',
        'Multiple users have the same meeting-platform or call-quality issue.'
    ],
    'causes': [
        'Common causes include wrong audio/video device selection, mute settings, disconnected headset/camera, blocked OS or browser permissions, another app using the device, outdated meeting app, poor Wi-Fi, VPN/proxy/firewall restrictions, driver problems, or meeting-service issues.',
        'Advanced causes include endpoint security or device policy blocking camera/microphone, USB dock or firmware issues, packet loss/jitter/latency, DNS or firewall blocks to meeting media endpoints, corrupted app cache/profile, conflicting virtual audio/video drivers, conditional access, or meeting policy restrictions.'
    ],
    'user_steps': [
        'Check that you are not muted in the meeting app.',
        'Confirm your headset, microphone, speakers, and camera are connected.',
        'In the meeting app, select the correct microphone, speaker, and camera.',
        'Test audio/video before joining if the app provides a test option.',
        'Close other apps that may be using the camera or microphone.',
        'Restart the meeting app.',
        'Try joining from another approved browser or the desktop app.',
        'Move closer to Wi-Fi or switch to wired Ethernet if available.',
        'Disconnect from VPN only if company policy allows and the meeting does not require VPN.',
        'Take a screenshot of any error message and submit a ticket if the issue continues.'
    ],
    'it_steps': [
        'Confirm the user, device name, meeting app, app version, meeting type, network type, VPN status, and exact symptom.',
        'Identify whether the issue is join/access, no microphone, no speaker/audio output, no camera, screen sharing failure, or poor quality/disconnects.',
        'Confirm the correct microphone, speaker, and camera are selected in the meeting app.',
        'Check whether the user is muted in the app or operating system sound settings.',
        'Confirm headset/camera physical connection, USB/Bluetooth status, and battery level.',
        'Confirm OS privacy permissions for microphone and camera.',
        'Check browser site permissions if the user is joining from the web client.',
        'Close other apps that may be using camera or microphone.',
        'Restart the meeting app and retest.',
        'Test with another approved meeting app, browser, or built-in/external device if appropriate.',
        'Check whether the issue follows the user, device, meeting app, headset/camera, or network.',
        'Check Device Manager or system settings for camera/audio device status.',
        'Update or reinstall the meeting app from approved source if needed.',
        'Check camera/audio drivers, headset firmware, or USB dock/hub behavior if available.',
        'Check network quality such as Wi-Fi signal, latency, packet loss, jitter, and bandwidth.',
        'Compare behavior on office network, home Wi-Fi, hotspot, wired Ethernet, and VPN where appropriate.',
        'Check whether firewall, proxy, VPN, or web filtering may block meeting media traffic.',
        'Check service health/status if multiple users are affected.',
        'Escalate with meeting app, version, device model, selected devices, network tests, error screenshots, affected scope, and troubleshooting already completed.'
    ]
}

VIDEO_CONFERENCING_ISSUE_SOLUTIONS = [
    ('FIX_VIDEO_CONF_AUDIO_DEVICE_MUTE', 'Check Meeting Audio Device and Mute Settings', 'Audio problems are often caused by mute status, wrong device selection, or headset connection.', 'Check mute/device selection and test audio.', 0, 'Escalate to Endpoint/Desktop if OS audio device detection, driver, headset, or hardware issue persists.', 'medium'),
    ('FIX_VIDEO_CONF_CAMERA_PERMISSIONS', 'Check Camera Device and Permissions', 'Camera problems are often caused by blocked permissions, wrong camera selection, or another app using the camera.', 'Check camera device selection, OS/browser permissions, and app conflicts.', 0, 'Escalate to Endpoint/Desktop if the OS does not detect the camera, policy blocks camera access, or driver/hardware issue is suspected.', 'medium'),
    ('FIX_VIDEO_CONF_JOIN_ACCESS', 'Check Meeting Link, Account, and App Access', 'Join failures may be caused by wrong account, expired link, app version, license, or meeting policy.', 'Check link, account, app/browser path, and meeting policy.', 1, 'Escalate to Collaboration Admin if meeting policy, external/guest access, license, or service issue blocks joining.', 'medium'),
    ('FIX_VIDEO_CONF_SCREEN_SHARE_PERMISSION', 'Check Screen Sharing Permission', 'Screen sharing can fail because app, OS, browser, or meeting policy blocks sharing.', 'Check host policy, OS/browser permissions, and sharing mode.', 1, 'Escalate to Collaboration or Endpoint if screen sharing is blocked by policy, OS permission, browser restriction, or managed app setting.', 'medium'),
    ('FIX_VIDEO_CONF_NETWORK_QUALITY_USER', 'Improve Network Connection for Meeting', 'Meeting lag or disconnects are often caused by Wi-Fi, bandwidth, VPN, latency, packet loss, or jitter.', 'Improve network path and reduce bandwidth use.', 0, 'Escalate to Network if quality issues persist across users, sites, VLANs, VPN paths, or show latency/packet-loss patterns.', 'medium'),
    ('FIX_VIDEO_CONF_OS_DEVICE_PRIVACY', 'Troubleshoot OS Device Detection and Privacy Permissions', 'Meeting app cannot use camera/microphone because OS does not detect device or permissions are blocked.', 'Check OS device detection, permissions, and approved drivers.', 1, 'Escalate to Endpoint/Desktop if hardware, driver, firmware, USB dock, or managed privacy policy issue is suspected.', 'high'),
    ('FIX_VIDEO_CONF_APP_DEVICE_SELECTION', 'Troubleshoot Meeting App Device Selection', 'OS detects the device, but the meeting app is using the wrong audio/video device.', 'Adjust meeting app device settings and compare app behavior.', 0, 'Escalate to Collaboration or Endpoint if app cache, profile, repair, or policy issue persists after device selection checks.', 'medium'),
    ('FIX_VIDEO_CONF_NETWORK_QUALITY_TECH', 'Troubleshoot Meeting Network Quality', 'Poor quality may require network-path testing and isolation.', 'Check Wi-Fi, VPN, latency, packet loss, jitter, and bandwidth.', 1, 'Escalate to Network or Collaboration with network test results, affected users, meeting platform, timestamps, and scope.', 'high'),
    ('FIX_VIDEO_CONF_ESCALATE_SERVICE_NETWORK', 'Escalate Collaboration Service or Network Issue', 'Multiple users affected may indicate meeting-platform service, network, or policy problem.', 'Confirm affected scope and escalate with evidence.', 1, 'Escalate to Collaboration, Network, or Systems team depending on whether service health, site/VPN path, or policy is suspected.', 'high'),
    ('FIX_VIDEO_CONF_POLICY_ACCOUNT_CACHE', 'Check Meeting Policy, Account, or App Cache', 'Access or app behavior may be affected by account, meeting policy, cache, or corrupted local app state.', 'Check account/license/policy and app cache or profile.', 1, 'Escalate to Collaboration Admin if tenant policy, license, guest/external access, or meeting setting is involved.', 'medium')
]

VIDEO_CONFERENCING_ISSUE_SOLUTION_STEPS = {
    'FIX_VIDEO_CONF_AUDIO_DEVICE_MUTE': {
        'user': ['Check that you are not muted in the meeting.', 'Select the correct microphone and speaker in meeting settings.', 'Check headset battery or cable connection.', 'Try disconnecting and reconnecting the headset.', 'Run the app audio test if available.'],
        'technician': ['Confirm selected microphone and speaker in meeting app.', 'Check OS sound input/output settings.', 'Confirm the app is not muted in volume mixer.', 'Test built-in audio versus headset.', 'Check Bluetooth pairing or USB connection.'],
        'admin': ['Escalation notes: involve Endpoint/Desktop if the audio device is not detected by the OS, driver/firmware issue is suspected, or a managed policy blocks audio.']
    },
    'FIX_VIDEO_CONF_CAMERA_PERMISSIONS': {
        'user': ['Confirm the camera is not physically covered.', 'Select the correct camera in meeting settings.', 'Close other apps that may use the camera.', 'Restart the meeting app.', 'Try the browser or desktop app alternative.'],
        'technician': ['Confirm OS detects the camera.', 'Check OS camera privacy permissions.', 'Check browser site permissions if using web meeting.', 'Test built-in versus external camera.', 'Check whether another process is using the camera.'],
        'admin': ['Escalation notes: involve Endpoint/Desktop or Security if camera access is blocked by managed policy, endpoint security, driver failure, or hardware issue.']
    },
    'FIX_VIDEO_CONF_JOIN_ACCESS': {
        'user': ['Confirm you are using the correct meeting link.', 'Sign in with your work account if required.', 'Try joining from the browser if desktop app fails.', 'Take a screenshot of the join error.'],
        'technician': ['Confirm meeting link and meeting platform.', 'Check user account/license if needed.', 'Check whether external/guest access or meeting policy blocks joining.', 'Test browser versus desktop app.', 'Escalate if policy or service issue is suspected.'],
        'admin': ['Escalation notes: provide meeting platform, meeting URL, user account, guest/external status, license state, error message, timestamp, and policy result to Collaboration Admin.']
    },
    'FIX_VIDEO_CONF_SCREEN_SHARE_PERMISSION': {
        'user': ['Confirm the host allows screen sharing.', 'Restart the meeting app.', 'Try sharing one window instead of the full screen.', 'Report any permission prompt or error.'],
        'technician': ['Check meeting policy and host permissions.', 'Check OS screen recording or screen sharing permission where applicable.', 'Check browser permissions if using web meeting.', 'Test desktop app versus browser.', 'Escalate to Collaboration admin if policy blocks sharing.'],
        'admin': ['Escalation notes: include meeting policy, host role, user account, OS/browser permission state, app version, and screenshot when handing off.']
    },
    'FIX_VIDEO_CONF_NETWORK_QUALITY_USER': {
        'user': ['Move closer to Wi-Fi or use wired Ethernet if available.', 'Close streaming or large downloads during the meeting.', 'Turn off video temporarily if bandwidth is poor.', 'Try reconnecting from a stable network.', 'Disconnect VPN only if company policy allows and the meeting does not require it.'],
        'technician': ['Confirm network type and VPN status.', 'Compare behavior on Wi-Fi, wired, hotspot, and VPN where appropriate.', 'Check basic latency, packet loss, jitter, and bandwidth where tools allow.', 'Determine whether issue is local network, VPN path, or meeting service.', 'Escalate with network test results and affected scope.'],
        'admin': ['Escalation notes: escalate to Network if packet loss, jitter, latency, Wi-Fi coverage, VPN media path, proxy, firewall, or site-wide quality issue is suspected.']
    },
    'FIX_VIDEO_CONF_OS_DEVICE_PRIVACY': {
        'user': ['Reconnect the headset or camera.', 'Restart the computer.', 'Tell IT if the device works in other apps.', 'Do not install drivers from unapproved websites.'],
        'technician': ['Check Device Manager or system settings for camera/audio device.', 'Check microphone/camera privacy permissions.', 'Check driver status and approved updates.', 'Test a known-good headset/camera.', 'Escalate if hardware, driver, or policy issue is suspected.'],
        'admin': ['Escalation notes: provide device model, peripheral model, driver status, OS privacy settings, dock/hub status, and known-good test result to Endpoint/Desktop.']
    },
    'FIX_VIDEO_CONF_APP_DEVICE_SELECTION': {
        'user': ['Open meeting app settings.', 'Select the correct microphone, speaker, and camera.', 'Run a test call if available.', 'Restart the app if the device list does not update.'],
        'technician': ['Confirm OS detects the device.', 'Confirm meeting app selected devices.', 'Clear or reset app device settings if available.', 'Update or repair meeting app if needed.', 'Compare Teams, Zoom, and browser behavior.'],
        'admin': ['Escalation notes: involve Collaboration or Endpoint if the app profile/cache, policy, or app install is preventing correct device selection.']
    },
    'FIX_VIDEO_CONF_NETWORK_QUALITY_TECH': {
        'user': ['Report whether the issue happens on Wi-Fi, VPN, or all networks.', 'Note whether audio, video, or screen sharing is affected.', 'Capture time of poor quality or disconnect.'],
        'technician': ['Check Wi-Fi signal and network type.', 'Compare on alternate trusted network.', 'Test latency, packet loss, jitter, and bandwidth where tools allow.', 'Check whether firewall, proxy, VPN, or web filtering may block meeting media traffic.', 'Escalate to Network/Collaboration team if multiple users or network path issue is suspected.'],
        'admin': ['Escalation notes: include network path, VPN status, public/office location, packet loss/jitter/latency, meeting platform, affected users, and timestamps.']
    },
    'FIX_VIDEO_CONF_ESCALATE_SERVICE_NETWORK': {
        'user': ['Report meeting time, platform, and error.', 'Ask whether coworkers are affected.', 'Use phone dial-in or alternate meeting method if available.'],
        'technician': ['Confirm affected users, locations, and meeting platform.', 'Check service health/status if available.', 'Check network or firewall impact if users share a site/VPN.', 'Escalate to Collaboration or Network team with evidence.', 'Document workaround and user impact.'],
        'admin': ['Escalation notes: hand off meeting platform, tenant/site, affected scope, network path, service-health result, screenshots, and business impact.']
    },
    'FIX_VIDEO_CONF_POLICY_ACCOUNT_CACHE': {
        'user': ['Sign out and back into the meeting app.', 'Try the browser or desktop app alternative.', 'Report any account or policy error.'],
        'technician': ['Confirm user account/license and meeting policy.', 'Check whether guest/external join is allowed.', 'Clear app cache or repair/reinstall app if policy allows.', 'Compare behavior with another user/device.', 'Escalate to Collaboration admin if policy or tenant setting is involved.'],
        'admin': ['Escalation notes: provide account/license state, policy result, app version, cache/repair attempt, comparison test, and error screenshots to Collaboration Admin.']
    }
}

VIDEO_CONFERENCING_ISSUE_USER_DIAGNOSTIC_NODES = [
    ('ROOT', None, 'question', 'Video Conferencing Issue', 'Start here for meeting audio, camera, join, screen sharing, or quality problems.', 'What part of the meeting is not working?', None, None, None, 1),
    ('AUDIO', 'ROOT', 'solution', 'Check Meeting Audio Device and Mute Settings', 'No speaker audio or others cannot hear the user.', None, 'Cannot hear / others cannot hear me', 'audio', 'FIX_VIDEO_CONF_AUDIO_DEVICE_MUTE', 1),
    ('CAMERA', 'ROOT', 'solution', 'Check Camera Device and Permissions', 'Camera is not detected, selected, or allowed.', None, 'Camera not working', 'camera', 'FIX_VIDEO_CONF_CAMERA_PERMISSIONS', 2),
    ('JOIN', 'ROOT', 'solution', 'Check Meeting Link, Account, and App Access', 'User cannot join the meeting.', None, 'Cannot join', 'join', 'FIX_VIDEO_CONF_JOIN_ACCESS', 3),
    ('SHARE', 'ROOT', 'solution', 'Check Screen Sharing Permission', 'Screen sharing does not work or is blocked.', None, 'Screen sharing not working', 'share', 'FIX_VIDEO_CONF_SCREEN_SHARE_PERMISSION', 4),
    ('QUALITY', 'ROOT', 'solution', 'Improve Network Connection for Meeting', 'Meeting lag, freezing, or disconnects.', None, 'Lag/disconnects', 'quality', 'FIX_VIDEO_CONF_NETWORK_QUALITY_USER', 5),
]

VIDEO_CONFERENCING_ISSUE_TECH_DIAGNOSTIC_NODES = [
    ('ROOT', None, 'question', 'Video Conferencing Issue - IT Support Specialist', 'Start here for meeting device, app, account, policy, service, or network quality issues.', 'Is the issue audio/video device detection or meeting access/network quality?', None, None, None, 1),
    ('DEVICE_Q', 'ROOT', 'question', 'Device Detection and Permissions', 'Check whether OS detects device and permissions allow access.', 'Does the OS detect the device and allow permissions?', 'Audio/video device', 'device', None, 1),
    ('DEVICE_NO', 'DEVICE_Q', 'solution', 'Troubleshoot OS Device Detection and Privacy Permissions', 'OS device detection or privacy permission issue.', None, 'No', 'no', 'FIX_VIDEO_CONF_OS_DEVICE_PRIVACY', 1),
    ('DEVICE_YES', 'DEVICE_Q', 'solution', 'Troubleshoot Meeting App Device Selection', 'OS detects device but app selection/settings may be wrong.', None, 'Yes', 'yes', 'FIX_VIDEO_CONF_APP_DEVICE_SELECTION', 2),
    ('MULTI_Q', 'ROOT', 'question', 'Affected Scope', 'Check whether the issue affects multiple users.', 'Are multiple users affected?', 'Access/network quality', 'access_network', None, 2),
    ('MULTI_YES', 'MULTI_Q', 'solution', 'Escalate Collaboration Service or Network Issue', 'Multiple users indicate service, policy, or network issue.', None, 'Yes', 'yes', 'FIX_VIDEO_CONF_ESCALATE_SERVICE_NETWORK', 1),
    ('NET_Q', 'MULTI_Q', 'question', 'Network Quality or VPN', 'Check network path and quality.', 'Is network quality poor or VPN/proxy involved?', 'No', 'no', None, 2),
    ('NET_YES', 'NET_Q', 'solution', 'Troubleshoot Meeting Network Quality', 'Network path, VPN, Wi-Fi, or media traffic may be affecting meetings.', None, 'Yes', 'yes', 'FIX_VIDEO_CONF_NETWORK_QUALITY_TECH', 1),
    ('POLICY', 'NET_Q', 'solution', 'Check Meeting Policy, Account, or App Cache', 'Account, policy, or app cache may be affecting access.', None, 'No', 'no', 'FIX_VIDEO_CONF_POLICY_ACCOUNT_CACHE', 2),
]

def seed_video_conferencing_issue_content(cursor):
    """Seed Video Conferencing Issue KB article, solutions, steps, and diagnostic trees."""
    code_, title, category, severity, description = VIDEO_CONFERENCING_ISSUE_PROBLEM
    cursor.execute("""
        INSERT INTO problem (problem_code, title, category, severity, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(problem_code) DO UPDATE SET
            title=excluded.title, category=excluded.category, severity=excluded.severity,
            description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, VIDEO_CONFERENCING_ISSUE_PROBLEM)
    cursor.execute('SELECT problem_id FROM problem WHERE problem_code = ?', (code_,))
    row = cursor.fetchone()
    if not row:
        return
    problem_id = row['problem_id']
    cursor.execute("""
        INSERT INTO kb_article (problem_id, title, summary, difficulty, estimated_time, escalation_required, escalation_notes, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, difficulty=excluded.difficulty,
            estimated_time=excluded.estimated_time, escalation_required=excluded.escalation_required,
            escalation_notes=excluded.escalation_notes, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, VIDEO_CONFERENCING_ISSUE_KB['title'], VIDEO_CONFERENCING_ISSUE_KB['summary'], VIDEO_CONFERENCING_ISSUE_KB['difficulty'], VIDEO_CONFERENCING_ISSUE_KB['estimated_time'], VIDEO_CONFERENCING_ISSUE_KB['escalation_required'], VIDEO_CONFERENCING_ISSUE_KB['escalation_notes']))
    cursor.execute('SELECT kb_article_id FROM kb_article WHERE problem_id = ?', (problem_id,))
    article = cursor.fetchone()
    if article:
        kb_id = article['kb_article_id']
        delete_kb_child_rows(cursor, kb_id)
        insert_kb_child_rows(cursor, 'kb_article_tag', 'tag', kb_id, VIDEO_CONFERENCING_ISSUE_KB['tags'])
        insert_kb_child_rows(cursor, 'kb_article_symptom', 'symptom', kb_id, VIDEO_CONFERENCING_ISSUE_KB['symptoms'])
        insert_kb_child_rows(cursor, 'kb_article_cause', 'cause', kb_id, VIDEO_CONFERENCING_ISSUE_KB['causes'])
        insert_kb_child_rows(cursor, 'kb_article_user_step', 'step_text', kb_id, VIDEO_CONFERENCING_ISSUE_KB['user_steps'])
        insert_kb_child_rows(cursor, 'kb_article_it_step', 'step_text', kb_id, VIDEO_CONFERENCING_ISSUE_KB['it_steps'])
    cursor.executemany("""
        INSERT INTO solution (solution_code, title, summary, resolution_steps, escalation_required, escalation_notes, priority_recommendation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(solution_code) DO UPDATE SET
            title=excluded.title, summary=excluded.summary, resolution_steps=excluded.resolution_steps,
            escalation_required=excluded.escalation_required, escalation_notes=excluded.escalation_notes,
            priority_recommendation=excluded.priority_recommendation, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, VIDEO_CONFERENCING_ISSUE_SOLUTIONS)
    for solution_code, audience_steps in VIDEO_CONFERENCING_ISSUE_SOLUTION_STEPS.items():
        solution_id = get_solution_id_by_code(cursor, solution_code)
        if not solution_id:
            continue
        for audience, steps in audience_steps.items():
            cursor.execute('DELETE FROM solution_step WHERE solution_id = ? AND audience = ?', (solution_id, audience))
            cursor.executemany('INSERT INTO solution_step (solution_id, audience, step_text, sort_order) VALUES (?, ?, ?, ?)', [(solution_id, audience, step, idx) for idx, step in enumerate(steps, start=1)])
    seed_video_conferencing_tree(cursor, 'user', 'VIDEO_CONFERENCING_ISSUE_USER', 'Video Conferencing Issue - User Diagnostic', 'User-friendly diagnostic tree for meeting audio, video, join, sharing, and call-quality issues.', VIDEO_CONFERENCING_ISSUE_USER_DIAGNOSTIC_NODES)
    seed_video_conferencing_tree(cursor, 'technician', 'VIDEO_CONFERENCING_ISSUE_TECHNICIAN', 'Video Conferencing Issue - IT Support Specialist Diagnostic', 'IT Support Specialist diagnostic tree for device, app, policy, service, and network-quality issues.', VIDEO_CONFERENCING_ISSUE_TECH_DIAGNOSTIC_NODES)

def seed_video_conferencing_tree(cursor, audience, tree_code, title, description, nodes):
    problem_id = get_problem_id_for_tree_code(cursor, 'VIDEO_CONFERENCING_ISSUE')
    cursor.execute("""
        INSERT INTO diagnostic_tree (problem_id, diagnostic_tree_code, base_tree_code, audience, title, description, is_active, updated_at)
        VALUES (?, ?, 'VIDEO_CONFERENCING_ISSUE', ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(diagnostic_tree_code) DO UPDATE SET
            problem_id=excluded.problem_id, base_tree_code=excluded.base_tree_code, audience=excluded.audience,
            title=excluded.title, description=excluded.description, is_active=1, updated_at=CURRENT_TIMESTAMP
    """, (problem_id, tree_code, audience, title, description))
    tree_id = get_diagnostic_tree_id_by_code(cursor, tree_code)
    if not tree_id:
        return
    cursor.execute('UPDATE diagnostic_node SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE diagnostic_tree_id = ?', (tree_id,))
    for node_key, parent_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_code, sort_order in nodes:
        parent_id = get_diagnostic_node_id_by_tree_and_key(cursor, tree_id, parent_key) if parent_key else None
        solution_id = get_solution_id_by_code(cursor, solution_code) if solution_code else None
        cursor.execute("""
            INSERT INTO diagnostic_node (
                diagnostic_tree_id, parent_diagnostic_node_id, problem_id, diagnostic_tree_code,
                node_key, node_type, title, description, prompt_text,
                condition_label, condition_value, solution_id, sort_order, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(diagnostic_tree_code, node_key) DO UPDATE SET
                diagnostic_tree_id=excluded.diagnostic_tree_id,
                parent_diagnostic_node_id=excluded.parent_diagnostic_node_id,
                problem_id=excluded.problem_id,
                node_type=excluded.node_type,
                title=excluded.title,
                description=excluded.description,
                prompt_text=excluded.prompt_text,
                condition_label=excluded.condition_label,
                condition_value=excluded.condition_value,
                solution_id=excluded.solution_id,
                sort_order=excluded.sort_order,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (tree_id, parent_id, problem_id, tree_code, node_key, node_type, node_title, node_desc, prompt, condition_label, condition_value, solution_id, sort_order))

def initialize_database():
    """Create SQLite tables if they do not already exist."""
    connection = get_db_connection()
    cursor = connection.cursor()

    initialize_relational_knowledge_schema(cursor)
    seed_problem_and_solution_data(cursor)
    seed_diagnostic_node_data(cursor)
    seed_relational_kb_articles(cursor)
    seed_audience_diagnostic_support(cursor)
    seed_role_specific_diagnostic_content(cursor)
    seed_printer_failure_content(cursor)
    seed_password_reset_request_content(cursor)
    seed_account_locked_content(cursor)
    seed_mfa_issue_content(cursor)
    seed_vpn_connection_failure_content(cursor)
    seed_shared_drive_access_content(cursor)
    seed_remote_desktop_connection_content(cursor)
    seed_slow_computer_performance_content(cursor)
    seed_application_not_opening_content(cursor)
    seed_application_crashing_freezing_content(cursor)
    seed_operating_system_update_issue_content(cursor)
    seed_device_storage_content(cursor)
    seed_phishing_email_reported_content(cursor)
    seed_malware_or_virus_suspected_content(cursor)
    seed_email_attachment_not_opening_content(cursor)
    seed_calendar_sync_issue_content(cursor)
    seed_software_installation_request_content(cursor)
    seed_browser_issue_content(cursor)
    seed_certificate_security_warning_content(cursor)
    seed_mobile_email_setup_issue_content(cursor)
    seed_video_conferencing_issue_content(cursor)
    seed_existing_issue_role_alignment(cursor)

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
        CREATE TABLE IF NOT EXISTS auth_session (
            session_token TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_session_username ON auth_session(username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_session_expires ON auth_session(expires_at)")

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

    # MVP+ troubleshooting audit trail tables.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS troubleshooting_session (
            session_id TEXT PRIMARY KEY,
            username TEXT,
            diagnostic_tree_code TEXT NOT NULL,
            issue_title TEXT,
            status TEXT NOT NULL DEFAULT 'Started',
            current_node_id INTEGER,
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ended_at TEXT,
            FOREIGN KEY (current_node_id)
                REFERENCES diagnostic_node(diagnostic_node_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS troubleshooting_event (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            node_id INTEGER,
            event_type TEXT NOT NULL,
            event_notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id)
                REFERENCES troubleshooting_session(session_id)
                ON DELETE CASCADE,
            FOREIGN KEY (node_id)
                REFERENCES diagnostic_node(diagnostic_node_id)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_troubleshooting_event_session ON troubleshooting_event(session_id, created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_troubleshooting_session_user ON troubleshooting_session(username, started_at)")

    # Add ticket_data column for full ticket JSON storage during migration.
    cursor.execute("PRAGMA table_info(tickets)")
    ticket_columns = [column[1] for column in cursor.fetchall()]
    if "ticket_data" not in ticket_columns:
        cursor.execute("ALTER TABLE tickets ADD COLUMN ticket_data TEXT")

    ticket_mvp_columns = {
        "business_impact": "TEXT DEFAULT ''",
        "contact_method": "TEXT DEFAULT ''",
        "device_or_location": "TEXT DEFAULT ''",
        "troubleshooting_session_id": "TEXT DEFAULT ''",
        "troubleshooting_summary_snapshot": "TEXT DEFAULT ''",
    }

    for column_name, column_definition in ticket_mvp_columns.items():
        if column_name not in ticket_columns:
            cursor.execute(f"ALTER TABLE tickets ADD COLUMN {column_name} {column_definition}")

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
    """Render ticket descriptions in a readable box.

    User-submitted ticket descriptions may contain characters that look like
    HTML. Escape them before rendering inside the styled card, while preserving
    line breaks for readability.
    """
    safe_text = html.escape(str(text or "No description provided.")).replace("\n", "<br>")
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
# MVP FLOW / NAVIGATION HELPERS
# -----------------------------
def normalize_mode_name(mode_name):
    """Normalize a sidebar/page name so buttons can navigate across badge labels."""
    return normalize_menu_choice(mode_name) if "normalize_menu_choice" in globals() else mode_name


def navigate_to_mode(mode_name):
    """Request navigation to a top-level sidebar mode and rerun the app."""
    st.session_state["selected_mode_request"] = mode_name
    st.rerun()


def render_mvp_flow_steps(active_step):
    """Render the MVP support flow as a compact visual stepper."""
    steps = [
        ("category", "1", "Select category"),
        ("question", "2", "Answer questions"),
        ("solution", "3", "Review solution"),
        ("ticket", "4", "Submit ticket if needed"),
    ]

    cols = st.columns(len(steps))
    for col, (step_key, number, label) in zip(cols, steps):
        is_active = step_key == active_step
        border_color = "#4e89ff" if is_active else "#d8dee9"
        background = "#eef5ff" if is_active else "#ffffff"
        col.markdown(
            f"""
            <div style="padding:0.75rem; border:1px solid {border_color}; background:{background}; border-radius:12px; text-align:center; min-height:78px;">
                <div style="font-weight:800; font-size:1.05rem;">{number}</div>
                <div style="font-size:0.9rem; color:#374151;">{label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_support_action_cards():
    """Show the three core portfolio MVP actions."""
    col_start, col_ticket, col_mine = st.columns(3)

    with col_start:
        st.markdown("""
        <div class="app-card">
            <h3>Start troubleshooting</h3>
            <p>Answer guided questions and receive a recommended fix.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Start guided troubleshooting", key="home_start_troubleshooting"):
            navigate_to_mode("🧭 Guided Troubleshooting")

    with col_ticket:
        st.markdown("""
        <div class="app-card">
            <h3>Create a ticket</h3>
            <p>Escalate unresolved issues with business impact and device details.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Create support ticket", key="home_create_ticket"):
            navigate_to_mode("🎫 Create Ticket")

    with col_mine:
        st.markdown("""
        <div class="app-card">
            <h3>Review tickets</h3>
            <p>Track submitted tickets, comments, status, and diagnostic history.</p>
        </div>
        """, unsafe_allow_html=True)
        target = "📋 View Tickets" if st.session_state.get("role") == "Admin" else "🎟 My Tickets"
        if st.button("View tickets", key="home_view_tickets"):
            navigate_to_mode(target)

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
    """Return technical troubleshooting steps for IT Support Specialists."""
    if issue.get("it_steps"):
        return issue["it_steps"]
    return issue.get("steps", [])


def show_role_based_steps(issue):
    """Display troubleshooting steps depending on the logged-in role."""
    role = st.session_state.get("role", "User")

    if role == "Admin":
        st.write("**IT Support Specialist Steps (Tier 1 / junior Tier 2):**")
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
def get_query_param_value(name):
    """Return one query parameter value across Streamlit versions."""
    try:
        value = st.query_params.get(name)
    except Exception:
        return ""

    if isinstance(value, list):
        return value[0] if value else ""
    return value or ""


def set_query_param_value(name, value):
    """Set one query parameter safely."""
    try:
        st.query_params[name] = value
    except Exception:
        pass


def clear_query_param_value(name):
    """Remove one query parameter safely."""
    try:
        if name in st.query_params:
            del st.query_params[name]
    except Exception:
        pass


def create_auth_session(username, role):
    """Create a refresh-safe login session token with a sliding timeout."""
    token = secrets.token_urlsafe(32)
    now = datetime.now()
    expires_at = now + timedelta(hours=AUTH_SESSION_TIMEOUT_HOURS)

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO auth_session (
            session_token,
            username,
            role,
            created_at,
            last_seen_at,
            expires_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            token,
            username,
            role,
            now.strftime("%Y-%m-%d %H:%M:%S"),
            now.strftime("%Y-%m-%d %H:%M:%S"),
            expires_at.strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    connection.commit()
    connection.close()
    return token


def delete_auth_session(token):
    """Delete one persisted auth session token."""
    if not token:
        return

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM auth_session WHERE session_token = ?", (token,))
    connection.commit()
    connection.close()


def restore_login_from_auth_session():
    """Restore login after browser refresh while the session has not expired."""
    if st.session_state.get("logged_in"):
        return True

    token = get_query_param_value(AUTH_SESSION_QUERY_PARAM)
    if not token:
        return False

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT session_token, username, role, expires_at
        FROM auth_session
        WHERE session_token = ?
        """,
        (token,),
    )
    row = cursor.fetchone()

    if not row:
        connection.close()
        clear_query_param_value(AUTH_SESSION_QUERY_PARAM)
        return False

    expires_at = parse_timestamp(row["expires_at"])
    now = datetime.now()

    if not expires_at or expires_at <= now:
        cursor.execute("DELETE FROM auth_session WHERE session_token = ?", (token,))
        connection.commit()
        connection.close()
        clear_query_param_value(AUTH_SESSION_QUERY_PARAM)
        return False

    refreshed_expires_at = now + timedelta(hours=AUTH_SESSION_TIMEOUT_HOURS)
    cursor.execute(
        """
        UPDATE auth_session
        SET last_seen_at = ?, expires_at = ?
        WHERE session_token = ?
        """,
        (
            now.strftime("%Y-%m-%d %H:%M:%S"),
            refreshed_expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            token,
        ),
    )
    connection.commit()
    connection.close()

    st.session_state["logged_in"] = True
    st.session_state["username"] = row["username"]
    st.session_state["role"] = row["role"]
    st.session_state["auth_session_token"] = token
    return True


def login_user(username, password):
    """Validate a user login using SQLite."""
    username_clean = username.strip()
    account = get_user(username_clean)

    if account and account["password"] == password:
        st.session_state["logged_in"] = True
        st.session_state["username"] = username_clean
        st.session_state["role"] = account["role"]
        auth_token = create_auth_session(username_clean, account["role"])
        st.session_state["auth_session_token"] = auth_token
        set_query_param_value(AUTH_SESSION_QUERY_PARAM, auth_token)
        return True

    return False


def logout_user():
    """Clear login session and invalidate the persisted refresh token."""
    token = st.session_state.get("auth_session_token") or get_query_param_value(AUTH_SESSION_QUERY_PARAM)
    delete_auth_session(token)
    clear_query_param_value(AUTH_SESSION_QUERY_PARAM)
    st.session_state["logged_in"] = False
    st.session_state.pop("username", None)
    st.session_state.pop("role", None)
    st.session_state.pop("auth_session_token", None)


def show_login_page():
    """Show login and registration forms."""
    st.title("🔐 IT Troubleshooting Login")

    tab_login, tab_register = st.tabs(["Login", "Create Account"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login", key="login_submit")

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
                "**IT Support Specialist Account**\n\n"
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
            submitted_register = st.form_submit_button("Create Account", key="register_submit")

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
        st.error("IT Support Specialist access required")
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
        mime="text/plain",
        key="download_troubleshooting_report",
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
# RELATIONAL DIAGNOSTIC AUDIENCE HELPERS
# -----------------------------
def get_problem_id_for_tree_code(cursor, tree_code):
    """Return problem_id for a diagnostic tree code."""
    cursor.execute(
        "SELECT problem_id FROM problem WHERE problem_code = ?",
        (tree_code,),
    )
    row = cursor.fetchone()
    return row["problem_id"] if row else None


def seed_diagnostic_tree_records(cursor):
    """Create one user-facing diagnostic_tree record per seeded diagnostic tree.

    Existing diagnostic_node rows use diagnostic_tree_code directly. This migration
    preserves them and links all nodes to a new diagnostic_tree row with audience='user'.
    """

    cursor.execute(
        """
        SELECT
            diagnostic_tree_code,
            MIN(title) AS title,
            MIN(description) AS description
        FROM diagnostic_node
        WHERE parent_diagnostic_node_id IS NULL
        GROUP BY diagnostic_tree_code
        """
    )
    root_rows = cursor.fetchall()

    for row in root_rows:
        base_tree_code = row["diagnostic_tree_code"]
        user_tree_code = f"{base_tree_code}_USER"
        problem_id = get_problem_id_for_tree_code(cursor, base_tree_code)

        cursor.execute(
            """
            INSERT OR IGNORE INTO diagnostic_tree (
                problem_id,
                diagnostic_tree_code,
                base_tree_code,
                audience,
                title,
                description
            )
            VALUES (?, ?, ?, 'user', ?, ?)
            """,
            (
                problem_id,
                user_tree_code,
                base_tree_code,
                row["title"] or base_tree_code.replace("_", " ").title(),
                row["description"] or "User-facing diagnostic tree.",
            ),
        )

        cursor.execute(
            """
            SELECT diagnostic_tree_id
            FROM diagnostic_tree
            WHERE diagnostic_tree_code = ?
            """,
            (user_tree_code,),
        )
        tree_row = cursor.fetchone()

        if tree_row:
            cursor.execute(
                """
                UPDATE diagnostic_node
                SET diagnostic_tree_id = ?
                WHERE diagnostic_tree_code = ?
                  AND diagnostic_tree_id IS NULL
                """,
                (tree_row["diagnostic_tree_id"], base_tree_code),
            )


def seed_solution_steps_from_solution_text(cursor):
    """Seed solution_step rows from existing solution.resolution_steps text.

    Existing solution records keep their original resolution_steps field, but this
    creates normalized user-facing solution steps for role-aware display.
    """

    cursor.execute(
        """
        SELECT solution_id, resolution_steps
        FROM solution
        WHERE is_active = 1
        """
    )
    rows = cursor.fetchall()

    for row in rows:
        solution_id = row["solution_id"]

        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM solution_step
            WHERE solution_id = ?
              AND audience = 'user'
            """,
            (solution_id,),
        )
        if cursor.fetchone()["count"] > 0:
            continue

        raw_steps = row["resolution_steps"] or ""
        steps = [
            step.strip(" -•\t")
            for step in raw_steps.splitlines()
            if step.strip(" -•\t")
        ]

        if not steps and raw_steps.strip():
            steps = [raw_steps.strip()]

        cursor.executemany(
            """
            INSERT INTO solution_step (
                solution_id,
                audience,
                step_text,
                sort_order
            )
            VALUES (?, 'user', ?, ?)
            """,
            [
                (solution_id, step_text, index)
                for index, step_text in enumerate(steps, start=1)
            ],
        )


def seed_audience_diagnostic_support(cursor):
    """Seed/migrate audience-aware diagnostic and solution-step support."""
    seed_diagnostic_tree_records(cursor)
    seed_solution_steps_from_solution_text(cursor)




# -----------------------------
# DIAGNOSTIC RESULT / TICKET CONTEXT HELPERS
# -----------------------------
def create_troubleshooting_session(tree_code, root_node_id, issue_title=None):
    """Create a persistent troubleshooting session for the current guided flow."""
    session_id = str(uuid.uuid4())
    username = st.session_state.get("username", "Unknown")

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO troubleshooting_session (
            session_id,
            username,
            diagnostic_tree_code,
            issue_title,
            status,
            current_node_id,
            started_at
        )
        VALUES (?, ?, ?, ?, 'Started', ?, ?)
        """,
        (
            session_id,
            username,
            tree_code,
            issue_title or tree_code,
            root_node_id,
            get_current_timestamp(),
        ),
    )
    connection.commit()
    connection.close()
    return session_id


def update_troubleshooting_session(session_id, current_node_id=None, status=None):
    """Update the active troubleshooting session status/current node."""
    if not session_id:
        return

    assignments = []
    values = []

    if current_node_id is not None:
        assignments.append("current_node_id = ?")
        values.append(current_node_id)

    if status:
        assignments.append("status = ?")
        values.append(status)
        if status in {"Resolved", "Ticket Submitted", "Abandoned"}:
            assignments.append("ended_at = ?")
            values.append(get_current_timestamp())

    if not assignments:
        return

    values.append(session_id)
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        f"UPDATE troubleshooting_session SET {', '.join(assignments)} WHERE session_id = ?",
        values,
    )
    connection.commit()
    connection.close()


def log_troubleshooting_event(session_id, node_id, event_type, event_notes=""):
    """Persist one troubleshooting audit event."""
    if not session_id:
        return

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO troubleshooting_event (
            session_id,
            node_id,
            event_type,
            event_notes,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            session_id,
            node_id,
            event_type,
            event_notes,
            get_current_timestamp(),
        ),
    )
    connection.commit()
    connection.close()


def build_troubleshooting_summary_snapshot(diagnostic_context):
    """Build a stable plain-text snapshot of the diagnostic trail for tickets."""
    diagnostic_context = diagnostic_context or {}
    lines = [
        f"Issue: {diagnostic_context.get('issue_title', 'N/A')}",
        f"Diagnostic tree: {diagnostic_context.get('diagnostic_tree_code', 'N/A')}",
        f"Audience: {str(diagnostic_context.get('diagnostic_audience', 'user')).title()}",
        f"Recommended solution: {diagnostic_context.get('solution_title', 'N/A')}",
        f"Priority recommendation: {diagnostic_context.get('priority_recommendation', 'N/A')}",
    ]

    if diagnostic_context.get("escalation_required"):
        lines.append("Escalation recommended: Yes")
        if diagnostic_context.get("escalation_notes"):
            lines.append(f"Escalation notes: {diagnostic_context.get('escalation_notes')}")
    else:
        lines.append("Escalation recommended: No")

    path = diagnostic_context.get("diagnostic_path") or []
    lines.append("Diagnostic path:")
    if path:
        lines.extend([f"- {step}" for step in path])
    else:
        lines.append("- No diagnostic path captured.")

    return "\n".join(lines)


def build_diagnostic_ticket_context(tree_code, solution, diagnostic_path, issue_title=None):
    """Build a serializable diagnostic context to store with a ticket."""
    solution = solution or {}
    diagnostic_path = diagnostic_path or []

    return {
        "issue_title": issue_title or tree_code,
        "diagnostic_tree_code": tree_code,
        "diagnostic_audience": get_current_diagnostic_audience(),
        "diagnostic_path": diagnostic_path,
        "solution_code": solution.get("solution_code", ""),
        "solution_title": solution.get("title", ""),
        "solution_summary": solution.get("summary", ""),
        "priority_recommendation": get_solution_priority_label(solution.get("priority_recommendation")),
        "escalation_required": bool(solution.get("escalation_required")),
        "escalation_notes": solution.get("escalation_notes", ""),
        "captured_at": get_current_timestamp(),
        "troubleshooting_session_id": st.session_state.get(f"diagnostic_session_id_{tree_code}", ""),
    }



def ticket_has_diagnostic_context(ticket):
    """Return True if a ticket was created after guided troubleshooting."""
    return bool(ticket.get("diagnostic_context"))


def get_diagnostic_ticket_label(ticket):
    """Return a compact label for tickets created from Guided Troubleshooting."""
    context = ticket.get("diagnostic_context") or {}

    if not context:
        return ""

    solution_title = context.get("solution_title", "")
    if solution_title:
        return f" 🧭 Diagnostic: {solution_title}"

    return " 🧭 Diagnostic"

def get_ticket_reference(ticket, fallback_index=None):
    """Return a stable, reviewer-friendly ticket reference."""
    if ticket.get("db_id"):
        return f"TICKET-{int(ticket['db_id']):04d}"
    if fallback_index is not None:
        return f"TICKET-{int(fallback_index):04d}"
    return "TICKET-PENDING"


def render_ticket_mvp_summary(ticket, fallback_index=None):
    """Render the MVP ticket fields that make the escalation useful."""
    st.markdown("### 🎫 Ticket Details")
    col_ref, col_contact, col_device = st.columns(3)
    col_ref.metric("Ticket Ref", get_ticket_reference(ticket, fallback_index))
    col_contact.metric("Contact", ticket.get("contact_method") or "Not provided")
    col_device.metric("Device / Location", ticket.get("device_or_location") or "Not provided")

    business_impact = ticket.get("business_impact", "").strip()
    if business_impact:
        st.markdown("**Business Impact**")
        render_description_box(business_impact)
    else:
        st.caption("Business impact was not provided for this ticket.")


def load_troubleshooting_events_for_session(session_id):
    """Load persisted troubleshooting events for a ticket's session trail."""
    if not session_id:
        return []

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            event_type,
            event_notes,
            created_at
        FROM troubleshooting_event
        WHERE session_id = ?
        ORDER BY created_at ASC, event_id ASC
        """,
        (session_id,),
    )
    events = [dict(row) for row in cursor.fetchall()]
    connection.close()
    return events


def show_troubleshooting_event_audit(session_id):
    """Display the full persisted event trail for a troubleshooting session."""
    events = load_troubleshooting_events_for_session(session_id)
    if not events:
        return

    with st.expander("View full troubleshooting event audit"):
        for event in events:
            event_type = event.get("event_type", "EVENT")
            notes = event.get("event_notes") or "No notes captured."
            created_at = event.get("created_at", "")
            st.write(f"**{event_type}** — {created_at}")
            st.caption(notes)


def show_ticket_trail_snapshot(ticket):
    """Show the historical ticket trail snapshot saved at submission time."""
    snapshot = ticket.get("troubleshooting_summary_snapshot", "").strip()
    if not snapshot:
        return

    with st.expander("View submitted troubleshooting trail snapshot"):
        st.code(snapshot, language="text")


def render_empty_ticket_state(message, button_key):
    """Display a helpful empty state with the next best action."""
    st.info(message)
    if st.button("Start guided troubleshooting", key=button_key):
        navigate_to_mode("🧭 Guided Troubleshooting")

def show_ticket_diagnostic_context(ticket):
    """Display diagnostic context stored in a ticket."""
    context = ticket.get("diagnostic_context") or {}

    if not context:
        return

    st.subheader("🧭 Diagnostic History")

    st.write(f"**Original Issue:** {context.get('issue_title', 'N/A')}")
    st.write(f"**Diagnostic Tree:** {context.get('diagnostic_tree_code', 'N/A')}")
    st.write(f"**Audience:** {context.get('diagnostic_audience', 'N/A').title()}")
    st.write(f"**Recommended Solution:** {context.get('solution_title', 'N/A')}")
    st.write(f"**Priority Recommendation:** {context.get('priority_recommendation', 'N/A')}")

    if context.get("escalation_required"):
        st.warning("🚨 Escalation was recommended by the diagnostic result.")
        if context.get("escalation_notes"):
            st.write(context.get("escalation_notes"))

    if context.get("solution_summary"):
        st.write("**Solution Summary:**")
        st.write(context.get("solution_summary"))

    path = context.get("diagnostic_path", [])
    if path:
        with st.expander("View diagnostic path"):
            for step in path:
                st.write(f"- {step}")

    session_id = context.get("troubleshooting_session_id") or ticket.get("troubleshooting_session_id", "")
    if session_id:
        st.caption(f"Troubleshooting session: {session_id}")
        show_troubleshooting_event_audit(session_id)

    if context.get("captured_at"):
        st.caption(f"Diagnostic captured at: {context.get('captured_at')}")

    show_ticket_trail_snapshot(ticket)

# -----------------------------
# RELATIONAL DIAGNOSTIC TREE ACCESS
# -----------------------------


def get_current_diagnostic_audience():
    """Return the troubleshooting audience for the logged-in role.

    In this MVP, the Streamlit role named ``Admin`` represents the app's
    support-side user. That person should see IT Support Specialist procedures
    rather than senior company-admin-only notes.
    """
    role = st.session_state.get("role", "User")

    if role in ["Admin", "Technician", "IT Support Specialist"]:
        return "technician"

    return "user"


def get_audience_display_name(audience):
    """Return reviewer-friendly audience labels for the UI."""
    if audience == "technician":
        return "IT Support Specialist"
    if audience == "admin":
        return "Escalation Notes"
    return "Regular User"


def get_role_display_name(role):
    """Return portfolio-friendly role labels without changing stored role values."""
    if role == "Admin":
        return "IT Support Specialist"
    return role or "User"


def get_audience_fallback_order(audience):
    """Return fallback order for diagnostic tree/solution-step lookup."""
    if audience in ["admin", "technician"]:
        return ["technician", "user"]
    return ["user"]


def get_solution_steps_by_audience(solution_id, audience):
    """Return normalized solution steps for the best available audience."""
    if not solution_id:
        return []

    connection = get_db_connection()
    cursor = connection.cursor()

    for candidate_audience in get_audience_fallback_order(audience):
        cursor.execute(
            """
            SELECT step_text
            FROM solution_step
            WHERE solution_id = ?
              AND audience = ?
            ORDER BY sort_order, solution_step_id
            """,
            (solution_id, candidate_audience),
        )
        rows = cursor.fetchall()

        if rows:
            connection.close()
            return [row["step_text"] for row in rows]

    connection.close()
    return []


def get_solution_steps_for_exact_audience(solution_id, audience):
    """Return solution steps for one exact audience without fallback.

    This is used for admin/technician displays so approved technician
    procedures are not hidden by a shorter admin escalation note.
    """
    if not solution_id or not audience:
        return []

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT step_text
        FROM solution_step
        WHERE solution_id = ?
          AND audience = ?
        ORDER BY sort_order, solution_step_id
        """,
        (solution_id, audience),
    )
    rows = cursor.fetchall()
    connection.close()
    return [row["step_text"] for row in rows]


def get_solution_steps_for_ticket_context(solution_id, audience):
    """Return the operational steps that should be copied into a ticket.

    Support-side users should capture IT Support Specialist steps first, plus
    escalation notes where available.
    """
    if audience in ["admin", "technician"]:
        technician_steps = get_solution_steps_for_exact_audience(solution_id, "technician")
        escalation_notes = get_solution_steps_for_exact_audience(solution_id, "admin")
        combined = technician_steps[:]
        combined.extend([f"Escalation note: {step}" for step in escalation_notes])
        if combined:
            return combined

    return get_solution_steps_by_audience(solution_id, audience)

def get_available_diagnostic_trees():
    """Return active diagnostic trees for the current audience."""
    audience = get_current_diagnostic_audience()
    fallback_audiences = get_audience_fallback_order(audience)

    connection = get_db_connection()
    cursor = connection.cursor()

    placeholders = ",".join(["?"] * len(fallback_audiences))

    cursor.execute(
        f"""
        SELECT
            dt.diagnostic_tree_code,
            dt.base_tree_code,
            dt.audience,
            dt.title,
            dt.description,
            p.title AS problem_title,
            p.category,
            p.severity
        FROM diagnostic_tree dt
        LEFT JOIN problem p
            ON dt.problem_id = p.problem_id
        WHERE dt.is_active = 1
          AND dt.audience IN ({placeholders})
        ORDER BY
            CASE dt.audience
                WHEN ? THEN 0
                WHEN 'technician' THEN 1
                WHEN 'user' THEN 2
                ELSE 3
            END,
            COALESCE(p.category, ''),
            COALESCE(p.title, dt.title)
        """,
        fallback_audiences + [audience],
    )

    rows = cursor.fetchall()
    connection.close()

    return [dict(row) for row in rows]


def diagnostic_tree_exists(tree_code):
    """Check whether a diagnostic tree exists for the current audience."""
    return get_diagnostic_tree_record(tree_code) is not None


def get_diagnostic_tree_record(base_tree_code):
    """Return the best diagnostic_tree record for a base tree code and current audience."""
    if not base_tree_code:
        return None

    audience = get_current_diagnostic_audience()
    fallback_audiences = get_audience_fallback_order(audience)

    connection = get_db_connection()
    cursor = connection.cursor()

    for candidate_audience in fallback_audiences:
        cursor.execute(
            """
            SELECT *
            FROM diagnostic_tree
            WHERE base_tree_code = ?
              AND audience = ?
              AND is_active = 1
            LIMIT 1
            """,
            (base_tree_code, candidate_audience),
        )
        row = cursor.fetchone()

        if row:
            connection.close()
            return dict(row)

    connection.close()
    return None


def get_diagnostic_root_node(tree_code):
    """Return the root diagnostic node for the best available audience tree."""
    tree_record = get_diagnostic_tree_record(tree_code)

    if not tree_record:
        return None

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM diagnostic_node
        WHERE diagnostic_tree_id = ?
          AND parent_diagnostic_node_id IS NULL
          AND is_active = 1
        ORDER BY sort_order, diagnostic_node_id
        LIMIT 1
        """,
        (tree_record["diagnostic_tree_id"],),
    )

    row = cursor.fetchone()
    connection.close()
    return dict(row) if row else None


def get_diagnostic_node(node_id):
    """Return a diagnostic node by ID."""
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM diagnostic_node
        WHERE diagnostic_node_id = ?
          AND is_active = 1
        """,
        (node_id,),
    )

    row = cursor.fetchone()
    connection.close()
    return dict(row) if row else None


def get_child_diagnostic_nodes(parent_node_id):
    """Return active child diagnostic nodes ordered for display."""
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM diagnostic_node
        WHERE parent_diagnostic_node_id = ?
          AND is_active = 1
        ORDER BY sort_order, diagnostic_node_id
        """,
        (parent_node_id,),
    )

    rows = cursor.fetchall()
    connection.close()
    return [dict(row) for row in rows]


def get_solution_by_id(solution_id):
    """Return a solution by ID."""
    if not solution_id:
        return None

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM solution
        WHERE solution_id = ?
          AND is_active = 1
        """,
        (solution_id,),
    )

    row = cursor.fetchone()
    connection.close()
    return dict(row) if row else None


def get_solution_priority_label(priority):
    """Normalize solution priority label for display."""
    if not priority:
        return "Medium"

    mapping = {
        "low": "Low",
        "medium": "Medium",
        "high": "High",
        "critical": "Critical",
    }
    return mapping.get(str(priority).lower(), "Medium")


def display_diagnostic_solution(solution, tree_code=None, diagnostic_path=None, issue_title=None):
    """Display a terminal solution from the relational solution table."""
    if not solution:
        st.error("No solution record was found for this diagnostic result.")
        return

    priority = get_solution_priority_label(solution.get("priority_recommendation"))

    render_mvp_flow_steps("solution")
    st.success(f"✅ Recommended Solution: {solution.get('title', 'Solution')}")

    if solution.get("summary"):
        st.write(solution["summary"])

    show_priority_badge(priority)

    if solution.get("escalation_required"):
        st.warning("🚨 Escalation recommended")
        if solution.get("escalation_notes"):
            st.write(solution["escalation_notes"])
    else:
        st.info("This solution can usually be attempted before escalation.")

    st.write("**Resolution Steps:**")
    audience = get_current_diagnostic_audience()

    if audience in ["admin", "technician"]:
        technician_steps = get_solution_steps_for_exact_audience(
            solution.get("solution_id"),
            "technician",
        )
        escalation_notes = get_solution_steps_for_exact_audience(
            solution.get("solution_id"),
            "admin",
        )

        if technician_steps:
            st.write("**IT Support Specialist steps (Tier 1 / junior Tier 2):**")
            for step in technician_steps:
                st.write("-", step)

        if escalation_notes:
            st.write("**Escalation notes / Tier 2-3 handoff:**")
            for step in escalation_notes:
                st.write("-", step)

        normalized_steps = technician_steps or escalation_notes
    else:
        normalized_steps = get_solution_steps_by_audience(solution.get("solution_id"), audience)
        if normalized_steps:
            for step in normalized_steps:
                st.write("-", step)

    if not normalized_steps:
        for step in str(solution.get("resolution_steps", "")).splitlines():
            clean_step = step.strip()
            if clean_step:
                st.write("-", clean_step)

    st.divider()
    st.write("**Did this solve the issue?**")

    col_yes, col_no = st.columns(2)

    with col_yes:
        if st.button("✅ Yes, issue resolved", key=f"resolved_{solution.get('solution_code')}"):
            session_id = st.session_state.get(f"diagnostic_session_id_{tree_code}", "")
            log_troubleshooting_event(
                session_id,
                None,
                "SOLUTION_FIXED",
                solution.get("title", "Solution marked fixed"),
            )
            update_troubleshooting_session(session_id, status="Resolved")
            st.success("Great. No ticket is needed if the issue is resolved.")

    with col_no:
        if st.button("🎫 No, create a support ticket", key=f"create_ticket_{solution.get('solution_code')}"):
            session_id = st.session_state.get(f"diagnostic_session_id_{tree_code}", "")
            log_troubleshooting_event(
                session_id,
                None,
                "SOLUTION_FAILED",
                solution.get("title", "Solution did not fix the issue"),
            )
            diagnostic_context = build_diagnostic_ticket_context(
                tree_code,
                solution,
                diagnostic_path or [],
                issue_title=issue_title,
            )

            original_issue_title = issue_title or diagnostic_context.get("issue_title") or "Support issue"
            recommended_steps = get_solution_steps_for_ticket_context(
                solution.get("solution_id"),
                get_current_diagnostic_audience(),
            )

            diagnostic_path_text = "\n".join(
                [f"- {step}" for step in diagnostic_context.get("diagnostic_path", [])]
            ) or "- No diagnostic path captured."

            recommended_steps_text = "\n".join(
                [f"- {step}" for step in recommended_steps]
            ) or "- No recommended steps captured."

            st.session_state["prefill_ticket_issue"] = original_issue_title
            st.session_state["prefill_ticket_description"] = (
                f"Problem reported: {original_issue_title}\n\n"
                f"Guided troubleshooting was completed, but the issue is still not resolved.\n\n"
                f"Recommended solution shown: {solution.get('title', '')}\n"
                f"Solution summary: {solution.get('summary', '')}\n\n"
                f"Diagnostic path followed:\n"
                f"{diagnostic_path_text}\n\n"
                f"Recommended steps already suggested:\n"
                f"{recommended_steps_text}\n\n"
                f"Please review and continue troubleshooting."
            )
            st.session_state["prefill_ticket_severity"] = priority if priority in ["Low", "Medium", "High"] else "High"
            st.session_state["prefill_diagnostic_context"] = diagnostic_context
            navigate_to_mode("🎫 Create Ticket")


def run_relational_diagnostic_tree(tree_code, issue_title=None):
    """Run a database-driven diagnostic tree."""
    root = get_diagnostic_root_node(tree_code)

    if not root:
        st.error("No diagnostic tree found for this issue.")
        return

    session_key = f"diagnostic_current_node_{tree_code}"
    path_key = f"diagnostic_path_{tree_code}"
    audit_session_key = f"diagnostic_session_id_{tree_code}"
    viewed_solution_key = f"diagnostic_solution_viewed_{tree_code}"

    if session_key not in st.session_state:
        st.session_state[session_key] = root["diagnostic_node_id"]
        st.session_state[path_key] = []
        st.session_state[audit_session_key] = create_troubleshooting_session(
            tree_code,
            root["diagnostic_node_id"],
            issue_title=issue_title,
        )
        st.session_state[viewed_solution_key] = set()
        log_troubleshooting_event(
            st.session_state[audit_session_key],
            root["diagnostic_node_id"],
            "SESSION_STARTED",
            issue_title or root.get("title", tree_code),
        )

    st.subheader(f"🧭 {issue_title or root.get('title', 'Guided Diagnostic')}")
    render_mvp_flow_steps("question")

    current_audience = get_current_diagnostic_audience()
    st.caption(f"Diagnostic audience: {get_audience_display_name(current_audience)}")

    if st.button("🔄 Restart diagnostic", key=f"restart_diag_{tree_code}"):
        previous_session_id = st.session_state.get(audit_session_key, "")
        previous_node_id = st.session_state.get(session_key)
        log_troubleshooting_event(
            previous_session_id,
            previous_node_id,
            "SESSION_RESTARTED",
            "User restarted diagnostic flow.",
        )
        update_troubleshooting_session(previous_session_id, status="Abandoned")
        st.session_state[session_key] = root["diagnostic_node_id"]
        st.session_state[path_key] = []
        st.session_state[audit_session_key] = create_troubleshooting_session(
            tree_code,
            root["diagnostic_node_id"],
            issue_title=issue_title,
        )
        st.session_state[viewed_solution_key] = set()
        log_troubleshooting_event(
            st.session_state[audit_session_key],
            root["diagnostic_node_id"],
            "SESSION_STARTED",
            issue_title or root.get("title", tree_code),
        )
        st.rerun()

    current_node = get_diagnostic_node(st.session_state[session_key])

    if not current_node:
        st.error("Diagnostic node could not be loaded.")
        return

    # Root/category nodes usually just introduce the tree. Move automatically to first child.
    if current_node["node_type"] == "category":
        if current_node.get("description"):
            st.info(current_node["description"])

        children = get_child_diagnostic_nodes(current_node["diagnostic_node_id"])

        if not children:
            st.warning("This diagnostic tree has no questions yet.")
            return

        first_child = children[0]
        log_troubleshooting_event(
            st.session_state.get(audit_session_key, ""),
            current_node["diagnostic_node_id"],
            "CATEGORY_SELECTED",
            current_node.get("title", "Category selected"),
        )
        update_troubleshooting_session(
            st.session_state.get(audit_session_key, ""),
            current_node_id=first_child["diagnostic_node_id"],
            status="In Progress",
        )
        st.session_state[session_key] = first_child["diagnostic_node_id"]
        st.rerun()

    if current_node["node_type"] == "solution":
        solution = get_solution_by_id(current_node.get("solution_id"))
        viewed_solutions = st.session_state.setdefault(viewed_solution_key, set())
        if current_node["diagnostic_node_id"] not in viewed_solutions:
            log_troubleshooting_event(
                st.session_state.get(audit_session_key, ""),
                current_node["diagnostic_node_id"],
                "SOLUTION_VIEWED",
                solution.get("title", "Solution viewed") if solution else current_node.get("title", "Solution viewed"),
            )
            update_troubleshooting_session(
                st.session_state.get(audit_session_key, ""),
                current_node_id=current_node["diagnostic_node_id"],
                status="Solution Viewed",
            )
            viewed_solutions.add(current_node["diagnostic_node_id"])

        if current_node.get("condition_label") and current_node.get("condition_value"):
            st.caption(f"Based on: {current_node['condition_label']} → {current_node['condition_value']}")

        display_diagnostic_solution(
            solution,
            tree_code,
            st.session_state.get(path_key, []),
            issue_title=issue_title,
        )

        with st.expander("Diagnostic path"):
            for step in st.session_state.get(path_key, []):
                st.write(f"- {step}")

        return

    # Question/check/instruction nodes.
    diagnostic_path = st.session_state.get(path_key, [])
    if diagnostic_path:
        st.caption("Breadcrumb: " + " › ".join(diagnostic_path[-3:]))

    if current_node.get("title"):
        st.markdown(f"### {current_node['title']}")

    if current_node.get("description"):
        st.write(current_node["description"])

    prompt = current_node.get("prompt_text") or "Choose the option that best matches the situation:"
    st.write(f"**{prompt}**")

    children = get_child_diagnostic_nodes(current_node["diagnostic_node_id"])

    if not children:
        st.warning("No next diagnostic steps are configured for this node.")
        return

    option_labels = []
    option_by_label = {}

    for child in children:
        label = child.get("condition_value") or child.get("title") or f"Option {child['diagnostic_node_id']}"

        # Keep labels unique for Streamlit radio.
        display_label = label
        counter = 2
        while display_label in option_by_label:
            display_label = f"{label} ({counter})"
            counter += 1

        option_labels.append(display_label)
        option_by_label[display_label] = child

    selected_label = st.radio(
        "Select an answer",
        option_labels,
        index=None,
        key=f"diag_answer_{current_node['diagnostic_node_id']}",
    )

    if selected_label is None:
        st.info("Select an answer to continue.")
        return

    selected_child = option_by_label[selected_label]

    if st.button("Continue", key=f"diag_continue_{current_node['diagnostic_node_id']}"):
        condition_value = selected_child.get("condition_value") or selected_label
        event_note = f"{prompt} → {condition_value}"
        st.session_state[path_key].append(event_note)
        log_troubleshooting_event(
            st.session_state.get(audit_session_key, ""),
            current_node["diagnostic_node_id"],
            "SYMPTOM_SELECTED",
            event_note,
        )
        update_troubleshooting_session(
            st.session_state.get(audit_session_key, ""),
            current_node_id=selected_child["diagnostic_node_id"],
            status="In Progress",
        )
        st.session_state[session_key] = selected_child["diagnostic_node_id"]
        st.rerun()

# -----------------------------
# LEGACY GUIDED TROUBLESHOOTING DATA
# -----------------------------
# Kept only as historical/reference data during migration.
# The active Guided Troubleshooting page now uses relational diagnostic trees.
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



def get_relational_diagnostic_issue_titles():
    """Return Knowledge Base issue titles that have relational diagnostic trees."""
    titles = []

    for issue in issues:
        tree_code = issue.get("problem_code") or PROBLEM_CODE_BY_ISSUE_TITLE.get(issue.get("title")) or make_problem_code(issue.get("title"))
        if diagnostic_tree_exists(tree_code):
            titles.append(issue.get("title"))

    return titles


def show_no_diagnostic_tree_message(issue):
    """Show a clear fallback message when no relational diagnostic tree exists."""
    st.warning("No database-driven diagnostic tree is available for this issue yet.")

    st.info(
        "You can still review the Knowledge Base guidance below. "
        "If the issue continues, create a support ticket and include what was already tried."
    )

    st.write("**Knowledge Base Guidance:**")
    show_role_based_steps(issue)

    if issue.get("causes"):
        with st.expander("Possible causes"):
            for cause in issue.get("causes", []):
                st.write("-", cause)

def show_guided_troubleshooting():
    st.title("🧭 Guided Troubleshooting Assistant")
    render_mvp_flow_steps("category")

    if MVP_CONTENT_FOCUS_ENABLED:
        st.info(MVP_CONTENT_FOCUS_NOTE)

    visible_issues = filter_visible_mvp_issues(issues)
    diagnostic_issue_titles = get_relational_diagnostic_issue_titles()

    if diagnostic_issue_titles:
        st.caption(
            f"Database-driven diagnostics available for {len(diagnostic_issue_titles)} issue(s)."
        )
    else:
        st.warning("No database-driven diagnostic trees are available yet.")

    categories = sorted({issue.get("category", "Other") for issue in visible_issues if issue.get("category")})
    if not categories:
        st.warning("No visible MVP troubleshooting issues are currently available.")
        return

    if "Other" not in categories:
        categories.append("Other")

    selected_category = st.selectbox(
        "1. Select problem category",
        categories,
        help="Start with the broad area of the problem. This keeps the demo flow clear and portfolio-friendly.",
        key="guided_problem_category",
    )

    category_issues = [
        issue for issue in visible_issues
        if issue.get("category", "Other") == selected_category
    ]

    issue_options = [issue["title"] for issue in category_issues]
    selected_issue = st.selectbox(
        "2. Select the issue that best matches the symptom",
        ["Other / Not listed"] + issue_options,
        help="Choose the closest match. If nothing fits, create a ticket with your own description.",
        key="guided_issue_selection",
    )

    if selected_issue == "Other / Not listed":
        st.info("This issue is not in the guided tree yet. Create a ticket and describe what is happening.")
        if st.button("Create ticket for an unlisted issue", key="create_unlisted_ticket_from_guided"):
            st.session_state["prefill_ticket_issue"] = f"{selected_category} issue - not listed"
            st.session_state["prefill_ticket_description"] = (
                f"Problem category: {selected_category}\n\n"
                "The issue was not listed in Guided Troubleshooting. Please review and continue troubleshooting."
            )
            st.session_state["prefill_ticket_severity"] = "Medium"
            st.session_state["prefill_diagnostic_context"] = {}
            navigate_to_mode("🎫 Create Ticket")
        return

    issue = find_issue_by_title(selected_issue)

    if not issue:
        st.error("Issue not found in the Knowledge Base.")
        return

    tree_code = issue.get("problem_code") or PROBLEM_CODE_BY_ISSUE_TITLE.get(selected_issue) or make_problem_code(selected_issue)

    st.divider()

    if diagnostic_tree_exists(tree_code):
        st.caption("Using reusable database-driven diagnostic page.")
        run_relational_diagnostic_tree(tree_code, selected_issue)
        return

    show_no_diagnostic_tree_message(issue)


# -----------------------------
# RELATIONAL KNOWLEDGE BASE ACCESS
# -----------------------------
def make_problem_code(title):
    """Create a stable fallback problem code from a title."""
    clean_title = re.sub(r"[^A-Za-z0-9]+", "_", title or "").strip("_").upper()
    return clean_title or "UNNAMED_PROBLEM"


def get_kb_child_values(cursor, table_name, column_name, kb_article_id):
    """Return ordered child values for a KB article."""
    cursor.execute(
        f"""
        SELECT {column_name}
        FROM {table_name}
        WHERE kb_article_id = ?
        ORDER BY sort_order, {column_name}
        """,
        (kb_article_id,),
    )
    return [row[column_name] for row in cursor.fetchall()]


def load_issues_from_relational_kb():
    """Load Knowledge Base articles from the normalized relational KB tables.

    Returns issue dictionaries compatible with the existing UI.
    """
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            p.problem_id,
            p.problem_code,
            p.title AS problem_title,
            p.category,
            p.severity,
            p.description AS problem_description,
            kb.kb_article_id,
            kb.title AS kb_title,
            kb.summary,
            kb.difficulty,
            kb.estimated_time,
            kb.escalation_required,
            kb.escalation_notes,
            kb.updated_at AS kb_updated_at
        FROM kb_article kb
        JOIN problem p
            ON kb.problem_id = p.problem_id
        WHERE p.is_active = 1
          AND kb.is_active = 1
        ORDER BY p.category, p.title
        """
    )

    rows = cursor.fetchall()
    relational_issues = []

    for row in rows:
        kb_article_id = row["kb_article_id"]

        tags = get_kb_child_values(cursor, "kb_article_tag", "tag", kb_article_id)
        symptoms = get_kb_child_values(cursor, "kb_article_symptom", "symptom", kb_article_id)
        causes = get_kb_child_values(cursor, "kb_article_cause", "cause", kb_article_id)
        user_steps = get_kb_child_values(cursor, "kb_article_user_step", "step_text", kb_article_id)
        it_steps = get_kb_child_values(cursor, "kb_article_it_step", "step_text", kb_article_id)

        relational_issues.append(
            {
                "problem_id": row["problem_id"],
                "problem_code": row["problem_code"],
                "title": row["problem_title"],
                "category": row["category"],
                "severity": row["severity"],
                "summary": row["summary"],
                "tags": tags,
                "symptoms": symptoms,
                "causes": causes,
                "user_steps": user_steps,
                "it_steps": it_steps,
                "steps": it_steps or user_steps,
                "difficulty": row["difficulty"] or "Beginner",
                "estimated_time": row["estimated_time"] or "5 minutes",
                "applies_to": tags,
                "escalation_required": bool(row["escalation_required"]),
                "escalation_notes": row["escalation_notes"] or "",
                "last_updated": row["kb_updated_at"] or "",
            }
        )

    connection.close()
    return relational_issues


def delete_kb_child_rows(cursor, kb_article_id):
    """Delete child rows for a KB article before rewriting them."""
    child_tables = [
        "kb_article_tag",
        "kb_article_symptom",
        "kb_article_cause",
        "kb_article_user_step",
        "kb_article_it_step",
    ]

    for table_name in child_tables:
        cursor.execute(
            f"DELETE FROM {table_name} WHERE kb_article_id = ?",
            (kb_article_id,),
        )


def insert_kb_child_rows(cursor, table_name, column_name, kb_article_id, values):
    """Insert ordered child rows for a KB article."""
    clean_values = [value.strip() for value in values if str(value).strip()]

    cursor.executemany(
        f"""
        INSERT INTO {table_name} (
            kb_article_id,
            {column_name},
            sort_order
        )
        VALUES (?, ?, ?)
        """,
        [
            (kb_article_id, value, index)
            for index, value in enumerate(clean_values, start=1)
        ],
    )


def upsert_relational_kb_article(issue):
    """Insert or update one issue in the normalized relational KB tables."""
    title = issue.get("title", "").strip()
    if not title:
        return

    problem_code = issue.get("problem_code") or PROBLEM_CODE_BY_ISSUE_TITLE.get(title) or make_problem_code(title)

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO problem (
            problem_code,
            title,
            category,
            severity,
            description,
            is_active,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_code) DO UPDATE SET
            title = excluded.title,
            category = excluded.category,
            severity = excluded.severity,
            description = excluded.description,
            is_active = 1,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            problem_code,
            title,
            issue.get("category", "Uncategorized"),
            issue.get("severity", "Medium"),
            issue.get("summary") or f"{title} troubleshooting article.",
        ),
    )

    cursor.execute(
        "SELECT problem_id FROM problem WHERE problem_code = ?",
        (problem_code,),
    )
    problem_row = cursor.fetchone()

    if not problem_row:
        connection.close()
        return

    problem_id = problem_row["problem_id"]

    cursor.execute(
        """
        INSERT INTO kb_article (
            problem_id,
            title,
            summary,
            difficulty,
            estimated_time,
            escalation_required,
            escalation_notes,
            is_active,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title = excluded.title,
            summary = excluded.summary,
            difficulty = excluded.difficulty,
            estimated_time = excluded.estimated_time,
            escalation_required = excluded.escalation_required,
            escalation_notes = excluded.escalation_notes,
            is_active = 1,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            problem_id,
            title,
            issue.get("summary") or f"{title} troubleshooting article.",
            issue.get("difficulty", "Beginner"),
            issue.get("estimated_time", "5 minutes"),
            1 if issue.get("escalation_required") else 0,
            issue.get("escalation_notes", ""),
        ),
    )

    cursor.execute(
        "SELECT kb_article_id FROM kb_article WHERE problem_id = ?",
        (problem_id,),
    )
    article_row = cursor.fetchone()

    if not article_row:
        connection.close()
        return

    kb_article_id = article_row["kb_article_id"]

    delete_kb_child_rows(cursor, kb_article_id)

    insert_kb_child_rows(cursor, "kb_article_tag", "tag", kb_article_id, issue.get("tags", []))
    insert_kb_child_rows(cursor, "kb_article_symptom", "symptom", kb_article_id, issue.get("symptoms", []))
    insert_kb_child_rows(cursor, "kb_article_cause", "cause", kb_article_id, issue.get("causes", []))
    insert_kb_child_rows(cursor, "kb_article_user_step", "step_text", kb_article_id, issue.get("user_steps", []))
    insert_kb_child_rows(cursor, "kb_article_it_step", "step_text", kb_article_id, issue.get("it_steps") or issue.get("steps", []))

    connection.commit()
    connection.close()


def deactivate_relational_kb_article(title):
    """Deactivate a KB article/problem by title without deleting diagnostic history."""
    problem_code = PROBLEM_CODE_BY_ISSUE_TITLE.get(title) or make_problem_code(title)

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE kb_article
        SET is_active = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE problem_id = (
            SELECT problem_id
            FROM problem
            WHERE problem_code = ?
        )
        """,
        (problem_code,),
    )

    cursor.execute(
        """
        UPDATE problem
        SET is_active = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE problem_code = ?
        """,
        (problem_code,),
    )

    connection.commit()
    connection.close()


def sync_relational_kb_from_issues():
    """Sync the current in-memory issues list into relational KB tables."""
    for issue in issues:
        upsert_relational_kb_article(issue)

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
    """Delete one issue from the legacy table and deactivate it in relational KB."""
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM issues WHERE title = ?", (title,))
    connection.commit()
    connection.close()

    deactivate_relational_kb_article(title)


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
    """Load Knowledge Base issues from the normalized relational KB when available."""
    relational_issues = load_issues_from_relational_kb()

    if relational_issues:
        visible_relational_issues = filter_visible_mvp_issues(relational_issues)
        issues.clear()
        issues.extend(visible_relational_issues)
        st.session_state["issues"] = issues
        return

    # Fallback for older databases that do not have relational KB rows yet.
    seed_issues_if_empty()
    db_issues = load_issues_from_db()

    if db_issues:
        visible_db_issues = filter_visible_mvp_issues(db_issues)
        issues.clear()
        issues.extend(visible_db_issues)
        st.session_state["issues"] = issues


def save_issues():
    """Save the full Knowledge Base to legacy and relational SQLite tables."""
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM issues")
    connection.commit()
    connection.close()

    for issue in issues:
        save_issue_to_db(issue)

    sync_relational_kb_from_issues()


# -----------------------------
# KNOWLEDGE BASE MODE
# -----------------------------
def show_knowledge_base():
    st.title("🔧 IT Troubleshooting Knowledge Base")

    if MVP_CONTENT_FOCUS_ENABLED:
        st.info(MVP_CONTENT_FOCUS_NOTE)

    st.subheader("⭐ Featured MVP Issue")
    common_titles = [
        "Printer Failure",
        "Password Reset Request",
        "Account Locked",
        "Multi-factor Authentication Issue",
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
        key="kb_search_query",
    )

    selected_category = st.selectbox("Filter by Category", get_categories(), key="kb_filter_category")
    selected_severity = st.selectbox("Filter by Severity", ["All", "Low", "Medium", "High"], key="kb_filter_severity")

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
        errors.append("At least one IT Support Specialist step is required.")
    if title.strip() and find_issue_by_title(title.strip()):
        errors.append("An issue with this title already exists.")

    return errors


def show_admin_kb_editor():
    require_admin()
    st.title("🛠 IT Support Knowledge Base Editor")

    st.info("Add or prototype troubleshooting issues without editing the Python code.")

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
        steps_text = st.text_area("IT Support Specialist Steps", placeholder="Enter Tier 1 / junior Tier 2 troubleshooting steps, one per line", key="kb_steps")

        submitted = st.form_submit_button("Add Issue", key="add_issue_submit")

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

def get_ticket_widget_key(ticket, fallback_index=None):
    """Return a stable, safe key fragment for ticket widgets.

    Streamlit widget keys should not depend only on the visible row number because
    filtering/sorting can move tickets around between reruns. This helper prefers
    database IDs and falls back to a stable ticket ID when available.
    """
    raw_key = (
        ticket.get("db_id")
        or ticket.get("ticket_id")
        or ticket.get("id")
        or ticket.get("created_at")
        or fallback_index
        or uuid.uuid4().hex
    )
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(raw_key))


def get_status_stage_index(status):
    """Return the progress-stage index for the current ticket status."""
    ordered_statuses = ["Open", "Assigned", "In Progress", "Waiting on User", "Resolved", "Closed"]
    normalized = normalize_ticket_status(status)
    return ordered_statuses.index(normalized) if normalized in ordered_statuses else 0


def render_ticket_status_tracker(status):
    """Render a compact status tracker for reviewers and support agents."""
    stages = ["Open", "Assigned", "In Progress", "Waiting on User", "Resolved", "Closed"]
    current_index = get_status_stage_index(status)

    cols = st.columns(len(stages))
    for index, (col, stage) in enumerate(zip(cols, stages)):
        is_current = index == current_index
        is_done = index < current_index or status == "Closed"
        marker = "Done" if is_done else ("Now" if is_current else "Next")
        border_color = "#22c55e" if is_done else ("#4e89ff" if is_current else "#d8dee9")
        background = "#f0fdf4" if is_done else ("#eef5ff" if is_current else "#ffffff")
        col.markdown(
            f"""
            <div style="padding:0.6rem; border:1px solid {border_color}; background:{background}; border-radius:10px; text-align:center; min-height:68px;">
                <div style="font-size:0.72rem; color:#6b7280; font-weight:700;">{marker}</div>
                <div style="font-size:0.78rem; color:#374151; font-weight:600;">{stage}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def get_effective_ticket_status(previous_status, selected_status, assigned_to):
    """Automatically move newly assigned open tickets into Assigned status.

    Support agents can still manually choose In Progress, Waiting on User,
    Resolved, or Closed. This helper only handles the common case where an
    agent assigns an Open ticket and forgets to change the Status dropdown.
    """
    normalized_status = normalize_ticket_status(selected_status)

    if (
        previous_status == "Open"
        and normalized_status == "Open"
        and assigned_to
        and assigned_to != "Unassigned"
    ):
        return "Assigned"

    return normalized_status


def validate_ticket_update(previous_status, new_status, new_assigned_to, new_resolution_notes):
    """Return validation messages before saving an admin ticket update."""
    errors = []
    warnings = []

    cleaned_notes = (new_resolution_notes or "").strip()

    if new_status in {"Resolved", "Closed"} and not cleaned_notes:
        errors.append("Add resolution notes before marking a ticket Resolved or Closed.")

    if new_status == "Closed" and previous_status not in {"Resolved", "Closed"}:
        warnings.append("This closes the ticket directly. For a realistic support workflow, consider moving it to Resolved first.")

    if new_status == "Waiting on User" and not cleaned_notes:
        warnings.append("Add a short note explaining what information is needed from the user.")

    return errors, warnings


def apply_ticket_status_timestamps(ticket, previous_status, new_status):
    """Apply lifecycle timestamps when status changes."""
    now = get_current_timestamp()

    if new_status == "Assigned" and not ticket.get("assigned_at"):
        ticket["assigned_at"] = now
    if new_status == "Waiting on User" and not ticket.get("waiting_on_user_at"):
        ticket["waiting_on_user_at"] = now
    if new_status == "Resolved" and not ticket.get("resolved_at"):
        ticket["resolved_at"] = now
    if new_status == "Closed" and not ticket.get("closed_at"):
        ticket["closed_at"] = now
    if previous_status in {"Resolved", "Closed"} and new_status not in {"Resolved", "Closed"}:
        ticket["reopened_at"] = now


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
            "diagnostic_context": {},
            "business_impact": row_dict.get("business_impact", ""),
            "contact_method": row_dict.get("contact_method", ""),
            "device_or_location": row_dict.get("device_or_location", ""),
            "troubleshooting_session_id": row_dict.get("troubleshooting_session_id", ""),
            "troubleshooting_summary_snapshot": row_dict.get("troubleshooting_summary_snapshot", ""),
            "admin_unread_type": "new_ticket",
            "user_unread_type": "",
        })

    st.session_state["tickets"] = loaded_tickets


TICKET_STORAGE_COLUMNS = [
    "username",
    "email",
    "issue",
    "description",
    "severity",
    "priority",
    "status",
    "assigned_to",
    "resolution_notes",
    "likely_infrastructure",
    "unread_for_admin",
    "unread_for_user",
    "business_impact",
    "contact_method",
    "device_or_location",
    "troubleshooting_session_id",
    "troubleshooting_summary_snapshot",
    "ticket_data",
]


def prepare_ticket_for_storage(ticket):
    """Return a normalized ticket payload and SQL values.

    Step 4 keeps the database safer by storing each ticket individually instead
    of deleting and rewriting the entire tickets table on every save.
    """
    ticket.setdefault("created_at", get_current_timestamp())
    ticket["updated_at"] = get_current_timestamp()

    ticket_data = json.dumps(ticket, indent=4)

    values = {
        "username": ticket.get("username") or ticket.get("name", ""),
        "email": ticket.get("email", ""),
        "issue": ticket.get("issue", ""),
        "description": ticket.get("description", ""),
        "severity": ticket.get("severity", "Medium"),
        "priority": ticket.get("priority", "Medium"),
        "status": ticket.get("status", "Open"),
        "assigned_to": ticket.get("assigned_to", "Unassigned"),
        "resolution_notes": ticket.get("resolution_notes", ""),
        "likely_infrastructure": 1 if ticket.get("likely_infrastructure") else 0,
        "unread_for_admin": 1 if ticket.get("unread_for_admin") else 0,
        "unread_for_user": 1 if ticket.get("unread_for_user") else 0,
        "business_impact": ticket.get("business_impact", ""),
        "contact_method": ticket.get("contact_method", ""),
        "device_or_location": ticket.get("device_or_location", ""),
        "troubleshooting_session_id": ticket.get("troubleshooting_session_id", ""),
        "troubleshooting_summary_snapshot": ticket.get("troubleshooting_summary_snapshot", ""),
        "ticket_data": ticket_data,
    }
    return values


def save_ticket_record(cursor, ticket):
    """Insert or update one ticket without clearing unrelated database rows."""
    values = prepare_ticket_for_storage(ticket)
    db_id = ticket.get("db_id")

    if db_id:
        set_clause = ", ".join([f"{column} = ?" for column in TICKET_STORAGE_COLUMNS])
        cursor.execute(
            f"UPDATE tickets SET {set_clause} WHERE id = ?",
            [values[column] for column in TICKET_STORAGE_COLUMNS] + [db_id],
        )

        if cursor.rowcount:
            return db_id

    placeholders = ", ".join(["?"] * len(TICKET_STORAGE_COLUMNS))
    column_list = ", ".join(TICKET_STORAGE_COLUMNS)
    cursor.execute(
        f"INSERT INTO tickets ({column_list}) VALUES ({placeholders})",
        [values[column] for column in TICKET_STORAGE_COLUMNS],
    )
    ticket["db_id"] = cursor.lastrowid

    # Store the db_id inside ticket_data after the database assigns it.
    values = prepare_ticket_for_storage(ticket)
    cursor.execute(
        "UPDATE tickets SET ticket_data = ? WHERE id = ?",
        (values["ticket_data"], ticket["db_id"]),
    )
    return ticket["db_id"]


def save_tickets():
    """Save tickets from session state into SQLite without deleting history.

    Earlier versions rewrote the whole tickets table. This version upserts each
    known ticket, which is safer for demos and avoids accidental data loss if the
    app is interrupted while saving.
    """
    tickets = st.session_state.get("tickets", [])

    connection = get_db_connection()
    cursor = connection.cursor()

    for ticket in tickets:
        save_ticket_record(cursor, ticket)

    connection.commit()
    connection.close()


def insert_ticket_directly(ticket):
    """Insert one new ticket directly into SQLite and update its db_id."""
    connection = get_db_connection()
    cursor = connection.cursor()
    db_id = save_ticket_record(cursor, ticket)
    connection.commit()
    connection.close()
    return db_id

def delete_ticket_from_storage(ticket):
    """Delete one ticket and its related comments/attachment metadata from SQLite."""
    db_id = ticket.get("db_id")
    if not db_id:
        return False

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM ticket_comments WHERE ticket_id = ?", (db_id,))
    cursor.execute("DELETE FROM ticket_attachments WHERE ticket_id = ?", (db_id,))
    cursor.execute("DELETE FROM tickets WHERE id = ?", (db_id,))
    deleted = cursor.rowcount > 0
    connection.commit()
    connection.close()
    return deleted


def delete_ticket_attachment_files(ticket):
    """Best-effort cleanup for files attached to a deleted test ticket."""
    for attachment in ticket.get("attachments", []):
        candidate_paths = []
        if attachment.get("path"):
            candidate_paths.append(attachment.get("path"))
        if attachment.get("saved_name"):
            candidate_paths.append(os.path.join(UPLOAD_FOLDER, attachment.get("saved_name")))

        for file_path in candidate_paths:
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
            except OSError:
                pass


def delete_ticket(ticket):
    """Delete one ticket from session state and persistent storage."""
    deleted = delete_ticket_from_storage(ticket)
    delete_ticket_attachment_files(ticket)

    db_id = ticket.get("db_id")
    st.session_state["tickets"] = [
        existing_ticket
        for existing_ticket in st.session_state.get("tickets", [])
        if existing_ticket.get("db_id") != db_id
    ]
    return deleted

def validate_ticket_submission(issue_title, description, business_impact, contact_method, device_or_location):
    """Validate and normalize ticket form values before saving."""
    normalized = {
        "issue_title": str(issue_title or "").strip(),
        "description": str(description or "").strip(),
        "business_impact": str(business_impact or "").strip(),
        "contact_method": str(contact_method or "").strip(),
        "device_or_location": str(device_or_location or "").strip(),
    }

    errors = []
    if not normalized["issue_title"]:
        errors.append("Issue Title is required.")
    if not normalized["description"]:
        errors.append("Description is required.")
    if normalized["description"] and len(normalized["description"]) < 10:
        errors.append("Description should include at least a brief symptom or error message.")
    if not normalized["business_impact"]:
        errors.append("Business impact is required so support can prioritize the ticket.")
    if not normalized["device_or_location"]:
        errors.append("Device or location is required so support knows where to investigate.")

    return normalized, errors


def show_ticket_form():
    st.title("🎫 Create Support Ticket")
    render_mvp_flow_steps("ticket")

    if "ticket_created_message" in st.session_state:
        st.success(st.session_state.pop("ticket_created_message"))
        target = "📋 View Tickets" if st.session_state.get("role") == "Admin" else "🎟 My Tickets"
        st.info("Open your ticket list to review the submitted troubleshooting trail.")
        if st.button("Open ticket list", key="open_ticket_list_after_create_message"):
            navigate_to_mode(target)

    current_username = st.session_state.get("username", "Unknown")
    current_user = get_user(current_username) or {}
    current_email = current_user.get("email", "")

    st.info(f"Creating ticket as: **{current_username}**")
    if current_email:
        st.caption(f"Email: {current_email}")

    prefill_issue = st.session_state.get("prefill_ticket_issue", "")
    prefill_description = st.session_state.get("prefill_ticket_description", "")
    prefill_severity = st.session_state.get("prefill_ticket_severity", "Medium")
    prefill_diagnostic_context = st.session_state.get("prefill_diagnostic_context", {})

    severity_options = ["Low", "Medium", "High"]
    if prefill_severity not in severity_options:
        prefill_severity = "Medium"

    if prefill_diagnostic_context:
        st.success("This ticket is linked to a guided troubleshooting session. The trail will be saved with the ticket.")
        with st.expander("Preview troubleshooting trail", expanded=False):
            snapshot = build_troubleshooting_summary_snapshot(prefill_diagnostic_context)
            st.text(snapshot or "No troubleshooting trail was captured yet.")
    else:
        st.info("💡 If you are not sure how to fix the issue, try Guided Troubleshooting before creating a ticket.")

    with st.form("ticket_form"):
        issue_title = st.text_input("Issue Title", value=prefill_issue, key="ticket_issue_title")
        description = st.text_area("Describe the issue", value=prefill_description, key="ticket_description")
        business_impact = st.text_area(
            "Business impact",
            placeholder="Example: I cannot print shipping labels for customer orders.",
            key="ticket_business_impact",
        )
        contact_method = st.selectbox(
            "Preferred contact method",
            ["Email", "Phone", "Chat", "In person"],
            key="ticket_contact_method",
        )
        device_or_location = st.text_input(
            "Device or location",
            placeholder="Example: Laptop asset tag, printer name, office, floor, or room.",
            key="ticket_device_or_location",
        )
        severity = st.selectbox(
            "Severity",
            severity_options,
            index=severity_options.index(prefill_severity),
            key="ticket_severity",
        )
        uploaded_files = st.file_uploader(
            "Attach screenshots or log files (optional)",
            type=["png", "jpg", "jpeg", "txt", "log", "pdf"],
            accept_multiple_files=True,
            key="ticket_attachments",
        )

        submitted = st.form_submit_button("Create Ticket", key="create_ticket_submit")

    if not submitted:
        return

    normalized, validation_errors = validate_ticket_submission(
        issue_title,
        description,
        business_impact,
        contact_method,
        device_or_location,
    )

    if validation_errors:
        for error in validation_errors:
            st.error(error)
        return

    attachments = save_uploaded_attachments(uploaded_files)
    priority = calculate_ticket_priority(normalized["description"], severity)

    troubleshooting_summary_snapshot = build_troubleshooting_summary_snapshot(prefill_diagnostic_context)
    troubleshooting_session_id = prefill_diagnostic_context.get("troubleshooting_session_id", "") if prefill_diagnostic_context else ""

    ticket = {
        "name": current_username,
        "username": current_username,
        "email": current_email,
        "issue": normalized["issue_title"],
        "description": normalized["description"],
        "severity": severity,
        "priority": priority,
        "business_impact": normalized["business_impact"],
        "contact_method": normalized["contact_method"],
        "device_or_location": normalized["device_or_location"],
        "troubleshooting_session_id": troubleshooting_session_id,
        "troubleshooting_summary_snapshot": troubleshooting_summary_snapshot,
        "status": "Open",
        "assigned_to": "Unassigned",
        "resolution_notes": "",
        "assigned_at": "",
        "waiting_on_user_at": "",
        "closed_at": "",
        "suggestions": [],
        "diagnostic_context": prefill_diagnostic_context,
        "likely_infrastructure": is_likely_infrastructure_issue(normalized["description"]),
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

    db_id = insert_ticket_directly(ticket)
    ticket["db_id"] = db_id
    st.session_state["tickets"].insert(0, ticket)

    if troubleshooting_session_id:
        log_troubleshooting_event(
            troubleshooting_session_id,
            None,
            "TICKET_SUBMITTED",
            f"Ticket submitted: {normalized['issue_title']}",
        )
        update_troubleshooting_session(troubleshooting_session_id, status="Ticket Submitted")

    for key in [
        "prefill_ticket_issue",
        "prefill_ticket_description",
        "prefill_ticket_severity",
        "prefill_diagnostic_context",
    ]:
        st.session_state.pop(key, None)

    attachment_note = f" {len(attachments)} attachment(s) saved." if attachments else ""
    st.session_state["ticket_created_message"] = f"✅ Ticket created successfully.{attachment_note}"
    st.rerun()

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
        render_empty_ticket_state(
            "No tickets submitted yet. Start guided troubleshooting first to create a ticket with a useful diagnostic trail.",
            "admin_empty_start_guided",
        )
        return

    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        status_filter = st.selectbox(
            "Filter by status",
            ["All"] + TICKET_STATUSES,
            key="admin_ticket_status_filter",
        )
    with filter_col2:
        priority_filter = st.selectbox(
            "Filter by priority",
            ["All", "Critical", "High", "Medium", "Low"],
            key="admin_ticket_priority_filter",
        )
    with filter_col3:
        diagnostic_filter = st.selectbox(
            "Filter by diagnostic source",
            ["All", "Created after Guided Troubleshooting", "Created manually"],
            key="admin_ticket_diagnostic_filter",
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

    visible_ticket_count = 0

    for i, ticket in enumerate(sorted_tickets, 1):
        if status_filter != "All" and ticket.get("status", "Open") != status_filter:
            continue

        priority = ticket.get("priority", calculate_ticket_priority(ticket.get("description", ""), ticket.get("severity", "Medium")))
        if priority_filter != "All" and priority != priority_filter:
            continue

        has_diagnostic_context = ticket_has_diagnostic_context(ticket)
        if diagnostic_filter == "Created after Guided Troubleshooting" and not has_diagnostic_context:
            continue
        if diagnostic_filter == "Created manually" and has_diagnostic_context:
            continue

        visible_ticket_count += 1
        ticket_key = get_ticket_widget_key(ticket, i)

        status = ticket.get("status", "Open")
        assigned_to = ticket.get("assigned_to", "Unassigned")

        if priority == "Critical":
            st.error(f"🚨 CRITICAL: {ticket['issue']} — {status}")
        elif priority == "High":
            st.warning(f"⚠️ HIGH PRIORITY: {ticket['issue']} — {status}")

        sla_status, _ = get_sla_status(ticket)
        sla_label = f" — SLA: {sla_status}"
        unread_label = get_unread_label(ticket, "admin") if ticket.get("unread_for_admin") else ""
        diagnostic_label = get_diagnostic_ticket_label(ticket)
        with st.expander(f"Ticket {i}: {ticket['issue']} — {status} — {priority}{sla_label}{unread_label}{diagnostic_label}"):
            st.write(f"**Name:** {ticket['name']}")
            st.write(f"**Email:** {ticket['email']}")
            st.write(f"**Severity:** {ticket['severity']}")
            show_priority_badge(priority)
            st.markdown(f"**Priority Label:** {format_priority_text(priority)}", unsafe_allow_html=True)
            show_sla_badge(ticket)
            st.write(f"**Status:** {status}")
            render_ticket_status_tracker(status)
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

            render_ticket_mvp_summary(ticket, i)
            show_ticket_diagnostic_context(ticket)

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
                                key=f"download_db_{ticket_key}_{attachment_index}",
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
                                    key=f"download_{ticket_key}_{attachment_index}",
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
                key=f"status_{ticket_key}",
            )

            assignment_options = ASSIGNMENT_OPTIONS.copy()
            if assigned_to not in assignment_options:
                assignment_options.append(assigned_to)

            new_assigned_to = st.selectbox(
                "Assigned To",
                assignment_options,
                index=assignment_options.index(assigned_to),
                key=f"assigned_{ticket_key}",
            )

            new_priority = st.selectbox(
                "Priority",
                ["Critical", "High", "Medium", "Low"],
                index=["Critical", "High", "Medium", "Low"].index(priority),
                key=f"priority_{ticket_key}",
            )

            template_key = f"resolution_template_{ticket_key}"
            notes_key = f"resolution_{ticket_key}"
            previous_template_key = f"previous_resolution_template_{ticket_key}"

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
                    st.session_state[notes_key] = existing_notes + "\n\n" + template_text

            st.session_state[previous_template_key] = selected_template

            new_resolution_notes = st.text_area(
                "Resolution Notes",
                key=notes_key,
            )

            if st.button("Save Ticket Updates", key=f"save_ticket_{ticket_key}"):
                previous_status = ticket.get("status", "Open")
                previous_assigned_to = ticket.get("assigned_to", "Unassigned")
                previous_priority = ticket.get("priority", "Medium")
                previous_resolution_notes = ticket.get("resolution_notes", "")
                previous_template = ticket.get("selected_resolution_template", "Select a template")

                effective_status = get_effective_ticket_status(
                    previous_status,
                    new_status,
                    new_assigned_to,
                )

                update_errors, update_warnings = validate_ticket_update(
                    previous_status,
                    effective_status,
                    new_assigned_to,
                    new_resolution_notes,
                )

                if update_errors:
                    for error in update_errors:
                        st.error(error)
                    st.stop()

                for warning in update_warnings:
                    st.warning(warning)

                ticket["status"] = effective_status
                ticket["priority"] = new_priority
                ticket["assigned_to"] = new_assigned_to
                ticket["resolution_notes"] = new_resolution_notes
                ticket["selected_resolution_template"] = selected_template
                ticket["updated_at"] = get_current_timestamp()

                apply_ticket_status_timestamps(ticket, previous_status, effective_status)

                if previous_status != effective_status:
                    add_ticket_activity(
                        ticket,
                        "status_change",
                        f"Status changed from {previous_status} to {effective_status}.",
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
                if new_status != effective_status:
                    st.info("Status automatically changed to Assigned because the ticket now has an assignee.")
                st.success("✅ Ticket updated successfully")

            st.divider()
            with st.expander("Danger zone - delete test ticket"):
                st.warning("Use this only for test tickets or mistaken demo entries. Deletion removes the ticket from the database.")
                confirm_delete = st.checkbox(
                    "I understand this will permanently delete this ticket.",
                    key=f"confirm_delete_ticket_{ticket_key}",
                )
                if st.button(
                    "Delete Ticket",
                    key=f"delete_ticket_{ticket_key}",
                    type="secondary",
                    disabled=not confirm_delete,
                ):
                    delete_ticket(ticket)
                    st.success("Ticket deleted.")
                    st.rerun()

            if ticket.get("resolution_notes"):
                st.write("**Saved Resolution Notes:**")
                if ticket.get("selected_resolution_template") and ticket.get("selected_resolution_template") != "Select a template":
                    st.caption(f"Template used: {ticket.get('selected_resolution_template')}")
                st.write(ticket["resolution_notes"])

            show_ticket_comments(ticket, ticket_key)


    if visible_ticket_count == 0:
        st.warning("No tickets match the current filters. Set Status and Priority filters to All to see every ticket.")



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
        key="download_tickets_csv",
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
    diagnostic_tickets = sum(1 for ticket in tickets if ticket_has_diagnostic_context(ticket))
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

    st.info(f"🧭 Tickets from Guided Troubleshooting: {diagnostic_tickets}")

    diagnostic_coverage = len(get_relational_diagnostic_issue_titles())
    st.info(f"🧭 Visible MVP diagnostic trees available for {diagnostic_coverage} focused issue(s).")

    st.divider()

    show_export_tools(tickets)

    st.divider()

    if not tickets:
        st.info("No ticket data available yet.")
        col_demo1, col_demo2 = st.columns(2)

        with col_demo1:
            if st.button("📦 Load sample demo tickets", key="admin_empty_load_sample_tickets"):
                added_count = load_sample_tickets()
                if added_count:
                    st.success(f"✅ Loaded {added_count} sample ticket(s).")
                    st.rerun()
                else:
                    st.info("Sample tickets are already loaded.")

        with col_demo2:
            if st.button("♻️ Reset demo tickets", key="admin_empty_reset_demo_tickets"):
                added_count = reset_demo_tickets()
                st.success(f"✅ Demo reset complete. Loaded {added_count} sample ticket(s).")
                st.rerun()

        return

    with st.expander("🧪 Demo Data Tools"):
        st.caption("Use these tools only for portfolio demos or testing.")

        col_demo1, col_demo2 = st.columns(2)

        with col_demo1:
            if st.button("📦 Load sample demo tickets", key="admin_expander_load_sample_tickets"):
                added_count = load_sample_tickets()
                if added_count:
                    st.success(f"✅ Loaded {added_count} sample ticket(s).")
                    st.rerun()
                else:
                    st.info("Sample tickets are already loaded.")

        with col_demo2:
            if st.button("♻️ Reset demo tickets", key="admin_expander_reset_demo_tickets"):
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
        render_empty_ticket_state(
            "No tickets found for your account. Start guided troubleshooting to capture a trail before escalating to IT.",
            "user_empty_start_guided",
        )
        return

    for i, ticket in enumerate(user_tickets, 1):
        unread_label = get_unread_label(ticket, "user") if ticket.get("unread_for_user") else ""
        with st.expander(f"Ticket {i}: {ticket.get('issue')} — {ticket.get('status', 'Open')}{unread_label}"):
            st.write(f"**Severity:** {ticket.get('severity')}")
            show_priority_badge(ticket.get("priority", "Medium"))
            st.markdown(f"**Priority Label:** {format_priority_text(ticket.get('priority', 'medium'))}", unsafe_allow_html=True)
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

            render_ticket_mvp_summary(ticket, i)
            show_ticket_diagnostic_context(ticket)

            if ticket.get("resolution_notes"):
                st.write("**Resolution Notes:**")
                st.write(ticket["resolution_notes"])

            show_ticket_comments(ticket, f"user_{i}")




def get_portfolio_health_metrics():
    """Return lightweight demo-readiness metrics for the portfolio home page."""
    tickets = st.session_state.get("tickets", [])
    issues_count = len(st.session_state.get("issues", []))
    diagnostic_tickets = sum(1 for ticket in tickets if ticket_has_diagnostic_context(ticket))

    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT COUNT(*) AS count FROM diagnostic_tree WHERE is_active = 1 AND base_tree_code IN ('PRINTER_FAILURE', 'PASSWORD_RESET_REQUEST', 'ACCOUNT_LOCKED', 'MULTI_FACTOR_AUTHENTICATION_ISSUE', 'VPN_CONNECTION_FAILURE')")
        diagnostic_tree_count = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) AS count FROM troubleshooting_event")
        event_count = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) AS count FROM solution_step")
        solution_step_count = cursor.fetchone()["count"]
    except sqlite3.Error:
        diagnostic_tree_count = 0
        event_count = 0
        solution_step_count = 0
    finally:
        connection.close()

    return {
        "issues_count": issues_count,
        "diagnostic_tree_count": diagnostic_tree_count,
        "ticket_count": len(tickets),
        "diagnostic_ticket_count": diagnostic_tickets,
        "event_count": event_count,
        "solution_step_count": solution_step_count,
    }


def render_portfolio_health_snapshot():
    """Show a compact snapshot of why the MVP is portfolio-ready."""
    metrics = get_portfolio_health_metrics()
    st.subheader("Portfolio MVP Snapshot")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Visible MVP issues", metrics["issues_count"])
    col2.metric("Diagnostic trees", metrics["diagnostic_tree_count"])
    col3.metric("Solution steps", metrics["solution_step_count"])
    col4.metric("Audit events", metrics["event_count"])

    if metrics["ticket_count"]:
        st.caption(
            f"Tickets in this local demo database: {metrics['ticket_count']} | "
            f"with guided troubleshooting trail: {metrics['diagnostic_ticket_count']}"
        )
    else:
        st.caption("No tickets have been submitted in this local demo database yet.")

    st.info(
        "For the strongest demo, start with Guided Troubleshooting, view a solution, choose that it did not fix the issue, "
        "then submit a ticket and review the saved trail."
    )



def get_database_readiness_status():
    """Return whether key MVP tables exist in the local SQLite database."""
    expected_tables = [
        "users",
        "diagnostic_node",
        "solution_step",
        "troubleshooting_session",
        "troubleshooting_event",
        "tickets",
    ]

    connection = get_db_connection()
    cursor = connection.cursor()
    existing_tables = set()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        existing_tables = {row["name"] for row in cursor.fetchall()}
    except sqlite3.Error:
        existing_tables = set()
    finally:
        connection.close()

    return {
        table_name: table_name in existing_tables
        for table_name in expected_tables
    }


def build_portfolio_demo_script():
    """Return a concise script the developer can use during portfolio demos."""
    return """Portfolio demo script - IT Support Troubleshooting Portal

1. Log in as a regular user.
2. Open Guided Troubleshooting.
3. Choose a category, such as Printer or Internet / Network.
4. Select a specific issue and answer the guided symptom questions.
5. Review the suggested solution and ordered steps.
6. Choose that the solution did not fix the problem.
7. Submit a support ticket with business impact and device/location details.
8. Open the submitted ticket and show the saved troubleshooting trail.
9. Log in as Admin and confirm the ticket contains enough context for IT support to continue without asking the user to repeat the same troubleshooting steps.

Portfolio explanation:
This app demonstrates a database-driven troubleshooting tree, session/event audit tracking, role-aware support workflows, and unresolved-issue escalation into a ticket with a historical trail snapshot. The ticketing features are intentionally lightweight because the portfolio focus is guided troubleshooting, not building a full help-desk platform.

Tradeoff explanation:
For the MVP, the app uses parent-child diagnostic trees instead of a full reusable graph model. This keeps the project finished, explainable, and demoable while leaving graph reuse, workflow approvals, SLA automation, and enterprise SSO as future enhancements.
"""


def build_portfolio_readme_markdown():
    """Return a README starter that matches the current MVP+ implementation."""
    metrics = get_portfolio_health_metrics()
    return f"""# IT Support Troubleshooting Portal

## Project Overview

This is a guided IT self-service support application built with Python, Streamlit, and SQLite. It helps users troubleshoot common IT issues, view suggested solutions, and escalate unresolved problems into support tickets with the troubleshooting trail attached.

## Problem Being Solved

IT support teams often receive tickets with missing context. This app improves ticket quality by guiding users through a structured troubleshooting flow before escalation. When a user submits a ticket, the app saves the diagnostic trail so IT support can see what was already attempted.

## Key Features

- Local login and role-aware user/support navigation
- Category-first guided troubleshooting
- Database-driven diagnostic trees
- Ordered solution steps for users and technicians
- Troubleshooting session and event audit tracking
- Support ticket submission with business impact and device/location details
- Ticket trail snapshot for unresolved issues
- Lightweight admin ticket review for escalated issues
- Knowledge Base and diagnostic tree viewer

## Tech Stack

- Python
- Streamlit
- SQLite
- HTML/CSS styling inside Streamlit

## Current Demo Metrics

- Visible MVP issues: {metrics['issues_count']}
- Active diagnostic trees: {metrics['diagnostic_tree_count']}
- User and IT Support Specialist solution steps: {metrics['solution_step_count']}
- Troubleshooting audit events: {metrics['event_count']}
- Tickets in local database: {metrics['ticket_count']}
- Tickets with guided troubleshooting trail: {metrics['diagnostic_ticket_count']}

## User Flow

1. User logs in.
2. User starts Guided Troubleshooting.
3. User selects a category and issue.
4. User answers 1-3 symptom questions.
5. App displays a relevant solution with ordered steps.
6. User marks the issue fixed or not fixed.
7. If unresolved, user submits a support ticket.
8. Ticket includes the saved troubleshooting trail.
9. Admin reviews the ticket context and can update the ticket when follow-up is needed.

## Database Design

Core MVP+ tables include:

- `users`
- `problem`
- `solution`
- `diagnostic_tree`
- `diagnostic_node`
- `solution_step`
- `kb_article` and KB child tables
- `troubleshooting_session`
- `troubleshooting_event`
- `tickets`
- `ticket_comments`
- `ticket_attachments`

## Sample Troubleshooting Tree

Example flow:

```text
Printer
└── Printer Failure
    ├── Check power / display / hardware warnings
    ├── Check USB or network reachability
    ├── Check queue / spooler / offline state
    └── Show solution or escalate ticket
```

## Tradeoffs

For the MVP, this project uses a parent-child diagnostic tree instead of a reusable graph model. This keeps routing, database design, and the portfolio demo easier to explain while still proving the core workflow. A future version could introduce a node-link table so symptoms and solutions can be reused across multiple branches.

The project uses local authentication rather than enterprise SSO. That keeps the portfolio app runnable on a local machine while still demonstrating user-specific sessions and tickets.

## Future Enhancements

- Enterprise SSO
- Reusable node-link graph model
- Admin approval workflow for Knowledge Base changes
- Search across tickets and KB articles
- SLA automation and notifications
- Import/export tools for troubleshooting trees
- Dedicated Tier 2/3 role views for Identity, Network, Security, Endpoint, and Systems teams
- Separate reporting or analytics module outside the core MVP

## How to Run Locally

```bash
pip install streamlit
streamlit run app.py
```

Before demoing a new version, back up the local SQLite database:

```bash
cp it_support.db it_support_backup_before_demo.db
```
"""


def build_database_backup_guide():
    """Return plain-text backup and restore guidance for the local SQLite demo database."""
    return f"""Database safety guide - IT Support Troubleshooting Portal

The app uses this local SQLite database file:
{DATABASE_FILE}

Before running a new app version, make a backup:

macOS / Linux / Git Bash:
cp {DATABASE_FILE} it_support_backup_before_update.db

Windows PowerShell:
Copy-Item {DATABASE_FILE} it_support_backup_before_update.db

Windows Command Prompt:
copy {DATABASE_FILE} it_support_backup_before_update.db

To restore a backup, stop Streamlit first, then copy the backup over the active database file.

This app version is designed to use non-destructive migrations such as CREATE TABLE IF NOT EXISTS and ALTER TABLE ADD COLUMN where needed. It should not empty or reset the database during normal startup.
"""


def build_database_erd_mermaid():
    """Return a lightweight Mermaid ERD for README documentation."""
    return """erDiagram
    users ||--o{ troubleshooting_session : starts
    troubleshooting_session ||--o{ troubleshooting_event : records
    troubleshooting_session ||--o{ tickets : escalates
    problem ||--o{ diagnostic_tree : has
    diagnostic_tree ||--o{ diagnostic_node : contains
    diagnostic_node ||--o{ diagnostic_node : branches_to
    solution ||--o{ solution_step : has
    solution ||--o{ diagnostic_node : resolves
    tickets ||--o{ ticket_comments : has
    tickets ||--o{ ticket_attachments : has
"""


def get_database_file_status():
    """Return local database file status for demo safety visibility."""
    if not os.path.exists(DATABASE_FILE):
        return {
            "exists": False,
            "size_kb": 0,
            "modified_at": "Not found",
        }

    stat = os.stat(DATABASE_FILE)
    return {
        "exists": True,
        "size_kb": round(stat.st_size / 1024, 1),
        "modified_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
    }


def render_portfolio_export_pack():
    """Show downloadable reviewer materials and database safety guidance."""
    st.subheader("Reviewer export pack")
    st.caption("Download these starter materials for your GitHub README, demo notes, and project documentation.")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            "Download README starter",
            data=build_portfolio_readme_markdown(),
            file_name="README_portfolio_starter.md",
            mime="text/markdown",
            key="download_readme_portfolio_starter",
        )
    with col2:
        st.download_button(
            "Download database safety guide",
            data=build_database_backup_guide(),
            file_name="database_backup_guide.txt",
            mime="text/plain",
            key="download_database_backup_guide",
        )
    with col3:
        st.download_button(
            "Download Mermaid ERD",
            data=build_database_erd_mermaid(),
            file_name="database_erd.mmd",
            mime="text/plain",
            key="download_database_erd_mermaid",
        )

    db_status = get_database_file_status()
    st.subheader("Local database safety status")
    if db_status["exists"]:
        st.success(
            f"Database file detected: `{DATABASE_FILE}` | Size: {db_status['size_kb']} KB | "
            f"Last modified: {db_status['modified_at']}"
        )
        st.code(f"cp {DATABASE_FILE} it_support_backup_before_demo.db", language="bash")
        st.caption("Stop Streamlit before restoring a backup over the active database file.")
    else:
        st.warning(f"Database file `{DATABASE_FILE}` was not found yet. It is usually created when the app starts.")


def render_demo_readiness_checklist():
    """Show a reviewer-friendly checklist of portfolio readiness signals."""
    metrics = get_portfolio_health_metrics()
    table_status = get_database_readiness_status()

    checklist = [
        (
            "Login and role-aware navigation",
            table_status.get("users", False),
            "Users table exists and the app separates regular-user and admin experiences.",
        ),
        (
            "Database-driven diagnostic tree",
            table_status.get("diagnostic_node", False) and metrics["diagnostic_tree_count"] > 0,
            f"{metrics['diagnostic_tree_count']} active diagnostic tree(s) detected.",
        ),
        (
            "Ordered solution steps",
            table_status.get("solution_step", False) and metrics["solution_step_count"] > 0,
            f"{metrics['solution_step_count']} role-specific solution step(s) detected.",
        ),
        (
            "Session and event tracking",
            table_status.get("troubleshooting_session", False) and table_status.get("troubleshooting_event", False),
            "Troubleshooting session and event tables are available for audit trails.",
        ),
        (
            "Ticket escalation with trail snapshot",
            table_status.get("tickets", False),
            "Tickets can store business impact, device/location, and troubleshooting summary snapshot fields.",
        ),
        (
            "Demo and README-ready explanation",
            True,
            "The Portfolio Demo Guide explains scope, tradeoffs, database design, and future enhancements.",
        ),
    ]

    st.subheader("Demo readiness checklist")
    for label, passed, detail in checklist:
        icon = "✅" if passed else "⚠️"
        st.write(f"{icon} **{label}** — {detail}")

    if all(passed for _, passed, _ in checklist):
        st.success("This local build has the main MVP+ portfolio signals ready for a demo.")
    else:
        st.warning("One or more readiness signals need attention before a polished demo.")

    st.download_button(
        "Download demo script",
        data=build_portfolio_demo_script(),
        file_name="portfolio_demo_script.txt",
        mime="text/plain",
        key="download_portfolio_demo_script",
    )

def show_portfolio_demo_guide():
    """Portfolio reviewer guide explaining the MVP scope, architecture, and tradeoffs."""
    st.title("📘 Portfolio Demo Guide")

    st.markdown(
        """
This page helps a reviewer understand the project quickly without reading the source code first.

**Portfolio statement:** This is a guided IT self-service support app. It uses a database-driven troubleshooting tree, records the user's path through the decision flow, displays relevant solution steps, and escalates unresolved issues into a support ticket with the troubleshooting trail attached.
"""
    )

    st.subheader("Recommended 3-minute demo path")
    demo_steps = [
        "Log in as a regular user.",
        "Open Guided Troubleshooting.",
        "Choose a category such as Printer or Internet / Network.",
        "Answer 1-3 symptom questions until a solution appears.",
        "Click that the solution did not fix the issue.",
        "Submit a ticket with business impact and device/location details.",
        "Open My Tickets or View Tickets and inspect the saved troubleshooting trail.",
    ]
    for step_number, step_text in enumerate(demo_steps, start=1):
        st.write(f"{step_number}. {step_text}")

    render_demo_readiness_checklist()
    render_portfolio_export_pack()

    st.subheader("Implemented MVP+ capabilities")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            """
- Basic login and role-aware user/support navigation
- Category-first guided troubleshooting
- Reusable diagnostic page driven by database nodes
- Solution display with ordered steps
- Support ticket submission
"""
        )
    with col2:
        st.markdown(
            """
- Troubleshooting session tracking
- Event audit trail
- Ticket trail snapshot
- Lightweight admin ticket review for escalated issues
- Knowledge Base and diagnostic tree viewer
"""
        )

    st.subheader("MVP scope boundary")
    st.markdown(
        """
This app is intentionally centered on **guided troubleshooting**. Ticket creation and ticket review are included only to show what happens when self-service troubleshooting does not resolve the issue. A full analytics dashboard, assignment queue, SLA engine, and reporting module are intentionally outside the visible MVP.

The support-side role is labeled **IT Support Specialist** in the UI. It represents Tier 1 help desk plus junior Tier 2 network/support work appropriate for A+, Network+, and CCNA-track troubleshooting: device/user/scope checks, IP/DNS/DHCP/VPN/printer reachability checks when relevant, clear documentation, and evidence-based escalation.
"""
    )

    st.subheader("Core database design")
    st.markdown(
        """
The MVP centers around these tables:

| Area | Tables |
|---|---|
| Authentication | `users` |
| Knowledge and diagnostics | `problem`, `solution`, `diagnostic_tree`, `diagnostic_node`, `solution_step`, `kb_article` and child tables |
| Workflow tracking | `troubleshooting_session`, `troubleshooting_event` |
| Escalation | `tickets`, `ticket_comments`, `ticket_attachments` |
"""
    )

    st.subheader("Intentional tradeoffs")
    st.markdown(
        """
- The troubleshooting model uses parent-child trees instead of a full reusable graph model, keeping routing simple and explainable.
- Authentication is local and portfolio-friendly rather than enterprise SSO.
- The admin Knowledge Base editor is useful for demos, but advanced versioning and approvals are intentionally left for future work.
- Search, notifications, SLA automation, dashboards, and assignment queues are intentionally left out of the visible MVP so the core guided-troubleshooting workflow stays finished and demoable.
- Ticketing is included only as the escalation endpoint for unresolved troubleshooting, not as the main product focus.
"""
    )

    st.subheader("Future enhancements")
    st.markdown(
        """
- Full SSO integration
- Reusable node-link graph model
- Dynamic ticket questions by category
- Email or chat notifications
- SLA escalation automation
- Import/export tools for troubleshooting trees
- Dedicated Tier 2/3 role views for Identity, Network, Security, Endpoint, and Systems teams
"""
    )

    st.subheader("Current local demo health")
    render_portfolio_health_snapshot()


# -----------------------------
# HOME / OVERVIEW PAGE
# -----------------------------
def show_home_page():
    st.title("🛠 IT Support Troubleshooting Portal")

    role = st.session_state.get("role", "User")

    st.markdown(
        """
        This portfolio MVP demonstrates a complete support workflow:
        **login → category selection → guided diagnostic questions → solution steps → ticket with troubleshooting trail**.
        """
    )

    render_support_action_cards()

    st.divider()
    render_portfolio_health_snapshot()

    st.divider()

    if role == "Admin":
        st.markdown("""
### 👨‍💼 IT Support Specialist Overview

Use this system to review escalated support tickets, inspect diagnostic trees, and follow structured Tier 1 / junior Tier 2 troubleshooting. The visible MVP intentionally stays focused on troubleshooting rather than analytics.
""")
        st.info("💡 Start with View Tickets to review, assign, update, or delete test tickets. Use Guided Troubleshooting to demo the main application flow.")
    else:
        st.markdown("""
### 👤 User Overview

Use this system to troubleshoot common IT issues, create support tickets, and track updates from IT support.
""")
        st.info("💡 For the best support trail, start with Guided Troubleshooting before creating a ticket.")



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
notifications, SLA tracking, and admin ticket-management views.

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
- Ticket review, assignment, comments, and lifecycle management
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
- **Operational views** — ticket filters, lifecycle tracking, and audit history
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
- Ticket lifecycle and audit trail logic
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
        "For demos, admins can use View Tickets to review ticket lifecycle behavior and delete test tickets created during testing. "
        "This keeps the application focused on troubleshooting while still supporting escalation."
    )

    st.caption("Built as a practical IT Support / Help Desk portfolio project.")



# -----------------------------
# ADMIN DIAGNOSTIC TREE VIEWER
# -----------------------------
def get_diagnostic_tree_records_for_admin():
    """Return all diagnostic tree records for admin viewing."""
    connection = get_db_connection()
    cursor = connection.cursor()

    active_problem_codes = sorted(MVP_ACTIVE_PROBLEM_CODES)
    if not active_problem_codes:
        connection.close()
        return []

    placeholders = ",".join("?" for _ in active_problem_codes)

    cursor.execute(
        f"""
        SELECT
            dt.diagnostic_tree_id,
            dt.diagnostic_tree_code,
            dt.base_tree_code,
            dt.audience,
            dt.title,
            dt.description,
            dt.is_active,
            p.title AS problem_title,
            p.category,
            p.severity
        FROM diagnostic_tree dt
        LEFT JOIN problem p
            ON dt.problem_id = p.problem_id
        WHERE dt.base_tree_code IN ({placeholders})
        ORDER BY
            COALESCE(p.category, ''),
            COALESCE(p.title, dt.title),
            CASE dt.audience
                WHEN 'user' THEN 1
                WHEN 'technician' THEN 2
                WHEN 'admin' THEN 3
                ELSE 4
            END,
            dt.title
        """,
        active_problem_codes,
    )

    rows = cursor.fetchall()
    connection.close()
    return [dict(row) for row in rows]


def get_diagnostic_tree_nodes_for_admin(diagnostic_tree_id):
    """Return all nodes for a diagnostic tree."""
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            dn.diagnostic_node_id,
            dn.parent_diagnostic_node_id,
            dn.diagnostic_tree_id,
            dn.diagnostic_tree_code,
            dn.node_key,
            dn.node_type,
            dn.title,
            dn.description,
            dn.prompt_text,
            dn.condition_label,
            dn.condition_value,
            dn.solution_id,
            dn.sort_order,
            s.solution_code,
            s.title AS solution_title,
            s.summary AS solution_summary,
            s.escalation_required,
            s.priority_recommendation
        FROM diagnostic_node dn
        LEFT JOIN solution s
            ON dn.solution_id = s.solution_id
        WHERE dn.diagnostic_tree_id = ?
          AND dn.is_active = 1
        ORDER BY
            COALESCE(dn.parent_diagnostic_node_id, 0),
            dn.sort_order,
            dn.diagnostic_node_id
        """,
        (diagnostic_tree_id,),
    )

    rows = cursor.fetchall()
    connection.close()
    return [dict(row) for row in rows]


def build_diagnostic_tree_lines(nodes):
    """Build readable indented lines from diagnostic nodes."""
    if not nodes:
        return []

    children_by_parent = {}
    node_by_id = {}

    for node in nodes:
        node_by_id[node["diagnostic_node_id"]] = node
        children_by_parent.setdefault(node["parent_diagnostic_node_id"], []).append(node)

    for children in children_by_parent.values():
        children.sort(key=lambda item: (item.get("sort_order") or 0, item.get("diagnostic_node_id") or 0))

    root_nodes = children_by_parent.get(None, [])

    # Some SQLite rows can store parent as NULL, but if no root is found,
    # fallback to nodes whose parent is missing from this selected tree.
    if not root_nodes:
        node_ids = set(node_by_id.keys())
        root_nodes = [
            node for node in nodes
            if node.get("parent_diagnostic_node_id") not in node_ids
        ]

    lines = []

    def visit(node, depth=0):
        indent = "    " * depth
        branch = ""

        if node.get("condition_value"):
            branch = f"[{node.get('condition_value')}] "

        node_icon = {
            "category": "📂",
            "question": "❓",
            "check": "🔎",
            "instruction": "🛠",
            "solution": "✅",
        }.get(node.get("node_type"), "•")

        title = node.get("title", "Untitled")
        node_type = node.get("node_type", "node")

        if node_type == "solution":
            solution_title = node.get("solution_title") or title
            line = f"{indent}{node_icon} {branch}{solution_title}"
            if node.get("solution_code"):
                line += f" ({node.get('solution_code')})"
        else:
            line = f"{indent}{node_icon} {branch}{title}"

        lines.append(line)

        if node.get("prompt_text"):
            lines.append(f"{indent}   ↳ Prompt: {node.get('prompt_text')}")

        for child in children_by_parent.get(node["diagnostic_node_id"], []):
            visit(child, depth + 1)

    for root in root_nodes:
        visit(root, 0)

    return lines


def show_diagnostic_node_details(nodes):
    """Show detailed node table-style expanders for one tree."""
    if not nodes:
        st.info("No nodes found for this diagnostic tree.")
        return

    for node in nodes:
        label = f"{node.get('node_type', '').title()} — {node.get('title', 'Untitled')}"
        if node.get("condition_value"):
            label += f" | Branch: {node.get('condition_value')}"
        if node.get("solution_title"):
            label += f" | Solution: {node.get('solution_title')}"

        with st.expander(label):
            st.write(f"**Node Key:** `{node.get('node_key', '')}`")
            st.write(f"**Node Type:** {node.get('node_type', '')}")
            st.write(f"**Sort Order:** {node.get('sort_order', '')}")

            if node.get("description"):
                st.write("**Description:**")
                st.write(node.get("description"))

            if node.get("prompt_text"):
                st.write("**Prompt:**")
                st.write(node.get("prompt_text"))

            if node.get("condition_label") or node.get("condition_value"):
                st.write("**Branch Condition:**")
                st.write(f"{node.get('condition_label', '')} → {node.get('condition_value', '')}")

            if node.get("solution_title"):
                st.success(f"Solution: {node.get('solution_title')}")
                st.write(f"**Solution Code:** `{node.get('solution_code', '')}`")
                if node.get("solution_summary"):
                    st.write(node.get("solution_summary"))
                st.write(f"**Escalation Required:** {'Yes' if node.get('escalation_required') else 'No'}")
                st.write(f"**Priority Recommendation:** {get_solution_priority_label(node.get('priority_recommendation'))}")


def show_admin_diagnostic_tree_viewer():
    """Admin page to inspect database-driven diagnostic trees."""
    require_admin()

    st.title("🧭 Diagnostic Tree Viewer")
    st.info(
        "This page shows the diagnostic trees stored in the relational database. "
        "It helps verify the hierarchy of questions, branches, and final solutions."
    )

    tree_records = get_diagnostic_tree_records_for_admin()

    if not tree_records:
        st.warning("No diagnostic trees found in the database.")
        return

    col_summary1, col_summary2, col_summary3 = st.columns(3)
    col_summary1.metric("Diagnostic Trees", len(tree_records))
    col_summary2.metric("User Trees", sum(1 for tree in tree_records if tree.get("audience") == "user"))
    col_summary3.metric("IT Support Specialist Trees", sum(1 for tree in tree_records if tree.get("audience") in ["technician", "admin"]))

    st.divider()

    audience_filter = st.selectbox(
        "Filter by audience",
        ["All", "user", "technician", "admin"],
        key="diag_tree_audience_filter",
    )

    problem_options = ["All"] + sorted(
        {
            tree.get("problem_title") or tree.get("title") or tree.get("base_tree_code")
            for tree in tree_records
        }
    )

    problem_filter = st.selectbox("Filter by problem", problem_options, key="diag_tree_problem_filter")

    filtered_trees = []

    for tree in tree_records:
        if audience_filter != "All" and tree.get("audience") != audience_filter:
            continue

        tree_problem = tree.get("problem_title") or tree.get("title") or tree.get("base_tree_code")
        if problem_filter != "All" and tree_problem != problem_filter:
            continue

        filtered_trees.append(tree)

    if not filtered_trees:
        st.warning("No diagnostic trees match the selected filters.")
        return

    tree_labels = [
        f"{tree.get('problem_title') or tree.get('title')} — {tree.get('audience').title()} — {tree.get('diagnostic_tree_code')}"
        for tree in filtered_trees
    ]

    selected_label = st.selectbox("Select a diagnostic tree", tree_labels, key="diag_tree_selected_label")
    selected_index = tree_labels.index(selected_label)
    selected_tree = filtered_trees[selected_index]

    st.divider()

    st.subheader(selected_tree.get("title", "Diagnostic Tree"))
    st.write(f"**Problem:** {selected_tree.get('problem_title', 'N/A')}")
    st.write(f"**Category:** {selected_tree.get('category', 'N/A')}")
    st.write(f"**Severity:** {selected_tree.get('severity', 'N/A')}")
    st.write(f"**Audience:** {selected_tree.get('audience', 'N/A').title()}")
    st.write(f"**Base Tree Code:** `{selected_tree.get('base_tree_code', '')}`")
    st.write(f"**Diagnostic Tree Code:** `{selected_tree.get('diagnostic_tree_code', '')}`")

    if selected_tree.get("description"):
        st.write("**Description:**")
        st.write(selected_tree.get("description"))

    nodes = get_diagnostic_tree_nodes_for_admin(selected_tree["diagnostic_tree_id"])

    st.divider()
    st.subheader("🌳 Tree Structure")

    tree_lines = build_diagnostic_tree_lines(nodes)

    if tree_lines:
        st.code("\n".join(tree_lines), language="text")
    else:
        st.info("No nodes found for this tree.")

    st.divider()
    st.subheader("🔎 Node Details")
    show_diagnostic_node_details(nodes)

# -----------------------------
# MAIN APP
# -----------------------------
def main():
    apply_global_styles()
    initialize_database()
    load_users()
    load_issues()
    st.session_state["issues"] = issues
    load_tickets()

    restore_login_from_auth_session()

    if not st.session_state.get("logged_in"):
        show_login_page()
        return

    st.sidebar.write(f"Logged in as: **{st.session_state.get('username')}**")
    st.sidebar.write(f"Role: **{get_role_display_name(st.session_state.get('role'))}**")

    if st.sidebar.button("Logout", key="sidebar_logout_button"):
        logout_user()
        st.rerun()

    tickets = st.session_state.get("tickets", [])

    if st.session_state.get("role") == "Admin":
        admin_notifications = get_admin_notification_counts(tickets)

        if admin_notifications["total"] > 0:
            st.sidebar.warning(
                f"🔔 {admin_notifications['total']} support alert(s): "
                f"{admin_notifications['critical']} critical, "
                f"{admin_notifications['overdue']} overdue, "
                f"{admin_notifications['unread_updates']} unread update(s)"
            )

        menu_options = [
            "ℹ️ About This App",
            "📘 Portfolio Demo Guide",
            "🏠 Home",
            "🧭 Guided Troubleshooting",
            "🔍 Knowledge Base",
            "🎫 Create Ticket",
            build_menu_label("📋 View Tickets", admin_notifications["unread_updates"]),
            "🧭 Diagnostic Tree Viewer",
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
            "📘 Portfolio Demo Guide",
            "🏠 Home",
            "🧭 Guided Troubleshooting",
            "🔍 Knowledge Base",
            "🎫 Create Ticket",
            build_menu_label("🎟 My Tickets", user_notifications["unread_updates"]),
        ]

    requested_mode = st.session_state.pop("selected_mode_request", None)
    requested_index = 0
    if requested_mode:
        for index, option in enumerate(menu_options):
            if normalize_menu_choice(option) == normalize_menu_choice(requested_mode):
                requested_index = index
                break

    selected_mode = st.sidebar.radio(
        "Select Mode",
        menu_options,
        index=requested_index,
        key="main_sidebar_mode",
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
    elif mode == "📘 Portfolio Demo Guide":
        show_portfolio_demo_guide()
    elif mode == "🏠 Home":
        show_home_page()
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
    elif mode == "🧭 Diagnostic Tree Viewer":
        show_admin_diagnostic_tree_viewer()
    elif mode == "🛠 Manage Knowledge Base":
        show_admin_kb_editor()


if __name__ == "__main__":
    main()
