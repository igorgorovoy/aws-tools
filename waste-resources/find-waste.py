import os
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from datetime import datetime, timedelta

def get_regions(service_name):
    session = boto3.Session()
    #print(session.get_available_regions(service_name))
    return session.get_available_regions(service_name)


def find_idle_ec2_instances():
    """ Find underutilized or idle EC2 instances. """
    ec2_regions = ['eu-central-1']  # Test with one region
    idle_instances = []

    for region in ec2_regions:
        print("Start searching in region: " + region)
        try:
            ec2 = boto3.client('ec2', region_name=region)
            instances = ec2.describe_instances(
                Filters=[
                    {
                        'Name': 'instance-state-name',
                        'Values': ['running']
                    }
                ]
            )

            if not instances['Reservations']:
                print(f"No running instances found in region: {region}")
            else:
                for reservation in instances['Reservations']:
                    for instance in reservation['Instances']:
                        print(f"Instance {instance['InstanceId']} in region {region} found.")

        except ClientError as e:
            if e.response['Error']['Code'] == 'AuthFailure':
                print(f"AuthFailure in region {region}, skipping...")
            else:
                print(f"Error occurred in region {region}: {e}")

find_idle_ec2_instances()

def find_unused_rds_instances():
    """ Find underutilized or idle RDS instances. """
    rds_regions = get_regions('rds')
    idle_rds = []

    for region in rds_regions:
        print(f"Checking RDS instances in {region}")
        try:
            rds = boto3.client('rds', region_name=region)
            instances = rds.describe_db_instances()

            for instance in instances['DBInstances']:
                if instance['DBInstanceStatus'] == 'available':
                    cpu_stats = rds.get_metric_statistics(
                        Namespace='AWS/RDS',
                        MetricName='CPUUtilization',
                        Dimensions=[
                            {'Name': 'DBInstanceIdentifier', 'Value': instance['DBInstanceIdentifier']}
                        ],
                        StartTime=datetime.utcnow() - timedelta(days=7),
                        EndTime=datetime.utcnow(),
                        Period=3600,
                        Statistics=['Average']
                    )

                    if cpu_stats['Datapoints']:
                        avg_cpu = sum([data_point['Average'] for data_point in cpu_stats['Datapoints']]) / len(cpu_stats['Datapoints'])
                        if avg_cpu < 5:
                            idle_rds.append({'DBInstanceIdentifier': instance['DBInstanceIdentifier'], 'Region': region, 'CPU': avg_cpu})
                    else:
                        print(f"No CPU data found for {instance['DBInstanceIdentifier']} in {region}")

        except ClientError as e:
            print(f"Error checking RDS in {region}: {e}")
        except Exception as e:
            print(f"Unexpected error in {region}: {e}")

    return idle_rds

def find_idle_eks_clusters():
    """ Find underutilized or idle EKS clusters. """
    eks_regions = get_regions('eks')
    idle_eks = []

    for region in eks_regions:
        eks = boto3.client('eks', region_name=region)
        clusters = eks.list_clusters()

        for cluster in clusters['clusters']:
            nodegroups = eks.list_nodegroups(clusterName=cluster)
            if not nodegroups['nodegroups']:
                idle_eks.append({'ClusterName': cluster, 'Region': region})

    return idle_eks


def find_unused_lambda_functions():
    """ Find underutilized or idle Lambda functions. """
    lambda_regions = get_regions('lambda')
    idle_lambda = []

    for region in lambda_regions:
        lambda_client = boto3.client('lambda', region_name=region)
        functions = lambda_client.list_functions()

        for function in functions['Functions']:
            invocations = lambda_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Invocations',
                Dimensions=[
                    {
                        'Name': 'FunctionName',
                        'Value': function['FunctionName']
                    }
                ],
                StartTime=datetime.utcnow() - timedelta(days=7),
                EndTime=datetime.utcnow(),
                Period=3600,
                Statistics=['Sum']
            )

            total_invocations = sum([data_point['Sum'] for data_point in invocations['Datapoints']])
            if total_invocations == 0:
                idle_lambda.append({'FunctionName': function['FunctionName'], 'Region': region})

    return idle_lambda


def find_unused_elasticache_clusters():
    """ Find underutilized or idle ElastiCache clusters. """
    elasticache_regions = get_regions('elasticache')
    idle_elasticache = []

    for region in elasticache_regions:
        elasticache = boto3.client('elasticache', region_name=region)
        clusters = elasticache.describe_cache_clusters(ShowCacheNodeInfo=True)

        for cluster in clusters['CacheClusters']:
            if cluster['CacheClusterStatus'] == 'available':
                cpu_stats = elasticache.get_metric_statistics(
                    Namespace='AWS/ElastiCache',
                    MetricName='CPUUtilization',
                    Dimensions=[
                        {
                            'Name': 'CacheClusterId',
                            'Value': cluster['CacheClusterId']
                        }
                    ],
                    StartTime=datetime.utcnow() - timedelta(days=7),
                    EndTime=datetime.utcnow(),
                    Period=3600,
                    Statistics=['Average']
                )
                avg_cpu = sum([data_point['Average'] for data_point in cpu_stats['Datapoints']]) / len(
                    cpu_stats['Datapoints'])
                if avg_cpu < 5:
                    idle_elasticache.append(
                        {'CacheClusterId': cluster['CacheClusterId'], 'Region': region, 'CPU': avg_cpu})

    return idle_elasticache


def find_unused_ec2_snapshots():
    """ Find unused EC2 snapshots older than 30 days. """
    ec2_regions = get_regions('ec2')
    unused_snapshots = []
    cutoff_date = datetime.utcnow() - timedelta(days=30)

    for region in ec2_regions:
        ec2 = boto3.client('ec2', region_name=region)
        snapshots = ec2.describe_snapshots(OwnerIds=['self'])

        for snapshot in snapshots['Snapshots']:
            if snapshot['StartTime'] < cutoff_date:
                unused_snapshots.append(
                    {'SnapshotId': snapshot['SnapshotId'], 'Region': region, 'StartTime': snapshot['StartTime']})

    return unused_snapshots


def find_unused_rds_snapshots():
    """ Find unused RDS snapshots older than 30 days. """
    rds_regions = get_regions('rds')
    unused_snapshots = []
    cutoff_date = datetime.utcnow() - timedelta(days=30)

    for region in rds_regions:
        rds = boto3.client('rds', region_name=region)
        snapshots = rds.describe_db_snapshots(SnapshotType='manual')

        for snapshot in snapshots['DBSnapshots']:
            if snapshot['SnapshotCreateTime'] < cutoff_date:
                unused_snapshots.append({'DBSnapshotIdentifier': snapshot['DBSnapshotIdentifier'], 'Region': region,
                                         'SnapshotCreateTime': snapshot['SnapshotCreateTime']})

    return unused_snapshots


def find_unused_elasticache_snapshots():
    """ Find unused ElastiCache snapshots older than 30 days. """
    elasticache_regions = get_regions('elasticache')
    unused_snapshots = []
    cutoff_date = datetime.utcnow() - timedelta(days=30)

    for region in elasticache_regions:
        elasticache = boto3.client('elasticache', region_name=region)
        snapshots = elasticache.describe_snapshots()

        for snapshot in snapshots['Snapshots']:
            if snapshot['SnapshotCreateTime'] < cutoff_date:
                unused_snapshots.append({'SnapshotName': snapshot['SnapshotName'], 'Region': region,
                                         'SnapshotCreateTime': snapshot['SnapshotCreateTime']})

    return unused_snapshots


if __name__ == "__main__":
    try:
        print("Finding idle EC2 instances...")
        idle_ec2_instances = find_idle_ec2_instances()
        print(f"Idle EC2 instances: {idle_ec2_instances}")

        print("Finding unused RDS instances...")
        unused_rds_instances = find_unused_rds_instances()
        print(f"Unused RDS instances: {unused_rds_instances}")

        print("Finding idle EKS clusters...")
        idle_eks_clusters = find_idle_eks_clusters()
        print(f"Idle EKS clusters: {idle_eks_clusters}")

        print("Finding unused Lambda functions...")
        unused_lambda_functions = find_unused_lambda_functions()
        print(f"Unused Lambda functions: {unused_lambda_functions}")

        print("Finding idle ElastiCache clusters...")
        idle_elasticache_clusters = find_unused_elasticache_clusters()
        print(f"Idle ElastiCache clusters: {idle_elasticache_clusters}")

        print("Finding unused EC2 snapshots...")
        unused_ec2_snapshots = find_unused_ec2_snapshots()
        print(f"Unused EC2 snapshots: {unused_ec2_snapshots}")

        print("Finding unused RDS snapshots...")
        unused_rds_snapshots = find_unused_rds_snapshots()
        print(f"Unused RDS snapshots: {unused_rds_snapshots}")

        print("Finding unused ElastiCache snapshots...")
        unused_elasticache_snapshots = find_unused_elasticache_snapshots()
        print(f"Unused ElastiCache snapshots: {unused_elasticache_snapshots}")

    except NoCredentialsError:
        print("Credentials not available.")
    except ClientError as e:
        print(f"Error occurred: {e}")
