# Sources and attribution

## Included code

**last30days-skill** — https://github.com/mvanhorn/last30days-skill
Copyright (c) 2026 Matt Van Horn. MIT.

Octopus derives from an installed v3.3.2 snapshot of this project. The precise upstream commit for that original installation was not recorded; this release does not claim to match the current upstream branch. Most files in `skills/octopus/scripts/lib/` and the core `last30days.py`, `store.py`, and `setup-keychain.sh` are inherited. The original naming of engine modules and configuration keys is retained for compatibility.

Octopus's modifications include Chinese topic-research instructions, evidence and recency rules, browser-consent defaults, daily history handling, partial-failure reporting, unique output paths, optional domestic-source wrappers, authenticated Xiaohongshu integration, portable release configuration, and tests. This is an independently maintained derivative, not an official upstream release.

**Bird search subset** — https://github.com/steipete/bird
Based on `@steipete/bird` v0.8.0 by Peter Steinberger. MIT.
The subset included by the upstream project remains in `skills/octopus/scripts/lib/vendor/bird-search/`, with its original `LICENSE` and attribution metadata.

## Optional external services, not bundled

| Project | Integration reference | License |
| --- | --- | --- |
| [DIYgod/RSSHub](https://github.com/DIYgod/RSSHub) | `1c7e106e63bcc6725fe6b13f39544385666c89c0` | [AGPL-3.0](https://github.com/DIYgod/RSSHub/blob/1c7e106e63bcc6725fe6b13f39544385666c89c0/LICENSE) |
| [rachelos/we-mp-rss](https://github.com/rachelos/we-mp-rss) | `d94db01372105bc479db81a0ac91829dac7f43e4` | [MIT at this revision](https://github.com/rachelos/we-mp-rss/blob/d94db01372105bc479db81a0ac91829dac7f43e4/LICENSE) |
| [xpzouying/xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp) | `v2.5.5`, commit `a5c8f7799980ba1fdd501999843eb2d17e4c9a9f` | [Apache-2.0](https://github.com/xpzouying/xiaohongshu-mcp/blob/a5c8f7799980ba1fdd501999843eb2d17e4c9a9f/LICENSE) |

The repository includes original client/wrapper code that communicates with these services, not their source distributions, installed dependencies, browser profiles, databases, credentials, or binaries. Follow each upstream project's own installation instructions and license for the version you install. These references identify integration versions, not guarantees of ongoing platform availability.
