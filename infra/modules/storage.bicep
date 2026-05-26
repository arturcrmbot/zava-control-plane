// Storage account + Azure Files share for KuzuDB persistence.
// (Uses storage key for ACA file-share mount — UAMI auth on Files needs
// AAD-domain joins which ACA doesn't support out of the box.)

@minLength(3)
@maxLength(24)
param name string
param location string
param fileShareName string = 'zava-data'

resource account 'Microsoft.Storage/storageAccounts@2024-01-01' = {
  name: name
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowSharedKeyAccess: true
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: 'Enabled'
  }
}

resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2024-01-01' = {
  parent: account
  name: 'default'
}

resource share 'Microsoft.Storage/storageAccounts/fileServices/shares@2024-01-01' = {
  parent: fileService
  name: fileShareName
  properties: {
    shareQuota: 5
  }
}

output accountName string = account.name
output accountKey string = account.listKeys().keys[0].value
output fileShareName string = share.name
