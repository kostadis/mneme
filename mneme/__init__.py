"""mneme — spin up the campaign runtime for a specific campaign.

`hypostasis` configures the environment (installs the shared libraries, references
the DGX/rpg-lib substrate, renders shared config). `mneme` is what you run *per
campaign*: it brings CampaignGenerator up for one campaign, on the environment
hypostasis prepared. Named for Mneme, the Muse of memory.
"""

__version__ = "0.1.0"
