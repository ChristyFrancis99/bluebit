# 🛡️ Academic Integrity System

A production-ready, modular platform for detecting academic integrity violations.

**Stack:** FastAPI · React · PostgreSQL · Redis · MinIO · PyTorch (RoBERTa)

## 🚀 Quick Start

```bash
docker compose up --build
```

| Service      | URL                                     |
|--------------|-----------------------------------------|
| Frontend     | http://localhost:3000                   |
| API Docs     | http://localhost:8000/api/docs          |
| MinIO Console| http://localhost:9001 (minioadmin/minioadmin) |

### Demo Accounts (auto-seeded)
| Role          | Email                 | Password     |
|---------------|-----------------------|--------------|
| Administrator | admin@demo.edu        | admin123     |
| Educator      | educator@demo.edu     | educator123  |
| Student       | student@demo.edu      | student123   |

## 🖥️ Frontend Pages

- **Login / Register** — JWT auth with role selection
- **Submit Document** — Drag-and-drop upload, module selector, real-time WebSocket streaming of results
- **History** — Paginated list of past submissions; click any to drill into module-level evidence
- **Admin** (admin role only) — Module weight sliders, enable/disable toggles, platform stats chart, audit log

## 🔬 Analysis Modules

| Module | Default Weight | Description |
|--------|---------------|-------------|
| AI Detection | 35% | RoBERTa transformer (mock mode by default) |
| Plagiarism | 40% | MinHash LSH + SimHash cross-document similarity |
| Writing Profile | 25% | 14-feature stylometric deviation + differential privacy |
| Proctoring | 0% | Behavioral signals (paste, tab switches, idle) |

## 🔧 Local Dev (without Docker)

```bash
# Backend
pip install -r requirements.txt fakeredis
cp .env.example .env
uvicorn api.main:app --reload
python scripts/seed.py   # seed demo users

# Frontend
cd frontend
npm install
npm run dev   # http://localhost:5173
```

## 📡 API Quick Reference

```
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/submissions           (multipart: file, modules, assignment_id)
GET    /api/v1/submissions/{id}/report
GET    /api/v1/submissions/{id}/report/pdf
PUT    /api/v1/modules/{id}/toggle   (admin)
PUT    /api/v1/admin/weights         (admin)
GET    /api/v1/admin/stats           (admin)
WS     /ws/submissions/{id}          (real-time events)
```

## 🔒 Privacy

- **DP Writing Profiles**: Laplace noise (ε=1.0) before storage
- **Plagiarism fingerprinting**: One-way MinHash — raw text never shared
- **Role-based access**: student/educator/admin enforced at API level
