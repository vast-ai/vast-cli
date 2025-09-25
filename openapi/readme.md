# Vast.ai API Documentation

This directory contains OpenAPI YAML files for the Vast.ai REST API documentation.

## Overview
The API documentation is maintained as separate YAML files that are combined into a single specification file for publication.

## File Structure
- Individual YAML files for different API endpoints
- `combine_api_yamls.py` - Script to merge all YAML files
- `combined_api.yaml` - Final combined specification (generated)

## Updating API Documentation

## Generating Combined Documentation
Run the combination script:
```bash
python3 combine_api_yamls.py
```

### Deployment
After PR approval and merge, the combined YAML file is released to production at docs.vast.ai/api by a Vast developer.

### Support
For questions or assistance, reach out to the #api channel on Discord. 
