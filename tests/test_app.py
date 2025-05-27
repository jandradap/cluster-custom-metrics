
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
        b"default\nkube-system\nns1",    # namespaces
        b"",                               # networkpolicy
        b"pod1 0/1 CrashLoopBackOff",      # pods
        b""                                # resourcequota
    ]

    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"egressip_total" in response.data

def test_home(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Métricas EgressIP" in response.data.decode("utf-8")
