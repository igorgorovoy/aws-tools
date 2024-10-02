import boto3
import json
import os
from botocore.exceptions import ClientError


def init_clients(region):
    ec2_client = boto3.client('ec2', region_name=region)
    ssm_client = boto3.client('ssm', region_name=region)
    return ec2_client, ssm_client


def get_active_instances(ec2_client, instance_ids, excluded_instances):
    instances_to_manage = [inst for inst in instance_ids if inst not in excluded_instances]
    return instances_to_manage


def save_instances_to_ssm(ssm_client, parameter_name, instances):
    try:
        ssm_client.put_parameter(
            Name=parameter_name,
            Value=json.dumps(instances),
            Type='String',
            Overwrite=True
        )
        print(f'Stored {len(instances)} EC2 instance IDs to SSM parameter {parameter_name}.')
    except ClientError as e:
        print(f'Failed to store parameters to SSM: {e}')
        raise


def get_instances_from_ssm(ssm_client, parameter_name):
    try:
        response = ssm_client.get_parameter(Name=parameter_name)
        instances = json.loads(response['Parameter']['Value'])
        print(f'Retrieved {len(instances)} EC2 instance IDs from SSM parameter {parameter_name}.')
        return instances
    except ssm_client.exceptions.ParameterNotFound:
        print(f'No SSM parameter found with name {parameter_name}.')
        return []
    except ClientError as e:
        print(f'Failed to retrieve parameters from SSM: {e}')
        raise


def disable_instances(ec2_client, ssm_client, parameter_name, instances):
    if not instances:
        print('No instances to disable.')
        return

    save_instances_to_ssm(ssm_client, parameter_name, instances)

    try:
        ec2_client.stop_instances(InstanceIds=instances)
        print(f'Stopped EC2 instances: {instances}')
    except ClientError as e:
        print(f'Failed to stop instances: {e}')
        raise


def enable_instances(ec2_client, ssm_client, parameter_name):
    instances = get_instances_from_ssm(ssm_client, parameter_name)

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
    ssm_parameter = event.get('SSM_PARAMETER', os.environ.get('SSM_PARAMETER', '/ec2/developers-disable-instances'))
    instances = event.get('INSTANCES', os.environ.get('INSTANCES', []))
    excluded_instances = event.get('EXCLUDED_INSTANCES', os.environ.get('EXCLUDED_INSTANCES', []))

    ec2_client, ssm_client = init_clients(region)

    if action == 'disable':
        instances_to_disable = get_active_instances(ec2_client, instances, excluded_instances)
        disable_instances(ec2_client, ssm_client, ssm_parameter, instances_to_disable)
    elif action == 'enable':
        enable_instances(ec2_client, ssm_client, ssm_parameter)
    else:
        print(f'Invalid action: {action}')
