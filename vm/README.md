# Windows VM for the rig

The Python-scripting Dolphin build ships for Windows only. On a Linux lab PC, run it in a local Windows VM. [`compose.yml`](compose.yml) runs one with [dockurr/windows](https://github.com/dockur/windows) (MIT), which runs Windows under KVM inside a Docker container.

The VM stays on the lab PC. Its ports listen on `127.0.0.1` only, the lab is shared into it as drive `Z:`, and nothing in it is uploaded anywhere.

## Limits

- **No GPU acceleration.** The VM has a basic display adapter, so Dolphin renders in software and runs well below full speed. That slows replays down but doesn't change their results, because emulated time doesn't depend on wall-clock speed.
- **Windows licence:** dockurr/windows downloads Windows from Microsoft and doesn't activate it. You need your own licence.
- **Docker Engine, not Docker Desktop:** Docker Desktop on Linux doesn't give containers KVM.

## 1. Start the VM (on the Linux PC)

1. Check that KVM works: `sudo apt install cpu-checker && kvm-ok` should say KVM acceleration can be used.
2. Install Docker Engine and the compose plugin (docs.docker.com/engine/install/ubuntu/), and add yourself to the `docker` group.
3. Pick a folder for the VM's disk, **outside every repo and every cloud-synced folder**. It needs about 64 GB. Treat it like the lab: it can end up holding Dolphin caches made from the disc. Back it up with the lab or not at all.
4. Start it:

   ```sh
   cd ~/Develop/rusty-arms/oracle/vm
   export LAB=~/Develop/rusty-arms/ma-lab
   export VM_STORAGE=~/Develop/rusty-arms/windows-vm
   docker compose up -d
   ```

5. Open <http://127.0.0.1:8006> and wait for Windows to install itself. The first start downloads Windows and takes a while.

## 2. Set up Windows (inside the VM)

Connect with remote desktop to `127.0.0.1:3389` (Remmina is on Pop!_OS), user `Docker`, password `admin`.

1. **Change the password** (Settings → Accounts → Sign-in options).
2. **Install Python 3.12** for Windows from python.org. Tick "Add python.exe to PATH".
3. **Install the scripting Dolphin:** from Felk's fork on GitHub, download the Windows build from the "Python Scripting Preview 4" release and unpack it to `C:\dolphin-scripting\`.
4. **Get the rig:** install Git for Windows and clone this repo to `C:\rusty-arms\oracle`, or download it as a ZIP and unpack it there.
5. **Turn on SSH,** so an observer session on the Linux side can start replays. In PowerShell, run as administrator:

   ```powershell
   Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
   Set-Service sshd -StartupType Automatic
   Start-Service sshd
   ```

6. Check that drive `Z:` shows the lab's folders.

## 3. Run the smoke test

**From the VM's desktop** (the reliable way). In PowerShell, in the remote desktop session:

```powershell
cd C:\rusty-arms\oracle
python -m oracle.replay examples\smoke.inputs --watch examples\smoke.watch `
    --dolphin C:\dolphin-scripting\Dolphin.exe --disc Z:\disc\<image> `
    --out Z:\traces\smoke --shots Z:\captures\smoke --repeat 2 --timeout 1800
```

It should end with "2 runs identical". The outputs land in the lab's `traces/` and `captures/` folders through drive `Z:`. Software rendering is slow, hence the long `--timeout`.

**From the Linux PC over SSH,** which is how an observer session would start a replay:

```sh
ssh -p 2222 Docker@127.0.0.1 "cd C:\rusty-arms\oracle && python -m oracle.replay examples\smoke.inputs --watch examples\smoke.watch --dolphin C:\dolphin-scripting\Dolphin.exe --disc Z:\disc\<image> --out Z:\traces\smoke-ssh --shots Z:\captures\smoke-ssh --timeout 1800"
```

This may fail: programs started over SSH on Windows have no desktop, and Dolphin needs one to draw. If it does, report it, and the next rig change adds a bridge that starts runs in the desktop session.

If Dolphin can't start its video backend in either case, add `--dolphin-arg=--video_backend=Software Renderer` and say so in the report.
