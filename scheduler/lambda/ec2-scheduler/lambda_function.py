import boto3
from botocore.exceptions import ClientError
import json
import os

def init_clients(region):
    print("Region: " + region)
    ec2_client = boto3.client('ec2', region_name=region)
    return ec2_client

def parse_instances(input_instances):
    if isinstance(input_instances, list):
        return input_instances
    elif isinstance(input_instances, str):
        try:
            return json.loads(input_instances)
        except json.JSONDecodeError:
            return [inst.strip() for inst in input_instances.split(',') if inst.strip()]
    else:
        return []

def get_active_instances(instance_ids, excluded_instances):
    instances_to_manage = [inst for inst in instance_ids if inst not in excluded_instances]
    return instances_to_manage

def disable_instances(ec2_client, instances):
    if not instances:
        print('No instances to disable.')
        return

    try:
        ec2_client.stop_instances(InstanceIds=instances)
        print(f'Stopped EC2 instances: {instances}')
    except ClientError as e:
        print(f'Failed to stop instances: {e}')
        raise

def enable_instances(ec2_client, instances):
    print("Instances to enable: " + str(instances))
    if not instances:
        print('No instances to enable.')
        return

    try:
        ec2_client.start_instances(InstanceIds=instances)
        print(f'Started EC2 instances: {instances}')
    except ClientError as e:
        print(f'Failed to start instances: {e}')
        raise

def lambda_handler(event, context):
    action = event.get('ACTION', os.environ.get('ACTION', 'enable'))
    region = event.get('REGION', os.environ.get('REGION', 'eu-central-1'))
    instances = event.get('INSTANCES', os.environ.get('INSTANCES', '[]'))
    excluded_instances = event.get('EXCLUDED_INSTANCES', os.environ.get('EXCLUDED_INSTANCES', '[]'))

    instances = parse_instances(instances)
    excluded_instances = parse_instances(excluded_instances)

    print(f"Parsed INSTANCES: {instances}")
    print(f"Parsed EXCLUDED_INSTANCES: {excluded_instances}")

    ec2_client = init_clients(region)

    instances_to_manage = get_active_instances(instances, excluded_instances)
    print(f"Instances to manage: {instances_to_manage}")

    if action == 'disable':
        disable_instances(ec2_client, instances_to_manage)
    elif action == 'enable':
        enable_instances(ec2_client, instances_to_manage)
    else:
        print(f'Invalid action: {action}')
