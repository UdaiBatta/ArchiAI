# ArchiAI — AI-Powered Architectural Design Platform

A full-stack platform for **deterministic bylaw-compliant architectural planning**, **AI-driven layout generation**, **real-time collaboration**, and **professional exports**. Features a modern browser-based UI for designing, visualizing, and exporting architectural layouts with intelligent compliance checking.

## 🎯 What's New (May 2026)

### ✨ Professional Design Studio
- **Browser-based design interface** with ChatGPT-style prompt input
- **Real-time 3D visualization** of generated layouts using CSS 3D transforms
- **Live project management** — create, save, load, and delete designs
- **Interactive layers panel** with visibility toggles, selection, and object inspector
- **Professional export workflow** — PDF reports, DXF for CAD, JSON, screenshots, and project downloads
- **Compliance dashboard** — instant bylaw validation with pass/fail/warning indicators
- **Responsive dark theme** with glass-morphism UI and smooth animations

### 🔌 Real-Time Collaboration
- **WebSocket support** with JWT authentication for instant design updates
- **Progress broadcasting** — watch designs generate in real-time
- **Revisions tracking** — all design iterations are saved
- **Comments system** — add feedback and notes to projects
- **Share links** — collaborate with team members without account registration

### 📊 Enhanced Exports
- **PDF reports** with geometry, compliance, and statistics using ReportLab
- **DXF exports** for CAD integration (AutoCAD, Revit compatibility)
- **JSON outputs** — structured data for integrations and archival
- **Background job tracking** — async processing with retry logic and timeouts

---

## 🚀 Quick Start (Windows)

### Backend Setup

1. Open **PowerShell** and navigate to the backend folder:

   \\\powershell
   cd "D:\My projects\Archi3D\backend"
   \\\

2. Install dependencies:

   \\\powershell
   uv sync
   \\\

3. Apply database migrations:

   \\\powershell
   uv run python manage.py migrate
   \\\

4. Start the development server:

   \\\powershell
   uv run python manage.py runserver 127.0.0.1:8000
   \\\

5. Open your browser:

   - **http://127.0.0.1:8000/api/v1/health/studio/** — Archi3D Design Studio (full UI)
   - **http://127.0.0.1:8000/api/v1/health/** — API health check (database, knowledge, services)

### Frontend Setup (Optional - for custom UI development)

\\\ash
cd "D:\My projects\Archi3D\frontend"

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
\\\

### Troubleshooting

- **\python\ not found**: Use \uv run python ...\ after \uv sync\ or activate the virtual environment
- **Wrong directory**: Ensure you're in the folder containing \manage.py\ (the \ackend\ folder)
- **Port already in use**: Try \uv run python manage.py runserver 127.0.0.1:8001\
- **PowerShell compatibility**: Use \;\ to chain commands instead of \&&\

### Quick API Test (PowerShell)

\\\powershell
\ = @{
  raw_text = "Design a 2-floor residential house in Mumbai on a 30x40m plot with parking."
  region = "india_mumbai"
  building_type = "residential"
  plot_width_m = 30
  plot_depth_m = 40
  num_floors = 2
  num_units = 1
  plot_facing_direction = "north"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/design/" -Method Post -ContentType "application/json" -Body \
\\\

---

## 📚 Setup & Testing

### Development Commands

\\\ash
# Install dependencies with lockfile
uv sync

# Run database migrations
uv run python manage.py migrate

# Start development server
uv run python manage.py runserver 127.0.0.1:8000

# Run all tests
uv run pytest -q
\\\

### Test Specific Features

\\\ash
# User authentication
uv run pytest tests/test_accounts.py -q

# Project management (CRUD, collaborators, revisions)
uv run pytest tests/test_projects.py -q

# Real-time WebSocket updates
uv run pytest tests/test_consumers.py -q

# PDF/DXF exports and reports
uv run pytest tests/test_reports.py -q
\\\

---

## 🎨 Browser-Based UI Features

### Design Studio (\/api/v1/health/studio/\)

The modern design studio includes:

- **Prompt input bar** — Enter design requirements in natural language with smart suggestions
- **Design generation** — Generate, improve, and regenerate layouts with one click
- **3D visualization** — Interactive zone visualization with selection, panning, and rotation
- **Layers panel** — Manage visibility, lock states, and object properties
- **Inspector panel** — View and edit room dimensions, area, and metadata
- **Compliance panel** — See all bylaw validation results at a glance
- **Export modal** — Choose format (PDF, DXF, JSON, screenshot) and download
- **Settings modal** — Configure project name, description, region, and preferences
- **Load modal** — Browse and open previously saved designs
- **Toast notifications** — Instant feedback on all operations
- **Toolbar** — Floor selector, view controls (2D/3D/Top/Frame/Grid), and reset

### Key UI Components

- **Top bar** — Project info and status indicator
- **Left panel** — Prompt input and design settings (collapsible)
- **Center canvas** — 3D room visualization
- **Right panel** — Layers, inspector, and statistics (collapsible)
- **Bottom toolbar** — Quick access to tools (Select, Move, Rotate, Scale, Delete, Duplicate)
- **Modals** — Export, settings, compliance, load project dialogs

---

## 🔌 API Reference

### Design Generation

Generate a new architectural layout from text requirements:

\\\ash
POST /api/v1/design/

Request:
{
  "raw_text": "Design a 2-floor residential house in Mumbai on a 30x40m plot",
  "region": "india_mumbai",
  "building_type": "residential",
  "plot_width_m": 30,
  "plot_depth_m": 40,
  "num_floors": 2,
  "num_units": 1,
  "plot_facing_direction": "north"
}

Response:
{
  "session_id": "uuid",
  "parsed_input": { ... },
  "design_output": {
    "zones": [ ... ],
    "connections": [ ... ],
    "compliance_result": { ... }
  },
  "pdf_path": "outputs/report_<seed>.pdf",
  "dxf_path": "outputs/design_<seed>.dxf",
  "json_path": "outputs/hypar_<seed>.json"
}
\\\

### Project Management

\\\
GET/POST /api/v1/projects/                    # List and create projects
GET/PUT/DELETE /api/v1/projects/<id>/         # Retrieve, update, delete
POST /api/v1/projects/<id>/collaborators/     # Add team members
GET /api/v1/projects/<id>/revisions/          # Access version history
POST /api/v1/projects/<id>/comments/          # Add comments
GET /api/v1/projects/<id>/share-link/         # Generate shareable links
\\\

### Background Jobs

\\\
POST /api/v1/design/hypar/bridge/jobs/        # Submit async export job
GET /api/v1/design/jobs/<job_id>/             # Check job status
GET /api/v1/design/jobs/?limit=20             # List recent jobs
\\\

### Knowledge Ingestion

\\\
POST /api/v1/design/ingestion/jobs/           # Ingest knowledge documents
GET /api/v1/design/jobs/<job_id>/             # Check ingestion status
\\\

---

## 🏗️ Project Architecture

\\\
archi3d/
├── backend/
│   ├── apps/
│   │   ├── accounts/          # User authentication
│   │   ├── design/            # Design generation & job tracking
│   │   ├── projects/          # Project management & collaboration
│   │   ├── reports/           # PDF/DXF generation
│   │   └── health/            # Health checks & studio UI
│   ├── archi3d/
│   │   ├── settings/          # Django settings (base/dev/prod)
│   │   ├── urls.py            # URL routing
│   │   ├── asgi.py            # Daphne ASGI server
│   │   ├── routing.py         # WebSocket routing
│   │   └── celery.py          # Async task queue
│   ├── bylaws/                # Regional bylaw data (YAML)
│   ├── knowledge/             # RAG corpus and ingested documents
│   ├── outputs/               # Generated designs and exports
│   ├── scripts/               # Utility scripts
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/        # React/Vue components
│   │   ├── pages/             # Page layouts
│   │   ├── styles/            # CSS/SCSS
│   │   └── api.js             # API integration
│   ├── public/                # Static assets
│   ├── package.json
│   └── vite.config.js
│
├── README.md
├── DEVELOPER_GUIDE.md
├── FRONTEND_SETUP_GUIDE.md
└── LICENSE
\\\

---

## 🔐 Technology Stack

**Backend:**
- Django 4.2 + Django REST Framework (DRF)
- Daphne ASGI server for WebSocket support
- Django Channels for real-time communication
- Redis for caching and job queue
- Celery for async task processing
- JWT authentication with secure token storage

**Frontend:**
- Modern browser-based UI (HTML/CSS/JavaScript)
- CSS 3D transforms for interactive visualization
- Fetch API for REST communication
- WebSocket for real-time updates
- Glass-morphism and modern CSS design

**Data & Export:**
- ReportLab for PDF generation with custom styling
- ezdxf for DXF export with CAD compatibility
- SQLite (development) / PostgreSQL (production)
- JSON for inter-system communication

**Knowledge & Intelligence:**
- Vectorless retriever with region/building-type scoping
- Ollama integration for local LLM inference
- RAG (Retrieval-Augmented Generation) for design explanations
- Regional bylaw engine with compliance checking

---

## ✨ Core Capabilities

### Layout Generation
- AI-driven zone creation based on natural language requirements
- Automatic compliance checking against regional bylaws
- Structural feasibility validation
- Optimization for circulation and accessibility

### Multi-Format Exports
- **PDF**: Professional reports with geometry, statistics, and compliance data
- **DXF**: CAD-compatible format for integration with design tools
- **JSON**: Structured data for programmatic access and integrations
- **Screenshots**: High-quality visualization captures

### Collaboration
- Real-time updates across multiple users
- Project sharing with role-based access
- Design revision history with rollback
- Comment threads on design elements

### Compliance Intelligence
- Automated bylaw validation against regional standards
- Detailed pass/fail/warning indicators
- Compliance report generation
- Support for multiple regions (India - Delhi, Mumbai, NCR; US - NYC; International)

---

## 🗺️ Completed Features ✅

- ✅ Professional browser-based design studio with full UI
- ✅ Django backend with project management system
- ✅ WebSocket support for real-time collaboration
- ✅ PDF and DXF export capabilities
- ✅ Background job tracking with retry logic
- ✅ User authentication and account management
- ✅ Multi-region bylaw compliance engine
- ✅ Knowledge ingestion pipeline
- ✅ Production-ready database setup

---

## 🚀 Roadmap — Future Enhancements

### Immediate Priority (Q2 2026)

1. **Enhanced Compliance Engine**
   - Corridor width validation and routing
   - Stair core continuity across floors
   - Service shaft and MEP routing verification
   - Fire safety and egress calculations
   - FSI (Floor Space Index) optimization

2. **Knowledge Expansion**
   - Additional Indian regions (Bangalore, Hyderabad, Pune, Chennai)
   - International bylaw support (UK, EU, APAC regions)
   - Architecture reference books (Neufert, Time-Saver Standards, NBC codes)
   - Building type-specific knowledge bases

3. **UI/UX Improvements**
   - Full 3D rendering with Three.js for better visualization
   - Section cuts and elevation views
   - Material and lighting preview
   - Undo/redo functionality with history panel
   - Keyboard shortcuts for power users

4. **Advanced Design Tools**
   - Manual zone adjustment and repositioning
   - Dimension fine-tuning
   - Custom zone types and properties
   - Design templates for quick starts

### Medium-term (Q3-Q4 2026)

5. **Real-time Collaboration Enhancements**
   - Multi-user simultaneous editing
   - Design versioning and branching
   - Role-based permissions (viewer, editor, owner)
   - Audit logs and change tracking
   - Conflict resolution for concurrent edits

6. **Advanced Visualization**
   - Full 3D model rendering with textures
   - Augmented Reality (AR) preview on mobile
   - Virtual Reality (VR) walkthrough support
   - Photorealistic rendering options

7. **Integration & API**
   - Hypar Elements API integration for geometry export
   - Direct Revit plugin for BIM integration
   - SketchUp plugin for design browsing
   - BIM360 and Construction Cloud integration
   - Third-party CAD tool plugins

8. **Data & Analytics**
   - Design performance metrics dashboard
   - Project analytics and statistics
   - Usage patterns and design trends
   - Client reporting and portfolio management

### Long-term (2027+)

9. **SaaS Platform**
   - Subscription tiers (free, professional, enterprise)
   - Multi-team management and organization support
   - Enterprise SSO and access controls
   - Usage analytics and billing dashboard
   - API marketplace for third-party integrations

10. **AI Model Improvements**
    - Custom model fine-tuning on architectural dataset
    - Region-specific design model variants
    - Machine learning-based design optimization
    - Automated design quality scoring
    - A/B testing framework for algorithm improvements

11. **Mobile Experience**
    - Native iOS/Android mobile apps
    - Offline-first architecture with local caching
    - Mobile-optimized design review interface
    - AR visualization on mobile devices
    - Quick project sharing and preview

12. **Advanced Features**
    - Parametric design support
    - Design pattern libraries and templates
    - Collaborative mood boards and inspiration
    - Cost estimation integration
    - Sustainability and green building scoring

---

## 📖 Documentation

- [Frontend Setup Guide](FRONTEND_SETUP_GUIDE.md) — Browser UI development, build, and deployment
- [Developer Guide](DEVELOPER_GUIDE.md) — Architecture, coding standards, and contribution guidelines
- [Backend Roadmap](backend/IMPLEMENTATION_ROADMAP.md) — Detailed implementation plan
- [Collaboration Handoff](backend/COLLABORATION_HANDOFF.md) — Team workflow and git practices

---

## 🤝 Contributing

We welcome contributions! Please refer to [Developer Guide](DEVELOPER_GUIDE.md) for:
- Code style and best practices
- Testing requirements and coverage
- Pull request workflow
- Setting up development environment
- Architecture and design patterns

---

## 📄 License

See [LICENSE](backend/LICENSE) file for licensing details.

---

**Made with ❤️ for architects and designers**
