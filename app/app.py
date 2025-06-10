
import os
import subprocess
import ipaddress
import json
import logging
import fnmatch
import ssl
import tempfile
import datetime
import time
from threading import Timer
from flask import Flask, Response, render_template
from prometheus_client import Gauge, generate_latest, CollectorRegistry

registry = CollectorRegistry()
debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
log_level = logging.DEBUG if debug_mode else logging.INFO
logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__, static_folder='static', template_folder='templates')

@app.template_filter('datetime')
def _format_datetime(value):
    try:
        return datetime.datetime.fromtimestamp(int(value)).strftime('%Y-%m-%d')
    except Exception:
        return ''

subnet_cidr = "192.168.1.0/24"
exclude_ns_patterns = []
feature_ns_exclusions = {}
update_seconds = 60
days_threshold = 180
enabled_features = {
    "np": True,
    "quota": True,
    "pv_unbound": True,
    "pvc_pending": True,
    "single_replica": True,
    "no_resources": True,
    "priv_sa": True,
    "no_antiaffinity": True,
    "route_cert": True,
}
scc_types = ["restricted", "anyuid", "hostaccess", "hostmount-anyuid", "privileged"]
cache_results = {
    "np": [],
    "quota": [],
    "pv_unbound": [],
    "pvc_pending": [],
    "single_replica": [],
    "no_resources": [],
    "priv_sa": [],
    "no_antiaffinity": [],
    "route_cert": []
}
cache_ips = {"nodes": [], "egress": []}

ip_pool_total = Gauge('ip_pool_total', 'Total IPs available in the VLAN', registry=registry)
ip_pool_used = Gauge('ip_pool_used', 'IPs in use (egressips + nodos)', registry=registry)
egressips_used = Gauge('egressips_used', 'IPs in use egress', registry=registry)
nodesips_used = Gauge('nodesips_used', 'IPs in use nodes)', registry=registry)
ns_without_np_total = Gauge('namespaces_without_networkpolicy_total', 'Total namespaces without NetworkPolicy', registry=registry)
ns_without_np_label = Gauge('namespace_without_networkpolicy', 'Namespace without NetworkPolicy', ['namespace'], registry=registry)
ns_quota_total = Gauge('namespaces_without_resourcequota_total', 'Total namespaces without ResourceQuotas', registry=registry)
ns_quota_label = Gauge('namespace_without_resourcequota', 'Namespace without ResourceQuota', ['namespace'], registry=registry)

# PVC metrics
pv_unbound_total = Gauge('pv_unbound_total', 'Total PVs not bound to any PVC', registry=registry)
pv_unbound_info = Gauge('pv_unbound', 'PV not bound to any PVC', ['pv'], registry=registry)
pvc_pending_total = Gauge('pvc_pending_total', 'Total PVCs pending', registry=registry)
pvc_pending_info = Gauge('pvc_pending', 'PVC in Pending state', ['namespace', 'pvc'], registry=registry)

# Workload metrics
workload_single_replica_total = Gauge(
    'workloads_single_replica_total',
    'Total Deployments/StatefulSets with a single replica',
    registry=registry)
workload_single_replica_info = Gauge(
    'workload_single_replica',
    'Deployment/StatefulSet running with one replica',
    ['namespace', 'app', 'kind'], registry=registry)

workload_no_resources_total = Gauge(
    'workloads_no_resources_total',
    'Total Deployments/StatefulSets without resource requests/limits',
    registry=registry)
workload_no_resources_info = Gauge(
    'workload_no_resources',
    'Deployment/StatefulSet without resource requests/limits',
    ['namespace', 'app', 'kind'], registry=registry)

# Workloads missing anti-affinity rules
workload_no_antiaffinity_total = Gauge(
    'workloads_no_antiaffinity_total',
    'Total Deployments/StatefulSets without anti-affinity rules',
    registry=registry)
workload_no_antiaffinity_info = Gauge(
    'workload_no_antiaffinity',
    'Deployment/StatefulSet without anti-affinity rules',
    ['namespace', 'app', 'kind'], registry=registry)

# Privileged service accounts metrics
priv_sa_total = Gauge(
    'privileged_serviceaccount_total',
    'Total workloads using privileged service accounts',
    registry=registry)
priv_sa_info = Gauge(
    'privileged_serviceaccount',
    'Workload using privileged service account and SCC',
    ['namespace', 'app', 'serviceaccount', 'scc'], registry=registry)

# HTTPS route certificate metrics
routes_cert_expiring_total = Gauge(
    'routes_cert_expiring_total',
    'Total HTTPS routes with certificates expiring soon',
    registry=registry)
route_cert_expiry_timestamp = Gauge(
    'route_cert_expiry_timestamp',
    'Days until route TLS certificate expires (expiry_date label shows date)',
    ['namespace', 'route', 'host', 'expiry_date'],
    registry=registry)

def exclude_ns(ns, feature=None):
    patterns = list(exclude_ns_patterns)
    if feature and feature in feature_ns_exclusions:
        patterns.extend(feature_ns_exclusions.get(feature, []))
    return any(fnmatch.fnmatch(ns, p) for p in patterns)

@app.route("/")
def home():
    total_ips = len(list(ipaddress.ip_network(subnet_cidr).hosts()))
    used = len(cache_ips["egress"]) + len(cache_ips["nodes"])
    ip_free = total_ips - used
    pie_data = f"{used},{ip_free},{total_ips}"
    ips = [{"type": "nodo", "ip": ip} for ip in cache_ips["nodes"]] + [{"type": "egress", "ip": ip} for ip in cache_ips["egress"]]
    ips = sorted(ips, key=lambda x: x["type"])
    return render_template(
        "home.html",
        subnet=subnet_cidr,
        pie_data=pie_data,
        np=cache_results["np"],
        quota=cache_results["quota"],
        pv_unbound=cache_results["pv_unbound"],
        pvc_pending=cache_results["pvc_pending"],
        single_replica=cache_results["single_replica"],
        no_resources=cache_results["no_resources"],
        no_antiaffinity=cache_results["no_antiaffinity"],
        priv_sa=cache_results["priv_sa"],
        route_cert=cache_results["route_cert"],
        ips=ips,
    )

@app.route("/metrics")
def metrics():
    return Response(generate_latest(registry), mimetype="text/plain")

@app.route("/healthz")
def healthz():
    return "OK", 200

def get_cert_expiry(cert_pem: str) -> int:
    """Return expiration timestamp from a PEM certificate."""
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(cert_pem.encode())
            tmp.flush()
            info = ssl._ssl._test_decode_cert(tmp.name)
        na = info.get('notAfter')
        if na:
            dt = datetime.datetime.strptime(na, "%b %d %H:%M:%S %Y %Z")
            return int(dt.timestamp())
    except Exception as e:
        logging.warning(f"Could not parse certificate expiry: {e}")
    return 0

def update_metrics():
    logging.debug("⏳ Running periodic metrics update")

    def run_cmd(desc, cmd):
        try:
            logging.debug(f"➡️ Running: {' '.join(cmd)}")
            result = subprocess.check_output(cmd, text=True)
            logging.debug(f"✅ Result {desc}:{result.strip()}")
            return result.strip().splitlines()
        except Exception as e:
            logging.warning(f"❌ Error at {desc}: {e}")
            return []

    def run_cmd_json(desc, cmd):
        lines = run_cmd(desc, cmd)
        try:
            return json.loads("\n".join(lines)) if lines else {}
        except Exception as e:
            logging.warning(f"❌ JSON parse error at {desc}: {e}")
            return {}

    # Egress IPs from spec.egressIPs
    #oc get egressip -A -o jsonpath='{range .items[*]}{.spec.egressIPs[*]}{"\n"}{end}'
    egress = run_cmd("egressip", [
        "oc", "get", "egressip", "-A", "-o",
        "jsonpath={range .items[*]}{.spec.egressIPs[*]}{.}{'\\n'}{end}"
    ])
    egress = [ip.strip() for ip in egress if ip.strip()]
    logging.debug(f"📤 Egress IPs processed: {egress}")

    # Node IPs (InternalIP only)
    raw_nodes = run_cmd("nodos", [
        "oc", "get", "nodes", "-o",
        "jsonpath={range .items[*]}{range .status.addresses[*]}{.type}:{.address}\n{end}{end}"
    ])
    nodes = [line.split(":", 1)[1] for line in raw_nodes if line.startswith("InternalIP:")]
    logging.debug(f"📤 Processed node IPs: {nodes}")

    cache_ips["egress"] = egress
    cache_ips["nodes"] = nodes

    used = len(egress) + len(nodes)
    total = len(list(ipaddress.ip_network(subnet_cidr).hosts()))
    ip_pool_total.set(total)
    ip_pool_used.set(used)
    nodesips_used.set(len(nodes))
    egressips_used.set(len(egress))

    ns_list = []
    if enabled_features.get("np") or enabled_features.get("quota"):
        ns_list = run_cmd("namespaces", ["oc", "get", "ns", "-o", "jsonpath={range .items[*]}{.metadata.name}\n{end}"])

    if enabled_features.get("np"):
        ns_list_np = [ns for ns in ns_list if not exclude_ns(ns, "np")]
        without_np = [ns for ns in ns_list_np if not run_cmd(f"networkpolicy in {ns}", ["oc", "get", "networkpolicy", "-n", ns])]
        cache_results["np"] = without_np
        ns_without_np_total.set(len(without_np))
        for ns in without_np:
            ns_without_np_label.labels(namespace=ns).set(1)
    else:
        cache_results["np"] = []
        ns_without_np_total.set(0)

    if enabled_features.get("quota"):
        ns_list_quota = [ns for ns in ns_list if not exclude_ns(ns, "quota")]
        namespace_without_resourcequota = [ns for ns in ns_list_quota if not run_cmd(f"quotas in {ns}", ["oc", "get", "resourcequota", "-n", ns])]
        cache_results["quota"] = namespace_without_resourcequota
        ns_quota_total.set(len(namespace_without_resourcequota))
        for ns in namespace_without_resourcequota:
            ns_quota_label.labels(namespace=ns).set(1)
    else:
        cache_results["quota"] = []
        ns_quota_total.set(0)

    if enabled_features.get("pvc_pending"):
        pvc_data = run_cmd_json("pvcs", ["oc", "get", "pvc", "-A", "-o", "json"])
        pvc_pending = []
        for pvc in pvc_data.get("items", []):
            ns = pvc["metadata"].get("namespace")
            if exclude_ns(ns, "pvc_pending"):
                continue
            name = pvc["metadata"]["name"]
            phase = pvc.get("status", {}).get("phase", "").lower()
            if phase == "pending":
                pvc_pending.append({"namespace": ns, "name": name})
        cache_results["pvc_pending"] = pvc_pending
        pvc_pending_total.set(len(pvc_pending))
        for p in pvc_pending:
            pvc_pending_info.labels(namespace=p["namespace"], pvc=p["name"]).set(1)
    else:
        cache_results["pvc_pending"] = []
        pvc_pending_total.set(0)

    if enabled_features.get("pv_unbound"):
        pv_data = run_cmd_json("pvs", ["oc", "get", "pv", "-o", "json"])
        pv_unbound = []
        for pv in pv_data.get("items", []):
            name = pv["metadata"].get("name")
            phase = pv.get("status", {}).get("phase", "").lower()
            if phase != "bound":
                pv_unbound.append({"name": name})
        cache_results["pv_unbound"] = [p["name"] for p in pv_unbound]
        pv_unbound_total.set(len(pv_unbound))
        for p in pv_unbound:
            pv_unbound_info.labels(pv=p["name"]).set(1)
    else:
        cache_results["pv_unbound"] = []
        pv_unbound_total.set(0)

    workloads_enabled = (
        enabled_features.get("single_replica")
        or enabled_features.get("no_resources")
        or enabled_features.get("priv_sa")
        or enabled_features.get("no_antiaffinity")
    )
    single_replica = []
    no_resources = []
    workload_sa = []
    no_antiaffinity = []
    if workloads_enabled:
        deploys = run_cmd_json("deployments", ["oc", "get", "deploy", "-A", "-o", "json"])
        sts = run_cmd_json("statefulsets", ["oc", "get", "statefulset", "-A", "-o", "json"])

        def process_workloads(items, kind):
            for it in items.get("items", []):
                ns = it["metadata"].get("namespace")
                name = it["metadata"]["name"]
                replicas = it.get("spec", {}).get("replicas", 1)
                sa = it.get("spec", {}).get("template", {}).get("spec", {}).get("serviceAccountName", "default")
                containers = it.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
                affinity = it.get("spec", {}).get("template", {}).get("spec", {}).get("affinity", {})
                has_anti = bool(affinity.get("podAntiAffinity"))
                if enabled_features.get("single_replica") and replicas <= 2 and not exclude_ns(ns, "single_replica"):
                    single_replica.append({"namespace": ns, "name": name, "kind": kind})
                if enabled_features.get("no_resources") and not exclude_ns(ns, "no_resources"):
                    no_resources.append({"namespace": ns, "name": name, "kind": kind})
                if enabled_features.get("priv_sa") and not exclude_ns(ns, "priv_sa"):
                    workload_sa.append({"namespace": ns, "name": name, "sa": sa, "kind": kind})
                if enabled_features.get("no_antiaffinity") and not has_anti and not exclude_ns(ns, "no_antiaffinity"):
                    no_antiaffinity.append({"namespace": ns, "name": name, "kind": kind})

        process_workloads(deploys, "deployment")
        process_workloads(sts, "statefulset")

    if enabled_features.get("single_replica"):
        cache_results["single_replica"] = single_replica
        workload_single_replica_total.set(len(single_replica))
        for w in single_replica:
            workload_single_replica_info.labels(namespace=w["namespace"], app=w["name"], kind=w["kind"]).set(1)
    else:
        cache_results["single_replica"] = []
        workload_single_replica_total.set(0)

    if enabled_features.get("no_resources"):
        cache_results["no_resources"] = no_resources
        workload_no_resources_total.set(len(no_resources))
        for w in no_resources:
            workload_no_resources_info.labels(namespace=w["namespace"], app=w["name"], kind=w["kind"]).set(1)
    else:
        cache_results["no_resources"] = []
        workload_no_resources_total.set(0)

    if enabled_features.get("no_antiaffinity"):
        cache_results["no_antiaffinity"] = no_antiaffinity
        workload_no_antiaffinity_total.set(len(no_antiaffinity))
        for w in no_antiaffinity:
            workload_no_antiaffinity_info.labels(
                namespace=w["namespace"], app=w["name"], kind=w["kind"]
            ).set(1)
    else:
        cache_results["no_antiaffinity"] = []
        workload_no_antiaffinity_total.set(0)

    if enabled_features.get("priv_sa"):
        sccs = run_cmd_json("scc", ["oc", "get", "scc", "-o", "json"])
        rbs = run_cmd_json("rolebindings", ["oc", "get", "rolebinding", "-A", "-o", "json"])
        crbs = run_cmd_json("clusterrolebindings", ["oc", "get", "clusterrolebinding", "-o", "json"])

        def parse_scc_from_role(name):
            prefix = "system:openshift:scc:"
            if name and name.startswith(prefix):
                return name[len(prefix):]
            return None

        sa_scc = {}
        for scc in sccs.get("items", []):
            scc_name = scc.get("metadata", {}).get("name")
            for user in scc.get("users", []) or []:
                if user.startswith("system:serviceaccount:"):
                    parts = user.split(":")
                    if len(parts) == 4:
                        sa_scc[(parts[2], parts[3])] = scc_name

        for rb in rbs.get("items", []):
            scc_name = parse_scc_from_role(rb.get("roleRef", {}).get("name"))
            if not scc_name:
                continue
            ns = rb.get("metadata", {}).get("namespace")
            for subj in rb.get("subjects", []) or []:
                if subj.get("kind") == "ServiceAccount":
                    sa_ns = subj.get("namespace", ns)
                    sa_scc[(sa_ns, subj.get("name"))] = scc_name

        for crb in crbs.get("items", []):
            scc_name = parse_scc_from_role(crb.get("roleRef", {}).get("name"))
            if not scc_name:
                continue
            for subj in crb.get("subjects", []) or []:
                if subj.get("kind") == "ServiceAccount":
                    sa_ns = subj.get("namespace")
                    sa_scc[(sa_ns, subj.get("name"))] = scc_name

        priv_list = []
        for w in workload_sa:
            key = (w["namespace"], w["sa"])
            scc_name = sa_scc.get(key, "restricted")
            if scc_types and scc_name not in scc_types:
                continue
            priv_list.append({
                "namespace": w["namespace"],
                "name": w["name"],
                "sa": w["sa"],
                "scc": scc_name,
            })

        cache_results["priv_sa"] = priv_list
        priv_sa_total.set(len(priv_list))
        for p in priv_list:
            priv_sa_info.labels(namespace=p["namespace"], app=p["name"], serviceaccount=p["sa"], scc=p["scc"]).set(1)
    else:
        cache_results["priv_sa"] = []
        priv_sa_total.set(0)

    if enabled_features.get("route_cert"):
        route_data = run_cmd_json("routes", ["oc", "get", "route", "-A", "-o", "json"])
        route_list = []
        expiring = 0
        now = int(time.time())
        for rt in route_data.get("items", []):
            ns = rt.get("metadata", {}).get("namespace")
            if exclude_ns(ns, "route_cert"):
                continue
            name = rt.get("metadata", {}).get("name")
            host = rt.get("spec", {}).get("host", "")
            tls = rt.get("spec", {}).get("tls") or {}
            cert = tls.get("certificate")
            if not cert:
                continue
            expiry = get_cert_expiry(cert)
            expiry_date = datetime.datetime.fromtimestamp(expiry).strftime('%Y-%m-%d') if expiry else ''
            days_left = int((expiry - now) // 86400) if expiry else 0
            route_cert_expiry_timestamp.labels(
                namespace=ns,
                route=name,
                host=host,
                expiry_date=expiry_date,
            ).set(days_left)
            if expiry and expiry - now <= days_threshold * 86400:
                route_list.append({"namespace": ns, "name": name, "host": host, "expiry": expiry})
                expiring += 1
        cache_results["route_cert"] = sorted(route_list, key=lambda x: x["expiry"])
        routes_cert_expiring_total.set(expiring)
    else:
        cache_results["route_cert"] = []
        routes_cert_expiring_total.set(0)

    Timer(update_seconds, update_metrics).start()

def create_app(config_path=os.getenv("CONFIG_PATH", "config.json")):
    global subnet_cidr, exclude_ns_patterns, feature_ns_exclusions, cache_results, update_seconds, enabled_features, days_threshold, scc_types

    with open(config_path) as f:
        config = json.load(f)

    subnet_cidr = config.get("subnet", "192.168.1.0/24")
    exclude_ns_patterns = config.get("exclude_namespaces", [])
    feature_ns_exclusions = config.get("feature_exclusions", {})
    enabled_features = config.get("enabled_features", enabled_features)
    update_seconds = int(config.get("update_seconds", 60))
    days_threshold = int(config.get("days", days_threshold))
    scc_types = config.get("scc_types", scc_types)
    cache_results.update({
        "np": [],
        "quota": [],
        "pv_unbound": [],
        "pvc_pending": [],
        "single_replica": [],
        "no_resources": [],
        "no_antiaffinity": [],
        "priv_sa": [],
        "route_cert": []
    })
    return app

if __name__ == "__main__":
    create_app()
    update_metrics()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=debug_mode, use_reloader=debug_mode)
