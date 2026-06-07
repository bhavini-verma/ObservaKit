# Discovered Bugs & Issues

## 1. Docker Desktop Daemon Offline

### Description

The automated smoke test requires the Docker daemon to build and start the test environment. If Docker Desktop is not running, Docker commands cannot connect to the Docker API.

### Steps to Reproduce

1. Ensure Docker Desktop is not running.
2. Open PowerShell or Terminal.
3. Run:

```bash
pytest -v -m smoke tests/smoke
```

### Expected Behavior

The smoke test should start the Docker Compose services and execute successfully.

### Actual Behavior

The test fails with an error indicating that the Docker daemon is unavailable.

### Severity

Low (Environment setup issue)

### Remediation

Start Docker Desktop before running the smoke test.

---

## 2. /status Endpoint Returns HTTP 500

### Description

During smoke test execution, the `/status` endpoint returned an HTTP 500 Internal Server Error instead of the expected HTTP 200 response.

### Steps to Reproduce

1. Start the application and required services.
2. Run:

```bash
pytest -v -m smoke tests/smoke
```

3. Observe the failure in `test_status_endpoint`.

### Expected Behavior

The `/status` endpoint should return HTTP 200 and provide application status information.

### Actual Behavior

The endpoint returns HTTP 500 Internal Server Error. Smoke test successfully identified a failure in the /status endpoint. CI shows /status returning HTTP 500 instead of HTTP 200. Additional backend investigation is required to determine the root cause.

### Severity

Medium

### Evidence

```text
FAILED tests/smoke/test_smoke.py::test_status_endpoint
assert 500 == 200
```
