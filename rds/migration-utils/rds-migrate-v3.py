import boto3
import time
import concurrent.futures
import botocore.exceptions

# Configuration
source_region = 'eu-central-1'  # Source region
target_region = 'eu-west-1'  # Target region
availability_zone = f'{target_region}a'  # Availability zone in the target region
multi_az = True  # Set to True for Multi-AZ deployment
publicly_accessible = True  # Set to False if the instance should not be publicly accessible

# Specify your KMS key ID in the target region (required for encrypted snapshots)
kms_key_id = '18d3258d-89df-4690-82a1-f2da9ba78ccb'  # Ireland
db_subnet_group_name = 'kuna-dev-vpc-blue'  # Your specific DB subnet group name

# Create a client for the source region
rds_client_source = boto3.client('rds', region_name=source_region)

# Create a client for the target region
rds_client_target = boto3.client('rds', region_name=target_region)

# Get the account ID for ARN generation
account_id = boto3.client('sts').get_caller_identity().get('Account')

# Define an exclude list for instance identifiers
exclude_list = ['instance-id-1', 'instance-id-2']  # Add your specific instance IDs to exclude

# Record the total start time
total_start_time = time.time()

def migrate_rds_instance(db_instance):
    try:
        db_instance_identifier = db_instance['DBInstanceIdentifier']

        if db_instance_identifier in exclude_list:
            print(f"Skipping excluded RDS instance: {db_instance_identifier}")
            return

        instance_start_time = time.time()

        db_instance_class = db_instance['DBInstanceClass']
        storage_type = db_instance.get('StorageType', 'Not specified')
        engine = db_instance['Engine']
        allocated_storage = db_instance['AllocatedStorage']

        print(f"Processing RDS Instance: {db_instance_identifier}")
        print(f" - Instance Class: {db_instance_class}")
        print(f" - Storage Type: {storage_type}")
        print(f" - Engine: {engine}")
        print(f" - Allocated Storage: {allocated_storage} GiB")

        snapshot_identifier = f"{db_instance_identifier}-snapshot-{int(time.time())}"
        target_db_instance_identifier = f"{db_instance_identifier}-migrated"

        print(f"\nCreating snapshot for RDS instance: {db_instance_identifier}")
        snapshot_start_time = time.time()

        response_snapshot = rds_client_source.create_db_snapshot(
            DBSnapshotIdentifier=snapshot_identifier,
            DBInstanceIdentifier=db_instance_identifier
        )

        print("Waiting for snapshot to be available...")
        snapshot_waiter = rds_client_source.get_waiter('db_snapshot_available')
        snapshot_waiter.wait(
            DBSnapshotIdentifier=snapshot_identifier
        )

        snapshot_end_time = time.time()
        snapshot_duration = snapshot_end_time - snapshot_start_time
        print(f"Snapshot {snapshot_identifier} is now available for {db_instance_identifier}. Time taken: {snapshot_duration:.2f} seconds.")

        print(f"Copying snapshot to the target region: {target_region}")
        copy_start_time = time.time()

        snapshot_details = rds_client_source.describe_db_snapshots(
            DBSnapshotIdentifier=snapshot_identifier
        )['DBSnapshots'][0]

        encrypted = snapshot_details['Encrypted']

        copy_params = {
            'SourceDBSnapshotIdentifier': f"arn:aws:rds:{source_region}:{account_id}:snapshot:{snapshot_identifier}",
            'TargetDBSnapshotIdentifier': snapshot_identifier,
            'SourceRegion': source_region
        }

        if encrypted:
            copy_params['KmsKeyId'] = kms_key_id
            print(f"Snapshot is encrypted. Using KMS key: {kms_key_id}")

        response_copy = rds_client_target.copy_db_snapshot(**copy_params)

        print("Waiting for the snapshot to be available in the target region...")
        copy_waiter = rds_client_target.get_waiter('db_snapshot_completed')

        max_attempts = 60
        delay = 30

        try:
            copy_waiter.wait(
                DBSnapshotIdentifier=snapshot_identifier,
                WaiterConfig={
                    'Delay': delay,
                    'MaxAttempts': max_attempts
                }
            )
        except botocore.exceptions.WaiterError as e:
            print(f"Error waiting for snapshot copy: {e}")
            return

        copy_end_time = time.time()
        copy_duration = copy_end_time - copy_start_time
        print(f"Snapshot {snapshot_identifier} copied successfully to {target_region} for {db_instance_identifier}. Time taken: {copy_duration:.2f} seconds.")

        print(f"Restoring DB instance from snapshot {snapshot_identifier} in {target_region}")
        restore_start_time = time.time()

        restore_params = {
            'DBInstanceIdentifier': target_db_instance_identifier,
            'DBSnapshotIdentifier': snapshot_identifier,
            'DBInstanceClass': db_instance_class,
            'DBSubnetGroupName': db_subnet_group_name,
            'MultiAZ': multi_az,
            'PubliclyAccessible': publicly_accessible
        }

        if not multi_az:
            restore_params['AvailabilityZone'] = availability_zone

        response_restore = rds_client_target.restore_db_instance_from_db_snapshot(**restore_params)

        print("Waiting for the new DB instance to be available...")
        instance_waiter = rds_client_target.get_waiter('db_instance_available')
        instance_waiter.wait(
            DBInstanceIdentifier=target_db_instance_identifier
        )

        restore_end_time = time.time()
        restore_duration = restore_end_time - restore_start_time
        print(f"DB instance {target_db_instance_identifier} is now available in {target_region}. Time taken: {restore_duration:.2f} seconds.")

        instance_end_time = time.time()
        instance_duration = instance_end_time - instance_start_time
        print(f"Migration of {db_instance_identifier} completed. Total time taken: {instance_duration:.2f} seconds.\n")

    except Exception as e:
        print(f"Error migrating instance {db_instance['DBInstanceIdentifier']}: {e}")

def main():
    response = rds_client_source.describe_db_instances()
    db_instances = response['DBInstances']

    if not db_instances:
        print("No RDS instances found in the source region.")
        return

    print(f"Found {len(db_instances)} RDS instances.")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(migrate_rds_instance, db_instances)

    total_end_time = time.time()
    total_duration = total_end_time - total_start_time
    print(f"All RDS instances have been processed for migration. Total time taken: {total_duration:.2f} seconds.")

if __name__ == '__main__':
    main()
