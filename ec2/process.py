import boto3
from concurrent.futures import ThreadPoolExecutor
from time import sleep

# Configure source and destination regions
SOURCE_REGION = 'eu-central-1'
DESTINATION_REGION = 'eu-north-1'

# Initialize Boto3 clients for both regions
source_ec2 = boto3.client('ec2', region_name=SOURCE_REGION)
destination_ec2 = boto3.client('ec2', region_name=DESTINATION_REGION)

# List of instance IDs to migrate
INSTANCE_IDS_TO_MIGRATE = [
    'i-0f655bd83bd781b09',
    'i-09722b6eda50d6423',
    'i-033b661ddab1fd1bd',
    'i-0386b00c68e3cb008',
    'i-0413186a7c5a98249',
    'i-0b51e80a3aed8b2f3',
    'i-0cd77cfb615c32cb7',
    'i-04051cd553334ba30',
    'i-0c3244c33dccd2e5b',
    'i-0810ab9036e010310',
    'i-051b2779f4549849d',
    'i-059a229c4c8dc8e94',
    'i-036c0dfea02cf95e2',
    'i-027f922e837fb4304',
]


def create_ami(instance_id):
    """Create an AMI from an EC2 instance."""
    response = source_ec2.create_image(
        InstanceId=instance_id,
        Name=f'Migration-{instance_id}',
        NoReboot=True
    )
    ami_id = response['ImageId']
    print(f'Created AMI {ami_id} from instance {instance_id}')
    return ami_id


def wait_for_ami(ami_id):
    """Wait for the AMI to become available."""
    print(f'Waiting for AMI {ami_id} to become available...')
    waiter = source_ec2.get_waiter('image_available')
    waiter.wait(ImageIds=[ami_id])
    print(f'AMI {ami_id} is now available.')


def copy_security_groups(security_group_ids):
    """Copy security groups from source to destination region."""
    copied_security_group_ids = []
    for sg_id in security_group_ids:
        sg = source_ec2.describe_security_groups(GroupIds=[sg_id])['SecurityGroups'][0]

        # Check if the security group already exists in the destination region
        existing_sg = destination_ec2.describe_security_groups(
            Filters=[{'Name': 'group-name', 'Values': [sg['GroupName']]}]
        )['SecurityGroups']

        if existing_sg:
            new_sg_id = existing_sg[0]['GroupId']
            print(f'Security group {sg["GroupName"]} already exists as {new_sg_id}')
        else:
            response = destination_ec2.create_security_group(
                GroupName=sg['GroupName'],
                Description=sg['Description'],
                VpcId=sg['VpcId'] if 'VpcId' in sg else None
            )
            new_sg_id = response['GroupId']
            print(f'Copied security group {sg_id} to {new_sg_id}')

        # Copy security group rules
        for permission in sg['IpPermissions']:
            try:
                destination_ec2.authorize_security_group_ingress(
                    GroupId=new_sg_id,
                    IpPermissions=[permission]
                )
            except Exception as e:
                print(f'Error copying rules for security group {new_sg_id}: {e}')

        copied_security_group_ids.append(new_sg_id)
    return copied_security_group_ids


def copy_ami(ami_id):
    """Copy an AMI to the destination region."""
    response = destination_ec2.copy_image(
        Name=f'Migration-{ami_id}',
        SourceImageId=ami_id,
        SourceRegion=SOURCE_REGION
    )
    copied_ami_id = response['ImageId']
    print(f'Copied AMI {ami_id} to destination region as {copied_ami_id}')
    return copied_ami_id


def wait_for_copied_ami(copied_ami_id):
    """Wait for the copied AMI to become available."""
    print(f'Waiting for copied AMI {copied_ami_id} to become available...')
    waiter = destination_ec2.get_waiter('image_available')
    waiter.wait(ImageIds=[copied_ami_id])
    print(f'Copied AMI {copied_ami_id} is now available.')


def launch_instance(instance_data, ami_id, security_group_ids):
    """Launch an EC2 instance from an AMI in the destination region."""
    # Extract block device mappings, excluding any ephemeral storage
    block_device_mappings = [
        mapping for mapping in instance_data['BlockDeviceMappings'] if 'Ebs' in mapping
    ]

    response = destination_ec2.run_instances(
        ImageId=ami_id,
        InstanceType=instance_data['InstanceType'],
        KeyName=instance_data.get('KeyName', None),
        SecurityGroupIds=security_group_ids,
        SubnetId=instance_data.get('SubnetId', None),
        IamInstanceProfile=instance_data.get('IamInstanceProfile', None),
        MinCount=1,
        MaxCount=1,
        BlockDeviceMappings=block_device_mappings,
        Monitoring={'Enabled': instance_data['Monitoring']['State'] == 'enabled'},
        EbsOptimized=instance_data.get('EbsOptimized', False)
    )
    new_instance_id = response['Instances'][0]['InstanceId']
    print(f'Launched new instance {new_instance_id} in destination region')
    return new_instance_id


def copy_tags(instance_id, new_instance_id):
    """Copy tags from the source instance to the destination instance."""
    tags = source_ec2.describe_tags(
        Filters=[{'Name': 'resource-id', 'Values': [instance_id]}]
    )['Tags']
    if tags:
        destination_ec2.create_tags(Resources=[new_instance_id], Tags=tags)
        print(f'Copied tags from {instance_id} to {new_instance_id}')


def migrate_instance(instance_id):
    """Migrate an EC2 instance from source to destination region."""
    try:
        # Describe the instance to get all parameters
        instance_info = source_ec2.describe_instances(InstanceIds=[instance_id])
        instance_data = instance_info['Reservations'][0]['Instances'][0]

        # Create an AMI
        ami_id = create_ami(instance_id)
        wait_for_ami(ami_id)

        # Copy the AMI to the destination region
        copied_ami_id = copy_ami(ami_id)
        wait_for_copied_ami(copied_ami_id)

        # Copy security groups
        security_group_ids = instance_data['SecurityGroups']
        security_group_ids = [sg['GroupId'] for sg in security_group_ids]
        copied_security_group_ids = copy_security_groups(security_group_ids)

        # Launch the new instance
        new_instance_id = launch_instance(instance_data, copied_ami_id, copied_security_group_ids)

        # Copy tags
        copy_tags(instance_id, new_instance_id)

    except Exception as e:
        print(f'Error migrating instance {instance_id}: {e}')


def main():
    # Use ThreadPoolExecutor to migrate instances in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(migrate_instance, INSTANCE_IDS_TO_MIGRATE)


if __name__ == '__main__':
    main()
