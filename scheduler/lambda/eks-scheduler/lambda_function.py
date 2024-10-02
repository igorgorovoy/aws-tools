import boto3
import json
import os
from botocore.exceptions import ClientError


# Ініціалізація клієнтів для EKS та SSM
def init_clients(region):
    eks_client = boto3.client('eks', region_name=region)
    ssm_client = boto3.client('ssm', region_name=region)
    return eks_client, ssm_client


# Отримання активних Node Groups, виключаючи ті, що в списку виключень
def get_active_nodegroups(eks_client, cluster_name, excluded_nodegroups):
    response = eks_client.list_nodegroups(clusterName=cluster_name)
    nodegroups = response['nodegroups']
    active_nodegroups = [ng for ng in nodegroups if ng not in excluded_nodegroups]
    return active_nodegroups


# Збереження конфігурації Node Group в SSM
def save_nodegroup_config_to_ssm(eks_client, ssm_client, cluster_name, nodegroup_name):
    response = eks_client.describe_nodegroup(clusterName=cluster_name, nodegroupName=nodegroup_name)
    scaling_config = response['nodegroup']['scalingConfig']

    parameter_name = f'/eks/{cluster_name}/{nodegroup_name}/scalingConfig'
    ssm_client.put_parameter(
        Name=parameter_name,
        Value=json.dumps(scaling_config),
        Type='String',
        Overwrite=True
    )
    print(f'Scaling config for {nodegroup_name} saved to SSM.')


# Вимкнення Node Group (масштабування вниз)
def scale_down_nodegroup(eks_client, cluster_name, nodegroup_name, original_scaling_config):
    new_scaling_config = {
        'minSize': 0,
        'maxSize': original_scaling_config['maxSize'],  # Залишаємо maxSize без змін
        'desiredSize': 0
    }

    eks_client.update_nodegroup_config(
        clusterName=cluster_name,
        nodegroupName=nodegroup_name,
        scalingConfig=new_scaling_config
    )
    print(f'Node group {nodegroup_name} in cluster {cluster_name} scaled down to 0 nodes.')


# Включення Node Group з параметрами з SSM
def scale_up_nodegroup(eks_client, ssm_client, cluster_name, nodegroup_name):
    parameter_name = f'/eks/{cluster_name}/{nodegroup_name}/scalingConfig'
    try:
        response = ssm_client.get_parameter(Name=parameter_name)
        scaling_config = json.loads(response['Parameter']['Value'])
    except ssm_client.exceptions.ParameterNotFound:
        print(f'No scaling config found in SSM for {nodegroup_name}. Skipping.')
        return

    eks_client.update_nodegroup_config(
        clusterName=cluster_name,
        nodegroupName=nodegroup_name,
        scalingConfig=scaling_config
    )
    print(f'Node group {nodegroup_name} in cluster {cluster_name} scaled up with saved parameters.')



def lambda_handler(event, context):
    cluster_name = event.get('CLUSTER_NAME', os.environ.get('CLUSTER_NAME', 'dev-1-30'))
    excluded_nodegroups =  event.get('EXCLUDED_NODEGROUPS', os.environ.get('EXCLUDED_NODEGROUPS', []))
    action = event.get('ACTION', os.environ.get('ACTION', 'enable'))
    region = event.get('REGION', os.environ.get('REGION', 'eu-central-1'))


    eks_client, ssm_client = init_clients(region)

    if action == 'disable':
        nodegroups = get_active_nodegroups(eks_client, cluster_name, excluded_nodegroups)
        for nodegroup in nodegroups:
            try:
                response = eks_client.describe_nodegroup(clusterName=cluster_name, nodegroupName=nodegroup)
                scaling_config = response['nodegroup']['scalingConfig']
                save_nodegroup_config_to_ssm(eks_client, ssm_client, cluster_name, nodegroup)
                scale_down_nodegroup(eks_client, cluster_name, nodegroup, scaling_config)
            except ClientError as e:
                print(f'Error processing nodegroup {nodegroup}: {e}')
    elif action == 'enable':
        nodegroups = get_active_nodegroups(eks_client, cluster_name, excluded_nodegroups)
        for nodegroup in nodegroups:
            try:
                scale_up_nodegroup(eks_client, ssm_client, cluster_name, nodegroup)
            except ClientError as e:
                print(f'Error processing nodegroup {nodegroup}: {e}')
    else:
        print(f'Invalid action: {action}')
