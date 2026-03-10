"""
Dependency Manager.
Automatically installs all required dependencies using appropriate package managers.
Supports npm, yarn, pnpm, pip, composer, pub, cargo, and Docker.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from autodev.infrastructure.command_executor import CommandExecutor

logger = logging.getLogger("autodev")


@dataclass
class DependencyInstallResult:
    """Result of a dependency installation."""

    success: bool
    package_manager: str
    installed_count: int
    output: str
    errors: list[str]


# Map of package manager detection files
PACKAGE_MANAGER_FILES = {
    "npm": "package.json",
    "yarn": "yarn.lock",
    "pnpm": "pnpm-lock.yaml",
    "pip": "requirements.txt",
    "poetry": "pyproject.toml",
    "composer": "composer.json",
    "pub": "pubspec.yaml",
    "cargo": "Cargo.toml",
}

# Install commands for each package manager
INSTALL_COMMANDS: dict[str, list[str]] = {
    "npm": ["npm", "install"],
    "yarn": ["yarn", "install"],
    "pnpm": ["pnpm", "install"],
    "pip": ["pip", "install", "-r", "requirements.txt"],
    "poetry": ["poetry", "install"],
    "composer": ["composer", "install"],
    "pub": ["flutter", "pub", "get"],
    "cargo": ["cargo", "build"],
}

# Commands to add individual packages
ADD_COMMANDS: dict[str, list[str]] = {
    "npm": ["npm", "install"],
    "yarn": ["yarn", "add"],
    "pnpm": ["pnpm", "add"],
    "pip": ["pip", "install"],
    "poetry": ["poetry", "add"],
    "composer": ["composer", "require"],
}

# Commands to add dev dependencies
ADD_DEV_COMMANDS: dict[str, list[str]] = {
    "npm": ["npm", "install", "--save-dev"],
    "yarn": ["yarn", "add", "--dev"],
    "pnpm": ["pnpm", "add", "--save-dev"],
    "pip": ["pip", "install"],
    "poetry": ["poetry", "add", "--group", "dev"],
    "composer": ["composer", "require", "--dev"],
}


class DependencyManager:
    """Manages project dependency installation."""

    def __init__(self, executor: CommandExecutor, project_dir: str) -> None:
        """
        Initialize the dependency manager.

        Args:
            executor: Command executor for running install commands.
            project_dir: Root directory of the project.
        """
        self.executor = executor
        self.project_dir = project_dir

    def detect_package_manager(self) -> str | None:
        """
        Detect the package manager based on project files.

        Returns:
            Name of the detected package manager, or None.
        """
        import os

        # Check for lock files first (more specific)
        lock_file_map = {
            "yarn.lock": "yarn",
            "pnpm-lock.yaml": "pnpm",
            "package-lock.json": "npm",
            "poetry.lock": "poetry",
            "Pipfile.lock": "pip",
            "composer.lock": "composer",
            "pubspec.lock": "pub",
            "Cargo.lock": "cargo",
        }
        for lock_file, manager in lock_file_map.items():
            if os.path.exists(os.path.join(self.project_dir, lock_file)):
                logger.info("Detected package manager from lock file: %s", manager)
                return manager

        # Fall back to config files
        for manager, config_file in PACKAGE_MANAGER_FILES.items():
            if os.path.exists(os.path.join(self.project_dir, config_file)):
                logger.info("Detected package manager from config: %s", manager)
                return manager

        return None

    async def install_all(self, package_manager: str | None = None) -> DependencyInstallResult:
        """
        Install all project dependencies.

        Args:
            package_manager: Specific package manager to use. Auto-detected if None.

        Returns:
            DependencyInstallResult with installation details.
        """
        pm = package_manager or self.detect_package_manager()
        if pm is None:
            return DependencyInstallResult(
                success=False,
                package_manager="unknown",
                installed_count=0,
                output="",
                errors=["Could not detect package manager"],
            )

        logger.info("Installing dependencies with: %s", pm)
        cmd = INSTALL_COMMANDS.get(pm)
        if cmd is None:
            return DependencyInstallResult(
                success=False,
                package_manager=pm,
                installed_count=0,
                output="",
                errors=[f"No install command for: {pm}"],
            )

        result = await self.executor.run(
            cmd,
            cwd=self.project_dir,
            timeout=300,
        )

        errors = []
        if not result.success:
            errors.append(result.stderr or f"Install failed with code {result.return_code}")

        return DependencyInstallResult(
            success=result.success,
            package_manager=pm,
            installed_count=0,  # Could parse output to count
            output=result.stdout,
            errors=errors,
        )

    async def add_packages(
        self,
        packages: list[str],
        dev: bool = False,
        package_manager: str | None = None,
    ) -> DependencyInstallResult:
        """
        Add specific packages.

        Args:
            packages: List of package names to install.
            dev: Whether these are dev dependencies.
            package_manager: Package manager to use. Auto-detected if None.

        Returns:
            DependencyInstallResult.
        """
        pm = package_manager or self.detect_package_manager()
        if pm is None:
            return DependencyInstallResult(
                success=False,
                package_manager="unknown",
                installed_count=0,
                output="",
                errors=["Could not detect package manager"],
            )

        cmd_base = (ADD_DEV_COMMANDS if dev else ADD_COMMANDS).get(pm)
        if cmd_base is None:
            return DependencyInstallResult(
                success=False,
                package_manager=pm,
                installed_count=0,
                output="",
                errors=[f"No add command for: {pm}"],
            )

        cmd = cmd_base + packages
        logger.info("Adding packages with %s: %s", pm, ", ".join(packages))

        result = await self.executor.run(
            cmd,
            cwd=self.project_dir,
            timeout=300,
        )

        errors = []
        if not result.success:
            errors.append(result.stderr or f"Package add failed with code {result.return_code}")

        return DependencyInstallResult(
            success=result.success,
            package_manager=pm,
            installed_count=len(packages) if result.success else 0,
            output=result.stdout,
            errors=errors,
        )

    async def install_docker_deps(self) -> DependencyInstallResult:
        """
        Build Docker containers for the project.

        Returns:
            DependencyInstallResult for Docker build.
        """
        import os

        compose_file = os.path.join(self.project_dir, "docker-compose.yml")
        dockerfile = os.path.join(self.project_dir, "Dockerfile")

        if os.path.exists(compose_file):
            cmd = ["docker", "compose", "build"]
        elif os.path.exists(dockerfile):
            cmd = ["docker", "build", "-t", "autodev-project", "."]
        else:
            return DependencyInstallResult(
                success=False,
                package_manager="docker",
                installed_count=0,
                output="",
                errors=["No Dockerfile or docker-compose.yml found"],
            )

        logger.info("Building Docker containers...")
        result = await self.executor.run(
            cmd,
            cwd=self.project_dir,
            timeout=600,
        )

        return DependencyInstallResult(
            success=result.success,
            package_manager="docker",
            installed_count=1 if result.success else 0,
            output=result.stdout,
            errors=[result.stderr] if not result.success and result.stderr else [],
        )
