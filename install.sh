#!/usr/bin/env bash
# StudyBuddy installer: prepares backend/frontend dependencies and reports hardware capabilities.

set -Eeuo pipefail
IFS=$'\n\t'

# Configure basic styling for terminal output.
if [[ -t 1 ]] && command -v tput >/dev/null 2>&1; then
    BOLD=$(tput bold)
    GREEN=$(tput setaf 2)
    YELLOW=$(tput setaf 3)
    RED=$(tput setaf 1)
    BLUE=$(tput setaf 4)
    RESET=$(tput sgr0)
else
    BOLD=""
    GREEN=""
    YELLOW=""
    RED=""
    BLUE=""
    RESET=""
fi

log_info() {
    printf "%b[INFO]%b %s\n" "$BLUE" "$RESET" "$1"
}

log_success() {
    printf "%b[OK]%b %s\n" "$GREEN" "$RESET" "$1"
}

log_warn() {
    printf "%b[WARN]%b %s\n" "$YELLOW" "$RESET" "$1"
}

log_error() {
    printf "%b[ERR]%b %s\n" "$RED" "$RESET" "$1" >&2
}

on_error() {
    log_error "install.sh hit an unexpected error. Check the log above for details."
}
trap 'on_error' ERR

abort() {
    trap - ERR
    log_error "$1"
    exit 1
}

print_banner() {
    cat <<'EOF'
============================================================
============================================================
 _____ _             _      ______           _     _       
/  ___| |           | |     | ___ \         | |   | |      
\ `--.| |_ _   _  __| |_   _| |_/ /_   _  __| | __| |_   _ 
 `--. \ __| | | |/ _` | | | | ___ \ | | |/ _` |/ _` | | | |
/\__/ / |_| |_| | (_| | |_| | |_/ / |_| | (_| | (_| | |_| |
\____/ \__|\__,_|\__,_|\__, \____/ \__,_|\__,_|\__,_|\__, |
                        __/ |                         __/ |
                       |___/                         |___/  
============================================================
Welcome to the StudyBuddy setup -
we will get both backend and frontend ready to go!
============================================================
EOF
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

prompt_step() {
    local prompt="$1"
    local choice
    while true; do
        read -rp "$(printf "%s [y]es/[n]o/[a]bort: " "$prompt")" choice || abort "Input interrupted. Aborting."
        choice=${choice,,}
        case "$choice" in
            y|yes)
                return 0
                ;;
            n|no)
                return 1
                ;;
            a|abort|q|quit)
                abort "Aborted by user: $prompt"
                ;;
            *)
                log_warn "Please answer with yes, no, or abort."
                ;;
        esac
    done
}

PYTHON_CMD=""
BACKEND_PY=""
BACKEND_INSTALL_SKIPPED=0
FRONTEND_INSTALL_SKIPPED=0

ensure_python() {
    if command_exists python3; then
        PYTHON_CMD=$(command -v python3)
    elif command_exists python; then
        PYTHON_CMD=$(command -v python)
    else
        abort "Python 3.10 or newer is required but was not found. Please install python3."
    fi

    local -a py_info
    if ! mapfile -t py_info < <("$PYTHON_CMD" -c 'import sys; print(sys.version_info.major); print(sys.version_info.minor); print(".".join(map(str, sys.version_info[:3])))'); then
        abort "Failed to query Python version from $PYTHON_CMD."
    fi
    if (( ${#py_info[@]} < 3 )); then
        abort "Unable to parse Python version from $PYTHON_CMD."
    fi

    local major="${py_info[0]}"
    local minor="${py_info[1]}"
    local version="${py_info[2]}"

    if [[ ! "$major" =~ ^[0-9]+$ || ! "$minor" =~ ^[0-9]+$ ]]; then
        abort "Unexpected Python version format reported by $PYTHON_CMD: ${py_info[*]}"
    fi

    if (( major < 3 || (major == 3 && minor < 10) )); then
        abort "Python >=3.10 is required. Detected $version at $PYTHON_CMD."
    fi

    log_success "Python $version detected at $PYTHON_CMD"
}

ensure_node_tools() {
    if ! command_exists node; then
        abort "Node.js 18+ is required but node was not found. Install Node.js and rerun this script."
    fi

    local node_version node_major
    node_version=$(node -p "process.versions.node")
    IFS='.' read -r node_major _ <<<"$node_version"
    if (( node_major < 18 )); then
        abort "Node.js >=18 is required. Detected $node_version."
    fi
    log_success "Node.js $node_version detected"

    if ! command_exists npm; then
        abort "npm was not found. It should come bundled with Node.js."
    fi
    log_success "npm $(npm --version) detected"
}

setup_backend() {
    local venv_dir="backend/.venv"

    if [[ -d "$venv_dir" ]]; then
        BACKEND_PY="$venv_dir/bin/python"
    fi

    if ! prompt_step "Install or update backend Python dependencies in backend/.venv?"; then
        BACKEND_INSTALL_SKIPPED=1
        log_warn "Skipped backend installation per user choice."
        if [[ -z "$BACKEND_PY" || ! -x "$BACKEND_PY" ]]; then
            log_warn "No existing backend virtual environment detected. Create one later and run pip install -r backend/requirements.txt."
        fi
        return
    fi

    BACKEND_INSTALL_SKIPPED=0
    log_info "Setting up backend virtual environment..."
    if [[ ! -d "$venv_dir" ]]; then
        log_info "Creating virtual environment at $venv_dir"
        "$PYTHON_CMD" -m venv "$venv_dir"
    else
        log_info "Reusing existing virtual environment at $venv_dir"
    fi

    BACKEND_PY="$venv_dir/bin/python"
    if [[ ! -x "$BACKEND_PY" ]]; then
        abort "Virtual environment seems broken. Expected Python at $BACKEND_PY."
    fi

    log_info "Upgrading pip and installing backend requirements (this can take a while)..."
    "$BACKEND_PY" -m pip install --upgrade pip wheel setuptools >/dev/null
    "$BACKEND_PY" -m pip install -r backend/requirements.txt
    log_success "Backend Python dependencies installed"
}

setup_frontend() {
    if ! prompt_step "Install frontend npm dependencies in frontend/?"; then
        FRONTEND_INSTALL_SKIPPED=1
        log_warn "Skipped frontend npm install per user choice."
        if [[ ! -d frontend/node_modules ]]; then
            log_warn "Frontend dependencies remain missing. Run npm install --prefix frontend when ready."
        fi
        return
    fi

    FRONTEND_INSTALL_SKIPPED=0
    log_info "Installing frontend npm dependencies..."
    npm install --prefix frontend
    log_success "Frontend npm dependencies installed"
}

verify_backend() {
    if [[ -z "$BACKEND_PY" || ! -x "$BACKEND_PY" ]]; then
        log_warn "Skipping backend verification because the virtual environment is unavailable."
        return
    fi

    log_info "Verifying required backend packages..."
    if "$BACKEND_PY" - <<'PY'
import importlib
modules = ("fastapi", "uvicorn", "torch", "transformers", "diffusers")
missing = []
for name in modules:
    try:
        importlib.import_module(name)
    except Exception as exc:  # noqa: BLE001
        missing.append(f"{name} ({exc})")

if missing:
    raise SystemExit("\n".join(missing))
PY
    then
        log_success "Backend environment check passed"
    else
        abort "Some backend packages failed to import. See messages above."
    fi
}

verify_frontend() {
    log_info "Verifying frontend toolchain..."

    if [[ ! -d frontend/node_modules ]]; then
        if (( FRONTEND_INSTALL_SKIPPED )); then
            log_warn "Frontend dependencies are not installed (skipped earlier). Run npm install --prefix frontend when ready."
            return
        fi
        abort "frontend/node_modules is missing. npm install may have failed."
    fi

    if npm --prefix frontend exec -- vite --version >/dev/null 2>&1; then
        log_success "Vite is available via npm exec"
    else
        log_warn "Could not run Vite from node_modules. You might need to reinstall frontend dependencies."
    fi

    log_success "Frontend dependency check passed"
}

hardware_report() {
    local python_for_hw="$PYTHON_CMD"
    if [[ -n "${BACKEND_PY:-}" && -x "$BACKEND_PY" ]]; then
        python_for_hw="$BACKEND_PY"
    fi

    log_info "Analyzing local hardware (RAM, VRAM, accelerator)..."
    if ! "$python_for_hw" - <<'PY'
import os
import subprocess
import sys


def get_total_ram_gb() -> float | None:
    try:
        if sys.platform.startswith("linux"):
            with open("/proc/meminfo", "r", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("MemTotal:"):
                        parts = line.split()
                        mem_kib = int(parts[1])
                        return round(mem_kib / (1024**2), 1)
        elif sys.platform == "Darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
            return round(int(out) / (1024**3), 1)
        elif os.name == "nt":
            out = subprocess.check_output(
                ["wmic", "ComputerSystem", "get", "TotalPhysicalMemory"],
                text=True,
            )
            for line in out.splitlines():
                line = line.strip()
                if line.isdigit():
                    return round(int(line) / (1024**3), 1)
    except Exception:  # noqa: BLE001
        return None
    return None


def get_cuda_devices_from_nvidia_smi() -> list[dict]:
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:  # noqa: BLE001
        return []

    devices: list[dict] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        name = parts[0]
        try:
            vram_gb = round(float(parts[1]) / 1024, 1)
        except ValueError:
            continue
        devices.append({"name": name, "vram_gb": vram_gb})
    return devices


ram_gb = get_total_ram_gb()
torch_available = False
torch_error = ""
cuda_available = False
mps_available = False
cuda_devices: list[dict] = []

try:
    import torch

    torch_available = True
    cuda_available = torch.cuda.is_available()
    if cuda_available:
        for idx in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(idx)
            cuda_devices.append(
                {
                    "name": props.name,
                    "vram_gb": round(props.total_memory / (1024**3), 1),
                },
            )
    if hasattr(torch.backends, "mps"):
        mps_available = torch.backends.mps.is_available()
except Exception as exc:  # noqa: BLE001
    torch_error = str(exc)


if not cuda_devices:
    cuda_devices = get_cuda_devices_from_nvidia_smi()
    cuda_available = bool(cuda_devices)


accelerator = "cpu"
if cuda_available and cuda_devices:
    accelerator = "cuda"
elif mps_available:
    accelerator = "mps"


max_vram = max((gpu["vram_gb"] for gpu in cuda_devices), default=None)

print("")
print("Hardware summary")
print("---------------")
if ram_gb is not None:
    print(f"- System RAM: {ram_gb:.1f} GB")
else:
    print("- System RAM: unknown (could not determine)")

cuda_state = "yes" if cuda_available else "no"
mps_state = "yes" if mps_available else "no"
print(f"- Accelerator mode: {accelerator.upper()} (CUDA available: {cuda_state}, MPS available: {mps_state})")

if cuda_devices:
    for idx, gpu in enumerate(cuda_devices, start=1):
        print(f"  GPU {idx}: {gpu['name']} - {gpu['vram_gb']:.1f} GB VRAM")
else:
    print("  No CUDA-capable GPU detected via PyTorch or nvidia-smi.")

if accelerator == "mps":
    print("  Apple Metal Performance Shaders backend detected.")

print("")
print("Model suggestions")
print("-----------------")

if accelerator == "cuda" and max_vram is not None:
    if max_vram >= 20:
        print("- Plenty of VRAM detected; you can explore larger models like meta-llama/Llama-3.1-70B (with quantization) or Mixtral variants.")
        print("- Image generation can stay enabled; try stabilityai/sdxl-turbo for fast diagrams.")
    elif max_vram >= 12:
        print("- Recommended text models: mistralai/Mistral-Nemo-Instruct-2407 or meta-llama/Llama-3.1-8B-Instruct.")
        print("- Image model: stabilityai/sdxl-turbo works well; disable images only if you need more VRAM for text models.")
    elif max_vram >= 8:
        print("- Stick with 7B/8B models such as Qwen/Qwen2.5-7B-Instruct or meta-llama/Llama-3.1-8B-Instruct.")
        print("- Consider disabling image generation or using lightweight checkpoints if you hit VRAM limits.")
    else:
        print("- GPU VRAM is limited; prefer 4-bit quantized 7B models or run on CPU.")
        print("- Turn off image generation (STUDYBUDDY_ENABLE_IMAGE_GENERATION=false) to conserve VRAM.")
elif accelerator == "mps":
    print("- Use models that provide Apple silicon wheels, e.g. meta-llama/Llama-3.1-8B-Instruct or Qwen/Qwen2.5-7B-Instruct.")
    print("- Keep image generation disabled unless you have plenty of unified memory available.")
else:
    print("- No hardware accelerator detected; backend will fall back to CPU.")
    print("- Expect slower responses. Keep defaults (mistralai/Mistral-7B-Instruct) and disable image generation for best results.")

if ram_gb is not None and ram_gb < 16:
    print("- System RAM is below 16 GB; keep concurrent workloads low to avoid swapping.")

if torch_available is False:
    if torch_error:
        print(f"- PyTorch import failed: {torch_error}")
    else:
        print("- PyTorch is not installed, so accelerator detection was limited.")
PY
    then
        log_success "Hardware analysis complete"
    else
        log_warn "Hardware detection was skipped because Python dependencies are missing."
    fi
}

main() {
    print_banner
    ensure_python
    ensure_node_tools
    setup_backend
    setup_frontend
    verify_backend
    verify_frontend
    hardware_report
    log_success "StudyBuddy is ready! Start everything with ./run_fullstack.sh or run backend/frontend scripts separately."
}

main "$@"
