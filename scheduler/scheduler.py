import boto3
from botocore.exceptions import ClientError

# Ініціалізуємо клієнти для Auto Scaling та RDS
autoscaling_client = boto3.client('autoscaling')
ec2_client = boto3.client('ec2')
rds_client = boto3.client('rds')

def get_all_auto_scaling_groups():
    """Отримує всі Auto Scaling групи."""
    groups = []
    paginator = autoscaling_client.get_paginator('describe_auto_scaling_groups')
    for page in paginator.paginate():
        groups.extend(page['AutoScalingGroups'])
    return groups

def get_all_rds_instances():
    """Отримує всі RDS інстанси."""
    instances = []
    paginator = rds_client.get_paginator('describe_db_instances')
    for page in paginator.paginate():
        instances.extend(page['DBInstances'])
    return instances

def suspend_auto_scaling_instances(group):
    """Зупиняє всі інстанси в Auto Scaling групі."""
    instance_ids = [instance['InstanceId'] for instance in group['Instances']]
    if instance_ids:
        ec2_client.stop_instances(InstanceIds=instance_ids)
        print(f"Інстанси {instance_ids} у групі {group['AutoScalingGroupName']} зупинено.")
    else:
        print(f"У групі {group['AutoScalingGroupName']} немає активних інстансів для зупинки.")

def stop_rds_instance(instance):
    """Зупиняє RDS інстанс."""
    try:
        rds_client.stop_db_instance(DBInstanceIdentifier=instance['DBInstanceIdentifier'])
        print(f"RDS інстанс {instance['DBInstanceIdentifier']} зупинено.")
    except ClientError as e:
        print(f"Не вдалося зупинити RDS інстанс {instance['DBInstanceIdentifier']}: {e}")

def manage_auto_scaling_groups(excluded_groups):
    """Призупиняє всі Auto Scaling групи, окрім тих, що у виключеннях."""
    groups = get_all_auto_scaling_groups()
    print(groups)
    for group in groups:
        if group['AutoScalingGroupName'] not in excluded_groups:
            print(f"Призупиняємо інстанси для групи {group['AutoScalingGroupName']}...")
            #suspend_auto_scaling_instances(group)
        else:
            print(f"Група {group['AutoScalingGroupName']} у виключеннях, пропускаємо.")

def manage_rds_instances(excluded_instances):
    """Зупиняє всі RDS інстанси, окрім тих, що у виключеннях."""
    instances = get_all_rds_instances()
    print(instances)
    for instance in instances:
        if instance['DBInstanceIdentifier'] not in excluded_instances:
            print(f"Зупиняємо RDS інстанс {instance['DBInstanceIdentifier']}...")
            #stop_rds_instance(instance)
        else:
            print(f"RDS інстанс {instance['DBInstanceIdentifier']} у виключеннях, пропускаємо.")

if __name__ == '__main__':
    # Список виключених Auto Scaling груп та RDS інстансів
    excluded_auto_scaling_groups = ['GROUP_NAME_1', 'GROUP_NAME_2']
    excluded_rds_instances = ['RDS_INSTANCE_1', 'RDS_INSTANCE_2']

    # Призупинення Auto Scaling груп (окрім виключених)
    manage_auto_scaling_groups(excluded_auto_scaling_groups)

    # Зупинка RDS інстансів (окрім виключених)
    manage_rds_instances(excluded_rds_instances)
