import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill/krouter-obsidian/scripts"))
sys.path.insert(0, str(ROOT / "extras/host-daily-evolution"))

# 测试绝不能写宿主真实的查询日志 / 学习游标 / 召回缓存：查询日志是夜间学习的输入，
# 评测题漏进去会被学成触发词（留出集也就不再是留出集）。子进程继承这里的环境变量。
import os  # noqa: E402
import tempfile  # noqa: E402

_ISOLATED = Path(tempfile.mkdtemp(prefix="krouter-tests-"))
os.environ["KROUTER_STATE_DIR"] = str(_ISOLATED / "state")
os.environ.setdefault("KROUTER_CACHE_DIR", str(_ISOLATED / "cache"))
os.environ["KROUTER_NOTIFY"] = "0"  # 测试不弹桌面通知
