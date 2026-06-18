# CodeBuddy — GitHub PR 자동 리뷰 Agent

Amazon Bedrock Agent 기반으로 GitHub Pull Request를 자동으로 분석하고, 코드 스타일/보안 취약점/복잡도를 점검하고, 단위 테스트와 리팩토링까지 제안한 뒤 PR에 댓글로 등록하는 서버리스 에이전트입니다.

## 아키텍처

```
GitHub PR (열림/업데이트, Webhook)
        ↓
API Gateway  POST /review  (API Key + Usage Plan Rate Limiting)
        ↓
Orchestrator Lambda (codebuddy-orchestrator)
  - Webhook 서명(X-Hub-Signature-256) 검증
  - PR URL 파싱 → sessionId 생성
  - Bedrock Agent invoke_agent() 호출
        ↓
Bedrock Agent (Action Group: 5개 Tool, OpenAPI 스키마 docs/api-spec.yaml)
  ┌───────────────┬──────────────────────┬─────────────────────┐
  │ get_github_pr │ analyze_complexity   │ generate_unit_test   │
  ├───────────────┼──────────────────────┼─────────────────────┤
  │ suggest_refactor │ post_pr_comment   │                      │
  └───────────────┴──────────────────────┴─────────────────────┘
        ↓
GitHub PR에 분석 결과 댓글 등록
```

Agent는 한 번의 PR 리뷰 요청에 대해 위 5개 Tool을 순서대로(get_github_pr → analyze_complexity → generate_unit_test/suggest_refactor → post_pr_comment) 호출하도록 Instructions에 구성되어 있습니다. Slack 알림 Tool은 의도적으로 제외했습니다(아래 "범위" 참고).

## 주요 기능

| 기능 | 구현 방식 | 코드 |
|---|---|---|
| GitHub PR 코드/diff 조회 | GitHub REST API, 이미지·PDF 등 바이너리 파일 제외 | [lambda/tools/github_pr.py](lambda/tools/github_pr.py) |
| 순환 복잡도 분석 | Python `ast` 기반 분기(if/for/while/except/bool op) 카운팅 | [lambda/tools/complexity.py](lambda/tools/complexity.py) |
| 코드 스타일 검사 | 줄 길이(79자), 탭 사용, camelCase 함수명 등 PEP8 규칙 기반 정규식 검사 | [lambda/tools/complexity.py](lambda/tools/complexity.py) |
| 보안 취약점 탐지 | SQL Injection, 하드코딩된 비밀정보, `pickle`/`eval`/`exec`, SSL 검증 비활성화 등 정규식 패턴 매칭 | [lambda/tools/complexity.py](lambda/tools/complexity.py) |
| pytest 단위 테스트 자동 생성 | `ast`로 함수 추출 후 정상/예외/Mock 케이스 템플릿 생성 | [lambda/tools/testgen.py](lambda/tools/testgen.py) |
| 리팩토링 제안 | 긴 함수, 중복 코드, 매직 넘버, 타입 힌트 누락 탐지 | [lambda/tools/refactor.py](lambda/tools/refactor.py) |
| GitHub PR 댓글 등록 | 분석 결과를 Markdown으로 포맷해 PR(Issue) 댓글로 등록 | [lambda/tools/post_pr_comment.py](lambda/tools/post_pr_comment.py) |

> 참고: 코드 스타일/보안/복잡도 분석은 Bedrock Knowledge Base(RAG)가 아니라 Lambda 내부의 로컬 AST/정규식 규칙으로 구현되어 있습니다. LLM 호출은 Bedrock Agent의 추론(Orchestration) 단계에만 사용됩니다.

## 저장소 구조

```
codebuddy-agent/
├── README.md
├── cloudformation/
│   └── template.yaml        # IAM Role, Orchestrator/Tool Lambda, API Gateway 등 전체 인프라
├── lambda/
│   ├── orchestrator.py      # Webhook 수신 → Bedrock Agent 호출
│   └── tools/
│       ├── github_pr.py
│       ├── complexity.py
│       ├── testgen.py
│       ├── refactor.py
│       └── post_pr_comment.py
├── docs/
│   ├── api-spec.yaml         # Bedrock Agent Action Group OpenAPI 스키마
│   ├── cost-analysis.md      # 월간 예상 비용 분석
│   └── test-report.md        # 테스트 범위 및 결과
└── tests/
    └── test_e2e.py           # 단위 테스트 + API E2E 테스트
```

## 사전 준비물

1. **AWS 계정** (Lambda, API Gateway, CloudFormation, Bedrock 사용 가능 리전 — 본 프로젝트는 `ap-northeast-2` 기준)
2. **Bedrock Agent + Alias** — AWS 콘솔(Amazon Bedrock → Agents)에서 미리 생성. Agent ID / Alias ID가 필요합니다.
3. **GitHub Personal Access Token** — PR 조회/댓글 작성 권한
4. **S3 버킷** — Lambda 코드(zip)와 Lambda Layer(zip)를 업로드할 버킷

값을 구하는 구체적인 방법은 [환경 변수/파라미터 값 가져오는 방법](#환경-변수파라미터-값-가져오는-방법) 섹션을 참고하세요.

## 배포 방법

### 1. Lambda 코드 패키징

```bash
# orchestrator.py + lambda/tools/*.py 를 모두 zip 루트에 압축
# (Orchestrator Lambda와 5개 Tool Lambda가 같은 zip을 공유하고, Handler로만 구분됨)
zip -j codebuddy-tools.zip lambda/orchestrator.py lambda/tools/*.py

# requests 패키지를 python/ 폴더 아래 담아서 Layer zip 생성
pip install requests -t layer/python
cd layer && zip -r ../requests-layer.zip python && cd ..
```

### 2. S3 업로드

```bash
aws s3 cp codebuddy-tools.zip s3://<YOUR_BUCKET>/codebuddy-tools.zip
aws s3 cp requests-layer.zip s3://<YOUR_BUCKET>/requests-layer.zip
```

### 3. CloudFormation 1-클릭 배포

```bash
aws cloudformation deploy \
  --template-file cloudformation/template.yaml \
  --stack-name CodeBuddyStack \
  --parameter-overrides \
      AgentIdParam=<BEDROCK_AGENT_ID> \
      AliasIdParam=<BEDROCK_AGENT_ALIAS_ID> \
      GitHubTokenParam=<GITHUB_PAT> \
      GitHubSecretParam=<WEBHOOK_SECRET> \
      ToolsCodeS3Bucket=<YOUR_BUCKET> \
  --capabilities CAPABILITY_NAMED_IAM
```

### 4. 배포 결과(API URL) 확인

```bash
aws cloudformation describe-stacks \
  --stack-name CodeBuddyStack \
  --query "Stacks[0].Outputs"
```

`ApiGatewayUrl` 출력값이 GitHub Webhook의 Payload URL이자, 직접 호출/테스트용 엔드포인트입니다.

### 5. Bedrock Agent Action Group 연결

`docs/api-spec.yaml`을 Action Group의 OpenAPI 스키마로 등록하고, 각 operationId(`get_github_pr`, `analyze_complexity`, `generate_unit_test`, `suggest_refactor`, `post_pr_comment`)를 3번에서 생성된 해당 Tool Lambda ARN에 연결한 뒤 `prepare_agent()`로 반영합니다.

### 6. GitHub Webhook 등록

저장소 Settings → Webhooks → Add webhook

- Payload URL: 위에서 확인한 `ApiGatewayUrl`
- Content type: `application/json`
- Secret: `GitHubSecretParam`과 동일한 값
- 이벤트: Pull requests

## 사용 방법

Webhook이 연결되면 PR을 열거나 업데이트(synchronize)할 때마다 자동으로 리뷰가 실행됩니다.

직접 호출해서 테스트할 수도 있습니다:

```bash
curl -X POST <ApiGatewayUrl> \
  -H "Content-Type: application/json" \
  -d '{"pr_url": "https://github.com/<owner>/<repo>/pull/<number>"}'
```

## 환경 변수 / 파라미터 값 가져오는 방법

| 이름 | 어디서 가져오나 |
|---|---|
| `AgentIdParam` (`AGENT_ID`) | Bedrock 콘솔 → Agents → 생성한 Agent 선택 → 개요 화면의 Agent ID. 또는 `aws bedrock-agent list-agents` |
| `AliasIdParam` (`ALIAS_ID`) | 같은 Agent 화면의 Aliases 탭. Alias를 만들지 않았다면 `aws bedrock-agent create-agent-alias`로 생성 후 반환되는 ID 사용 |
| `GitHubTokenParam` (`GITHUB_TOKEN`) | GitHub → Settings → Developer settings → Personal access tokens에서 직접 발급 (classic: `repo` scope / fine-grained: Contents Read + Pull requests Read & Write) |
| `GitHubSecretParam` (`GITHUB_SECRET`) | 본인이 직접 정하는 임의의 문자열(랜덤 시크릿 권장). GitHub Webhook 설정의 Secret 필드에 **동일한 값**을 입력해야 서명 검증이 통과함 |
| `ToolsCodeS3Bucket` / `ToolsCodeS3Key` | 본인이 만든 S3 버킷 이름과, 그 버킷에 업로드한 zip 파일의 키(파일명). AWS가 발급하는 값이 아니라 직접 지정 |
| `CODEBUDDY_API_URL` (테스트용) | AWS가 생성해주는 값. CloudFormation 배포 완료 후 `aws cloudformation describe-stacks --stack-name CodeBuddyStack --query "Stacks[0].Outputs"`로 조회되는 `ApiGatewayUrl` 출력값 |

## 테스트

```bash
# 단위 테스트만 (AWS 배포 없이 로컬에서 즉시 실행 가능)
pytest tests/test_e2e.py -v -k "not TestCodeBuddyAPI"

# 배포된 API까지 포함한 전체 E2E 테스트
export CODEBUDDY_API_URL="https://<api-id>.execute-api.ap-northeast-2.amazonaws.com/prod/review"
pytest tests/test_e2e.py -v
```

테스트 범위와 결과는 [docs/test-report.md](docs/test-report.md), 예상 운영 비용은 [docs/cost-analysis.md](docs/cost-analysis.md)를 참고하세요.

## 범위 / 알려진 제한

- Slack 알림은 구현하지 않았습니다(선택 사항으로 판단하여 제외).
- 코드 스타일/보안/복잡도 분석은 Bedrock Knowledge Base(RAG)가 아닌 로컬 규칙 기반(AST/정규식)입니다.
- 1000줄을 초과하는 대용량 코드에 대한 함수 단위 청크 분할 분석은 아직 구현되어 있지 않습니다.
