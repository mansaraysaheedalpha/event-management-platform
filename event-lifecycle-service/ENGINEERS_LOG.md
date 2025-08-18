# Event Lifecycle Service: Engineering Log & Debugging History

This document tracks all major errors encountered during the setup of the testing suite and CI/CD pipeline for the `event-lifecycle-service`.

---
### Error 1: Widespread API Test Failures (`AttributeError` & `ResponseValidationError`)

* **Exact Error Message:** `AttributeError: 'dict' object has no attribute 'org_id'` and `fastapi.exceptions.ResponseValidationError`
* **What it Means:** The API tests were failing because our mocks for the CRUD layer were returning simple Python dictionaries (`{}`). The application code expected real objects that allow attribute access (e.g., `event.org_id`), and FastAPI's response validation rejected the incomplete dictionaries.
* **Exact Solution:** We created a central `tests/conftest.py` file to provide a `test_client` fixture with all dependencies correctly mocked. We also updated all API test mocks to return either instances of Pydantic schemas or `MagicMock` objects instead of simple dictionaries.
* **Resolution Attempts:** 3

---
### Error 2: CI/CD Failure - `NoBrokersAvailable` (Kafka)

* **Exact Error Message:** `ImportError while loading conftest... kafka.errors.NoBrokersAvailable: NoBrokersAvailable`
* **What it Means:** The CI pipeline was failing before tests could even run. When `pytest` imported the application code, the `kafka_producer.py` file immediately tried to connect to a live Kafka server, which wasn't available in the CI environment.
* **Exact Solution:** We added `zookeeper` and `kafka` to the `services` block in the `.github/workflows/event-lifecycle-ci.yml` file. This ensures that temporary Kafka and Zookeeper containers are running and available before the tests start.
* **Resolution Attempts:** 2

---
### Error 3: CI/CD Failure - `pytest: command not found`

* **Exact Error Message:** `pytest: command not found`
* **What it Means:** The GitHub Actions runner had successfully installed the project's dependencies (including `pytest`), but the shell in the "Run Tests" step could not find the `pytest` executable in its path.
* **Exact Solution:** We updated the `run` command in the CI workflow file from `pytest` to `python -m pytest`. This is a more robust method that uses the configured Python interpreter to locate and run the `pytest` module.
* **Resolution Attempts:** 2

---
### Error 4: CI/CD Failure - `pnpm` vs `npm` Mismatch

* **Exact Error Message:** `ERR_PNPM_NO_LOCKFILE Cannot install with "frozen-lockfile"...`
* **What it Means:** This was a series of errors caused by me providing CI configurations that assumed the wrong package manager (`pnpm` instead of `npm` for the NestJS service, or vice-versa) or incorrect paths for a monorepo.
* **Exact Solution:** We created a separate, dedicated CI workflow file for each service in the monorepo (`.github/workflows/`). Each file was then meticulously configured for the specific service's package manager (`npm` or `pnpm`) and directory structure (`working-directory`).
* **Resolution Attempts:** 4