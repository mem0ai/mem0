# OpenMemory Azure Container Registry CI/CD Setup

This document provides step-by-step instructions for setting up GitHub Actions to build and deploy OpenMemory Docker containers to Azure Container Registry (ACR).

## Overview

The CI/CD workflow automatically builds and pushes two Docker images to the Azure Container Registry at `schoollawregistry.azurecr.io`:

1. **API Service** (`openmemory-api`) - Built from `openmemory/api/Dockerfile`
2. **UI Service** (`openmemory-ui`) - Built from `openmemory/ui/Dockerfile`

## Prerequisites

- Access to Azure Container Registry: `schoollawregistry.azurecr.io`
- GitHub repository with admin access to configure secrets
- Azure CLI (for ACR setup)

## Azure Container Registry Setup

### 1. Enable Admin User on ACR

First, enable the admin user on your Azure Container Registry:

```bash
# Login to Azure
az login

# Enable admin user on the container registry
az acr update --name schoollawregistry --admin-enabled true

# Get the credentials
az acr credential show --name schoollawregistry
```

This will output something like:
```json
{
  "passwords": [
    {
      "name": "password",
      "value": "your-registry-password-1"
    },
    {
      "name": "password2", 
      "value": "your-registry-password-2"
    }
  ],
  "username": "schoollawregistry"
}
```

### 2. Alternative: Service Principal Authentication (Recommended for Production)

For production environments, it's recommended to use a Service Principal instead of admin credentials:

```bash
# Create a service principal for ACR
az ad sp create-for-rbac \
  --name "openmemory-github-actions" \
  --role "AcrPush" \
  --scope "/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.ContainerRegistry/registries/schoollawregistry"
```

This will output:
```json
{
  "appId": "service-principal-id",
  "displayName": "openmemory-github-actions",
  "password": "service-principal-password",
  "tenant": "tenant-id"
}
```

## GitHub Secrets Configuration

Navigate to your GitHub repository → Settings → Secrets and variables → Actions, and add the following secrets:

### Option 1: Using Admin Credentials
- **AZURE_REGISTRY_USERNAME**: `schoollawregistry`
- **AZURE_REGISTRY_PASSWORD**: `your-registry-password-1` (from step 1)

### Option 2: Using Service Principal (Recommended)
- **AZURE_REGISTRY_USERNAME**: `service-principal-id` (appId from service principal creation)
- **AZURE_REGISTRY_PASSWORD**: `service-principal-password` (password from service principal creation)

## Workflow Triggers

The workflow is triggered by:

1. **Push to main branch** with changes in `openmemory/` directory
2. **Pull requests** with changes in `openmemory/` directory  
3. **Manual trigger** via GitHub Actions UI

## Image Tagging Strategy

Images are tagged with:
- **Branch name** for branch pushes (e.g., `main`)
- **PR number** for pull requests (e.g., `pr-123`)
- **Git SHA** with branch prefix (e.g., `main-a1b2c3d`)
- **latest** tag for main branch pushes

## Built Images

The workflow builds and pushes:

1. **API Service**: `schoollawregistry.azurecr.io/openmemory-api:latest`
2. **UI Service**: `schoollawregistry.azurecr.io/openmemory-ui:latest`

## Azure Container Apps Deployment

To deploy these images to Azure Container Apps, use the following configuration:

### API Container App
```yaml
# api-container-app.yaml
properties:
  managedEnvironmentId: /subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.App/managedEnvironments/<environment-name>
  configuration:
    activeRevisionsMode: Single
    ingress:
      external: true
      targetPort: 8765
      traffic:
      - weight: 100
        latestRevision: true
    registries:
    - server: schoollawregistry.azurecr.io
      username: <registry-username>
      passwordSecretRef: registry-password
    secrets:
    - name: registry-password
      value: <registry-password>
  template:
    containers:
    - image: schoollawregistry.azurecr.io/openmemory-api:latest
      name: openmemory-api
      env:
      - name: USER
        value: <user-value>
      - name: API_KEY
        value: <api-key-value>
      resources:
        cpu: 0.5
        memory: 1Gi
    scale:
      minReplicas: 1
      maxReplicas: 3
```

### UI Container App
```yaml
# ui-container-app.yaml
properties:
  managedEnvironmentId: /subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.App/managedEnvironments/<environment-name>
  configuration:
    activeRevisionsMode: Single
    ingress:
      external: true
      targetPort: 3000
      traffic:
      - weight: 100
        latestRevision: true
    registries:
    - server: schoollawregistry.azurecr.io
      username: <registry-username>
      passwordSecretRef: registry-password
    secrets:
    - name: registry-password
      value: <registry-password>
  template:
    containers:
    - image: schoollawregistry.azurecr.io/openmemory-ui:latest
      name: openmemory-ui
      env:
      - name: NEXT_PUBLIC_API_URL
        value: <api-url>
      - name: NEXT_PUBLIC_USER_ID
        value: <user-id>
      resources:
        cpu: 0.5
        memory: 1Gi
    scale:
      minReplicas: 1
      maxReplicas: 3
```

## Deployment Commands

Deploy to Azure Container Apps using Azure CLI:

```bash
# Create or update API container app
az containerapp create \
  --name openmemory-api \
  --resource-group <resource-group> \
  --environment <environment-name> \
  --yaml api-container-app.yaml

# Create or update UI container app  
az containerapp create \
  --name openmemory-ui \
  --resource-group <resource-group> \
  --environment <environment-name> \
  --yaml ui-container-app.yaml
```

## Monitoring and Troubleshooting

### Viewing Workflow Logs
1. Go to your GitHub repository
2. Click on "Actions" tab
3. Select the "OpenMemory Docker Build and Deploy" workflow
4. Click on a specific run to view logs

### Checking ACR Images
```bash
# List repositories in ACR
az acr repository list --name schoollawregistry

# List tags for a specific image
az acr repository show-tags --name schoollawregistry --repository openmemory-api
az acr repository show-tags --name schoollawregistry --repository openmemory-ui
```

### Container App Logs
```bash
# View container app logs
az containerapp logs show --name openmemory-api --resource-group <resource-group>
az containerapp logs show --name openmemory-ui --resource-group <resource-group>
```

## Security Considerations

1. **Use Service Principal**: Prefer service principal authentication over admin credentials
2. **Least Privilege**: Grant only necessary permissions (AcrPush role)
3. **Secret Rotation**: Regularly rotate registry passwords and service principal credentials
4. **Environment Variables**: Store sensitive configuration in Azure Key Vault and reference in Container Apps

## Environment Mapping

The current docker-compose.yml setup maps to Azure Container Apps as follows:

| docker-compose service | Azure Container App | Image |
|------------------------|---------------------|-------|
| `openmemory-mcp` | `openmemory-api` | `schoollawregistry.azurecr.io/openmemory-api:latest` |
| `openmemory-ui` | `openmemory-ui` | `schoollawregistry.azurecr.io/openmemory-ui:latest` |
| `mem0_store` (Qdrant) | External Qdrant service or Azure equivalent | N/A |

## Next Steps

1. Configure the GitHub secrets as described above
2. Push changes to trigger the workflow
3. Verify images are pushed to ACR
4. Set up Azure Container Apps environment
5. Deploy container apps using the provided configurations
6. Configure networking and environment variables as needed