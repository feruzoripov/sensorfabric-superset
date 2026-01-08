from urllib.parse import quote_plus
from sensorfabric.mdh import MDH
from sensorfabric import utils
import re
import os
from datetime import datetime, timezone
import base64

# Will store global keys for connecting directly with MDH Data Explorer.
MDH_dataExplorer = {
    'AccessKeyId': '',
    'SecretAccessKey': '',
    'SessionToken':'',
    'Expiration':'',
    'region':'us-east-1',
    'catalog':'AwsDataCatalog',
    'schema_name':'',
    'workgroup': 'mdh_export_database_external_prod',
    's3_output': ''
}

# Holds details about MDH service account credentials.
secret_key = None
service_account = None
project_id = None

def getExplorerCredentials(secret_key, service_account, project_id):
    """
    Get the temporary AWS explorer credentials from AWS.
    These only last for a certain amount of time before they expire.
    """
    global MDH_dataExplorer  # We are going to make changes to this.

    mdh = MDH(account_secret=secret_key,
          account_name=service_account,
          project_id=project_id)
    token = mdh.genServiceToken()

    dataExplorer = mdh.getExplorerCreds()

    # Populate the global MDH explorer credentials.
    for key in dataExplorer.keys():
        if key in MDH_dataExplorer:
            MDH_dataExplorer[key] = dataExplorer[key]

    print(f"New explorer credentials have been generated. Will expire on - {MDH_dataExplorer['Expiration']}")

def custom_db_connector_mutator(uri, params, username, security_manager, source):
    global MDH_dataExplorer

    # We only update the sql alchemy parameters
    if not uri.host == 'mdh.athena.com': 
        return uri, params

    # Do a quick check to make sure that the credentials have not expired.
    expireUTC = datetime.fromisoformat(MDH_dataExplorer['Expiration'])
    nowUTC = datetime.now(timezone.utc)
    if nowUTC > expireUTC:
        getExplorerCredentials(secret_key, service_account, project_id)

    # Rewrite the SQLALCHEMY_DATABASE_URI here if needed for mdh specific injections.
    uri = (
            f"awsathena+rest://"
            f"athena.{MDH_dataExplorer['region']}.amazonaws.com:443/{MDH_dataExplorer['schema_name']}"
            f"?s3_staging_dir={quote_plus(MDH_dataExplorer['s3_output'])}&work_group={MDH_dataExplorer['workgroup']}"
            )

    params = {
        "connect_args": {
            "catalog_name": MDH_dataExplorer['catalog'],
            "aws_access_key_id": MDH_dataExplorer['AccessKeyId'],
            "aws_secret_access_key": MDH_dataExplorer['SecretAccessKey'],
            "aws_session_token": MDH_dataExplorer['SessionToken']
        }
    }

    return uri, params

DB_CONNECTION_MUTATOR=custom_db_connector_mutator

ROW_LIMIT = 100000
PREFERRED_DATABASES = [
    'Amazon Athena'
]

SECRET_KEY=os.environ.get('SECRET_KEY')
if SECRET_KEY is None:
    raise Exception('SECRET_KEY environment variable not set')

# If the MDH_SECRET envrionment variable has been set then we put superset in MDH
# connect mode.
if os.getenv('MDH_SECRET') and os.getenv('MDH_ACC_NAME') and os.getenv('MDH_PROJECT_ID'):
    print('Superset is being put in MDH connect mode.')

    secret_key = os.getenv('MDH_SECRET')
    # Decode the base64 string into normal multiline string for the key.
    secret_key = base64.b64decode(secret_key)
    service_account = os.getenv('MDH_ACC_NAME')
    project_id = os.getenv('MDH_PROJECT_ID')

    # This sets the global variable MDH_dataExplorer with the required credentials.
    getExplorerCredentials(secret_key,
                           service_account,
                           project_id)

    # Also add some of the other fields needed to make the connection from the enviroment
    # variables.
    MDH_dataExplorer['region'] = os.getenv('MDH_REGION', 'us-east-1')
    MDH_dataExplorer['schema_name'] = os.getenv('MDH_SCHEMA')
    MDH_dataExplorer['s3_output'] = os.getenv('MDH_S3')
else:
    print('Normal superset mode.')

# ========================================
# Redis Configuration for Production
# ========================================

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# Cache configuration
CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "superset_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": REDIS_DB,
}

# Data cache configuration for query results
DATA_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 86400,  # 24 hours
    "CACHE_KEY_PREFIX": "superset_results_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": REDIS_DB,
}

# Filter state cache configuration
FILTER_STATE_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 86400,
    "CACHE_KEY_PREFIX": "superset_filter_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": REDIS_DB,
}

# Explore form data cache configuration
EXPLORE_FORM_DATA_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 86400,
    "CACHE_KEY_PREFIX": "superset_explore_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": REDIS_DB,
}

# Celery configuration for async queries (optional)
CELERY_CONFIG = {
    "broker_url": f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
    "imports": ("superset.sql_lab",),
    "result_backend": f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
    "worker_prefetch_multiplier": 1,
    "task_acks_late": True,
    "task_annotations": {
        "sql_lab.get_sql_results": {
            "rate_limit": "100/s",
        },
    },
}

# Production settings
DEBUG = False
WTF_CSRF_ENABLED = True

# Enable async queries
FEATURE_FLAGS = {
    "ENABLE_TEMPLATE_PROCESSING": True,
}

# Logging configuration
import logging
from logging.handlers import RotatingFileHandler

# Create logs directory if it doesn't exist
log_dir = os.path.join(os.environ.get('SUPERSET_HOME', '/app/superset_home'), 'logs')
os.makedirs(log_dir, exist_ok=True)

ENABLE_PROXY_FIX = True

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s:%(levelname)s:%(name)s:%(message)s"

# File handler for application logs
file_handler = RotatingFileHandler(
    os.path.join(log_dir, 'superset.log'),
    maxBytes=10485760,  # 10MB
    backupCount=10
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

# Tables you want to block (case-insensitive).
BLOCKED_TABLES = {
    "allparticipants",
}

# This matches quoted or unquoted identifiers, with or without schema,
# and respects word boundaries so 'secret_table_bak' won't trigger.
def _compile_block_patterns(blocked=set()):
    pats = []
    for name in blocked:
        parts = name.split(".")
        if len(parts) == 2:
            schema, table = map(re.escape, parts)
            pat = rf'(?i)(?<![\w"])("?\b{schema}\b"?\s*\.\s*"?\b{table}\b"?)'
        else:
            table = re.escape(parts[0])
            pat = rf'(?i)(?<![\w"])("?\b{table}\b"?)'
        pats.append(re.compile(pat))
    return pats

_BLOCK_PATTERNS = _compile_block_patterns(BLOCKED_TABLES)

def _strip_sql_comments(sql):
    # Remove /* ... */ and -- ... comments to avoid false positives in comments
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql

def SQL_QUERY_MUTATOR(sql, **kwargs):
    """
    If the SQL references a blocked table, raise an error and prevent execution.
    Otherwise, prefix the SQL with a comment (optional) and pass it through.
    """
    cleaned = _strip_sql_comments(sql)

    # Look for any blocked table patterns
    for pat in _BLOCK_PATTERNS:
        if pat.search(cleaned):
            # Raise an exception to stop SQL Lab from running this query
            raise Exception(
                "This query references a restricted table and cannot be executed. "
                "If you believe you need access, contact the data admin."
            )

    dttm = datetime.now().isoformat()
    return f"-- [SQL LAB] {dttm}\n{sql}"

SQL_QUERY_MUTATOR = SQL_QUERY_MUTATOR