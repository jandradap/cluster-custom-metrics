import pytest
from unittest.mock import patch
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()

@patch("subprocess.check_output")
@patch("subprocess.run")
def test_metrics(mock_run, mock_check_output, client):
    mock_check_output.side_effect = [
        b"node1\nnode2",  # oc get nodes
        b"default\nkube-system\nns1",  # oc get ns
        b"",  # oc get networkpolicy
        b"pod1 0/1 CrashLoopBackOff",  # oc get pods
        b""   # oc get resourcequota
    ]
    mock_run.return_value.stdout = "192.168.1.100\n192.168.1.101\n"

    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"egressip_total" in response.data
    assert b"namespace_crashloop" in response.data

def test_home(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"M\xc3\xa9tricas EgressIP" in response.data
