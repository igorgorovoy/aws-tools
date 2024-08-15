import boto3
import time

# Configuration
source_region = 'eu-central-1'  # Source region
target_region = 'eu-west-1'  # Target region
# Commented out as we will save and use the original DB instance class
# db_instance_class = 'db.t4g.small'
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

# Record the total start time
total_start_time = time.time()

# Define an exclude list for instance identifiers
exclude_list = ['instance-id-1', 'instance-id-2']  # Add your specific instance IDs to exclude

# Step 1: List RDS instances in the source region
print(f"Listing RDS instances in source region: {source_region}")
response = rds_client_source.describe_db_instances()
db_instances = response['DBInstances']

if not db_instances:
    print("No RDS instances found in the source region.")
else:
    print(f"Found {len(db_instances)} RDS instances.")

    # List to store original DB instance configurations
    original_instance_configs = []

    for db_instance in db_instances:
        # Extract information about the DB instance
        db_instance_identifier = db_instance['DBInstanceIdentifier']

        # Check if the instance is in the exclude list
        if db_instance_identifier in exclude_list:
            print(f"Skipping excluded RDS instance: {db_instance_identifier}")
            continue  # Skip the excluded instance and move to the next one

        # Start time for the migration process of the current instance
        instance_start_time = time.time()

        # Save instance class, storage type, engine, and allocated storage
        db_instance_class = db_instance['DBInstanceClass']
        storage_type = db_instance.get('StorageType', 'Not specified')
        engine = db_instance['Engine']
        allocated_storage = db_instance['AllocatedStorage']

        # Save the instance details to the list
        original_instance_configs.append({
            'DBInstanceIdentifier': db_instance_identifier,
            'DBInstanceClass': db_instance_class,
            'StorageType': storage_type,
            'Engine': engine,
            'AllocatedStorage': allocated_storage
        })

        # Print instance configuration for logging or auditing purposes
        print(f"Processing RDS Instance: {db_instance_identifier}")
        print(f" - Instance Class: {db_instance_class}")
        print(f" - Storage Type: {storage_type}")
        print(f" - Engine: {engine}")
        print(f" - Allocated Storage: {allocated_storage} GiB")

        snapshot_identifier = f"{db_instance_identifier}-snapshot-{int(time.time())}"
        target_db_instance_identifier = f"{db_instance_identifier}-migrated"

        # Step 2: Create a snapshot of each RDS instance
        print(f"\nCreating snapshot for RDS instance: {db_instance_identifier}")
        snapshot_start_time = time.time()

        response_snapshot = rds_client_source.create_db_snapshot(
            DBSnapshotIdentifier=snapshot_identifier,
            DBInstanceIdentifier=db_instance_identifier
        )

        # Wait for the snapshot to be available
        print("Waiting for snapshot to be available...")
        snapshot_waiter = rds_client_source.get_waiter('db_snapshot_available')
        snapshot_waiter.wait(
            DBSnapshotIdentifier=snapshot_identifier
        )

        snapshot_end_time = time.time()
        snapshot_duration = snapshot_end_time - snapshot_start_time
        print(
            f"Snapshot {snapshot_identifier} is now available for {db_instance_identifier}. Time taken: {snapshot_duration:.2f} seconds.")

        # Step 3: Copy the snapshot to the target region
        print(f"Copying snapshot to the target region: {target_region}")
        copy_start_time = time.time()

        # Check if the snapshot is encrypted
        snapshot_details = rds_client_source.describe_db_snapshots(
            DBSnapshotIdentifier=snapshot_identifier
        )['DBSnapshots'][0]

        encrypted = snapshot_details['Encrypted']

        # Prepare the copy snapshot request parameters
        copy_params = {
            'SourceDBSnapshotIdentifier': f"arn:aws:rds:{source_region}:{account_id}:snapshot:{snapshot_identifier}",
            'TargetDBSnapshotIdentifier': snapshot_identifier,
            'SourceRegion': source_region
        }

        # Add the KMS key if the snapshot is encrypted
        if encrypted:
            copy_params['KmsKeyId'] = kms_key_id
            print(f"Snapshot is encrypted. Using KMS key: {kms_key_id}")

        response_copy = rds_client_target.copy_db_snapshot(**copy_params)

        # Wait for the snapshot to be available in the target region
        print("Waiting for the snapshot to be available in the target region...")
        copy_waiter = rds_client_target.get_waiter('db_snapshot_completed')

        # Use a custom configuration for the waiter
        max_attempts = 60  # Increase maximum number of attempts (default is 40)
        delay = 30  # Increase delay between attempts in seconds (default is 15)

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
            continue  # Skip to the next instance or handle the error as needed

        copy_end_time = time.time()
        copy_duration = copy_end_time - copy_start_time
        print(
            f"Snapshot {snapshot_identifier} copied successfully to {target_region} for {db_instance_identifier}. Time taken: {copy_duration:.2f} seconds.")

        # Step 4: Restore the DB instance from the snapshot in the target region
        print(f"Restoring DB instance from snapshot {snapshot_identifier} in {target_region}")
        restore_start_time = time.time()

        # Prepare the restore request parameters
        restore_params = {
            'DBInstanceIdentifier': target_db_instance_identifier,
            'DBSnapshotIdentifier': snapshot_identifier,
            'DBInstanceClass': db_instance_class,  # Use the original instance class
            'DBSubnetGroupName': db_subnet_group_name,  # Use the specified DB subnet group
            'MultiAZ': multi_az,
            'PubliclyAccessible': publicly_accessible
        }

        # Include AvailabilityZone only if MultiAZ is False
        if not multi_az:
            restore_params['AvailabilityZone'] = availability_zone

        response_restore = rds_client_target.restore_db_instance_from_db_snapshot(**restore_params)

        # Wait for the new DB instance to be available
        print("Waiting for the new DB instance to be available...")
        instance_waiter = rds_client_target.get_waiter('db_instance_available')
        instance_waiter.wait(
            DBInstanceIdentifier=target_db_instance_identifier
        )

        restore_end_time = time.time()
        restore_duration = restore_end_time - restore_start_time
        print(
            f"DB instance {target_db_instance_identifier} is now available in {target_region}. Time taken: {restore_duration:.2f} seconds.")

        # End time for the migration process of the current instance
        instance_end_time = time.time()
        instance_duration = instance_end_time - instance_start_time
        print(f"Migration of {db_instance_identifier} completed. Total time taken: {instance_duration:.2f} seconds.\n")

    # Print all original instance configurations
    print("\nOriginal RDS Instance Configurations:")
    for config in original_instance_configs:
        print(f"Instance Identifier: {config['DBInstanceIdentifier']}")
        print(f" - Instance Class: {config['DBInstanceClass']}")
        print(f" - Storage Type: {config['StorageType']}")
        print(f" - Engine: {config['Engine']}")
        print(f" - Allocated Storage: {config['AllocatedStorage']} GiB")
        print("")

# Record the total end time
total_end_time = time.time()
total_duration = total_end_time - total_start_time
print(f"All RDS instances have been processed for migration. Total time taken: {total_duration:.2f} seconds.")