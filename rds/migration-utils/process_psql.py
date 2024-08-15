import subprocess
import time
from urllib.parse import urlparse, parse_qs


def read_mapping_file(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()

    mappings = [line.strip().split('@@') for line in lines if line.strip()]
    return mappings


def parse_db_url(db_url):
    parsed_url = urlparse(db_url)
    username = parsed_url.username
    password = parsed_url.password
    host = parsed_url.hostname
    port = parsed_url.port
    dbname = parsed_url.path.lstrip('/')
    query_params = parse_qs(parsed_url.query)

    return {
        "user": username,
        "password": password,
        "host": host,
        "port": str(port),
        "dbname": dbname,
        "options": query_params
    }


def export_database(config, dump_file):
    print(f"Starting database export for {config['dbname']}...")
    start_time = time.time()

    dump_command = [
        "/usr/bin/pg_dump",
        "-h", config['host'],
        "-p", config['port'],
        "-U", config['user'],
        "-d", config['dbname'],
        #"-F", "c",
        "--verbose",
        "--no-privileges",
        "--no-owner",
        "-f", dump_file
    ]

    env = {"PGPASSWORD": config['password']}

    try:
        subprocess.run(dump_command, check=True, env=env)
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Database exported to {dump_file} in {elapsed_time:.2f} seconds.")
    except subprocess.CalledProcessError as e:
        print("Error exporting database:", e)


def import_database(config, dump_file):
    print(f"Starting database import for {config['dbname']}...")
    start_time = time.time()

    import_command = [
        "/usr/bin/psql",
        "-h", config['host'],
        "-p", config['port'],
        "-U", config['user'],
        "-d", config['dbname'],
        "-f",
        dump_file
    ]

    env = {"PGPASSWORD": config['password']}

    try:
        subprocess.run(import_command, check=True, env=env)
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Database imported from {dump_file} in {elapsed_time:.2f} seconds.")
    except subprocess.CalledProcessError as e:
        print("Error importing database:", e)


def process_mappings(file_path):
    mappings = read_mapping_file(file_path)

    total_start_time = time.time()
    for old_db_url, new_db_url in mappings:

        old_db_config = parse_db_url(old_db_url)
        new_db_config = parse_db_url(new_db_url)

        print(f"Processing mapping: {new_db_config['dbname']}")
        dump_file = f"{old_db_config['dbname']}.dump"

        export_database(old_db_config, dump_file)
        import_database(new_db_config, dump_file)

    total_end_time = time.time()
    total_elapsed_time = total_end_time - total_start_time
    print(f"Total process completed in {total_elapsed_time:.2f} seconds.")


#mapping_file_path = "db_mapping_core.txt"
#process_mappings(mapping_file_path)
#mapping_file_path = "db_mapping_pay.txt"
#process_mappings(mapping_file_path)
#mapping_file_path = "db_mapping_pro.txt"
#process_mappings(mapping_file_path)
#mapping_file_path = "db_mapping_pp.txt"
#process_mappings(mapping_file_path)
mapping_file_path = "db_mapping_saas.txt"
process_mappings(mapping_file_path)