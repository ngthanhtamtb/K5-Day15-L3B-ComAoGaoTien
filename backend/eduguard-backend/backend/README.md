### Installation

2. **Set up environment variables**

cp .env.example .env


3. **Install dependencies**

pip install -r requirements.txt


5. **Run the application**

nohup uvicorn main:app --host 0.0.0.0 --port 8077 


### Using Docker

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api


## API Documentation

- **Swagger UI**: http://localhost:8077/api-docs
- **ReDoc**: http://localhost:8077/api-redoc

## Project Structure


smartslides/
├── app/
│   ├── api/v1/endpoints/    # API route handlers
│   ├── core/                # Core functionality (auth, config, db)
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   └── services/            # Business logic services
├── uploads/                 # File storage directory
├── alembic/                 # Database migrations
├── main.py                  # FastAPI application entry point
├── requirements.txt         # Python dependencies
├── Dockerfile               # Container configuration
└── docker-compose.yml       # Multi-container setup

