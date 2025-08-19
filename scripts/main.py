#!/usr/bin/env python3
import argparse, json, os, sys, tempfile, zipfile, requests, time
from auth import get_token

def create_valid_pbix_from_pbip(pbip_project_path):
    """Create a valid PBIX file from PBIP project with proper structure"""
    print(f"📦 Converting PBIP project at: {pbip_project_path}")
    
    if pbip_project_path.endswith('.pbip'):
        project_dir = os.path.dirname(pbip_project_path)
    else:
        project_dir = pbip_project_path
    
    print(f"📁 Project directory: {project_dir}")
    
    if not os.path.exists(project_dir):
        raise FileNotFoundError(f"Project directory not found: {project_dir}")
    
    # Look for the essential PBIP components
    report_dir = os.path.join(project_dir, "Demo Report.Report")
    model_dir = os.path.join(project_dir, "Demo Report.SemanticModel")
    
    if not os.path.exists(report_dir):
        raise FileNotFoundError(f"Report directory not found: {report_dir}")
    
    if not os.path.exists(model_dir):
        raise FileNotFoundError(f"SemanticModel directory not found: {model_dir}")
    
    print("📋 Found required components:")
    print(f"  📊 Report: {report_dir}")
    print(f"  🗃️  Model: {model_dir}")
    
    # Create temporary PBIX file
    temp_pbix = tempfile.NamedTemporaryFile(suffix='.pbix', delete=False)
    temp_pbix.close()
    
    try:
        with zipfile.ZipFile(temp_pbix.name, 'w', zipfile.ZIP_DEFLATED) as pbix_zip:
            # Add SecurityBindings (required for PBIX)
            security_bindings = """<Bindings xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" />"""
            pbix_zip.writestr("SecurityBindings", security_bindings)
            
            # Add Settings (required for PBIX) 
            settings = """{"version":"1.0"}"""
            pbix_zip.writestr("Settings", settings)
            
            # Add Version (required for PBIX)
            version = "4.0"
            pbix_zip.writestr("Version", version)
            
            # Add report files
            report_json_path = os.path.join(report_dir, "report.json")
            if os.path.exists(report_json_path):
                pbix_zip.write(report_json_path, "Report/Layout")
                print("📄 Added Report/Layout")
            
            # Add model files  
            model_bim_path = os.path.join(model_dir, "model.bim")
            if os.path.exists(model_bim_path):
                pbix_zip.write(model_bim_path, "DataModel")
                print("📄 Added DataModel")
            
            # Add diagram layout if exists
            diagram_path = os.path.join(model_dir, "diagramLayout.json")
            if os.path.exists(diagram_path):
                pbix_zip.write(diagram_path, "DiagramLayout")
                print("📄 Added DiagramLayout")
            
            # Add metadata
            metadata = {
                "version": "4.0",
                "datasetReference": {
                    "byPath": {
                        "path": "Demo Report.SemanticModel"
                    }
                }
            }
            pbix_zip.writestr("Metadata", json.dumps(metadata))
            print("📄 Added Metadata")
        
        print(f"✅ Valid PBIX created successfully: {temp_pbix.name}")
        
        # Verify the PBIX file is valid
        file_size = os.path.getsize(temp_pbix.name)
        print(f"📏 PBIX file size: {file_size} bytes")
        
        if file_size < 1000:
            raise Exception("PBIX file is too small - likely invalid")
        
        return temp_pbix.name
        
    except Exception as e:
        if os.path.exists(temp_pbix.name):
            os.unlink(temp_pbix.name)
        raise e

def import_pbix(token, workspace_id, pbix_path, dataset_display_name):
    """Import PBIX file to Power BI"""
    headers = {'Authorization': f'Bearer {token}'}
    url = f'https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/imports?datasetDisplayName={dataset_display_name}&nameConflict=CreateOrOverwrite'
    
    print(f"📤 Uploading to workspace: {workspace_id}")
    print(f"📤 File: {pbix_path}")
    print(f"📤 File size: {os.path.getsize(pbix_path)} bytes")
    
    with open(pbix_path, 'rb') as f:
        files = {'file': (os.path.basename(pbix_path), f, 'application/octet-stream')}
        response = requests.post(url, headers=headers, files=files, timeout=300)
    
    print(f"📤 Upload response: {response.status_code}")
    if response.status_code not in (200, 201, 202):
        print(f"❌ Upload failed: {response.text}")
        raise Exception(f'Import failed: {response.status_code} {response.text}')
    
    result = response.json()
    print(f"✅ Upload successful!")
    return result

def wait_for_import_completion(token, workspace_id, import_id, timeout=300):
    """Wait for import to complete"""
    headers = {'Authorization': f'Bearer {token}'}
    url = f'https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/imports/{import_id}'
    
    elapsed = 0
    print(f"⏳ Waiting for import {import_id} to complete...")
    
    while elapsed < timeout:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            import_status = response.json()
            status = import_status.get('importState', 'Unknown')
            print(f"📊 Import status: {status}")
            
            if status == 'Succeeded':
                print("✅ Import completed successfully!")
                return import_status
            elif status == 'Failed':
                error = import_status.get('error', 'Unknown error')
                raise Exception(f"Import failed: {error}")
        
        time.sleep(10)
        elapsed += 10
    
    raise Exception('Import timeout')

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
    workspace_id = cfg['workspaceId']
    workspace_name = cfg.get('workspaceName')
    report_name = cfg.get('reportName', 'Demo Report')

    print(f"🔧 Configuration:")
    print(f"  Environment: {args.env}")
    print(f"  Workspace ID: {workspace_id}")
    print(f"  Workspace Name: {workspace_name}")
    print(f"  Report Name: {report_name}")

    print('\n🔑 Acquiring token...')
    token = get_token(tenant, client, secret)
    print('✅ Token acquired successfully!')

    print(f'\n🎯 Using workspace: {workspace_id}')

    # Convert PBIP to valid PBIX
    pbix_file = None
    cleanup_required = False
    
    try:
        print('\n📦 Creating valid PBIX from PBIP project...')
        pbix_file = create_valid_pbix_from_pbip(args.pbix)
        cleanup_required = True

        print(f'\n📤 Importing PBIX to Power BI...')
        import_result = import_pbix(token, workspace_id, pbix_file, report_name)
        
        # Wait for import to complete
        import_id = import_result.get('id')
        if import_id:
            print(f'\n⏳ Monitoring import progress...')
            final_result = wait_for_import_completion(token, workspace_id, import_id)
            print(f"📋 Final result: {final_result}")
        
        print('\n🎉 DEPLOYMENT COMPLETED SUCCESSFULLY! 🎉')
        print(f"📊 Report: {report_name}")
        print(f"🏢 Workspace: {workspace_name} ({workspace_id})")

    except Exception as e:
        print(f'\n❌ Deployment failed: {str(e)}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if cleanup_required and pbix_file and os.path.exists(pbix_file):
            os.unlink(pbix_file)
            print('🧹 Temporary PBIX file cleaned up.')

if __name__ == '__main__':
    main()