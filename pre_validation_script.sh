#!/usr/bin/env bash

# Helper formatting
BOLD='\033[1m'
NC='\033[0m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'

REPO_DIR="."
DOCKER_BUILD_TIMEOUT=300

log() { echo -e "$1"; }
pass() { echo -e "  ${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "  ${RED}[FAIL]${NC} $1"; }
hint() { echo -e "    ${YELLOW}Hint:${NC} $1"; }
stop_at() {
  echo -e "\n${RED}${BOLD}Validation failed at $1. Fix the errors above and try again.${NC}"
  exit 1
}

run_with_timeout() {
  local timeout=$1
  shift
  # Windows git bash fallback if timeout command is missing
  if command -v timeout &>/dev/null; then
    timeout "$timeout" "$@"
  else
    "$@"
  fi
}

log "${BOLD}Step 1/3: Checking Environment Structure${NC} ..."

if [ -f "$REPO_DIR/openenv.yaml" ]; then
  pass "openenv.yaml found"
else
  fail "openenv.yaml not found at root"
  stop_at "Step 1"
fi

log "${BOLD}Step 2/3: Running docker build${NC} ..."

if ! command -v docker &>/dev/null; then
  fail "docker command not found"
  hint "Install Docker: https://docs.docker.com/get-docker/"
  stop_at "Step 2"
fi

if [ -f "$REPO_DIR/Dockerfile" ]; then
  DOCKER_CONTEXT="$REPO_DIR"
elif [ -f "$REPO_DIR/server/Dockerfile" ]; then
  DOCKER_CONTEXT="$REPO_DIR/server"
else
  fail "No Dockerfile found in repo root or server/ directory"
  stop_at "Step 2"
fi

log "  Found Dockerfile in $DOCKER_CONTEXT"

docker build "$DOCKER_CONTEXT"
BUILD_OK=$?

if [ "$BUILD_OK" = "0" ]; then
  pass "Docker build succeeded"
else
  fail "Docker build failed"
  stop_at "Step 2"
fi

log "${BOLD}Step 3/3: Running openenv validate${NC} ..."

if ! command -v openenv &>/dev/null; then
  fail "openenv command not found"
  hint "Install it: pip install openenv-core"
  stop_at "Step 3"
fi

cd "$REPO_DIR" && openenv validate
VALIDATE_OK=$?

if [ "$VALIDATE_OK" = "0" ]; then
  pass "openenv validate passed"
else
  fail "openenv validate failed"
  stop_at "Step 3"
fi

printf "\n"
printf "${BOLD}========================================${NC}\n"
printf "${GREEN}${BOLD}  All 3/3 checks passed!${NC}\n"
printf "${GREEN}${BOLD}  Your submission is ready to submit.${NC}\n"
printf "${BOLD}========================================${NC}\n"
printf "\n"
exit 0
