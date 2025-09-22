# LVFlow MVP – Making Tendering Smarter

![LVFlow image](/images/lvflow.jpg)

## Quickstart

### 1) Start Services

```bash
# Start Postgres + pgAdmin
docker compose up -d

# Verify containers are running
docker ps
```

### 2) Install Dependencies & Run API

```bash
# Install dependencies
uv sync

# Run FastAPI server
uv run python main.py
```

### 3) Access Services

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **pgAdmin**: http://localhost:5050
  - Email: `finn.ferchau@pool.com`
  - Password: `pool`

## Database Setup

### Initialize Database

```bash
# Create tables
curl -X POST http://localhost:8000/ingest/init-db
```

### Ingest Data from JSON

```bash
# Import extracted LV data
curl -X POST "http://localhost:8000/ingest/from-json?offer_name=DKFZ%20Labortechnik"
```

## Frontend (SSR + HTMX)

- Root page: http://localhost:8000/ renders a simple form to trigger ingestion and shows results inline via HTMX.
- Tech: Jinja2 templates, HTMX for partial updates, Tailwind via CDN.
- Templates live in `app/templates/`.

## API Endpoints

### Health
- `GET /health/ready` - Readiness probe
- `GET /health/live` - Liveness probe

### Data Ingestion
- `POST /ingest/init-db` - Create database tables
- `POST /ingest/from-json?offer_name={name}` - Import JSON data

## Database Schema

Based on ERD with tables:
- `offer` - Main documents
- `prod_group` - Product groups within offers
- `prod_variant` - Specific product variants
- `component` - Reusable components
- `prod_variant_component` - Many-to-many relationship

## Data Sources

The ingestion expects JSON files in `data/`:
- `product_groups.json` - Product group definitions
- `product_variants.json` - Product variant details
- `required_components.json` - Component requirements (optional)

## pgAdmin Connection

Add server in pgAdmin:
- **Name**: lv_local
- **Host**: db
- **Port**: 5432
- **Username**: lvuser
- **Password**: lvpass
- **Maintenance DB**: lvflow

## Environment Variables

Copy `env.example` to `.env` to override defaults:
```bash
cp env.example .env
```

Default database URL: `postgresql+asyncpg://lvuser:lvpass@localhost:5432/lvflow`
