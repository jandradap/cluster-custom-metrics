import os
import time
from unittest import mock

import app.app as app_module
from prometheus_client import generate_latest


@mock.patch("app.app.Timer")
@mock.patch("app.app.get_cert_expiry")
@mock.patch("subprocess.check_output")
def test_update_metrics(mock_check_output, mock_cert, mock_timer):
    pvc_json = b'{"items":[{"metadata":{"namespace":"ns1","name":"pvc1"},"status":{"phase":"Pending"}},{"metadata":{"namespace":"ns1","name":"pvc2"},"status":{"phase":"Lost"}}]}'
    pv_json = b'{"items":[{"metadata":{"name":"pv1"},"status":{"phase":"Available"}}]}'
    deploy_json = b'{"items":[{"metadata":{"namespace":"ns1","name":"app1"},"spec":{"replicas":1,"template":{"spec":{"serviceAccountName":"sa1","containers":[{"name":"c1"}]}}}},{"metadata":{"namespace":"ns1","name":"app2"},"spec":{"replicas":2,"template":{"spec":{"serviceAccountName":"sa2","containers":[{"name":"c2","resources":{"requests":{"cpu":"10m"},"limits":{"cpu":"20m"}}}]}}}}]}'
    sts_json = b'{"items":[]}'
    scc_json = b'{"items":[{"metadata":{"name":"privileged"},"users":["system:serviceaccount:ns1:sa1"]}]}'
    rb_json = b'{"items":[{"metadata":{"namespace":"ns1"},"roleRef":{"name":"system:openshift:scc:privileged"},"subjects":[{"kind":"ServiceAccount","name":"sa2"}]}]}'
    crb_json = b'{"items":[]}'
    route_json = b'{"items":[{"metadata":{"namespace":"ns1","name":"r1"},"spec":{"host":"r1.example.com","tls":{"certificate":"dummy"}}}]}'

    mock_timer.return_value.start.return_value = None
    mock_cert.return_value = int(time.time()) + 60 * 86400
    mock_check_output.side_effect = [
        "192.168.1.100\n192.168.1.101",
        "node1\nnode2",
        "ns1",
        "",
        "",
        pvc_json.decode(),
        pv_json.decode(),
        deploy_json.decode(),
        sts_json.decode(),
        scc_json.decode(),
        rb_json.decode(),
        crb_json.decode(),
        route_json.decode(),
    ]

    os.environ["CONFIG_PATH"] = "tests/config_test.json"
    app_module.create_app("tests/config_test.json")
    app_module.update_metrics()

    assert app_module.ip_pool_total._value.get() == 254
    assert app_module.pv_unbound_total._value.get() == 1
    assert app_module.pvc_pending_total._value.get() == 1
    assert app_module.workload_single_replica_total._value.get() == 1
    assert app_module.workload_no_resources_total._value.get() == 1
    assert app_module.workload_no_antiaffinity_total._value.get() == 2
    assert app_module.priv_sa_total._value.get() == 2
    assert app_module.routes_cert_expiring_total._value.get() == 0

    metrics = app_module.generate_latest(app_module.registry).decode("utf-8")
    assert 'serviceaccount="sa2"' in metrics
    assert 'privileged_serviceaccount{app="app1",namespace="ns1",scc="privileged",serviceaccount="sa1"} 1.0' in metrics
    assert 'privileged_serviceaccount{app="app2",namespace="ns1",scc="privileged",serviceaccount="sa2"} 1.0' in metrics
