| NFR | Target | How |
|---|---|---|
| Availability | 99.9% per region | Azure SLA-backed across all services in the stack |
| RTO | <5 minutes | Azure Traffic Manager + Cosmos DB automatic failover + Durable Functions replay |
| RPO | Near-zero | Cosmos DB continuous backup with point-in-time restore; Durable Functions checkpoints in geo-redundant Azure Storage |
| Control Plane latency | <5 seconds | Fleet Manager pre-composes situational context; SignalR push to the operator UI |
| Concurrent workflows (pilot) | 5,000+ | Durable Functions auto-scaling; Cosmos DB horizontal partitioning; multiple Hosted Agent deployments |
| Concurrent workflows (production) | 50,000+ | Same architecture, scaled; tiered model usage and skill crystallisation reduce inference bottleneck |
| Audit log retention | 7–12 years | Azure Log Analytics archive tier; immutability via Azure Storage export with immutability policies |
| Data residency | Enforced at platform level | APIM routes by jurisdiction; Cosmos DB regional deployment; Log Analytics regional workspaces; not developer-configured |
| Workflow state | Survives full restart | Durable Functions replays from checkpoint; Cosmos DB serves from geo-replica; maximum loss is the current in-flight phase which replays from its start |

Three additional operational notes:

99.9% per region is delivered by Azure's financially-backed SLAs across all services in the architecture. Multi-region disaster recovery combines Azure Traffic Manager, Cosmos DB automatic failover, and Durable Functions replay.

Cost attribution is operational risk at scale. 500 concurrent workflows × 30 markets × mixed model usage produces material token spend. APIM AI Gateway meters tokens per model, per team, and per workflow, with budget enforcement exposed in the Control Plane cost dashboard. Semantic caching reduces redundant inference cost.

Jurisdictional residency is platform-enforced, not developer-configured. An APIOps CI gate rejects any pull request that registers a cross-region backend against a jurisdiction-tagged skill or model before deployment. Reference architectures for 50,000+ concurrent workflows are available on request — the same stack, scaled via Durable Functions auto-scaling, Cosmos DB horizontal partitioning, multiple Hosted Agent deployments, tiered model selection, and skill crystallisation to reduce inference volume.
