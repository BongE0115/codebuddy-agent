import os
import json
import requests

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')

HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}


def format_comment_body(analysis_result: str) -> str:
    """analyze_complexity/generate_unit_test/suggest_refactor 결과(JSON 문자열)를 마크다운으로 포맷"""
    try:
        data = json.loads(analysis_result) if analysis_result else {}
    except (json.JSONDecodeError, TypeError):
        data = {}

    sections = []

    complexity = data.get('complexity', {})
    if complexity and 'error' not in complexity:
        lines = [f"- `{name}`: 복잡도 {info.get('complexity', '?')} ({info.get('risk', '?')})"
                 for name, info in complexity.items()]
        sections.append('### 복잡도\n' + '\n'.join(lines))

    style_issues = data.get('style_issues', [])
    if style_issues:
        sections.append('### 스타일 위반\n' + '\n'.join(f"- {issue}" for issue in style_issues))

    security_issues = data.get('security_issues', [])
    if security_issues:
        lines = [f"- **{issue.get('type', '')}** (줄 {issue.get('line', '?')}): {issue.get('suggestion', '')}"
                 for issue in security_issues]
        sections.append('### 🔒 보안 취약점\n' + '\n'.join(lines))

    refactoring_suggestions = data.get('refactoring_suggestions', [])
    if refactoring_suggestions:
        lines = [f"- **[{item.get('category', '')}]** {item.get('detail', '')} → {item.get('suggestion', '')}"
                 for item in refactoring_suggestions]
        sections.append('### 리팩토링 제안\n' + '\n'.join(lines))

    test_code = data.get('test_code', '')
    if test_code:
        sections.append('### 제안된 테스트 코드\n```python\n' + test_code + '\n```')

    if not sections:
        sections.append('변경 사항에서 특별한 이슈가 발견되지 않았습니다. ✅')

    return '## 🤖 CodeBuddy 자동 리뷰 결과\n\n' + '\n\n'.join(sections)


def post_comment(owner: str, repo: str, pr_number: str, body: str) -> dict:
    """GitHub PR(=issue)에 댓글 등록"""
    url = f'https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments'
    response = requests.post(url, headers=HEADERS, json={'body': body}, timeout=10)
    response.raise_for_status()
    return response.json()


def handler(event, context):
    """Lambda 핸들러 - Bedrock Agent Action Group에서 호출"""
    print(f"post_pr_comment 호출: {json.dumps(event)}")

    parameters = {p['name']: p['value'] for p in event.get('parameters', [])}
    owner = parameters.get('owner', '')
    repo = parameters.get('repo', '')
    pr_number = parameters.get('pr_number', '')
    analysis_result = parameters.get('analysis_result', '')

    try:
        comment_body = format_comment_body(analysis_result)
        comment = post_comment(owner, repo, pr_number, comment_body)
        result = {
            'success': True,
            'comment_url': comment.get('html_url', '')
        }
    except Exception as e:
        error_msg = f"PR 댓글 등록 실패: {str(e)}"
        print(error_msg)
        result = {'success': False, 'error': error_msg}

    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': event.get('actionGroup'),
            'function': event.get('function'),
            'functionResponse': {
                'responseBody': {
                    'TEXT': {'body': json.dumps(result, ensure_ascii=False)}
                }
            }
        }
    }
