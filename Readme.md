# Despliegue de cluster-custom-metrics en OpenShift

**Docker Hub:**
[![Docker Hub - Tag](https://img.shields.io/docker/v/jorgeandrada/cluster-custom-metrics?label=version&sort=semver)](https://hub.docker.com/r/jorgeandrada/cluster-custom-metrics)
[![Docker Hub - Pulls](https://img.shields.io/docker/pulls/jorgeandrada/cluster-custom-metrics)](https://hub.docker.com/r/jorgeandrada/cluster-custom-metrics)

**Quay.io:**
[![Quay - Version](https://img.shields.io/badge/quay.io-latest-red)](https://quay.io/repository/jandradap/cluster-custom-metrics)
[![Quay - Repositorio](https://img.shields.io/badge/Quay.io-cluster--custom--metrics-blue?logo=redhat)](https://quay.io/repository/jandradap/cluster-custom-metrics)

**Info:**
[![codecov](https://codecov.io/github/jandradap/cluster-custom-metrics/branch/develop/graph/badge.svg?token=3XICVV1DMD)](https://codecov.io/github/jandradap/cluster-custom-metrics)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/jandradap/cluster-custom-metrics)

Este documento describe los pasos para desplegar la aplicación `cluster-custom-metrics` en un clúster OpenShift, así como las variables de entorno requeridas, permisos necesarios y ejemplo de dashboard en Grafana.

---

## 1. Requisitos

- OpenShift 4.x
- Permisos para crear `ServiceAccount`, `ClusterRoleBinding`, `Deployment`, `Service` y `ServiceMonitor`
- Acceso a Prometheus y Grafana

---

## 2. Crear ServiceAccount con permisos

```bash
oc create serviceaccount metrics-reader -n cluster-monitoring
oc adm policy add-cluster-role-to-user cluster-reader -z metrics-reader -n cluster-monitoring
```

---

## 3. Desplegar la aplicación

1. **Crear el `Deployment` y recursos asociados:**

```bash
oc apply -f deployment-cluster-custom-metrics.yaml
```

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
