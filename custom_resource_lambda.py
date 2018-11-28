"""
This lambda implements the custom resource handler for creating an SSH key
and storing in in SSM parameter store.

e.g.

SSHKeyCR:
    Type: Custom::CreateSSHKey
    Version: "1.0"
    Properties:
      ServiceToken: !Ref FunctionArn
      KeyName: MyKey

An SSH key called MyKey will be created.

"""

from json import dumps
import sys
import traceback
import urllib.request

import boto3


def log_exception():
    "Log a stack trace"
    exc_type, exc_value, exc_traceback = sys.exc_info()
    print(repr(traceback.format_exception(
        exc_type,
        exc_value,
        exc_traceback)))


def send_response(event, context, response):
    "Send a response to CloudFormation to handle the custom resource lifecycle"

    responseBody = { 
        'Status': response,
        'Reason': 'See details in CloudWatch Log Stream: ' + \
            context.log_stream_name,
        'PhysicalResourceId': context.log_stream_name,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
    }

    print('RESPONSE BODY: \n' + dumps(responseBody))

    data = dumps(responseBody).encode('utf-8')
    
    req = urllib.request.Request(
        event['ResponseURL'], 
        data,
        headers={'Content-Length': len(data), 'Content-Type': ''})
    req.get_method = lambda: 'PUT'

    try:
        with urllib.request.urlopen(req) as response:
            print(f'response.status: {response.status}, ' + 
                  f'response.reason: {response.reason}')
            print('response from cfn: ' + response.read().decode('utf-8'))
    except urllib.error.URLError:
        log_exception()
        raise Exception('Received non-200 response while sending ' +\
            'response to AWS CloudFormation')

    return True


def custom_resource_handler(event, context):
    '''
    This function creates a PEM key, commits it as a key pair in EC2, 
    and stores it, encrypted, in SSM.

    To retrieve the key with currect RSA format, you must use the command line: 

    aws ssm get-parameter \
        --name <KEYNAME> \
        --with-decryption \
        --region <REGION> \
        --output text

    Copy the values from (and including) -----BEGIN RSA PRIVATE KEY----- to 
    -----END RSA PRIVATE KEY----- into a file.

    To use it, change the permissions to 600
    Ensure to bundle the necessary packages into the zip stored in S3

    '''
    print("Event JSON: \n" + dumps(event))

    # session = boto3.session.Session()
    # region = session.region_name

    # Original
    # pem_key_name = os.environ['KEY_NAME']
    
    pem_key_name = event['ResourceProperties']['KeyName']

    response = 'FAILED'
    
    ec2 = boto3.client('ec2')

    if event['RequestType'] == 'Create':
        try:
            print("Creating key name %s" % str(pem_key_name))

            key = ec2.create_key_pair(KeyName=pem_key_name)
            key_material = key['KeyMaterial']
            ssm_client = boto3.client('ssm')
            param = ssm_client.put_parameter(
                Name=pem_key_name, 
                Value=key_material, 
                Type='SecureString')

            print(param)
            print(f'The parameter {pem_key_name} has been created.')

            response = 'SUCCESS'

        except Exception as e:
            print(f'There was an error {e} creating and committing ' +\
                f'key {pem_key_name} to the parameter store')
            log_exception()
            response = 'FAILED'

        send_response(event, context, response)

        return

    if event['RequestType'] == 'Update':
        # Do nothing and send a success immediately
        send_response(event, context, response)
        return

    if event['RequestType'] == 'Delete':
        #Delete the entry in SSM Parameter store and EC2
        try:
            print(f"Deleting key name {pem_key_name}")

            ssm_client = boto3.client('ssm')
            rm_param = ssm_client.delete_parameter(Name=pem_key_name)

            print(rm_param)

            _ = ec2.delete_key_pair(KeyName=pem_key_name)

            response = 'SUCCESS'
        except Exception as e:
            print(f"There was an error {e} deleting the key {pem_key_name} ' +\
            from SSM Parameter store or EC2")
            log_exception()
            response = 'FAILED'
         
        send_response(event, context, response)


def lambda_handler(event, context):
    "Lambda handler for the custom resource"

    try:
        return custom_resource_handler(event, context)
    except Exception:
        log_exception()
        raise
