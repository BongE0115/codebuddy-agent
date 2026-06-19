import json
import os
import hmac
import hashlib
import boto3

# 환경 변수
AGENT_ID = os.environ.get('AGENT_ID', '')
ALIAS_ID = os.environ.get('ALIAS_ID', '')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_SECRET = os.environ.get('GITHUB_SECRET', '')

bedrock_agent = boto3.client('bedrock-agent-runtime', region_name='ap-northeast-2')


def verify_github_signature(payload_body: bytes, signature: str) -> bool:
    """GitHub Webhook 서명 검증"""
    if not GITHUB_SECRET:
        return True  # 개발 환경에서는 검증 생략
    expected = 'sha256=' + hmac.new(
        GITHUB_SECRET.encode(), payload_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def invoke_bedrock_agent(pr_url: str, session_id: str) -> str:
    """Bedrock Agent 호출"""
    prompt = f"""
다음 GitHub PR을 분석해주세요: {pr_url}

아래 항목을 순서대로 수행해주세요:
1. get_github_pr 툴로 PR 코드 가져오기
2. analyze_complexity 툴로 복잡도 분석
3. 보안 취약점 확인 (SQL Injection, 하드코딩된 비밀번호 등)
4. generate_unit_test 툴로 테스트 코드 제안
5. suggest_refactor 툴로 리팩토링 제안
6. post_pr_comment 툴로 GitHub PR에 리뷰 댓글 등록
7. send_slack_message 툴로 리뷰가 완료되었다는 사실과 PR 링크를 팀 채널에 알리기
"""

    response = bedrock_agent.invoke_agent(
        agentId=AGENT_ID,
        agentAliasId=ALIAS_ID,
        sessionId=session_id,
        inputText=prompt
    )

    result = ''
    for event in response['completion']:
        if 'chunk' in event:
            result += event['chunk']['bytes'].decode('utf-8')

    return result


def handler(event, context):
    """Lambda 핸들러"""
    print(f"Event: {json.dumps(event)}")

    # CORS 헤더
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
    }

    try:
        # OPTIONS 요청 처리 (CORS preflight)
        if event.get('httpMethod') == 'OPTIONS':
            return {'statusCode': 200, 'headers': headers, 'body': ''}

        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)

        # GitHub Webhook 서명 검증
        signature = event.get('headers', {}).get('X-Hub-Signature-256', '')
        raw_body = event.get('body', '').encode() if isinstance(event.get('body'), str) else b''
        if signature and not verify_github_signature(raw_body, signature):
            return {
                'statusCode': 401,
                'headers': headers,
                'body': json.dumps({'error': 'Invalid signature'})
            }

        # PR URL 추출 (직접 호출 또는 Webhook)
        pr_url = body.get('pr_url')
        if not pr_url:
            # GitHub Webhook 형식
            pull_request = body.get('pull_request', {})
            pr_url = pull_request.get('html_url')
            action = body.get('action', '')

            # PR이 열렸을 때만 처리
            if action not in ['opened', 'synchronize']:
                return {
                    'statusCode': 200,
                    'headers': headers,
                    'body': json.dumps({'message': f'Action {action} ignored'})
                }

        if not pr_url:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'pr_url이 필요합니다'})
            }

        # PR 번호로 세션 ID 생성
        pr_number = pr_url.split('/')[-1]
        session_id = f"webhook-{pr_number}"

        print(f"PR 분석 시작: {pr_url}")

        # Bedrock Agent 호출
        result = invoke_bedrock_agent(pr_url, session_id)

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'message': 'PR 리뷰 완료',
                'pr_url': pr_url,
                'result': result
            }, ensure_ascii=False)
        }

    except Exception as e:
        print(f"오류 발생: {e}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)}, ensure_ascii=False)
        }