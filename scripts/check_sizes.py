import argparse
import os
import re
import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path

GIT_LIMIT_BYTES = 500 * 1024**2
LOCAL_LIMIT_BYTES = int(1.5 * 1024**3)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OLLAMA_MODEL = "qwen2.5:0.5b"
SIZE_PATTERN = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>B|KB|MB|GB)\b")
UNIT_MULTIPLIERS = {
    "B": 1,
    "KB": 1024,
    "MB": 1024**2,
    "GB": 1024**3,
}


def calculate_paths_size(paths: Iterable[Path]) -> int:
    """累加存在文件的逻辑字节数。"""
    return sum(path.stat().st_size for path in paths if path.is_file())


def calculate_directory_size(directory: Path) -> int:
    """递归计算目录中的普通文件，不跟随目录外链接。"""
    if not directory.exists():
        return 0
    return calculate_paths_size(path for path in directory.rglob("*") if not path.is_symlink())


def list_tracked_paths(project_root: Path) -> list[Path]:
    """读取 Git 跟踪清单，避免把本地产物计入仓库容量。"""
    result = subprocess.run(
        ["git", "-C", str(project_root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [
        project_root / relative_path
        for relative_path in result.stdout.decode("utf-8").split("\0")
        if relative_path
    ]


def parse_ollama_model_size(output: str, model: str) -> int:
    """从 Ollama 表格中读取指定模型的 MB 或 GB 大小。"""
    for line in output.splitlines():
        columns = line.split()
        if not columns or columns[0] != model:
            continue
        match = SIZE_PATTERN.search(line)
        if match:
            value = float(match.group("value"))
            return int(value * UNIT_MULTIPLIERS[match.group("unit")])
    return 0


def get_ollama_model_size(model: str) -> tuple[int, bool]:
    """返回默认模型大小和是否检测到该模型。"""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return 0, False
    size = parse_ollama_model_size(result.stdout, model)
    return size, size > 0


def evaluate_limits(*, git_bytes: int, local_bytes: int, git_only: bool) -> int:
    """按硬性上限返回命令行退出码。"""
    git_over_limit = git_bytes > GIT_LIMIT_BYTES
    local_over_limit = not git_only and local_bytes > LOCAL_LIMIT_BYTES
    return 1 if git_over_limit or local_over_limit else 0


def format_bytes(size: int) -> str:
    """将字节转换为便于核对的二进制单位。"""
    if size >= 1024**3:
        return f"{size / 1024**3:.2f} GB"
    return f"{size / 1024**2:.2f} MB"


def main(argv: Sequence[str] | None = None) -> int:
    """执行 Git 与本地环境容量检查。"""
    parser = argparse.ArgumentParser(description="检查 tourGuide 项目容量")
    parser.add_argument("--git-only", action="store_true", help="仅检查 Git 跟踪文件")
    args = parser.parse_args(argv)

    tracked_paths = list_tracked_paths(PROJECT_ROOT)
    git_bytes = calculate_paths_size(tracked_paths)
    print(f"Git 跟踪文件：{format_bytes(git_bytes)} / 500.00 MB")

    local_bytes = 0
    if not args.git_only:
        model = os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        venv_bytes = calculate_directory_size(PROJECT_ROOT / ".venv")
        model_bytes, model_found = get_ollama_model_size(model)
        local_bytes = venv_bytes + model_bytes
        print(f"项目虚拟环境：{format_bytes(venv_bytes)}")
        if model_found:
            print(f"默认 Ollama 模型：{format_bytes(model_bytes)}")
        else:
            print(f"默认 Ollama 模型：未检测到 {model}")
        print(f"本地环境合计：{format_bytes(local_bytes)} / 1.50 GB")

    exit_code = evaluate_limits(
        git_bytes=git_bytes,
        local_bytes=local_bytes,
        git_only=args.git_only,
    )
    print("容量检查通过" if exit_code == 0 else "容量检查失败：已超过硬性上限")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
