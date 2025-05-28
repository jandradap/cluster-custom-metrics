# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## \[Unreleased]

### Added

* Initial changelog file.
* Refactored README with project description, images, and usage.
* CONTRIBUTING and TODO markdown files.

### Planned

* Unit tests and GitHub Actions CI.
* Docker image automation.
* Additional metric types.

---

## \[0.1.0] - 2024-05-01

### Added

* Base implementation of Python metric exporter.
* Metrics: `ips_vlan_total`, `ips_egress`, `ips_nodes`, `namespaces without quotas or policies`.
* OpenShift-compatible manifests: ConfigMap, Deployment, Service, ServiceMonitor.

### Changed

* Initial test and deployment in OpenShift.

### Known Issues

* Missing retry logic in API calls.
* No authentication for `/metrics` endpoint.

---

*End of Changelog*
