import boto3
import json
import os
from botocore.exceptions import ClientError


# Ініціалізація клієнтів для Auto Scaling і SSM
def init_clients(region):
    asg_client = boto3.client('autoscaling', region_name=region)
    ssm_client = boto3.client('ssm', region_name=region)
    return asg_client, ssm_client


# Отримання активних ASG, виключаючи ті, що в списку виключень
def get_active_asgs(asg_client, excluded_asgs):
    response = asg_client.describe_auto_scaling_groups()
    all_asgs = response['AutoScalingGroups']
    active_asgs = [asg['AutoScalingGroupName'] for asg in all_asgs if asg['AutoScalingGroupName'] not in excluded_asgs]
    return active_asgs


# Збереження конфігурації ASG в SSM
def save_asg_config_to_ssm(asg_client, ssm_client, asg_name):
    response = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])
    scaling_config = response['AutoScalingGroups'][0]['MinSize'], response['AutoScalingGroups'][0]['MaxSize'], response['AutoScalingGroups'][0]['DesiredCapacity']

    parameter_name = f'/asg/{asg_name}/scalingConfig'
    ssm_client.put_parameter(
        Name=parameter_name,
        Value=json.dumps(scaling_config),
        Type='String',
        Overwrite=True
    )
    print(f'Scaling config for {asg_name} saved to SSM.')


# Вимкнення ASG (масштабування вниз)
def scale_down_asg(asg_client, asg_name):
    response = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])
    original_scaling_config = response['AutoScalingGroups'][0]

    new_scaling_config = {
        'MinSize': 0,
        'MaxSize': original_scaling_config['MaxSize'],  # Залишаємо maxSize без змін
        'DesiredCapacity': 0
    }

    asg_client.update_auto_scaling_group(
        AutoScalingGroupName=asg_name,
        MinSize=new_scaling_config['MinSize'],
        MaxSize=new_scaling_config['MaxSize'],
        DesiredCapacity=new_scaling_config['DesiredCapacity']
    )
    print(f'ASG {asg_name} scaled down to 0 instances.')


# Включення ASG з параметрами з SSM
def scale_up_asg(asg_client, ssm_client, asg_name):
    parameter_name = f'/asg/{asg_name}/scalingConfig'
    try:
        response = ssm_client.get_parameter(Name=parameter_name)
        scaling_config = json.loads(response['Parameter']['Value'])
        min_size, max_size, desired_capacity = scaling_config
    except ssm_client.exceptions.ParameterNotFound:
        print(f'No scaling config found in SSM for {asg_name}. Skipping.')
        return

    asg_client.update_auto_scaling_group(
        AutoScalingGroupName=asg_name,
        MinSize=min_size,
        MaxSize=max_size,
        DesiredCapacity=desired_capacity
    )
    print(f'ASG {asg_name} scaled up with saved parameters.')


def lambda_handler(event, context):
    excluded_asgs = event.get('EXCLUDED_ASGS', os.environ.get('EXCLUDED_ASGS', []))
    action = event.get('ACTION', os.environ.get('ACTION', 'enable'))
    region = event.get('REGION', os.environ.get('REGION', 'eu-central-1'))

    asg_client, ssm_client = init_clients(region)

    if action == 'disable':
        asgs = get_active_asgs(asg_client, excluded_asgs)
        for asg in asgs:
            try:
                save_asg_config_to_ssm(asg_client, ssm_client, asg)
                scale_down_asg(asg_client, asg)
            except ClientError as e:
                print(f'Error processing ASG {asg}: {e}')
    elif action == 'enable':
        asgs = get_active_asgs(asg_client, excluded_asgs)
        for asg in asgs:
            try:
                scale_up_asg(asg_client, ssm_client, asg)
            except ClientError as e:
                print(f'Error processing ASG {asg}: {e}')
    else:
        print(f'Invalid action: {action}')
