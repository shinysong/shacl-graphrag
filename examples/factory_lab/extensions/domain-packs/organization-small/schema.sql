CREATE TABLE approvals (id INTEGER PRIMARY KEY, project_id INTEGER REFERENCES projects(id), approver_id INTEGER REFERENCES employees(id), decided_at TEXT, decision TEXT);

CREATE TABLE assignments (id INTEGER PRIMARY KEY, employee_id INTEGER REFERENCES employees(id), project_id INTEGER REFERENCES projects(id), valid_from TEXT, valid_to TEXT, role TEXT);

CREATE TABLE employees (id INTEGER PRIMARY KEY, team_id INTEGER REFERENCES teams(id), name TEXT, active INTEGER);

CREATE TABLE exceptions (id INTEGER PRIMARY KEY, project_id INTEGER REFERENCES projects(id), reason TEXT, expires_at TEXT);

CREATE TABLE projects (id INTEGER PRIMARY KEY, owner_team_id INTEGER REFERENCES teams(id), name TEXT, deadline TEXT);

CREATE TABLE teams (id INTEGER PRIMARY KEY, name TEXT);
