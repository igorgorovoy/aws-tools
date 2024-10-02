import boto3
import json
import argparse
import sys
from botocore.exceptions import ClientError

# Ініціалізація клієнтів для EC2 та SSM
def init_clients(region):
    ec2_client = boto3.client('ec2', region_name=region)
    ssm_client = boto3.client('ssm', region_name=region)
    return ec2_client, ssm_client

# Отримання списку EC2 інстансів, за винятком виключених
def get_active_instances(ec2_client, instance_ids, excluded_instances):
    # Фільтрація виключених інстансів
    instances_to_manage = [inst for inst in instance_ids if inst not in excluded_instances]
    return instances_to_manage

# Збереження списку EC2 інстансів в SSM
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
        sys.exit(1)

# Отримання списку EC2 інстансів з SSM
def get_instances_from_ssm(ssm_client, parameter_name):
    try:
        response = ssm_client.get_parameter(Name=parameter_name)
        instances = json.loads(response['Parameter']['Value'])
        print(f'Retrieved {len(instances)} EC2 instance IDs from SSM parameter {parameter_name}.')
        return instances
    except ssm_client.exceptions.ParameterNotFound:
        print(f'No SSM parameter found with name {parameter_name}.')
        sys.exit(1)
    except ClientError as e:
        print(f'Failed to retrieve parameters from SSM: {e}')
        sys.exit(1)

# Вимкнення (зупинка) EC2 інстансів
def disable_instances(ec2_client, ssm_client, parameter_name, instances):
    if not instances:
        print('No instances to disable.')
        return

    # Збереження списку інстансів у SSM
    save_instances_to_ssm(ssm_client, parameter_name, instances)

    try:
       # ec2_client.stop_instances(InstanceIds=instances)
        print(f'Stopped EC2 instances: {instances}')
    except ClientError as e:
        print(f'Failed to stop instances: {e}')
        sys.exit(1)

# Включення (запуск) EC2 інстансів
def enable_instances(ec2_client, ssm_client, parameter_name):
    # Отримання списку інстансів з SSM
    instances = get_instances_from_ssm(ssm_client, parameter_name)

    if not instances:
        print('No instances to enable.')
        return

    try:
        ec2_client.start_instances(InstanceIds=instances)
        print(f'Started EC2 instances: {instances}')
    except ClientError as e:
        print(f'Failed to start instances: {e}')
        sys.exit(1)

# Основна функція
def main():
    parser = argparse.ArgumentParser(description='Disable or enable EC2 instances and manage their state in SSM.')
    parser.add_argument('--region', required=True, help='AWS region')
    parser.add_argument('--instances', nargs='*', default=[], help='List of EC2 instance IDs to manage')
    parser.add_argument('--excluded-instances', nargs='*', default=[], help='List of EC2 instance IDs to exclude')
    parser.add_argument('--action', choices=['disable', 'enable'], required=True, help='Action to perform: disable or enable EC2 instances')
    parser.add_argument('--ssm-parameter', required=True, help='SSM Parameter name to store/retrieve instance IDs')

    args = parser.parse_args()

    ec2_client, ssm_client = init_clients(args.region)

    if args.action == 'disable':
        instances = get_active_instances(ec2_client, args.instances, args.excluded_instances)
        disable_instances(ec2_client, ssm_client, args.ssm_parameter, instances)
    elif args.action == 'enable':
        enable_instances(ec2_client, ssm_client, args.ssm_parameter)

if __name__ == '__main__':
    main()
