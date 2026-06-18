# CodeBuddy 테스트 리포트

## 테스트 범위

`tests/test_e2e.py`는 두 종류로 구성되어 있습니다.

1. **로컬 단위 테스트** — AWS 배포 없이 `lambda/tools/*.py`의 순수 함수를 직접 import해서 검증. CI나 로컬 환경에서 즉시 실행 가능.
2. **API E2E 테스트** (`TestCodeBuddyAPI`) — 실제 배포된 API Gateway 엔드포인트(`CODEBUDDY_API_URL`)에 HTTP 요청을 보내 전체 파이프라인(Orchestrator → Bedrock Agent → Tool Lambda들)을 검증.

## 로컬 단위 테스트 결과

실행 명령:

```bash
pytest tests/test_e2e.py -v -k "not TestCodeBuddyAPI"
```

실행 결과 (2026-06-18 기준, Python 3.13.9 / pytest 8.4.2):

```
tests/test_e2e.py::TestComplexityTool::test_simple_function_complexity PASSED
tests/test_e2e.py::TestComplexityTool::test_complex_function_detection PASSED
tests/test_e2e.py::TestComplexityTool::test_sql_injection_detection PASSED
tests/test_e2e.py::TestComplexityTool::test_hardcoded_secret_detection PASSED
tests/test_e2e.py::TestTestGenTool::test_generates_test_for_function PASSED
tests/test_e2e.py::TestEdgeCases::test_empty_code PASSED
tests/test_e2e.py::TestEdgeCases::test_syntax_error_code PASSED
tests/test_e2e.py::TestEdgeCases::test_non_python_file PASSED

8 passed, 4 deselected in 0.31s
```

| 테스트 | 검증 대상 | 결과 |
|---|---|---|
| test_simple_function_complexity | 단순 함수의 순환 복잡도가 1로 계산되는지 | PASS |
| test_complex_function_detection | 분기/루프가 많은 함수의 복잡도가 5 초과로 탐지되는지 | PASS |
| test_sql_injection_detection | f-string SQL 조합 패턴이 SQL Injection으로 탐지되는지 | PASS |
| test_hardcoded_secret_detection | `API_KEY = "..."` 형태의 하드코딩된 비밀정보 탐지 | PASS |
| test_generates_test_for_function | 함수 추출 및 pytest 테스트 코드 생성(`def test_*`, `import pytest`) | PASS |
| test_empty_code | 빈 코드 입력 시 빈 결과 반환(예외 없음) | PASS |
| test_syntax_error_code | 문법 오류 코드에 대해 에러 처리 또는 빈 결과 반환 | PASS |
| test_non_python_file | `.py`가 아닌 파일은 분석을 생략하고 안내 메시지 반환 | PASS |

## API E2E 테스트 (배포 후 실행 필요)

`TestCodeBuddyAPI`의 4개 테스트는 CloudFormation 스택이 배포되어 있고 `CODEBUDDY_API_URL` 환경 변수가 실제 API Gateway URL을 가리킬 때만 의미 있는 결과가 나옵니다. 본 리포트 작성 시점에는 라이브 엔드포인트에 대해 실행하지 않았으므로(인프라 미배포), 아래는 코드 기준 테스트 계획입니다.

| 테스트 | 시나리오 | 기대 결과 |
|---|---|---|
| test_valid_pr_review | 유효한 PR URL로 리뷰 요청 | 200, 응답에 `result` 또는 `message` 포함 |
| test_invalid_pr_url | `pr_url: "invalid-url"` | 400 또는 500 |
| test_missing_pr_url | body에 `pr_url` 누락 | 400 |
| test_nonexistent_pr | 존재하지 않는 repo/PR | 200(에러 메시지 포함) 또는 500 |

배포 후 실행:

```bash
export CODEBUDDY_API_URL="https://<api-id>.execute-api.ap-northeast-2.amazonaws.com/prod/review"
pytest tests/test_e2e.py -v
```

## 엣지 케이스 커버리지

| 케이스 | 현재 커버 여부 | 비고 |
|---|---|---|
| 잘못된 PR URL | 커버 (`test_invalid_pr_url`) | |
| `pr_url` 누락 | 커버 (`test_missing_pr_url`) | |
| 존재하지 않는 PR | 커버 (`test_nonexistent_pr`) | |
| 빈 코드/문법 오류 코드 | 커버 (`TestEdgeCases`) | |
| Python이 아닌 파일 | 커버 (`test_non_python_file`) | |
| 변경 파일 없는 빈 PR | 부분 커버 | `github_pr.py`에 "변경된 코드 파일이 없습니다" 메시지 로직은 있으나 전용 테스트 없음 |
| 1000줄 초과 대용량 PR (청크 분할) | **미커버** | 현재 `complexity.py`/`refactor.py`는 청크 분할 로직 자체가 없음(코드 전체를 한 번에 분석) |
| 바이너리 파일(이미지/PDF) 무시 | 부분 커버 | `github_pr.py`의 확장자 필터링 로직은 있으나 전용 단위 테스트 없음 |
| 동시 PR 처리 | **미커버** | Lambda는 기본적으로 동시 실행을 지원하지만 별도 동시성 테스트는 없음 |
| `suggest_refactor` 단위 테스트 | **미커버** | `refactor.py`에 대한 전용 테스트 없음(현재는 `complexity.py`, `testgen.py`만 단위 테스트 존재) |
| `send_slack_message` 단위 테스트 | **미커버** | `send_slack.py`에 대한 전용 테스트 없음. Slack Webhook 실패(잘못된 URL 등) 시 에러 처리 경로 미검증 |
| 평균 응답 시간 / 성공률 측정 | **미커버** | CloudWatch 커스텀 메트릭(`put_metric_data`) 미구현 |

## 다음에 추가하면 좋은 테스트

- `refactor.py`의 `find_long_functions`, `find_duplicate_code`, `find_magic_numbers`, `suggest_type_hints`에 대한 단위 테스트
- `github_pr.py`의 바이너리 파일 필터링, 빈 PR 처리에 대한 단위 테스트
- `send_slack.py`의 Webhook 호출 성공/실패 케이스에 대한 Mock 기반 단위 테스트
- 배포 후 CloudWatch Logs Insights 또는 `put_metric_data`로 평균 리뷰 시간 측정
