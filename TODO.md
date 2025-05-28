# TODO List for Cluster Custom Metrics

This document tracks known improvements, enhancements, and tasks for the project.

## 📌 Improvements

* [ ] Refactor metric collection scripts to use modular structure
* [ ] Improve error handling and logging clarity
* [ ] Add retry logic for OpenShift API calls
* [ ] Parameterize namespace and service settings via environment variables
* [ ] Validate configuration files with schema checks (YAML/JSON)

## 🧪 Testing

* [ ] Add unit tests for metric logic using pytest
* [ ] Create integration tests with a mock Prometheus environment
* [ ] Setup GitHub Actions for CI with Python linting and testing

## 📚 Documentation

* [x] Clean up and reformat `README.md`
* [x] Add architecture and deployment diagrams
* [x] Create `CONTRIBUTING.md`
* [x] Add `CHANGELOG.md`
* [x] Add `CODE_OF_CONDUCT.md`

## 🧩 Features

* [ ] Add support for additional custom metrics (e.g. unused PVCs, non-labeled namespaces)
* [ ] Enable metrics toggle via ConfigMap entries

## 🛠️ Maintenance

* [x] Automate Docker image build and push
* [x] Add image tagging strategy and documentation

---

Feel free to add to this list by submitting a Pull Request!
