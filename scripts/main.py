#!/usr/bin/env python3
import argparse, json, os, sys, tempfile, zipfile, requests, time
from auth import get_token

def create_proper_pbix_from_pbip(pbip_project_path):
    """Create a proper PBIX file from PBIP with exact Power BI structure"""
    print(f"📦 Converting PBIP project at: {pbip_project_path}")
    
    if pbip_project_path.endswith('.pbip'):
        project_dir = os.path.dirname(pbip_project_path)
    else:
        project_dir = pbip_project_path
    
    print(f"📁 Project directory: {project_dir}")
    
    # Find the report and model directories
    report_dir = os.path.join(project_dir, "Demo Report.Report")
    model_dir = os.path.join(project_dir, "Demo Report.SemanticModel")
    
    if not os.path.exists(report_dir):
        raise FileNotFoundError(f"Report directory not found: {report_dir}")
    if not os.path.exists(model_dir):
        raise FileNotFoundError(f"SemanticModel directory not found: {model_dir}")
    
    print("📋 Found required components")
    
    # Create temporary PBIX file
    temp_pbix = tempfile.NamedTemporaryFile(suffix='.pbix', delete=False)
    temp_pbix.close()
    
    try:
        with zipfile.ZipFile(temp_pbix.name, 'w', zipfile.ZIP_DEFLATED) as pbix_zip:
            
            # 1. Add Version (REQUIRED - must be first)
            pbix_zip.writestr("Version", "4.0")
            print("📄 Added Version")
            
            # 2. Add DataModelSchema (REQUIRED)
            pbix_zip.writestr("DataModelSchema", "https://developer.microsoft.com/json-schemas/analysis-services/2016/tabular-object-model.json")
            print("📄 Added DataModelSchema")
            
            # 3. Add Report/Layout from report.json
            report_json_path = os.path.join(report_dir, "report.json")
            if os.path.exists(report_json_path):
                with open(report_json_path, 'r', encoding='utf-8') as f:
                    report_content = f.read()
                pbix_zip.writestr("Report/Layout", report_content)
                print("📄 Added Report/Layout")
            
            # 4. Add DataModel from model.bim
            model_bim_path = os.path.join(model_dir, "model.bim")
            if os.path.exists(model_bim_path):
                with open(model_bim_path, 'r', encoding='utf-8') as f:
                    model_content = f.read()
                pbix_zip.writestr("DataModel", model_content)
                print("📄 Added DataModel")
            
            # 5. Add DiagramLayout
            diagram_path = os.path.join(model_dir, "diagramLayout.json") 
            if os.path.exists(diagram_path):
                with open(diagram_path, 'r', encoding='utf-8') as f:
                    diagram_content = f.read()
                pbix_zip.writestr("DiagramLayout", diagram_content)
                print("📄 Added DiagramLayout")
            
            # 6. Add Settings
            pbix_zip.writestr("Settings", '{"version":"1.0"}')
            print("📄 Added Settings")
            
            # 7. Add SecurityBindings
            security_bindings = """<Bindings xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" />"""
            pbix_zip.writestr("SecurityBindings", security_bindings)
            print("📄 Added SecurityBindings")
            
            # 8. Add Connections (if needed)
            connections = """<?xml version="1.0" encoding="utf-8"?><Connections><Connection></Connection></Connections>"""
            pbix_zip.writestr("Connections", connections)
            print("📄 Added Connections")
            
            # 9. Add Report/StaticResources if they exist
            static_resources_dir = os.path.join(report_dir, "StaticResources")
            if os.path.exists(static_resources_dir):
                for root, dirs, files in os.walk(static_resources_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_name = f"Report/{os.path.relpath(file_path, report_dir)}"
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        pbix_zip.writestr(arc_name, content)
                        print(f"📄 Added {arc_name}")
        
        file_size = os.path.getsize(temp_pbix.name)
        print(f"✅ PBIX created successfully: {temp_pbix.name}")
        print(f"📏 File size: {file_size} bytes")
        
        # Verify it's a valid zip
        try:
            with zipfile.ZipFile(temp_pbix.name, 'r') as test_zip:
                file_list = test_zip.namelist()
                print(f"📋 PBIX contains {len(file_list)} files:")
                for f in file_list:
                    print(f"  - {f}")
        except Exception as e:
            raise Exception(f"Created invalid zip file: {e}")
        
        return temp_pbix.name
        
    except Exception as e:
        if os.path.exists(temp_pbix.name):
            os.unlink(temp_pbix.name)
        raise e

def import_pbix_simple(token, workspace_id, pbix_path, dataset_display_name):
    """Simple PBIX import without extra parameters"""
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'multipart/form-data'
    }
    
    # Use simpler URL without extra parameters
    url = f'https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/imports'
    
    print(f"📤 Uploading to: {url}")
    print(f"📤 File: {pbix_path}")
    print(f"📤 File size: {os.path.getsize(pbix_path)} bytes")
    
    # Remove Content-Type to let requests set it automatically for multipart
    headers = {'Authorization': f'Bearer {token}'}
    
    with open(pbix_path, 'rb') as f:
        files = {
            'file': (f'{dataset_display_name}.pbix', f, 'application/octet-stream')
        }
        data = {
            'datasetDisplayName': dataset_display_name,
            'nameConflict': 'CreateOrOverwrite'
        }
        
        response = requests.post(url, headers=headers, files=files, data=data, timeout=600)
    
    print(f"📤 Response: {response.status_code}")
    
    if response.status_code not in (200, 201, 202):
        print(f"❌ Failed: {response.text}")
        
        # Try alternative approach - direct upload
        print("🔄 Trying alternative upload method...")
        url2 = f'https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/imports?datasetDisplayName={dataset_display_name}&nameConflict=Overwrite'
        
        with open(pbix_path, 'rb') as f:
            files2 = {'file': f}
            response2 = requests.post(url2, headers=headers, files=files2, timeout=600)
        
        print(f"📤 Alternative response: {response2.status_code}")
        if response2.status_code not in (200, 201, 202):
            print(f"❌ Alternative failed: {response2.text}")
            raise Exception(f'Both import methods failed. Last error: {response2.status_code} {response2.text}')
        else:
            response = response2
    
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