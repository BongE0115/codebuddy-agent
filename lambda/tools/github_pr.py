import os
import json
import requests

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')

HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}


def parse_pr_url(pr_url: str) -> tuple:
    """PR URL에서 owner, repo, pr_number 추출
    예: https://github.com/owner/repo/pull/123
    """
    parts = pr_url.rstrip('/').split('/')
    pr_number = parts[-1]
    repo = parts[-3]
    owner = parts[-4]
    return owner, repo, pr_number


def get_pr_files(owner: str, repo: str, pr_number: str) -> list:
    """PR에서 변경된 파일 목록 가져오기"""
    url = f'https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files'
    response = requests.get(url, headers=HEADERS, timeout=10)
    response.raise_for_status()
    return response.json()


def get_pr_info(owner: str, repo: str, pr_number: str) -> dict:
    """PR 기본 정보 가져오기"""
    url = f'https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}'
    response = requests.get(url, headers=HEADERS, timeout=10)
    response.raise_for_status()
    return response.json()


def handler(event, context):
    """Lambda 핸들러 - Bedrock Agent Action Group에서 호출"""
    print(f"get_github_pr 호출: {json.dumps(event)}")

    # Bedrock Agent가 전달하는 파라미터 추출
    parameters = {p['name']: p['value'] for p in event.get('parameters', [])}
    pr_url = parameters.get('pr_url', '')

    try:
        owner, repo, pr_number = parse_pr_url(pr_url)

        # PR 정보 가져오기
        pr_info = get_pr_info(owner, repo, pr_number)
        files = get_pr_files(owner, repo, pr_number)

        # 코드 파일만 필터링 (이미지, PDF 제외)
        code_extensions = {'.py', '.js', '.ts', '.java', '.go', '.rb', '.php', '.cs', '.cpp', '.c', '.h'}
        code_files = []
        for f in files:
            ext = '.' + f['filename'].split('.')[-1] if '.' in f['filename'] else ''
            if ext in code_extensions or not ext:
                code_files.append({
                    'filename': f['filename'],
                    'status': f['status'],  # added, modified, removed
                    'additions': f['additions'],
                    'deletions': f['deletions'],
                    'patch': f.get('patch', '')[:3000]  # 너무 긴 diff는 잘라냄
                })

        result = {
            'pr_title': pr_info.get('title', ''),
            'pr_author': pr_info.get('user', {}).get('login', ''),
            'base_branch': pr_info.get('base', {}).get('ref', ''),
            'head_branch': pr_info.get('head', {}).get('ref', ''),
            'total_files': len(files),
            'code_files': code_files[:10],  # 최대 10개 파일
            'owner': owner,
            'repo': repo,
            'pr_number': pr_number
        }

        # 변경 파일 없는 경우
        if not code_files:
            result['message'] = '변경된 코드 파일이 없습니다.'

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

    except Exception as e:
        error_msg = f"GitHub PR 가져오기 실패: {str(e)}"
        print(error_msg)
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event.get('actionGroup'),
                'function': event.get('function'),
                'functionResponse': {
                    'responseBody': {
                        'TEXT': {'body': json.dumps({'error': error_msg}, ensure_ascii=False)}
                    }
                }
            }
        }