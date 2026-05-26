// Subscription-scoped orchestrator for the Zava control plane.
//
// Provisions (per skill `zava-workspace-deploy`):
//   - Resource group
//   - User-Assigned Managed Identity (UAMI)
//   - Storage account + Azure Files share for KuzuDB persistence
//   - ACA managed environment + volume
//   - ACA container app (placeholder image swapped by `azd deploy`)
//   - AcrPull RBAC on the existing shared ACR
//
// Does NOT provision: ACR, App Insights, Citadel APIM, Foundry —
// these are shared per-subscription and referenced via parameters.

targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('azd environment name (used as RG suffix and resource prefix)')
param environmentName string

@description('Region for all resources')
param location string = 'swedencentral'

@description('Existing ACR login server (e.g. myacr.azurecr.io)')
param acrLoginServer string

@description('Existing ACR name')
param acrName string

@description('Resource group of the existing ACR')
param acrResourceGroup string

@description('App Insights connection string (existing shared instance)')
@secure()
param appInsightsConnectionString string = ''

@description('Azure OpenAI / Citadel APIM endpoint (LLM gateway)')
param azureOpenAiEndpoint string = ''

@description('Default model deployment name')
param azureOpenAiDeployment string = 'gpt-4.1'

@description('Embedding model deployment name')
param azureOpenAiEmbedDeployment string = 'text-embedding-3-large'

@description('Azure OpenAI API version')
param azureOpenAiApiVersion string = '2024-10-21'

@description('Fleet manager model deployment')
param fleetManagerModel string = 'gpt-4.1'

@description('Optional override: comma-separated simulator ramp domains (Profile 1 vs 2)')
param simulatorRampDomains string = 'expense-claim'

@description('Optional override: comma-separated PERSONA_AUTO_CLOSE roles (Profile 2 demo experience)')
param personaAutoClose string = ''

@description('LLM runtime: "fake" (template responses, no LLM calls) or "azure"')
@allowed(['fake', 'azure'])
param llmRuntime string = 'fake'

@description('Provision Azure Files share + mount for KuzuDB persistence. Set false in tenants where Azure Policy disables shared-key access on Storage accounts (ACA SMB mount requires the key).')
param persistData bool = false

// ── Resource group ────────────────────────────────────────────────────
resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: {
    'azd-env-name': environmentName
  }
}

var prefix = uniqueString(rg.id)

module uami 'modules/uami.bicep' = {
  scope: rg
  name: 'uami'
  params: {
    name: 'id-${environmentName}-${prefix}'
    location: location
  }
}

module storage 'modules/storage.bicep' = {
  scope: rg
  name: 'storage'
  params: {
    name: 'st${take(replace(toLower(environmentName), '-', ''), 12)}${take(prefix, 6)}'
    location: location
    fileShareName: 'zava-data'
    createFileShare: persistData
    uamiPrincipalId: uami.outputs.principalId
  }
}

module acaEnv 'modules/aca-env.bicep' = {
  scope: rg
  name: 'aca-env'
  params: {
    name: 'cae-${environmentName}'
    location: location
    persistData: persistData
    storageAccountName: persistData ? storage.outputs.accountName : ''
    storageAccountKey: persistData ? storage.outputs.accountKey : ''
    fileShareName: persistData ? storage.outputs.fileShareName : ''
    storageMountName: 'zava-data'
    appInsightsConnectionString: appInsightsConnectionString
  }
}

module acaApp 'modules/aca-app.bicep' = {
  scope: rg
  name: 'aca-app'
  params: {
    name: 'zava-${environmentName}'
    location: location
    environmentId: acaEnv.outputs.environmentId
    userAssignedIdentityId: uami.outputs.id
    acrLoginServer: acrLoginServer
    persistData: persistData
    storageMountName: 'zava-data'
    appInsightsConnectionString: appInsightsConnectionString
    azureOpenAiEndpoint: azureOpenAiEndpoint
    azureOpenAiDeployment: azureOpenAiDeployment
    azureOpenAiEmbedDeployment: azureOpenAiEmbedDeployment
    azureOpenAiApiVersion: azureOpenAiApiVersion
    fleetManagerModel: fleetManagerModel
    simulatorRampDomains: simulatorRampDomains
    personaAutoClose: personaAutoClose
    llmRuntime: llmRuntime
    funcStorageAccountName: storage.outputs.accountName
  }
}

module acrPull 'modules/rbac-acr-pull.bicep' = {
  scope: resourceGroup(acrResourceGroup)
  name: 'rbac-acr-pull'
  params: {
    acrName: acrName
    principalId: uami.outputs.principalId
  }
}

output SERVICE_ZAVA_RESOURCE_GROUP_NAME string = rg.name
output SERVICE_ZAVA_IMAGE_NAME string = '${acrLoginServer}/zava-control-plane:latest'
output AZURE_CONTAINER_APP_NAME string = acaApp.outputs.name
output AZURE_CONTAINER_APP_FQDN string = acaApp.outputs.fqdn
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = acrLoginServer
output AZURE_CONTAINER_REGISTRY_NAME string = acrName
output AZURE_RESOURCE_GROUP string = rg.name
