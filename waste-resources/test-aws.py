import os

print("AWS_ACCESS_KEY_ID:", os.getenv('AWS_ACCESS_KEY_ID'))
print("AWS_SECRET_ACCESS_KEY:", os.getenv('AWS_SECRET_ACCESS_KEY'))
print("AWS_DEFAULT_REGION:", os.getenv('AWS_DEFAULT_REGION'))

import boto3

try:
    ec2 = boto3.client('ec2')
    response = ec2.describe_instances()
    print("EC2 instances found: ", response)
except Exception as e:
    print(f"Error: {e}")
