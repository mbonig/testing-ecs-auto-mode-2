# Runtime requirements

What the deployment environment must supply for the DSQL connectivity check to
report `ok`. Until all of it is in place, `/api/` still returns HTTP 200 and the
static page still loads — the check simply reports `not_configured` or
`connection_failed`.

## Environment variables on the task

| Variable | Required | Default | Notes |
| --- | --- | --- | --- |
| `DSQL_CLUSTER_ENDPOINT` | yes | — | `<cluster-id>.dsql.<region>.on.aws` |
| `DSQL_CLUSTER_USER` | yes | — | Database role. `admin` switches the app to the admin token API; prefer a least-privilege role linked to the task role |
| `DSQL_DATABASE` | no | `postgres` | |
| `DSQL_PORT` | no | `5432` | |
| `DSQL_SSLROOTCERT` | no | system CA bundle | Only needed if the image's trust store does not chain to the Amazon root |
| `AWS_REGION` / `AWS_DEFAULT_REGION` | no | parsed from the endpoint | botocore itself reads `AWS_DEFAULT_REGION`, not `AWS_REGION`; the app reads either and falls back to the region embedded in the endpoint |

## IAM

The task role needs, on the target cluster:

- `dsql:DbConnect` for a non-admin database role, **or**
- `dsql:DbConnectAdmin` when `DSQL_CLUSTER_USER` is `admin`.

This is in addition to the existing `ssm:GetParameter` grant on
`/cdk-bootstrap/hnb659fds/version`.

For a non-admin role, the database role must also be linked to the IAM role
inside the cluster — see "Using database roles with IAM roles" in the Aurora
DSQL user guide. Granting the IAM action alone is not sufficient.

## Network

The task needs egress to the cluster endpoint on **TCP 5432**. There is no
interface endpoint for the DSQL data plane, so a task in an isolated subnet with
no NAT gateway cannot reach it. That is a change from the current posture: the
ECS work deliberately placed tasks in isolated subnets because SSM was reachable
through an interface endpoint and nothing else left the VPC.

Adding DSQL therefore requires one of:

- a NAT gateway (or egress-only path) from the task subnets, or
- moving the tasks to subnets that already have egress, or
- a PrivateLink path to DSQL if one is available in the target region.

Whichever is chosen, it is an infrastructure decision, not an application one.

## Where this has to be wired up

Not in this repository as it currently stands. On `main` (`068ec12`) there is no
`infra/` content — the ECS/CDK commit `d7396ac`, which adds the projen CDK app,
the GitHub Actions pipeline, and the task role, is **not on this branch**, and
the working tree's `infra/` holds only `node_modules`.

So the environment variables, the IAM grant, and the egress path have to be
applied wherever that stack actually lives. The application side is complete and
inert until they are.
