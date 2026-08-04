#!/bin/bash
# GCE L4 VM 부팅 시 자동 실행되는 스크립트.
# 멱등(idempotent)하게 작성 — 재부팅/Spot 재시작 때 다시 돌아도 안전.
set -euo pipefail

MODEL="exaone3.5:7.8b"          # Ollama 생성 모델 — 지금은 롤백 경로 전용(아래 5번 주석)
EMBEDDING_MODEL="bge-m3"

# vLLM(생성) 설정. 모델은 docs/vllm.md §9에서 네 후보를 같은 조건으로 재측정해 확정했다
# (충실성 5개 항목 전부 0, 속도 1위, Apache 2.0).
VLLM_USER="dohyun0312"
VLLM_ENV="/home/$VLLM_USER/vllmenv"
VLLM_MODEL="Qwen/Qwen3-8B-AWQ"
# 백엔드가 보내는 `model` 필드와 정확히 일치해야 한다(settings.llm_model). docs/vllm.md §12.
VLLM_SERVED_NAME="qwen3-8b"
# 바이트로 직접 지정(≈11.6GiB). 비율(--gpu-memory-utilization) 대신 쓰는 이유는 모델을
# 바꿔도 KV 예산이 같아야 벤치가 공정하기 때문이다. 도출 근거는 docs/vllm.md §12 [확인 필요].
VLLM_KV_CACHE_BYTES=12446605210

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

# 5) 임베딩만 워밍업한다. **생성 모델(exaone)은 더 이상 상주시키지 않는다** — vLLM과 VRAM이
# 겹치기 때문이다(L4 24GB):
#     vLLM 가중치 5.0 + KV 11.6 = 16.6GB, bge-m3 0.7GB  -> 17.3GB (여유 6.7GB)
#     여기에 exaone 5.7GB를 상주시키면 23.0GB -> OOM 위험
# `ollama pull`은 그대로 둔다(디스크에만 있음) — 롤백 시 재다운로드 없이 쓰려는 것이다.
# ⚠️ 롤백(LLM_BASE_URL을 :11434로 되돌림) 시에는 **vLLM을 먼저 멈춰야 한다**
# (`systemctl stop vllm`). 안 멈추면 Ollama가 exaone을 올리다 OOM으로 죽는다. docs/vllm.md §6.
curl -s -X POST http://localhost:11434/api/embed \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$EMBEDDING_MODEL\",\"input\":\"워밍업\",\"keep_alive\":-1}" >/dev/null || true

# 6) vLLM(생성 전용) — 임베딩은 Ollama에 남긴다. 재임베딩(knowledge_chunk 936개)을 피하려는
# 결정이다(docs/vllm.md §4). 지금까지는 사람이 SSH로 손으로 띄워서 재부팅 한 번에 사라졌다.
if [ ! -x "$VLLM_ENV/bin/vllm" ]; then
  # 기존 VM에는 손으로 만든 venv가 이미 있다. 신규 VM에서만 타는 경로다(수 분 소요).
  sudo -u "$VLLM_USER" python3 -m venv "$VLLM_ENV"
  sudo -u "$VLLM_USER" "$VLLM_ENV/bin/pip" install --upgrade pip
  sudo -u "$VLLM_USER" "$VLLM_ENV/bin/pip" install "vllm==0.26.0"
fi

# nohup/setsid 대신 systemd를 쓴다 — 재부팅·크래시 복구를 OS가 해준다.
cat >/etc/systemd/system/vllm.service <<EOF
[Unit]
Description=vLLM OpenAI-compatible server (generation only)
After=network-online.target
Wants=network-online.target

[Service]
User=$VLLM_USER
Environment="HOME=/home/$VLLM_USER"
# FlashInfer 샘플러를 끈다 — 켜두면 이 조합(L4 + vllm 0.26)에서 기동이 실패한다.
Environment="VLLM_USE_FLASHINFER_SAMPLER=0"
ExecStart=$VLLM_ENV/bin/vllm serve $VLLM_MODEL \\
  --port 8000 \\
  --max-model-len 8192 \\
  --kv-cache-memory $VLLM_KV_CACHE_BYTES \\
  --max-num-seqs 8 \\
  --served-model-name $VLLM_SERVED_NAME
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable vllm
systemctl restart vllm
