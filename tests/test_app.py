import os
import pytest
from unittest import mock
from app.app import create_app
from app import app as app_module
from prometheus_client import generate_latest
import time

@pytest.fixture
def client():
    os.environ["CONFIG_PATH"] = "tests/config_test.json"
    app = create_app("tests/config_test.json")
    app.config['TESTING'] = True
    return app.test_client()

@pytest.fixture
def client_disabled():
    os.environ["CONFIG_PATH"] = "tests/config_disabled.json"
    app = create_app("tests/config_disabled.json")
    app.config['TESTING'] = True
    return app.test_client()

@mock.patch("app.app.get_cert_expiry")
@mock.patch("subprocess.check_output")
def test_metrics(mock_check_output, mock_cert, client):
    pvc_json = b'{"items":[{"metadata":{"namespace":"ns1","name":"pvc1"},"status":{"phase":"Pending"}},{"metadata":{"namespace":"ns1","name":"pvc2"},"status":{"phase":"Lost"}}]}'
    pv_json = b'{"items":[{"metadata":{"name":"pv1"},"status":{"phase":"Available"}}]}'
    deploy_json = b'{"items":[{"metadata":{"namespace":"ns1","name":"app1"},"spec":{"replicas":1,"template":{"spec":{"serviceAccountName":"sa1","containers":[{"name":"c1"}]}}}},{"metadata":{"namespace":"ns1","name":"app2"},"spec":{"replicas":2,"template":{"spec":{"serviceAccountName":"sa2","containers":[{"name":"c2","resources":{"requests":{"cpu":"10m"},"limits":{"cpu":"20m"}}}]}}}}]}'
    sts_json = b'{"items":[]}'
    scc_json = b'{"items":[{"metadata":{"name":"privileged"},"users":["system:serviceaccount:ns1:sa1"]}]}'
    route_json = b'{"items":[{"metadata":{"namespace":"ns1","name":"r1"},"spec":{"host":"r1.example.com","tls":{"certificate":"dummy"}}}]}'
    mock_cert.return_value = int(time.time()) + 60*86400
    mock_check_output.side_effect = [
        b"192.168.1.100\n192.168.1.101",  # egressip
        b"node1\nnode2",                  # nodes
        b"ns1",                            # namespaces
        b"",                               # networkpolicy
        b"",                               # resourcequota
        pvc_json,
        pv_json,
        deploy_json,
        sts_json,
        scc_json,
        route_json
    ]

    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"ip_pool_total" in response.data
    assert b'egressips_used' in response.data
    assert b'nodesips_used' in response.data
    assert b'pv_unbound_total' in response.data
    assert b'pvc_pending_total' in response.data
    assert b'workloads_single_replica_total' in response.data
    assert b'workloads_no_resources_total' in response.data
    assert b'workloads_no_antiaffinity_total' in response.data
    assert b'privileged_serviceaccount_total' in response.data
    assert b'routes_cert_expiring_total' in response.data

def test_home(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "EgressIP Metrics" in body
    assert "PV Unbound" in body

def test_metrics_format(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    lines = response.data.decode("utf-8").splitlines()
    for line in lines:
        if not line.startswith("#"):
            assert " " in line and line.strip().split(" ")[-1].replace(".", "").isdigit()

@mock.patch("app.app.get_cert_expiry")
@mock.patch("subprocess.check_output")
def test_metrics_namespace_filtering(mock_check_output, mock_cert, client):
    pvc_json = b'{"items":[]}'
    pv_json = b'{"items":[]}'
    empty_json = b'{"items":[]}'
    route_json = b'{"items":[]}'
    mock_cert.return_value = int(time.time()) + 60*86400
    mock_check_output.side_effect = [
        b"192.168.1.10",         # egressip
        b"node1",                # nodes
        b"default\nns-user\nopenshift-monitoring",  # namespaces
        b"",                     # networkpolicy ns-user
        b"",                     # resourcequota ns-user
        pvc_json,                # pvcs
        pv_json,                 # pvs
        empty_json,              # deploy
        empty_json,              # sts
        b'{"items":[]}',        # scc
        route_json
    ]

    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "namespace_without_networkpolicy" in body
    assert "openshift-monitoring" not in body  # filtered namespace


@mock.patch("subprocess.check_output")
def test_feature_toggle(mock_check_output, client_disabled):
    mock_check_output.side_effect = [
        b"192.168.1.10",  # egressip
        b"node1",        # nodes
    ]

    response = client_disabled.get("/metrics")
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    # Disabled metrics should report zero
    assert "pv_unbound_total 0.0" in body
    assert "pvc_pending_total 0.0" in body
    assert "workloads_single_replica_total 0.0" in body
    assert "workloads_no_antiaffinity_total 0.0" in body
    assert "privileged_serviceaccount_total 0.0" in body
    assert "routes_cert_expiring_total 0.0" in body
    # IP metrics still available
    assert "ip_pool_total" in body

def test_config_file_loaded(client):
    config_path = os.environ.get("CONFIG_PATH")
    assert config_path is not None
    assert os.path.exists(config_path)

def test_health_endpoint(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.data.decode("utf-8") == "OK"


@mock.patch("app.app.Timer")
@mock.patch("app.app.get_cert_expiry")
@mock.patch("subprocess.check_output")
def test_workloads_processed_once(mock_check_output, mock_cert, mock_timer, client):
    deploy_json = '{"items":[{"metadata":{"namespace":"ns1","name":"app1"},"spec":{"replicas":1,"template":{"spec":{"serviceAccountName":"sa1","containers":[{"name":"c1"}]}}}}]}'
    sts_json = '{"items":[]}'
    pvc_json = '{"items":[]}'
    pv_json = '{"items":[]}'
    scc_json = '{"items":[{"metadata":{"name":"privileged"},"users":["system:serviceaccount:ns1:sa1"]}]}'
    rb_json = '{"items":[{"metadata":{"namespace":"ns1"},"roleRef":{"name":"system:openshift:scc:privileged"},"subjects":[{"kind":"ServiceAccount","name":"sa1"}]}]}'
    crb_json = '{"items":[]}'
    route_json = '{"items":[]}'

    mock_cert.return_value = int(time.time()) + 60 * 86400
    mock_check_output.side_effect = [
        '192.168.1.100\n192.168.1.101',  # egressip
        'InternalIP:node1\nInternalIP:node2',  # nodes
        'ns1',  # namespaces
        '',  # networkpolicy
        '',  # resourcequota
        pvc_json,
        pv_json,
        deploy_json,
        sts_json,
        scc_json,
        rb_json,
        crb_json,
        route_json,
    ]

    app_module.update_metrics()
    metrics = generate_latest(app_module.registry).decode("utf-8")
    expected_label = 'workload_single_replica{app="app1",kind="deployment",namespace="ns1"} 1.0'
    assert "workloads_single_replica_total 1.0" in metrics
    assert metrics.count(expected_label) == 1
    expected_aff_label = 'workload_no_antiaffinity{app="app1",kind="deployment",namespace="ns1"} 1.0'
    assert "workloads_no_antiaffinity_total 1.0" in metrics
    assert metrics.count(expected_aff_label) == 1
    expected_priv = 'privileged_serviceaccount{app="app1",namespace="ns1",scc="privileged",serviceaccount="sa1"} 1.0'
    assert expected_priv in metrics
