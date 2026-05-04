from urllib.parse import quote_plus, urlparse
from sensorfabric.mdh import MDH
from sensorfabric import utils
import re
import os
from datetime import datetime, timezone
import base64
import yaml
from cachelib.redis import RedisCache

# ========================================
# Multi-Project MDH Configuration
# ========================================

MDH_PROJECTS = {}

class MDHProject:
    def __init__(self, project_alias, config):
        self.alias = project_alias
        self.project_id = config.get('project_id', project_alias)
        self.account_name = config['account_name']

        # Handle secret key - support both field names
        secret_value = config.get('secret') or config.get('account_secret_b64')
        if not secret_value:
            raise ValueError(f"No secret key found for project {project_alias}")

        # Decode base64 secret to bytes
        self.secret_key = base64.b64decode(secret_value)

        self.schema = config.get('schema') or config.get('schema_name', '')
        self.s3_output = config.get('s3_output', '')
        self.region = config.get('region', 'us-east-1')
        self.workgroup = config.get('workgroup', 'mdh_export_database_external_prod')
        self.catalog = config.get('catalog', 'AwsDataCatalog')

        # Credentials storage
        self.credentials = {
            'AccessKeyId': '',
            'SecretAccessKey': '',
            'SessionToken': '',
            'Expiration': '1970-01-01T00:00:00+00:00',
            'region': self.region,
            'catalog': self.catalog,
            'schema_name': self.schema,
            'workgroup': self.workgroup,
            's3_output': self.s3_output
        }

    def _credentials_expired(self):
        """Check if current credentials are expired"""
        try:
            exp_time = datetime.fromisoformat(self.credentials['Expiration'])
            return datetime.now(timezone.utc) >= exp_time
        except:
            return True

    def _refresh_credentials(self):
        """Get fresh credentials from MDH"""
        mdh = MDH(
            account_secret=self.secret_key,
            account_name=self.account_name,
            project_id=self.project_id
        )

        token = mdh.genServiceToken()
        dataExplorer = mdh.getExplorerCreds()

        # Update credentials
        for key in dataExplorer.keys():
            if key in self.credentials:
                self.credentials[key] = dataExplorer[key]

    def get_connection_params(self):
        """Get SQLAlchemy URI and connection parameters"""
        if self._credentials_expired():
            self._refresh_credentials()

        # Build URI
        uri = (
            f"awsathena+rest://"
            f"athena.{self.credentials['region']}.amazonaws.com:443/{self.credentials['schema_name']}"
            f"?s3_staging_dir={quote_plus(self.credentials['s3_output'])}&work_group={self.credentials['workgroup']}"
        )

        params = {
            "connect_args": {
                "catalog_name": self.credentials['catalog'],
                "aws_access_key_id": self.credentials['AccessKeyId'],
                "aws_secret_access_key": self.credentials['SecretAccessKey'],
                "aws_session_token": self.credentials['SessionToken']
            }
        }

        return uri, params

def load_mdh_projects():
    """Load MDH projects from environment variables or YAML"""
    global MDH_PROJECTS

    # Try JSON from environment variable first
    projects_env = os.getenv('MDH_PROJECTS')
    if projects_env:
        try:
            import json
            projects_config = json.loads(projects_env)
            
            for project_config in projects_config:
                project_alias = project_config.get('alias')
                if project_alias:
                    try:
                        project = MDHProject(project_alias, project_config)
                        MDH_PROJECTS[project_alias] = project
                    except Exception:
                        continue
            return
        except Exception:
            pass

    # Try YAML configuration file
    config_file = os.getenv('MDH_CONFIG_FILE', 'mdh_projects.yaml')
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            if config and 'projects' in config:
                for project_alias, project_config in config['projects'].items():
                    if project_config.get('account_name') and project_config.get('secret'):
                        try:
                            project = MDHProject(project_alias, project_config)
                            MDH_PROJECTS[project_alias] = project
                        except Exception:
                            continue
        except Exception:
            pass

def get_project_from_uri(uri_str):
    """Extract project ID from database URI"""
    # MDH uri come with the hostnmae "mdh.athena.com".
    # If we do not find that we just return for normal processing.
    hostname = urlparse(uri_str).hostname
    if not hostname == 'mdh.athena.com':
        return None

    # Check for query parameter
    if '?mdh_project=' in uri_str:
        try:
            return uri_str.split('?mdh_project=')[1].split('&')[0]
        except:
            pass

    return None

def custom_db_connector_mutator(uri, params, username, security_manager, source):
    """Multi-project MDH database connector mutator"""
    uri_str = str(uri)
    project_alias = get_project_from_uri(uri_str)

    if not project_alias or project_alias not in MDH_PROJECTS:
        return uri, params

    # Get connection parameters from the project
    project = MDH_PROJECTS[project_alias]
    new_uri, new_params = project.get_connection_params()

    return new_uri, new_params

# Initialize MDH projects
load_mdh_projects()

DB_CONNECTION_MUTATOR = custom_db_connector_mutator

# ========================================
# Superset Configuration
# ========================================

ROW_LIMIT = 100000
PREFERRED_DATABASES = ["Amazon Athena"]

SECRET_KEY = os.environ.get("SECRET_KEY")
if SECRET_KEY is None:
    raise Exception("SECRET_KEY environment variable not set")

# ========================================
# Redis Configuration
# ========================================

REDIS_HOST = os.getenv("REDIS_HOST", None)
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
log_dir = os.path.join(os.environ.get("SUPERSET_HOME", "/app/superset_home"), "logs")
os.makedirs(log_dir, exist_ok=True)

ENABLE_PROXY_FIX = True

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s:%(levelname)s:%(name)s:%(message)s"

# File handler for application logs
file_handler = RotatingFileHandler(
    os.path.join(log_dir, "superset.log"), maxBytes=10485760, backupCount=10  # 10MB
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

# ---- Access control configuration from env ----

# Fully blocked tables (no access at all unless ALLOWED_COLUMNS grants exceptions)
BLOCKED_TABLES = {
    t.strip()
    for t in os.getenv("BLOCKED_TABLES", "").split(",")
    if t.strip()
}

# Columns allowed from blocked tables (table.column format)
ALLOWED_COLUMNS = {}
for entry in os.getenv("ALLOWED_COLUMNS", "").split(","):
    entry = entry.strip()
    if "." in entry:
        table, column = entry.split(".", 1)
        ALLOWED_COLUMNS.setdefault(table.strip().lower(), set()).add(column.strip().lower())

# Blocked field values - rows with these values in BLOCKED_FIELDS_COLUMNS are excluded
BLOCKED_FIELDS = {
    f.strip().lower()
    for f in os.getenv("BLOCKED_FIELDS", "").split(",")
    if f.strip()
}

# Columns that contain field identifiers to filter against (comma-separated)
# Use column_name for varchar columns, or column_name:map for map-type columns
BLOCKED_FIELDS_COLUMNS = []
for c in os.getenv("BLOCKED_FIELDS_COLUMN", "").split(","):
    c = c.strip()
    if c:
        BLOCKED_FIELDS_COLUMNS.append(c)


def _strip_sql_comments(sql: str) -> str:
    """Remove SQL comments to avoid false matches"""
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql


def _query_references_table(sql_lower: str, table: str) -> bool:
    """Check if SQL references a specific table"""
    table_escaped = re.escape(table.lower())
    pattern = rf'(?:from|join|update|into|delete\s+from)\s+["`]?{table_escaped}["`]?(?:\s|$|,|;)'
    return bool(re.search(pattern, sql_lower))


def _query_uses_star_on_table(sql_lower: str, table: str) -> bool:
    """Check if query uses SELECT * on a specific table"""
    if re.search(r'\bselect\s+\*\s+from\b', sql_lower):
        return True
    table_escaped = re.escape(table.lower())
    if re.search(rf'\b{table_escaped}\s*\.\s*\*', sql_lower):
        return True
    return False


def _get_selected_columns(sql_lower: str) -> set:
    """Extract column names from SELECT clause"""
    match = re.search(r'select\s+(.*?)\s+from\b', sql_lower, re.S)
    if not match:
        return set()

    select_clause = match.group(1)
    columns = set()
    for col in select_clause.split(","):
        col = col.strip()
        if "." in col:
            col = col.split(".")[-1]
        if " as " in col:
            col = col.split(" as ")[0].strip()
        col = col.strip('"`')
        columns.add(col.lower())

    return columns


def _inject_blocked_fields_filter(sql: str) -> str:
    """
    Rewrite the query to exclude rows where any BLOCKED_FIELDS_COLUMNS
    matches a blocked field value. Only filters on columns that exist
    in the original query.
    
    For varchar columns: filters rows where column value matches blocked fields
    For map columns: removes blocked keys from the map
    """
    if not BLOCKED_FIELDS_COLUMNS or not BLOCKED_FIELDS:
        return sql

    sql_lower = sql.lower()

    # Only apply filter for columns that are actually referenced in the query
    applicable_columns = [
        col for col in BLOCKED_FIELDS_COLUMNS
        if col.lower().split(":")[0] in sql_lower
    ]

    if not applicable_columns:
        return sql

    blocked_list = ", ".join(f"'{f}'" for f in sorted(BLOCKED_FIELDS))

    # Separate varchar columns from map columns
    varchar_conditions = []
    map_columns = []

    for col in applicable_columns:
        if ":" in col and col.split(":")[1].lower() == "map":
            map_columns.append(col.split(":")[0])
        else:
            varchar_conditions.append(f"LOWER({col}) NOT IN ({blocked_list})")

    # If we only have varchar columns, use simple WHERE filter
    if varchar_conditions and not map_columns:
        conditions = " AND ".join(varchar_conditions)
        return (
            f"SELECT * FROM (\n{sql}\n) __filtered\n"
            f"WHERE {conditions}"
        )

    # If we have map columns, we need to rebuild the SELECT to strip blocked keys
    # For map columns: use map_filter to remove blocked keys
    map_transforms = []
    for col in map_columns:
        blocked_array = ", ".join(f"'{f}'" for f in sorted(BLOCKED_FIELDS))
        map_transforms.append(
            f"map_filter({col}, (k, v) -> LOWER(k) NOT IN ({blocked_array})) AS {col}"
        )

    # Build the outer query
    if map_transforms:
        # Get all columns except the map ones we're transforming, then add transformed versions
        map_col_names = {c.lower() for c in map_columns}
        
        # Replace the map columns with filtered versions
        select_parts = []
        select_parts.append("*")  # We'll use EXCEPT syntax or subquery approach
        
        # Athena supports replacing columns via subquery
        other_cols = "__inner.*"
        
        # Simpler approach: wrap and replace
        inner_alias = "__inner"
        map_selects = ", ".join(map_transforms)
        
        # Use a subquery that excludes map columns, then add filtered versions
        filtered_sql = (
            f"SELECT {inner_alias}.*, {map_selects} FROM (\n{sql}\n) {inner_alias}"
        )
        
        # This will create duplicate columns - let's use a different approach
        # Just wrap the query and apply map_filter in outer SELECT
        # Athena doesn't support EXCEPT, so we select * and override with map_filter
        
        # Simplest approach: just filter the map in a wrapping query
        map_filter_exprs = ", ".join(
            f"map_filter({col}, (k, v) -> LOWER(k) NOT IN ({blocked_list})) AS {col}"
            for col in map_columns
        )
        
        filtered_sql = f"SELECT *, {map_filter_exprs} FROM (\n{sql}\n) __filtered"
        
        # Add varchar conditions if any
        if varchar_conditions:
            conditions = " AND ".join(varchar_conditions)
            filtered_sql += f"\nWHERE {conditions}"
        
        return filtered_sql

    return sql


def SQL_QUERY_MUTATOR(sql: str, **kwargs) -> str:
    """
    Access control for SQL queries:
    1. Block queries to BLOCKED_TABLES unless only querying ALLOWED_COLUMNS
    2. Block SELECT * on restricted tables
    3. Automatically exclude rows matching BLOCKED_FIELDS from results
    """
    cleaned = _strip_sql_comments(sql)
    sql_lower = cleaned.lower()

    # Check each blocked table
    for table in BLOCKED_TABLES:
        if not _query_references_table(sql_lower, table):
            continue

        table_lower = table.lower()

        # If table has no allowed columns, block entirely
        if table_lower not in ALLOWED_COLUMNS:
            raise Exception(
                f"Access denied: Table '{table}' is restricted. "
                "Contact the data admin if you need access."
            )

        # Block SELECT * on restricted tables
        if _query_uses_star_on_table(sql_lower, table):
            allowed = ", ".join(sorted(ALLOWED_COLUMNS[table_lower]))
            raise Exception(
                f"Access denied: SELECT * is not allowed on '{table}'. "
                f"You may only query these columns: {allowed}"
            )

        # Check that only allowed columns are being selected
        selected_columns = _get_selected_columns(sql_lower)
        allowed_cols = ALLOWED_COLUMNS[table_lower]

        for col in selected_columns:
            if col not in allowed_cols and col != "*":
                raise Exception(
                    f"Access denied: Column '{col}' is not accessible on '{table}'. "
                    f"Allowed columns: {', '.join(sorted(allowed_cols))}"
                )

    # Inject filter to exclude blocked fields from results
    sql = _inject_blocked_fields_filter(sql)

    dttm = datetime.now().isoformat()
    return f"-- [SQL LAB] {dttm}\n{sql}"

SQL_QUERY_MUTATOR = SQL_QUERY_MUTATOR

