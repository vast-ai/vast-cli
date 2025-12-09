import yaml
import glob
from pathlib import Path
import os

# Add this constant near the top of the file, after imports
# Note that this combine script merges yaml files with the same path and method.  Since 
# start, stop, and label instance are all PUT to the same API path, we have created 
# instance_management.yaml to combine them all into one.
YAML_IGNORE_LIST = [
    'launch_instance.yaml',
    'start_instance.yaml',
    'start_instances.yaml',
    'stop_instance.yaml',
    'label_instance.yaml',
]

def clean_description(text):
    """Clean up description text formatting"""
    if not text:
        return text
    lines = [line.rstrip() for line in text.split('\n')]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return '\n'.join(lines)

def remove_existing_combined_file(directory):
    """Remove the existing combined API YAML file if it exists.
    
    This function is idempotent - it succeeds whether or not the file exists.
    Returns True unless there's an error during deletion.
    """
    combined_file = directory / "combined_api.yaml"
    try:
        if (combined_file.exists()):
            combined_file.unlink()
            print(f"Removed existing combined API spec at {combined_file}")
        else:
            print(f"No existing combined API spec found at {combined_file}")
    except Exception as e:
        print(f"Error removing existing combined file: {str(e)}")

def combine_yaml_files(directory):
    """Combines API specs into a single document, preserving different methods for same path"""
    directory = Path(directory)
    if not directory.exists():
        print(f"Creating directory: {directory}")
        directory.mkdir(parents=True, exist_ok=True)
    
    master_doc = {
        'openapi': '3.1.0',
        'info': {
            'title': 'Vast.ai API',
            'description': 'Welcome to Vast.ai \'s API documentation. Our API allows you to programmatically manage GPU instances, handle machine operations, and automate your AI/ML workflow. Whether you\'re running individual GPU instances or managing a fleet of machines, our API provides comprehensive control over all Vast.ai  platform features.',
            'version': '1.0.0',
            'contact': {
                'name': 'Vast.ai Support',
                'url': 'https://discord.gg/vast'
            }
        },
        'servers': [
            {
                'url': 'https://console.vast.ai',
                'description': 'Production server'
            }
        ],
        'security': [
            {
                'BearerAuth': []
            }
        ],
        'paths': {},
        'components': {
            'schemas': {},
            'securitySchemes': {
                'BearerAuth': {
                    'type': 'http',
                    'scheme': 'bearer',
                    'description': 'API key must be provided in the Authorization header'
                }
            }
        }
    }

    yaml_files = sorted(directory.glob("*.yaml"))
    if not yaml_files:
        print(f"Warning: No YAML files found in {directory}")
        return None
    
    # Process each YAML file
    for yaml_file in yaml_files:
        if yaml_file.name in YAML_IGNORE_LIST:
            print(f"Skipping ignored file: {yaml_file.name}")
            continue
            
        print(f"Processing {yaml_file.name}...")
        try:
            with open(yaml_file, 'r') as f:
                spec = yaml.safe_load(f)
                
                # Extract paths
                if 'paths' in spec:
                    for path, path_item in spec['paths'].items():
                        # Clean up descriptions
                        for method in path_item.values():
                            if 'description' in method:
                                method['description'] = clean_description(method['description'])
                            
                            # Update to BearerAuth if needed
                            if 'security' in method:
                                method['security'] = [{'BearerAuth': []}]
                            
                            # Remove api_key parameter if present
                            if 'parameters' in method:
                                method['parameters'] = [
                                    p for p in method['parameters'] 
                                    if not (p.get('name') == 'api_key' and p.get('in') == 'query')
                                ]
                        
                        # Add path to master doc, merging methods if path exists
                        if path in master_doc['paths']:
                            master_doc['paths'][path].update(path_item)
                        else:
                            master_doc['paths'][path] = path_item
                
                # Extract schemas from components
                if 'components' in spec and 'schemas' in spec['components']:
                    master_doc['components']['schemas'].update(spec['components']['schemas'])
                    
        except Exception as e:
            print(f"Error processing {yaml_file.name}: {str(e)}")
            continue

    # Write the combined file
    output_file = directory / "combined_api.yaml"
    try:
        with open(output_file, 'w') as f:
            yaml.dump(master_doc, f, default_flow_style=False, sort_keys=False, width=80)
        print(f"\nCreated combined API spec at {output_file}")
        return output_file
    except Exception as e:
        print(f"Error writing combined file: {str(e)}")
        return None

if __name__ == "__main__":
    yaml_dir = Path("yaml")

    try:
        # First remove existing combined file
        remove_existing_combined_file(yaml_dir)
        # Then generate new combined file
        combined_file = combine_yaml_files(yaml_dir)
        if (combined_file):
            print("Successfully combined API specifications")
        else:
            print("Failed to combine API specifications")
    except Exception as e:
        print(f"Error: {str(e)}")
