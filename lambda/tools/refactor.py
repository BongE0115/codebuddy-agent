import json
import ast
import re


def find_long_functions(code: str, max_lines: int = 20) -> list:
    """너무 긴 함수 탐지"""
    issues = []
    try:
        tree = ast.parse(code)
        lines = code.split('\n')
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end_line = getattr(node, 'end_lineno', node.lineno + 10)
                func_lines = end_line - node.lineno + 1
                if func_lines > max_lines:
                    issues.append({
                        'function': node.name,
                        'lines': func_lines,
                        'suggestion': f'함수를 {func_lines // max_lines + 1}개의 작은 함수로 분리하세요.'
                    })
    except SyntaxError:
        pass
    return issues


def find_duplicate_code(code: str) -> list:
    """중복 코드 패턴 탐지 (간단한 버전)"""
    issues = []
    lines = [l.strip() for l in code.split('\n') if l.strip() and not l.strip().startswith('#')]

    # 3줄 이상 연속 중복 찾기
    seen = {}
    for i in range(len(lines) - 2):
        chunk = '\n'.join(lines[i:i+3])
        if len(chunk) > 30:  # 너무 짧은 코드는 제외
            if chunk in seen:
                issues.append({
                    'type': '중복 코드',
                    'location': f'줄 {i+1} 근처',
                    'suggestion': '공통 함수로 추출하세요.'
                })
            else:
                seen[chunk] = i

    return issues[:5]  # 최대 5개


def find_magic_numbers(code: str) -> list:
    """매직 넘버 탐지"""
    issues = []
    lines = code.split('\n')
    pattern = re.compile(r'(?<!["\'\w])\b([0-9]{2,})\b(?!["\'\w])')

    for i, line in enumerate(lines, 1):
        if line.strip().startswith('#'):
            continue
        matches = pattern.findall(line)
        for num in matches:
            if num not in ('10', '100', '200', '404', '500'):  # 일반적인 숫자 제외
                issues.append({
                    'line': i,
                    'value': num,
                    'suggestion': f'숫자 {num}을 의미있는 상수로 선언하세요. 예: MAX_RETRY = {num}'
                })

    return issues[:5]


def suggest_type_hints(code: str) -> list:
    """타입 힌트 추가 제안"""
    suggestions = []
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args_without_hints = [
                    arg.arg for arg in node.args.args
                    if arg.annotation is None and arg.arg != 'self'
                ]
                if args_without_hints or node.returns is None:
                    suggestions.append({
                        'function': node.name,
                        'args_without_hints': args_without_hints,
                        'has_return_hint': node.returns is not None,
                        'suggestion': f'타입 힌트를 추가하세요. 예: def {node.name}({", ".join(f"{a}: Any" for a in args_without_hints)}) -> None:'
                    })
    except SyntaxError:
        pass
    return suggestions[:5]


def handler(event, context):
    """Lambda 핸들러"""
    print(f"suggest_refactor 호출: {json.dumps(event)}")

    parameters = {p['name']: p['value'] for p in event.get('parameters', [])}
    code = parameters.get('code', '')
    filename = parameters.get('filename', 'unknown.py')

    try:
        result = {
            'filename': filename,
            'refactoring_suggestions': []
        }

        if filename.endswith('.py') and code:
            long_functions = find_long_functions(code)
            duplicate_code = find_duplicate_code(code)
            magic_numbers = find_magic_numbers(code)
            type_hints = suggest_type_hints(code)

            suggestions = []

            for item in long_functions:
                suggestions.append({
                    'category': '함수 분리',
                    'severity': 'high',
                    'detail': f"함수 '{item['function']}'이 {item['lines']}줄로 너무 깁니다.",
                    'suggestion': item['suggestion']
                })

            for item in duplicate_code:
                suggestions.append({
                    'category': '중복 제거',
                    'severity': 'medium',
                    'detail': f"{item['location']}에 중복 코드가 있습니다.",
                    'suggestion': item['suggestion']
                })

            for item in magic_numbers:
                suggestions.append({
                    'category': '매직 넘버',
                    'severity': 'low',
                    'detail': f"줄 {item['line']}: 숫자 {item['value']}가 하드코딩되어 있습니다.",
                    'suggestion': item['suggestion']
                })

            for item in type_hints:
                suggestions.append({
                    'category': '타입 힌트',
                    'severity': 'low',
                    'detail': f"함수 '{item['function']}'에 타입 힌트가 없습니다.",
                    'suggestion': item['suggestion']
                })

            result['refactoring_suggestions'] = suggestions
            result['summary'] = f"총 {len(suggestions)}개의 리팩토링 제안사항이 있습니다."

            if not suggestions:
                result['summary'] = "리팩토링이 필요한 부분이 없습니다. 코드 품질이 좋습니다! ✅"
        else:
            result['message'] = f'{filename}은 Python 파일이 아니어서 상세 분석을 생략합니다.'

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
        error_msg = f"리팩토링 분석 실패: {str(e)}"
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