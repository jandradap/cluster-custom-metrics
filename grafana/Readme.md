# Enabling User Workload Monitoring in OpenShift

OpenShift supports a separate monitoring stack for user-defined workloads. This guide explains how to enable and configure User Workload Monitoring (UWM) to allow Prometheus scraping of custom metrics via ServiceMonitor.

---

## ✅ Step 1: Enable UWM via ConfigMap

Edit the `cluster-monitoring-config` ConfigMap in the `openshift-monitoring` namespace:

```bash
oc edit configmap cluster-monitoring-config -n openshift-monitoring
```

Modify it to include:

```yaml
data:
  config.yaml: |
    enableUserWorkload: true
```

Save and exit. This will trigger the redeployment of monitoring components.

---

## 🔁 Step 2: Verify Monitoring Components

Ensure the UWM components are deployed:

```bash
oc get pods -n openshift-user-workload-monitoring
```

You should see pods such as:

* `prometheus-user-workload-...`
* `thanos-ruler-user-workload-...`

---

## 🛠 Step 3: Create a Namespace for Your Metrics Exporter

```bash
oc create ns cluster-monitoring
```

Ensure all components (Deployment, Service, ServiceMonitor) are in this namespace.

---

## 📡 Step 4: Deploy ServiceMonitor

Here is an example ServiceMonitor definition:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: cluster-custom-metrics
  namespace: cluster-monitoring
spec:
  selector:
    matchLabels:
      app: cluster-custom-metrics
  endpoints:
  - port: http
    path: /metrics
    interval: 30s
```

Ensure your Service resource has a matching label selector and exposes the `/metrics` endpoint on the correct port.

---

## 🔍 Step 5: Validate Scraping

### Web Console:

* Navigate to **Observe → Targets** in the OpenShift Console.
* Look under the **User Workload** tab.

### CLI with Port Forwarding:

```bash
oc -n openshift-user-workload-monitoring port-forward svc/prometheus-user-workload 9090
```

Then open: [http://localhost:9090](http://localhost:9090)

Query your custom metric to confirm it appears.

---

## 📦 Note on RBAC

If using a custom ServiceAccount, ensure it has the appropriate roles to expose metrics.

---

## 📊 Grafana Integration

To visualize user workload metrics in Grafana, you'll need to configure Prometheus as a data source with an access token. Here's how to generate the token:

### 🔑 Obtain Datasource Token

```bash
oc create sa grafana-reader -n openshift-monitoring

oc adm policy add-cluster-role-to-user cluster-monitoring-view -z grafana-reader -n openshift-monitoring

cat <<EOF | oc apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: grafana-reader-token
  namespace: openshift-monitoring
  annotations:
    kubernetes.io/service-account.name: grafana-reader
type: kubernetes.io/service-account-token
EOF

oc get secret grafana-reader-token -n openshift-monitoring -o jsonpath='{.data.token}' | base64 -d; echo
```

Use the resulting token in your Grafana Prometheus datasource configuration.

---

## ✅ Summary

* User Workload Monitoring is disabled by default.
* It must be enabled via `cluster-monitoring-config`.
* Deploy your Service and ServiceMonitor in the same namespace.
* Use the web console or Prometheus UI to verify metrics are being scraped.
* Generate Grafana access token to integrate with Prometheus.

---

For more information, see the official Red Hat docs: [Monitoring Your Own Services](https://docs.openshift.com/container-platform/latest/monitoring/enabling-monitoring-for-user-defined-projects.html)
