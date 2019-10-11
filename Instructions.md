# Hands-On with Advanced AWS CloudFormation Techniques and New Features

You've written templates for AWS CloudFormation, and now it's time to move to the next level. In this workshop, we explore advanced AWS CloudFormation functionality to help you improve your authoring skills for complex templates. Learn how to use AWS CloudFormation custom resources, mappings and constraints, StackSets, and macros to increase your infrastructure automation efficiency, while simultaneously addressing complex business requirements. A laptop is required for all participants.

## Lab #1 - Custom Resources

You can extend the capabilities of CloudFormation with [custom resources](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/template-custom-resources.html) by delegating work to a Lambda function that is specially crafted to interact with the CloudFormation service. In your code, you implement the create, update, and delete actions, and then you send a response with the status of the operation.

In this lab, you will create a custom resource that generates an SSH key and stores it in SSM parameter store.

**Note - This lab requires you to be in the N.Virginia region**

1. Log in to your AWS account, select the N. Virginia region, and go to the Lambda console

2. Click **Create Function** and choose **Author From Scratch**. 

3. Give it a descriptive **Name** such as 'ssh-key-gen'.

4. Choose Python 3.6 as the **Runtime**

5. Choose **Create a Custom Role**. A new tab will open. 

6. Give the role a name such as 'ssh-key-gen-role', expand **View Policy Document**, click **Edit**, and paste in the policy from [lambda\_policy.json](lambda_policy.json). 

7. **Click Allow** to associate the new role with the lambda function.

   1. Examine the policy to see what permissions we are granting to the new function

      ```json
      {
          "Version": "2012-10-17",
          "Statement": [
              {
                  "Effect": "Allow",
                  "Action": [
                      "logs:CreateLogGroup",
                      "logs:CreateLogStream",
                      "logs:PutLogEvents"
                  ],
                  "Resource": "arn:aws:logs:*:*:*"
              },
              {
                  "Effect": "Allow",
                  "Action": [
                      "ec2:CreateKeyPair",
                      "ec2:DescribeKeyPairs",
                      "ssm:PutParameter"
                  ],
                  "Resource": "*"
              },
              {
                  "Effect": "Allow",
                  "Action": [
                      "ec2:DeleteKeyPair",
                      "ssm:DeleteParameter"
                  ],
                  "Resource": "*"
              }
          ]
      }
      
      ```

8. Click **Create Function** and then paste in the code from [custom\_resource\_lambda.py](custom_resource_lambda.py) into the editor.

   1. Examine the function to see what we are doing to implement the custom resource.

      Every lambda function has a handler that is called by the lambda environment in response to a trigger.

      ```python
      def lambda_handler(event, context):
          "Lambda handler for the custom resource"
      
          try:
              return custom_resource_handler(event, context)
          except Exception:
              log_exception()
              raise
      
      ```

      The handler function must determine the type of request and send a response back to CloudFormation. In this code snippet, we handle a create request from CloudFormation.

      ```python
       
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
      
      ```

   2. Responses are sent to the CloudFormation endpoints as HTTPS PUTs. This code snippet uses urllib, which is a part of the Python 3 standard library.

    ```python
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
    ```

9. Click **Save** to save the function. Copy the ARN at the top right of the screen.

![](arn.png)

11. Go to the CloudFormation console and click **Create Stack**

12. Select **Upload a template to Amazon S3** and upload [custom\_resource\_cfn.yml](custom_resource_cfn.yml) 

    1. Examine the CloudFormation template to see how a custom resource is configured.

     ```yaml
       Resources:
         SSHKeyCR:
             Type: Custom::CreateSSHKey
             Version: "1.0"
             Properties:
               ServiceToken: !Ref FunctionArn
               KeyName: !Ref SSHKeyName
     ```

13. Give the stack a unique name such as ssh-key-gen-cr and paste in the ARN from the function you created earlier into the **FunctionArn** parameter text box. 

14. Fill out the remaining parameters, Click **Next**, then **Next** on the following screen.

15. Check the box that reads **I acknowledge that AWS CloudFormation might create IAM resources.** and then click **Create**.

16. Once the stack has completed creation (it might take a few minutes), go to the EC2 console and confirm the creation of your new instance.

17. Go to the Systems Manager Console, view Parameter Store and confirm that the key has been stored. It was stored with the Secure String setting, which uses KMS to encrypt the parameter value.

18. Download your SSH key from Parameter Store (***not*** the EC2 console!) and store it in a .pem file with permissions set to 600 on Linux or Mac. You can download it from the console by selecting the key and clicking **Show** under the **Value** at the bottom of the screen. Copy-paste everything beginning with -----BEGIN RSA PRIVATE KEY----- and ending with -----END RSA PRIVATE KEY-----

19. As an alternative to using the console to copy and paste the key, use the following shell commands (assuming that you kept the default key name of MyKey01, and that you have a .ssh directory in your home directory)

    ```bash
    aws ssm get-parameter --name MyKey01 --with-decryption \
        --query Parameter.Value --output text > ~/.ssh/MyKey01.pem
    
    chmod 600 ~/.ssh/MyKey01.pem
    
    ssh -i ~/.ssh/MyKey01.pem ec2-user@<PUBLIC DNS>
    ```

20. **NOTE that this is a private key, and in a production setting you must take steps to ensure that this key is not compromised!**

21. Log in to the newly created EC2 instance to confirm that the key was associated with the instance.

22. Delete the stack and the lambda function.

## Lab #2 - Macros

A CloudFormation [macro](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/template-macros.html) is a type of template transformation that allows you to use a Lambda function to make changes to a template before it is executed.

In this lab, you will create a macro that extends the EC2 resource to automatically create an SSH key for that instance with a name specified in the template. This lab builds on the last one by augmenting the lambda function you wrote to add macro functionality. 

1. Log in to your AWS account and go to the Lambda console

2. Click **Create Function** and choose **Author From Scratch**. 

3. Give it a descriptive name such as 'ssh-key-gen-macro'.

4. Choose Python 3.6 as the **Runtime**

5. Use the role you created earlier with [lambda\_policy.json](lambda_policy.json)

6. Click **Create Function**

7. Paste in the code from [macro\_lambda.py](macro_lambda.py) and **Save**. Copy the ARN at the top of the screen.

  1. Inspect the code to see what is being done by the function. You will notice that it is mostly the same function from the previous lab, with a new handler added for macro functionality.

   ```python
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
   ```

1. The code searches through the template looking for an EC2 resource with an SSHKey property that starts with 'AutoGenerate-'. If it finds one, it injects the custom resource into the template.

    ```python
     
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
    ```

  2. The resource is injected by simply adding it to the resources dictionary in the fragment

   ```python
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
     
   ```

8. Go to the CloudFormation console. You will create two stacks. The first one is for the macro itself, so that it exists in your selected region as a transform that can be used by any future template.

9. Create the macro stack with [macro\_cfn.yml](macro_cfn.yml). This will create the macro itself as a unique named resource within your account.

10. Give the stack a unique name such as ssh-key-macro and paste in the ARN from the function you created earlier in this lab into the **FunctionArn** parameter text box. 

11. Fill out the remaining parameters, click **Next**, then **Next** on the following screen. Click **Create** and wait for it to complete. 

    1. Inspect the template to see how the macro is created. 

     ```yaml
       AWSTemplateFormatVersion: "2010-09-09"
       Description: "This template creates the macro"
       Parameters:
         FunctionArn:
           Type: String
       Resources:
         CloudTrailBucketMacro:
           Type: AWS::CloudFormation::Macro
           Properties:
             Name: AutoGenerateSSHKey
             # Paste in the ARN for the function when you create the stack
             FunctionName: !Ref FunctionArn
             
     ```

12. Create the EC2 instance and key with [macro\_ec2.yml](macro_ec2.yml)

13. Give it a unique name like ssh-key-macro-ec2 and fill out the remaining parameters as you did in lab 1.

14. For this template, you will be prompted to create a change set, since the macro is transforming the original template.

    1. If you get an error like "Error creating change set: Received malformed response from transform ############::AutoGenerateSSHKey", you might have referenced the wrong lambda function. Check the ARN you pasted in as a parameter to make sure it was the correct function ARN.

15. Once the change set is created, review it to see what resources will be created, and then **Execute**.

    1. Inspect the template to see the differences from the previous version. Instead of creating the custom resource explicitly, we invoke the macro to inject it into the template.

     ```yaml
       AWSTemplateFormatVersion: "2010-09-09"
       Transform: AutoGenerateSSHKey
       ...
       MyEC2Instance:
           Type: AWS::EC2::Instance
           Properties:
             # A key called MyKey01 will be created by a custom resource that is 
             # injected into this template when the transform macro runs
             KeyName: AutoGenerate-MyKey01
             InstanceType: t2.micro
             
     ```

16. Download your ssh key from parameter store and confirm that you can log in to your EC2 instance with that key. (Follow the same steps outlined in Lab #1)

17. Delete the stack and the lambda function

18. *Stretch Goal: Modify the CloudFormation template so that you can specify the key name as a parameter.*



## Lab #3 - Mapping and StackSets

**Mappings**

The mappings section of a CloudFormation template matches a key to a corresponding set of named values. For example, if you want to set values based on a region, you can create a mapping that uses the AWS region name as a key and contains the values you want to specify depending on the region where the template is deployed. This may be particularly useful when deploying AMIs globally where you must deploy a different AMI ID per region due to disaster recovery or security considerations that differ across geographic regions. 

**StackSets**

[AWS CloudFormation StackSets](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-concepts.html) extend the functionality of stacks by enabling you to create, update, or delete stacks across multiple accounts and regions with a single operation. Using an administrator account, you define and manage an AWS CloudFormation template, and use the template as the basis for provisioning stacks into selected target accounts across specified regions. For example, you can easily establish a global AWS CloudTrail or AWS Config policy across multiple accounts with a single StackSet operation. You can also use StackSets to deploy resources in a single account across multiple regions. 

In this lab, we will deploy a simple CloudFormation template that provisions an EC2 instance with a simple webserver to verify proper deployment across multiple regions. We will use mappings to properly deploy the proper Amazon Linux 2 AMI for the selected region while using StackSets to configure which AWS regions will deploy this template.

For the sake of simplicity, we will be utilizing one account as both the administrator and execution role but you can utilize StackSets across multiple accounts. Please review the [Prerequisites: Granting Permissions for Stack Set Operations](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-prereqs.html) page for additional information on how to properly configure the two roles required to deploy StackSets across multiple accounts. 

**Deploy StackSet IAM Permissions**

1. Log into your AWS account from the N. Virginia region and click the role selection menu. Click "My Account" and take note of your AccountId. We will need this to properly establish IAM permissions. 

2. Navigate to the CloudFormation console. 

3. Click **Create Stack**

4. Select **Upload a template to Amazon S3** and upload the [mapping\_stacksets\_iam.yml](mapping_stacksets_iam.yml) CloudFormation template. 
    1. Examine the CloudFormation template to see that it is a simple nested CloudFormation template that will call two AWS-provided YAML files to provision IAM roles within your account. 
    
        ```yaml
        AWSTemplateFormatVersion: '2010-09-09'
        Description: This CloudFormation StackSet deploys two AWS provided CloudFormation templates that add Administrator and Execution Roles required to use AWSCloudFormationStackSetAdministrationRole
        Resources:
        AWSCloudFormationStackSetAdministrationRole:
        Type: AWS::CloudFormation::Stack
        Properties:
        TemplateURL: https://s3.amazonaws.com/cloudformation-stackset-sample-templates-us-east-1/AWSCloudFormationStackSetAdministrationRole.yml 
        TimeoutInMinutes: '3'
        AWSCloudFormationStackSetExecutionRole:
        Type: AWS::CloudFormation::Stack
        Properties:
        TemplateURL: https://s3.amazonaws.com/cloudformation-stackset-sample-templates-us-east-1/AWSCloudFormationStackSetExecutionRole.yml 
        TimeoutInMinutes: '3'
        Parameters:
        AdministratorAccountId : !Ref 'AccountID'
        Parameters:
        AccountID:
        Type: String
        Description: Your AWS Account ID
        MaxLength: 12
        MinLength: 12
        ```
    
    You can review the resources deployed in each template here:
    [AWSCloudFormationStackSetAdministrationRole](https://s3.amazonaws.com/cloudformation-stackset-sample-templates-us-east-1/AWSCloudFormationStackSetAdministrationRole.yml)
    
    [AWSCloudFormationStackSetExecutionRole](https://s3.amazonaws.com/cloudformation-stackset-sample-templates-us-east-1/AWSCloudFormationStackSetExecutionRole.yml)

5. Click **Next**.

6. Give your CloudFormation stack a descriptive name such as 'mapping-stacksets-iam'.

7. Specify the AccountID of your AWS account that you obtained earlier and click **Next**.

8. Review any desired tags and additional options and click **Next** 

9. Click the checkbox next to 'I acknowledge that AWS CloudFormation might create IAM resources with custom names.' and then click **Create**.

10. Click the refresh button to see that the two nested CloudFormation templates were successfully deployed into your account.

11. Do not delete these nested stacks until the end of the next session as they are the permissions necessary to deploy a StackSet in your account. 

**Deploy StackSet with Mapping**

1. Navigate to the CloudFormation console and from the CloudFormation drop-down, select **StackSets**.

2. Click **Create StackSet**.

3. Examine the AWS-provided CloudFormation sample templates to get an idea of what configuration operations are possible with StackSets and then click **Upload a template to Amazon S3**. 

4. Click **Browse**, then upload [mapping\_stacksets\_ec2.yml](mapping_stacksets_ec2.yml) and then click **Next**.

    1. Notice the mapping component of this template that will deploy the proper Amazon Linux 2 AMI based on the region where the template is deployed.

    ```yaml
    Mappings:
    # Mapping of Amazon Linux 2 AMI IDs in every AWS Region
    # When deploying a StackSet, the template will automatically deploy the proper AMI in each selected region
    RegionMap:
        us-east-1: 
        AMI: ami-04681a1dbd79675a5
        us-east-2: 
        AMI: ami-0cf31d971a3ca20d6
        us-west-1:
        AMI: ami-0782017a917e973e7
        us-west-2:
        AMI: ami-6cd6f714
        ap-south-1:
        AMI: ami-00b6a8a2bd28daf19
        ap-northeast-3:
        AMI: ami-00f7ef6bf92e8f916
        ap-northeast-2:
        AMI: ami-012566705322e9a8e
        ap-southeast-1:
        AMI: ami-01da99628f381e50a
        ap-southeast-2:
        AMI: ami-00e17d1165b9dd3ec
        ap-northeast-1:
        AMI: ami-08847abae18baa040
        ca-central-1:
        AMI: ami-ce1b96aa
        eu-central-1:
        AMI: ami-0f5dbc86dd9cbf7a8
        eu-west-1:
        AMI: ami-0bdb1d6c15a40392c
        eu-west-2:
        AMI: ami-e1768386
        eu-west-3:
        AMI: ami-06340c8c12baa6a09
        sa-east-1:
        AMI: ami-0ad7b0031d41ed4b9
    ```

*Note: The EC2 instance that is deployed in this template will use the default VPC*

5. Give your CloudFormation stack a descriptive name such as 'mapping-stacksets-ec2', provide a source CIDR IP range that you want to allow HTTP traffic from to verify operation of your web server and then click **Next**. 

*We recommend that you provide the smallest IP range possible depending on your network configuration.*

6. Under "Specify Accounts", click "Deploy stacks in accounts" and provide your AWS AccoundId that you obtained earlier. This input accepts multiple account numbers as well as *.csv files so that you can scale your configuration to multiple accounts. 

7. Scroll down and highlight the regions where you would like to deploy the resources described in the [mapping\_stacksets\_iam.yml](mapping_stacksets_iam.yml) CloudFormation template. The order that regions are selected in the StackSet console will be maintained such that this will be the same order that regions are provisioned when deploying the StackSet. Take note of the regions where you choose to deploy these resources. We recommend you deploy to at least two regions. The more regions you select, the longer the StackSet will take to deploy. 

*NOTE: This template will deploy resources into the default VPC in each selected region. Please select regions where there is still a default VPC*

8. Scroll down and click **Next** 

9. Note that the IAM Administration and IAM Execution Roles are pre-populated. Click **Next**.

10. Review the details of this StackSet deployment and click **Create**.

11. Under the Operations section, you will see the status of this StackSet as running. Under Stacks, you will see an entry for each region you selected when deploying the StackSet. Allow approximately 5 minutes for this deployment to complete. The operation will be complete when all selected regions display a status as "CURRENT".

12. Navigate to the CloudFormation console in one of the regions where you deployed the StackSet. Select Stacks from the CloudFormation dropdown menu and select the StackSet. 

13. On the Outputs tab, click the link to the "Webserver URL" to verify that your webserver successfully deployed in this region.

14. Change to each of the remaining regions that you chose to deploy the StackSet to and repeat step 13.

**Delete StackSet**

1. Navigate back to the region where you deployed the StackSet (N. Virginia) and return to the StackSet console. StackSets are deployed globally but reside only in the region where they were initially deployed.

2. Click the StackSet name.

3. Click **Manage StackSet**.

4. Click **Delete Stacks** and then click **Next**.

5. Enter your AWS account ID into the "Delete stacks from account" input.

6. Click **Add all** to select all regions for deletion and then scroll down to click **Next**.

7. Click **Delete Stacks**.

8. Refresh this page and note that the DELETE operation is running. Allow approximately 5 minutes for this operation to complete across all regions and then navigate to the StackSets console. The operation is finished when there are no regions present under the Stacks section. 

9. Select the StackSet. Under actions, select **Delete StackSet** and then click **Yes, Delete**. If you receive a "Failed to delete StackSet" error, please allow more time for the underlying stacks to be deleted. 

10. Return to the CloudFormation Stacks console and delete the parent mapping-stacksets-iam (or similar) template that you deployed in the first step of this lab. Be sure to select the parent Stack, not the "NESTED" stacks.



## Lab #4 - Drift Detection

AWS CloudFormation allows you to detect if configuration changes were made to your stack resources outside of CloudFormation via the AWS Management Console, CLI, and SDKs. Drift is the difference between the expected configuration values of stack resources defined in CloudFormation templates and the actual configuration values of these resources in the corresponding CloudFormation stacks. This allows you to better manage your CloudFormation stacks and ensure consistency in your resource configurations. For more information on Drift detection, visit the [AWS Blog](https://aws.amazon.com/blogs/aws/new-cloudformation-drift-detection).

In this lab, you will create a CloudFormation stack and purposefully make changes to its resources via other AWS Consoles, so that different types of changes can be visualized using the Drift Detection feature.

**Note - This lab requires you to be in the N.Virginia region**

1. Log in to your AWS account, select the N. Virginia region, and go to the CloudFormation console

2. Click **Create Stack**. 

3. Select **Upload a template to Amazon S3** and upload [drift/my_cfn_stack.yml](drift/my_cfn_stack.yml)

    1. The template defines a Stack with two SQS Queues: an input queue and an error queue.
    
    ```yaml
    AWSTemplateFormatVersion: "2010-09-09"
    Resources: 
      InputQueue: 
        Type: "AWS::SQS::Queue"
        Properties: 
        QueueName: "DriftLab-InputQueue"
        VisibilityTimeout: 30
        RedrivePolicy: 
          deadLetterTargetArn: 
            Fn::GetAtt: 
              - "DeadLetterQueue"
              - "Arn"
          maxReceiveCount: 5
      DeadLetterQueue: 
        Type: "AWS::SQS::Queue"
        Properties: 
        QueueName: "DriftLab-ErrorQueue"
    ```

4. Give the stack a unique name such as drift-lab-with-sqs and **Next**.

5. Leave the options on the next page (parameters, IAM role, etc.) blank and click **Next**.

6. Review the details of your stack and click **Create**.

7. Wait for the stack to complete creation (it might take a few minutes). When complete, the Drift status column will show **NOT_CHECKED**.

8. Select drift-lab-with-sqs on the CloudFormation Stacks view, click **Actions** and **Detect drift**, then click **Yes** to confirm the drift detection operation.

9. You will see a dialog with the progress of the asynchronous drift operation. When complete, the dialog will inform that the stack is **IN_SYNC**.

10. ![](drift_dialog_complete_insync.png)

*NOTE: At this point the stack is in the expected Drift state, which is **IN_SYNC**. You will now simulate a situation that causes the template's definition of resources to diverge from their actual live state, by making changes outside of the CloudFormation Console.*

**Modifying resources**

1. Go to the **Simple Queue Service** Console.

2. Find the DriftLab-InputQueue, select it, and on **Queue Actions**, click **Configure Queue**.

3. Make the following changes to the queue:

    1. Set **Default Visibility Timeout** to 50.
    2. Set **Delivery Delay** to 120.
    3. Uncheck **Use Redrive Policy** to delete the redirection to the error queue on consecutive failures.
    4. Click **Save Changes**.
    

*NOTE: You have now made a change in the value of an existing property, added a new property, and deleted an existing property of the InputQueue resource.*

4. Go to the CloudFormation Console.

5. Select drift-lab-with-sqs on the CloudFormation Stacks view, click **Actions** and **Detect drift**, then click **Yes** to confirm the drift detection operation.

6. When complete, this time the dialog result will show the status as **DRIFTED**.

7. ![](dift_dialog_complete_drifted.png) 

8. Click on **View details** link on the dialog. 

*NOTE: The Drift details are also available from the Stack detail screen. On the Stacks screen, click the drift-lab-with-sqs stack to go to the details screen. As part ofthe stack detail information, notice **Drift status** with a **View details** link.*

9. The **Drift Details** screen shows information of the last drift operation executed for the stack. Notice the **Drift status** is **DRIFTED**.

10. On the **Resource drift status** section, observe the drift status for DeadLetterQueue is **IN_SYNC** since no changes were made. However, the status for InputQueue is **MODIFIED** since the properties specified in the stack's template do not match the live state of the resource.

11. Click to expand InputQueue. On the ride side, under **Differences**, click **Select all**. Note that this will highlight the differences in the template. 

*NOTE: The Drift Detection feature is intended to compare differences between the resources and their properties as specified in the template versus their live state. Properties which are not specified in the template will not be shown in the drift status for the resource. In the case of this example, the change to the property **Delivery Delay** will not be reflected because the property is not specified in the template. The CloudFormation template of a Stack should contain values for all properties which are meant to be compared by Drift Detection.*

**Remediating by changing resources**

One option to recover a stack from a **DRIFTED** state is modifying its resources to revert their properties to the values specified in the stack's template. This will bring the resources inline with the values expected by the template and will allow CloudFormation to make changes based on the actual values during future operations for this stack.

1. Go to the **Simple Queue Service** Console.

2. Find the DriftLab-InputQueue, select it, and on **Queue Actions**, click **Configure Queue**.

3. Make the following changes to the queue:

    1. Set **Default Visibility Timeout** to 30.
    2. Check **Use Redrive Policy**, for **Dead Letter Queue** specify DriftLab-ErrorQueue, and for **Maximum Receives** enter 5.
    3. Click **Save Changes**.

4. Go to the CloudFormation Console.

5. Select drift-lab-with-sqs on the CloudFormation Stacks view, click **Actions** and **Detect drift**, then click **Yes** to confirm the drift detection operation.

6. When complete, time the dialog result will show the status as **IN_SYNC**.

**OPTIONAL: Remediating by overwriting property values**

*Note: applying a stack update operation over resources that are out of sync with their template definition is a RISKY operation. Consider carefully what the differences between the template and the live state of resources represent on each specific scenario and for each specific property. Simulate your exact scenario in a non-production environment. Keep in mind the interaction between resources and the consequences of a stack update rollback (applying the values of the last version of the template). If possible, this operation should be avoided.*

1. Go to the **Simple Queue Service** Console.

2. Find the DriftLab-InputQueue, select it, and on **Queue Actions**, click **Configure Queue**.

3. Make the following changes to the queue:

    1. Set **Default Visibility Timeout** to 80.
    2. Click **Save Changes**.
    
4. Go to the CloudFormation Console.

5. Select drift-lab-with-sqs on the CloudFormation Stacks view, click **Actions** and **Detect drift**, then click **Yes** to confirm the drift detection operation.

6. When complete, the dialog result will show the status as **DRIFTED**.

7. Edit the template file [drift\my_cfn_stack.yml](my_cfn_stack.yml)

    1. Set **Default Visibility Timeout** to 40.
    2. Save the file.
    
8. Go to the CloudFormation Console.

9. Select drift-lab-with-sqs on the CloudFormation Stacks view, click **Actions** and **Update Stack**.

10. Select **Upload a template to Amazon S3** and upload your locally edited template my_cfn_stack.yml

11. Click **Next** on the **Select Template** screen, then click **Next** on the next two pages, and finally click **Update** on the review page.

12. After the stack is in **UPDATE_COMPLETE** state, select drift-lab-with-sqs on the CloudFormation Stacks view, click **Actions** and **Detect drift**, then click **Yes** to confirm the drift detection operation.

13. When complete, the dialog result will show the status as **IN_SYNC**.











