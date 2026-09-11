#!/usr/bin/env bash
# =============================================================================
# AURELIUS — Developer Setup Script
# =============================================================================
# Usage:
#   bash scripts/setup.sh
#
# What this script does:
#   1. Verifies required tools (Python 3.12+, Node 18+, uv)
#   2. Creates backend virtual environment and installs dependencies
#   3. Installs frontend npm dependencies
#   4. Creates .env from .env.example (if .env doesn't exist)
#   5. Prints next steps
#
# This script is IDEMPOTENT: safe to run multiple times.
# =============================================================================

set -euo pipefail

# --- Terminal colors (safe fallback if not supported) -----------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
header()  { echo -e "\n${BOLD}$*${NC}"; }

# --- Locate project root (directory containing this script's parent) --------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

header "=== AURELIUS Developer Setup ==="
info "Project root: $PROJECT_ROOT"

# ---------------------------------------------------------------------------
# Step 1: Verify required tools
# ---------------------------------------------------------------------------
header "Step 1: Verifying required tools"

check_tool() {
    local name="$1"
    local min_version="$2"
    local cmd="$3"
    if command -v "$name" &>/dev/null; then
        local version
        version=$(eval "$cmd" 2>/dev/null || echo "unknown")
        success "$name found: $version"
    else
        error "$name not found. $min_version"
        exit 1
    fi
}

# Python
if command -v python3 &>/dev/null; then
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PYTHON_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
    PYTHON_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 12 ]; then
        success "Python $PYTHON_VERSION found"
    else
        error "Python 3.12+ required, found $PYTHON_VERSION"
        exit 1
    fi
else
    error "python3 not found. Install Python 3.12+."
    exit 1
fi

# Node.js
if command -v node &>/dev/null; then
    NODE_VERSION=$(node --version)
    NODE_MAJOR=$(node --version | sed 's/v//' | cut -d. -f1)
    if [ "$NODE_MAJOR" -ge 18 ]; then
        success "Node.js $NODE_VERSION found"
    else
        error "Node.js 18+ required, found $NODE_VERSION"
        exit 1
    fi
else
    error "node not found. Install Node.js 18+ (recommend: nvm)."
    exit 1
fi

# uv
UV_BIN=""
if command -v uv &>/dev/null; then
    UV_BIN="uv"
elif [ -f "$HOME/.local/bin/uv" ]; then
    UV_BIN="$HOME/.local/bin/uv"
elif [ -f "$HOME/.cargo/bin/uv" ]; then
    UV_BIN="$HOME/.cargo/bin/uv"
fi

if [ -n "$UV_BIN" ]; then
    UV_VERSION=$($UV_BIN --version)
    success "uv found: $UV_VERSION"
else
    warn "uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    UV_BIN="uv"
    success "uv installed: $(uv --version)"
fi

# ---------------------------------------------------------------------------
# Step 2: Backend setup
# ---------------------------------------------------------------------------
header "Step 2: Setting up Python backend"

BACKEND_DIR="$PROJECT_ROOT/backend"
info "Working in: $BACKEND_DIR"

cd "$BACKEND_DIR"
info "Running: uv sync --dev (creates .venv and installs all dependencies)"
$UV_BIN sync --dev
success "Backend virtual environment ready at: $BACKEND_DIR/.venv"

# ---------------------------------------------------------------------------
# Step 3: Frontend setup
# ---------------------------------------------------------------------------
header "Step 3: Setting up React/TypeScript frontend"

FRONTEND_DIR="$PROJECT_ROOT/frontend"
info "Working in: $FRONTEND_DIR"

cd "$FRONTEND_DIR"
info "Running: npm install"
npm install
success "Frontend dependencies installed"

# ---------------------------------------------------------------------------
# Step 4: Environment file
# ---------------------------------------------------------------------------
header "Step 4: Environment configuration"

cd "$PROJECT_ROOT"
if [ -f ".env" ]; then
    success ".env file already exists — skipping creation"
    warn "If you need to reset it, delete .env and run this script again."
else
    cp .env.example .env
    success ".env created from .env.example"
    warn "Edit .env and fill in your API keys before starting the server."
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
header "=== Setup Complete ==="
echo ""
echo "  Next steps:"
echo ""
echo "  1. Edit .env with your API keys (see .env.example for documentation)"
echo ""
echo "  2. Start the backend:"
echo "     cd backend"
echo "     source .venv/bin/activate"
echo "     uvicorn aurelius.api.main:app --reload --port 8000"
echo ""
echo "  3. Start the frontend (in a separate terminal):"
echo "     cd frontend"
echo "     npm run dev"
echo ""
echo "  4. Open in browser:"
echo "     Frontend: http://localhost:5173"
echo "     API docs: http://localhost:8000/docs"
echo "     Health:   http://localhost:8000/api/v1/health"
echo ""
echo "  5. Run backend tests:"
echo "     cd backend"
echo "     source .venv/bin/activate"
echo "     pytest                          # unit tests only (fast)"
echo "     pytest -m integration           # integration tests (requires network)"
echo ""
