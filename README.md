# Lights On, Nobody Home

A full-stack university electricity-wastage reporting and management starter application.

## Homepage visuals
- The public landing page uses the classroom photograph supplied for this project, stored locally at `frontend/public/images/classroom-observation.png`.
- The homepage has an alternating zig-zag image/text layout, feature ribbon, four-step process, and responsive green-and-cream styling.

## Stack
- Frontend: React, Vite, React Router, plain CSS, Lucide React, Recharts
- Backend: FastAPI, SQLAlchemy, PostgreSQL, JWT, Argon2
- API docs: `http://localhost:8000/docs`

## Quick start

### 1. Backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate | macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set DATABASE_URL and SECRET_KEY in .env. For local development you may use SQLite:
# DATABASE_URL=sqlite:///./lights_on.db
uvicorn app.main:app --reload
```
The API creates tables on startup for convenient local evaluation. Alembic configuration is included for migration workflows.

### 2. Frontend
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```
Open the Vite URL printed in the terminal. The frontend expects the API at `http://localhost:8000` by default.

## First admin account
For safety, public registration always creates a **student** account. Create the first administrator directly in the database using the provided helper:
```bash
cd backend
python create_admin.py --name "Project Admin" --email admin@example.com --password "ChangeMe123!"
```
Run it after installing dependencies and configuring `.env`. Staff accounts and area assignments can then be created from the admin panel.

## Core workflow
1. Admin creates buildings and areas, then creates staff accounts and assigns staff to areas.
2. A student submits a report for an area.
3. The backend looks up the area's active assignment and assigns the report.
4. Assigned staff updates the status and adds resolution remarks.
5. The student sees the status and history; dashboard metrics update from database records.

## Scope and limitations
This version implements the reporting and management workflow. It does **not** switch lights off or detect occupancy. IoT/sensor integration is a future extension. Email/SMS/push delivery is not configured; notifications are stored in-app. File uploads are stored locally under `backend/uploads` for development and should be moved to private object storage for production. Before deployment, configure HTTPS, a strong secret, backups, rate limiting, production migrations and institution-approved account provisioning.

## Preventive energy-management features (first version)
The first version now includes preventive features alongside issue reporting:

- **Room closing checklist:** students and authorized staff can record whether lights, fans, AC and the room itself were checked before leaving. Students can see their own entries; staff can see entries for assigned areas; admins can see all entries.
- **Daily energy inspection:** staff record whether lights, fans or AC were left on in an apparently unoccupied space, with notes. Staff are restricted to their assigned areas.
- **Awareness campaigns:** admins can publish campaigns; students and staff can join with a recorded pledge. Duplicate pledges are prevented.
- **Energy dashboard:** admins can view recorded checklist, inspection, issue and campaign participation counts.
- **Awareness tips:** existing tips remain available, with admin publishing controls.

The public homepage now includes a visual impact gallery and an explanation of why prevention matters, followed by the room checklist, inspection and awareness initiatives. The provided classroom photograph is retained, and additional locally stored image crops are included in `frontend/public/images`.

### New API endpoints
- `POST/GET /api/checklists`
- `POST/GET /api/inspections`
- `GET/POST /api/campaigns`
- `POST /api/campaigns/{campaign_id}/pledge`
- `GET /api/energy/overview` (admin only)

New database tables: `room_checklists`, `energy_inspections`, `energy_campaigns`, and `campaign_pledges`. A migration file `0002_preventive_energy.py` is included. The development app also creates missing tables on startup.

**Measurement note:** dashboard counts represent recorded platform activity. They must not be presented as kWh saved, money saved or verified carbon reduction because no electricity meter/sensor data is integrated in this first version.
