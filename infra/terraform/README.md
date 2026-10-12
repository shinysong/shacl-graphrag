# Terraform (placeholder)

AWS 서버·스토리지·(후반) Neptune 스택을 여기 둡니다.

**현재:** 파일 없음. EC2 사양·리전·계정 정책이 확정되면 추가합니다.

예정 모듈 초안:

- `network` — VPC/subnet/SG (DB 포트는 SSH 터널만)
- `compute` — EC2 + EBS
- `storage` — S3 버킷 (실험 산출물)
- `neptune` — Serverless, 단기간만 (optional)

로컬에서 state를 커밋하지 마세요 (`.gitignore`에 `*.tfstate`, `.terraform/` 포함됨).
