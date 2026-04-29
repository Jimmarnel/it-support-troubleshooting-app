import base64
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
# DATABASE SETUP
# -----------------------------
def get_db_connection():
    """Create and return a SQLite database connection."""
    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    """Create SQLite tables if they do not already exist."""
    connection = get_db_connection()
    cursor = connection.cursor()

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

    connection.commit()
    connection.close()


# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(page_title="IT Troubleshooting Tool", layout="wide")

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

        st.info("Demo accounts: user / user123, admin / admin123")

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
    "Slow Internet Performance": {
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
    "Wi-Fi Connected But No Internet": {
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
            ["Select"] + question["options"],
            key=f"{flow_name}_{current_question_id}",
        )

        if answer == "Select":
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

    st.info("This guided flow is auto-generated from the Knowledge Base data.")

    has_symptoms = st.radio(
        "Is the user experiencing one or more of these symptoms?",
        ["Select", "Yes", "No"],
        key=f"auto_{issue['title']}_symptoms",
    )

    with st.expander("View symptoms"):
        for symptom in issue["symptoms"]:
            st.write("-", symptom)

    if has_symptoms == "Select":
        st.stop()

    if has_symptoms == "No":
        show_recommendations(
            "👉 The selected issue may not fully match your problem.",
            "info",
            [
                "Do not worry if you are unsure about the exact symptoms",
                "Create a support ticket and describe what happened in your own words",
                "Include details such as when it started, what you were trying to do, and any error message you saw",
                "An IT technician can review the ticket and identify the correct issue",
            ],
        )
        return

    confirmed_scope = st.radio(
        "Does the issue match this category and severity?",
        ["Select", "Yes", "No / Not sure"],
        key=f"auto_{issue['title']}_scope",
    )

    st.write("**Category:**", issue["category"])
    show_severity(issue["severity"])

    if confirmed_scope == "Select":
        st.stop()

    if confirmed_scope == "No / Not sure":
        show_recommendations(
            "👉 Gather more information before applying a fix.",
            "warning",
            [
                "Confirm when the issue started",
                "Check whether one user or multiple users are affected",
                "Review recent changes, updates, or outages",
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
        for cause in issue["causes"]:
            st.write("-", cause)


def show_guided_troubleshooting():
    st.title("🧭 Guided Troubleshooting Assistant")

    issue_titles = [issue["title"] for issue in issues]

    selected_issue = st.selectbox(
        "Select an issue to troubleshoot:",
        ["None"] + issue_titles,
    )

    if selected_issue == "None":
        st.info("Select an issue to begin guided troubleshooting.")
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
            user_steps, it_steps, steps
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(title) DO UPDATE SET
            category = excluded.category,
            severity = excluded.severity,
            tags = excluded.tags,
            symptoms = excluded.symptoms,
            causes = excluded.causes,
            user_steps = excluded.user_steps,
            it_steps = excluded.it_steps,
            steps = excluded.steps
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
        "Cannot Login to System",
        "Outlook Keeps Asking for Password",
        "Weak Wi-Fi Signal",
        "Cannot Access Network Drive",
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
            edit_tags = st.text_input(
                "Tags (comma separated)",
                value=", ".join(issue.get("tags", [])),
                key=f"edit_tags_{idx}",
            )
            edit_symptoms = st.text_area(
                "Symptoms (one per line)",
                value="".join(issue.get("symptoms", [])),
                key=f"edit_symptoms_{idx}",
            )
            edit_user_steps = st.text_area(
                "User-Friendly Steps (one per line)",
                value="".join(get_user_friendly_steps(issue)),
                key=f"edit_user_steps_{idx}",
            )
            edit_steps = st.text_area(
                "Advanced IT Steps (one per line)",
                value="".join(get_it_steps(issue)),
                key=f"edit_steps_{idx}",
            )

            col1, col2 = st.columns(2)

            with col1:
                if st.button("💾 Save Changes", key=f"save_issue_{idx}"):
                    issue["title"] = edit_title.strip()
                    issue["category"] = edit_category.strip()
                    issue["severity"] = edit_severity
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

    for uploaded_file in uploaded_files:
        safe_name = uploaded_file.name.replace(" ", "_")
        unique_name = f"{uuid.uuid4().hex}_{safe_name}"
        file_path = os.path.abspath(os.path.join(UPLOAD_FOLDER, unique_name))

        with open(file_path, "wb") as file:
            file.write(uploaded_file.getbuffer())

        saved_attachments.append({
            "original_name": uploaded_file.name,
            "saved_name": unique_name,
            "path": file_path,
            "type": uploaded_file.type,
            "size": uploaded_file.size,
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

        submitted = st.form_submit_button("Create Ticket")

        if submitted:
            if not issue_title or not description:
                st.error("Issue Title and Description are required")
                return

            suggested_issues = suggest_issues_from_text(description, issue_title)
            user_guidance = get_user_guidance_for_ticket(description)
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
                "suggestions": [
                    {
                        "title": issue["title"],
                        "category": issue["category"],
                        "severity": issue["severity"],
                        "score": score,
                    }
                    for issue, score in suggested_issues
                ],
                "user_guidance": user_guidance,
                "likely_infrastructure": is_likely_infrastructure_issue(description),
                "attachments": attachments,
                "comments": [],
                "unread_for_admin": True,
                "unread_for_user": False,
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

            st.subheader("User Guidance")
            for item in user_guidance:
                st.write("-", item)

            if suggested_issues:
                st.subheader("🔎 Suggested matching issues")
                for issue, score in suggested_issues:
                    with st.expander(f"{issue['title']} — Match score: {score}"):
                        st.write("**Category:**", issue["category"])
                        show_severity(issue["severity"])

                        st.write("**Possible causes:**")
                        for cause in issue["causes"]:
                            st.write("-", cause)

                        show_role_based_steps(issue)
            else:
                st.warning("No matching Knowledge Base issue found for this ticket.")


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
        ["All", "Open", "In Progress", "Resolved"],
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

        unread_label = " 🔔 New comment" if ticket.get("unread_for_admin") else ""
        with st.expander(f"Ticket {i}: {ticket['issue']} — {status} — {priority}{unread_label}"):
            st.write(f"**Name:** {ticket['name']}")
            st.write(f"**Email:** {ticket['email']}")
            st.write(f"**Severity:** {ticket['severity']}")
            show_priority_badge(priority)
            st.write(f"**Status:** {status}")
            st.write(f"**Assigned To:** {assigned_to}")
            st.write("**Description:**")
            st.write(ticket["description"])

            if ticket.get("likely_infrastructure"):
                st.warning("Possible wider IT/infrastructure issue")

            guidance = ticket.get("user_guidance", [])
            if guidance:
                st.write("**User Guidance:**")
                for item in guidance:
                    st.write("-", item)

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

            new_status = st.selectbox(
                "Status",
                ["Open", "In Progress", "Resolved"],
                index=["Open", "In Progress", "Resolved"].index(status),
                key=f"status_{i}",
            )

            new_assigned_to = st.text_input(
                "Assigned To",
                value=assigned_to,
                key=f"assigned_{i}",
            )

            new_priority = st.selectbox(
                "Priority",
                ["Critical", "High", "Medium", "Low"],
                index=["Critical", "High", "Medium", "Low"].index(priority),
                key=f"priority_{i}",
            )

            new_resolution_notes = st.text_area(
                "Resolution Notes",
                value=ticket.get("resolution_notes", ""),
                key=f"resolution_{i}",
            )

            if st.button("Save Ticket Updates", key=f"save_ticket_{i}"):
                ticket["status"] = new_status
                ticket["priority"] = new_priority
                ticket["assigned_to"] = new_assigned_to
                ticket["resolution_notes"] = new_resolution_notes
                save_tickets()
                st.success("✅ Ticket updated successfully")

            if ticket.get("resolution_notes"):
                st.write("**Saved Resolution Notes:**")
                st.write(ticket["resolution_notes"])

            show_ticket_comments(ticket, i)


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
    })

    if author_role == "Admin":
        ticket["unread_for_user"] = True
    else:
        ticket["unread_for_admin"] = True

    save_tickets()
    return True


def show_ticket_comments(ticket, ticket_index):
    """Display and add ticket comments."""
    st.subheader("💬 Ticket Conversation")

    role = st.session_state.get("role", "User")
    unread_key = "unread_for_admin" if role == "Admin" else "unread_for_user"

    if ticket.get(unread_key):
        st.warning("🔔 New unread comment(s)")
        if st.button("Mark comments as read", key=f"mark_read_{ticket_index}"):
            ticket[unread_key] = False
            save_tickets()
            st.success("Comments marked as read")
            st.rerun()

    comments = ticket.get("comments", [])

    if not comments:
        st.info("No comments yet.")
    else:
        for comment in comments:
            st.write(f"**{comment.get('author', 'Unknown')} ({comment.get('role', 'User')})**")
            st.write(comment.get("comment", ""))
            st.divider()

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


# -----------------------------
# ADMIN DASHBOARD
# -----------------------------
def show_admin_dashboard():
    require_admin()
    st.title("📊 Admin Dashboard")

    tickets = st.session_state.get("tickets", [])

    total_tickets = len(tickets)
    open_tickets = sum(1 for ticket in tickets if ticket.get("status", "Open") == "Open")
    in_progress_tickets = sum(1 for ticket in tickets if ticket.get("status") == "In Progress")
    resolved_tickets = sum(1 for ticket in tickets if ticket.get("status") == "Resolved")
    critical_tickets = sum(1 for ticket in tickets if ticket.get("priority") == "Critical")
    unread_admin_comments = sum(1 for ticket in tickets if ticket.get("unread_for_admin"))

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total Tickets", total_tickets)
    col2.metric("Open", open_tickets)
    col3.metric("In Progress", in_progress_tickets)
    col4.metric("Resolved", resolved_tickets)
    col5.metric("Critical", critical_tickets)
    col6.metric("Unread Comments", unread_admin_comments)

    st.divider()

    if not tickets:
        st.info("No ticket data available yet.")
        return

    critical_items = [
        ticket for ticket in tickets
        if ticket.get("priority") == "Critical"
    ]

    if critical_items:
        st.error(f"🚨 {len(critical_items)} critical ticket(s) need immediate attention.")
        with st.expander("View critical tickets"):
            for ticket in critical_items:
                st.write(f"- **{ticket.get('issue', 'Unknown issue')}** — {ticket.get('status', 'Open')}")

    unread_comment_items = [ticket for ticket in tickets if ticket.get("unread_for_admin")]
    if unread_comment_items:
        st.warning(f"🔔 {len(unread_comment_items)} ticket(s) have unread comments for admin.")
        with st.expander("View tickets with unread comments"):
            for ticket in unread_comment_items:
                st.write(f"- **{ticket.get('issue', 'Unknown issue')}** — {ticket.get('status', 'Open')}")

    st.subheader("Tickets by Status")
    status_counts = {
        "Open": open_tickets,
        "In Progress": in_progress_tickets,
        "Resolved": resolved_tickets,
    }
    st.bar_chart(status_counts)

    st.subheader("Tickets by Priority")
    priority_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for ticket in tickets:
        priority = ticket.get("priority", calculate_ticket_priority(ticket.get("description", ""), ticket.get("severity", "Medium")))
        priority_counts[priority] = priority_counts.get(priority, 0) + 1
    st.bar_chart(priority_counts)

    st.subheader("Tickets by Severity")
    severity_counts = {"Low": 0, "Medium": 0, "High": 0}
    for ticket in tickets:
        severity = ticket.get("severity", "Medium")
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
    st.bar_chart(severity_counts)

    st.subheader("Most Common Ticket Titles")
    issue_counts = {}
    for ticket in tickets:
        issue_title = ticket.get("issue", "Unknown")
        issue_counts[issue_title] = issue_counts.get(issue_title, 0) + 1

    sorted_issues = sorted(issue_counts.items(), key=lambda item: item[1], reverse=True)

    for issue_title, count in sorted_issues[:5]:
        st.write(f"- **{issue_title}**: {count}")


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
        unread_label = " 🔔 New comment" if ticket.get("unread_for_user") else ""
        with st.expander(f"Ticket {i}: {ticket.get('issue')} — {ticket.get('status', 'Open')}{unread_label}"):
            st.write(f"**Severity:** {ticket.get('severity')}")
            show_priority_badge(ticket.get("priority", "Medium"))
            st.write(f"**Status:** {ticket.get('status', 'Open')}")
            st.write("**Description:**")
            st.write(ticket.get("description", ""))

            if ticket.get("resolution_notes"):
                st.write("**Resolution Notes:**")
                st.write(ticket["resolution_notes"])

            show_ticket_comments(ticket, f"user_{i}")


# -----------------------------
# MAIN APP
# -----------------------------
def main():
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

    if st.session_state.get("role") == "Admin":
        menu_options = [
            "📊 Dashboard",
            "🧭 Guided Troubleshooting",
            "🔍 Knowledge Base",
            "🎫 Create Ticket",
            "📋 View Tickets",
            "🛠 Manage Knowledge Base",
        ]
    else:
        menu_options = [
            "🧭 Guided Troubleshooting",
            "🎫 Create Ticket",
            "🎟 My Tickets",
        ]

    mode = st.sidebar.radio(
        "Select Mode",
        menu_options,
    )

    if mode == "📊 Dashboard":
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
