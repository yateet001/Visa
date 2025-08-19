#!/usr/bin/env python3
import argparse, json, os, sys, tempfile, zipfile
from auth import get_token
from deploy import import_pbix, wait_for_dataset, get_workspace_id, get_datasources, build_update_requests, update_datasources

def create_pbix_from_pbip(pbip_path):
    """
    Convert PBIP project to PBIX format by creating a zip file
    This is a simplified conversion - for production use, consider using Power BI CLI
    """
    pbip_dir = os.path.dirname(pbip_path)
    
    # Create a temporary PBIX file
    temp_pbix = tempfile.NamedTemporaryFile(suffix='.pbix', delete=False)
    temp_pbix.close()
    
    try:
        with zipfile.ZipFile(temp_pbix.name, 'w', zipfile.ZIP_DEFLATED) as pbix_zip:
            # Add all files from the PBIP project directory
            for root, dirs, files in os.walk(pbip_dir):
                for file in files:
                    if file.endswith('.pbip'):
                        continue  # Skip the .pbip file itself
                    
                    file_path = os.path.join(root, file)
                    arc_name = os.path.relpath(file_path, pbip_dir)
                    pbix_zip.write(file_path, arc_name)
        
        return temp_pbix.name
    except Exception as e:
        os.unlink(temp_pbix.name)
        raise e

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--env', choices=['dev','prod'], required=True)
    p.add_argument('--pbip', required=True, help='Path to PBIP file to convert and import')
    args = p.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg_path = os.path.join(repo_root, 'config', f"{args.env}.json")
    
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
    print('Workspace id:', ws_id)

    # Convert PBIP to PBIX
    print('Converting PBIP to PBIX...')
    pbix_file = None
    try:
        pbix_file = create_pbix_from_pbip(args.pbip)
        print(f'PBIX created at: {pbix_file}')

        print('Importing PBIX...')
        import_pbix(token, ws_id, pbix_file, report_name)
        print('Waiting for dataset...')
        ds_id = wait_for_dataset(token, ws_id, report_name)
        print('Dataset id:', ds_id)

        print('Fetching datasources...')
        datasources = get_datasources(token, ws_id, ds_id)
        print('Datasources:', datasources)
        updates = build_update_requests(datasources, dw_conn, dw_name, username=None, password=None)
        print('Updating datasources to point to DW...')
        res = update_datasources(token, ws_id, ds_id, updates)
        print('Update response:', res)
        print('Deployment completed.')

    finally:
        # Clean up temporary PBIX file
        if pbix_file and os.path.exists(pbix_file):
            os.unlink(pbix_file)
            print('Temporary PBIX file cleaned up.')

if __name__ == '__main__':
    main()