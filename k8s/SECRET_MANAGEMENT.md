# Secret Management for Pan-Finder

This document outlines secure approaches for managing secrets in the Pan-Finder application.

## Current Secrets

The application requires the following secrets:

### pgvector-secret
- `POSTGRES_PASSWORD`: Password for the PostgreSQL database

### server-secret
- `DATABASE_URL`: Connection string for PostgreSQL database
- `AZURE_OPENAI_ENDPOINT`: Azure OpenAI service endpoint
- `AZURE_OPENAI_API_KEY`: API key for Azure OpenAI service

## Recommended Approaches

### 1. External Secret Operator (Recommended for Production)

Use External Secret Operator with cloud secret managers:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: azure-keyvault-store
  namespace: pan-finder
spec:
  provider:
    azurekv:
      vaultUrl: "https://your-keyvault.vault.azure.net/"
      authSecretRef:
        clientId:
          name: azure-secret
          key: client-id
        clientSecret:
          name: azure-secret
          key: client-secret
      tenantId: "your-tenant-id"
---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: pan-finder-secrets
  namespace: pan-finder
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: azure-keyvault-store
    kind: SecretStore
  target:
    name: server-secret
    creationPolicy: Owner
  data:
  - secretKey: AZURE_OPENAI_API_KEY
    remoteRef:
      key: azure-openai-api-key
  - secretKey: POSTGRES_PASSWORD
    remoteRef:
      key: postgres-password
```

### 2. Sealed Secrets

Install Sealed Secrets controller and use sealed secrets:

```bash
# Install sealed secrets controller
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.18.0/controller.yaml

# Create sealed secret
echo -n mypassword | kubectl create secret generic mysecret --dry-run=client --from-file=password=/dev/stdin -o yaml | kubeseal -w mysealedsecret.yaml
```

### 3. CI/CD Pipeline Injection

Configure your CI/CD pipeline to inject secrets at deployment time:

```yaml
# Example GitHub Actions workflow
- name: Deploy to Kubernetes
  env:
    POSTGRES_PASSWORD: ${{ secrets.POSTGRES_PASSWORD }}
    AZURE_OPENAI_API_KEY: ${{ secrets.AZURE_OPENAI_API_KEY }}
  run: |
    envsubst < k8s/base/secret.yaml | kubectl apply -f -
```

### 4. Manual kubectl Commands

For development/testing environments:

```bash
# Create secrets manually
kubectl create secret generic pgvector-secret \
  --from-literal=POSTGRES_PASSWORD="your_password" \
  --namespace=pan-finder

kubectl create secret generic server-secret \
  --from-literal=DATABASE_URL="postgresql://usr:your_password@pgvector-service:5432/pan-finder" \
  --from-literal=AZURE_OPENAI_ENDPOINT="your_endpoint" \
  --from-literal=AZURE_OPENAI_API_KEY="your_api_key" \
  --namespace=pan-finder
```

## Local Development

For local development:

1. Copy `secret.yaml.template` to `secret.yaml`
2. Fill in the actual values
3. Apply with `kubectl apply -f secret.yaml`
4. **Never commit the filled `secret.yaml` to the repository**

## Security Best Practices

- Use unique, strong passwords for each environment
- Rotate secrets regularly
- Use least-privilege access for service accounts
- Monitor secret access and usage
- Consider using short-lived tokens where possible
- Encrypt secrets at rest and in transit

## .gitignore Entry

Add the following to your `.gitignore` file:

```
# Kubernetes secrets with actual values
k8s/**/secret.yaml
!k8s/**/secret.yaml.template
```
