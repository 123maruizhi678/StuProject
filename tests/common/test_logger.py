"""日志迁移回归：复用同一初始化状态，验证虚构日志可写入临时文件。"""

import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.common import logger as common_logger
from app.core.common import response


class LoggerContractTests(unittest.TestCase):
    def test_response_uses_canonical_logger(self):
        self.assertIs(response.get_logger, common_logger.get_logger)
        self.assertIs(response.logger, logging.getLogger("exception"))

    def test_initialization_is_idempotent_and_writes_utf8(self):
        root = logging.Logger("isolated-common-logger")
        with tempfile.TemporaryDirectory() as directory:
            logfile = Path(directory) / "test.log"
            with (
                patch.object(common_logger, "_initialized", False),
                patch.object(common_logger, "LOG_FILE", logfile),
                patch.object(common_logger.logging, "getLogger", return_value=root),
            ):
                try:
                    common_logger.init_logger(to_console=False)
                    common_logger.init_logger(to_console=False)
                    self.assertEqual(len(root.handlers), 1)
                    self.assertIs(common_logger.get_logger("same"), root)
                    root.warning("虚构日志：公共组件迁移测试")
                    root.handlers[0].flush()
                    self.assertIn("虚构日志：公共组件迁移测试", logfile.read_text(encoding="utf-8"))
                finally:
                    for handler in root.handlers[:]:
                        root.removeHandler(handler)
                        handler.close()

    def test_level_resolution(self):
        self.assertEqual(common_logger._resolve_level("warning"), logging.WARNING)
        self.assertEqual(common_logger._resolve_level("not-a-level"), logging.INFO)


if __name__ == "__main__":
    unittest.main()
