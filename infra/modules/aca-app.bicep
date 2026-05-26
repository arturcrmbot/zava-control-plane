// ACA Container App — the Zava control plane.
//
// Notes:
//  * `image` starts as the public `mcr` quickstart placeholder. `azd deploy`
//    swaps in the freshly-built ACR image after `azd provision`.
//  * Liveness and readiness probes hit `/healthz` (NOT `/`). The skill
//    troubleshooting log (May 2026 cloud rollout) showed that hitting `/`
//    returns the SPA index.html 200 even when the API is dead — that's
//    why we have an explicit `/healthz` route registered before any
//    StaticFiles mount in `api/server/main.py`, and why probes target it.
//  * `corsPolicy` and ingress allow all origins by default for the demo;
//    tighten via APIM in front of this in production.

param name string
param location string
param environmentId string
param userAssignedIdentityId string
param acrLoginServer string
param persistData bool = true
param storageMountName string = 'zava-data'

@secure()
param appInsightsConnectionString string = ''
param azureOpenAiEndpoint string = ''
param azureOpenAiDeployment string = 'gpt-4.1'
param azureOpenAiEmbedDeployment string = 'text-embedding-3-large'
param azureOpenAiApiVersion string = '2024-10-21'
param fleetManagerModel string = 'gpt-4.1'
param simulatorRampDomains string = 'expense-claim'
param personaAutoClose string = ''
@allowed(['fake', 'azure'])
param llmRuntime string = 'fake'

@description('Set to "replay" to boot the container against a baked tape (no live workers, no Functions host, no LLM calls). Anything else boots live mode.')
@allowed(['live', 'replay'])
param zavaMode string = 'live'

@description('Path inside the container to the baked tape archive. Only used when zavaMode=replay.')
param zavaTapePath string = '/app/tape/tape.tar.gz'

@description('Shared secret for the Functions worker → FastAPI /internal/durable-event callback. If empty, callbacks fail 401 and workflows stall.')
@secure()
param durableEventSecret string = ''

@description('Storage account name for identity-based AzureWebJobsStorage (Functions Durable host).')
param funcStorageAccountName string

var placeholderImage = 'mcr.microsoft.com/k8se/quickstart:latest'

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentityId}': {}
    }
  }
  tags: {
    'azd-service-name': 'zava'
  }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 80
        transport: 'auto'
        allowInsecure: false
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['GET','POST','PUT','PATCH','DELETE','OPTIONS']
          allowedHeaders: ['*']
        }
      }
      registries: [
        {
          server: acrLoginServer
          identity: userAssignedIdentityId
        }
      ]
      secrets: [
        {
          name: 'durable-event-secret'
          value: durableEventSecret
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'zava'
          image: placeholderImage
          resources: {
            cpu: json('2.0')
            memory: '4Gi'
          }
          env: [
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
            { name: 'AZURE_CLIENT_ID', value: reference(userAssignedIdentityId, '2023-01-31').clientId }

            // Replay mode toggles. When ZAVA_MODE=replay the entrypoint
            // skips the Functions host, the FastAPI lifespan boots the
            // Player against ZAVA_TAPE_PATH, and the read-only middleware
            // 403s every write.
            { name: 'ZAVA_MODE', value: zavaMode }
            { name: 'ZAVA_TAPE_PATH', value: zavaTapePath }

            { name: 'AZURE_OPENAI_ENDPOINT', value: azureOpenAiEndpoint }
            { name: 'AZURE_OPENAI_DEPLOYMENT', value: azureOpenAiDeployment }
            { name: 'AZURE_OPENAI_EMBED_DEPLOYMENT', value: azureOpenAiEmbedDeployment }
            { name: 'AZURE_OPENAI_API_VERSION', value: azureOpenAiApiVersion }
            { name: 'FLEET_MANAGER_MODEL', value: fleetManagerModel }
            { name: 'LLM_RUNTIME', value: llmRuntime }

            { name: 'SIMULATOR_RAMP_ENABLED', value: '1' }
            { name: 'SIMULATOR_RAMP_DOMAINS', value: simulatorRampDomains }
            { name: 'MEMORY_DOMAINS', value: 'expense-claim,hiring,fleet-vendor-kyc,fleet-travel-preapproval,fleet-purchase-order' }
            { name: 'PERSONA_AUTO_CLOSE', value: personaAutoClose }
            { name: 'DEMO_TIME_WARP_FACTOR', value: '3600' }

            { name: 'ENTITY_PLANE_ENABLED', value: '1' }

            // Azure Functions host (Durable orchestrator on :7071, started
            // alongside uvicorn by deploy/entrypoint.sh). Identity-based
            // AzureWebJobsStorage avoids the MCAPS shared-key policy.
            { name: 'AzureWebJobsStorage__accountName', value: funcStorageAccountName }
            { name: 'AzureWebJobsStorage__credential', value: 'managedidentity' }
            { name: 'AzureWebJobsStorage__clientId', value: reference(userAssignedIdentityId, '2023-01-31').clientId }
            { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
            { name: 'PYTHON_ISOLATE_WORKER_DEPENDENCIES', value: '0' }
            { name: 'FASTAPI_WEBHOOK_URL', value: 'http://localhost:80/internal/durable-event' }
            { name: 'DURABLE_EVENT_SECRET', secretRef: 'durable-event-secret' }

            // No AUTHORITY_MCP_URL → /api/authority/* uses the in-process
            // kernel and /api/authority/health reports backend=in-process.
          ]
          volumeMounts: persistData ? [
            {
              volumeName: 'zava-data'
              mountPath: '/data'
            }
          ] : []
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/healthz'
                port: 80
                scheme: 'HTTP'
              }
              initialDelaySeconds: 30
              periodSeconds: 30
              timeoutSeconds: 5
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/healthz'
                port: 80
                scheme: 'HTTP'
              }
              initialDelaySeconds: 10
              periodSeconds: 10
              timeoutSeconds: 5
              failureThreshold: 3
            }
            {
              type: 'Startup'
              httpGet: {
                path: '/healthz'
                port: 80
                scheme: 'HTTP'
              }
              initialDelaySeconds: 10
              periodSeconds: 5
              timeoutSeconds: 5
              failureThreshold: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
      volumes: persistData ? [
        {
          name: 'zava-data'
          storageType: 'AzureFile'
          storageName: storageMountName
        }
      ] : []
    }
  }
}

output name string = app.name
output id string = app.id
output fqdn string = app.properties.configuration.ingress.fqdn
