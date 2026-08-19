## 1. Dependencies

- [x] 1.1 Add `psycopg[binary]==3.3.4` to `requirements.txt` (exact pin, matching the existing entries) and upgrade `boto3` from `1.34.162` to `1.43.74` — the old pin has no `dsql` client. `flask` unchanged
- [x] 1.2 Rebuild the image and confirm `psycopg` imports inside the container without adding any apt packages to the Dockerfile

## 2. Configuration loading

- [x] 2.1 Add a helper in `app.py` that reads `DSQL_CLUSTER_ENDPOINT`, `DSQL_CLUSTER_USER`, `DSQL_DATABASE` (default `postgres`), `DSQL_PORT` (default `5432`), and `DSQL_SSLROOTCERT` from the environment
- [x] 2.2 Resolve the region from `AWS_REGION`, falling back to parsing it out of the `<cluster-id>.dsql.<region>.on.aws` endpoint
- [x] 2.3 Return a "not configured" signal when `DSQL_CLUSTER_ENDPOINT` or `DSQL_CLUSTER_USER` is missing, so the app still starts and serves both routes with no DSQL variables set
- [x] 2.4 Read the environment on each call rather than at import time, so configuration is not frozen into the module at startup

## 3. DSQL connectivity probe

- [x] 3.1 Add a `check_dsql()` function that returns a dict shaped `{"ok": bool, "result": int}` on success and `{"ok": False, "error": "<identifier>"}` on failure
- [x] 3.2 Generate a fresh IAM auth token per call with a `boto3` `dsql` client — `generate_db_connect_admin_auth_token` when the user is `admin`, `generate_db_connect_auth_token` otherwise — and map any failure to `auth_token_failed`
- [x] 3.3 Connect with `psycopg.connect` using the token as `password`, `sslmode="verify-full"`, `sslrootcert` only when `DSQL_SSLROOTCERT` is set, and an explicit `connect_timeout` of 5 seconds
- [x] 3.4 Set `sslnegotiation="direct"` when `psycopg.pq.version() >= 170000`, matching the AWS sample's guard
- [x] 3.5 Execute `SELECT 1`, treat the check as successful only when the returned value is `1`, and map a post-connect query error to `query_failed`
- [x] 3.6 Map connection failures to `connection_failed` and missing configuration to `not_configured`
- [x] 3.7 Close the connection on every path, including both failure paths — use a context manager or `try/finally`
- [x] 3.8 Log full exception detail via the existing module logger, and keep the response body limited to the four sentinel identifiers with no driver text, host, user, or token

## 4. Verify TLS against the base image trust store

- [ ] 4.1 From a `python:3.12-slim` container, connect to a real DSQL cluster with `sslmode=verify-full` and no `sslrootcert` to confirm the image's `ca-certificates` bundle trusts the Amazon root
- [ ] 4.2 If verification fails, document the required bundle and confirm `DSQL_SSLROOTCERT` overrides it — do not weaken `sslmode` to make the check pass

## 5. API endpoint

- [x] 5.1 Call `check_dsql()` from the `/api/` handler and add its result under a `dsql` key in the JSON response
- [x] 5.2 Confirm `cdk_bootstrap_version` keeps its existing name, value, and `unavailable` fallback so current consumers are unaffected
- [x] 5.3 Confirm the handler returns HTTP 200 for every DSQL failure mode, and that an SSM failure and a DSQL failure are independent of each other

## 6. Status page

- [x] 6.1 Add a DSQL row to `index.html` next to the CDK bootstrap version line
- [x] 6.2 Render success from `data.dsql.ok`, and render the `data.dsql.error` identifier on failure
- [x] 6.3 Keep the existing `catch` fallback working when `/api/` itself is unreachable

## 7. Verification

- [x] 7.1 Run the container with no DSQL variables set: `/` loads, `/api/` returns 200, and `dsql.error` is `not_configured`
- [x] 7.2 Run with a bogus `DSQL_CLUSTER_ENDPOINT`: `/api/` returns 200 with `connection_failed` within the 5-second timeout, not a hang
- [ ] 7.3 Run against a real cluster with `dsql:DbConnect` granted: `/api/` returns 200 with `dsql.ok` true and `result` `1`
- [ ] 7.4 Run against a real cluster with the IAM permission removed: `/api/` returns 200 with `connection_failed`, and the full reason appears in the container logs but not in the response body
- [x] 7.5 Load `/` in a browser for the success and failure cases and confirm the page renders both — failure case exercised for real; success case exercised with `check_dsql` stubbed, pending 7.3
- [ ] 7.6 Measure `/api/` latency against a real cluster and confirm it stays well inside the ALB health-check timeout, since `/api/` is the health-check target

## 8. Handoff notes

- [x] 8.1 Record in the change what the runtime must supply: the `DSQL_*` environment variables, `dsql:DbConnect` (or `dsql:DbConnectAdmin`) on the cluster for the task role, and egress to the cluster endpoint on TCP 5432 — written to `runtime-requirements.md`
- [x] 8.2 Note that `infra/` is not on `main` (the ECS/CDK commit `d7396ac` is not on this branch), so the above must be wired up wherever that stack actually lives — covered in `runtime-requirements.md`
