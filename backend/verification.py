"""注册/找回密码验证码服务(单进程内存实现)。

生命周期:
- 10 分钟有效;新码发送成功后旧码立即失效;
- 校验成功立即销毁(一次性);连续 5 次错误作废;
- key=(email, purpose),注册码不能用于重置,反之亦然;
- 频控:同邮箱 60 秒 1 条 + 全来源滑动窗口 10 条/分钟;
- threading.Lock 保证并发校验/消费原子,不会同一码成功两次;
- 惰性清理过期记录。

局限(单机 MVP 有意为之):服务重启后验证码失效;多 worker 部署需换共享存储。
"""
import secrets
import threading
import time

CODE_TTL = 600          # 验证码有效期(秒)
RESEND_INTERVAL = 60    # 同邮箱重发间隔(秒)
MAX_ATTEMPTS = 5        # 连续错误次数上限,超过即作废
GLOBAL_WINDOW = 60      # 全来源频控窗口(秒)
GLOBAL_LIMIT = 10       # 窗口内最大发送条数


class RateLimited(Exception):
    pass


class VerificationService:
    def __init__(self):
        self.lock = threading.Lock()
        self.codes = {}     # (email, purpose) -> {code, expires, attempts, sent_at}
        self.sent_log = []  # 全来源发送时间戳(滑动窗口)

    def issue(self, email, purpose, now=None):
        """签发验证码;触发频控抛 RateLimited。返回明文码(演示模式回显/SMTP 正文共用)。"""
        now = now if now is not None else time.time()
        with self.lock:
            self._gc(now)
            recent = [t for t in self.sent_log if now - t < GLOBAL_WINDOW]
            if len(recent) >= GLOBAL_LIMIT:
                raise RateLimited('验证码发送过于频繁，请稍后再试')
            last = self.codes.get((email, purpose))
            if last and now - last['sent_at'] < RESEND_INTERVAL:
                wait = int(RESEND_INTERVAL - (now - last['sent_at'])) + 1
                raise RateLimited(f'请 {wait} 秒后再获取验证码')
            code = f'{secrets.randbelow(1000000):06d}'
            self.codes[(email, purpose)] = {'code': code, 'expires': now + CODE_TTL, 'attempts': 0, 'sent_at': now}
            self.sent_log.append(now)
            return code

    def verify(self, email, purpose, code, now=None):
        """校验并一次性消费;错误累计达上限作废;过期/不存在返回 False。"""
        now = now if now is not None else time.time()
        with self.lock:
            self._gc(now)
            key = (email, purpose)
            entry = self.codes.get(key)
            if not entry or entry['expires'] <= now:
                self.codes.pop(key, None)
                return False
            if entry['code'] != str(code).strip():
                entry['attempts'] += 1
                if entry['attempts'] >= MAX_ATTEMPTS:
                    self.codes.pop(key, None)
                return False
            self.codes.pop(key, None)
            return True

    def _gc(self, now):
        expired = [key for key, entry in self.codes.items() if entry['expires'] <= now]
        for key in expired:
            self.codes.pop(key, None)
        self.sent_log[:] = [t for t in self.sent_log if now - t < GLOBAL_WINDOW]
