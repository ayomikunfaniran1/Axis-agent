Axis Camera IP Automation Agent

Overview
- Lightweight agent to apply VLAN settings to Axis cameras from a YAML matrix.
- Supports dry-run mode, rollback, and an offline simulation mode for safe testing.

Quickstart

1. Create or edit your `matrix.yaml` with cameras (see `matrix_sim.yaml` example).
2. Install deps:

```powershell
python -m pip install -r requirements.txt
```

3. Dry-run (no changes):

```powershell
python agent.py --dry-run -c config.yaml
```

4. Simulated offline dry-run (no network):

```powershell
python agent.py --dry-run --simulate -c config.yaml
```

5. Rollback last action:

```powershell
python agent.py --rollback 1 -c config.yaml
```

Docker

- Build (requires Docker daemon):

```powershell
docker build -t axis-agent:latest .
```

- Run:

```powershell
docker run --rm -v %cd%:/app axis-agent:latest --dry-run -c config.yaml
```

Notes
- `matrix_sim.yaml` is provided for offline testing.
- The agent uses best-effort restore and conservative operations; test thoroughly before running in production.
