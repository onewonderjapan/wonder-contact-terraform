import json
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


def lambda_handler(event, context):
    try:
        # 解析请求体
        body = json.loads(event.get("body", "{}"))
        logger.info(f"Received form data: {body}")

        # 确定主题基于表单类型
        form_type = body.get("formType", "")
        
        # 根据表单类型设置邮件主题
        if form_type in EMAIL_CONFIG.get('email_subjects', {}):
            subject = EMAIL_CONFIG['email_subjects'][form_type]
        else:
            subject = "お問い合わせ"
            
        if form_type == "individual":
            # 获取个人问询者的邮箱和名字
            inquirer_email = body.get("メール", "")
            inquirer_name = body.get("氏名", "")
            # 称呼
            greeting = f"{inquirer_name} 様"
        else:
            # 获取企业问询者的邮箱、公司名和担当者
            inquirer_email = body.get("メール", "")
            company_name = body.get("会社名", "")
            contact_person = body.get("担当者", "")
            # 称呼：会社名+担当者
            greeting = f"{company_name} {contact_person} 様"

        # 格式化邮件正文（发送给公司）
        email_body = "以下の内容でお問い合わせがありました：\n\n"

        # 添加所有表单字段到邮件正文
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
        logger.info(f"Email sent to company! Message ID: {response['MessageId']}")

        # 如果有提供邮箱，发送自动回执给问い合わせ人
        if inquirer_email:
            # 格式化自动回执邮件正文
            auto_reply_body = f"""{greeting}

※こちらは株式会社ワンワンダーからの自動返信メールです。
下記案件へのエントリーを受け付いたしました。別途担当よりご連絡されていただきます。

=================
{email_body}
=================

お問い合わせありがとうございました。
株式会社ワンワンダー
"""

            # 设置SES参数（发送给问い合わせ人）
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

            # 发送自动回执邮件
            auto_reply_response = ses.send_email(**auto_reply_params)
            logger.info(
                f"Auto-reply sent! Message ID: {auto_reply_response['MessageId']}"
            )

        # 返回成功响应
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",  # 支持CORS
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "OPTIONS,POST",
            },
            "body": json.dumps(
                {
                    "message": "お問い合わせが送信されました。",
                    "messageId": response["MessageId"],
                }
            ),
        }

    except ClientError as e:
        logger.error(f"Email sending error: {e.response['Error']['Message']}")
        return {
            "statusCode": 500,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "OPTIONS,POST",
            },
            "body": json.dumps(
                {
                    "message": "メール送信中にエラーが発生しました。",
                    "error": e.response["Error"]["Message"],
                }
            ),
        }

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "OPTIONS,POST",
            },
            "body": json.dumps({"message": "エラーが発生しました。", "error": str(e)}),
        }