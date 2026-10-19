Prepare and transfer the Axis Agent project via Google Drive

1) Create package (on source machine)

- Windows (PowerShell):

```powershell
cd path\to\agent
python -m pip install -r requirements.txt
python prepare_package.py
# or
./package.ps1
```

- macOS / Linux:

```bash
cd /path/to/agent
python3 -m pip install -r requirements.txt
python3 prepare_package.py
# or
./package.sh
```

2) Upload
- Upload the generated zip file (name like `axis-agent-YYYYMMDDTHHMMSSZ.zip`) to Google Drive.
- Set sharing permissions as needed.

3) On the target machine (recipient)
- Download and unzip the archive.
- Open the folder in VS Code:
  - `File -> Open Folder` -> select the project directory.
- Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

4) Run quick tests / demo
- Simulated dry-run (no network changes):

```powershell
python agent.py --dry-run --simulate -c config.yaml
```

- For real network runs ensure your machine can reach the camera subnet, and follow the README.md instructions.

5) Contributing in VS Code
- Use the provided `.vscode/tasks.json` to run install/test tasks quickly.
- Commit changes to Git before uploading new archives if you want versioned updates.

Security
- Remove any sensitive credentials before uploading publicly.
- Use Drive's restricted sharing and rotate credentials after transfer if needed.
