#!/usr/bin/env python3
import argparse, json, os, sys, tempfile, zipfile, requests
from auth import get_token

def create_workspace(token, workspace_name):
    """Create a new workspace if it doesn't exist"""
    print(f"🏗️  Creating new workspace: {workspace_name}")
    
    url = "https://api.powerbi.com/v1.0/myorg/groups"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "name": workspace_name
    }
    
    response = requests.post(url, headers=headers, json=data)
    if response.status_code in [200, 201]:
        workspace = response.json()
        print(f"✅ Workspace created successfully: {workspace['id']}")
        return workspace['id']
    else:
        print(f"❌ Failed to create workspace: {response.status_code}")
        print(response.text)
        return None

def get_or_create_workspace(token, target_name=None, target_id=None):
    """Get workspace ID, create if doesn't exist"""
    print("🔍 Searching for accessible workspaces...")
    
    url = "https://api.powerbi.com/v1.0/myorg/groups"
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"❌ Failed to fetch workspaces: {response.status_code} {response.text}")
        return None
    
    workspaces = response.json().get("value", [])
    print(f"📋 Found {len(workspaces)} accessible workspaces:")
    
    for ws in workspaces:
        print(f"  - '{ws['name']}' (ID: {ws['id']})")
        
        # Check if this matches what we're looking for
        if target_id and ws['id'] == target_id:
            print(f"✅ Found target workspace by ID: {ws['name']}")
            return ws['id']
        
        if target_name and ws['name'].lower() == target_name.lower():
            print(f"✅ Found target workspace by name: {ws['name']}")
            return ws['id']
    
    # If we get here, workspace wasn't found
    if target_name:
        print(f"⚠️  Workspace '{target_name}' not found. Creating it...")
        return create_workspace(token, target_name)
    
    # If no target name and we have workspaces, use the first one
    if workspaces:
        first_ws = workspaces[0]
        print(f"⚠️  Using first available workspace: {first_ws['name']}")
        return first_ws['id']
    
    print("❌ No workspaces available and cannot create one")
    return None

def import_pbix(token, workspace_id, pbix_path, dataset_display_name):
    """Import PBIX file to Power BI"""
    headers = {'Authorization': f'Bearer {token}'}
    url = f'https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/imports?datasetDisplayName={dataset_display_name}&nameConflict=CreateOrOverwrite'
    
    print(f"📤 Uploading to: {url}")
    
    with open(pbix_path, 'rb') as f:
        files = {'file': (os.path.basename(pbix_path), f, 'application/octet-stream')}
        response = requests.post(url, headers=headers, files=files)
    
    print(f"📤 Upload response: {response.status_code}")
    if response.status_code not in (200, 201, 202):
        print(f"❌ Upload failed: {response.text}")
        raise Exception(f'Import failed: {response.status_code} {response.text}')
    
    result = response.json()
    print(f"✅ Upload successful: {result}")
    return result

def wait_for_dataset(token, workspace_id, dataset_name, timeout=120):
    """Wait for dataset to be available after import"""
    import time
    
    headers = {'Authorization': f'Bearer {token}'}
    url = f'https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets'
    
    elapsed = 0
    print(f"⏳ Waiting for dataset '{dataset_name}' to be ready...")
    
    while elapsed < timeout:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            datasets = response.json().get('value', [])
            for ds in datasets:
                if ds.get('name') == dataset_name:
                    print(f"✅ Dataset ready: {ds['id']}")
                    return ds['id']
        
        print(f"⏳ Still waiting... ({elapsed}s/{timeout}s)")
        time.sleep(10)
        elapsed += 10
    
    raise Exception('Dataset not found after import timeout')

def convert_pbip_to_pbix(pbip_project_path):
    """Convert PBIP project to PBIX by zipping the project contents"""
    print(f"📦 Converting PBIP project at: {pbip_project_path}")
    
    if pbip_project_path.endswith('.pbip'):
        project_dir = os.path.dirname(pbip_project_path)
    else:
        project_dir = pbip_project_path
    
    print(f"📁 Project directory: {project_dir}")
    
    if not os.path.exists(project_dir):
        raise FileNotFoundError(f"Project directory not found: {project_dir}")
    
    print("📋 Project contents:")
    for item in os.listdir(project_dir):
        item_path = os.path.join(project_dir, item)
        if os.path.isdir(item_path):
            print(f"  📁 {item}/")
        else:
            print(f"  📄 {item}")
    
    temp_pbix = tempfile.NamedTemporaryFile(suffix='.pbix', delete=False)
    temp_pbix.close()
    
    try:
        with zipfile.ZipFile(temp_pbix.name, 'w', zipfile.ZIP_DEFLATED) as pbix_zip:
            for root, dirs, files in os.walk(project_dir):
                for file in files:
                    if file.endswith('.pbip'):
                        continue
                    
                    file_path = os.path.join(root, file)
                    arc_name = os.path.relpath(file_path, project_dir)
                    print(f"📦 Adding to PBIX: {arc_name}")
                    pbix_zip.write(file_path, arc_name)
        
        print(f"✅ PBIX created successfully: {temp_pbix.name}")
        return temp_pbix.name
        
    except Exception as e:
        if os.path.exists(temp_pbix.name):
            os.unlink(temp_pbix.name)
        raise e

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--env', choices=['dev','prod'], required=True)
    p.add_argument('--pbix', required=True, help='Path to PBIP project or PBIX file')
    args = p.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg_path = os.path.join(repo_root, 'config', f"{args.env}.json")
    
    print(f"📁 Loading config from: {cfg_path}")
    with open(cfg_path, 'r') as f:
        cfg = json.load(f)

    tenant = cfg['tenantId']
    client = cfg['clientId'] 
    secret = cfg['clientSecret']
    workspace_id = cfg.get('workspaceId')
    workspace_name = cfg.get('workspaceName')
    dw_conn = cfg['warehouseConnection']
    dw_name = cfg['warehouseName']
    report_name = cfg.get('reportName', 'Demo Report')

    print(f"🔧 Configuration:")
    print(f"  Environment: {args.env}")
    print(f"  Target Workspace ID: {workspace_id}")
    print(f"  Target Workspace Name: {workspace_name}")
    print(f"  Report Name: {report_name}")

    print('\n🔑 Acquiring token...')
    token = get_token(tenant, client, secret)
    print('✅ Token acquired successfully!')

    print('\n🎯 Resolving workspace...')
    ws_id = get_or_create_workspace(token, workspace_name, workspace_id)
    
    if not ws_id:
        print("❌ Could not resolve or create workspace")
        sys.exit(1)
    
    print(f'✅ Using workspace: {ws_id}')

    # Convert PBIP to PBIX
    pbix_file = None
    cleanup_required = False
    
    try:
        if args.pbix.endswith('.pbip') or os.path.isdir(args.pbix):
            print('\n📦 Converting PBIP project to PBIX...')
            pbix_file = convert_pbip_to_pbix(args.pbix)
            cleanup_required = True
        elif args.pbix.endswith('.pbix') and os.path.exists(args.pbix):
            pbix_file = args.pbix
        else:
            base_path = args.pbix.replace('.pbix', '')
            if os.path.exists(base_path):
                print(f'📦 Converting PBIP project to PBIX...')
                pbix_file = convert_pbip_to_pbix(base_path)
                cleanup_required = True
            else:
                raise FileNotFoundError(f"Neither PBIX file nor PBIP project found at: {args.pbix}")

        print(f'\n📤 Importing PBIX to Power BI...')
        import_result = import_pbix(token, ws_id, pbix_file, report_name)
        
        print('\n⏳ Waiting for dataset...')
        ds_id = wait_for_dataset(token, ws_id, report_name)
        
        print('\n🎉 DEPLOYMENT COMPLETED SUCCESSFULLY! 🎉')
        print(f"📊 Report: {report_name}")
        print(f"🏢 Workspace: {ws_id}")
        print(f"📈 Dataset: {ds_id}")

    except Exception as e:
        print(f'\n❌ Deployment failed: {str(e)}')
        raise
    finally:
        if cleanup_required and pbix_file and os.path.exists(pbix_file):
            os.unlink(pbix_file)
            print('🧹 Temporary PBIX file cleaned up.')

if __name__ == '__main__':
    main()