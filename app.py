import logging
import os
import re

import boto3
import psycopg
from botocore.exceptions import BotoCoreError, ClientError
from flask import Flask, jsonify, send_from_directory
from psycopg import pq

SSM_PARAMETER_NAME = "/cdk-bootstrap/hnb659fds/version"

DSQL_CONNECT_TIMEOUT_SECONDS = 5
DSQL_ENDPOINT_REGION = re.compile(r"\.dsql\.([a-z0-9-]+)\.on\.aws\.?$")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=".", static_url_path="")
ssm_client = boto3.client("ssm")

# Cached per region. The client is reused; the auth token it produces is not.
dsql_clients = {}


def dsql_config():
    """Read the DSQL connection settings from the environment.

    Called on every check so the settings are never frozen into the module at
    import time. Returns None when the cluster is not configured, which lets the
    app start and serve both routes with no DSQL variables set.
    """
    endpoint = os.environ.get("DSQL_CLUSTER_ENDPOINT")
    user = os.environ.get("DSQL_CLUSTER_USER")
    if not endpoint or not user:
        return None

    # botocore itself honors AWS_DEFAULT_REGION rather than AWS_REGION, so read
    # both before falling back to the region embedded in the endpoint.
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if not region:
        match = DSQL_ENDPOINT_REGION.search(endpoint)
        region = match.group(1) if match else None
    if not region:
        logger.warning(
            "No region is set and none could be parsed from the DSQL endpoint"
        )
        return None

    return {
        "endpoint": endpoint,
        "user": user,
        "region": region,
        "dbname": os.environ.get("DSQL_DATABASE") or "postgres",
        "port": os.environ.get("DSQL_PORT") or "5432",
        "sslrootcert": os.environ.get("DSQL_SSLROOTCERT") or None,
    }


def dsql_auth_token(config):
    """Generate a fresh IAM auth token. Tokens are short lived, so one is
    generated per check rather than cached."""
    client = dsql_clients.get(config["region"])
    if client is None:
        client = boto3.client("dsql", region_name=config["region"])
        dsql_clients[config["region"]] = client

    if config["user"] == "admin":
        return client.generate_db_connect_admin_auth_token(
            config["endpoint"], config["region"]
        )
    return client.generate_db_connect_auth_token(config["endpoint"], config["region"])


def check_dsql():
    """Run a SELECT 1 probe against the configured DSQL cluster.

    Never raises. Failures are logged in full and reported as a short identifier
    so the response body carries no driver text, host, user, or token.
    """
    config = dsql_config()
    if config is None:
        logger.info("DSQL is not configured; skipping the connectivity check")
        return {"ok": False, "error": "not_configured"}

    try:
        password = dsql_auth_token(config)
    except (BotoCoreError, ClientError):
        logger.exception("Could not generate a DSQL authentication token")
        return {"ok": False, "error": "auth_token_failed"}

    conn_params = {
        "dbname": config["dbname"],
        "user": config["user"],
        "host": config["endpoint"],
        "port": config["port"],
        "password": password,
        "sslmode": "verify-full",
        "connect_timeout": DSQL_CONNECT_TIMEOUT_SECONDS,
        "autocommit": True,
    }
    if config["sslrootcert"]:
        conn_params["sslrootcert"] = config["sslrootcert"]
    # Use the more efficient connection method if the bundled libpq supports it.
    if pq.version() >= 170000:
        conn_params["sslnegotiation"] = "direct"

    try:
        conn = psycopg.connect(**conn_params)
    except Exception:
        logger.exception("Could not connect to the DSQL cluster")
        return {"ok": False, "error": "connection_failed"}

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            row = cur.fetchone()
    except Exception:
        logger.exception("DSQL connectivity query failed")
        return {"ok": False, "error": "query_failed"}
    finally:
        conn.close()

    if not row or row[0] != 1:
        logger.error("DSQL connectivity query returned an unexpected result")
        return {"ok": False, "error": "query_failed"}

    return {"ok": True, "result": row[0]}


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/")
def api():
    try:
        response = ssm_client.get_parameter(Name=SSM_PARAMETER_NAME)
        version = response["Parameter"]["Value"]
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ParameterNotFound":
            logger.info("SSM parameter %s not found", SSM_PARAMETER_NAME)
        else:
            logger.exception("Error retrieving SSM parameter %s", SSM_PARAMETER_NAME)
        version = "unavailable"

    return jsonify({"cdk_bootstrap_version": version, "dsql": check_dsql()})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
