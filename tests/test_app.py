import pytest
from unittest import mock
from app import create_app

@pytest.fixture
def client():
    # Creamos la app con un archivo de configuración alternativo
    app = create_app("./config_test.json")
    app.config['TESTING'] = True
    return app.test_client()

@mock.patch("subprocess.check_output")
@mock.patch("subprocess.run")
def test_metrics(mock_run, mock_check_output, client):
    # Simulamos salidas de los comandos `oc`
    mock_check_output.side_effect = [
        b"192.168.1.100\n192.168.1.101",  # egressip
        b"node1\nnode2",                  # nodes
        b"default\nkube-system\nns1",     # namespaces
        b"",                              # networkpolicy (none)
        b"pod1 0/1 CrashLoopBackOff",     # pod con crash
        b""                               # resourcequota (none)
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
