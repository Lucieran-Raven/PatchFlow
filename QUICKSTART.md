# PatchFlow Quick Start Guide

## Prerequisites

- Docker & Docker Compose
- Node.js 20+ (for local frontend dev)
- Python 3.11+ (for local backend dev)
- Git

## Option 1: Quick Start with Docker Compose (Recommended)

The fastest way to get PatchFlow running locally:

```bash
# 1. Clone the repository
git clone https://github.com/Lucieran-Raven/PatchFlow.git
cd PatchFlow

# 2. Copy environment variables
cp .env.example .env
# Edit .env with your API keys (GitHub, OpenAI, etc.)

# 3. Start all services
docker-compose up -d

# 4. Wait for services to be healthy
docker-compose ps

# 5. Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## Option 2: Manual Development Setup

### Backend Setup

```bash
# 1. Navigate to backend
cd backend

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up database (requires PostgreSQL running)
# Create database: patchflow

# 5. Run migrations
# alembic upgrade head

# 6. Start the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
# 1. Navigate to frontend
cd frontend

# 2. Install dependencies
npm install

# 3. Start development server
npm run dev

# 4. Access at http://localhost:3000
```

## What's Been Built

### Week 1 Deliverables (MVP Foundation)

✅ **Project Structure**
- Complete directory structure following the blueprint
- Frontend (Next.js + Tailwind + shadcn/ui)
- Backend (FastAPI + PostgreSQL + Redis)
- AI Agents framework (BaseAgent class + Triage + Code Fix)

✅ **Frontend (Marketing Website)**
- Landing page with hero section, features, pricing
- Responsive design with Tailwind CSS
- Component architecture ready for dashboard

✅ **Backend (Core API)**
- FastAPI application with auto-generated docs
- Database models (User, Repository, Vulnerability)
- API endpoints for auth, repos, vulnerabilities, agents
- Health check and monitoring endpoints

✅ **AI Agents Framework**
- BaseAgent abstract class
- Triage Agent implementation
- Code Fix Agent implementation
- Ready for integration with LLMs

✅ **Infrastructure**
- Dockerfiles for frontend and backend
- Docker Compose for local development
- Kubernetes manifests for deployment
- GitHub Actions CI/CD pipeline
- Environment configuration templates

## Next Steps (Week 2)

1. **Install dependencies and test locally**
   ```bash
   cd frontend && npm install
   cd backend && pip install -r requirements.txt
   ```

2. **Connect external services**
   - Set up GitHub OAuth app
   - Get OpenAI API key
   - Configure Stripe (for billing)

3. **Implement GitHub integration**
   - OAuth login
   - Repository webhooks
   - Code scanning triggers

4. **Set up database**
   - Run PostgreSQL locally or use managed service
   - Execute migrations
   - Test API endpoints

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info |
| `/health/health` | GET | Health check |
| `/auth/register` | POST | User registration |
| `/auth/login` | POST | User login |
| `/repositories/` | GET | List repos |
| `/repositories/` | POST | Add repo |
| `/vulnerabilities/` | GET | List vulnerabilities |
| `/vulnerabilities/stats` | GET | Vulnerability stats |
| `/agents/` | GET | List AI agents |
| `/agents/{id}/run` | POST | Run agent |

## Project Structure

```
PatchFlow/
├── frontend/          # Next.js marketing website
├── backend/           # FastAPI core API
│   ├── api/routes/    # API endpoints
│   ├── models/        # Database models
│   └── core/          # Config & database
├── agents/            # AI Agent system
│   ├── triage/        # Triage Agent
│   └── code_fix/      # Code Fix Agent
├── infrastructure/    # IaC & K8s manifests
└── docker-compose.yml
```

## Troubleshooting

**Port conflicts?**
- Frontend: Change in `docker-compose.yml` (default 3000)
- Backend: Change in `docker-compose.yml` (default 8000)

**Database connection issues?**
- Ensure PostgreSQL is running: `docker-compose logs postgres`
- Check DATABASE_URL in `.env`

**Need help?**
- Check API docs at http://localhost:8000/docs
- Review logs: `docker-compose logs -f backend`

---

**Status:** MVP Foundation Complete ✨  
**Next:** Week 2 - GitHub Integration & Scanner Setup
