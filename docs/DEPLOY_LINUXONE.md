# Deploying LoanLens on IBM LinuxONE (Community Cloud / L1CC)

> I could not view the "LinuxONE Setup & Tech Prep Session" video (YouTube blocked the transcript), and the exact
> Community Cloud details below (usernames, open ports, OS images) are from general knowledge. **Where the session
> or the portal says otherwise, follow them.** Verify each step on the real VM.

## 0. Rule of thumb
Run **training and inference on the LinuxONE VM** (`uname -m` → `s390x`). Don't ship a model trained on a laptop: pickles
of tree models can be endian-sensitive, and judges want inference executing on IBM Z. The zip contains **no trained model** on purpose.

## 1. Get a VM
Request/launch a virtual server in the LinuxONE Community Cloud portal (https://linuxone.cloud.marist.edu), choose an
Ubuntu / RHEL / SLES image, note the IP and login user, and add your SSH key if asked.
```bash
ssh <user>@<vm-ip>
uname -m          # expect s390x  → screenshot #1
lscpu | head -20  # screenshot #2
```

## 2. Copy the project
```bash
# from your laptop
scp loanlens.zip <user>@<vm-ip>:~
# on the VM
sudo apt-get update && sudo apt-get install -y unzip python3 python3-venv python3-pip   # Ubuntu
#  RHEL: sudo dnf install -y unzip python3 python3-pip      SLES: sudo zypper install -y unzip python3 python3-pip
unzip loanlens.zip && cd loanlens
```

## 3. Install + train + test (one command)
```bash
LOANLENS_DATASET=auto ./scripts/setup_linuxone.sh
```
This creates `.venv`, installs **core** deps only (numpy, pandas, scikit-learn, joblib), trains on the VM, finds a demo
profile, runs 17 tests, and writes `evidence/linuxone_evidence.json`.

**If `pip install` fails or takes forever (no s390x wheel → source build):** use distro packages instead.
```bash
sudo apt-get install -y python3-numpy python3-pandas python3-sklearn python3-joblib     # Ubuntu names
python3 -m venv --system-site-packages .venv && source .venv/bin/activate
python -m loanlens.train --dataset auto && python -m unittest discover -s tests -t .
```
(Needs scikit-learn ≥ 1.2. If the distro version is older, replace `sparse_output=False` with `sparse=False` in `features.py`.)
IBM's official ML lab for s390x is a good reference: https://github.com/linuxone-community-cloud/jupyter-lab-ml

No internet on the VM? Download German Credit on your laptop, `scp german.data` into `loanlens/data/`, then train with `--dataset german`.
If nothing is available, `--dataset synthetic` still demonstrates the workflow (the UI shows a "synthetic" banner).

## 4. Run the API on the VM (this is your "inference on IBM Z" proof)
```bash
export LOANLENS_REVIEWER_TOKEN='choose-a-long-random-string'
./scripts/run_api.sh 127.0.0.1 8000 &        # loopback only = secure default
./scripts/api_smoke.sh                        # curl evidence → screenshot #3 (include `uname -m` in the same terminal)
```


## 5. Run the custom dashboard

The API and custom dashboard run as separate processes on the LinuxONE VM.

In the API terminal, activate the virtual environment, set a long random reviewer token, and run `./scripts/run_api.sh 127.0.0.1 8000`.

In a second VM terminal, activate the virtual environment and run `python loanlens/web_ui.py`.

From Windows, open an SSH tunnel using your own key path and VM address:
`ssh -L 8080:127.0.0.1:8080 -i "C:/path/to/key.pem" linux1@YOUR_VM_IP`

Keep the tunnel open and visit http://127.0.0.1:8080/ in your browser. Keep the services bound to loopback and never share your reviewer token or private key.

Only expose ports publicly (`--host 0.0.0.0`) if the portal's firewall allows and you set the reviewer token; otherwise use the tunnel.

## 6. Optional: Docker
Only if Docker/Podman is available on your VM: `docker build -t loanlens . && docker run -p 8000:8000 -e LOANLENS_REVIEWER_TOKEN=... -v ll-data:/data loanlens`
(builds as s390x when built on the VM). Not required.

## 7. Evidence to capture (submission requires LinuxONE proof)
1. `uname -m` = `s390x` + `lscpu` header. 2. `setup_linuxone.sh` ending with tests OK. 3. `api_smoke.sh` output.
4. UI showing `s390x` banner + an assessment. 5. `evidence/linuxone_evidence.json` (latency p50/p95, versions, audit chain valid).
6. `curl -H "X-Reviewer-Token: $LOANLENS_REVIEWER_TOKEN" localhost:8000/audit` showing VALIDATION_FAILED / ASSESSED / CORRECTION_* events.

## 8. Claims you may and may not make
✔ "Inference and explanation run inside our LinuxONE instance (s390x)." ✔ "Audit log is hash-chained; tampering is detected."
✘ "Uses Telum / AI accelerator" — scikit-learn runs on CPU. `evidence` records whether `nnpa` appears in CPU features, nothing more.
✘ "Secure because it's on LinuxONE" ✘ "Encrypted at rest" (not implemented) ✘ "Fair / bias-free" ✘ "Predicts bank approval".
Future work worth naming: ONNX Runtime + IBM zDNN / Z Deep Learning Compiler for accelerated inference; pervasive encryption / confidential computing.
