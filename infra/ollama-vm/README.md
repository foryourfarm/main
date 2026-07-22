# Ollama L4 서버 (GCE)

Spring Boot 백엔드가 HTTP로 호출할 로컬 LLM 서버. GCE VM에 L4 GPU 1장 + Ollama.

전제: `gcloud` CLI 로그인 및 프로젝트 설정 완료 (`gcloud auth login`, `gcloud config set project <PROJECT_ID>`).

## 0. GPU 쿼터 확인 (제일 먼저)

신규 계정은 GPU 쿼터가 0 → VM 생성이 막힌다. 콘솔에서 확인/신청:

- IAM & Admin → Quotas → `NVIDIA L4 GPUs` (리전 `asia-northeast3`) 필터
- 값이 0이면 **Edit Quotas**로 1 이상 신청 (보통 몇 분~하루 내 승인)

```bash
# CLI로 현재 쿼터 확인
gcloud compute regions describe asia-northeast3 \
  --format="table(quotas.metric,quotas.limit,quotas.usage)" | grep -i gpu
```

## 1. 방화벽 — Ollama 포트는 내부에서만

11434를 공개 인터넷에 절대 열지 않는다. VPC 내부 대역에서만 허용:

```bash
gcloud compute firewall-rules create allow-ollama-internal \
  --network=default \
  --direction=INGRESS \
  --action=ALLOW \
  --rules=tcp:11434 \
  --source-ranges=10.128.0.0/9   # default VPC 내부 대역
```

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
2. 백엔드 환경변수 `OLLAMA_BASE_URL=http://<VM_INTERNAL_IP>:11434`.
3. VM 내부 IP 확인:
   ```bash
   gcloud compute instances describe ollama-l4 --zone=asia-northeast3-b \
     --format="value(networkInterfaces[0].networkIP)"
   ```

> 개발 초기엔 커넥터 없이, 방화벽에 본인 IP만 임시 허용해서 로컬에서 `curl`로 붙어 테스트해도 된다. 프로덕션 배선만 커넥터로.

## 비용 절약

- 안 쓸 땐 **끈다**: `gcloud compute instances stop ollama-l4 --zone=asia-northeast3-b` → 재시작 시 startup 스크립트가 다시 돌아 Ollama 자동 복구(설치는 캐시되어 빠름).
- **자동 재시작(선점 대비)**이 필요하면 이 VM을 Managed Instance Group(size 1)으로 감싸면 선점 후 자동 재생성된다. (필요해지면 추가)
- 발표 당일만 온디맨드로 재생성해 선점 리스크 제거.
