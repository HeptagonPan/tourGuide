import subprocess
import sys
from pathlib import Path

from scripts.check_sizes import (
    GIT_LIMIT_BYTES,
    LOCAL_LIMIT_BYTES,
    calculate_paths_size,
    evaluate_limits,
    parse_ollama_model_size,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_git_files_over_500_mb_fail(tmp_path: Path) -> None:
    oversized = tmp_path / "oversized.bin"
    with oversized.open("wb") as file_handle:
        file_handle.truncate(GIT_LIMIT_BYTES + 1)

    git_bytes = calculate_paths_size([oversized])

    assert evaluate_limits(git_bytes=git_bytes, local_bytes=0, git_only=True) == 1


def test_small_repository_passes(tmp_path: Path) -> None:
    small_file = tmp_path / "small.txt"
    small_file.write_text("tourGuide", encoding="utf-8")

    git_bytes = calculate_paths_size([small_file])

    assert evaluate_limits(git_bytes=git_bytes, local_bytes=0, git_only=False) == 0


def test_local_environment_over_1_5_gb_fails() -> None:
    assert (
        evaluate_limits(
            git_bytes=1,
            local_bytes=LOCAL_LIMIT_BYTES + 1,
            git_only=False,
        )
        == 1
    )


def test_ollama_size_parser_supports_mb_and_gb() -> None:
    mb_output = "NAME ID SIZE MODIFIED\nqwen2.5:0.5b abc123 397 MB 1 minute ago\n"
    gb_output = "NAME ID SIZE MODIFIED\nqwen2.5:0.5b abc123 1.2 GB 1 minute ago\n"

    assert parse_ollama_model_size(mb_output, "qwen2.5:0.5b") == 397 * 1024**2
    assert parse_ollama_model_size(gb_output, "qwen2.5:0.5b") == int(1.2 * 1024**3)


def test_script_runs_directly_from_project_root() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_sizes.py", "--git-only"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Git 跟踪文件" in result.stdout
