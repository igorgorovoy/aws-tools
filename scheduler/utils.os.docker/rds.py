import boto3
import json
import argparse
import sys
from botocore.exceptions import ClientError

# Ініціалізація клієнтів для RDS та SSM
def init_clients(region):
    rds_client = boto3.client('rds', region_name=region)
    ssm_client = boto3.client('ssm', region_name=region)
    return rds_client, ssm_client

# Отримання списку RDS інстансів, за винятком виключених
def get_active_rds_instances(rds_client, db_instance_identifiers, excluded_instances):
    # Фільтрування виключених інстансів
    instances_to_manage = [inst for inst in db_instance_identifiers if inst not in excluded_instances]
    return instances_to_manage

# Збереження списку RDS інстансів в SSM
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
        sys.exit(1)

# Отримання списку RDS інстансів з SSM
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
        sys.exit(1)

# Вимкнення (зупинка) RDS інстансів
def disable_rds_instances(rds_client, ssm_client, parameter_name, instances):
    if not instances:
        print('No RDS instances to disable.')
        return

    # Збереження списку інстансів у SSM
    save_instances_to_ssm(ssm_client, parameter_name, instances)

    for instance_id in instances:
        try:
            # Перевірка, чи інстанс можна зупинити
            response = rds_client.describe_db_instances(DBInstanceIdentifier=instance_id)
            db_instance = response['DBInstances'][0]
            status = db_instance['DBInstanceStatus']
            engine = db_instance['Engine']

            if status != 'available':
                print(f'RDS instance {instance_id} is not in available state (current state: {status}). Skipping.')
                continue

            # Зупинка інстансу
            rds_client.stop_db_instance(DBInstanceIdentifier=instance_id)
            print(f'Stopped RDS instance: {instance_id}')
        except ClientError as e:
            print(f'Failed to stop RDS instance {instance_id}: {e}')

# Включення (запуск) RDS інстансів
def enable_rds_instances(rds_client, ssm_client, parameter_name):
    # Отримання списку інстансів з SSM
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

            # Запуск інстансу
            rds_client.start_db_instance(DBInstanceIdentifier=instance_id)
            print(f'Started RDS instance: {instance_id}')
        except ClientError as e:
            print(f'Failed to start RDS instance {instance_id}: {e}')

# Основна функція
def main():
    parser = argparse.ArgumentParser(description='Disable or enable RDS instances and manage their state in SSM.')
    parser.add_argument('--region', required=True, help='AWS region')
    parser.add_argument('--instances', nargs='*', default=[], help='List of RDS DB instance identifiers to manage')
    parser.add_argument('--excluded-instances', nargs='*', default=[], help='List of RDS DB instance identifiers to exclude')
    parser.add_argument('--action', choices=['disable', 'enable'], required=True, help='Action to perform: disable or enable RDS instances')
    parser.add_argument('--ssm-parameter', required=True, help='SSM Parameter name to store/retrieve instance IDs')

    args = parser.parse_args()

    rds_client, ssm_client = init_clients(args.region)

    if args.action == 'disable':
        instances = get_active_rds_instances(rds_client, args.instances, args.excluded_instances)
        disable_rds_instances(rds_client, ssm_client, args.ssm_parameter, instances)
    elif args.action == 'enable':
        enable_rds_instances(rds_client, ssm_client, args.ssm_parameter)

if __name__ == '__main__':
    main()
