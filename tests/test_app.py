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
    mock_check_output.side_effect = [
        b"192.168.1.100\n192.168.1.101",  # egressip
        b"node1\nnode2",                  # nodes
        b"default\nkube-system\nns1",     # namespaces
        b"",                              # networkpolicy
        b"pod1 0/1 CrashLoopBackOff",     # pods
        b""                               # resourcequota
    ]

    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"ip_pool_total" in response.data
    assert b'egressips_used' in response.data
    assert b'nodesips_used' in response.data

def test_home(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "EgressIP Metrics" in response.data.decode("utf-8")

def test_metrics_format(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    lines = response.data.decode("utf-8").splitlines()
    for line in lines:
        if not line.startswith("#"):
            assert " " in line and line.strip().split(" ")[-1].replace(".", "").isdigit()

@mock.patch("subprocess.check_output")
def test_metrics_namespace_filtering(mock_check_output, client):
    mock_check_output.side_effect = [
        b"192.168.1.10",         # egressip
        b"node1",                # nodes
        b"default\nns-user\nopenshift-monitoring",  # namespaces
        b"", b"", b""            # remaining subprocess calls
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
