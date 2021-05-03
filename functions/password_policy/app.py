# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import os
import logging
import boto3
from crhelper import CfnResource
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
helper = CfnResource()


@helper.create
@helper.update
def create(event, context):
    """Updates the IAM password policy."""
    logger.info("Create Event")
    iam_client = get_client(event)
    logger.info(json.dumps(event))
    event = format_properties(event)
    logger.info(json.dumps(event))
    resource_properties = event['ResourceProperties']
    iam_client.update_account_password_policy(
        MinimumPasswordLength=resource_properties['MinimumPasswordLength'],
        RequireSymbols=resource_properties['RequireSymbols'],
        RequireNumbers=resource_properties['RequireNumbers'],
        RequireUppercaseCharacters=resource_properties['RequireUppercaseCharacters'],
        RequireLowercaseCharacters=resource_properties['RequireLowercaseCharacters'],
        AllowUsersToChangePassword=resource_properties['AllowUsersToChangePassword'],
        MaxPasswordAge=resource_properties['MaxPasswordAge'],
        PasswordReusePrevention=resource_properties['PasswordReusePrevention'],
        HardExpiry=resource_properties['HardExpiry']
    )


@helper.delete
def delete(event, context):
    """Deletes custom the IAM password policy."""
    logger.info("Delete Event")
    try:
        iam_client = get_client(event)
        response = iam_client.delete_account_password_policy()
        logger.info(response)
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchEntity':
            logger.warn("The entity does not exist")
        else:
            raise Exception("Unexpected error: %s" % e)


def get_client(event):
    """Creates and returns an IAM client."""
    stack_id = event['StackId']
    stack_account = stack_id.split(":")[4]
    stack_region = stack_id.split(":")[3]
    aws_partition = os.getenv("AWS_PARTITION")
    target_role = os.getenv("TARGET_ROLE")
    role_arn = "arn:{}:iam::{}:role/{}".format(aws_partition, stack_account, target_role)
    session = CustomSession(role_arn=role_arn, role_session_name="assumed-role-session").session
    iam_client = session.client('iam', stack_region)
    return iam_client


def format_properties(event):
    """Formats the user input for a password policy."""
    event_properties = event["ResourceProperties"]
    allowed_properties_bool = [
              "RequireSymbols",
              "RequireNumbers",
              "RequireUppercaseCharacters",
              "RequireLowercaseCharacters",
              "AllowUsersToChangePassword",
              "HardExpiry"
            ]
    for i in allowed_properties_bool:
        if event_properties[i] == "true":
            event_properties[i] = True
        elif event_properties[i] == "false":
            event_properties[i] = False
        else:
            raise Exception("Resource property values not supported. Values must be boolean.")

    allowed_properties_int = [
      "MinimumPasswordLength",
      "MaxPasswordAge",
      "PasswordReusePrevention"
    ]
    for j in allowed_properties_int:
        event_properties[j] = int(event['ResourceProperties'][j])

    return event


def lambda_handler(event, context):
    """AWS Lambda function handler."""
    cf_event = json.loads(event['Records'][0]['Sns']['Message'])
    helper(cf_event, context)


class CustomSession:
    def __init__(self, role_arn, role_session_name):
        self.role_arn = role_arn
        self.role_session_name = role_session_name
        self.session = self.create_session()

    def create_session(self):
        """Creates boto3 session."""
        target_account = self.role_arn.split(":")[4]
        sts_client = boto3.client('sts')
        caller_identity = sts_client.get_caller_identity()
        if caller_identity['Account'] != target_account:
            response = sts_client.assume_role(RoleArn=self.role_arn, RoleSessionName=self.role_session_name)
            return boto3.Session(
                aws_access_key_id=response['Credentials']['AccessKeyId'],
                aws_secret_access_key=response['Credentials']['SecretAccessKey'],
                aws_session_token=response['Credentials']['SessionToken']
            )
        else:
            return boto3.Session()
