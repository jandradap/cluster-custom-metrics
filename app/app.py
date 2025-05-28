
import os
import subprocess
import ipaddress
import json
import logging
import fnmatch
from threading import Timer
from flask import Flask, Response, render_template
from prometheus_client import Gauge, generate_latest, CollectorRegistry

registry = CollectorRegistry()
debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
log_level = logging.DEBUG if debug_mode else logging.INFO
logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__, static_folder='static', template_folder='templates')

subnet_cidr = "192.168.1.0/24"
exclude_ns_patterns = []
cache_results = {"np": [], "quota": []}
cache_ips = {"nodes": [], "egress": []}

ip_pool_total = Gauge('ip_pool_total', 'Total IPs available in the VLAN', registry=registry)
ip_pool_used = Gauge('ip_pool_used', 'IPs in use (egressips + nodos)', registry=registry)
egressips_used = Gauge('egressips_used', 'IPs in use egress', registry=registry)
nodesips_used = Gauge('nodesips_used', 'IPs in use nodes)', registry=registry)
ns_without_np_total = Gauge('namespaces_without_networkpolicy_total', 'Total namespaces without NetworkPolicy', registry=registry)
ns_without_np_label = Gauge('namespace_without_networkpolicy', 'Namespace without NetworkPolicy', ['namespace'], registry=registry)
ns_quota_total = Gauge('namespaces_without_resourcequota_total', 'Total namespaces without ResourceQuotass', registry=registry)
ns_quota_label = Gauge('namespace_namespace_without_resourcequota', 'Namespace without ResourceQuota', ['namespace'], registry=registry)

def exclude_ns(ns):
    return any(fnmatch.fnmatch(ns, pattern) for pattern in exclude_ns_patterns)

@app.route("/")
def home():
    total_ips = len(list(ipaddress.ip_network(subnet_cidr).hosts()))
    used = len(cache_ips["egress"]) + len(cache_ips["nodes"])
    ip_free = total_ips - used
    pie_data = f"{used},{ip_free},{total_ips}"
    ips = [{"type": "nodo", "ip": ip} for ip in cache_ips["nodes"]] + [{"type": "egress", "ip": ip} for ip in cache_ips["egress"]]
    ips = sorted(ips, key=lambda x: x["type"])
    return render_template("home.html", subnet=subnet_cidr, pie_data=pie_data,
                           np=cache_results["np"], quota=cache_results["quota"], ips=ips)

@app.route("/metrics")
def metrics():
    return Response(generate_latest(registry), mimetype="text/plain")

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

    ns_list = run_cmd("namespaces", ["oc", "get", "ns", "-o", "jsonpath={range .items[*]}{.metadata.name}\n{end}"])
    ns_list = [ns for ns in ns_list if not exclude_ns(ns)]

    without_np = [ns for ns in ns_list if not run_cmd(f"networkpolicy in {ns}", ["oc", "get", "networkpolicy", "-n", ns])]
    cache_results["np"] = without_np
    ns_without_np_total.set(len(without_np))
    for ns in without_np:
        ns_without_np_label.labels(namespace=ns).set(1)

    namespace_without_resourcequota = [ns for ns in ns_list if not run_cmd(f"quotas in {ns}", ["oc", "get", "resourcequota", "-n", ns])]
    cache_results["quota"] = namespace_without_resourcequota
    ns_quota_total.set(len(namespace_without_resourcequota))
    for ns in namespace_without_resourcequota:
        ns_quota_label.labels(namespace=ns).set(1)

    Timer(60, update_metrics).start()

def create_app(config_path=os.getenv("CONFIG_PATH", "config.json")):
    global subnet_cidr, exclude_ns_patterns, cache_results

    with open(config_path) as f:
        config = json.load(f)

    subnet_cidr = config.get("subnet", "192.168.1.0/24")
    exclude_ns_patterns = config.get("exclude_namespaces", [])
    cache_results.update({"np": [], "quota": []})
    return app

if __name__ == "__main__":
    create_app()
    update_metrics()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=debug_mode, use_reloader=debug_mode)
