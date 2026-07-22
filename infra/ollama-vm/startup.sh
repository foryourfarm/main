#!/bin/bash
# GCE L4 VM 부팅 시 자동 실행되는 스크립트.
# 멱등(idempotent)하게 작성 — 재부팅/Spot 재시작 때 다시 돌아도 안전.
set -euo pipefail

MODEL="exaone3.5:7.8b"

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
