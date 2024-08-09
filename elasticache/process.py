import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed

# AWS Regions
source_region = 'eu-central-1'  # Source region
target_region = 'eu-north-1'  # Target region

# Elasticache Cluster Details
elasticache_clusters = ['my-cluster1', 'my-cluster2']  # Add your cluster names here
snapshot_prefix = 'snapshot-'

# Boto3 Clients
source_client = boto3.client('elasticache', region_name=source_region)
target_client = boto3.client('elasticache', region_name=target_region)

def fetch_cluster_configuration(cluster_id):
    """
    Fetch the configuration of the specified Elasticache cluster.
    """
    try:
        response = source_client.describe_cache_clusters(
            CacheClusterId=cluster_id,
            ShowCacheNodeInfo=True
        )
        cluster = response['CacheClusters'][0]
        return {
            'Engine': cluster['Engine'],
            'CacheNodeType': cluster['CacheNodeType'],
            'NumCacheNodes': cluster['NumCacheNodes'],
            'CacheParameterGroupName': cluster['CacheParameterGroup']['CacheParameterGroupName'],
            'SecurityGroupIds': [sg['SecurityGroupId'] for sg in cluster.get('SecurityGroups', [])],
            'SubnetGroupName': cluster.get('CacheSubnetGroupName'),
            'EngineVersion': cluster['EngineVersion'],
            'PreferredMaintenanceWindow': cluster['PreferredMaintenanceWindow'],
            'SnapshotRetentionLimit': cluster.get('SnapshotRetentionLimit', 1),
            'AutomaticFailoverEnabled': cluster.get('AutomaticFailover', False)
        }
    except Exception as e:
        print(f"Error fetching configuration for {cluster_id}: {e}")
        return None

def create_snapshot(cluster_id):
    """
    Create a snapshot for the specified Elasticache cluster.
    """
    snapshot_name = f"{snapshot_prefix}{cluster_id}"
    try:
        response = source_client.create_snapshot(
            CacheClusterId=cluster_id,
            SnapshotName=snapshot_name
        )
        return snapshot_name, response['Snapshot']['SnapshotStatus']
    except Exception as e:
        print(f"Error creating snapshot for {cluster_id}: {e}")
        return None, None

def copy_snapshot(snapshot_name):
    """
    Copy the snapshot to the target region.
    """
    try:
        target_snapshot_name = f"{snapshot_name}-copy"
        response = source_client.copy_snapshot(
            SourceSnapshotName=snapshot_name,
            TargetSnapshotName=target_snapshot_name,
            SourceRegion=source_region
        )
        return target_snapshot_name, response['Snapshot']['SnapshotStatus']
    except Exception as e:
        print(f"Error copying snapshot {snapshot_name}: {e}")
        return None, None

def restore_from_snapshot(cluster_id, snapshot_name, config):
    """
    Restore a new Elasticache cluster from the specified snapshot using the provided configuration.
    """
    try:
        response = target_client.create_cache_cluster(
            CacheClusterId=cluster_id,
            SnapshotName=snapshot_name,
            Engine=config['Engine'],
            CacheNodeType=config['CacheNodeType'],
            NumCacheNodes=config['NumCacheNodes'],
            CacheParameterGroupName=config['CacheParameterGroupName'],
            SecurityGroupIds=config['SecurityGroupIds'],
            SubnetGroupName=config['SubnetGroupName'],
            EngineVersion=config['EngineVersion'],
            PreferredMaintenanceWindow=config['PreferredMaintenanceWindow'],
            SnapshotRetentionLimit=config['SnapshotRetentionLimit'],
            AutomaticFailoverEnabled=config['AutomaticFailoverEnabled']
        )
        return response['CacheCluster']['CacheClusterStatus']
    except Exception as e:
        print(f"Error restoring from snapshot {snapshot_name}: {e}")
        return None

# Step 1: Fetch Cluster Configurations
cluster_configurations = {}
for cluster in elasticache_clusters:
    config = fetch_cluster_configuration(cluster)
    if config:
        cluster_configurations[cluster] = config
    else:
        print(f"Failed to fetch configuration for cluster: {cluster}")

# Debugging: Print the cluster configurations fetched
print("Fetched Cluster Configurations:")
for cluster_id, config in cluster_configurations.items():
    print(f"{cluster_id}: {config}")

# Step 2: Create Snapshots
with ThreadPoolExecutor(max_workers=5) as executor:
    future_to_snapshot = {executor.submit(create_snapshot, cluster): cluster for cluster in elasticache_clusters}
    for future in as_completed(future_to_snapshot):
        cluster = future_to_snapshot[future]
        try:
            snapshot_name, status = future.result()
            print(f"Snapshot {snapshot_name} for {cluster} status: {status}")
        except Exception as e:
            print(f"Error creating snapshot for {cluster}: {e}")

# Step 3: Copy Snapshots
with ThreadPoolExecutor(max_workers=5) as executor:
    future_to_copy = {executor.submit(copy_snapshot, f"{snapshot_prefix}{cluster}"): cluster for cluster in elasticache_clusters}
    for future in as_completed(future_to_copy):
        cluster = future_to_copy[future]
        try:
            target_snapshot_name, status = future.result()
            print(f"Copied Snapshot {target_snapshot_name} for {cluster} status: {status}")
        except Exception as e:
            print(f"Error copying snapshot for {cluster}: {e}")

# Step 4: Restore from Snapshots
with ThreadPoolExecutor(max_workers=5) as executor:
    future_to_restore = {
        executor.submit(
            restore_from_snapshot, cluster, f"{snapshot_prefix}{cluster}-copy", cluster_configurations.get(cluster, {})
        ): cluster for cluster in elasticache_clusters if cluster in cluster_configurations
    }
    for future in as_completed(future_to_restore):
        cluster = future_to_restore[future]
        try:
            status = future.result()
            print(f"Restored {cluster} status: {status}")
        except Exception as e:
            print(f"Error restoring cluster {cluster}: {e}")