"""
This is a dual-purpose lambda function that handles creation of an SSH key 
from within a CloudFormation template.

It is used as a macro that transforms a template with an EC2 resource. If the 
resource has a KeyName property with a value that starts with AutoGenerate, the 
template will be transformed to include a custom resource.

e.g.

Resources:
    MyEC2:
        Type: AWS::EC2::Instance
        Properties:
            KeyName: AutoGenerate-MyKey01

An SSH key called MyKey01 will be created.

This function handles both the macro and the custom resource.

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


def inject_sshkey_resource(fragment, key_name):
    'Injects the SSH Key custom resource into the template fragment'
        
    # SSHKeyCR
    custom_resource = {
        'Type': 'Custom::CreateSSHKey',
        'Version': '1.0',
        'Properties': {
            'ServiceToken': {
                'Ref': 'FunctionArn'
            },
            'KeyName': key_name
        }
    }

    fragment['Resources']['SSHKeyCR'] = custom_resource
    
    return True


AUTO_GENERATE = 'AutoGenerate-'


def macro_handler(event, _):
    "Handler for the template macro"
    
    print(event)

    # Get the template fragment, which is the entire starting template
    fragment = event['fragment']
    
    key_name = None
    ec2_resource = None

    # Look through resources to find one with type CloudTrailBucket
    for _, r in fragment['Resources'].items():
        if r['Type'] == 'AWS::EC2::Instance':
            for p_name, p in r['Properties'].items():
                if p_name == 'KeyName':
                    if isinstance(p, str) and p.startswith(AUTO_GENERATE):
                        # We found an EC2 instance with our KeyName property
                        ec2_resource = r
                        key_name = p.replace(AUTO_GENERATE, '')
                        # For the lab we will only support one resource
                        break 
    
    if key_name:
        # Make the EC2 resource depend on the injected custom resource
        if "DependsOn" not in ec2_resource:
            ec2_resource["DependsOn"] = []
        elif isinstance(ec2_resource["DependsOn"], str):
            # We need this to be an array, not a string
            s = ec2_resource["DependsOn"]
            ec2_resource["DependsOn"] = []
            ec2_resource["DependsOn"].append(s)

        ec2_resource["DependsOn"].append("SSHKeyCR")
        ec2_resource["Properties"]["KeyName"] = key_name

        # Inject the custom resource
        inject_sshkey_resource(fragment, key_name)

    # Return the transformed fragment
    return {
        "requestId": event["requestId"],
        "status": "success",
        "fragment": fragment,
    }


def lambda_handler(event, context):
    "Lambda handler for custom resource and macro"

    # Figure out if this is a custom resource request or a macro request
    try:
        if 'RequestType' in event:
            return custom_resource_handler(event, context)
        else:
            return macro_handler(event, context)
    except Exception:
        log_exception()
        raise
