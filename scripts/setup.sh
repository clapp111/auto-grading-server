#!/bin/sh
# 개발 환경 온보딩 스크립트 — 클론 후 한 번 실행하면 필요한 로컬 설정을 일괄 적용한다.
#
# 새 온보딩 단계가 생기면:
#   1) 아래에 함수를 하나 추가하고
#   2) main()에서 호출만 추가한다.
set -eu

# 어디서 실행하든 저장소 루트 기준으로 동작
REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

log() { printf '\n\033[1;34m▶ %s\033[0m\n' "$1"; }

# ── git hook 활성화 ─────────────────────────────────────────────
# core.hooksPath는 로컬 설정이라 clone으로 전파되지 않는다. 각 개발자가 1회 켜야 한다.
setup_git_hooks() {
    log "git hook 활성화 (core.hooksPath=scripts)"
    git config core.hooksPath scripts
}

# ── 파이썬 의존성 설치 ──────────────────────────────────────────
# 의도한 가상환경을 활성화한 상태에서 실행하는 것을 전제로 한다.
install_dependencies() {
    log "파이썬 의존성 설치 (requirements.txt)"
    python -m pip install -r requirements.txt
}

# ── 온보딩 단계 실행 순서 ───────────────────────────────────────
main() {
    setup_git_hooks
    install_dependencies
    log "설정 완료"
}

main "$@"
