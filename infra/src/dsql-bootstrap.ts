// HAND-WRITTEN addition to ecs-truly-auto-mode's generated platform stack — not
// part of the skill's standard templates. Requested to avoid the manual
// CREATE ROLE / AWS IAM GRANT step the skill otherwise documents as required after
// the platform stack deploys. See .ecs-auto-mode/manifest.yaml,
// plan.resources[].id === 'dsql-role-grant'.
//
// Needs Docker at `cdk synth` / `cdk deploy` time: the handler bundles
// psycopg[binary], which ships platform-specific wheels and cannot be installed by
// plain asset copying the way the rest of this stack's assets are.

import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as cr from 'aws-cdk-lib/custom-resources';

export interface DsqlRoleGrantProps {
  /** `arn:aws:dsql:<region>:<account>:cluster/<id>` */
  readonly clusterResourceArn: string;
  /**
   * The cluster's *public* endpoint, always — regardless of the task's own egress
   * mode. This bootstrap Lambda runs outside the VPC (default Lambda networking, no
   * `vpc` prop set below), so it always has internet access and never needs the
   * data-plane VPC endpoint the task itself may use.
   */
  readonly publicEndpoint: string;
  readonly region: string;
  /** The database role to create and link. Never 'admin' — the caller skips that case. */
  readonly dbUser: string;
  readonly taskRoleArn: string;
}

/**
 * Links a DSQL database role to the task role's IAM principal, so the task can
 * authenticate as `dbUser` with a SigV4 token as soon as the platform stack finishes
 * deploying.
 *
 * A CloudFormation custom resource that connects to the cluster as `admin` (via a
 * freshly generated IAM auth token) and runs the two statements the skill's own
 * resource catalog documents as a manual step:
 *
 *   CREATE ROLE <dbUser> WITH LOGIN;         -- guarded: CREATE ROLE is not idempotent
 *   AWS IAM GRANT <dbUser> TO '<task-role-arn>';
 *
 * Never reverses either statement on stack deletion or update — an orphaned role
 * costs nothing, matching the cluster's own retained, deletion-protected posture.
 * Deliberately independent of the ECS task's own Fargate architecture: this Lambda
 * is ARM64, and the bundling `platform` below is pinned to match it explicitly —
 * without that, Docker bundles for whatever machine happens to run `cdk deploy`,
 * and a wheel built for the wrong architecture fails at runtime, not at synth time.
 */
export class DsqlRoleGrant extends Construct {
  constructor(scope: Construct, id: string, props: DsqlRoleGrantProps) {
    super(scope, id);

    const architecture = lambda.Architecture.ARM_64;

    const handler = new lambda.Function(this, 'Handler', {
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture,
      handler: 'index.handler',
      timeout: cdk.Duration.seconds(30),
      description: `One-time DSQL role bootstrap for ${props.dbUser}`,
      code: lambda.Code.fromAsset(path.join(__dirname, '..', 'lambda', 'dsql-role-grant'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          platform: architecture.dockerPlatform,
          command: [
            'bash',
            '-c',
            'pip install -r requirements.txt -t /asset-output && cp -au . /asset-output',
          ],
        },
      }),
    });

    // Scoped to this one cluster. Full admin DB access, but only this function ever
    // uses it, and only to run the two statements above.
    handler.addToRolePolicy(
      new iam.PolicyStatement({
        sid: 'DsqlAdminConnect',
        actions: ['dsql:DbConnectAdmin'],
        resources: [props.clusterResourceArn],
      }),
    );

    const provider = new cr.Provider(this, 'Provider', { onEventHandler: handler });

    new cdk.CustomResource(this, 'Resource', {
      serviceToken: provider.serviceToken,
      properties: {
        ClusterEndpoint: props.publicEndpoint,
        Region: props.region,
        DbUser: props.dbUser,
        TaskRoleArn: props.taskRoleArn,
      },
    });
  }
}
