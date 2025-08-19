#!/usr/bin/env python3
import argparse, json, os, sys, tempfile, zipfile, requests, time, subprocess, shutil, glob
from auth import get_token

def create_proper_pbix_from_pbip(pbip_project_path):
    """Build a valid PBIX using pbi-tools from a PBIP project or return the path if PBIX is provided.

    This relies on the official pbi-tools CLI to construct a correct PBIX structure.
    """
    print(f"📦 Preparing PBIX from input: {pbip_project_path}")

    # If a PBIX file is already provided, use it as-is
    if pbip_project_path.lower().endswith('.pbix') and os.path.isfile(pbip_project_path):
        print("📄 PBIX provided directly; skipping build")
        return pbip_project_path

    # Determine PBIP project directory
    project_dir = (
        os.path.dirname(pbip_project_path)
        if pbip_project_path.lower().endswith('.pbip')
        else pbip_project_path
    )
    print(f"📁 Project directory: {project_dir}")

    if not os.path.isdir(project_dir):
        raise FileNotFoundError(f"PBIP project directory not found: {project_dir}")

    # Ensure expected subfolders exist (basic sanity)
    expected_report_dir = os.path.join(project_dir, "Demo Report.Report")
    expected_model_dir = os.path.join(project_dir, "Demo Report.SemanticModel")
    if not os.path.exists(expected_report_dir) or not os.path.exists(expected_model_dir):
        print("⚠️ Expected Report/SemanticModel folders not found. Proceeding regardless.")

    # Locate pbi-tools
    pbi_tools_exe = shutil.which('pbi-tools') or os.path.expanduser('~/.dotnet/tools/pbi-tools')
    if not os.path.exists(pbi_tools_exe):
        raise RuntimeError(
            "pbi-tools not found. Ensure it is installed and on PATH (dotnet tool install -g pbi-tools)."
        )

    # Build into a temp output directory
    out_dir = tempfile.mkdtemp(prefix='pbitools_build_')
    print(f"🛠️ Building PBIX with pbi-tools into: {out_dir}")

    cmd_variants = [
        [pbi_tools_exe, 'build', project_dir, '--format', 'pbix', '--out', out_dir],
        [pbi_tools_exe, 'build', project_dir, '-f', 'pbix', '-o', out_dir],
    ]

    last_error_output = None
    for cmd in cmd_variants:
        print(f"➡️ Running: {' '.join(cmd)}")
        try:
            completed = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=True,
                text=True
            )
            print(completed.stdout)
            break
        except subprocess.CalledProcessError as e:
            last_error_output = e.stdout
            print(last_error_output)
    else:
        raise RuntimeError('pbi-tools build failed')

    # Find the produced PBIX
    pbix_candidates = glob.glob(os.path.join(out_dir, '*.pbix'))
    if not pbix_candidates:
        raise FileNotFoundError('pbi-tools did not produce a PBIX file')

    pbix_path = pbix_candidates[0]
    print(f"✅ PBIX built: {pbix_path} ({os.path.getsize(pbix_path)} bytes)")
    return pbix_path

def import_pbix_simple(token, workspace_id, pbix_path, dataset_display_name):
    """Upload PBIX using the official Imports API with correct query parameters."""
    headers = {'Authorization': f'Bearer {token}'}

    url = (
        f'https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/imports'
        f'?datasetDisplayName={requests.utils.quote(dataset_display_name)}'
        f'&nameConflict=Overwrite'
    )

    print(f"📤 Uploading to: {url}")
    print(f"📤 File: {pbix_path}")
    print(f"📤 File size: {os.path.getsize(pbix_path)} bytes")

    with open(pbix_path, 'rb') as f:
        files = {
            'file': (f'{dataset_display_name}.pbix', f, 'application/octet-stream')
        }
        response = requests.post(url, headers=headers, files=files, timeout=600)

    print(f"📤 Response: {response.status_code}")
    if response.status_code not in (200, 201, 202):
        raise Exception(f'Import failed: {response.status_code} {response.text}')

    result = response.json() if response.content else {"status": "success"}
    print(f"✅ Upload successful: {result}")
    return result

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--env', choices=['dev','prod'], required=True)
    p.add_argument('--pbix', required=True, help='Path to PBIP project')
    args = p.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg_path = os.path.join(repo_root, 'config', f"{args.env}.json")
    
    print(f"📁 Loading config from: {cfg_path}")
    with open(cfg_path, 'r') as f:
        cfg = json.load(f)

    workspace_id = cfg['workspaceId']
    workspace_name = cfg.get('workspaceName', 'Unknown')
    report_name = cfg.get('reportName', 'Demo Report')

    print(f"🔧 Configuration:")
    print(f"  Environment: {args.env}")
    print(f"  Workspace: {workspace_name} ({workspace_id})")
    print(f"  Report: {report_name}")

    print('\n🔑 Getting token...')
    token = get_token(cfg['tenantId'], cfg['clientId'], cfg['clientSecret'])
    print('✅ Token acquired!')

    pbix_file = None
    
    try:
        print('\n📦 Creating proper PBIX...')
        pbix_file = create_proper_pbix_from_pbip(args.pbix)

        print(f'\n📤 Importing to Power BI...')
        result = import_pbix_simple(token, workspace_id, pbix_file, report_name)
        
        print('\n🎉 SUCCESS! DEPLOYMENT COMPLETED! 🎉')
        print(f"📊 Report '{report_name}' deployed to '{workspace_name}'")
        print(f"🔗 Check your Power BI workspace: {workspace_name}")

    except Exception as e:
        print(f'\n❌ Error: {str(e)}')
        sys.exit(1)
    finally:
        if pbix_file and os.path.exists(pbix_file):
            os.unlink(pbix_file)
            print('🧹 Cleanup completed')

if __name__ == '__main__':
    main()