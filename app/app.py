
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
excluir_ns_patterns = []
cache_resultados = {"np": [], "quota": []}

egressip_total = Gauge('egressip_total', 'Total de IPs disponibles en la VLAN', registry=registry)
egresip_uso = Gauge('egresip_uso', 'IPs en uso (egressips + nodos)', registry=registry)
ns_sin_np_total = Gauge('namespaces_sin_networkpolicy_total', 'Total de namespaces sin NetworkPolicy', registry=registry)
ns_sin_np_label = Gauge('namespace_sin_networkpolicy', 'Namespace sin NetworkPolicy', ['namespace'], registry=registry)
ns_quota_total = Gauge('namespaces_sin_resourcequota_total', 'Total de namespaces sin ResourceQuotas', registry=registry)
ns_quota_label = Gauge('namespace_sin_quota', 'Namespace sin ResourceQuota', ['namespace'], registry=registry)

def excluir_ns(ns):
    return any(fnmatch.fnmatch(ns, pattern) for pattern in excluir_ns_patterns)

@app.route("/")
def home():
    total_ips = len(list(ipaddress.ip_network(subnet_cidr).hosts()))
    used = len(cache_resultados["np"])
    libres = total_ips - used
    pie_data = f"{used},{libres},{total_ips}"
    return render_template("home.html", subnet=subnet_cidr, pie_data=pie_data,
                           np=cache_resultados["np"], quota=cache_resultados["quota"])

@app.route("/metrics")
def metrics():
    return Response(generate_latest(registry), mimetype="text/plain")

def actualizar_metricas():
    logging.debug("⏳ Ejecutando actualización periódica de métricas")

    def run_cmd(desc, cmd):
        try:
            logging.debug(f"➡️ Ejecutando: {' '.join(cmd)}")
            result = subprocess.check_output(cmd, text=True)
            logging.debug(f"✅ Resultado {desc}:\n{result.strip()}")
            return result.strip().splitlines()
        except Exception as e:
            logging.warning(f"❌ Error en {desc}: {e}")
            return []

    egress = run_cmd("egressip", ["oc", "get", "egressip", "-A", "-o", "jsonpath={range .items[*]}{.status.assignedIP}\n{end}"])
    nodes = run_cmd("nodos", ["oc", "get", "nodes", "-o", "name"])
    used = len(egress) + len(nodes)
    total = len(list(ipaddress.ip_network(subnet_cidr).hosts()))
    egressip_total.set(total)
    egresip_uso.set(used)

    ns_list = run_cmd("namespaces", ["oc", "get", "ns", "-o", "jsonpath={range .items[*]}{.metadata.name}\n{end}"])
    ns_list = [ns for ns in ns_list if not excluir_ns(ns)]

    sin_np = [ns for ns in ns_list if not run_cmd(f"networkpolicy en {ns}", ["oc", "get", "networkpolicy", "-n", ns])]
    cache_resultados["np"] = sin_np
    ns_sin_np_total.set(len(sin_np))
    for ns in sin_np:
        ns_sin_np_label.labels(namespace=ns).set(1)

    sin_quota = [ns for ns in ns_list if not run_cmd(f"quotas en {ns}", ["oc", "get", "resourcequota", "-n", ns])]
    cache_resultados["quota"] = sin_quota
    ns_quota_total.set(len(sin_quota))
    for ns in sin_quota:
        ns_quota_label.labels(namespace=ns).set(1)

    Timer(60, actualizar_metricas).start()

def create_app(config_path=os.getenv("CONFIG_PATH", "config.json")):
    global subnet_cidr, excluir_ns_patterns, cache_resultados

    with open(config_path) as f:
        config = json.load(f)

    subnet_cidr = config.get("subnet", "192.168.1.0/24")
    excluir_ns_patterns = config.get("exclude_namespaces", [])
    cache_resultados = {"np": [], "quota": []}
    return app

if __name__ == "__main__":
    create_app()
    actualizar_metricas()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=debug_mode, use_reloader=debug_mode)
