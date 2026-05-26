// ACA managed environment + Azure Files volume registration.
// The container app (`aca-app.bicep`) references the storage mount by name.

param name string
param location string
param storageAccountName string
@secure()
param storageAccountKey string
param fileShareName string
param storageMountName string = 'zava-data'
@secure()
param appInsightsConnectionString string = ''

resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${name}'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: name
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: law.properties.customerId
        sharedKey: law.listKeys().primarySharedKey
      }
    }
    daprAIConnectionString: empty(appInsightsConnectionString) ? null : appInsightsConnectionString
    zoneRedundant: false
  }
}

resource storageMount 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: env
  name: storageMountName
  properties: {
    azureFile: {
      accountName: storageAccountName
      accountKey: storageAccountKey
      shareName: fileShareName
      accessMode: 'ReadWrite'
    }
  }
}

output environmentId string = env.id
output logAnalyticsWorkspaceId string = law.id
