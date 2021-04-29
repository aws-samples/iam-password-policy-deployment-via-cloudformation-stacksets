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
    logger.info("Create Event")
    iam_client = get_client(event)
    logger.info(json.dumps(event))
    event = format_properties(event)
    logger.info(json.dumps(event))
    iam_client.update_account_password_policy(
        MinimumPasswordLength=event['ResourceProperties']['MinimumPasswordLength'],
        RequireSymbols=event['ResourceProperties']['RequireSymbols'],
        RequireNumbers=event['ResourceProperties']['RequireNumbers'],
        RequireUppercaseCharacters=event['ResourceProperties']['RequireUppercaseCharacters'],
        RequireLowercaseCharacters=event['ResourceProperties']['RequireLowercaseCharacters'],
        AllowUsersToChangePassword=event['ResourceProperties']['AllowUsersToChangePassword'],
        MaxPasswordAge=event['ResourceProperties']['MaxPasswordAge'],
        PasswordReusePrevention=event['ResourceProperties']['PasswordReusePrevention'],
        HardExpiry=event['ResourceProperties']['HardExpiry']
    )
@helper.delete
def delete(event, context):
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
    stack_id = event['StackId']
    stack_account = stack_id.split(":")[4]
    stack_region = stack_id.split(":")[3]
    aws_partition = os.getenv("AWS_PARTITION")
    target_role = os.getenv("TARGET_ROLE")
    role_arn = "arn:{}:iam::{}:role/{}".format(aws_partition,stack_account,target_role)
    session = CustomSession(role_arn=role_arn, role_session_name="assumed-role-session").session
    iam_client = session.client('iam',stack_region)
    return iam_client
def format_properties(event):
    for i in ["RequireSymbols","RequireNumbers","RequireUppercaseCharacters","RequireLowercaseCharacters","AllowUsersToChangePassword","HardExpiry"]:
        if event['ResourceProperties'][i] == "true":
            event['ResourceProperties'][i] = True
        elif event['ResourceProperties'][i] == "false":
            event['ResourceProperties'][i] = False
        else:
            raise Exception("Resource property values not supported. Values must be boolean.")
    for j in ["MinimumPasswordLength","MaxPasswordAge","PasswordReusePrevention"]:
        event['ResourceProperties'][j] = int(event['ResourceProperties'][j])
    return event
def lambda_handler(event, context):
    cf_event = json.loads(event['Records'][0]['Sns']['Message'])
    helper(cf_event, context)
class CustomSession:
  def __init__(self, role_arn, role_session_name):
      self.role_arn = role_arn
      self.role_session_name = role_session_name
      self.session = self.create_session()
  def create_session(self):
      target_account = self.role_arn.split(":")[4]
      sts_client = boto3.client('sts')
      caller_identity = sts_client.get_caller_identity()
      if caller_identity['Account'] != target_account:
          response = sts_client.assume_role(RoleArn=self.role_arn,RoleSessionName=self.role_session_name)
          return boto3.Session(
              aws_access_key_id=response['Credentials']['AccessKeyId'],
              aws_secret_access_key=response['Credentials']['SecretAccessKey'],
              aws_session_token=response['Credentials']['SessionToken']
          )
      else:
          return boto3.Session()