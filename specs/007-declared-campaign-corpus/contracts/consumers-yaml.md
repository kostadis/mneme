# Contract: `mneme/recipes/consumers.yaml` (consumer inventory, GM-maintained)

The known consumers of campaign files and how each picks them (FR-023). It is versioned
with mneme and is not per campaign: the same skills and CG pipelines serve every campaign.

```yaml
schema: 1
consumers:
  - name: cg.prep
    repo: CampaignGenerator
    entry: pipelines/session_prep/prep.py:43
    kinds: [grounding, party]
    mode: independent          # palace | toc | partial | independent
    via: config.yaml documents[]
    reads:                     # paths it reads, as it reads them (GM-reviewed; FR-024)
      - docs/world_state.md
      - docs/campaign_state.md
      - docs/party.md
      - docs/planning.md
    issue: null                # follow-up issue once filed
  - name: skill.campaign-recall
    repo: ~/.claude/skills
    entry: campaign-recall/SKILL.md:36
    kinds: [summaries]
    mode: independent
    via: "zg index found from cwd"
```

- `palace` and `toc` are compliant. `partial` is compliant for part of what it reads (through
  the palace, or through the TOC for the kinds in the optional `kinds_toc`) and independent
  for the rest. `independent` is non-compliant, and status shows it as owed work (FR-024).
- Optional fields: `reads` (path patterns the consumer reads; status diffs them per campaign
  against the resolved corpus), `kinds_toc`, `other` (non-corpus files it reads), `note`
  (free-text remark from review). Unknown fields are errors.
- **Seeding**: the first version is drafted from the 2026-10-23 read-only sweep (research
  R9). That sweep is unreviewed model output, so the GM reviews and corrects the draft
  before it is committed. Status never reads an unreviewed inventory.
- A consumer moves to `toc` only when its conversion has landed in its own repo, and `entry`
  is updated to the converted code.
