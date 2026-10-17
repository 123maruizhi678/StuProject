"""把仓库 dify/report/report.yml 的 LLM 提示词同步到 Dify 已部署工作流。

设计原则：仓库 DSL 是唯一事实来源；本脚本只替换草稿中 LLM 节点的
system 提示词，不改动模型绑定、节点结构与其它配置（模型由 Dify
工作区自行管理，避免覆盖线上有效配置）。

前置：
    - Dify 控制台可访问（DIFY_CONSOLE_BASE，默认 http://127.0.0.1）；
    - 控制台账号通过环境变量提供，不写入任何文件：
        DIFY_CONSOLE_EMAIL、DIFY_CONSOLE_PASSWORD
      （Dify 1.12 登录接口要求 password 为 Base64 编码后提交）。

用法：
    # 预演：只打印将写入的提示词，不做任何修改
    python scripts/report/sync_report_workflow.py --app-id <app_id> --dry-run

    # 同步草稿（不发布）
    python scripts/report/sync_report_workflow.py --app-id <app_id>

    # 同步并发布（发布后 /workflows/run 立即生效）
    python scripts/report/sync_report_workflow.py --app-id <app_id> --publish
"""
import argparse
import base64
import os
import sys
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[2]
DSL_PATH = ROOT / "dify" / "report" / "report.yml"
DEFAULT_BASE = "http://127.0.0.1"


class ConsoleError(RuntimeError):
    """控制台操作失败。"""


class DifyConsole:
    """Dify 控制台最小客户端：登录（Cookie + CSRF）与工作流草稿/发布。"""

    def __init__(self, base: str, email: str, password: str):
        self.base = base.rstrip("/")
        self.session = requests.Session()
        encoded = base64.b64encode(password.encode("utf-8")).decode("ascii")
        response = self.session.post(
            f"{self.base}/console/api/login",
            json={"email": email, "password": encoded},
            timeout=30,
        )
        if response.status_code != 200:
            raise ConsoleError(f"控制台登录失败：HTTP {response.status_code} {response.text[:200]}")
        self.csrf = self.session.cookies.get("csrf_token")
        if not self.csrf:
            raise ConsoleError("登录响应缺少 csrf_token Cookie")

    def _headers(self) -> dict:
        return {"X-CSRF-Token": self.csrf}

    def get_draft(self, app_id: str) -> dict:
        response = self.session.get(
            f"{self.base}/console/api/apps/{app_id}/workflows/draft",
            headers=self._headers(),
            timeout=30,
        )
        if response.status_code != 200:
            raise ConsoleError(f"获取草稿失败：HTTP {response.status_code} {response.text[:200]}")
        return response.json()

    def sync_draft(self, app_id: str, graph: dict, features: dict, unique_hash: str | None) -> dict:
        payload = {"graph": graph, "features": features}
        if unique_hash:
            payload["hash"] = unique_hash
        response = self.session.post(
            f"{self.base}/console/api/apps/{app_id}/workflows/draft",
            json=payload,
            headers=self._headers(),
            timeout=60,
        )
        if response.status_code != 200:
            raise ConsoleError(f"同步草稿失败：HTTP {response.status_code} {response.text[:300]}")
        return response.json()

    def publish(self, app_id: str, marked_name: str, marked_comment: str) -> dict:
        response = self.session.post(
            f"{self.base}/console/api/apps/{app_id}/workflows/publish",
            json={"marked_name": marked_name, "marked_comment": marked_comment},
            headers=self._headers(),
            timeout=60,
        )
        if response.status_code != 200:
            raise ConsoleError(f"发布失败：HTTP {response.status_code} {response.text[:300]}")
        return response.json()


def load_dsl_prompt(dsl_path: Path) -> str:
    """从仓库 DSL 提取 LLM 节点的 system 提示词（唯一事实来源）。"""
    if not dsl_path.exists():
        raise ConsoleError(f"DSL 不存在：{dsl_path}")
    document = yaml.safe_load(dsl_path.read_text(encoding="utf-8"))
    nodes = document.get("workflow", {}).get("graph", {}).get("nodes", [])
    for node in nodes:
        data = node.get("data", {})
        if data.get("type") != "llm":
            continue
        for prompt in data.get("prompt_template", []):
            if prompt.get("role") == "system":
                text = prompt.get("text")
                if isinstance(text, str) and text.strip():
                    return text
    raise ConsoleError("DSL 中未找到 LLM 节点的 system 提示词")


def update_draft_prompt(draft: dict, prompt: str) -> tuple[dict, int]:
    """替换草稿中全部 LLM 节点的 system 提示词，返回 (graph, 变更节点数)。"""
    graph = draft.get("graph") or {}
    llm_nodes = [n for n in graph.get("nodes", []) if n.get("data", {}).get("type") == "llm"]
    if not llm_nodes:
        raise ConsoleError("草稿中未找到 LLM 节点")
    changed = 0
    for node in llm_nodes:
        for prompt_item in node["data"].get("prompt_template") or []:
            if prompt_item.get("role") == "system" and prompt_item.get("text") != prompt:
                prompt_item["text"] = prompt
                changed += 1
    return graph, changed


def main() -> int:
    parser = argparse.ArgumentParser(description="同步仓库报告 DSL 提示词到 Dify 工作流")
    parser.add_argument("--app-id", required=True, help="Dify 应用 ID（智能报告生成工作流）")
    parser.add_argument("--dsl", default=str(DSL_PATH), help="仓库 DSL 路径")
    parser.add_argument("--base", default=os.environ.get("DIFY_CONSOLE_BASE", DEFAULT_BASE))
    parser.add_argument("--publish", action="store_true", help="同步后立即发布")
    parser.add_argument("--dry-run", action="store_true", help="只打印将写入的提示词")
    parser.add_argument("--marked-name", default="", help="发布版本名（可选）")
    parser.add_argument("--marked-comment", default="", help="发布备注（可选）")
    args = parser.parse_args()

    prompt = load_dsl_prompt(Path(args.dsl))
    print(f"== 仓库 DSL 提示词（{args.dsl}）==")
    print(prompt)
    print()

    if args.dry_run:
        print("[预演] 未做任何修改")
        return 0

    email = os.environ.get("DIFY_CONSOLE_EMAIL")
    password = os.environ.get("DIFY_CONSOLE_PASSWORD")
    if not email or not password:
        print("[失败] 请设置环境变量 DIFY_CONSOLE_EMAIL 与 DIFY_CONSOLE_PASSWORD（不写入文件）")
        return 2

    console = DifyConsole(args.base, email, password)
    draft = console.get_draft(args.app_id)
    print(f"== 草稿（app_id={args.app_id}）==")
    graph, changed = update_draft_prompt(draft, prompt)
    if changed == 0:
        print("  提示词已与仓库一致，无需同步")
    else:
        result = console.sync_draft(
            args.app_id,
            graph,
            draft.get("features") or {},
            draft.get("hash"),
        )
        print(f"  草稿已同步：{result}")

    if args.publish:
        result = console.publish(args.app_id, args.marked_name, args.marked_comment)
        print(f"  已发布：{result}")
        print("  发布后 /workflows/run 立即使用新提示词")
    else:
        print("  未发布（加 --publish 发布后生效）")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ConsoleError as exc:
        print(f"[失败] {exc}")
        raise SystemExit(1)
