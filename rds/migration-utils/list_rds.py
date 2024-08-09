import boto3

def list_rds_endpoints(region_name='eu-central-1'):
    session = boto3.Session(region_name=region_name)
    rds_client = session.client('rds')

    try:
        response = rds_client.describe_db_instances()
        db_instances = response['DBInstances']

        for db_instance in db_instances:
            endpoint = db_instance.get('Endpoint', {})
            endpoint_address = endpoint.get('Address')
            db_identifier = db_instance.get('DBInstanceIdentifier')
            db_engine = db_instance.get('Engine')
            db_status = db_instance.get('DBInstanceStatus')
            db_class = db_instance.get('DBInstanceClass')
            availability_zone = db_instance.get('AvailabilityZone')

            print(f"DB Instance Identifier: {db_identifier}")
            print(f"Endpoint Address: {endpoint_address}")
            print(f"Engine: {db_engine}")
            print(f"Status: {db_status}")
            print(f"Instance Class: {db_class}")
            print(f"Availability Zone: {availability_zone}")
            print("-" * 40)

    except Exception as e:
        print("An error occurred while fetching RDS instances:", str(e))

list_rds_endpoints()
