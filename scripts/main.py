#!/usr/bin/env python3
import argparse, json, os, sys, tempfile, zipfile, shutil
from auth import get_token
from deploy import import_pbix, wait_for_dataset, get_workspace_id, get_datasources, build_update_requests, update_datasources

def convert_pbip_to_pbix(pbip_project_path):
    """
    Convert PBIP project to PBIX by zipping the project contents
    """
    print(f"Converting PBIP project at: {pbip_project_path}")
    
    # Get the project directory (remove .pbip extension to get folder)
    if pbip_project_path.endswith('.pbip'):
        project_dir = os.path.dirname(pbip_project_path)
    else:
        project_dir = pbip_project_path
    
    print(f"Project directory: {project_dir}")
    
    # Check if project directory exists
    if not os.path.exists(project_dir):
        raise FileNotFoundError(f"Project directory not found: {project_dir}")
    
    # List contents for debugging
    print("Project contents:")
    for item in os.listdir(project_dir):
        item_path = os.path.join(project_dir, item)
        if os.path.isdir(item_path):
            print(f"  📁 {item}/")
        else:
            print(f"  📄 {item}")
    
    # Create temporary PBIX file
    temp_pbix = tempfile.NamedTemporaryFile(suffix='.pbix', delete=False)
    temp_pbix.close()
    
    try:
        with zipfile.ZipFile(temp_pbix.name, 'w', zipfile.ZIP_DEFLATED) as pbix_zip:
            # Add all files from the project directory
            for root, dirs, files in os.walk(project_dir):
                for file in files:
                    if file.endswith('.pbip'):
                        continue  # Skip .pbip configuration files
                    
                    file_path = os.path.join(root, file)
                    # Create archive path relative to project directory
                    arc_name = os.path.relpath(file_path, project_dir)
                    print(f"Adding to PBIX: {arc_name}")
                    pbix_zip.write(file_path, arc_name)
        
        print(f"PBIX created successfully: {temp_pbix.name}")
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
    
    print(f"Loading config from: {cfg_path}")
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

    print('Acquiring token...')
    token = get_token(tenant, client, secret)
    print('Token acquired. Resolving workspace...')
    ws_id = get_workspace_id(token, workspace_id=workspace_id, workspace_name=workspace_name)
    print(f'Workspace id: {ws_id}')

    # Handle both PBIX and PBIP paths
    pbix_file = None
    cleanup_required = False
    
    try:
        if args.pbix.endswith('.pbip') or os.path.isdir(args.pbix):
            # Convert PBIP project to PBIX
            print('Converting PBIP project to PBIX...')
            pbix_file = convert_pbip_to_pbix(args.pbix)
            cleanup_required = True
        elif args.pbix.endswith('.pbix') and os.path.exists(args.pbix):
            # Use existing PBIX file
            pbix_file = args.pbix
        else:
            # Try to find PBIP project in the same directory
            base_path = args.pbix.replace('.pbix', '')
            if os.path.exists(base_path):
                print(f'PBIX file not found, but found project directory: {base_path}')
                print('Converting PBIP project to PBIX...')
                pbix_file = convert_pbip_to_pbix(base_path)
                cleanup_required = True
            else:
                raise FileNotFoundError(f"Neither PBIX file nor PBIP project found at: {args.pbix}")

        print(f'Using PBIX file: {pbix_file}')
        print('Importing PBIX...')
        import_result = import_pbix(token, ws_id, pbix_file, report_name)
        print(f'Import result: {import_result}')
        
        print('Waiting for dataset...')
        ds_id = wait_for_dataset(token, ws_id, report_name)
        print(f'Dataset id: {ds_id}')

        print('Fetching datasources...')
        datasources = get_datasources(token, ws_id, ds_id)
        print(f'Datasources: {datasources}')
        
        if datasources:
            updates = build_update_requests(datasources, dw_conn, dw_name, username=None, password=None)
            print('Updating datasources to point to DW...')
            res = update_datasources(token, ws_id, ds_id, updates)
            print(f'Update response: {res}')
        else:
            print('No datasources found to update.')
        
        print('✅ Deployment completed successfully!')

    except Exception as e:
        print(f'❌ Deployment failed: {str(e)}')
        raise
    finally:
        # Clean up temporary PBIX file if created
        if cleanup_required and pbix_file and os.path.exists(pbix_file):
            os.unlink(pbix_file)
            print('🧹 Temporary PBIX file cleaned up.')

if __name__ == '__main__':
    main()