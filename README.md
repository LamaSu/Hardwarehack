read me

## Projects

- [`drug-screen-platform/`](drug-screen-platform/) — plate layout designer and pipetting
  planner for an end-to-end drug screen on the Opentrons Flex (Track 3)

## Claude Code in Docker

From Git Bash in the repo root:

```bash
./scripts/start_claude.sh        # builds the image on first run, then starts Claude Code
./scripts/start_claude.sh bash   # shell in the same container
```

The repo is mounted at `/workspace`; the Claude Code login is kept in a Docker volume.
