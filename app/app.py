from flask import Flask, Response, request, render_template_string, send_from_directory
from prometheus_client import Gauge, generate_latest, CollectorRegistry
import subprocess, os, ipaddress

app = Flask(__name__, static_folder='static')
registry = CollectorRegistry()

subnet_cidr = os.getenv("SUBNET", "192.168.1.0/24")

egressip_total = Gauge('egressip_total', 'Total de IPs disponibles en la VLAN', registry=registry)
egresip_uso = Gauge('egressip_uso', 'IPs en uso (egressips + nodos)', registry=registry)

ns_sin_np_total = Gauge('namespaces_sin_networkpolicy_total', 'Total de namespaces sin NetworkPolicy', registry=registry)
ns_sin_np_label = Gauge('namespace_sin_networkpolicy', 'Namespace sin NetworkPolicy', ['namespace'], registry=registry)

ns_crashloop_total = Gauge('namespaces_con_pods_crashloop_total', 'Total de namespaces con pods en CrashLoopBackOff', registry=registry)
ns_crashloop_label = Gauge('namespace_crashloop', 'Namespace con pods en CrashLoopBackOff', ['namespace'], registry=registry)

ns_quota_total = Gauge('namespaces_sin_resourcequota_total', 'Total de namespaces sin ResourceQuotas', registry=registry)
ns_quota_label = Gauge('namespace_sin_quota', 'Namespace sin ResourceQuota', ['namespace'], registry=registry)

cache_resultados = { "np": [], "crashloop": [], "quota": [] }

@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

@app.route("/")
def home():
    total_ips = len(list(ipaddress.ip_network(subnet_cidr).hosts()))
    used = len(cache_resultados["np"]) + len(cache_resultados["crashloop"])
    libres = total_ips - used
    pie_data = f"{used},{libres}"
    return render_template_string("""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Métricas EgressIP</title>
            <script src="/static/chart.min.js"></script>
            <meta http-equiv="refresh" content="60">
            <style>
                body {
                    font-family: 'RedHatDisplay', sans-serif;
                    background-color: #f5f5f5;
                    padding: 2em;
                    color: #003366;
                }
                h2 {
                    color: #cc0000;
                }
                h3 {
                    color: #003366;
                    margin-top: 2em;
                }
                canvas {
                    max-width: 300px;
                    margin: 1em auto;
                    display: block;
                }
                ul {
                    background: #fff;
                    padding: 1em;
                    border-radius: 5px;
                    list-style: square;
                }
                li {
                    padding: 0.2em 0;
                }
                .legend {
                    display: flex;
                    justify-content: center;
                    gap: 1em;
                    margin-bottom: 1em;
                }
                .legend span {
                    display: inline-block;
                    width: 15px;
                    height: 15px;
                    margin-right: 5px;
                    vertical-align: middle;
                }
                .red { background: #cc0000; }
                .green { background: #7dc243; }
            </style>
        </head>
        <body>
            <h2>Resumen IPs en red {{ subnet }}</h2>
            <div class="legend">
              <div><span class="red"></span>Usadas</div>
              <div><span class="green"></span>Disponibles</div>
            </div>
            <canvas id="pieChart"></canvas>
            <script>
              new Chart(document.getElementById('pieChart').getContext('2d'), {
                type: 'pie',
                data: {
                  labels: ['Usadas', 'Disponibles'],
                  datasets: [{ data: [{{ pie_data }}], backgroundColor: ['#cc0000', '#7dc243'] }]
                }
              });
            </script>

            <h3>Namespaces sin NetworkPolicy</h3>
            <ul>{% for ns in np %}<li>{{ ns }}</li>{% endfor %}</ul>

            <h3>Namespaces con CrashLoopBackOff</h3>
            <ul>{% for ns in crashloop %}<li>{{ ns }}</li>{% endfor %}</ul>

            <h3>Namespaces sin ResourceQuota</h3>
            <ul>{% for ns in quota %}<li>{{ ns }}</li>{% endfor %}</ul>
        </body>
        </html>
    """, subnet=subnet_cidr, pie_data=pie_data, np=cache_resultados["np"], crashloop=cache_resultados["crashloop"], quota=cache_resultados["quota"])

@app.route("/metrics")
def metrics():
    try:
        result = subprocess.run(["oc", "get", "egressip", "-A", "-o", "jsonpath={range .items[*]}{.status.assignedIP}\n{end}"], capture_output=True, text=True)
        egressips_usadas = len(result.stdout.strip().splitlines())
        nodos = len(subprocess.check_output(["oc", "get", "nodes", "-o", "name"], text=True).strip().splitlines())
        total = len(list(ipaddress.ip_network(subnet_cidr).hosts()))
        used = egressips_usadas + nodos
        egressip_total.set(total)
        egresip_uso.set(used)
    except Exception as e:
        print("[ERROR] cálculo IPs:", e)

    try:
        ns_list = subprocess.check_output(["oc", "get", "ns", "-o", "jsonpath={range .items[*]}{.metadata.name}\n{end}"], text=True).splitlines()
        sin_np = []
        for ns in ns_list:
            output = subprocess.run(["oc", "get", "networkpolicy", "-n", ns], capture_output=True, text=True)
            if "No resources found" in output.stdout:
                sin_np.append(ns)
        cache_resultados["np"] = sin_np
        ns_sin_np_total.set(len(sin_np))
        for ns in sin_np:
            ns_sin_np_label.labels(namespace=ns).set(1)
    except Exception as e:
        print("[ERROR] networkpolicy:", e)

    try:
        crashloop = []
        for ns in ns_list:
            pods = subprocess.check_output(["oc", "get", "pods", "-n", ns, "--no-headers"], text=True).splitlines()
            for pod_line in pods:
                if "CrashLoopBackOff" in pod_line:
                    crashloop.append(ns)
                    break
        cache_resultados["crashloop"] = crashloop
        ns_crashloop_total.set(len(crashloop))
        for ns in crashloop:
            ns_crashloop_label.labels(namespace=ns).set(1)
    except Exception as e:
        print("[ERROR] crashloop:", e)

    try:
        sin_quota = []
        for ns in ns_list:
            output = subprocess.run(["oc", "get", "resourcequota", "-n", ns], capture_output=True, text=True)
            if "No resources found" in output.stdout:
                sin_quota.append(ns)
        cache_resultados["quota"] = sin_quota
        ns_quota_total.set(len(sin_quota))
        for ns in sin_quota:
            ns_quota_label.labels(namespace=ns).set(1)
    except Exception as e:
        print("[ERROR] quotas:", e)

    return Response(generate_latest(registry), mimetype="text/plain")

if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=debug_mode, use_reloader=debug_mode)