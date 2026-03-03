# Kubernetes Single-Node GPU Setup

## Overview

Step-by-step guide for setting up a **single-node Kubernetes cluster** with
**NVIDIA GPU** support on a dedicated machine (tested on Surface Book 3 with
NVIDIA GeForce GTX 1660 Ti). The end result is a fully functional K8s control
plane that can schedule GPU workloads.

**Target state after completing this guide:**

- Ubuntu Server 24.04 LTS installed (UEFI, GPT)
- NVIDIA proprietary driver installed and verified
- containerd runtime with systemd cgroups
- NVIDIA Container Toolkit configured
- Kubernetes 1.35 via kubeadm (single-node, untainted)
- Flannel CNI networking
- NVIDIA RuntimeClass + Device Plugin
- GPU-enabled Pod verified with `nvidia-smi`

---

## Hardware & Prerequisites

| Component | Requirement |
|-----------|-------------|
| CPU | x86_64 (Intel or AMD) |
| RAM | 8 GB minimum (16 GB recommended) |
| Storage | 50 GB minimum (SSD recommended) |
| GPU | NVIDIA with CUDA support |
| Network | Ethernet or WiFi |
| USB drive | 8 GB+ for installer |
| Host machine | For creating the bootable USB (Rufus on Windows) |

---

## Phase 1 — Create Bootable USB

### 1.1 Download the ISO

Download **Ubuntu Server 24.04 LTS** from
[ubuntu.com/download/server](https://ubuntu.com/download/server).

File: `ubuntu-24.04.x-live-server-amd64.iso`

### 1.2 Flash with Rufus

Download [Rufus](https://rufus.ie/) on a Windows machine and configure:

| Setting | Value |
|---------|-------|
| Device | Your USB drive |
| Boot selection | The downloaded `.iso` file |
| Persistent partition | 0 (none) |
| **Partition scheme** | **GPT** |
| **Target system** | **UEFI (non-CSM)** |
| File system | FAT32 |
| Cluster size | Default |

> **Important:** Do NOT use MBR. Modern hardware (anything from ~2013 onward)
> uses UEFI. GPT + UEFI avoids Secure Boot and driver signing issues with
> NVIDIA later.

When Rufus prompts for write mode, select **ISO mode (Recommended)**.

### 1.3 BIOS/UEFI Settings

Before booting from USB, enter BIOS/UEFI on the target machine and verify:

- **Boot mode** = UEFI
- **Secure Boot** = can remain ON (Ubuntu handles it)
- **USB boot** = enabled

Boot from the USB drive and select **Try or Install Ubuntu Server**.

---

## Phase 2 — Install Ubuntu Server 24.04 LTS

The installer runs in text mode. Follow each screen in order:

### 2.1 Language

Select: **English**

> Use English even on non-English systems. Kubernetes logs, error messages,
> and community documentation are all in English. This avoids locale-related
> issues with scripts and tooling.

### 2.2 Keyboard Layout

Select your physical keyboard layout (e.g., **Spanish** for an ES keyboard).

### 2.3 Installation Type

Select: **Ubuntu Server** (full, not minimal)

Do **NOT** select:
- ~~Ubuntu Server (minimal)~~ — missing dependencies needed later
- ~~Search for third-party drivers~~ — we install NVIDIA drivers manually

### 2.4 Network Configuration

If **Ethernet** is available, it will auto-configure via DHCP. Prefer Ethernet
over WiFi for server stability.

If only **WiFi** is available:
1. Select the WLAN interface
2. Choose your network SSID
3. Enter WiFi password
4. Save

Verify the interface shows a DHCP address (e.g., `192.168.1.x`), then select
**Done**.

### 2.5 Proxy

Leave blank → **Done**

### 2.6 Archive Mirror

Keep the default (`http://archive.ubuntu.com/ubuntu`) → **Done**

Ubuntu auto-redirects to a geographically close mirror.

### 2.7 Storage Configuration

Select: **Use an entire disk**

| Option | Value |
|--------|-------|
| Disk | Your primary disk (NOT the USB) |
| Set up as LVM group | **Yes** (checked) |
| Encrypt with LUKS | **No** (unchecked) |

> **Why LVM?** Allows future volume resizing, snapshots, and flexibility.
>
> **Why no encryption?** Adds boot complexity and overhead with no real benefit
> for a homelab Kubernetes node. Unattended reboots (e.g., after kernel
> updates) would require manual passphrase entry.

Confirm the destructive action → **Continue**

### 2.8 Profile Setup

| Field | Recommended value |
|-------|-------------------|
| Your name | Your name |
| Server name | `kube-server` |
| Username | `kiko` (or your preference) |
| Password | Strong password (write it down) |

### 2.9 Ubuntu Pro

Select: **Skip for now**

Not needed for a homelab Kubernetes setup.

### 2.10 OpenSSH Server

Select: **Yes — Install OpenSSH server**

> **Critical.** SSH is the primary way to manage the server. Without it you
> must be physically at the machine for every command.

### 2.11 Featured Server Snaps

**Do NOT select anything.** Leave all options unchecked.

Notably, do NOT install `microk8s` — we use `kubeadm` for full control over
the runtime, CNI, and GPU configuration.

Select **Done**.

### 2.12 Wait for Installation

The installer runs for 5–15 minutes. When complete:

1. Select **Reboot Now**
2. **Remove the USB drive** when prompted
3. Let the machine boot from the internal disk

### 2.13 First Login

You should see:

```
Ubuntu 24.04 LTS kube-server tty1

kube-server login:
```

Log in with the username and password from step 2.8.

> **Note:** The `DRM-Master device location failed: -19` message during boot
> is normal. It means the kernel tried to initialize a graphics device before
> the NVIDIA driver is installed. Completely harmless on a headless server.

---

## Phase 3 — Post-Install & SSH Access

### 3.1 Find the Server IP

```bash
ip a
```

Look for the IP on your network interface (e.g., `inet 192.168.1.143/24` on
`eth0` or `wlan0`).

### 3.2 Connect via SSH

From your workstation (using Terminal, Termius, PuTTY, etc.):

```bash
ssh kiko@192.168.1.143
```

Accept the host key fingerprint on first connection.

> From this point forward, all commands are run over SSH. You no longer need
> a monitor or keyboard on the server.

### 3.3 Update the System

```bash
sudo apt update && sudo apt upgrade -y
```

Reboot if kernel updates were applied:

```bash
sudo reboot
```

Reconnect via SSH after ~30 seconds.

---

## Phase 4 — NVIDIA Driver Installation

### 4.1 List Available GPU Drivers

```bash
sudo ubuntu-drivers list --gpgpu
```

Expected output (varies by GPU):

```
nvidia-driver-550
nvidia-driver-545
nvidia-driver-535
```

### 4.2 Install the Recommended Driver

```bash
sudo ubuntu-drivers install --gpgpu
```

This automatically selects the best driver for your hardware.

### 4.3 Reboot

```bash
sudo reboot
```

### 4.4 Verify

```bash
nvidia-smi
```

**Expected output:**

```
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 550.xx    Driver Version: 550.xx    CUDA Version: 12.x          |
|-------------------------------+----------------------+----------------------+
| GPU  Name        Persistence-M | Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp  Perf  Pwr:Usage/Cap |         Memory-Usage | GPU-Util  Compute M. |
|===============================+======================+======================|
|   0  NVIDIA GeForce ...   Off | 00000000:XX:00.0 Off |                  N/A |
| ...                           |      0MiB / XXXXX MiB|      0%      Default |
+-------------------------------+----------------------+----------------------+
```

Also verify the driver module:

```bash
cat /proc/driver/nvidia/version
```

> **Troubleshooting — `nvidia-smi` fails:**
>
> - **Secure Boot blocking the module:** Check `dmesg | grep -i nvidia`.
>   If you see signature errors, either disable Secure Boot in BIOS or
>   sign the module with MOK (Machine Owner Key).
> - **Wrong driver installed:** Run `sudo apt remove --purge 'nvidia-*'`,
>   reboot, and retry from step 4.2.
> - **Module not loaded:** Run `sudo modprobe nvidia` and check
>   `lsmod | grep nvidia`.

---

## Phase 5 — Kernel Modules & System Configuration

These settings are required by both containerd and kubelet.

### 5.1 Load Required Kernel Modules

```bash
sudo tee /etc/modules-load.d/k8s.conf >/dev/null <<'EOF'
overlay
br_netfilter
EOF

sudo modprobe overlay
sudo modprobe br_netfilter
```

### 5.2 Configure Sysctl Parameters

```bash
sudo tee /etc/sysctl.d/99-k8s-cri.conf >/dev/null <<'EOF'
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF

sudo sysctl --system
```

### 5.3 Disable Swap

kubelet refuses to start if swap is active.

```bash
sudo swapoff -a
sudo sed -i.bak '/\sswap\s/s/^/#/' /etc/fstab
```

Verify:

```bash
free -h | grep -i swap
# Swap:          0B          0B          0B
```

### 5.4 Verify cgroup v2

```bash
stat -fc %T /sys/fs/cgroup
# Expected: cgroup2fs
```

---

## Phase 6 — Install containerd

### 6.1 Install the Package

```bash
sudo apt-get update
sudo apt-get install -y containerd
```

### 6.2 Generate Default Config with systemd Cgroups

```bash
sudo mkdir -p /etc/containerd
sudo containerd config default | sudo tee /etc/containerd/config.toml >/dev/null
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
```

> **Why `SystemdCgroup = true`?** Aligns containerd with kubelet and the
> systemd cgroup driver. Mismatched cgroup drivers cause `kubelet` startup
> failures and mysterious Pod crashes.

### 6.3 Enable and Start

```bash
sudo systemctl enable --now containerd
sudo systemctl restart containerd
```

Verify:

```bash
systemctl status containerd --no-pager
# Active: active (running)
```

---

## Phase 7 — NVIDIA Container Toolkit

This allows containerd to inject the GPU into containers.

### 7.1 Add the NVIDIA Repository

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
```

### 7.2 Install the Toolkit

```bash
sudo apt-get install -y nvidia-container-toolkit
```

### 7.3 Configure containerd to Use the NVIDIA Runtime

```bash
sudo nvidia-ctk runtime configure --runtime=containerd --set-as-default
sudo systemctl restart containerd
```

> **Why `--set-as-default`?** The NVIDIA device plugin DaemonSet runs
> without `runtimeClassName`, so it uses the default containerd runtime.
> Without this flag, the plugin can't access NVML to discover GPUs and
> crashes with `Incompatible strategy detected auto`. Setting nvidia as
> the default runtime ensures all containers (including the device plugin
> itself) can see the GPU.

Verify configuration was applied:

```bash
cat /etc/containerd/conf.d/99-nvidia.toml
```

> **Note:** Newer versions of `nvidia-ctk` write to a **drop-in file**
> (`/etc/containerd/conf.d/99-nvidia.toml`) instead of modifying
> `config.toml` directly. If you grep `config.toml` for "nvidia" and
> get nothing, that is expected — check the drop-in file above instead.

You should see the `nvidia` runtime handler defined, similar to:

```toml
[plugins."io.containerd.grpc.v1.cri".containerd.runtimes.nvidia]
  privileged_without_host_devices = false
  runtime_engine = ""
  runtime_root = ""
  runtime_type = "io.containerd.runc.v2"
[plugins."io.containerd.grpc.v1.cri".containerd.runtimes.nvidia.options]
  BinaryName = "/usr/bin/nvidia-container-runtime"
```

> **Note:** You do NOT need the full CUDA toolkit on the host. The host
> driver + NVIDIA Container Toolkit is sufficient. CUDA libraries are
> provided by the container images themselves.

---

## Phase 8 — Install Kubernetes (kubeadm)

### 8.1 Install Prerequisites

```bash
sudo apt-get update
sudo apt-get install -y apt-transport-https ca-certificates curl gpg
```

### 8.2 Add the Kubernetes Repository

```bash
sudo mkdir -p -m 755 /etc/apt/keyrings

curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.35/deb/Release.key \
  | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.35/deb/ /' \
  | sudo tee /etc/apt/sources.list.d/kubernetes.list >/dev/null
```

### 8.3 Install kubeadm, kubelet, kubectl

```bash
sudo apt-get update
sudo apt-get install -y kubelet kubeadm kubectl
sudo apt-mark hold kubelet kubeadm kubectl
```

> `apt-mark hold` prevents accidental upgrades that could break the cluster.

---

## Phase 9 — Initialize the Cluster

### 9.1 kubeadm init

```bash
sudo kubeadm init --pod-network-cidr=10.244.0.0/16
```

The `--pod-network-cidr` matches Flannel's default range (installed next).

### 9.2 Configure kubectl for Your User

```bash
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown "$(id -u):$(id -g)" $HOME/.kube/config
```

### 9.3 Allow Scheduling on the Control Plane

Since this is a single-node cluster, remove the taint that prevents workloads
from running on the control plane:

```bash
kubectl taint nodes --all node-role.kubernetes.io/control-plane-
```

### 9.4 Verify

```bash
kubectl get nodes
```

Expected:

```
NAME          STATUS     ROLES           AGE   VERSION
kube-server   NotReady   control-plane   30s   v1.35.x
```

Status will be `NotReady` until the CNI is installed (next step).

---

## Phase 10 — Install CNI (Flannel)

```bash
kubectl apply -f https://raw.githubusercontent.com/flannel-io/flannel/master/Documentation/kube-flannel.yml
```

Wait for all system Pods to be running:

```bash
kubectl get pods -A -w
```

**Expected:** `coredns-*` and `kube-flannel-*` Pods reach `Running` status.
The node status should change to `Ready`:

```bash
kubectl get nodes
# NAME          STATUS   ROLES           AGE   VERSION
# kube-server   Ready    control-plane   2m    v1.35.x
```

---

## Phase 11 — Expose GPU to Kubernetes

### 11.1 Create the NVIDIA RuntimeClass

```bash
cat <<'EOF' > runtimeclass-nvidia.yaml
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: nvidia
handler: nvidia
EOF

kubectl apply -f runtimeclass-nvidia.yaml
kubectl get runtimeclass
```

### 11.2 Install the NVIDIA Device Plugin

```bash
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.18.2/deployments/static/nvidia-device-plugin.yml
```

> **Verify the apply succeeded.** You MUST see output like
> `daemonset.apps/nvidia-device-plugin-daemonset created`. If the command
> returns silently with no output, it failed — check network connectivity
> and that the URL returns HTTP 200:
> ```bash
> curl -sL -o /dev/null -w "%{http_code}" https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.18.2/deployments/static/nvidia-device-plugin.yml
> ```

Wait for the DaemonSet Pod to start:

```bash
kubectl -n kube-system get daemonset | grep nvidia
kubectl -n kube-system get pods | grep nvidia
# nvidia-device-plugin-daemonset-xxxxx   1/1   Running   0   30s
```

### 11.3 Verify GPU is Visible to the Node

```bash
kubectl describe node "$(hostname)" | grep -A5 'Capacity:'
```

**Expected:** The output includes `nvidia.com/gpu: 1` (or more, depending on
hardware).

```
Capacity:
  cpu:                8
  memory:          16384Ki
  nvidia.com/gpu:  1
```

---

## Phase 12 — GPU Smoke Test

```bash
cat <<'EOF' > gpu-smoke.yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-smoke
spec:
  restartPolicy: Never
  runtimeClassName: nvidia
  containers:
    - name: cuda-test
      image: nvidia/cuda:12.6.3-base-ubuntu24.04
      command: ["nvidia-smi"]
      resources:
        limits:
          nvidia.com/gpu: 1
EOF

kubectl apply -f gpu-smoke.yaml
kubectl wait --for=condition=Ready pod/gpu-smoke --timeout=120s || true
kubectl logs gpu-smoke
```

**Expected:** The `nvidia-smi` output table, showing the GPU from inside the
container.

Clean up:

```bash
kubectl delete pod gpu-smoke
```

---

## Quick Troubleshooting Reference

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `kubelet` won't start | Swap is active | `sudo swapoff -a` |
| `bridge-nf-call-iptables` missing | Kernel modules not loaded | `sudo modprobe br_netfilter && sudo sysctl --system` |
| GPU not in node capacity | Device plugin not running or can't access NVML | `kubectl -n kube-system logs -l name=nvidia-device-plugin-ds` |
| `nvidia-smi` fails on host | Driver not loaded / Secure Boot | `dmesg \| grep -i nvidia \| tail -20` |
| Pod stuck in `ContainerCreating` | containerd can't find nvidia runtime | Re-run `sudo nvidia-ctk runtime configure --runtime=containerd && sudo systemctl restart containerd` |
| Node stays `NotReady` | CNI not installed | Apply Flannel manifest (Phase 10) |

---

## Version Reference

This guide was validated with:

| Component | Version |
|-----------|---------|
| Ubuntu Server | 24.04 LTS |
| Kubernetes | 1.35.1 |
| containerd | OS package (apt) |
| NVIDIA Driver | 570.211.01 (via `ubuntu-drivers`) |
| CUDA (in-container) | 12.8 |
| NVIDIA Container Toolkit | Latest stable |
| NVIDIA Device Plugin | v0.18.2 |
| Flannel | Latest master |
| Target Hardware | Surface Book 3, GTX 1660 Ti (6 GB) |

---

## What's Next

With Kubernetes and GPU access confirmed, the cluster is ready for workloads.
Subsequent steps (not covered here) include:

- **Local Path Provisioner** for PersistentVolumeClaims
- **Helm** for package management
- **Deploying the Travel Planner stack** (Ollama, FastAPI, PostgreSQL, etc.)
- **Monitoring** with Prometheus + Grafana

See [architecture.md](architecture.md) for the application topology that runs
on top of this cluster.
