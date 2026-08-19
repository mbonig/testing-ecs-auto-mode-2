## Why

The `/api/` endpoint currently proves only that the task can reach AWS Systems Manager. It says nothing about whether the container can reach its database, so a broken or misconfigured Aurora DSQL connection stays invisible until a real query fails. Adding a trivial `SELECT 1` alongside the existing SSM lookup turns the endpoint into a single place that confirms both dependencies are reachable from the running task.

## What Changes

- `/api/` performs an Aurora DSQL connectivity check in addition to the existing SSM `GetParameter` call, and reports both results in one JSON body.
- The DSQL check opens a connection using an IAM authentication token, runs `SELECT 1`, and closes the connection.
- Connection details are read from the runtime environment: `DSQL_CLUSTER_ENDPOINT`, `DSQL_CLUSTER_USER`, optional `DSQL_DATABASE` (default `postgres`), optional `DSQL_PORT` (default `5432`), and the region from `AWS_REGION`/`AWS_DEFAULT_REGION` (falling back to the region embedded in the endpoint).
- The endpoint keeps returning HTTP 200 when the database is unreachable or unconfigured; the failure is reported inside the JSON body, matching the existing `unavailable` behavior for SSM.
- `index.html` displays the DSQL check result next to the CDK bootstrap version.
- `psycopg[binary]` is added to `requirements.txt`, and `boto3` is upgraded — the pinned `1.34.162` predates Aurora DSQL and has no `dsql` client at all.
- The runtime IAM role needs `dsql:DbConnect` (or `dsql:DbConnectAdmin`) on the target cluster, and the task needs network reachability to the DSQL endpoint on port 5432.

## Capabilities

### New Capabilities
- `dsql-connectivity-check`: Reading DSQL connection settings from the environment, authenticating with a short-lived IAM token over TLS, running a `SELECT 1` probe, and reporting the outcome through `/api/` without failing the request.

### Modified Capabilities

<!-- None. The `/api/` endpoint's existing SSM behavior is unchanged; the new field is additive.
     `web-ssm-status-api` has no baseline spec in openspec/specs/ yet (its change is still unarchived),
     so this change adds a separate capability rather than a delta against a spec that does not exist. -->

## Impact

- **Code**: `app.py` (new DSQL probe + expanded `/api/` response), `index.html` (render the new field), `requirements.txt` (add `psycopg[binary]`).
- **APIs**: `/api/` JSON response gains a `dsql` object. The existing `cdk_bootstrap_version` key is unchanged, so current consumers keep working.
- **Dependencies**: adds `psycopg[binary]` and upgrades `boto3` from `1.34.162` to a version that ships the `dsql` client (bundled libpq, no system package needed in the `python:3.12-slim` image). Relies on the image's `ca-certificates` bundle for TLS verification of the DSQL endpoint.
- **Runtime/infra**: requires the DSQL environment variables to be injected into the task, an IAM policy granting `dsql:DbConnect` on the cluster, and egress to the cluster endpoint on TCP 5432. Note that `infra/` is not present on `main` at the time of writing (the ECS/CDK commit is not on this branch), so wiring those in is outside this change.
- **Not affected**: the Dockerfile needs no change, and the static page continues to be served from the same process and port.
