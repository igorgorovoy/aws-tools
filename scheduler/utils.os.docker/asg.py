import boto3
import json
import argparse
import sys


# Ініціалізація клієнтів для EKS та SSM
def init_clients(region):
    eks_client = boto3.client('eks', region_name=region)
    ssm_client = boto3.client('ssm', region_name=region)
    return eks_client, ssm_client


# Читання всіх Node Groups з кластера, за винятком виключених
def get_active_nodegroups(eks_client, cluster_name, excluded_nodegroups):
    response = eks_client.list_nodegroups(clusterName=cluster_name)
    nodegroups = response['nodegroups']
    # Фільтруємо виключені Node Groups
    active_nodegroups = [ng for ng in nodegroups if ng not in excluded_nodegroups]
    return active_nodegroups


# Збереження конфігурації Node Group в SSM
def save_nodegroup_config_to_ssm(eks_client, ssm_client, cluster_name, nodegroup_name):
    response = eks_client.describe_nodegroup(clusterName=cluster_name, nodegroupName=nodegroup_name)
    scaling_config = response['nodegroup']['scalingConfig']

    # Збереження параметрів у форматі JSON
    parameter_name = f'/eks/{cluster_name}/{nodegroup_name}/scalingConfig'
    ssm_client.put_parameter(
        Name=parameter_name,
        Value=json.dumps(scaling_config),
        Type='String',
        Overwrite=True
    )
    print(f'Scaling config for {nodegroup_name} saved to SSM.')


# Вимкнення (масштабування вниз) Node Group
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


# Основна функція для вимкнення Node Groups
def disable_nodegroups(eks_client, ssm_client, cluster_name, excluded_nodegroups):
    nodegroups = get_active_nodegroups(eks_client, cluster_name, excluded_nodegroups)
    for nodegroup in nodegroups:
        # Отримуємо поточну конфігурацію
        response = eks_client.describe_nodegroup(clusterName=cluster_name, nodegroupName=nodegroup)
        scaling_config = response['nodegroup']['scalingConfig']

        # Зберігаємо конфігурацію в SSM
        save_nodegroup_config_to_ssm(eks_client, ssm_client, cluster_name, nodegroup)

        # Масштабування вниз з використанням оригінальної maxSize
        scale_down_nodegroup(eks_client, cluster_name, nodegroup, scaling_config)


# Основна функція для включення Node Groups
def enable_nodegroups(eks_client, ssm_client, cluster_name, excluded_nodegroups):
    nodegroups = get_active_nodegroups(eks_client, cluster_name, excluded_nodegroups)
    for nodegroup in nodegroups:
        scale_up_nodegroup(eks_client, ssm_client, cluster_name, nodegroup)


# Функція для обробки параметрів командного рядка
def parse_arguments():
    parser = argparse.ArgumentParser(description='Scale EKS Node Groups up or down and store config in SSM.')
    parser.add_argument('--cluster-name', required=True, help='EKS cluster name')
    parser.add_argument('--region', required=True, help='AWS region')
    parser.add_argument('--excluded-nodegroups', nargs='*', default=[], help='List of Node Groups to exclude')
    parser.add_argument('--action', choices=['disable', 'enable'], required=True,
                        help='Action to perform: disable or enable Node Groups')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_arguments()

    # Ініціалізація клієнтів
    eks_client, ssm_client = init_clients(args.region)

    if args.action == 'disable':
        disable_nodegroups(eks_client, ssm_client, args.cluster_name, args.excluded_nodegroups)
    elif args.action == 'enable':
        enable_nodegroups(eks_client, ssm_client, args.cluster_name, args.excluded_nodegroups)
