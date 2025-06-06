import datetime
from unittest import mock
import pytest

import app.app as app_module


def test_exclude_ns_patterns(monkeypatch):
    monkeypatch.setattr(app_module, 'exclude_ns_patterns', ['kube-*', 'openshift*'])
    monkeypatch.setattr(app_module, 'feature_ns_exclusions', {'np': ['custom*']})

    assert app_module.exclude_ns('kube-system')
    assert app_module.exclude_ns('openshift-monitoring')
    assert app_module.exclude_ns('custom-ns', feature='np')
    assert not app_module.exclude_ns('default')
    assert not app_module.exclude_ns('other', feature='np')


def test_get_cert_expiry(monkeypatch):
    sample_not_after = 'May  1 12:00:00 2030 GMT'

    def fake_decode(path):
        return {'notAfter': sample_not_after}

    monkeypatch.setattr(app_module.ssl._ssl, '_test_decode_cert', fake_decode)

    ts = app_module.get_cert_expiry('dummy')
    expected_ts = int(datetime.datetime.strptime(sample_not_after, '%b %d %H:%M:%S %Y %Z').timestamp())
    assert ts == expected_ts


def test_get_cert_expiry_failure(monkeypatch):
    def fake_decode(path):
        raise ValueError('bad cert')

    monkeypatch.setattr(app_module.ssl._ssl, '_test_decode_cert', fake_decode)
    ts = app_module.get_cert_expiry('bad')
    assert ts == 0


def test_format_datetime_valid():
    ts = 1700000000
    result = app_module._format_datetime(ts)
    assert result == '2023-11-14'


def test_format_datetime_invalid():
    assert app_module._format_datetime('bad') == ''
