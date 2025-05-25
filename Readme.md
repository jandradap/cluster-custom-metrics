# Despliegue de cluster-custom-metrics en OpenShift

Este documento describe los pasos para desplegar la aplicación `cluster-custom-metrics` en un clúster OpenShift, así como las variables de entorno requeridas, permisos necesarios y ejemplo de dashboard en Grafana.

---

## 1. Requisitos

- OpenShift 4.x
- Permisos para crear `ServiceAccount`, `ClusterRoleBinding`, `Deployment`, `Service` y `ServiceMonitor`
- Acceso a Prometheus y Grafana

---

## 2. Crear ServiceAccount con permisos

```bash
oc create serviceaccount metrics-reader -n openshift-monitoring
oc adm policy add-cluster-role-to-user cluster-reader -z metrics-reader -n openshift-monitoring
```

---

## 3. Desplegar la aplicación

1. **Crear el `Deployment` y recursos asociados:**

```bash
oc apply -f deployment-cluster-custom-metrics.yaml
```

2. **(Opcional)** Si estás en entorno desconectado, asegúrate de haber construido la imagen previamente:

```bash
podman build -t cluster-custom-metrics:latest .
podman tag cluster-custom-metrics:latest yourregistry/cluster-custom-metrics:latest
podman push yourregistry/cluster-custom-metrics:latest
```

---

## 4. Variables de entorno utilizadas

- `PORT`: Puerto de la aplicación (por defecto: 8080)
- `SUBNET`: Rango de red CIDR para calcular IPs disponibles (por defecto: `192.168.1.0/24`)

---

## 5. Métricas disponibles en Prometheus

```text
egressip_total
egressip_uso
namespaces_sin_networkpolicy_total
namespace_sin_networkpolicy{namespace="..."}
namespaces_con_pods_crashloop_total
namespace_crashloop{namespace="..."}
namespaces_sin_resourcequota_total
namespace_sin_quota{namespace="..."}
```

---

## 6. Dashboard de Grafana

```json
{
  "title": "Cluster Custom Metrics",
  "panels": [
    {
      "type": "stat",
      "title": "IPs en uso",
      "targets": [ { "expr": "egressip_uso" } ],
      "datasource": "Prometheus",
      "fieldConfig": { "defaults": { "unit": "short" } }
    },
    {
      "type": "stat",
      "title": "IPs disponibles",
      "targets": [ { "expr": "egressip_total - egressip_uso" } ],
      "datasource": "Prometheus"
    },
    {
      "type": "table",
      "title": "Namespaces sin NetworkPolicy",
      "targets": [ { "expr": "namespace_sin_networkpolicy" } ],
      "datasource": "Prometheus"
    },
    {
      "type": "table",
      "title": "Namespaces con CrashLoopBackOff",
      "targets": [ { "expr": "namespace_crashloop" } ],
      "datasource": "Prometheus"
    },
    {
      "type": "table",
      "title": "Namespaces sin ResourceQuota",
      "targets": [ { "expr": "namespace_sin_quota" } ],
      "datasource": "Prometheus"
    }
  ],
  "schemaVersion": 34,
  "version": 1
}
```

Importa este JSON directamente en Grafana para visualizar el estado del clúster.

---

## 7. Notas adicionales

- El contenedor incluye el binario `oc` y usa la `ServiceAccount` montada automáticamente por OpenShift.
- No se necesita acceso externo a Internet si la imagen se construye previamente y Chart.js se copia localmente.