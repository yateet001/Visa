#!/usr/bin/env python3
import argparse, json, os, sys
from auth import get_token
from deploy import import_pbix, wait_for_dataset, get_workspace_id, get_datasources, build_update_requests, update_datasources

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--env', choices=['dev','prod'], required=True)
    p.add_argument('--pbix', required=True, help='Path to PBIX file to import')
    args=p.parse_args()

    repo_root=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg_path=os.path.join(repo_root,'config', f"{args.env}.json")
    cfg=json.load(open(cfg_path))

    tenant=cfg['tenantId']; client=cfg['clientId']; secret=cfg['clientSecret']
    workspace_id=cfg.get('workspaceId'); workspace_name=cfg.get('workspaceName')
    dw_conn=cfg['dataWarehouse']['connection']; dw_name=cfg['dataWarehouse']['name']
    report_name=cfg.get('reportName','Demo Report')

    print('Acquiring token...')
    token=get_token(tenant, client, secret)
    print('Token acquired. Resolving workspace...')
    ws_id=get_workspace_id(token, workspace_id=workspace_id, workspace_name=workspace_name)
    print('Workspace id:', ws_id)

    print('Importing PBIX...')
    import_pbix(token, ws_id, args.pbix, report_name)
    print('Waiting for dataset...')
    ds_id=wait_for_dataset(token, ws_id, report_name)
    print('Dataset id:', ds_id)

    print('Fetching datasources...')
    datasources=get_datasources(token, ws_id, ds_id)
    print('Datasources:', datasources)
    updates=build_update_requests(datasources, dw_conn, dw_name, username=None, password=None)
    print('Updating datasources to point to DW...')
    res=update_datasources(token, ws_id, ds_id, updates)
    print('Update response:', res)
    print('Deployment completed.')

if __name__=='__main__':
    main()
