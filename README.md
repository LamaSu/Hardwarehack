# Hardwarehack

Physical AI for Science Hack (San Francisco, Oct 2026), Track 3: an end-to-end
drug screen on the Opentrons Flex. Design a plate in the browser, plan the
dilutions, generate and simulate the Flex protocol, then run it with a camera
snapshot of the deck before and after.

## Projects

- [`drug-screen-platform/`](drug-screen-platform/): Python planner, protocol
  generator, Flex client, web API and the `plate` / `flex` command-line tools
- [`web/`](web/): Next.js plate editor, worklist and robot control

## Run it (macOS or Windows)

Needs [uv](https://docs.astral.sh/uv/) and Node.js 20+.

```bash
# terminal 1: API on 127.0.0.1:8000
cd drug-screen-platform
uv sync
uv run python scripts/serve.py

# terminal 2: UI on http://127.0.0.1:3000
cd web
npm install
npm run dev
```

Both servers listen on 127.0.0.1 only, so nothing is reachable from the LAN.
If you also run a host firewall, block inbound connections on 3000 and 8000
and allow outbound TCP 31950 to the robot.

## Robot from the terminal

```bash
cd drug-screen-platform
uv run flex health --host <robot-ip>
uv run flex demo plate.json --host <robot-ip>   # check, protocol, simulate, before, run, after
uv run flex demo plate.json --mock              # rehearsal without a robot
```

Before the first real run, open the generated `runs/<plate>/protocol.py` and
check the deck constants at the top (pipettes, tip racks, stock rack, slots)
against the robot. Runs started over HTTP use no Labware Position Check
offsets.
