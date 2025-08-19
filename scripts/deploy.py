import requests, json, time
def get_workspace_id(token, workspace_id=None, workspace_name=None):
    # ✅ If WorkspaceID is already provided, use it directly
    if workspace_id:
        print(f"Using provided WorkspaceID: {workspace_id}")
        return workspace_id

    # Otherwise, resolve by name
    url = "https://api.powerbi.com/v1.0/myorg/groups"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    workspaces = response.json().get("value", [])

    for ws in workspaces:
        if workspace_name and ws["name"].lower() == workspace_name.lower():
            print(f"Resolved Workspace '{workspace_name}' to ID: {ws['id']}")
            return ws["id"]

    raise Exception(f"Workspace not found (Name: {workspace_name}, ID: {workspace_id})")

def import_pbix(access_token, workspace_id, pbix_path, dataset_display_name):
    headers={'Authorization':f'Bearer {access_token}'}
    url=f'https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/imports?datasetDisplayName={dataset_display_name}&nameConflict=CreateOrOverwrite'
    with open(pbix_path,'rb') as f:
        files={'file': (pbix_path, f, 'application/octet-stream')}
        r=requests.post(url, headers=headers, files=files)
    if r.status_code not in (200,201):
        raise Exception(f'Import failed: {r.status_code} {r.text}')
    return r.json()

def wait_for_dataset(access_token, workspace_id, dataset_name, timeout=120):
    headers={'Authorization':f'Bearer {access_token}'}
    url=f'https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets'
    elapsed=0
    while elapsed < timeout:
        r=requests.get(url, headers=headers)
        r.raise_for_status()
        ds=[d for d in r.json().get('value',[]) if d.get('name')==dataset_name]
        if ds:
            return ds[0]['id']
        time.sleep(5); elapsed+=5
    raise Exception('Dataset not found after import')

def get_datasources(access_token, workspace_id, dataset_id):
    headers={'Authorization':f'Bearer {access_token}'}
    url=f'https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/datasources'
    r=requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json().get('value',[])

def update_datasources(access_token, workspace_id, dataset_id, updates):
    headers={'Authorization':f'Bearer {access_token}','Content-Type':'application/json'}
    url=f'https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/Default.UpdateDatasources'
    body={'updateDetails': updates}
    r=requests.post(url, headers=headers, data=json.dumps(body))
    r.raise_for_status()
    return r.json()

def build_update_requests(datasources, dw_connection, dw_name, username=None, password=None):
    updates=[]
    for ds in datasources:
        selector={}
        if 'datasourceId' in ds:
            selector['datasourceId']=ds['datasourceId']
        selector['datasourceType']=ds.get('datasourceType')
        conn_details={}
        conn_details['connectionString']=f'powerbi://{dw_connection};Initial Catalog={dw_name}'
        cred=None
        if username and password:
            cred={
                'credentialType':'Basic',
                'basicCredentials':{'username':username,'password':password},
                'credentialsEncrypted':False
            }
        updates.append({
            'datasourceSelector': selector,
            'connectionDetails': conn_details,
            'credentialDetails': cred
        })
    return updates
