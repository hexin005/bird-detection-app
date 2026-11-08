"""验证码邮件投递。

- smtp_host 配置齐全 → smtplib 真发(465 走 SSL,587 走 STARTTLS);发送失败抛
  MailSendError,由接口转 502,绝不降级回演示码。
- 未配置 SMTP 且 email_demo=True(显式演示开关,local.json 缺省即 True)→ 验证码
  打印到服务端日志,接口返回 demo_code 供页面横幅展示。
"""
import smtplib
import ssl
from email.message import EmailMessage


class MailSendError(Exception):
    pass


PURPOSE_LABELS = {'register': '注册', 'reset': '找回密码'}


def send_code_mail(settings, email, code, purpose):
    """返回 True 表示演示模式(demo_code 可回显);真发成功返回 False;失败抛异常。"""
    label = PURPOSE_LABELS.get(purpose, '验证')
    if settings.smtp_host:
        message = EmailMessage()
        message['Subject'] = f'青禾果园守护{label}验证码:{code}'
        message['From'] = settings.smtp_from or settings.smtp_user
        message['To'] = email
        message.set_content(f'您的{label}验证码是 {code},10 分钟内有效。若非本人操作请忽略本邮件。')
        try:
            if settings.smtp_port == 465:
                with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port,
                                      context=ssl.create_default_context(), timeout=10) as server:
                    if settings.smtp_user:
                        server.login(settings.smtp_user, settings.smtp_pass)
                    server.send_message(message)
            else:
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port or 25, timeout=10) as server:
                    server.ehlo()
                    if settings.smtp_port == 587:
                        server.starttls(context=ssl.create_default_context())
                    if settings.smtp_user:
                        server.login(settings.smtp_user, settings.smtp_pass)
                    server.send_message(message)
        except Exception as exc:
            raise MailSendError(f'验证码邮件发送失败({exc.__class__.__name__})，请检查 SMTP 配置') from exc
        return False
    if not settings.email_demo:
        raise MailSendError('邮件服务未配置，且演示模式未开启（local.json: email_demo）')
    print(f'[email-demo] {label} 验证码 -> {email}: {code}（10 分钟内有效）', flush=True)
    return True
