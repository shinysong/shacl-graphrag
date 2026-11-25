CREATE TABLE approval_events (id INTEGER PRIMARY KEY, request_id INTEGER REFERENCES approval_requests(id), actor_id INTEGER REFERENCES employees(id), decided_at TEXT, decision TEXT);

CREATE TABLE approval_requests (id INTEGER PRIMARY KEY, project_id INTEGER REFERENCES projects(id), requester_id INTEGER REFERENCES employees(id), requested_at TEXT, status TEXT);

CREATE TABLE assignments (id INTEGER PRIMARY KEY, employee_id INTEGER REFERENCES employees(id), project_id INTEGER REFERENCES projects(id), allocation_percent INTEGER);

CREATE TABLE audit_events (id INTEGER PRIMARY KEY, request_id INTEGER REFERENCES approval_requests(id), recorded_at TEXT, event_type TEXT);

CREATE TABLE dependencies (id INTEGER PRIMARY KEY, predecessor_id INTEGER REFERENCES milestones(id), successor_id INTEGER REFERENCES milestones(id), relation TEXT);

CREATE TABLE employees (id INTEGER PRIMARY KEY, team_id INTEGER REFERENCES teams(id), active INTEGER);

CREATE TABLE exceptions (id INTEGER PRIMARY KEY, project_id INTEGER REFERENCES projects(id), scope TEXT, expires_at TEXT, status TEXT);

CREATE TABLE milestones (id INTEGER PRIMARY KEY, project_id INTEGER REFERENCES projects(id), due_at TEXT, state TEXT);

CREATE TABLE projects (id INTEGER PRIMARY KEY, owner_team_id INTEGER REFERENCES teams(id), deadline TEXT);

CREATE TABLE role_grants (id INTEGER PRIMARY KEY, employee_id INTEGER REFERENCES employees(id), role_id INTEGER REFERENCES roles(id), valid_from TEXT, valid_to TEXT);

CREATE TABLE roles (id INTEGER PRIMARY KEY, name TEXT, can_approve INTEGER);

CREATE TABLE teams (id INTEGER PRIMARY KEY, name TEXT);
