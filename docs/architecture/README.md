# Campaign System Architecture (cross-cutting)

These docs describe the campaign system that spans multiple repos. They live in `mneme` because
`mneme` is the source authority (its `hypostasis.yaml` renders the external wiring the other repos
consume), so cross-cutting architecture is owned here.

| Doc | Scope |
|---|---|
| [campaign-system-architecture.md](./campaign-system-architecture.md) | Whole-system architecture: subsystems, planes, cross-repo edges, flows |
| [config-wiring-graph.md](./config-wiring-graph.md) | Cross-tool configuration & wiring: files, formats, defaults, precedence, the `hypostasis.yaml → wiring.yaml` bridge |
| [pruned-campaign-system.md](./pruned-campaign-system.md) | How the runtime system was pruned from the full workspace graph |

Repo-specific docs live in their own repos:

- **CampaignGenerator** config: `CampaignGenerator/docs/config/`
- **turbovecdb** internals: `turbovecdb/docs/`
- **Mempalace** internals: `Mempalace/docs/`
