import logging

from hub import config


class _RedactSecretsFilter(logging.Filter):
    def __init__(self) -> None:
        super().__init__()
        self._secrets = [s for s in (config.BOT_TOKEN, config.AGENT_SHARED_SECRET) if s]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for secret in self._secrets:
            msg = msg.replace(secret, "***REDACTED***")
        record.msg = msg
        record.args = ()
        return True


def configure() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(_RedactSecretsFilter())

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    # python-telegram-bot's own HTTP client logs request URLs at INFO, which
    # is noisy and not actionable; keep it at WARNING.
    logging.getLogger("httpx").setLevel(logging.WARNING)
