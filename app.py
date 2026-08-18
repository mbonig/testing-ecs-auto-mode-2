import logging

import boto3
from botocore.exceptions import ClientError
from flask import Flask, jsonify, send_from_directory

SSM_PARAMETER_NAME = "/cdk-bootstrap/hnb659fds/version"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=".", static_url_path="")
ssm_client = boto3.client("ssm")


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

    return jsonify({"cdk_bootstrap_version": version})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
