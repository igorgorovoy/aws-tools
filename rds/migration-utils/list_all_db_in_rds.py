import psycopg2
from psycopg2 import sql


def get_rds_databases(host, port, user, password):
    """
    Connects to an RDS PostgreSQL instance and retrieves a list of all databases
    excluding the template databases.

    Args:
        host (str): The RDS endpoint (host address).
        port (int): The port number for PostgreSQL.
        user (str): The username for the database connection.
        password (str): The password for the database connection.

    Returns:
        None
    """
    try:
        # Connect to the PostgreSQL RDS instance
        connection = psycopg2.connect(
            dbname='postgres',  # Connecting to the default 'postgres' database
            user=user,
            password=password,
            host=host,
            port=port
        )

        # Create a cursor object
        cursor = connection.cursor()

        # Execute the SQL query to list all databases ordered by name
        cursor.execute(sql.SQL("SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;"))

        # Fetch all results from the executed query
        databases = cursor.fetchall()

        # Print the list of databases
        print("List of databases:")
        for db in databases:
            print(f"- {db[0]}")

        # Close the cursor and connection
        cursor.close()
        connection.close()

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == '__main__':
    # RDS connection details
    rds_host = 'athena-devrds.cr***********zo.eu-central-1.rds.amazonaws.com'
    rds_port = 5432
    rds_user = 'devrds'
    rds_password = 'xxx'

    # Call the function to get the list of databases
    get_rds_databases(rds_host, rds_port, rds_user, rds_password)
