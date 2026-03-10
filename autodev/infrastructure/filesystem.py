"""
File System Manager.
Creates and manages project folders and files automatically.
Handles creation, reading, updating, and deletion of files and directories.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger("autodev")


class FileSystemManager:
    """Manages project file system operations."""

    def __init__(self, base_dir: str) -> None:
        """
        Initialize the file system manager.

        Args:
            base_dir: The root directory for the generated project.
        """
        self.base_dir = Path(base_dir).resolve()

    def ensure_base_dir(self) -> None:
        """Create the base directory if it doesn't exist."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Ensured base directory: %s", self.base_dir)

    def create_directory(self, relative_path: str) -> Path:
        """
        Create a directory relative to the base directory.

        Args:
            relative_path: Path relative to base_dir.

        Returns:
            The absolute Path of the created directory.
        """
        dir_path = self.base_dir / relative_path
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.debug("Created directory: %s", dir_path)
        return dir_path

    def create_directories(self, paths: list[str]) -> list[Path]:
        """
        Create multiple directories.

        Args:
            paths: List of relative directory paths.

        Returns:
            List of absolute Paths created.
        """
        created = []
        for p in paths:
            created.append(self.create_directory(p))
        logger.info("Created %d directories", len(created))
        return created

    def write_file(self, relative_path: str, content: str) -> Path:
        """
        Write content to a file, creating parent directories as needed.

        Args:
            relative_path: File path relative to base_dir.
            content: File content to write.

        Returns:
            The absolute Path of the written file.
        """
        file_path = self.base_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        logger.debug("Wrote file: %s (%d bytes)", file_path, len(content))
        return file_path

    def read_file(self, relative_path: str) -> str:
        """
        Read content from a file.

        Args:
            relative_path: File path relative to base_dir.

        Returns:
            File content as string.

        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        file_path = self.base_dir / relative_path
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        return file_path.read_text(encoding="utf-8")

    def update_file(self, relative_path: str, content: str) -> Path:
        """
        Update an existing file's content (alias for write_file).

        Args:
            relative_path: File path relative to base_dir.
            content: New file content.

        Returns:
            The absolute Path of the updated file.
        """
        return self.write_file(relative_path, content)

    def append_to_file(self, relative_path: str, content: str) -> Path:
        """
        Append content to an existing file.

        Args:
            relative_path: File path relative to base_dir.
            content: Content to append.

        Returns:
            The absolute Path of the file.
        """
        file_path = self.base_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(content)
        logger.debug("Appended to file: %s", file_path)
        return file_path

    def delete_file(self, relative_path: str) -> bool:
        """
        Delete a file.

        Args:
            relative_path: File path relative to base_dir.

        Returns:
            True if file was deleted, False if it didn't exist.
        """
        file_path = self.base_dir / relative_path
        if file_path.exists():
            file_path.unlink()
            logger.debug("Deleted file: %s", file_path)
            return True
        return False

    def delete_directory(self, relative_path: str) -> bool:
        """
        Delete a directory and its contents.

        Args:
            relative_path: Directory path relative to base_dir.

        Returns:
            True if directory was deleted, False if it didn't exist.
        """
        dir_path = self.base_dir / relative_path
        if dir_path.exists():
            shutil.rmtree(dir_path)
            logger.debug("Deleted directory: %s", dir_path)
            return True
        return False

    def file_exists(self, relative_path: str) -> bool:
        """Check if a file exists."""
        return (self.base_dir / relative_path).exists()

    def list_files(self, relative_path: str = "", pattern: str = "*") -> list[str]:
        """
        List files in a directory.

        Args:
            relative_path: Directory path relative to base_dir.
            pattern: Glob pattern to filter files.

        Returns:
            List of relative file paths.
        """
        dir_path = self.base_dir / relative_path
        if not dir_path.exists():
            return []
        files = []
        for p in dir_path.rglob(pattern):
            if p.is_file():
                files.append(str(p.relative_to(self.base_dir)))
        return sorted(files)

    def get_project_tree(self, max_depth: int = 4) -> str:
        """
        Get a text representation of the project directory tree.

        Args:
            max_depth: Maximum depth to traverse.

        Returns:
            String representation of the directory tree.
        """
        lines: list[str] = []
        self._build_tree(self.base_dir, "", 0, max_depth, lines)
        return "\n".join(lines)

    def _build_tree(
        self, path: Path, prefix: str, depth: int, max_depth: int, lines: list[str]
    ) -> None:
        """Recursively build the directory tree."""
        if depth > max_depth:
            return
        entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir() and not entry.name.startswith("."):
                extension = "    " if is_last else "│   "
                self._build_tree(entry, prefix + extension, depth + 1, max_depth, lines)

    def get_absolute_path(self, relative_path: str = "") -> str:
        """Get the absolute path for a relative path."""
        return str(self.base_dir / relative_path)

    def copy_file(self, src_relative: str, dst_relative: str) -> Path:
        """
        Copy a file within the project.

        Args:
            src_relative: Source file path relative to base_dir.
            dst_relative: Destination file path relative to base_dir.

        Returns:
            The absolute Path of the destination file.
        """
        src = self.base_dir / src_relative
        dst = self.base_dir / dst_relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        logger.debug("Copied %s -> %s", src, dst)
        return dst
