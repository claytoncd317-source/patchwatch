import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "/tmp/patchwatch.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_schema() -> str:
    conn = get_connection()
    cursor = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    rows = cursor.fetchall()
    conn.close()
    return "\n\n".join(row[0] for row in rows if row[0])


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id          INTEGER PRIMARY KEY,
            hostname    TEXT NOT NULL,
            ip_address  TEXT NOT NULL,
            os          TEXT NOT NULL,
            environment TEXT NOT NULL CHECK(environment IN ('production','staging','development')),
            team        TEXT NOT NULL,
            last_seen   TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS vulnerabilities (
            id          INTEGER PRIMARY KEY,
            cve_id      TEXT UNIQUE NOT NULL,
            title       TEXT NOT NULL,
            severity    TEXT NOT NULL CHECK(severity IN ('critical','high','medium','low')),
            cvss_score  REAL NOT NULL,
            description TEXT,
            published   TEXT NOT NULL,
            patch_available INTEGER NOT NULL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS findings (
            id             INTEGER PRIMARY KEY,
            asset_id       INTEGER NOT NULL REFERENCES assets(id),
            vuln_id        INTEGER NOT NULL REFERENCES vulnerabilities(id),
            status         TEXT NOT NULL CHECK(status IN ('open','remediated','accepted_risk','in_progress')),
            discovered_at  TEXT NOT NULL,
            remediated_at  TEXT,
            sla_deadline   TEXT NOT NULL
        )
    """)

    if cur.execute("SELECT COUNT(*) FROM assets").fetchone()[0] > 0:
        conn.close()
        return

    assets = [
        ("web-prod-01",   "10.0.1.10", "Ubuntu 22.04",  "production",  "platform", "2025-03-20"),
        ("web-prod-02",   "10.0.1.11", "Ubuntu 22.04",  "production",  "platform", "2025-03-20"),
        ("db-prod-01",    "10.0.2.10", "RHEL 9.2",      "production",  "data",     "2025-03-19"),
        ("db-prod-02",    "10.0.2.11", "RHEL 9.2",      "production",  "data",     "2025-03-18"),
        ("api-prod-01",   "10.0.3.10", "Debian 12",     "production",  "backend",  "2025-03-20"),
        ("cache-prod-01", "10.0.4.10", "Ubuntu 20.04",  "production",  "platform", "2025-03-17"),
        ("web-stg-01",    "10.1.1.10", "Ubuntu 22.04",  "staging",     "platform", "2025-03-20"),
        ("api-stg-01",    "10.1.3.10", "Debian 12",     "staging",     "backend",  "2025-03-19"),
        ("dev-laptop-01", "192.168.1.5","Windows 11",   "development", "security", "2025-03-15"),
        ("dev-laptop-02", "192.168.1.6","macOS 14.4",   "development", "backend",  "2025-03-14"),
        ("k8s-node-01",   "10.0.5.10", "Ubuntu 22.04",  "production",  "infra",    "2025-03-20"),
        ("k8s-node-02",   "10.0.5.11", "Ubuntu 22.04",  "production",  "infra",    "2025-03-20"),
    ]
    cur.executemany(
        "INSERT INTO assets (hostname,ip_address,os,environment,team,last_seen) VALUES (?,?,?,?,?,?)",
        assets
    )

    vulns = [
        ("CVE-2024-6387",  "OpenSSH RegreSSHion RCE",               "critical", 9.8,  "Unauthenticated RCE in OpenSSH sshd via signal handler race condition.", "2024-07-01", 1),
        ("CVE-2024-3094",  "XZ Utils Supply Chain Backdoor",         "critical", 9.8,  "Malicious code in liblzma enabling SSH auth bypass on systemd-linked sshd.", "2024-03-29", 1),
        ("CVE-2023-44487", "HTTP/2 Rapid Reset DDoS",                "high",     7.5,  "Zero-day HTTP/2 attack causing server exhaustion via rapid stream resets.", "2023-10-10", 1),
        ("CVE-2024-21762", "Fortinet FortiOS Out-of-Bounds Write",   "critical", 9.6,  "Out-of-bounds write in FortiOS SSL-VPN allowing unauthenticated RCE.", "2024-02-08", 1),
        ("CVE-2024-23897", "Jenkins Arbitrary File Read",            "critical", 9.8,  "Path traversal in Jenkins CLI allows unauthenticated arbitrary file read.", "2024-01-24", 1),
        ("CVE-2023-46604", "Apache ActiveMQ RCE",                    "critical", 10.0, "Deserialization vulnerability allowing unauthenticated remote code execution.", "2023-10-27", 1),
        ("CVE-2024-27198", "JetBrains TeamCity Auth Bypass",         "critical", 9.8,  "Authentication bypass leading to full server takeover without credentials.", "2024-03-04", 1),
        ("CVE-2023-4966",  "Citrix Bleed Session Token Leak",        "critical", 9.4,  "Sensitive info disclosure allowing session hijacking on NetScaler ADC/Gateway.", "2023-10-10", 1),
        ("CVE-2024-1709",  "ConnectWise ScreenConnect Auth Bypass",  "critical", 10.0, "Authentication bypass and path traversal leading to unauthenticated RCE.", "2024-02-19", 1),
        ("CVE-2023-36884", "Microsoft Office HTML Injection RCE",    "high",     8.3,  "RCE via specially crafted Office documents without Mark-of-the-Web.", "2023-07-11", 1),
        ("CVE-2024-30078", "Windows Wi-Fi Driver RCE",               "high",     8.8,  "Unauthenticated RCE in Windows Wi-Fi driver when in range of attacker AP.", "2024-06-11", 1),
        ("CVE-2023-35078", "Ivanti EPMM Auth Bypass",                "critical", 10.0, "Zero-day authentication bypass in MobileIron/Ivanti EPMM API endpoints.", "2023-07-23", 1),
        ("CVE-2024-0519",  "Chrome V8 Out-of-Bounds Memory Access",  "high",     8.8,  "High-severity Chrome V8 OOB vulnerability exploited in the wild.", "2024-01-16", 1),
        ("CVE-2023-42793", "JetBrains TeamCity CI/CD Auth Bypass",   "critical", 9.8,  "Auth bypass in JetBrains TeamCity allows RCE as server process.", "2023-09-06", 1),
        ("CVE-2024-20767", "Adobe ColdFusion Auth Bypass",           "critical", 9.8,  "Improper access control allows arbitrary file read and potential RCE.", "2024-03-12", 0),
        ("CVE-2023-29357", "Microsoft SharePoint Privilege Escalation","high",   9.8,  "Privilege escalation via spoofed JWT tokens allows attacker admin access.", "2023-09-12", 1),
        ("CVE-2024-38063", "Windows TCP/IP Remote Code Execution",   "critical", 9.8,  "Zero-click RCE in Windows TCP/IP stack via malformed IPv6 packets.", "2024-08-13", 1),
        ("CVE-2023-23397", "Microsoft Outlook NTLM Credential Theft","critical", 9.8,  "Zero-click Outlook vulnerability leaks NTLM hash via calendar invite.", "2023-03-14", 1),
        ("CVE-2024-26169", "Windows Error Reporting Priv Escalation","high",     7.8,  "Windows Error Reporting race condition allows local privilege escalation.", "2024-03-12", 1),
        ("CVE-2023-38545", "curl SOCKS5 Heap Buffer Overflow",       "high",     9.8,  "Heap-based buffer overflow in curl SOCKS5 proxy handshake.", "2023-10-11", 1),
    ]
    cur.executemany(
        "INSERT INTO vulnerabilities (cve_id,title,severity,cvss_score,description,published,patch_available) VALUES (?,?,?,?,?,?,?)",
        vulns
    )

    findings = [
        (1,  1,  "open",          "2024-07-05", None,         "2024-07-12"),
        (1,  3,  "remediated",    "2023-10-15", "2023-10-20", "2023-10-24"),
        (1,  10, "open",          "2023-07-15", None,         "2023-07-29"),
        (2,  1,  "in_progress",   "2024-07-05", None,         "2024-07-12"),
        (2,  3,  "remediated",    "2023-10-15", "2023-10-22", "2023-10-24"),
        (3,  6,  "open",          "2023-11-01", None,         "2023-11-08"),
        (3,  12, "open",          "2023-07-28", None,         "2023-08-04"),
        (3,  18, "remediated",    "2023-03-18", "2023-03-25", "2023-03-28"),
        (4,  6,  "accepted_risk", "2023-11-01", None,         "2023-11-08"),
        (4,  2,  "open",          "2024-04-01", None,         "2024-04-08"),
        (5,  5,  "open",          "2024-01-28", None,         "2024-02-04"),
        (5,  7,  "open",          "2024-03-08", None,         "2024-03-15"),
        (5,  13, "remediated",    "2024-01-20", "2024-01-25", "2024-01-30"),
        (6,  20, "open",          "2023-10-15", None,         "2023-10-25"),
        (6,  1,  "open",          "2024-07-08", None,         "2024-07-15"),
        (7,  1,  "open",          "2024-07-05", None,         "2024-07-19"),
        (7,  14, "in_progress",   "2023-09-10", None,         "2023-09-24"),
        (8,  5,  "open",          "2024-01-28", None,         "2024-02-11"),
        (9,  11, "open",          "2024-06-15", None,         "2024-06-29"),
        (9,  10, "open",          "2023-07-15", None,         "2023-07-29"),
        (10, 11, "open",          "2024-06-15", None,         "2024-06-29"),
        (11, 1,  "open",          "2024-07-05", None,         "2024-07-12"),
        (11, 17, "open",          "2024-08-15", None,         "2024-08-22"),
        (12, 1,  "open",          "2024-07-05", None,         "2024-07-12"),
        (12, 17, "in_progress",   "2024-08-15", None,         "2024-08-22"),
        (1,  4,  "open",          "2024-02-12", None,         "2024-02-19"),
        (3,  9,  "open",          "2024-02-23", None,         "2024-03-02"),
        (5,  15, "open",          "2024-03-16", None,         "2024-03-30"),
        (6,  16, "remediated",    "2023-09-15", "2023-09-20", "2023-09-26"),
        (8,  8,  "open",          "2023-10-15", None,         "2023-10-24"),
    ]
    cur.executemany(
        "INSERT INTO findings (asset_id,vuln_id,status,discovered_at,remediated_at,sla_deadline) VALUES (?,?,?,?,?,?)",
        findings
    )

    conn.commit()
    conn.close()