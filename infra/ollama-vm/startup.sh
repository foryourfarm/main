#!/bin/bash
# GCE L4 VM 부팅 시 자동 실행되는 스크립트.
# 멱등(idempotent)하게 작성 — 재부팅/Spot 재시작 때 다시 돌아도 안전.
set -euo pipefail

MODEL="exaone3.5:7.8b"
EMBEDDING_MODEL="bge-m3"

# GCE startup-script는 root로 돌지만 $HOME이 비어 있다 — ollama CLI가 모델 저장 경로를
# 계산할 때 $HOME을 참조해 죽는다(실측: "panic: $HOME is not defined").
export HOME=/root

# 1) NVIDIA 드라이버 (없을 때만 설치)
if ! command -v nvidia-smi &>/dev/null; then
  curl -fsSL https://raw.githubusercontent.com/GoogleCloudPlatform/compute-gpu-installation/main/linux/install_gpu_driver.py -o /tmp/install_gpu_driver.py
  python3 /tmp/install_gpu_driver.py
fi

# 2) Ollama (없을 때만 설치) — 설치 스크립트가 systemd 서비스까지 등록해줌
if ! command -v ollama &>/dev/null; then
  curl -fsSL https://ollama.com/install.sh | sh
fi

# 3) 외부(백엔드)에서 접근 가능하도록 0.0.0.0 바인딩. 노출은 방화벽으로 막음.
mkdir -p /etc/systemd/system/ollama.service.d
cat >/etc/systemd/system/ollama.service.d/override.conf <<'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF
systemctl daemon-reload
systemctl enable ollama
systemctl restart ollama

# 4) 모델 pull (이미 있으면 no-op)
sleep 5
ollama pull "$MODEL"
ollama pull "$EMBEDDING_MODEL"

# 5) 워밍업 — VRAM 콜드로드(실측: exaone 67초, bge-m3 18초)를 실사용자 첫 요청이 아니라
# 부팅 과정에서 미리 흡수한다. keep_alive:-1이라 이후 요청은 상주된 채로 빠르게 응답한다.
curl -s -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL\",\"prompt\":\"안녕\",\"stream\":false,\"keep_alive\":-1}" >/dev/null || true
curl -s -X POST http://localhost:11434/api/embed \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$EMBEDDING_MODEL\",\"input\":\"워밍업\",\"keep_alive\":-1}" >/dev/null || true
