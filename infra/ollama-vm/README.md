# Ollama L4 서버 (GCE)

FastAPI 백엔드가 HTTP로 호출할 로컬 LLM 서버. GCE VM에 L4 GPU 1장 + Ollama(개발) / vLLM(다중 사용자 서빙).

전제: `gcloud` CLI 로그인 및 프로젝트 설정 완료 (`gcloud auth login`, `gcloud config set project <PROJECT_ID>`).

> ⚠️ **아래 명령들의 인스턴스 이름 `ollama-l4`는 실제와 다르다.** 현재 운영 중인 VM은
> `ollama-t4-20260726-153805`(zone `asia-northeast3-b`)다. 문서를 만든 뒤 VM을 다시 만들면서
> 이름이 갈렸고 문서가 안 따라왔다. 복붙 전에 `gcloud compute instances list`로 확인할 것.

## 0. GPU 쿼터 확인 (제일 먼저)

신규 계정은 GPU 쿼터가 0 → VM 생성이 막힌다. 콘솔에서 확인/신청:

- IAM & Admin → Quotas → `NVIDIA L4 GPUs` (리전 `asia-northeast3`) 필터
- 값이 0이면 **Edit Quotas**로 1 이상 신청 (보통 몇 분~하루 내 승인)

```bash
# CLI로 현재 쿼터 확인
gcloud compute regions describe asia-northeast3 \
  --format="table(quotas.metric,quotas.limit,quotas.usage)" | grep -i gpu
```

## 1. 방화벽 — LLM 포트는 내부에서만

11434(Ollama=임베딩)·8000(vLLM=생성) **둘 다** 공개 인터넷에 절대 열지 않는다.
VPC 내부 대역에서만 허용:

```bash
gcloud compute firewall-rules create allow-llm-internal \
  --network=default \
  --direction=INGRESS \
  --action=ALLOW \
  --rules=tcp:11434,tcp:8000 \
  --source-ranges=10.128.0.0/9   # default VPC 내부 대역
```

> 기존에 `allow-ollama-internal`(11434만)이 있다면 8000을 추가한다:
> `gcloud compute firewall-rules update allow-ollama-internal --rules=tcp:11434,tcp:8000`

## 2. VM 생성 (Spot L4)

```bash
gcloud compute instances create ollama-l4 \
  --zone=asia-northeast3-b \
  --machine-type=g2-standard-4 \
  --accelerator=type=nvidia-l4,count=1 \
  --provisioning-model=SPOT \
  --instance-termination-action=STOP \
  --maintenance-policy=TERMINATE \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=100GB \
  --boot-disk-type=pd-balanced \
  --metadata-from-file=startup-script=startup.sh
```

- 드라이버+Ollama+모델 자동 설치까지 **첫 부팅에 5~10분** 걸린다. 완료 확인:
  ```bash
  gcloud compute ssh ollama-l4 --zone=asia-northeast3-b -- 'nvidia-smi && ollama list'
  ```
- 온디맨드로 쓰려면 `--provisioning-model` / `--instance-termination-action` 두 줄 빼면 된다.

## 3. 동작 확인

```bash
# VM 내부에서
gcloud compute ssh ollama-l4 --zone=asia-northeast3-b -- \
  'curl -s http://localhost:11434/api/generate -d "{\"model\":\"exaone3.5:7.8b\",\"prompt\":\"안녕하세요\",\"stream\":false}"'
```

## 4. 백엔드(Cloud Run)에서 호출

Cloud Run은 기본적으로 VPC 밖이라, 내부 IP의 Ollama에 닿으려면 **Serverless VPC Access 커넥터**가 필요하다.

1. 커넥터 생성 → Cloud Run 서비스에 연결(egress: private ranges).
2. 백엔드 환경변수 `LLM_BASE_URL=http://<VM_INTERNAL_IP>:11434` (코드가 읽는 실제 변수명은 `app/core/config.py`의 `llm_base_url` — `OLLAMA_BASE_URL`이 아니다).
3. VM 내부 IP 확인:
   ```bash
   gcloud compute instances describe ollama-l4 --zone=asia-northeast3-b \
     --format="value(networkInterfaces[0].networkIP)"
   ```

> 개발 초기엔 커넥터 없이, 방화벽에 본인 IP만 임시 허용해서 로컬에서 `curl`로 붙어 테스트해도 된다. 프로덕션 배선만 커넥터로.

## 5. vLLM (생성) 운영 — 역할이 둘로 나뉘어 있다

    :8000  vLLM   생성(챗봇·행동추천)   systemd 서비스 `vllm`
    :11434 Ollama 임베딩(bge-m3)만      systemd 서비스 `ollama`

**왜 나눴나**: vLLM은 한 프로세스에 한 모델이라 생성·임베딩을 같이 못 한다. 임베딩을
Ollama에 남긴 건 `knowledge_chunk` 936개를 재임베딩하지 않기 위해서다. 상세: `docs/vllm.md` §4.

```bash
# 상태·로그
gcloud compute ssh <VM> --zone=asia-northeast3-b -- 'systemctl status vllm --no-pager'
gcloud compute ssh <VM> --zone=asia-northeast3-b -- 'journalctl -u vllm -n 50 --no-pager'
# 동작 확인 (모델명은 --served-model-name 값과 일치해야 한다)
gcloud compute ssh <VM> --zone=asia-northeast3-b -- 'curl -s http://localhost:8000/v1/models'
```

**⚠️ 롤백은 순서가 있다.** `LLM_BASE_URL`을 `:11434`로 되돌리기 **전에** vLLM을 먼저 멈춘다:

```bash
gcloud compute ssh <VM> --zone=asia-northeast3-b -- 'sudo systemctl stop vllm'
```

안 멈추면 Ollama가 생성 모델(5.7GB)을 올리는 순간 L4 24GB가 넘쳐 OOM으로 죽는다.
vLLM이 16.6GB(가중치 5.0 + KV 11.6) + bge-m3 0.7GB를 이미 쥐고 있기 때문이다.
같은 이유로 `startup.sh`는 생성 모델을 **VRAM에 상주시키지 않는다**(디스크에만 받아둔다).

**⚠️ 모델을 바꾸면 백엔드 `settings.llm_model`도 같이 바꿔야 한다.** vLLM은 요청의 `model`
필드가 `--served-model-name`과 정확히 일치해야 응답한다(현재 `qwen3-8b`).

**GPU 정리는 PID를 특정해서 죽인다.** `pkill -f`(SSH 세션째 죽음)·`fuser -k 8000/tcp`
(EngineCore 자식이 고아로 남아 다음 기동이 OOM) 둘 다 실패로 확인됐다. `docs/vllm.md` §0.

```bash
gcloud compute ssh <VM> --zone=asia-northeast3-b -- 'nvidia-smi --query-compute-apps=pid,used_memory --format=csv'
```

## 비용 절약

- 안 쓸 땐 **끈다**: `gcloud compute instances stop ollama-l4 --zone=asia-northeast3-b` → 재시작 시 startup 스크립트가 다시 돌아 Ollama 자동 복구(설치는 캐시되어 빠름).
- **자동 재시작(선점 대비)**이 필요하면 이 VM을 Managed Instance Group(size 1)으로 감싸면 선점 후 자동 재생성된다. (필요해지면 추가)
- 발표 당일만 온디맨드로 재생성해 선점 리스크 제거.
