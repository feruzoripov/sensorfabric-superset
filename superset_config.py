from urllib.parse import quote_plus
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
    # Check for query parameter
    if '?mdh_project=' in uri_str:
        try:
            return uri_str.split('?mdh_project=')[1].split('&')[0]
        except:
            pass

    # Check hostname patterns
    if 'mdh-' in uri_str:
        try:
            start = uri_str.find('mdh-') + 4
            end_markers = ['.', ':', '/', '?']
            end = len(uri_str)
            for marker in end_markers:
                marker_pos = uri_str.find(marker, start)
                if marker_pos != -1:
                    end = min(end, marker_pos)
            return uri_str[start:end]
        except:
            pass

    # Check if URI contains any configured project names
    for project_alias in MDH_PROJECTS.keys():
        if project_alias in uri_str:
            return project_alias

    # If only one project configured, use it
    if len(MDH_PROJECTS) == 1:
        return list(MDH_PROJECTS.keys())[0]

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

# ---- Read blocked tables from env ----
# Example in .env:
# BLOCKED_TABLES=raw.pii_users, finance.payments_ledger, secret_table
BLOCKED_TABLES = {
    t.strip()
    for t in os.getenv("BLOCKED_TABLES", "").split(",")
    if t.strip()
}

def _compile_block_patterns(blocked: set[str]) -> list[re.Pattern]:
    """
    Compile regexes that match quoted/unquoted, schema-qualified or plain names.
    """
    patterns: list[re.Pattern] = []
    for name in blocked:
        parts = name.split(".")
        if len(parts) == 2:
            schema, table = map(re.escape, parts)
            # e.g. raw.pii_users (with optional quotes/whitespace)
            pat = rf'(?i)(?<![\w"])("?\b{schema}\b"?\s*\.\s*"?\b{table}\b"?)'
        else:
            table = re.escape(parts[0])
            pat = rf'(?i)(?<![\w"])("?\b{table}\b"?)'
        patterns.append(re.compile(pat))
    return patterns

_BLOCK_PATTERNS = _compile_block_patterns(BLOCKED_TABLES)

def _strip_sql_comments(sql: str) -> str:
    # Remove /* ... */ and -- ... to avoid matches in comments
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql

def SQL_QUERY_MUTATOR(sql: str, **kwargs) -> str:
    """
    Blocks queries that reference any table in BLOCKED_TABLES.
    """
    cleaned = _strip_sql_comments(sql)

    for pat in _BLOCK_PATTERNS:
        if pat.search(cleaned):
            raise Exception(
                "This query references a restricted table and cannot be executed. "
                "If you believe you need access, contact the data admin."
            )

    dttm = datetime.now().isoformat()
    return f"-- [SQL LAB] {dttm}\n{sql}"

SQL_QUERY_MUTATOR = SQL_QUERY_MUTATOR