# HAND-WRITTEN addition to ecs-truly-auto-mode's generated platform stack — not part
# of the skill's standard templates. See ../../src/dsql-bootstrap.ts and
# .ecs-auto-mode/manifest.yaml, plan.resources[].id === "dsql-role-grant".
#
# CloudFormation custom resource handler (wrapped by the CDK Provider framework in
# dsql-bootstrap.ts, which sends the response — this function only returns a dict).
#
# Connects to the DSQL cluster as `admin` using a freshly generated IAM auth token,
# and links the configured database role to the task role's IAM principal:
#
#   CREATE ROLE <DbUser> WITH LOGIN;          -- guarded: CREATE ROLE is not idempotent
#   AWS IAM GRANT <DbUser> TO '<TaskRoleArn>';
#
# Never runs anything on Delete — the role and its grant are left in place, matching
# the cluster's own retained, deletion-protected posture. An orphaned role costs
# nothing, and reverting it here could cut off a still-running task.

import os

import boto3
import psycopg

# Bundled alongside this file: Amazon Root CA 1-4 plus the Starfield Services Root
# G2 cross-sign, fetched from https://www.amazontrust.com/repository/ — the actual
# chain DSQL's certificate presents (openssl s_client -showcerts against the
# cluster's own endpoint: leaf -> "Amazon RSA 2048 M01" -> "Amazon Root CA 1"),
# confirmed by `openssl verify -CAfile amazon-trust-roots.pem` returning "OK".
#
# Two things this is deliberately NOT:
#   - "system": failed with "SSL error: certificate verify failed" — the Lambda
#     Python 3.12 runtime's ambient trust store doesn't chain to this root, at
#     least not in a way this statically-linked libpq (from psycopg[binary])
#     resolves.
#   - the RDS global bundle (truststore.pki.rds.amazonaws.com): also failed
#     verification — DSQL's certificate chains to the generic Amazon Trust
#     Services roots, not RDS's own CA hierarchy, despite the "Aurora" branding.
ROOT_CERT = os.path.join(os.path.dirname(__file__), "amazon-trust-roots.pem")


def handler(event, context):
    props = event["ResourceProperties"]
    endpoint = props["ClusterEndpoint"]
    region = props["Region"]
    db_user = props["DbUser"]
    task_role_arn = props["TaskRoleArn"]
    physical_id = f"dsql-role-grant-{db_user}"

    if event["RequestType"] == "Delete":
        return {"PhysicalResourceId": physical_id}

    client = boto3.client("dsql", region_name=region)
    token = client.generate_db_connect_admin_auth_token(endpoint, region)

    conn = psycopg.connect(
        host=endpoint,
        port=5432,
        dbname="postgres",
        user="admin",
        password=token,
        sslmode="verify-full",
        # libpq's default sslrootcert (~/.postgresql/root.crt) doesn't exist in the
        # Lambda sandbox — see ROOT_CERT's comment above for why this is a bundled
        # file rather than "system".
        sslrootcert=ROOT_CERT,
        connect_timeout=10,
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (db_user,))
            role_exists = cur.fetchone() is not None
            if not role_exists:
                # CREATE ROLE takes no bind parameter for an identifier. db_user is a
                # deploy-time value from the manifest/CDK config, never external input.
                cur.execute(f'CREATE ROLE "{db_user}" WITH LOGIN')

            try:
                cur.execute(f"AWS IAM GRANT \"{db_user}\" TO '{task_role_arn}'")
            except psycopg.Error as e:
                # An Update event with an unchanged task role ARN re-runs this
                # statement; treat "already granted" as success rather than failing
                # the custom resource on a no-op re-run.
                message = str(e).lower()
                if "already" not in message and "duplicate" not in message:
                    raise
    finally:
        conn.close()

    return {"PhysicalResourceId": physical_id}
