import json
import re
import boto3
import logging
import os
from botocore.exceptions import ClientError

# 設置日志
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 初始化SES客户端
ses = boto3.client("ses", region_name="ap-northeast-1")

# 获取环境变量
EMAIL_CONFIG = json.loads(os.environ.get('EMAIL_CONFIG', '{}'))
RECIPIENT_EMAIL = os.environ.get('RECIPIENT_EMAIL', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', '')
AUTOMATICALLY_SENDER_EMAIL = os.environ.get('AUTOMATICALLY_SENDER_EMAIL', '')

# ---- サーバー側入力検証（2026-10 脆弱性診断 S04/S07 対応）----
# 送信を許可するフィールドの白名单。フロント側の契約
# （contact/page.tsx の name 属性 + formType/submissionId + attribution 白名单键）と一致させる。
ALLOWED_FIELDS = {
    "formType", "submissionId",
    "氏名", "ふりがな", "メール", "会社名", "担当者", "種別", "内容",
    "source", "page", "contentId", "projectId", "category",
}
ALLOWED_FORM_TYPES = {"individual", "corporate"}
# ハニーポット。フロントは通常このキーを送信しない（送信前に削除）。
HONEYPOT_FIELDS = {"website", "privacyConsent"}
MAX_BODY_BYTES = 8192
MAX_FIELD_CHARS = 2000
# 自動返信の送信先を兼ねるため、メール欄は厳しめの形式検証を行う。
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
ALLOWED_ORIGIN_PREFIXES = ("https://www.onewonder.co.jp", "https://onewonder.co.jp")

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "OPTIONS,POST",
}


def _response(status_code, payload):
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(payload, ensure_ascii=False),
    }


def _silent_ok():
    # ボットには成功と同じ応答を返し、送信は行わない。
    return _response(200, {"message": "お問い合わせが送信されました。"})


def _reject(message):
    return _response(400, {"message": message})


def _origin_allowed(headers):
    # Origin/Referer が付いている場合は自社サイト由来のみ許可する。
    # 付いていない直接の POST（監視・古いクライアント）は後段の検証と
    # API Gateway のスロットリング（main.tf 側）に任せる。
    if not headers:
        return True
    for name in ("Origin", "origin", "Referer", "referer"):
        value = headers.get(name, "")
        if value:
            return any(value.startswith(prefix) for prefix in ALLOWED_ORIGIN_PREFIXES)
    return True


def _sanitize(body):
    """白名单外のキーを除去し、各値を文字列として長さ制限にかける。

    返り値は (sanitized_dict, dropped_count)。ボディは dict のみ受け入れる。
    """
    if not isinstance(body, dict):
        return None, 0
    sanitized = {}
    dropped = 0
    for key, value in body.items():
        if not isinstance(key, str):
            dropped += 1
            continue
        if key in HONEYPOT_FIELDS:
            # フロント契約では送信されない管理フィールド。届いた場合は無視。
            dropped += 1
            continue
        if key not in ALLOWED_FIELDS:
            dropped += 1
            continue
        if not isinstance(value, str) or len(value) > MAX_FIELD_CHARS:
            dropped += 1
            continue
        sanitized[key] = value
    return sanitized, dropped


def _is_honeypot_filled(body):
    for key in ("website", "website-url", "url"):
        value = body.get(key)
        if isinstance(value, str) and value.strip() != "":
            return True
    return False


def lambda_handler(event, context):
    try:
        # 请求体は必ず JSON・サイズ上限以内
        raw_body = event.get("body", "{}")
        if raw_body and len(raw_body) > MAX_BODY_BYTES:
            return _reject("リクエストが大きすぎます。")

        headers = event.get("headers") or {}
        if not _origin_allowed(headers):
            return _reject("リクエストの送信元が不正です。")

        body = json.loads(raw_body or "{}")
        if not isinstance(body, dict):
            return _reject("リクエストの形式が不正です。")

        # ハニーポット（フロント契約外に埋められていた場合も含めて判定）
        if _is_honeypot_filled(body):
            # ログには内容を残さない（PII 不落地）
            logger.info("honeypot triggered; dropped silently")
            return _silent_ok()

        body, dropped = _sanitize(body)
        if body is None:
            return _reject("リクエストの形式が不正です。")
        # PII をログに落とさない。形式と件数のみ記録する（S07 対応）。
        logger.info(
            "contact submission accepted for validation: fields=%d dropped=%d request_id=%s",
            len(body), dropped, getattr(context, "aws_request_id", "-"),
        )

        form_type = body.get("formType", "")
        if form_type not in ALLOWED_FORM_TYPES:
            return _reject("リクエストの形式が不正です。")

        # 確定主题
        if form_type in EMAIL_CONFIG.get('email_subjects', {}):
            subject = EMAIL_CONFIG['email_subjects'][form_type]
        else:
            subject = "お問い合わせ"

        inquirer_email = body.get("メール", "")
        # 自動返信の送信先になるため、ここで必ず形式検証する（S04 対応）。
        if not EMAIL_RE.match(inquirer_email):
            return _reject("メールアドレスの形式をご確認ください。")

        if form_type == "individual":
            inquirer_name = body.get("氏名", "")
            greeting = f"{inquirer_name} 様"
        else:
            company_name = body.get("会社名", "")
            contact_person = body.get("担当者", "")
            greeting = f"{company_name} {contact_person} 様"

        # 格式化邮件正文（发送给公司）——白名单済みフィールドのみ出力
        email_body = "以下の内容でお問い合わせがありました：\n\n"
        for key, value in body.items():
            if key != "formType":
                email_body += f"{key}: {value}\n"

        # 设置SES参数（发送给公司）
        params = {
            "Source": SENDER_EMAIL,  # 发件人地址
            "Destination": {
                "ToAddresses": [RECIPIENT_EMAIL],  # 收件人地址
            },
            "Message": {
                "Subject": {
                    "Data": subject,
                    "Charset": "UTF-8",
                },
                "Body": {
                    "Text": {
                        "Data": email_body,
                        "Charset": "UTF-8",
                    },
                },
            },
        }

        # 如果有配置抄送地址
        if 'cc_emails' in EMAIL_CONFIG and EMAIL_CONFIG['cc_emails']:
            params["Destination"]["CcAddresses"] = EMAIL_CONFIG['cc_emails']

        # 如果有配置密送地址
        if 'bcc_emails' in EMAIL_CONFIG and EMAIL_CONFIG['bcc_emails']:
            params["Destination"]["BccAddresses"] = EMAIL_CONFIG['bcc_emails']

        # 发送邮件给公司
        response = ses.send_email(**params)
        logger.info("Email sent to company! Message ID: %s", response['MessageId'])

        # 发送自动回执给问い合わせ人（宛先は上で形式検証済み）
        auto_reply_body = f"""{greeting}

※こちらは株式会社ワンワンダーからの自動返信メールです。
下記案件へのエントリーを受け付いたしました。別途担当よりご連絡されていただきます。

=================
{email_body}
=================

お問い合わせありがとうございました。
株式会社ワンワンダー
"""

        auto_reply_params = {
            "Source": AUTOMATICALLY_SENDER_EMAIL,  # 发件人地址
            "Destination": {
                "ToAddresses": [inquirer_email],  # 收件人地址（问い合わせ人的邮箱）
            },
            "Message": {
                "Subject": {
                    "Data": "お問い合わせありがとうございます",
                    "Charset": "UTF-8",
                },
                "Body": {
                    "Text": {
                        "Data": auto_reply_body,
                        "Charset": "UTF-8",
                    },
                },
            },
        }

        auto_reply_response = ses.send_email(**auto_reply_params)
        logger.info(
            "Auto-reply sent! Message ID: %s", auto_reply_response['MessageId']
        )

        # 返回成功响应
        return _response(200, {
            "message": "お問い合わせが送信されました。",
            "messageId": response["MessageId"],
        })

    except ClientError as e:
        # 内部エラーの詳細はログのみに出し、応答には含めない。
        logger.error("Email sending error: %s", e.response['Error']['Message'])
        return _response(500, {
            "message": "メール送信中にエラーが発生しました。",
        })

    except Exception as e:
        logger.error("Error processing request: %s", str(e))
        return _response(500, {
            "message": "メール送信中にエラーが発生しました。",
        })
