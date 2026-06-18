# CodeBuddy 월간 예상 비용 분석

리전: `ap-northeast-2` (서울) 기준. 모든 수치는 추정치이며, 실제 비용은 PR 크기(토큰 수), 호출 빈도, 로그 보존 기간에 따라 달라집니다.

## 가정

- 하루 100건의 PR 리뷰 요청 (영업일 22일/월 기준)
- PR 1건당 Bedrock Agent가 5개 Tool(get_github_pr → analyze_complexity → generate_unit_test → suggest_refactor → post_pr_comment)을 순차 호출
- send_slack_message는 사용자가 명시적으로 요청할 때만 호출되므로 정기 비용 산정에서는 제외(호출당 Lambda 비용은 다른 Tool과 동일하게 미미함)
- Tool Lambda는 모두 로컬 AST/정규식 기반 정적 분석이라 Bedrock을 추가로 호출하지 않음(Bedrock 호출은 Agent의 추론 단계 1회에 집중)

## 비용 구성 요소

| 서비스 | 단가 | 산정 기준 | 일 100건 | 월 (22일) |
|---|---|---|---|---|
| Orchestrator Lambda (1024MB) | $0.0000166667/GB-초 | 평균 20초 실행(Agent 응답 대기 포함) | ~$0.03 | ~$0.73 |
| Tool Lambda 6종 (256MB) | $0.0000166667/GB-초 | PR당 5회 호출(+ 요청 시 Slack 1회), 평균 1~2초 | ~$0.01 | ~$0.20 |
| API Gateway (REST, Lambda 프록시) | $1.00 / 백만 호출 | 100건/일 | <$0.01 | <$0.01 |
| Bedrock Agent (Claude Sonnet 4.6) | 입력 $0.003/1K, 출력 $0.015/1K 토큰 | PR당 추론+5단계 Tool 호출 | ~$0.20 | ~$4.40 |
| CloudWatch Logs | $0.50/GB | Lambda 로그 적재 | ~$0.05 | ~$1.10 |
| **합계** | | | **~$0.29/일** | **~$6.4/월** |

> Bedrock Agent 항목의 단가/산정 기준은 동일한 사용 패턴(에이전트 1회 호출 + 순차 Tool 호출)을 가정한 강의 자료의 추정치를 그대로 적용했습니다. 실제 PR의 diff 크기가 클수록 입력 토큰이 늘어나 비용이 증가합니다.

## 강의 예시(풀 RAG 아키텍처)와의 차이

강의 10장에서 제시한 최종 아키텍처는 Bedrock Knowledge Base + OpenSearch Serverless를 사용해 코드 스타일/보안 규정을 RAG로 검색하며, 이 경우 다음 비용이 추가됩니다.

| 서비스 | 단가 | 월 비용 |
|---|---|---|
| OpenSearch Serverless (Knowledge Base 벡터 저장) | $0.24/OCU-시간 | ~$11.00 |
| Bedrock 임베딩 | $0.0001/1K 토큰 | ~$0.22 |

본 프로젝트는 스타일/보안/복잡도 분석을 Lambda 내부의 로컬 규칙(AST/정규식)으로 구현해 Knowledge Base를 사용하지 않으므로, 위 ~$11.2/월이 절감됩니다. 강의 예시 총액(~$27.79/월) 대비 본 프로젝트의 예상 비용(~$6.4/월)이 낮은 주된 이유입니다.

## 비용 절감 팁

- **CloudWatch 로그 보존 기간 설정**: 기본값(무기한)이 아니라 7~14일로 제한하면 Logs 비용을 더 줄일 수 있습니다.
- **동일 PR 재분석 캐싱**: 같은 커밋 SHA에 대한 중복 Webhook 이벤트(synchronize 재발생 등)를 캐싱해 Agent 재호출을 방지합니다.
- **Lambda 메모리 최적화**: Tool Lambda는 단순 정적 분석이라 256MB로 충분합니다. 과도하게 높은 메모리는 비용만 늘립니다.
- **무료 사용량(Free Tier)**: 신규 계정 기준 Lambda는 매월 100만 건 요청 + 400,000 GB-초 컴퓨팅, API Gateway는 12개월간 월 100만 건 호출이 무료이므로, 초기 트래픽에서는 위 추정치보다 실제 청구액이 더 낮을 수 있습니다.
