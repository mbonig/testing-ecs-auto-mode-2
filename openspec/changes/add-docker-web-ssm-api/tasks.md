## 1. Backend API

- [x] 1.1 Create `requirements.txt` with `flask` and `boto3` pinned to compatible versions.
- [x] 1.2 Create `app.py` implementing a Flask app with a module-level `boto3` SSM client.
- [x] 1.3 Implement the `/api/` route: call `ssm_client.get_parameter(Name="/cdk-bootstrap/hnb659fds/version")`, return `{"cdk_bootstrap_version": <value>}` as JSON on success.
- [x] 1.4 Handle `ParameterNotFound` (and other `ClientError`s) in the `/api/` route by returning `{"cdk_bootstrap_version": "unavailable"}` with HTTP 200, logging the exception server-side.
- [x] 1.5 Configure Flask to serve `index.html` as a static file at `/`.
- [x] 1.6 Set the app to listen on `0.0.0.0` on a fixed port (e.g., 8080).

## 2. Frontend

- [x] 2.1 Create `index.html` with minimal markup and inline JS that calls `/api/` via `fetch` on page load.
- [x] 2.2 Display the returned `cdk_bootstrap_version` value (or `unavailable`) on the page.

## 3. Containerization

- [x] 3.1 Create `Dockerfile` based on `python:3.12-slim`.
- [x] 3.2 Copy `requirements.txt` and run `pip install --no-cache-dir -r requirements.txt`.
- [x] 3.3 Copy `app.py` and `index.html` into the image.
- [x] 3.4 `EXPOSE` the app's port and set `CMD` to run `app.py`.

## 4. Verification

- [x] 4.1 Build the image locally with `docker build`.
- [ ] 4.2 Run the container locally with valid AWS credentials/role and confirm `/api/` returns the real SSM parameter value. (Blocked: no AWS credentials available in this environment — needs manual verification against a real account.)
- [x] 4.3 Run the container without access to the parameter (or against a region/account where it doesn't exist) and confirm `/api/` returns `"unavailable"` with HTTP 200.
- [x] 4.4 Confirm `/` serves `index.html` and the page displays the value returned by `/api/`.
