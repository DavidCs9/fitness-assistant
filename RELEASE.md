# Release Strategy

## Versioning — `vMAJOR.MINOR.PATCH`

| Segment | When to bump | Examples |
|---|---|---|
| **PATCH** `v1.2.x` | Bug fixes, copy tweaks, prompt adjustments, config changes | Fix a parsing bug, tweak LLM feedback wording, adjust a cron schedule |
| **MINOR** `v1.x.0` | New user-facing features or meaningful behaviour changes | New intent type, profile fields, weekly trend improvements |
| **MAJOR** `vx.0.0` | Breaking changes — DynamoDB schema changes, architectural rewrites | New table key structure, replacing Telegram with another channel |

## Workflow

```
push to main → auto-deploy to dev → test manually on dev bot
                                           ↓
                              ready to ship? create a release
                                           ↓
                         GitHub release → auto-deploy to prod
```

## How to release

1. Make sure dev bot is working as expected.
2. Pick the right version bump (see table above).
3. Create a GitHub release:
   ```bash
   gh release create v1.2.1 --title "v1.2.1" --notes "What changed and why."
   ```
4. CI runs tests → deploys to prod automatically.

## Guidelines

- **PATCH releases are cheap** — ship them often. A fix in dev should reach prod the same day.
- **Don't batch unrelated changes** into one release to avoid a version bump. Small, frequent releases are safer and easier to roll back.
- **MINOR releases** should have release notes that describe the feature from the user's perspective (in Spanish if user-facing).
- **MAJOR releases** require a DynamoDB migration plan before shipping — there is no rollback once the table schema changes.
- There is no staging environment — dev is the only gate before prod. Test thoroughly on the dev bot before releasing.
