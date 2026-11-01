# Moonraker Update Manager Integration

Nexus Screen can be updated from the **Update Manager** panel in Mainsail or Fluidd
once the following configuration is added to Moonraker.

---

## Configuration

Add this block to your `moonraker.conf` (usually at `~/printer_data/config/moonraker.conf`):

```ini
[update_manager nexus-screen]
type: git_repo
path: ~/nexus-screen
origin: https://github.com/omarmunoz5371/Nexus-Screen.git
primary_branch: main
is_system_service: False
```

Then restart Moonraker:

```bash
sudo systemctl restart moonraker
```

---

## Applying an Update

When an update is available, the Update Manager panel in Mainsail or Fluidd will show
a pending update for **nexus-screen**.

After Moonraker pulls the update, restart the service to apply it:

```bash
sudo systemctl restart nexus-screen
```

> **Note:** Moonraker updates the repository files but does not restart `nexus-screen.service`
> automatically because `is_system_service: False`. You must restart it manually or via a
> Moonraker macro.

---

## Manual Update

```bash
cd ~/nexus-screen
git pull
sudo systemctl restart nexus-screen
```

---

## Pinning to a Specific Version

To stay on a specific release tag:

```bash
cd ~/nexus-screen
git fetch --tags
git checkout v0.1.0-beta.1
sudo systemctl restart nexus-screen
```

To return to the latest main branch:

```bash
git checkout main
git pull
sudo systemctl restart nexus-screen
```
