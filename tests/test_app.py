import os
import pytest
from unittest import mock
from app.app import create_app

@pytest.fixture
def client():
    os.environ["CONFIG_PATH"] = "tests/config_test.json"
    app = create_app("tests/config_test.json")
    app.config['TESTING'] = True
    return app.test_client()

@mock.patch("subprocess.check_output")
def test_metrics(mock_check_output, client):
    pvc_json = b'{"items":[{"metadata":{"namespace":"ns1","name":"pvc1"},"status":{"phase":"Pending"}},{"metadata":{"namespace":"ns1","name":"pvc2"},"status":{"phase":"Lost"}}]}'
    pv_json = b'{"items":[{"metadata":{"name":"pv1"},"status":{"phase":"Available"}}]}'
    deploy_json = b'{"items":[{"metadata":{"namespace":"ns1","name":"app1"},"spec":{"replicas":1,"template":{"spec":{"serviceAccountName":"sa1","containers":[{"name":"c1"}]}}}},{"metadata":{"namespace":"ns1","name":"app2"},"spec":{"replicas":2,"template":{"spec":{"serviceAccountName":"sa2","containers":[{"name":"c2","resources":{"requests":{"cpu":"10m"},"limits":{"cpu":"20m"}}}]}}}}]}'
    sts_json = b'{"items":[]}'
    scc_json = b'{"items":[{"metadata":{"name":"privileged"},"users":["system:serviceaccount:ns1:sa1"]}]}'
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
        scc_json
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
    assert b'privileged_serviceaccount_total' in response.data

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

@mock.patch("subprocess.check_output")
def test_metrics_namespace_filtering(mock_check_output, client):
    pvc_json = b'{"items":[]}'
    pv_json = b'{"items":[]}'
    empty_json = b'{"items":[]}'
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
        b'{"items":[]}'         # scc
    ]

    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "namespace_without_networkpolicy" in body
    assert "openshift-monitoring" not in body  # filtered namespace

def test_config_file_loaded(client):
    config_path = os.environ.get("CONFIG_PATH")
    assert config_path is not None
    assert os.path.exists(config_path)
