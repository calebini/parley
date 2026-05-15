from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile

from parley.errors import FileIOError, ParleyError
from parley.hashing import sha256_text


def commit_files(project_root: Path, files: dict[Path, bytes], report_files: dict[Path, str]) -> None:
    temp_dir = Path(tempfile.mkdtemp(prefix=".parley-staging-", dir=project_root))
    backups: dict[Path, Path | None] = {}
    committed: list[Path] = []
    try:
        staged_binary: dict[Path, Path] = {}
        staged_text: dict[Path, Path] = {}
        for final, content in files.items():
            staged = temp_dir / "files" / sha256_text(str(final))
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(content)
            staged_binary[final] = staged
        for final, content in report_files.items():
            staged = temp_dir / "reports" / sha256_text(str(final))
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_text(content, encoding="utf-8")
            staged_text[final] = staged
        for final in [*files, *report_files]:
            backups[final] = _backup_path(final, temp_dir)
        for final, staged in staged_binary.items():
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, final)
            committed.append(final)
        for final, staged in staged_text.items():
            final.parent.mkdir(parents=True, exist_ok=True)
            if final.exists():
                raise FileIOError(f"report already exists: {final}")
            os.replace(staged, final)
            committed.append(final)
    except Exception as exc:
        rollback(backups, committed)
        if isinstance(exc, ParleyError):
            raise
        raise FileIOError(f"failed to commit files: {exc}") from exc
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _backup_path(path: Path, temp_dir: Path) -> Path | None:
    if not path.exists():
        return None
    backup = temp_dir / "backups" / sha256_text(str(path))
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup)
    return backup


def rollback(backups: dict[Path, Path | None], committed: list[Path]) -> None:
    for path in reversed(committed):
        backup = backups.get(path)
        if backup is None:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(backup, path)
