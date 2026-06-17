"""日志模块"""

import logging


class Logger:
    def __init__(self, log_file: str):
        self.logger = logging.getLogger("cttc")
        self.logger.setLevel(logging.DEBUG)

        # 控制台
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
        self.logger.addHandler(ch)

        # 文件
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        self.logger.addHandler(fh)

    def info(self, msg): self.logger.info(msg)
    def warn(self, msg): self.logger.warning(msg)
    def error(self, msg): self.logger.error(msg)
    def debug(self, msg): self.logger.debug(msg)
