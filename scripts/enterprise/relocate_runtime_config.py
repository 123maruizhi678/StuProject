"""历史命令兼容入口：统一工作流配置直接写入唯一根 .env。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.enterprise.apply_workflow_config import main

if __name__ == "__main__":
    main()
