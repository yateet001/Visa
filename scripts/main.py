#!/usr/bin/env python3
import argparse, json, os, sys, tempfile, zipfile, requests, time
from auth import get_token

def validate_pbip_structure(project_dir):
    """Validate that the PBIP project has the required structure"""
    required_files = []
    report_dir = os.path.join(project_dir, "Demo Report.Report")
    model_dir = os.path.join(project_dir, "Demo Report.SemanticModel")
    
    if os.path.exists(report_dir):
        report_json = os.path.join(report_dir, "report.json")
        if os.path.exists(report_json):
            required_files.append(("Report JSON", report_json))
    
    if os.path.exists(model_dir):
        model_bim = os.path.join(model_dir, "model.bim")
        if os.path.exists(model_bim):
            required_files.append(("Model BIM", model_bim))
    
    print("📋 Validating PBIP structure:")
    for name, path in required_files:
        size = os.path.getsize(path)
        print(f"  ✅ {name}: {size} bytes")
    
    return len(required_files) >= 2  # At least report.json and model.bim

def create_minimal_pbix_for_testing():
    """Create a minimal PBIX file for testing purposes"""
    print("🧪 Creating minimal test PBIX...")
    
    temp_pbix = tempfile.NamedTemporaryFile(suffix='.pbix', delete=False)
    temp_pbix.close()
    
    try:
        with zipfile.ZipFile(temp_pbix.name, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as pbix_zip:
            
            # Essential entries in the exact order Power BI expects
            
            # 1. Version (MUST be first)
            pbix_zip.writestr("Version", "4.0")
            
            # 2. DataModelSchema (REQUIRED)
            pbix_zip.writestr("DataModelSchema", "https://developer.microsoft.com/json-schemas/analysis-services/2016/tabular-object-model.json")
            
            # 3. DataModel with proper structure
            minimal_model = {
                "compatibilityLevel": 1550,
                "model": {
                    "culture": "en-US",
                    "dataAccessOptions": {
                        "legacyRedirects": True,
                        "returnErrorValuesAsNull": True
                    },
                    "defaultPowerBIDataSourceVersion": "powerBI_V3",
                    "tables": []
                }
            }
            pbix_zip.writestr("DataModel", json.dumps(minimal_model, separators=(',', ':')))
            
            # 4. Report/Layout with proper structure
            minimal_report = {
                "config": "{\"version\":\"5.59\",\"themeCollection\":{\"baseTheme\":{\"name\":\"CY24SU10\",\"version\":\"5.61\",\"type\":2}},\"activeSectionIndex\":0,\"defaultDrillFilterOtherVisuals\":true}",
                "layoutOptimization": 0,
                "sections": [
                    {
                        "name": "ReportSection",
                        "displayName": "Page 1",
                        "filters": "[]",
                        "ordinal": 0,
                        "visualContainers": []
                    }
                ]
            }
            pbix_zip.writestr("Report/Layout", json.dumps(minimal_report, separators=(',', ':')))
            
            # 5. Settings with proper structure
            settings = {
                "version": "1.0",
                "useStylableVisualContainerHeader": True
            }
            pbix_zip.writestr("Settings", json.dumps(settings, separators=(',', ':')))
            
            # 6. SecurityBindings (XML format)
            security_bindings = '<?xml version="1.0" encoding="utf-8"?><Bindings xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" />'
            pbix_zip.writestr("SecurityBindings", security_bindings)
            
            # 7. Connections (XML format)
            connections = '<?xml version="1.0" encoding="utf-8"?><Connections></Connections>'
            pbix_zip.writestr("Connections", connections)
            
            # 8. Metadata (XML format)
            metadata = '<?xml version="1.0" encoding="utf-8"?><Metadata xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema"><SelectionBookmark></SelectionBookmark><Timestamp>2024-01-01T00:00:00Z</Timestamp></Metadata>'
            pbix_zip.writestr("Metadata", metadata)
        
        file_size = os.path.getsize(temp_pbix.name)
        print(f"✅ Minimal PBIX created: {temp_pbix.name}")
        print(f"📏 File size: {file_size} bytes")
        
        return temp_pbix.name
        
    except Exception as e:
        if os.path.exists(temp_pbix.name):
            os.unlink(temp_pbix.name)
        raise e

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
        with zipfile.ZipFile(temp_pbix.name, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as pbix_zip:
            
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
                # Ensure the JSON is properly formatted and not corrupted
                try:
                    json.loads(report_content)  # Validate JSON
                    pbix_zip.writestr("Report/Layout", report_content)
                    print("📄 Added Report/Layout")
                except json.JSONDecodeError as e:
                    raise Exception(f"Invalid JSON in report.json: {e}")
            
            # 4. Add DataModel from model.bim
            model_bim_path = os.path.join(model_dir, "model.bim")
            if os.path.exists(model_bim_path):
                with open(model_bim_path, 'r', encoding='utf-8') as f:
                    model_content = f.read()
                # Validate JSON structure
                try:
                    json.loads(model_content)  # Validate JSON
                    pbix_zip.writestr("DataModel", model_content)
                    print("📄 Added DataModel")
                except json.JSONDecodeError as e:
                    raise Exception(f"Invalid JSON in model.bim: {e}")
            
            # 5. Add DiagramLayout
            diagram_path = os.path.join(model_dir, "diagramLayout.json") 
            if os.path.exists(diagram_path):
                with open(diagram_path, 'r', encoding='utf-8') as f:
                    diagram_content = f.read()
                try:
                    json.loads(diagram_content)  # Validate JSON
                    pbix_zip.writestr("DiagramLayout", diagram_content)
                    print("📄 Added DiagramLayout")
                except json.JSONDecodeError as e:
                    print(f"⚠️ Warning: Invalid JSON in diagramLayout.json: {e}")
            
            # 6. Add Settings
            settings_content = '{"version":"1.0","useStylableVisualContainerHeader":true}'
            pbix_zip.writestr("Settings", settings_content)
            print("📄 Added Settings")
            
            # 7. Add SecurityBindings
            security_bindings = """<?xml version="1.0" encoding="utf-8"?><Bindings xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" />"""
            pbix_zip.writestr("SecurityBindings", security_bindings)
            print("📄 Added SecurityBindings")
            
            # 8. Add Connections (if needed)
            connections = """<?xml version="1.0" encoding="utf-8"?><Connections></Connections>"""
            pbix_zip.writestr("Connections", connections)
            print("📄 Added Connections")
            
            # 9. Add Metadata
            metadata = """<?xml version="1.0" encoding="utf-8"?><Metadata xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema"><SelectionBookmark></SelectionBookmark><Timestamp>2024-01-01T00:00:00Z</Timestamp></Metadata>"""
            pbix_zip.writestr("Metadata", metadata)
            print("📄 Added Metadata")
            
            # 10. Add Report/StaticResources if they exist
            static_resources_dir = os.path.join(report_dir, "StaticResources")
            if os.path.exists(static_resources_dir):
                for root, dirs, files in os.walk(static_resources_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_name = f"Report/{os.path.relpath(file_path, report_dir)}"
                        
                        # Handle both text and binary files appropriately
                        try:
                            # Try to read as text first for JSON/text files
                            if file.lower().endswith(('.json', '.txt', '.css', '.js')):
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                pbix_zip.writestr(arc_name, content)
                            else:
                                # Read as binary for other files
                                with open(file_path, 'rb') as f:
                                    content = f.read()
                                pbix_zip.writestr(arc_name, content)
                            print(f"📄 Added {arc_name}")
                        except Exception as e:
                            print(f"⚠️ Warning: Could not add {arc_name}: {e}")
        
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
                # Test that we can read all entries
                for entry in file_list:
                    try:
                        test_zip.read(entry)
                    except Exception as e:
                        raise Exception(f"Cannot read zip entry {entry}: {e}")
        except Exception as e:
            raise Exception(f"Created invalid zip file: {e}")
        
        return temp_pbix.name
        
    except Exception as e:
        if os.path.exists(temp_pbix.name):
            os.unlink(temp_pbix.name)
        raise e

def import_pbix_with_temp_upload(token, workspace_id, pbix_path, dataset_display_name):
    """Import PBIX using temporary upload location method"""
    print(f"📤 Using temporary upload location method...")
    print(f"📤 File: {pbix_path}")
    print(f"📤 File size: {os.path.getsize(pbix_path)} bytes")
    
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    
    # Step 1: Create temporary upload location
    temp_upload_url = f'https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/imports/createTemporaryUploadLocation'
    print(f"🔄 Step 1: Creating temporary upload location...")
    
    temp_response = requests.post(temp_upload_url, headers=headers, timeout=60)
    print(f"📤 Temp upload response: {temp_response.status_code}")
    
    if temp_response.status_code not in (200, 201):
        print(f"❌ Failed to create temp upload location: {temp_response.text}")
        return None
    
    temp_data = temp_response.json()
    upload_url = temp_data.get('url')
    
    if not upload_url:
        print(f"❌ No upload URL in response: {temp_data}")
        return None
    
    print(f"✅ Temporary upload URL created: {upload_url[:50]}...")
    
    # Step 2: Upload file to temporary location
    print(f"🔄 Step 2: Uploading file to temporary location...")
    
    with open(pbix_path, 'rb') as file_handle:
        file_data = file_handle.read()
    
    upload_headers = {
        'Content-Type': 'application/octet-stream',
        'x-ms-blob-type': 'BlockBlob'
    }
    
    # Use PUT for Azure Blob Storage upload (not POST)
    upload_response = requests.put(upload_url, headers=upload_headers, data=file_data, timeout=600)
    print(f"📤 File upload response: {upload_response.status_code}")
    
    if upload_response.status_code not in (200, 201):
        print(f"❌ Failed to upload file: {upload_response.text}")
        return None
    
    print(f"✅ File uploaded successfully")
    
    # Step 3: Import from uploaded location
    print(f"🔄 Step 3: Importing from uploaded location...")
    
    import_url = f'https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/imports'
    import_headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    
    import_data = {
        'fileUrl': upload_url,
        'datasetDisplayName': dataset_display_name,
        'nameConflict': 'CreateOrOverwrite'
    }
    
    import_response = requests.post(import_url, headers=import_headers, json=import_data, timeout=600)
    print(f"📤 Import response: {import_response.status_code}")
    
    if import_response.status_code in (200, 201, 202):
        result = import_response.json() if import_response.content else {"status": "success"}
        print(f"✅ Import successful: {result}")
        return result
    else:
        print(f"❌ Import failed: {import_response.text}")
        return None

def import_pbix_simple(token, workspace_id, pbix_path, dataset_display_name):
    """Simple PBIX import with proper file handling based on Power BI API best practices"""
    print(f"📤 Uploading to Power BI...")
    print(f"📤 File: {pbix_path}")
    print(f"📤 File size: {os.path.getsize(pbix_path)} bytes")
    
    # Verify file exists and is readable
    if not os.path.exists(pbix_path):
        raise FileNotFoundError(f"PBIX file not found: {pbix_path}")
    
    if os.path.getsize(pbix_path) == 0:
        raise Exception("PBIX file is empty")
    
    # Test that the file is a valid ZIP
    try:
        with zipfile.ZipFile(pbix_path, 'r') as test_zip:
            test_zip.testzip()
    except Exception as e:
        raise Exception(f"PBIX file is corrupted or not a valid ZIP: {e}")
    
    headers = {'Authorization': f'Bearer {token}'}
    
    # First, test the token by getting workspace info
    print("🔍 Validating token and workspace access...")
    try:
        workspace_url = f'https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}'
        workspace_response = requests.get(workspace_url, headers=headers, timeout=30)
        print(f"📋 Workspace access test: {workspace_response.status_code}")
        if workspace_response.status_code == 200:
            workspace_info = workspace_response.json()
            print(f"✅ Workspace accessible: {workspace_info.get('name', 'Unknown')}")
        elif workspace_response.status_code == 403:
            print("⚠️ Warning: Access forbidden - service principal may need admin permissions")
        else:
            print(f"⚠️ Warning: Workspace access issue: {workspace_response.text}")
    except Exception as e:
        print(f"⚠️ Warning: Could not validate workspace access: {e}")
    
    # Method 1: Direct binary upload (recommended approach)
    print("🔄 Method 1: Direct binary upload...")
    # URL encode the dataset name to handle spaces and special characters
    import urllib.parse
    encoded_dataset_name = urllib.parse.quote(dataset_display_name)
    url = f'https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/imports?datasetDisplayName={encoded_dataset_name}&nameConflict=CreateOrOverwrite'
    print(f"📤 Uploading to: {url}")
    
    try:
        # Read file as binary data
        with open(pbix_path, 'rb') as file_handle:
            file_data = file_handle.read()
        
        # Set proper headers for binary upload
        upload_headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/octet-stream'
        }
        
        print(f"🔍 Debug info:")
        print(f"  - Dataset name: '{dataset_display_name}'")
        print(f"  - Name conflict: 'CreateOrOverwrite'")
        print(f"  - Content-Type: application/octet-stream")
        print(f"  - Data size: {len(file_data)} bytes")
        
        response = requests.post(
            url, 
            headers=upload_headers, 
            data=file_data,
            timeout=600
        )
        
        print(f"📤 Response: {response.status_code}")
        
        if response.status_code in (200, 201, 202):
            result = response.json() if response.content else {"status": "success"}
            print(f"✅ Upload successful: {result}")
            return result
        else:
            print(f"❌ Method 1 failed: {response.text}")
            
            # Method 2: Multipart form data upload
            print("🔄 Method 2: Multipart form data upload...")
            url2 = f'https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/imports'
            
            # Sanitize the filename to avoid issues with special characters
            safe_filename = dataset_display_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
            
            with open(pbix_path, 'rb') as file_handle:
                files = {
                    'file': (f'{safe_filename}.pbix', file_handle, 'application/octet-stream')
                }
                data = {
                    'datasetDisplayName': dataset_display_name,
                    'nameConflict': 'CreateOrOverwrite'
                }
                
                response2 = requests.post(
                    url2, 
                    headers=headers,  # Only Authorization header for multipart
                    files=files, 
                    data=data, 
                    timeout=600
                )
            
            print(f"📤 Method 2 response: {response2.status_code}")
            
            if response2.status_code in (200, 201, 202):
                result = response2.json() if response2.content else {"status": "success"}
                print(f"✅ Method 2 successful: {result}")
                return result
            else:
                print(f"❌ Method 2 failed: {response2.text}")
                
                # Method 3: Try with minimal parameters
                print("🔄 Method 3: Minimal parameter upload...")
                url3 = f'https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/imports?nameConflict=CreateOrOverwrite'
                
                with open(pbix_path, 'rb') as file_handle:
                    files3 = {
                        'file': ('report.pbix', file_handle, 'application/octet-stream')
                    }
                    response3 = requests.post(url3, headers=headers, files=files3, timeout=600)
                
                print(f"📤 Method 3 response: {response3.status_code}")
                
                if response3.status_code in (200, 201, 202):
                    result = response3.json() if response3.content else {"status": "success"}
                    print(f"✅ Method 3 successful: {result}")
                    return result
                else:
                    print(f"❌ Method 3 failed: {response3.text}")
                    
                    # All methods failed
                    raise Exception(f'All import methods failed. Last errors:\n'
                                  f'Method 1 (Binary): {response.status_code} {response.text}\n'
                                  f'Method 2 (Multipart): {response2.status_code} {response2.text}\n'
                                  f'Method 3 (Minimal): {response3.status_code} {response3.text}')
    
    except requests.exceptions.RequestException as e:
        raise Exception(f'Network error during upload: {str(e)}')

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
        # Validate PBIP structure first
        if args.pbix.endswith('.pbip'):
            project_dir = os.path.dirname(args.pbix)
        else:
            project_dir = args.pbix
            
        if not validate_pbip_structure(project_dir):
            raise Exception("PBIP project structure validation failed. Missing required files.")
        
        print('\n📦 Creating proper PBIX...')
        pbix_file = create_proper_pbix_from_pbip(args.pbix)

        print(f'\n📤 Importing to Power BI...')
        
        # Try temporary upload method first (recommended for all files)
        result = import_pbix_with_temp_upload(token, workspace_id, pbix_file, report_name)
        
        # If temp upload fails, try the direct methods
        if not result:
            print(f'\n🔄 Temp upload failed, trying direct methods...')
            result = import_pbix_simple(token, workspace_id, pbix_file, report_name)
        
        print('\n🎉 SUCCESS! DEPLOYMENT COMPLETED! 🎉')
        print(f"📊 Report '{report_name}' deployed to '{workspace_name}'")
        print(f"🔗 Check your Power BI workspace: {workspace_name}")
        if 'id' in result:
            print(f"📋 Import ID: {result['id']}")

    except Exception as e:
        print(f'\n❌ Error: {str(e)}')
        # Print more diagnostic information
        if pbix_file and os.path.exists(pbix_file):
            try:
                print(f"🔍 PBIX file details:")
                print(f"  - Path: {pbix_file}")
                print(f"  - Size: {os.path.getsize(pbix_file)} bytes")
                with zipfile.ZipFile(pbix_file, 'r') as z:
                    print(f"  - ZIP entries: {len(z.namelist())}")
                    for entry in z.namelist()[:10]:  # Show first 10 entries
                        print(f"    - {entry}")
                    if len(z.namelist()) > 10:
                        print(f"    - ... and {len(z.namelist()) - 10} more")
            except Exception as debug_e:
                print(f"  - Could not read PBIX details: {debug_e}")
        sys.exit(1)
    finally:
        if pbix_file and os.path.exists(pbix_file):
            os.unlink(pbix_file)
            print('🧹 Cleanup completed')

if __name__ == '__main__':
    main()