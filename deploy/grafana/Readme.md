# Grafana

OBtain datasource token:

```bash
oc create sa grafana-reader -n openshift-monitoring

oc adm policy add-cluster-role-to-user cluster-monitoring-view -z grafana-reader -n openshift-monitoring

cat <<EOF | oc apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: grafana-reader-token
  annotations:
    kubernetes.io/service-account.name: grafana-reader
type: kubernetes.io/service-account-token
EOF

oc get secret grafana-reader-token -n openshift-monitoring -o jsonpath='{.data.token}' | base64 -d; echo
```
