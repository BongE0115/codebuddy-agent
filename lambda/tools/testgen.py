import json
import ast
import re


def extract_functions(code: str) -> list:
    """Python 코드에서 함수 정의 추출"""
    functions = []
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [arg.arg for arg in node.args.args if arg.arg != 'self']
                functions.append({
                    'name': node.name,
                    'args': args,
                    'lineno': node.lineno,
                    'is_async': isinstance(node, ast.AsyncFunctionDef)
                })
    except SyntaxError:
        pass
    return functions


def generate_test_code(filename: str, code: str) -> str:
    """함수에 대한 pytest 테스트 코드 자동 생성"""
    module_name = filename.replace('.py', '').replace('/', '.').replace('\\', '.')
    functions = extract_functions(code)

    if not functions:
        return f"# {filename}에서 테스트할 함수를 찾지 못했습니다."

    test_lines = [
        f'"""',
        f'{filename}에 대한 자동 생성 테스트',
        f'생성 도구: CodeBuddy Agent',
        f'"""',
        f'',
        f'import pytest',
        f'from unittest.mock import patch, MagicMock',
        f'# from {module_name} import {", ".join(f["name"] for f in functions[:5])}',
        f'',
        f'',
    ]

    for func in functions:
        name = func['name']
        args = func['args']
        is_async = func['is_async']

        # 테스트용 기본값 생성
        arg_defaults = []
        for arg in args:
            if 'id' in arg.lower():
                arg_defaults.append('1')
            elif 'name' in arg.lower():
                arg_defaults.append('"test_name"')
            elif 'url' in arg.lower():
                arg_defaults.append('"https://example.com"')
            elif 'data' in arg.lower() or 'content' in arg.lower():
                arg_defaults.append('{"key": "value"}')
            elif 'code' in arg.lower():
                arg_defaults.append('"def hello(): pass"')
            else:
                arg_defaults.append('"test_value"')

        args_str = ', '.join(arg_defaults)

        if is_async:
            test_lines += [
                f'@pytest.mark.asyncio',
                f'async def test_{name}_success():',
                f'    """정상 케이스: {name}"""',
                f'    # TODO: 실제 구현에 맞게 수정 필요',
                f'    result = await {name}({args_str})',
                f'    assert result is not None',
                f'',
                f'',
                f'@pytest.mark.asyncio',
                f'async def test_{name}_invalid_input():',
                f'    """비정상 케이스: {name} - 잘못된 입력"""',
                f'    with pytest.raises((ValueError, TypeError, Exception)):',
                f'        await {name}(None)',
                f'',
                f'',
            ]
        else:
            test_lines += [
                f'def test_{name}_success():',
                f'    """정상 케이스: {name}"""',
                f'    # TODO: 실제 구현에 맞게 수정 필요',
                f'    result = {name}({args_str})',
                f'    assert result is not None',
                f'',
                f'',
                f'def test_{name}_invalid_input():',
                f'    """비정상 케이스: {name} - 잘못된 입력"""',
                f'    with pytest.raises((ValueError, TypeError, Exception)):',
                f'        {name}(None)',
                f'',
                f'',
            ]

            # 외부 호출이 있는 함수는 mock 테스트 추가
            if any(keyword in name.lower() for keyword in ['get', 'post', 'fetch', 'send', 'call', 'invoke']):
                test_lines += [
                    f'@patch("requests.get")',
                    f'def test_{name}_with_mock(mock_get):',
                    f'    """Mock 테스트: {name} - 외부 의존성 제거"""',
                    f'    mock_get.return_value.status_code = 200',
                    f'    mock_get.return_value.json.return_value = {{"status": "ok"}}',
                    f'    result = {name}({args_str})',
                    f'    assert result is not None',
                    f'    mock_get.assert_called_once()',
                    f'',
                    f'',
                ]

    return '\n'.join(test_lines)


def handler(event, context):
    """Lambda 핸들러"""
    print(f"generate_unit_test 호출: {json.dumps(event)}")

    parameters = {p['name']: p['value'] for p in event.get('parameters', [])}
    code = parameters.get('code', '')
    filename = parameters.get('filename', 'module.py')

    try:
        if not filename.endswith('.py'):
            result = {
                'message': f'{filename}은 Python 파일이 아니어서 pytest 생성을 생략합니다.',
                'test_code': ''
            }
        else:
            test_code = generate_test_code(filename, code)
            functions = extract_functions(code)
            result = {
                'filename': f'test_{filename}',
                'functions_found': [f['name'] for f in functions],
                'test_code': test_code,
                'message': f'{len(functions)}개 함수에 대한 테스트 코드를 생성했습니다.'
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
        error_msg = f"테스트 생성 실패: {str(e)}"
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