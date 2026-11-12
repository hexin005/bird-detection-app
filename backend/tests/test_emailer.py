"""emailer 报错细节：SMTP 拒收原文应进入 MailSendError（页面可见真实原因，如 550 收件账号不存在）。"""
import smtplib
import unittest

from backend.emailer import _smtp_detail


class SmtpDetailTests(unittest.TestCase):
    def test_data_error_includes_code_and_text(self):
        exc = smtplib.SMTPDataError(550, b'The recipient may contain a non-existent account')
        detail = _smtp_detail(exc)
        self.assertIn('550', detail)
        self.assertIn('non-existent account', detail)

    def test_recipients_refused_bytes_decoded(self):
        exc = smtplib.SMTPRecipientsRefused({'bad@qq.com': (550, b'User not found')})
        detail = _smtp_detail(exc)
        self.assertTrue(detail)  # 无 smtp_error 属性时回退 str(exc)，不抛错

    def test_non_smtp_error_falls_back_to_str(self):
        self.assertIn('timed out', _smtp_detail(TimeoutError('timed out')))

    def test_detail_truncated_to_160(self):
        exc = smtplib.SMTPDataError(550, 'x' * 500)
        self.assertLessEqual(len(_smtp_detail(exc)), 160)


if __name__ == '__main__':
    unittest.main()
