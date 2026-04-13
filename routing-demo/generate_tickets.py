"""
Generate 1000 complex synthetic tickets for routing demo.
Complexity factors:
- Multiple CIs mentioned in a single ticket (cross-dependency)
- Ambiguous ownership (ticket could go to multiple resolver groups)
- Typos, inconsistent formatting, mixed case, abbreviations
- Incomplete information (missing CI, vague descriptions)
- Red herrings (mentions CIs that aren't the root cause)
- Varying note quality (terse vs verbose, technical vs non-technical author)
- Escalation chains (references to prior tickets, prior assignments)
- Multi-language fragments (German, Spanish mixed in)
- Copy-pasted error logs, stack traces, monitoring alerts
"""

import json
import random
import string
from pathlib import Path

random.seed(42)

# Load CMDB
cmdb = json.loads(Path("cmdb.json").read_text())
cis = cmdb["configuration_items"]
resolver_groups = list(cmdb["resolver_groups"].keys())

# Extended CI universe (references that appear in tickets but may not be primary CI)
EXTRA_HOSTS = [
    "ivosql06w", "ivosql07w", "ivosql09w", "lnxapp13p", "lnxapp15p",
    "lnxdb10p", "lnxdb11p", "winctx04p", "winctx05p", "esx-cl-eu-06",
    "esx-cl-eu-07", "azvm-crm-01", "azvm-crm-02", "azvm-erp-01",
    "san-stor-eu-05", "san-stor-eu-06", "san-stor-eu-08",
    "fw-palo-eu-02", "fw-palo-eu-03", "k8s-cl-eu-staging",
    "lnxweb15p", "lnxweb16p", "exch-mb-eu-04", "exch-mb-eu-05",
    "sap-app-eu-02", "sap-app-eu-03", "sap-db-eu-02",
    "ad-dc-eu-03", "ad-dc-uk-01", "mon-splunk-eu-02",
    "netscaler-eu-02", "f5-lb-eu-03", "proxy-squid-eu-01",
]

USERS = [
    "John", "Maria", "Stefan", "Priya", "Ahmed", "Elena", "Tomasz",
    "Chen Wei", "Raj", "Olga", "Marco", "Fatima", "Hans", "Yuki",
    "Dmitri", "Anita", "Lars", "Deepak", "Sofia", "Kenji",
    "Aleksander", "Nadia", "Ravi", "Ingrid", "Mohammed",
]

GREETINGS = [
    "Hello Team,", "Hi,", "Hi team,", "Dear support,", "Team,",
    "Hallo,", "Good morning,", "Urgent:", "URGENT -",
    "Please help -", "FYI -", "", "Hey,", "Hi all,",
    "Guten Tag,", "Hola equipo,", "Please assist.",
    "Escalation from L1:", "As discussed on the call:",
    "Following up on yesterday's bridge call:",
    "Per Slack thread in #incident-response:",
]

CLOSINGS = [
    "Thanks.", "Thankyou.", "Thank you.", "Regards", "Best regards",
    "Pls fix ASAP.", "Please treat as urgent.", "Danke.", "Gracias.",
    "Cheers", "Many thanks", "Please advise.", "Awaiting your response.",
    "Need this resolved before EOD.", "SLA breach in 2 hours.",
    "Customer escalation pending.", "Management visibility on this.",
    "Please update the ticket when done.", "",
    "CC: servicedesk@vodafone.com", "Ref: CHG0045123",
]

ERROR_FRAGMENTS = [
    "java.lang.OutOfMemoryError: Java heap space",
    "ORA-04031: unable to allocate 4096 bytes of shared memory",
    "SQLSTATE[HY000] [2002] Connection refused",
    "ERROR 1040 (HY000): Too many connections",
    "System.OutOfMemoryException: Exception of type",
    "kernel: Out of memory: Kill process",
    "FATAL: remaining connection slots are reserved",
    "IOException: No space left on device",
    "SSL_ERROR_HANDSHAKE_FAILURE_ALERT",
    "LDAP error code 49 - Invalid Credentials",
    "Kerberos error: KRB5KDC_ERR_S_PRINCIPAL_UNKNOWN",
    "HTTP/1.1 502 Bad Gateway\nServer: nginx/1.18.0",
    "HTTP/1.1 504 Gateway Time-out",
    "Connection timed out after 30001 milliseconds",
    "ICMP Destination Unreachable (Host Unreachable)",
    "TLS handshake timeout after 10s",
    "MSSQL Error 18456: Login failed for user",
    "pg_basebackup: could not connect to server",
    "OOM killed process 12345 (java) total-vm:8388608kB",
    "WARN  [org.apache.catalina.core] - Failed to initialize",
    "E0410 03:14:22.123456 1 controller.go:234] error syncing",
    "cannot allocate memory (errno=12)",
    "disk I/O error - Loss of communication with storage array",
    "SCSI sense key: Medium Error, ASC=0x11",
    "NetApp: wafl.vol.full (WARNING)",
    "Pure Storage: Array controller failover initiated",
    "VMware ESXi: PSOD - Purple Diagnostic Screen",
    "NSX-T: Transport node connectivity status DOWN",
    "Citrix: XML Service request failed - socket error",
    "Exchange: Store.exe consuming 98% CPU",
]

MONITORING_ALERTS = [
    "Nagios CRITICAL - {ci} - {metric} is {value}",
    "Zabbix trigger: {ci} - {metric} ({value})",
    "Splunk Alert: {ci} {metric} threshold exceeded ({value})",
    "Azure Monitor: {ci} - {metric} = {value}",
    "SCOM Alert: {ci} {metric} crossed threshold. Value: {value}",
    "PagerDuty incident triggered for {ci}: {metric}",
    "ServiceNow Event: CI={ci} Metric={metric} Value={value}",
    "Dynatrace Problem: {ci} - {metric} anomaly detected",
]

METRICS = [
    ("CPU utilization", "97%"), ("Memory usage", "94%"),
    ("Disk space", "96%"), ("Response time", "45000ms"),
    ("Connection count", "498/500"), ("Queue depth", "15432"),
    ("Error rate", "23%"), ("Packet loss", "8.5%"),
    ("Replication lag", "7200s"), ("Thread pool", "200/200"),
    ("IOPS", "45000 (throttled)"), ("Latency", "250ms"),
    ("Buffer pool hit ratio", "67%"), ("Lock waits", "342/sec"),
    ("GC pause time", "12.4s"), ("Swap usage", "8.2GB"),
]


def typo(text, probability=0.15):
    """Introduce realistic typos."""
    if random.random() > probability:
        return text
    words = text.split()
    if not words:
        return text
    idx = random.randint(0, len(words) - 1)
    word = words[idx]
    if len(word) < 3:
        return text
    mutation = random.choice(["swap", "drop", "double", "case"])
    if mutation == "swap" and len(word) > 3:
        i = random.randint(1, len(word) - 2)
        word = word[:i] + word[i+1] + word[i] + word[i+2:]
    elif mutation == "drop":
        i = random.randint(1, len(word) - 1)
        word = word[:i] + word[i+1:]
    elif mutation == "double":
        i = random.randint(0, len(word) - 1)
        word = word[:i] + word[i] * 2 + word[i+1:]
    elif mutation == "case":
        word = word.upper() if random.random() > 0.5 else word.lower()
    words[idx] = word
    return " ".join(words)


def gen_monitoring_alert(ci_name):
    template = random.choice(MONITORING_ALERTS)
    metric, value = random.choice(METRICS)
    return template.format(ci=ci_name, metric=metric, value=value)


def pick_ci_and_group():
    """Pick a primary CI and its correct resolver group."""
    ci_name = random.choice(list(cis.keys()))
    ci_data = cis[ci_name]
    return ci_name, ci_data, ci_data["resolver_group"]


# Ticket templates by complexity tier
def simple_ticket(ticket_id):
    """Straightforward: one CI, clear description, correct group obvious."""
    ci_name, ci_data, group = pick_ci_and_group()
    service = random.choice(ci_data["services"]) if ci_data["services"] else ci_name

    templates = [
        f"{service} on {ci_name} is down. Please investigate.",
        f"Alert received for {ci_name}. {service} not responding. Need urgent fix.",
        f"Users reporting issues with {service}. Server {ci_name} seems to be the source.",
        f"Scheduled maintenance follow-up: {ci_name} {service} did not come back online after reboot.",
        f"Performance degradation on {ci_name} affecting {service}. Response times >10s.",
    ]

    summary = f"{service} issue on {ci_name}"
    notes = random.choice(GREETINGS) + " " + random.choice(templates) + " " + random.choice(CLOSINGS)

    return {
        "ticket_id": ticket_id,
        "priority": random.choice(["P3", "P4"]),
        "category": random.choice(["Database", "Application", "Infrastructure", "Network", "Security", "Identity", "Collaboration", "Monitoring", "Storage"]),
        "summary": typo(summary),
        "notes": typo(notes),
        "ci_hint": ci_name,
        "correct_resolver_group": group,
        "complexity": "simple"
    }


def multi_ci_ticket(ticket_id):
    """Multiple CIs mentioned. Root cause is on one, but symptoms on others."""
    ci_name, ci_data, group = pick_ci_and_group()
    deps = ci_data.get("dependencies", [])
    extra_mentions = random.sample(EXTRA_HOSTS, k=random.randint(1, 3))

    dep_text = ""
    if deps:
        dep_ci = random.choice(deps)
        dep_data = cis.get(dep_ci, {})
        dep_service = random.choice(dep_data.get("services", ["unknown service"])) if dep_data else "dependent service"
        dep_text = f" We also see errors on {dep_ci} ({dep_service}) but that might be a downstream effect."

    extra_text = ""
    if extra_mentions:
        extra_text = f" Note: {', '.join(extra_mentions)} are also showing alerts but those might be unrelated."

    service = random.choice(ci_data["services"]) if ci_data["services"] else ci_name

    templates = [
        f"Multiple systems affected. Primary issue appears to be {service} on {ci_name}.{dep_text}{extra_text} Started at {random.randint(0,23):02d}:{random.randint(0,59):02d} UTC.",
        f"Cascade failure starting from {ci_name}. {service} went down first, then we saw impact on downstream systems.{dep_text}{extra_text}",
        f"Incident bridge running. {ci_name} identified as probable root cause. {service} throwing errors.{dep_text}{extra_text} Bridge ID: {random.randint(1000,9999)}",
        f"Automated correlation shows {ci_name} as origin. {service} failure cascading.{dep_text}{extra_text} Impact: {random.randint(50, 5000)} users.",
    ]

    summary = f"Multi-system impact - {ci_name} {service} cascade"
    notes = random.choice(GREETINGS) + "\n\n" + random.choice(templates) + "\n\n" + random.choice(CLOSINGS)

    return {
        "ticket_id": ticket_id,
        "priority": random.choice(["P3", "P3", "P4"]),
        "category": random.choice(["Database", "Application", "Infrastructure", "Network"]),
        "summary": typo(summary),
        "notes": typo(notes),
        "ci_hint": ci_name,
        "mentioned_cis": [ci_name] + deps[:1] + extra_mentions,
        "correct_resolver_group": group,
        "complexity": "multi_ci"
    }


def ambiguous_ticket(ticket_id):
    """Could be routed to multiple groups. Tests reasoning ability."""
    # Pick two related CIs
    ci1_name, ci1_data, group1 = pick_ci_and_group()
    deps = ci1_data.get("dependencies", [])

    if deps and deps[0] in cis:
        ci2_name = deps[0]
        ci2_data = cis[ci2_name]
        group2 = ci2_data["resolver_group"]
    else:
        ci2_name, ci2_data, group2 = pick_ci_and_group()

    svc1 = random.choice(ci1_data["services"]) if ci1_data["services"] else ci1_name
    svc2 = random.choice(ci2_data["services"]) if ci2_data["services"] else ci2_name

    templates = [
        f"Issue between {ci1_name} and {ci2_name}. {svc1} cannot connect to {svc2}. Not sure if it's the application side or the backend. Connectivity was fine until this morning. No changes logged in CMDB for either system.",
        f"Users reporting slow performance. Traced to {svc1} on {ci1_name} but backend calls to {svc2} on {ci2_name} are also slow. Could be either system. Please investigate both and coordinate.",
        f"Error in {svc1} logs on {ci1_name}: connection to {ci2_name} refused. But {ci2_name} is accepting connections from other sources. Might be network, might be app config, might be {svc2} issue.",
        f"Intermittent failures between {ci1_name} ({svc1}) and {ci2_name} ({svc2}). Works sometimes, fails sometimes. Load balancer? Firewall? App bug? Need someone to take ownership and triage.",
    ]

    summary = f"Connectivity issue between {ci1_name} and {ci2_name}"
    notes = random.choice(GREETINGS) + "\n\n" + random.choice(templates) + "\n\n" + random.choice(CLOSINGS)

    return {
        "ticket_id": ticket_id,
        "priority": random.choice(["P3", "P4"]),
        "category": random.choice(["Application", "Infrastructure", "Network"]),
        "summary": typo(summary),
        "notes": typo(notes),
        "ci_hint": ci1_name,
        "mentioned_cis": [ci1_name, ci2_name],
        "correct_resolver_group": group1,
        "alternate_resolver_group": group2,
        "complexity": "ambiguous"
    }


def error_log_ticket(ticket_id):
    """Ticket with copy-pasted error logs and stack traces."""
    ci_name, ci_data, group = pick_ci_and_group()
    service = random.choice(ci_data["services"]) if ci_data["services"] else ci_name

    errors = random.sample(ERROR_FRAGMENTS, k=random.randint(1, 4))
    error_block = "\n".join(errors)

    alert = gen_monitoring_alert(ci_name)

    templates = [
        f"Getting the following errors on {ci_name}:\n\n{error_block}\n\n{alert}\n\nStarted around {random.randint(0,23):02d}:{random.randint(0,59):02d}. {service} affected.",
        f"Monitoring alert triggered:\n{alert}\n\nChecked logs on {ci_name} and found:\n{error_block}\n\n{service} is degraded. Please investigate.",
        f"Copy from {ci_name} console:\n\n{error_block}\n\nThis is happening every {random.randint(1,30)} minutes. {service} keeps crashing and restarting.",
        f"Automated ticket from monitoring:\n{alert}\n\nAdditional context from log analysis:\n{error_block}\n\nAffects {service} on {ci_name}.",
    ]

    summary = f"Errors on {ci_name} - {service}"
    notes = random.choice(templates)

    return {
        "ticket_id": ticket_id,
        "priority": random.choice(["P3", "P3", "P4"]),
        "category": random.choice(["Database", "Application", "Infrastructure"]),
        "summary": typo(summary),
        "notes": notes,
        "ci_hint": ci_name,
        "correct_resolver_group": group,
        "complexity": "error_log"
    }


def vague_ticket(ticket_id):
    """Minimal info, non-technical author, missing CI details."""
    ci_name, ci_data, group = pick_ci_and_group()
    service = random.choice(ci_data["services"]) if ci_data["services"] else ci_name
    biz = ci_data.get("business_function", "IT")
    user = random.choice(USERS)

    templates = [
        f"Hi, {user} from {biz} here. Something is not working. I think it's the {service.split(':')[-1].split('-')[-1]} thing. Can someone look at it? It was working yesterday.",
        f"System down. Affecting our team. Not sure which server but it's the {biz.lower()} application. Very urgent as we have a deadline.",
        f"Hello, I cannot access the system since this morning. My manager said to raise a ticket. I don't know the technical details but it's related to {biz}. Error message says something about connection.",
        f"The thing we use for {biz.lower()} is broken again. Same issue as last month (don't remember the ticket number). Please fix.",
        f"FW: from {user}\n\nOriginal message:\n'{service.split(':')[-1]} is slow and sometimes shows an error page. Can IT please fix this?'\n\nPlease route to appropriate team.",
        f"User called service desk. Reports: cannot access {biz} application. Tried restarting browser. Tried different PC. Same error. No error code noted. User phone: ext {random.randint(1000,9999)}.",
    ]

    summary = f"{biz} system issue reported by {user}"
    notes = random.choice(templates)

    return {
        "ticket_id": ticket_id,
        "priority": "P4",
        "category": random.choice(["Application", "Infrastructure"]),
        "summary": summary,
        "notes": typo(notes, probability=0.25),
        "ci_hint": ci_name,
        "correct_resolver_group": group,
        "complexity": "vague"
    }


def escalation_ticket(ticket_id):
    """References prior tickets, reassignments, escalation context."""
    ci_name, ci_data, group = pick_ci_and_group()
    service = random.choice(ci_data["services"]) if ci_data["services"] else ci_name

    wrong_group = random.choice([g for g in resolver_groups if g != group])
    prior_ticket = f"INC{random.randint(800000, 999999):07d}"

    templates = [
        f"This is the 3rd time this ticket is being reassigned. Originally went to {wrong_group} who said it's not theirs. Then to {random.choice(resolver_groups)} who also bounced it. Issue is {service} on {ci_name}. Prior ticket {prior_ticket} had same problem. PLEASE route correctly this time.",
        f"Escalation: Ticket has been open for 5 days with no resolution. Currently assigned to {wrong_group} but they say the issue is on {ci_name} which is not their CI. {service} still down. Reassigning. See {prior_ticket} for full history.",
        f"Manager escalation. Original ticket {prior_ticket} was closed as 'resolved' but issue persists. {service} on {ci_name} still intermittent. {wrong_group} closed it claiming workaround applied. Need proper fix from correct team.",
        f"Re-opening issue from {prior_ticket}. Root cause was never addressed. {wrong_group} applied band-aid fix on {ci_name} but {service} keeps failing. Need the team that actually owns this CI to investigate properly.",
        f"SLA BREACH WARNING. Ticket bounced between {wrong_group} and {random.choice(resolver_groups)} for 3 days. Nobody owns the fix for {service} on {ci_name}. Escalating to service delivery manager. Ref: {prior_ticket}.",
    ]

    summary = f"Escalation: {service} on {ci_name} - reassignment"
    notes = random.choice(GREETINGS) + "\n\n" + random.choice(templates) + "\n\n" + random.choice(CLOSINGS)

    return {
        "ticket_id": ticket_id,
        "priority": random.choice(["P3", "P3"]),
        "category": random.choice(["Database", "Application", "Infrastructure", "Network", "Security"]),
        "summary": typo(summary),
        "notes": typo(notes),
        "ci_hint": ci_name,
        "prior_ticket": prior_ticket,
        "wrong_assignments": [wrong_group],
        "correct_resolver_group": group,
        "complexity": "escalation"
    }


def bulk_ci_ticket(ticket_id):
    """Mentions many CIs/services in raw dump format (like the real sample)."""
    ci_name, ci_data, group = pick_ci_and_group()

    # Generate a dump of services/CIs
    if "MSSQL" in str(ci_data.get("services", [])) or "sql" in ci_name.lower():
        db_names = [
            "MSSQL:" + name for name in random.sample([
                "TPSWebShop", "ChangeAuditor2014", "CTX-ITCLogging", "ActiveRoles73",
                "TPS_Performance", "CTX-ITCMonitoring", "msdb", "ITC_ICMS",
                "ReportServer", "BDSMgmt", "CTX-ITCSite", "master", "BDSMgmt_UDS",
                "ITC", "Airwatch", "ReportServerTempDB", "BillingCore", "BillingArchive",
                "RatingEngine", "TempDB", "model", "SSISDB", "DWH_Staging",
                "CRM_Analytics", "AuditLog", "ConfigMgr", "WSUS_DB",
            ], k=random.randint(5, 15))
        ]
        ci_dump = " ".join(db_names)
        context = f"please check the mode of sql db instances on host {ci_name}. {ci_dump}"
    elif "PostgreSQL" in str(ci_data.get("services", [])):
        dbs = random.sample([
            "crm_prod", "crm_audit", "crm_analytics", "crm_staging",
            "etl_workspace", "reporting_cache", "session_store",
        ], k=random.randint(3, 6))
        ci_dump = " ".join([f"PostgreSQL:{d}" for d in dbs])
        context = f"connection issues to PostgreSQL databases on {ci_name}: {ci_dump}"
    elif "SAP" in str(ci_data.get("services", [])):
        sap_items = random.sample([
            "SM21 showing W errors", "ST22 dumps increasing", "SM37 jobs stuck",
            "SM51 instance down", "STMS transport stuck", "SM12 lock entries growing",
            "SE16 table VBAK inconsistent", "SU01 user locks increasing",
            "SM66 long running processes", "AL11 file system full",
            "RZ20 CCMS alerts active", "SM04 orphaned sessions",
        ], k=random.randint(3, 7))
        ci_dump = "; ".join(sap_items)
        context = f"Multiple issues on {ci_name}: {ci_dump}"
    elif ci_data.get("type") == "network":
        interfaces = [f"Gi1/0/{random.randint(1,48)}" for _ in range(random.randint(3, 8))]
        ci_dump = ", ".join(interfaces)
        context = f"errors on {ci_name} interfaces: {ci_dump}. CRC errors and input drops."
    elif ci_data.get("type") == "storage":
        vols = [f"vol_{random.choice(['data','log','backup','temp','idx'])}_{random.randint(1,20):02d}" for _ in range(random.randint(3, 8))]
        ci_dump = ", ".join(vols)
        context = f"volume issues on {ci_name}: {ci_dump}. Space or performance."
    else:
        services = ci_data.get("services", ["unknown"])
        extra_svcs = random.sample([
            "httpd", "sshd", "crond", "rsyslog", "postfix",
            "docker", "kubelet", "containerd", "etcd",
            "prometheus", "grafana", "alertmanager",
        ], k=random.randint(2, 5))
        ci_dump = ", ".join(services + extra_svcs)
        context = f"services affected on {ci_name}: {ci_dump}"

    summary = f"Multiple items affected on {ci_name}"
    notes = f"{random.choice(GREETINGS)} {context} {random.choice(CLOSINGS)}"

    return {
        "ticket_id": ticket_id,
        "priority": random.choice(["P3", "P4"]),
        "category": random.choice(["Database", "Application", "Infrastructure", "Storage"]),
        "summary": typo(summary),
        "notes": typo(notes),
        "ci_hint": ci_name,
        "correct_resolver_group": group,
        "complexity": "bulk_ci_dump"
    }


def change_related_ticket(ticket_id):
    """Incident tied to a recent change, mentions CHG numbers."""
    ci_name, ci_data, group = pick_ci_and_group()
    service = random.choice(ci_data["services"]) if ci_data["services"] else ci_name

    chg = f"CHG{random.randint(100000, 999999)}"
    change_window = f"{random.randint(0,5):02d}:00-{random.randint(5,8):02d}:00 UTC"

    templates = [
        f"Post-change incident. {chg} was implemented last night ({change_window}) on {ci_name}. {service} has not been functioning correctly since. Change was: {random.choice(['firmware upgrade', 'security patch', 'config update', 'certificate renewal', 'OS patch', 'application deployment', 'network ACL change', 'storage expansion', 'DB maintenance'])}. Need owning team to verify and potentially roll back.",
        f"Possible change-related failure. {service} on {ci_name} started failing at {random.randint(0,23):02d}:{random.randint(0,59):02d}. Correlates with {chg} completion time. Change record says low risk but impact is P3. Please review.",
        f"Emergency: {chg} broke {service} on {ci_name}. Users impacted immediately after change window closed. Need urgent rollback assessment. Change implementer says they followed the plan exactly.",
        f"{chg} post-implementation check failed for {ci_name}. {service} health check returning errors. Backout plan available but needs approval. Owning team please assess damage and decide on rollback vs fix-forward.",
    ]

    summary = f"Post-change issue: {ci_name} - {chg}"
    notes = random.choice(GREETINGS) + "\n\n" + random.choice(templates) + "\n\n" + random.choice(CLOSINGS)

    return {
        "ticket_id": ticket_id,
        "priority": random.choice(["P3", "P3"]),
        "category": random.choice(["Database", "Application", "Infrastructure", "Network", "Security"]),
        "summary": summary,
        "notes": typo(notes),
        "ci_hint": ci_name,
        "change_ref": chg,
        "correct_resolver_group": group,
        "complexity": "change_related"
    }


def outage_ticket(ticket_id):
    """Major outage with bridge call, timeline, multiple stakeholders."""
    ci_name, ci_data, group = pick_ci_and_group()
    service = random.choice(ci_data["services"]) if ci_data["services"] else ci_name
    deps = ci_data.get("dependencies", [])
    biz = ci_data.get("business_function", "IT")

    bridge_id = random.randint(100000, 999999)
    impact_users = random.randint(500, 50000)

    timeline_entries = [
        f"{random.randint(0,23):02d}:{random.randint(0,59):02d} - First alert received from monitoring",
        f"{random.randint(0,23):02d}:{random.randint(0,59):02d} - Incident bridge opened (ID: {bridge_id})",
        f"{random.randint(0,23):02d}:{random.randint(0,59):02d} - {service} confirmed down on {ci_name}",
        f"{random.randint(0,23):02d}:{random.randint(0,59):02d} - Attempted service restart - failed",
        f"{random.randint(0,23):02d}:{random.randint(0,59):02d} - Root cause suspected: {random.choice(['memory leak', 'disk full', 'network partition', 'certificate expiry', 'config corruption', 'hardware failure'])}",
    ]

    dep_text = ""
    if deps:
        dep_text = f"\n\nDownstream impact: {', '.join(deps[:3])}"

    notes = (
        f"MAJOR INCIDENT - {biz}\n"
        f"Bridge: {bridge_id} | Impact: {impact_users} users | Priority: CRITICAL\n\n"
        f"Timeline:\n" + "\n".join(timeline_entries) +
        f"\n\nPrimary CI: {ci_name}\nAffected service: {service}"
        f"{dep_text}\n\n"
        f"Action required: Owning resolver group to join bridge immediately.\n"
        f"Comms sent to: {biz} leadership, Service Delivery, {random.choice(USERS)} (account manager)\n\n"
        f"{random.choice(CLOSINGS)}"
    )

    summary = f"MAJOR INCIDENT: {biz} - {service} outage"

    return {
        "ticket_id": ticket_id,
        "priority": "P3",
        "category": random.choice(["Application", "Infrastructure", "Database"]),
        "summary": summary,
        "notes": notes,
        "ci_hint": ci_name,
        "correct_resolver_group": group,
        "complexity": "major_outage"
    }


def misrouted_context_ticket(ticket_id):
    """Ticket where notes mention a symptom CI but root cause is elsewhere."""
    # Pick a dependency as the real root cause
    ci_name, ci_data, group = pick_ci_and_group()
    deps = ci_data.get("dependencies", [])

    if deps and deps[0] in cis:
        root_ci = deps[0]
        root_data = cis[root_ci]
        root_group = root_data["resolver_group"]
        root_service = random.choice(root_data["services"]) if root_data["services"] else root_ci
    else:
        root_ci, root_data, root_group = pick_ci_and_group()
        root_service = random.choice(root_data["services"]) if root_data["services"] else root_ci

    symptom_service = random.choice(ci_data["services"]) if ci_data["services"] else ci_name

    templates = [
        f"Users see errors in {symptom_service} on {ci_name} but after initial investigation, the actual issue is on {root_ci}. {root_service} is not responding. {ci_name} is just showing symptoms because it depends on {root_ci}. Please route to the team that owns {root_ci}.",
        f"Ticket originally raised for {ci_name} ({symptom_service}) but L1 investigation shows {root_ci} ({root_service}) is the root cause. Dependency: {ci_name} -> {root_ci}. Reassigning to correct team.",
        f"False alarm on {ci_name}. Real issue is {root_service} on {root_ci}. Application team confirmed {symptom_service} errors are caused by backend dependency failure. Please route to {root_ci} owners.",
    ]

    summary = f"Root cause on {root_ci} - symptoms on {ci_name}"
    notes = random.choice(GREETINGS) + "\n\n" + random.choice(templates) + "\n\n" + random.choice(CLOSINGS)

    return {
        "ticket_id": ticket_id,
        "priority": random.choice(["P3", "P4"]),
        "category": random.choice(["Application", "Infrastructure", "Database"]),
        "summary": typo(summary),
        "notes": typo(notes),
        "ci_hint": root_ci,
        "symptom_ci": ci_name,
        "correct_resolver_group": root_group,
        "complexity": "misrouted_context"
    }


def batch_alert_ticket(ticket_id):
    """Auto-generated ticket from monitoring with multiple alerts pasted in."""
    ci_name, ci_data, group = pick_ci_and_group()

    alerts = [gen_monitoring_alert(ci_name) for _ in range(random.randint(3, 8))]

    # Sometimes include alerts from other CIs (noise)
    noise_cis = random.sample(list(cis.keys()) + EXTRA_HOSTS, k=random.randint(0, 3))
    for noise_ci in noise_cis:
        alerts.append(gen_monitoring_alert(noise_ci))
    random.shuffle(alerts)

    notes = (
        f"Auto-generated ticket from monitoring consolidation.\n\n"
        f"Alerts:\n" + "\n".join([f"  [{i+1}] {a}" for i, a in enumerate(alerts)]) +
        f"\n\nPrimary CI based on alert volume: {ci_name}\n"
        f"Auto-classification: {ci_data.get('business_function', 'Unknown')}\n"
        f"Please review and assign to appropriate resolver group."
    )

    summary = f"Consolidated monitoring alerts - {ci_name}"

    return {
        "ticket_id": ticket_id,
        "priority": random.choice(["P3", "P4"]),
        "category": "Monitoring",
        "summary": summary,
        "notes": notes,
        "ci_hint": ci_name,
        "correct_resolver_group": group,
        "complexity": "batch_alerts"
    }


# Distribution of complexity tiers
GENERATORS = [
    (simple_ticket, 0.15),         # 15% straightforward
    (multi_ci_ticket, 0.15),       # 15% multi-CI cascade
    (ambiguous_ticket, 0.12),      # 12% ambiguous ownership
    (error_log_ticket, 0.12),      # 12% pasted error logs
    (vague_ticket, 0.10),          # 10% vague/non-technical
    (escalation_ticket, 0.08),     # 8% escalation/reassignment
    (bulk_ci_ticket, 0.08),        # 8% bulk CI dump (like real sample)
    (change_related_ticket, 0.07), # 7% change-related
    (outage_ticket, 0.05),         # 5% major outage
    (misrouted_context_ticket, 0.05), # 5% misrouted
    (batch_alert_ticket, 0.03),    # 3% auto-generated alert consolidation
]

def generate_tickets(n=1000):
    tickets = []
    generators = []
    weights = []
    for gen, weight in GENERATORS:
        generators.append(gen)
        weights.append(weight)

    for i in range(n):
        ticket_id = f"INC{2000001 + i}"
        gen = random.choices(generators, weights=weights, k=1)[0]
        ticket = gen(ticket_id)
        tickets.append(ticket)

    return tickets


if __name__ == "__main__":
    tickets = generate_tickets(1000)

    # Stats
    complexity_counts = {}
    group_counts = {}
    for t in tickets:
        c = t.get("complexity", "unknown")
        complexity_counts[c] = complexity_counts.get(c, 0) + 1
        g = t["correct_resolver_group"]
        group_counts[g] = group_counts.get(g, 0) + 1

    print("Generated 1000 tickets")
    print("\nComplexity distribution:")
    for k, v in sorted(complexity_counts.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print("\nResolver group distribution:")
    for k, v in sorted(group_counts.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    Path("tickets_1000.json").write_text(json.dumps(tickets, indent=2))
    print("\nWritten to tickets_1000.json")
