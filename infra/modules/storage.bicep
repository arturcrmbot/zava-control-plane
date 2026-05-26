// Storage account for Azure Functions host (AzureWebJobsStorage, identity-based)
// + optional Azure Files share for KuzuDB persistence.
//
// MCAPS tenants force `allowSharedKeyAccess = false` via Azure Policy, so:
//   - Functions host uses identity-based connection (no keys).
//   - Files share (if enabled) needs an exemption tenant — disabled by default.

@minLength(3)
@maxLength(24)
param name string
param location string
param fileShareName string = 'zava-data'
@description('Provision the Azure Files share for KuzuDB persistence (requires shared-key access).')
param createFileShare bool = false
@description('UAMI principal that needs Blob/Queue/Table Data Contributor on this account for identity-based AzureWebJobsStorage.')
param uamiPrincipalId string

resource account 'Microsoft.Storage/storageAccounts@2024-01-01' = {
  name: name
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowSharedKeyAccess: createFileShare
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: 'Enabled'
  }
}

resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2024-01-01' = if (createFileShare) {
  parent: account
  name: 'default'
}

resource share 'Microsoft.Storage/storageAccounts/fileServices/shares@2024-01-01' = if (createFileShare) {
  parent: fileService
  name: fileShareName
  properties: {
    shareQuota: 5
  }
}

// ── RBAC: UAMI → identity-based AzureWebJobsStorage ──────────────────────
// Built-in role IDs (subscription-scoped GUIDs):
//   Storage Blob Data Owner     b7e6dc6d-f1e8-4753-8033-0f276bb0955b
//   Storage Queue Data Contrib  974c5e8b-45b9-4653-ba55-5f855dd0fb88
//   Storage Table Data Contrib  0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3
var blobOwnerRoleId  = 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
var queueContribRoleId = '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
var tableContribRoleId = '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'

resource blobOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: account
  name: guid(account.id, uamiPrincipalId, blobOwnerRoleId)
  properties: {
    principalId: uamiPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobOwnerRoleId)
  }
}

resource queueContrib 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: account
  name: guid(account.id, uamiPrincipalId, queueContribRoleId)
  properties: {
    principalId: uamiPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', queueContribRoleId)
  }
}

resource tableContrib 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: account
  name: guid(account.id, uamiPrincipalId, tableContribRoleId)
  properties: {
    principalId: uamiPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', tableContribRoleId)
  }
}

output accountName string = account.name
output blobEndpoint string = account.properties.primaryEndpoints.blob
output queueEndpoint string = account.properties.primaryEndpoints.queue
output tableEndpoint string = account.properties.primaryEndpoints.table
output accountKey string = createFileShare ? account.listKeys().keys[0].value : ''
output fileShareName string = createFileShare ? share.name : ''

