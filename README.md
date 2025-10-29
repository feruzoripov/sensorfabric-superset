# Apache Superset Docker Setup

This repository contains a production-ready Docker setup for Apache Superset v5.0.0 with support for both development and production deployments.

## Features

- 🐳 **Containerized Deployment**: Full Docker-based setup
- 🚀 **Production Ready**: Gunicorn WSGI server with Nginx reverse proxy
- 💾 **Redis Caching**: Distributed caching for improved performance
- 🔒 **Security**: Configured with security headers and best practices
- 🛠️ **Development Mode**: Lightweight standalone container for testing
- 📊 **MDH Integration**: Optional integration with MDH Data Explorer

## Prerequisites

- Docker (v20.10 or higher)
- Docker Compose (v2.0 or higher)
- 4GB+ RAM recommended

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
cd superset-docker

# Create environment file
cp .env.example .env
```

### 2. Generate Secret Key

Generate a secure secret key for Superset:

```bash
openssl rand -base64 42
```

Copy the output and set it in your `.env` file:

```bash
SECRET_KEY=your_generated_secret_key_here
```

### 3. Configure Environment Variables

Edit `.env` and set your values:

```env
# Required
SECRET_KEY=<output from openssl rand -base64 42>

# Admin credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password
ADMIN_EMAIL=admin@yourdomain.com

# Optional: Change default ports and settings
NGINX_PORT=80
GUNICORN_WORKERS=4
```

### 4. Start Services

**Production Mode (recommended):**
```bash
chmod +x up.sh down.sh
./up.sh --build
```

**Development Mode:**
```bash
chmod +x build.sh run.sh stop.sh cleanup.sh
./build.sh
./run.sh -d
```

### 5. Access Superset

Open your browser and navigate to:
- **Production**: `http://localhost` (or your configured `NGINX_PORT`)
- **Development**: `http://localhost:8088`

Login with your configured admin credentials.

---

## Development Mode

Development mode runs Superset as a standalone container without Redis or Nginx. This is ideal for:
- Quick testing and development
- Lightweight resource usage
- Rapid iteration

### Build Image

Build the Docker image for your platform:

```bash
./build.sh
```

**Options:**
- `--tag TAG` - Set custom image tag (default: latest)
- `--name NAME` - Set image name (default: superset-base)
- `--platforms PLAT` - Set target platforms (default: linux/amd64,linux/arm64)
- `--push` - Push to registry after build

**Examples:**
```bash
# Build for local use
./build.sh

# Build and tag for production
./build.sh --tag v1.0.0

# Build multi-platform and push to registry
./build.sh --platforms linux/amd64,linux/arm64 --push
```

### Run Container

Start the Superset container:

```bash
./run.sh -d
```

**Options:**
- `-d, --detach` - Run in background
- `--port PORT` - Expose on custom port (default: 8088)
- `--name NAME` - Set container name (default: superset)
- `--env-file FILE` - Use custom env file (default: .env)
- `--rm` - Remove container when stopped

**Examples:**
```bash
# Run in background
./run.sh -d

# Run on custom port
./run.sh -d --port 9000

# Run with custom env file
./run.sh -d --env-file .env.local
```

### Stop Container

Stop the running container:

```bash
./stop.sh
```

**Options:**
- `--name NAME` - Stop specific container (default: superset)

### Clean Up

Remove container and wipe all data:

```bash
./cleanup.sh
```

**Options:**
- `-f, --force` - Skip confirmation prompt
- `--volume VOL` - Specify volume name (default: superset_data)

**Warning:** This will delete all Superset data including dashboards, charts, and database!

---

## Production Mode

Production mode deploys a full stack with:
- **Nginx**: Reverse proxy with caching and compression
- **Superset**: Running on Gunicorn WSGI server
- **Redis**: Distributed caching and async task queue

### Start Production Stack

Start all services with Docker Compose:

```bash
./up.sh --build
```

**Options:**
- `--build` - Build images before starting
- `--no-detach` - Run in foreground (view logs)
- `--env-file FILE` - Use custom env file (default: .env)

**Examples:**
```bash
# First time setup (build and start)
./up.sh --build

# Start existing services
./up.sh

# Run in foreground to view logs
./up.sh --no-detach
```

### Stop Production Stack

Stop all services:

```bash
./down.sh
```

**Options:**
- `-v, --volumes` - Remove volumes (deletes all data!)
- `--images` - Remove images

**Examples:**
```bash
# Stop services (preserve data)
./down.sh

# Stop and remove all data
./down.sh --volumes

# Stop and clean up everything
./down.sh --volumes --images
```

### View Logs

Monitor service logs:

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f superset
docker compose logs -f nginx
docker compose logs -f redis
```

### Check Service Status

```bash
docker compose ps
```

### Restart Services

```bash
# Restart all services
docker compose restart

# Restart specific service
docker compose restart superset
```

### Health Checks

All services include built-in health checks for monitoring:

```bash
# Check Superset health
curl http://localhost/health

# Check Redis health (from within container)
docker compose exec redis redis-cli ping

# View service health status
docker compose ps
```

Health check endpoints:
- **Superset**: `http://localhost:8088/health` (returns 200 OK when healthy)
- **Redis**: `redis-cli ping` (returns PONG when healthy)
- **Nginx**: `http://localhost/health` (proxies to Superset health check)

Docker Compose uses `condition: service_healthy` to ensure proper startup order.

---

## Environment Variables

### Superset Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SECRET_KEY` | Secret key for encryption | - | ✅ |
| `ADMIN_USERNAME` | Admin user username | admin | ✅ |
| `ADMIN_PASSWORD` | Admin user password | admin | ✅ |
| `ADMIN_FIRSTNAME` | Admin first name | Admin | ✅ |
| `ADMIN_LASTNAME` | Admin last name | User | ✅ |
| `ADMIN_EMAIL` | Admin email address | admin@superset.com | ✅ |

### Redis Configuration (Production)

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_HOST` | Redis hostname | redis |
| `REDIS_PORT` | Redis port | 6379 |
| `REDIS_DB` | Redis database number | 0 |

### Gunicorn Configuration (Production)

| Variable | Description | Default |
|----------|-------------|---------|
| `GUNICORN_WORKERS` | Number of worker processes | 4 |
| `GUNICORN_THREADS` | Threads per worker | 4 |
| `GUNICORN_TIMEOUT` | Request timeout (seconds) | 300 |
| `GUNICORN_LOG_LEVEL` | Log level | info |

### Nginx Configuration (Production)

| Variable | Description | Default |
|----------|-------------|---------|
| `NGINX_PORT` | HTTP port to expose | 80 |

### Application Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Application log level | INFO |

### MDH Configuration (Optional)

| Variable | Description | Required |
|----------|-------------|----------|
| `MDH_SECRET` | Base64 encoded MDH secret key | No |
| `MDH_ACC_NAME` | MDH account name | No |
| `MDH_PROJECT_ID` | MDH project ID | No |
| `MDH_SCHEMA` | MDH schema name | No |
| `MDH_S3` | MDH S3 output location | No |

**Note:** All MDH variables must be set to enable MDH integration mode.

---

## Architecture

### Production Stack

```
┌─────────────────────────────────────────────┐
│                  Internet                    │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
         ┌─────────────────┐
         │  Nginx (Port 80) │
         │  Reverse Proxy   │
         └────────┬─────────┘
                  │
                  ▼
    ┌─────────────────────────┐
    │  Superset (Port 8088)   │
    │  Gunicorn WSGI Server   │
    └──────────┬──────────────┘
               │
               ▼
    ┌─────────────────────────┐
    │   Redis (Port 6379)     │
    │   Caching & Queue       │
    └─────────────────────────┘
```

### Services

- **Nginx**: Handles SSL, compression, caching, and load balancing
- **Superset**: Application server with Gunicorn for production performance
- **Redis**: Distributed cache for query results, filter state, and async tasks

### Data Persistence

- **superset_data**: Volume for Superset database and application data
- **redis_data**: Volume for Redis persistence

---

## Configuration Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Container image definition |
| `docker-compose.yml` | Production stack orchestration |
| `entry.sh` | Container entrypoint script |
| `gunicorn_config.py` | Gunicorn WSGI server configuration |
| `nginx.conf` | Nginx reverse proxy configuration |
| `superset_config.py` | Superset application configuration |
| `.env` | Environment variables (create from .env.example) |
| `.gitignore` | Git ignore rules |
| `CLAUDE.md` | Project instructions for Claude Code AI assistant |

---

## Troubleshooting

### Container won't start

**Check logs:**
```bash
# Development mode
docker logs superset

# Production mode
docker compose logs superset
```

**Common issues:**
- Missing `.env` file - Copy from `.env.example`
- Missing `SECRET_KEY` - Generate with `openssl rand -base64 42`
- Port already in use - Change `NGINX_PORT` or stop conflicting service

### Cannot connect to Redis (Production)

**Check Redis status:**
```bash
docker compose ps redis
docker compose logs redis
```

**Verify connection:**
```bash
docker compose exec redis redis-cli ping
# Should return: PONG
```

### Database initialization fails

**Reset database:**
```bash
# Development mode
./cleanup.sh -f
./run.sh -d

# Production mode
./down.sh --volumes
./up.sh --build
```

### Permission issues

**Check volume permissions:**
```bash
# Development mode
docker exec superset ls -la /app/superset_home

# Production mode
docker compose exec superset ls -la /app/superset_home
```

### Out of memory errors

**Increase Docker resources:**
- Docker Desktop: Settings → Resources → Memory (recommend 4GB+)

**Reduce workers:**
Edit `.env`:
```env
GUNICORN_WORKERS=2
GUNICORN_THREADS=2
```

---

## Security Considerations

### Production Deployment

1. **Generate strong SECRET_KEY:**
   ```bash
   openssl rand -base64 42
   ```

2. **Change default admin credentials:**
   - Update `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `.env`

3. **Use HTTPS:**
   - Configure SSL certificates in `nginx.conf` (see commented HTTPS section)
   - Update port mapping in `docker-compose.yml`

4. **Restrict network access:**
   - Configure firewall rules
   - Use Docker networks for service isolation

5. **Regular updates:**
   - Keep Superset and dependencies updated
   - Monitor security advisories

### Environment Variables

- Never commit `.env` to version control
- Use secrets management in production (e.g., Docker Secrets, HashiCorp Vault)
- Rotate `SECRET_KEY` and admin passwords regularly

---

## Advanced Configuration

### Custom Database

By default, Superset uses SQLite. For production, configure PostgreSQL or MySQL:

Edit `superset_config.py`:
```python
SQLALCHEMY_DATABASE_URI = 'postgresql://user:password@host:port/database'
```

Add database service to `docker-compose.yml`.

### Celery Workers (Async Queries)

To enable async query execution, add Celery workers:

1. Uncomment Celery configuration in `superset_config.py`
2. Add worker service to `docker-compose.yml`:
```yaml
  worker:
    build: .
    command: celery --app=superset.tasks.celery_app:app worker
    depends_on:
      - redis
      - superset
```

### Custom Gunicorn Settings

Edit `gunicorn_config.py` or set environment variables in `.env`:
```env
GUNICORN_WORKERS=8
GUNICORN_THREADS=4
GUNICORN_TIMEOUT=600
```

### Nginx SSL/TLS

Uncomment HTTPS section in `nginx.conf` and mount certificates:
```yaml
volumes:
  - ./ssl/cert.pem:/etc/nginx/ssl/cert.pem
  - ./ssl/key.pem:/etc/nginx/ssl/key.pem
```

---

## MDH Integration

This setup includes optional integration with MDH Data Explorer for AWS Athena queries.

### Setup

1. Obtain MDH service account credentials
2. Base64 encode your secret key:
   ```bash
   cat your_secret_key.pem | base64
   ```
3. Configure in `.env`:
   ```env
   MDH_SECRET=<base64_encoded_secret>
   MDH_ACC_NAME=your_account_name
   MDH_PROJECT_ID=your_project_id
   MDH_SCHEMA=your_schema
   MDH_S3=s3://your-bucket/path/
   ```

### Usage

When MDH variables are set, Superset will:
- Automatically connect to MDH Data Explorer
- Fetch temporary AWS credentials
- Enable Amazon Athena as a data source

Connection URL format: `mdh.athena.com`

---

## Maintenance

### Backup Data

**Development mode:**
```bash
docker cp superset:/app/superset_home ./backup
```

**Production mode:**
```bash
docker compose cp superset:/app/superset_home ./backup
```

### Restore Data

**Development mode:**
```bash
docker cp ./backup superset:/app/superset_home
```

**Production mode:**
```bash
docker compose cp ./backup superset:/app/superset_home
docker compose restart superset
```

### Update Images

```bash
# Development
./build.sh
./stop.sh
./run.sh -d

# Production
./up.sh --build
```

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test in both development and production modes
5. Submit a pull request

---

## License

This project is provided as-is for deploying Apache Superset with Docker.

---

## Resources

- [Apache Superset Documentation](https://superset.apache.org/)
- [Docker Documentation](https://docs.docker.com/)
- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [Redis Documentation](https://redis.io/documentation)

---

## Support

For issues and questions:
- Check the [Troubleshooting](#troubleshooting) section
- Review logs for error messages
- Consult Apache Superset documentation
- Open an issue in the repository

---

**Happy data visualization with Superset! 📊**
