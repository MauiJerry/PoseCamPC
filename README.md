# PoseCamPC (Phase 1.1

PoseCamPC is part of the Pose2Art project.

Minimal repo to run the Pose2Art camera app that:

- Reads webcam or video file
- Sends OSC landmarks
- Publishes video via NDI (using a **local** `ndi-python` wheel for Python 3.12)
- Uses `pyenv-win` to manage Python versions (3.12 now, 3.11 ready for fallback)

> We intentionally **do not** list `ndi-python` in `requirements.txt`.  
> Install the local `.whl` from `./ndi/` manually after setting up the venv.

---

## Prereqs (Windows 11)

### 1. Install **NDI Tools** and SDK
- Download from the [NDI Tools website](https://ndi.video/tools/)
- Run the installer, select all NDI Tools (includes the NDI runtime and SDK)
- This is required for `ndi-python` to function

### 2. Install **pyenv-win**
```powershell
Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile "./install-pyenv-win.ps1"
&"./install-pyenv-win.ps1"
```
Close and reopen your terminal so PATH changes take effect

Check installation:
```powershell
pyenv --version
```
expect v 3.1.1 or later

### Setup

Install Python 3.12 (and optional 3.11 for fallback)

```powershell
pyenv install 3.12.6
pyenv install 3.11.9   # optional
pyenv local 3.12.6
```
Run the setup scripts to create/ activate virtual env and install dependencies

```powershell
scripts/setup.bat
```
## Preflight Tests

preflight_tx.py and preflight_rx.py are included to confirm that OSC and NDI are working correctly before running the main app.  To run these, open two powershells in the project folder and run the commands

In one terminal (sender):
```powershell
run_tx.bat 
```
In another terminal (receiver/validator):
```powershell
run_rx.bat
```
### Expected output:

Receiver prints periodic NDI resolution/fps updates (e.g. NDI 1280x720 30.0 fps)

OSC messages arrive (/image-width, /image-height, /numLandmarks, /p1/<name> …)

OK summary once metadata is seen

If you want this to exactly match the current TouchDesigner address schema, keep /p1/<name> (triples).
To use the older per-axis messages, uncomment those lines in preflight_tx.py.

## Editing

VSCode is my preferred environment. the .vscode folder (should have) several files to make it so included in the git.

## Running
```powershell
scripts/run.bat
```
TKinker UI should appear.

1. select either the webcam radio button or browse for file
2. check the NDI Video Out Name (posePC)
3. check the OSC Output URL (127.0.0.1  5005)
4. start NDI
5. start OSC
6. Play Video (opens composite video in window)

you must do all this to see the results show in the client tool (eg TouchDesigner)