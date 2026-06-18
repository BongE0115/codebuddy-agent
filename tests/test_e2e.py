import pytest
import requests
import json
import os

# 테스트 설정
API_URL = os.environ.get('CODEBUDDY_API_URL', 'https://zq70dn3jr3.execute-api.ap-northeast-2.amazonaws.com/prod/review')

HEADERS = {
    'Content-Type': 'application/json',
}


class TestCodeBuddyAPI:
    """CodeBuddy API E2E 테스트"""

    def test_valid_pr_review(self):
        """정상 케이스: 유효한 PR URL로 리뷰 요청"""
        payload = {
            'pr_url': 'https://github.com/your-org/codebuddy-test/pull/1'
        }
        response = requests.post(API_URL, json=payload, headers=HEADERS, timeout=60)
        assert response.status_code == 200
        data = response.json()
        assert 'result' in data or 'message' in data

    def test_invalid_pr_url(self):
        """비정상 케이스: 잘못된 PR URL"""
        payload = {'pr_url': 'invalid-url'}
        response = requests.post(API_URL, json=payload, headers=HEADERS, timeout=30)
        assert response.status_code in [400, 500]

    def test_missing_pr_url(self):
        """비정상 케이스: pr_url 누락"""
        payload = {}
        response = requests.post(API_URL, json=payload, headers=HEADERS, timeout=30)
        assert response.status_code == 400

    def test_nonexistent_pr(self):
        """비정상 케이스: 존재하지 않는 PR"""
        payload = {
            'pr_url': 'https://github.com/nonexistent-org/nonexistent-repo/pull/99999'
        }
        response = requests.post(API_URL, json=payload, headers=HEADERS, timeout=60)
        # 오류 메시지가 포함된 200 또는 500 반환
        assert response.status_code in [200, 500]


class TestComplexityTool:
    """복잡도 분석 툴 단위 테스트"""

    def test_simple_function_complexity(self):
        """단순 함수의 복잡도가 낮아야 함"""
        import sys
        sys.path.insert(0, 'lambda/tools')
        from complexity import calculate_cyclomatic_complexity

        code = """
def add(a, b):
    return a + b
"""
        result = calculate_cyclomatic_complexity(code)
        assert 'add' in result
        assert result['add']['complexity'] == 1

    def test_complex_function_detection(self):
        """복잡한 함수가 높은 복잡도로 탐지되어야 함"""
        import sys
        sys.path.insert(0, 'lambda/tools')
        from complexity import calculate_cyclomatic_complexity

        code = """
def complex_function(x, y, z):
    if x > 0:
        if y > 0:
            for i in range(z):
                if i % 2 == 0:
                    print(i)
                else:
                    continue
        elif y < 0:
            while z > 0:
                z -= 1
    else:
        return None
    return x + y + z
"""
        result = calculate_cyclomatic_complexity(code)
        assert 'complex_function' in result
        assert result['complex_function']['complexity'] > 5

    def test_sql_injection_detection(self):
        """SQL Injection 취약점이 탐지되어야 함"""
        import sys
        sys.path.insert(0, 'lambda/tools')
        from complexity import check_security

        code = """
def get_user(id):
    query = f"SELECT * FROM users WHERE id = {id}"
    return execute(query)
"""
        issues = check_security(code)
        sql_issues = [i for i in issues if 'SQL' in i.get('type', '')]
        assert len(sql_issues) > 0

    def test_hardcoded_secret_detection(self):
        """하드코딩된 비밀번호가 탐지되어야 함"""
        import sys
        sys.path.insert(0, 'lambda/tools')
        from complexity import check_security

        code = 'API_KEY = "12345secret"'
        issues = check_security(code)
        assert len(issues) > 0


class TestTestGenTool:
    """테스트 생성 툴 단위 테스트"""

    def test_generates_test_for_function(self):
        """함수에 대한 테스트 코드 생성 확인"""
        import sys
        sys.path.insert(0, 'lambda/tools')
        from testgen import generate_test_code, extract_functions

        code = """
def add(a, b):
    return a + b

def get_user(user_id):
    return {"id": user_id}
"""
        functions = extract_functions(code)
        assert len(functions) == 2
        assert functions[0]['name'] == 'add'

        test_code = generate_test_code('math.py', code)
        assert 'def test_add' in test_code
        assert 'def test_get_user' in test_code
        assert 'import pytest' in test_code


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_empty_code(self):
        """빈 코드 처리"""
        import sys
        sys.path.insert(0, 'lambda/tools')
        from complexity import calculate_cyclomatic_complexity
        result = calculate_cyclomatic_complexity('')
        assert result == {}

    def test_syntax_error_code(self):
        """문법 오류 코드 처리"""
        import sys
        sys.path.insert(0, 'lambda/tools')
        from complexity import calculate_cyclomatic_complexity
        result = calculate_cyclomatic_complexity('def broken(:')
        assert 'error' in result or result == {}

    def test_non_python_file(self):
        """Python이 아닌 파일 처리"""
        import sys
        sys.path.insert(0, 'lambda/tools')
        from testgen import generate_test_code
        result = generate_test_code('index.js', 'const x = 1;')
        assert '# index.js에서' in result or result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])