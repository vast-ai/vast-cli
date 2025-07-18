# Vast.ai API Documentation

This directory contains OpenAPI YAML files for the Vast.ai REST API documentation.

## Overview
The API documentation is maintained as separate YAML files that are combined into a single specification file for publication.

## File Structure
- Individual YAML files for different API endpoints
- `combine_api_yamls.py` - Script to merge all YAML files
- `combined_api.yaml` - Final combined specification (generated)

## Updating API Documentation

### 1. Prerequisites
- Python environment with required dependencies
- Access to [Swagger Editor](https://editor.swagger.io/) for validation

### 2. Making Changes
1. Locate the relevant YAML file for your endpoint
2. Ensure request format matches the expected structure
3. Validate consistency across API documentation, CLI, Postman, and console website

<<<<<<< HEAD
### 3. Validation and Testing Process

#### 3.1 YAML Structure Validation
1. Use [Swagger Editor](https://editor.swagger.io/) to validate YAML structure
2. Ensure adherence to OpenAPI standards
3. Verify no syntax errors or schema violations

#### 3.2 Request Format Comparison
1. Compare request formats between old and new YAML specifications
2. Ensure backward compatibility is maintained
3. Document any breaking changes with proper versioning
4. **TODO**: Include detailed instructions for automated comparison tools

#### 3.3 Implementation Consistency
1. Compare with CLI implementation for consistency
2. Verify parameter names, types, and required fields match
3. Ensure response schemas align with actual API responses

#### 3.4 End-to-End Testing Requirements
1. **Critical**: E2E testing must be performed on docs.vast.ai to avoid CORS errors
2. Test API requests directly from the documentation interface
3. Verify all endpoints function correctly with real authentication
4. Validate response formats match the documented schemas
5. Test edge cases and error scenarios
=======
### 3. Validation Process
1. Use [Swagger Editor](https://editor.swagger.io/) to validate YAML structure
2. Ensure adherence to OpenAPI standards
3. Compare with CLI implementation for consistency
4. Test the API request format
>>>>>>> e42daf7 (Add tests, readme, util scripts for vast api docs)

### 4. Generating Combined Documentation
Run the combination script:
```bash
<<<<<<< HEAD
python3 combine_api_yamls.py
```
This generates `combined_api.yaml` which is deployed to docs.vast.ai/api

**Note**: Use `python3` instead of `python` to ensure compatibility with the system Python installation.

### 5. Submitting Changes
1. Ensure all validation and testing steps are completed
2. Include test results and validation screenshots in your PR description
3. Create a Pull Request to the [vast-cli GitHub repository](https://github.com/vast-ai/vast-cli) with your changes for review
4. Document any breaking changes or new features in the PR description
=======
python combine_api_yamls.py
```
This generates `combined_api.yaml` which is deployed to docs.vast.ai/api

### 5. Submitting Changes
Create a Pull Request to the [vast-cli GitHub repository](https://github.com/vast-ai/vast-cli) with your changes for review.
>>>>>>> e42daf7 (Add tests, readme, util scripts for vast api docs)

### 6. Deployment
After PR approval and merge, the combined YAML file is released to production at docs.vast.ai/api by a Vast developer.

## Support
For questions or assistance, reach out to the #api channel on Discord. 
