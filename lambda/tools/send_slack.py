import os
import json
import requests

SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL', '')


def post_to_slack(channel: str, message: str) -> None:
    """Slack Incoming Webhook으로 메시지 전송"""
    payload = {'text': message}
    if channel:
        payload['channel'] = channel
    response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
    response.raise_for_status()


def handler(event, context):
    """Lambda 핸들러 - Bedrock Agent Action Group에서 호출"""
    print(f"send_slack_message 호출: {json.dumps(event)}")

    parameters = {p['name']: p['value'] for p in event.get('parameters', [])}
    channel = parameters.get('channel', '')
    message = parameters.get('message', '')

    try:
        if not SLACK_WEBHOOK_URL:
            raise ValueError('SLACK_WEBHOOK_URL이 설정되지 않았습니다')
        post_to_slack(channel, message)
        result = {'success': True, 'message': 'Slack 알림이 전송되었습니다.'}
    except Exception as e:
        error_msg = f"Slack 알림 전송 실패: {str(e)}"
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
