import boto3
import json
import os
from botocore.exceptions import ClientError


# Optional: Initialize a global cache for clients if you expect multiple regions
# client_cache = {}

def get_boto3_client(service, region):
    return boto3.client(service, region_name=region)


# Get active RDS instances excluding the specified ones
def get_active_rds_instances(db_instance_identifiers, excluded_instances):
    instances_to_manage = [inst for inst in db_instance_identifiers if inst not in excluded_instances]
    return instances_to_manage


# Save the list of RDS instances to SSM
def save_instances_to_ssm(ssm_client, parameter_name, instances):
    try:
        ssm_client.put_parameter(
            Name=parameter_name,
            Value=json.dumps(instances),
            Type='String',
            Overwrite=True
        )
        print(f'Stored {len(instances)} RDS instance IDs to SSM parameter {parameter_name}.')
    except ClientError as e:
        print(f'Failed to store parameters to SSM: {e}')
        raise


# Get the list of RDS instances from SSM
def get_instances_from_ssm(ssm_client, parameter_name):
    try:
        response = ssm_client.get_parameter(Name=parameter_name)
        instances = json.loads(response['Parameter']['Value'])
        print(f'Retrieved {len(instances)} RDS instance IDs from SSM parameter {parameter_name}.')
        return instances
    except ssm_client.exceptions.ParameterNotFound:
        print(f'No SSM parameter found with name {parameter_name}.')
        return []
    except ClientError as e:
        print(f'Failed to retrieve parameters from SSM: {e}')
        raise


# Disable (stop) RDS instances
def disable_rds_instances(rds_client, ssm_client, parameter_name, instances):
    if not instances:
        print('No RDS instances to disable.')
        return

    save_instances_to_ssm(ssm_client, parameter_name, instances)

    for instance_id in instances:
        try:
            response = rds_client.describe_db_instances(DBInstanceIdentifier=instance_id)
            db_instance = response['DBInstances'][0]
            status = db_instance['DBInstanceStatus']
            engine = db_instance['Engine']

            if status != 'available':
                print(f'RDS instance {instance_id} is not in available state (current state: {status}). Skipping.')
                continue

            # Stop the instance
            rds_client.stop_db_instance(DBInstanceIdentifier=instance_id)
            print(f'Stopped RDS instance: {instance_id}')
        except ClientError as e:
            print(f'Failed to stop RDS instance {instance_id}: {e}')


# Enable (start) RDS instances
def enable_rds_instances(rds_client, ssm_client, parameter_name):
    instances = get_instances_from_ssm(ssm_client, parameter_name)

    if not instances:
        print('No RDS instances to enable.')
        return

    for instance_id in instances:
        try:
            response = rds_client.describe_db_instances(DBInstanceIdentifier=instance_id)
            db_instance = response['DBInstances'][0]
            status = db_instance['DBInstanceStatus']

            if status != 'stopped':
                print(f'RDS instance {instance_id} is not in stopped state (current state: {status}). Skipping.')
                continue

            # Start the instance
            rds_client.start_db_instance(DBInstanceIdentifier=instance_id)
            print(f'Started RDS instance: {instance_id}')
        except ClientError as e:
            print(f'Failed to start RDS instance {instance_id}: {e}')


def lambda_handler(event, context):
    # Extract parameters from the event or environment variables
    action = event.get('ACTION', os.environ.get('ACTION', 'enable')).lower()
    region = event.get('REGION', os.environ.get('REGION', 'eu-west-1'))
    parameter_name = event.get('SSM_PARAMETER', os.environ.get('SSM_PARAMETER', '/rds/disable-instances'))

    # Ensure INSTANCES and EXCLUDED_INSTANCES are lists
    db_instance_identifiers = event.get('INSTANCES', os.environ.get('INSTANCES', []))
    if isinstance(db_instance_identifiers, str):
        db_instance_identifiers = [db_instance_identifiers]

    excluded_instances = event.get('EXCLUDED_INSTANCES', os.environ.get('EXCLUDED_INSTANCES', []))
    if isinstance(excluded_instances, str):
        excluded_instances = [excluded_instances]

    # Initialize Boto3 clients with the specified region
    try:
        rds_client = get_boto3_client('rds', region)
        ssm_client = get_boto3_client('ssm', region)
    except Exception as e:
        print(f'Error initializing Boto3 clients: {e}')
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to initialize AWS clients.'})
        }

    if action == 'disable':
        instances = get_active_rds_instances(db_instance_identifiers, excluded_instances)
        disable_rds_instances(rds_client, ssm_client, parameter_name, instances)
    elif action == 'enable':
        enable_rds_instances(rds_client, ssm_client, parameter_name)
    else:
        message = 'Invalid action specified. Use "disable" or "enable".'
        print(message)
        return {
            'statusCode': 400,
            'body': json.dumps({'error': message})
        }

    return {
        'statusCode': 200,
        'body': json.dumps({'message': f'Action "{action}" completed successfully.'})
    }
