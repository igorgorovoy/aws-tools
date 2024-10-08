import boto3
from botocore.exceptions import ClientError
import json
import os


def get_boto3_client(service, region):
    return boto3.client(service, region_name=region)


def parse_instances(input_instances):
    """
    Функція для парсингу вхідних даних інстансів.
    Повертає список інстансів незалежно від того, чи передано їх як список чи рядок.
    """
    if isinstance(input_instances, list):
        return input_instances
    elif isinstance(input_instances, str):
        try:
            # Спробуємо розпарсити як JSON список
            return json.loads(input_instances)
        except json.JSONDecodeError:
            # Якщо не JSON, розділимо рядок за комами
            return [inst.strip() for inst in input_instances.split(',') if inst.strip()]
    else:
        return []


def get_active_rds_instances(db_instance_identifiers, excluded_instances):
    """
    Фільтрує список інстансів, виключаючи ті, які знаходяться у списку виключень.
    """
    instances_to_manage = [inst for inst in db_instance_identifiers if inst not in excluded_instances]
    return instances_to_manage


def disable_rds_instances(rds_client, instances):
    """
    Зупиняє вказані RDS інстанси, якщо вони знаходяться в стані 'available'.
    """
    if not instances:
        print('No RDS instances to disable.')
        return

    for instance_id in instances:
        try:
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


def enable_rds_instances(rds_client, instances):
    """
    Запускає вказані RDS інстанси, якщо вони знаходяться в стані 'stopped'.
    """
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


def lambda_handler(event, context):
    """
    Основна функція Lambda, яка керує запуском та зупинкою RDS інстансів.
    """
    # Отримання параметрів з події або змінних середовища
    action = event.get('ACTION', os.environ.get('ACTION', 'enable')).lower()
    region = event.get('REGION', os.environ.get('REGION', 'eu-west-1'))

    # Отримання списків інстансів
    db_instance_identifiers = event.get('INSTANCES', os.environ.get('INSTANCES', '[]'))
    excluded_instances = event.get('EXCLUDED_INSTANCES', os.environ.get('EXCLUDED_INSTANCES', '[]'))

    # Парсинг списків інстансів
    db_instance_identifiers = parse_instances(db_instance_identifiers)
    excluded_instances = parse_instances(excluded_instances)

    print(f"Region: {region}")
    print(f"Parsed INSTANCES: {db_instance_identifiers}")
    print(f"Parsed EXCLUDED_INSTANCES: {excluded_instances}")

    # Ініціалізація клієнтів Boto3
    try:
        rds_client = get_boto3_client('rds', region)
    except Exception as e:
        print(f'Error initializing Boto3 RDS client: {e}')
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to initialize RDS client.'})
        }

    # Фільтрація інстансів для керування
    instances_to_manage = get_active_rds_instances(db_instance_identifiers, excluded_instances)
    print(f"Instances to manage: {instances_to_manage}")

    # Виконання дії на основі параметра ACTION
    if action == 'disable':
        disable_rds_instances(rds_client, instances_to_manage)
        message = f'Action "disable" completed successfully on instances: {instances_to_manage}.'
    elif action == 'enable':
        enable_rds_instances(rds_client, instances_to_manage)
        message = f'Action "enable" completed successfully on instances: {instances_to_manage}.'
    else:
        message = 'Invalid action specified. Use "disable" or "enable".'
        print(message)
        return {
            'statusCode': 400,
            'body': json.dumps({'error': message})
        }

    return {
        'statusCode': 200,
        'body': json.dumps({'message': message})
    }
