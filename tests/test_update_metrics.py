import os
import time
import datetime
import re
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
    route_json = b'{"items":[{"metadata":{"namespace":"ns1","name":"r1"},"spec":{"host":"r1.example.com","tls":{"certificate":"dummy","key":"dummy"}}}]}'

    mock_timer.return_value.start.return_value = None
    mock_cert.return_value = 2000000000
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

    metrics = generate_latest(app_module.registry).decode("utf-8")
    assert 'serviceaccount="sa2"' in metrics
    assert 'privileged_serviceaccount{app="app1",namespace="ns1",scc="privileged",serviceaccount="sa1"} 1.0' in metrics
    assert 'privileged_serviceaccount{app="app2",namespace="ns1",scc="privileged",serviceaccount="sa2"} 1.0' in metrics
    expiry_date = datetime.datetime.fromtimestamp(2000000000).strftime("%Y-%m-%d")
    pattern = (
        r"route_cert_expiry_timestamp{"
        r"(?=.*namespace=\"ns1\")"
        r"(?=.*route=\"r1\")"
        r"(?=.*host=\"r1\.example\.com\")"
        rf"(?=.*expiry_date=\"{expiry_date}\")"
        r"[^}]*}"
        r" ([0-9]+\.?[0-9]*)"
    )
    match = re.search(pattern, metrics)
    assert match and float(match.group(1)) > 0


@mock.patch("app.app.Timer")
@mock.patch("app.app.get_cert_expiry")
@mock.patch("subprocess.check_output")
def test_networkpolicy_metric_resets(mock_check_output, mock_cert, mock_timer):
    pvc_json = b'{"items":[]}'
    pv_json = b'{"items":[]}'
    empty_json = b'{"items":[]}'

    mock_timer.return_value.start.return_value = None
    mock_cert.return_value = 0

    first_side_effect = [
        "",  # egressip
        "",  # nodes
        "ns1",  # namespaces
        "",  # networkpolicy
        "",  # resourcequota
        pvc_json.decode(),
        pv_json.decode(),
        empty_json.decode(),  # deploy
        empty_json.decode(),  # sts
        empty_json.decode(),  # scc
        empty_json.decode(),  # rb
        empty_json.decode(),  # crb
        empty_json.decode(),  # route
    ]

    second_side_effect = [
        "",  # egressip
        "",  # nodes
        "ns1",  # namespaces
        "np1",  # networkpolicy exists
        "",  # resourcequota
        pvc_json.decode(),
        pv_json.decode(),
        empty_json.decode(),
        empty_json.decode(),
        empty_json.decode(),
        empty_json.decode(),
        empty_json.decode(),
        empty_json.decode(),
    ]

    mock_check_output.side_effect = first_side_effect
    os.environ["CONFIG_PATH"] = "tests/config_test.json"
    app_module.create_app("tests/config_test.json")
    app_module.update_metrics()
    metrics = generate_latest(app_module.registry).decode("utf-8")
    assert 'namespace_without_networkpolicy{namespace="ns1"} 1.0' in metrics

    mock_check_output.side_effect = second_side_effect
    app_module.update_metrics()
    metrics = generate_latest(app_module.registry).decode("utf-8")
    assert 'namespace_without_networkpolicy{namespace="ns1"}' not in metrics
    assert app_module.ns_without_np_total._value.get() == 0
@mock.patch("app.app.Timer")

@mock.patch("app.app.get_cert_expiry")
@mock.patch("subprocess.check_output")
def test_route_cert_expiry_removal(mock_check_output, mock_cert, mock_timer):
    route_json_first = b'{"items":[{"metadata":{"namespace":"ns1","name":"r1"},"spec":{"host":"r1.example.com","tls":{"certificate":"dummy","key":"dummy"}}}]}'
    route_json_empty = b'{"items":[]}'
    mock_timer.return_value.start.return_value = None
    mock_cert.return_value = int(time.time()) + 10 * 86400
    mock_check_output.side_effect = [
        "192.168.1.10",
        "node1",
        route_json_first.decode(),
    ]
    os.environ["CONFIG_PATH"] = "tests/config_disabled.json"
    app_module.create_app("tests/config_disabled.json")
    app_module.enabled_features = {"route_cert": True}
    app_module.update_metrics()
    metrics = generate_latest(app_module.registry).decode("utf-8")
    assert "routes_cert_expiring_total 1.0" in metrics
    assert 'namespace="ns1"' in metrics and 'route="r1"' in metrics
    mock_check_output.side_effect = [
        "",
        "",
        route_json_empty.decode(),
    ]
    app_module.update_metrics()
    metrics = generate_latest(app_module.registry).decode("utf-8")
    assert "routes_cert_expiring_total 0.0" in metrics
    assert 'route_cert_expiry_timestamp{namespace="ns1",route="r1"' not in metrics

@mock.patch("app.app.Timer")
@mock.patch("app.app.get_cert_expiry")
@mock.patch("subprocess.check_output")
def test_priv_sa_scc_filter(mock_check_output, mock_cert, mock_timer):
    pvc_json = b'{"items":[]}'
    pv_json = b'{"items":[]}'
    deploy_json = b'{"items":[{"metadata":{"namespace":"ns1","name":"app1"},"spec":{"replicas":1,"template":{"spec":{"serviceAccountName":"sa1","containers":[{"name":"c1"}]}}}}]}'
    sts_json = b'{"items":[]}'
    scc_json = b'{"items":[{"metadata":{"name":"privileged"},"users":[]} ]}'
    rb_json = b'{"items":[{"metadata":{"namespace":"ns1"},"roleRef":{"name":"system:openshift:scc:privileged"},"subjects":[{"kind":"ServiceAccount","name":"sa1"}]}]}'
    crb_json = b'{"items":[]}'
    route_json = b'{"items":[]}'
    mock_timer.return_value.start.return_value = None
    mock_cert.return_value = int(time.time()) + 60 * 86400
    mock_check_output.side_effect = [
        "192.168.1.10",
        "node1",
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
    app_module.scc_types = ["anyuid"]
    app_module.update_metrics()
    metrics = generate_latest(app_module.registry).decode("utf-8")
    assert "privileged_serviceaccount_total 0.0" in metrics
