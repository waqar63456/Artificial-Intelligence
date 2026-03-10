"""
Configuration management for the autonomous development platform.
Handles LLM API keys, model selection, project defaults, and system settings.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LLMConfig:
    """Configuration for a specific LLM provider."""

    provider: str  # "openai", "deepseek", "claude"
    api_key: str = ""
    model: str = ""
    base_url: str = ""
    max_tokens: int = 4096
    temperature: float = 0.2

    def __post_init__(self) -> None:
        if not self.api_key:
            env_map = {
                "openai": "OPENAI_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
                "claude": "ANTHROPIC_API_KEY",
            }
            env_var = env_map.get(self.provider, "")
            self.api_key = os.environ.get(env_var, "")

        if not self.model:
            model_map = {
                "openai": "gpt-4o",
                "deepseek": "deepseek-coder",
                "claude": "claude-sonnet-4-20250514",
            }
            self.model = model_map.get(self.provider, "gpt-4o")

        if not self.base_url:
            url_map = {
                "openai": "https://api.openai.com/v1",
                "deepseek": "https://api.deepseek.com/v1",
                "claude": "https://api.anthropic.com",
            }
            self.base_url = url_map.get(self.provider, "")


@dataclass
class ProjectConfig:
    """Configuration for a generated project."""

    name: str = "my-project"
    output_dir: str = "./output"
    project_type: str = ""  # "web", "api", "mobile", "desktop", "microservice", "fullstack"
    tech_stack: dict[str, str] = field(default_factory=dict)
    features: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)


@dataclass
class PlatformConfig:
    """Top-level platform configuration."""

    llm: LLMConfig = field(default_factory=lambda: LLMConfig(provider="openai"))
    fallback_llms: list[LLMConfig] = field(default_factory=list)
    project: ProjectConfig = field(default_factory=ProjectConfig)
    max_debug_iterations: int = 10
    max_test_retries: int = 3
    enable_browser_testing: bool = True
    enable_security_scan: bool = True
    enable_optimization: bool = True
    log_dir: str = "./logs"
    verbose: bool = False

    @classmethod
    def from_file(cls, path: str | Path) -> PlatformConfig:
        """Load configuration from a JSON file."""
        config_path = Path(path)
        if not config_path.exists():
            return cls()
        with open(config_path) as f:
            data = json.load(f)
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> PlatformConfig:
        llm_data = data.get("llm", {})
        llm = LLMConfig(**llm_data) if llm_data else LLMConfig(provider="openai")

        fallback_data = data.get("fallback_llms", [])
        fallback_llms = [LLMConfig(**fb) for fb in fallback_data]

        project_data = data.get("project", {})
        project = ProjectConfig(**project_data) if project_data else ProjectConfig()

        return cls(
            llm=llm,
            fallback_llms=fallback_llms,
            project=project,
            max_debug_iterations=data.get("max_debug_iterations", 10),
            max_test_retries=data.get("max_test_retries", 3),
            enable_browser_testing=data.get("enable_browser_testing", True),
            enable_security_scan=data.get("enable_security_scan", True),
            enable_optimization=data.get("enable_optimization", True),
            log_dir=data.get("log_dir", "./logs"),
            verbose=data.get("verbose", False),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize configuration to a dictionary."""
        from dataclasses import asdict

        return asdict(self)

    def save(self, path: str | Path) -> None:
        """Save configuration to a JSON file."""
        config_path = Path(path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
