import json
import ast
import re


def calculate_cyclomatic_complexity(code: str) -> dict:
    """
    간단한 순환 복잡도 계산
    분기점(if, for, while, except, and, or) 개수 + 1
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {'error': '파이썬 문법 오류로 분석 불가'}

    results = {}

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            complexity = 1  # 기본값
            for child in ast.walk(node):
                if isinstance(child, (
                    ast.If, ast.For, ast.While, ast.ExceptHandler,
                    ast.With, ast.Assert, ast.comprehension
                )):
                    complexity += 1
                elif isinstance(child, ast.BoolOp):
                    complexity += len(child.values) - 1

            results[node.name] = {
                'complexity': complexity,
                'line': node.lineno,
                'risk': get_risk_level(complexity)
            }

    return results


def get_risk_level(complexity: int) -> str:
    """복잡도에 따른 위험 수준"""
    if complexity <= 5:
        return '낮음 (양호)'
    elif complexity <= 10:
        return '중간 (주의)'
    elif complexity <= 15:
        return '높음 (리팩토링 권장)'
    else:
        return '매우 높음 (즉시 리팩토링 필요)'


def check_code_style(code: str) -> list:
    """기본적인 코드 스타일 체크"""
    issues = []
    lines = code.split('\n')

    for i, line in enumerate(lines, 1):
        # 너무 긴 줄 (PEP8: 79자)
        if len(line) > 79:
            issues.append(f"줄 {i}: 줄 길이가 {len(line)}자로 79자를 초과합니다 (PEP8)")

        # 탭 사용
        if '\t' in line:
            issues.append(f"줄 {i}: 탭 대신 스페이스를 사용하세요 (PEP8)")

        # 함수명 camelCase 사용 (snake_case 권장)
        camel_func = re.search(r'def ([a-z]+[A-Z][a-zA-Z]*)\(', line)
        if camel_func:
            issues.append(f"줄 {i}: 함수명 '{camel_func.group(1)}'은 snake_case로 변경하세요 (PEP8)")

    return issues


def check_security(code: str) -> list:
    """보안 취약점 체크"""
    vulnerabilities = []
    lines = code.split('\n')

    patterns = [
        (r'f["\'].*SELECT.*\{', 'SQL Injection', '파라미터화된 쿼리 사용 권장: cursor.execute("SELECT ... WHERE id = %s", (id,))'),
        (r'(password|passwd|secret|api_key|token)\s*=\s*["\'][^"\']+["\']', '하드코딩된 민감 정보', '환경 변수 또는 AWS Secrets Manager 사용 권장'),
        (r'pickle\.loads?\(', '안전하지 않은 역직렬화', 'json.loads() 사용 권장'),
        (r'eval\(', 'eval() 사용', '안전한 대안 사용 권장'),
        (r'exec\(', 'exec() 사용', '코드 실행 함수 사용 주의'),
        (r'console\.log\(.*secret|print\(.*password', '민감 정보 로깅', '로그에서 민감 정보 제거 필요'),
        (r'verify\s*=\s*False', 'SSL 검증 비활성화', 'SSL 인증서 검증을 활성화하세요'),
    ]

    for i, line in enumerate(lines, 1):
        for pattern, vuln_type, suggestion in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                vulnerabilities.append({
                    'line': i,
                    'type': vuln_type,
                    'code': line.strip(),
                    'suggestion': suggestion
                })

    return vulnerabilities


def handler(event, context):
    """Lambda 핸들러"""
    print(f"analyze_complexity 호출: {json.dumps(event)}")

    parameters = {p['name']: p['value'] for p in event.get('parameters', [])}
    code = parameters.get('code', '')
    filename = parameters.get('filename', 'unknown.py')

    try:
        result = {
            'filename': filename,
            'complexity': {},
            'style_issues': [],
            'security_issues': []
        }

        # Python 파일만 복잡도 분석
        if filename.endswith('.py') and code:
            result['complexity'] = calculate_cyclomatic_complexity(code)
            result['style_issues'] = check_code_style(code)
            result['security_issues'] = check_security(code)
        elif code:
            # 다른 언어는 보안 체크만
            result['security_issues'] = check_security(code)
            result['message'] = f'{filename}은 Python이 아니어서 복잡도 분석을 생략합니다.'

        # 요약
        high_complexity = [
            f for f, d in result['complexity'].items()
            if isinstance(d, dict) and d.get('complexity', 0) > 10
        ]
        result['summary'] = {
            'total_functions': len(result['complexity']),
            'high_complexity_functions': high_complexity,
            'style_issue_count': len(result['style_issues']),
            'security_issue_count': len(result['security_issues'])
        }

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
        error_msg = f"복잡도 분석 실패: {str(e)}"
        print(error_msg)
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event.get('actionGroup'),
                'function': event.get('function'),
                'functionResponse': {
                    'responseBody': {
                        'TEXT': {'body': json.dumps({'error': error_msg})}
                    }
                }
            }
        }