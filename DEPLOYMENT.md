# TradeMind Production Deployment Guide

This document supersedes any ad-hoc deployment notes and will be linked from README.md and plan.md.
User instruction: "complete all phases in plan.md"

## Overview

This guide covers deploying TradeMind to production environments. The application consists of:
- **FastAPI Backend** (port 8000): Market data, research agent, trading agent, risk engine
- **Streamlit Frontend** (port 8501): Multi-page dashboard
- **PostgreSQL Database** (port 5432): Persistent storage for market data, orders, positions

## Prerequisites

- Docker 24+ and Docker Compose 2+
- PostgreSQL 16+ (or use provided Docker service)
- 2GB+ RAM, 2+ CPU cores recommended
- Domain name with SSL certificate (for production)

## Quick Start (Development)

```bash
# Clone and configure
git clone https://github.com/your-org/trademind.git
cd trademind
cp .env.example .env

# Start all services
docker-compose up -d

# Verify health
curl http://localhost:8000/health
curl http://localhost:8501/_stcore/health

# View logs
docker-compose logs -f api
docker-compose logs -f streamlit
```

## Environment Configuration

Create `.env` file with required variables:

```bash
# Database
DATABASE_URL=postgresql+psycopg://trademind:secure_password@postgres:5432/trademind

# Application
ENVIRONMENT=production
LOG_LEVEL=INFO
SECRET_KEY=your-super-secret-key-min-32-chars
API_KEY=your-api-key-for-authentication

# External APIs
OPENAI_API_KEY=sk-...  # Optional: for AI narration
YAHOO_FINANCE_TIMEOUT=30

# Frontend
FASTAPI_BASE_URL=http://api:8000
STREAMLIT_SERVER_PORT=8501
```

## Production Deployment Options

### Option 1: Docker Compose (Single Server)

```yaml
# docker-compose.prod.yml
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: trademind
      POSTGRES_USER: trademind
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U trademind -d trademind"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - trademind-network

  api:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql+psycopg://trademind:${POSTGRES_PASSWORD}@postgres:5432/trademind
      ENVIRONMENT: production
      LOG_LEVEL: INFO
      SECRET_KEY: ${SECRET_KEY}
      API_KEY: ${API_KEY}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
    networks:
      - trademind-network

  streamlit:
    build:
      context: .
      dockerfile: Dockerfile.streamlit
    environment:
      FASTAPI_BASE_URL: http://api:8000
      STREAMLIT_SERVER_PORT: 8501
      STREAMLIT_SERVER_ADDRESS: 0.0.0.0
    ports:
      - "8501:8501"
    depends_on:
      - api
    deploy:
      replicas: 1
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M
    networks:
      - trademind-network

volumes:
  postgres_data:

networks:
  trademind-network:
    driver: bridge
```

Deploy:
```bash
docker-compose -f docker-compose.prod.yml up -d --build
```

### Option 2: Kubernetes (Recommended for Scale)

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: trademind
---
# k8s/postgres.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: trademind
spec:
  serviceName: postgres
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:16-alpine
        env:
        - name: POSTGRES_DB
          value: trademind
        - name: POSTGRES_USER
          value: trademind
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: trademind-secrets
              key: postgres-password
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: postgres-data
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: postgres-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 20Gi
---
# k8s/api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: trademind
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
      - name: api
        image: your-registry/trademind-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          value: postgresql+psycopg://trademind:$(POSTGRES_PASSWORD)@postgres:5432/trademind
        - name: ENVIRONMENT
          value: production
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: trademind-secrets
              key: secret-key
        - name: API_KEY
          valueFrom:
            secretKeyRef:
              name: trademind-secrets
              key: api-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
---
# k8s/api-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: api
  namespace: trademind
spec:
  selector:
    app: api
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP
---
# k8s/streamlit-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: streamlit
  namespace: trademind
spec:
  replicas: 2
  selector:
    matchLabels:
      app: streamlit
  template:
    metadata:
      labels:
        app: streamlit
    spec:
      containers:
      - name: streamlit
        image: your-registry/trademind-streamlit:latest
        ports:
        - containerPort: 8501
        env:
        - name: FASTAPI_BASE_URL
          value: http://api.trademind.svc.cluster.local:8000
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /_stcore/health
            port: 8501
          initialDelaySeconds: 30
          periodSeconds: 10
---
# k8s/streamlit-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: streamlit
  namespace: trademind
spec:
  selector:
    app: streamlit
  ports:
  - port: 8501
    targetPort: 8501
  type: ClusterIP
---
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: trademind-ingress
  namespace: trademind
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  tls:
  - hosts:
    - api.trademind.example.com
    - app.trademind.example.com
    secretName: trademind-tls
  rules:
  - host: api.trademind.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api
            port:
              number: 8000
  - host: app.trademind.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: streamlit
            port:
              number: 8501
```

Deploy to Kubernetes:
```bash
# Create namespace and secrets
kubectl apply -f k8s/namespace.yaml
kubectl create secret generic trademind-secrets \
  --namespace trademind \
  --from-literal=postgres-password='secure-password' \
  --from-literal=secret-key='your-32-char-secret' \
  --from-literal=api-key='your-api-key'

# Apply deployments
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/api-service.yaml
kubectl apply -f k8s/streamlit-deployment.yaml
kubectl apply -f k8s/streamlit-service.yaml
kubectl apply -f k8s/ingress.yaml
```

### Option 3: Cloud Managed Services

#### AWS (ECS Fargate + RDS + ALB)
```bash
# Use AWS Copilot or CDK for infrastructure
# Key services: ECS Fargate, RDS PostgreSQL, Application Load Balancer, ECR
```

#### Google Cloud (Cloud Run + Cloud SQL)
```bash
# Build and deploy to Cloud Run
gcloud builds submit --tag gcr.io/PROJECT_ID/trademind-api
gcloud run deploy trademind-api --image gcr.io/PROJECT_ID/trademind-api --platform managed
```

#### Azure (Container Apps + PostgreSQL Flexible Server)
```bash
# Use Azure Container Apps with managed PostgreSQL
```

## Database Migrations

### Run Migrations
```bash
# Local
alembic upgrade head

# Docker
docker-compose exec api alembic upgrade head

# Kubernetes
kubectl exec -n trademind deploy/api -- alembic upgrade head
```

### Create New Migration
```bash
alembic revision --autogenerate -m "description"
```

### Backup & Restore
```bash
# Backup
pg_dump -U trademind -h localhost trademind > backup_$(date +%Y%m%d).sql

# Restore
psql -U trademind -h localhost trademind < backup_20240115.sql
```

## Health Checks & Monitoring

### API Health Endpoints
- `GET /health` - Basic liveness
- `GET /health/ready` - Readiness (DB connectivity)
- `GET /metrics` - Prometheus metrics (if enabled)

### Streamlit Health
- `GET /_stcore/health` - Streamlit health

### Prometheus Metrics (Add to FastAPI)
```python
# app/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge

REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency', ['method', 'endpoint'])
ACTIVE_POSITIONS = Gauge('trading_active_positions', 'Number of open positions')
DAILY_PNL = Gauge('trading_daily_pnl', 'Daily realized P&L')
```

### Grafana Dashboard
Import dashboard JSON for:
- Request rate, latency, errors
- Trading metrics (positions, P&L, exposure)
- System metrics (CPU, memory, disk)

## SSL/TLS Configuration

### Let's Encrypt with Cert-Manager (Kubernetes)
```yaml
# Automatically handled by ingress annotations
cert-manager.io/cluster-issuer: letsencrypt-prod
```

### Nginx Reverse Proxy (Docker Compose)
```nginx
# nginx.conf
server {
    listen 443 ssl http2;
    server_name api.trademind.example.com;

    ssl_certificate /etc/ssl/certs/trademind.crt;
    ssl_certificate_key /etc/ssl/private/trademind.key;

    location / {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Security Hardening

### Network Policies (Kubernetes)
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-network-policy
  namespace: trademind
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    ports:
    - protocol: TCP
      port: 5432
```

### API Key Authentication
```python
# Add to FastAPI dependencies
async def verify_api_key(api_key: str = Header(...)):
    if api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key
```

### Rate Limiting
```python
# Add to FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/api/v1/market-data/{ticker}")
@limiter.limit("60/minute")
async def get_market_data(request: Request, ticker: str):
    ...
```

## Scaling Considerations

### Horizontal Scaling
- API: Stateless, scale replicas based on CPU/requests
- Streamlit: Session affinity required, use sticky sessions
- PostgreSQL: Read replicas for reporting queries

### Caching
```python
# Add Redis for caching market data
import redis
cache = redis.Redis(host='redis', port=6379, decode_responses=True)
```

### Background Workers
```python
# Use Celery for async tasks
from celery import Celery

celery = Celery('trademind', broker='redis://redis:6379/0')

@celery.task
def scheduled_research_run(tickers: list[str]):
    for ticker in tickers:
        # Run research agent
        pass
```

## Disaster Recovery

### Backup Strategy
- Daily automated PostgreSQL backups (pg_dump)
- Weekly full system snapshots
- Test restore procedure monthly

### RTO/RPO Targets
- RTO (Recovery Time Objective): < 30 minutes
- RPO (Recovery Point Objective): < 1 hour

### Failover
- PostgreSQL: Streaming replication with automatic failover (Patroni)
- API: Multi-AZ deployment with load balancer
- DNS: Route53/Cloud DNS health checks with failover

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Database connection refused | Check PostgreSQL is running, verify DATABASE_URL |
| Migration fails | Check alembic version, run `alembic upgrade head` |
| Streamlit can't reach API | Verify FASTAPI_BASE_URL, check network connectivity |
| High memory usage | Reduce worker count, add memory limits |
| Slow queries | Add indexes, check query plans |

### Debug Commands
```bash
# Check container logs
docker-compose logs -f api
docker-compose logs -f streamlit
docker-compose logs -f postgres

# Execute into container
docker-compose exec api bash
docker-compose exec postgres psql -U trademind -d trademind

# Check database status
docker-compose exec api alembic current
docker-compose exec api alembic history
```

## Maintenance

### Regular Tasks
- Weekly: Review logs, check disk space
- Monthly: Update dependencies, security patches
- Quarterly: Rotate secrets, review access controls

### Upgrade Procedure
```bash
# 1. Backup database
pg_dump ... > backup.sql

# 2. Pull latest images
docker-compose pull

# 3. Run migrations
docker-compose exec api alembic upgrade head

# 4. Restart services
docker-compose up -d --build

# 5. Verify health
curl https://api.trademind.example.com/health
```

## Support Contacts

- Platform Team: platform@company.com
- On-call: PagerDuty rotation
- Security: security@company.com