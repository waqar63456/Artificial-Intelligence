"""
Security Checker Agent.
Scans generated code for common vulnerabilities such as
SQL injection, XSS, authentication flaws, and other OWASP Top 10 risks.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from autodev.core.llm import LLMManager
from autodev.infrastructure.filesystem import FileSystemManager

logger = logging.getLogger("autodev")


class VulnerabilitySeverity(Enum):
    """Severity levels for security vulnerabilities."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Vulnerability:
    """A detected security vulnerability."""

    title: str
    description: str
    severity: VulnerabilitySeverity
    file_path: str
    line_number: int = 0
    category: str = ""  # "sql_injection", "xss", "auth", "secrets", etc.
    recommendation: str = ""
    cwe_id: str = ""


@dataclass
class SecurityReport:
    """Complete security scan report."""

    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    files_scanned: int = 0
    scan_duration_seconds: float = 0.0

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.severity == VulnerabilitySeverity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.severity == VulnerabilitySeverity.HIGH)

    @property
    def has_critical_issues(self) -> bool:
        return self.critical_count > 0

    def summary(self) -> str:
        counts = {s.value: 0 for s in VulnerabilitySeverity}
        for v in self.vulnerabilities:
            counts[v.severity.value] += 1
        return (
            f"Security Scan: {len(self.vulnerabilities)} issues found "
            f"(critical={counts['critical']}, high={counts['high']}, "
            f"medium={counts['medium']}, low={counts['low']})"
        )


# Static analysis patterns for common vulnerabilities
VULN_PATTERNS: list[tuple[str, str, VulnerabilitySeverity, str, str]] = [
    # SQL Injection
    (
        r'(?:query|execute|raw)\s*\(\s*["\'].*?\+|(?:query|execute|raw)\s*\(\s*f["\']',
        "Potential SQL Injection",
        VulnerabilitySeverity.CRITICAL,
        "sql_injection",
        "Use parameterized queries or an ORM instead of string concatenation.",
    ),
    (
        r'\$\{.*?\}.*?(?:SELECT|INSERT|UPDATE|DELETE|DROP)',
        "SQL Injection via template literal",
        VulnerabilitySeverity.CRITICAL,
        "sql_injection",
        "Use parameterized queries instead of template literals in SQL.",
    ),
    # XSS
    (
        r'innerHTML\s*=|dangerouslySetInnerHTML|v-html\s*=',
        "Potential XSS vulnerability",
        VulnerabilitySeverity.HIGH,
        "xss",
        "Sanitize user input before rendering as HTML. Use textContent or proper escaping.",
    ),
    (
        r'document\.write\s*\(',
        "Potential XSS via document.write",
        VulnerabilitySeverity.HIGH,
        "xss",
        "Avoid document.write. Use DOM manipulation methods instead.",
    ),
    # Hardcoded Secrets
    (
        r'(?:password|secret|api_key|apikey|token|auth)\s*=\s*["\'][^"\']{8,}["\']',
        "Hardcoded secret/credential detected",
        VulnerabilitySeverity.CRITICAL,
        "secrets",
        "Move secrets to environment variables. Never hardcode credentials.",
    ),
    (
        r'(?:AKIA|ASIA)[A-Z0-9]{16}',
        "AWS Access Key ID detected",
        VulnerabilitySeverity.CRITICAL,
        "secrets",
        "Remove AWS credentials from code. Use IAM roles or environment variables.",
    ),
    # Authentication Issues
    (
        r'(?:jwt|token).*?(?:verify|validate)\s*=\s*false',
        "JWT/Token verification disabled",
        VulnerabilitySeverity.CRITICAL,
        "auth",
        "Always verify tokens. Never disable signature verification.",
    ),
    (
        r'(?:cors|CORS).*?\*',
        "Overly permissive CORS configuration",
        VulnerabilitySeverity.MEDIUM,
        "auth",
        "Restrict CORS to specific allowed origins instead of wildcard.",
    ),
    # Insecure Communication
    (
        r'http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)',
        "Insecure HTTP URL (non-localhost)",
        VulnerabilitySeverity.MEDIUM,
        "transport",
        "Use HTTPS for all external communications.",
    ),
    # Path Traversal
    (
        r'(?:readFile|writeFile|open)\s*\(\s*(?:req\.|request\.|params\.|query\.)',
        "Potential path traversal vulnerability",
        VulnerabilitySeverity.HIGH,
        "path_traversal",
        "Validate and sanitize file paths from user input. Use path.resolve and verify against allowed directories.",
    ),
    # Command Injection
    (
        r'(?:exec|spawn|system|popen)\s*\(\s*(?:req\.|request\.|params\.|query\.|.*?\+)',
        "Potential command injection",
        VulnerabilitySeverity.CRITICAL,
        "command_injection",
        "Never pass unsanitized user input to system commands. Use parameterized command execution.",
    ),
    # Insecure Randomness
    (
        r'Math\.random\s*\(\s*\).*?(?:token|secret|password|key|session|auth)',
        "Insecure randomness for security-sensitive operation",
        VulnerabilitySeverity.HIGH,
        "crypto",
        "Use crypto.randomBytes() or crypto.getRandomValues() for security-sensitive random values.",
    ),
    # Eval usage
    (
        r'(?<!\.)\beval\s*\(',
        "Use of eval() detected",
        VulnerabilitySeverity.HIGH,
        "code_injection",
        "Avoid eval(). It can lead to code injection vulnerabilities.",
    ),
]

# File extensions to scan
SCANNABLE_EXTENSIONS = {
    ".js", ".ts", ".jsx", ".tsx", ".py", ".php", ".rb",
    ".java", ".go", ".rs", ".vue", ".svelte", ".dart",
}

# Files to skip
SKIP_PATTERNS = {
    "node_modules", ".git", "vendor", "__pycache__",
    "dist", "build", ".next", "coverage",
}


class SecurityChecker:
    """Scans code for security vulnerabilities."""

    def __init__(self, llm: LLMManager, fs: FileSystemManager) -> None:
        self.llm = llm
        self.fs = fs
        self._compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE | re.MULTILINE), *rest)
            for pattern, *rest in VULN_PATTERNS
        ]

    async def scan(self, tech_stack: dict[str, Any] | None = None) -> SecurityReport:
        """
        Perform a security scan on the entire project.

        Args:
            tech_stack: Technology stack for context-aware scanning.

        Returns:
            SecurityReport with all found vulnerabilities.
        """
        import time

        start = time.time()
        logger.info("Starting security scan...")

        all_files = self.fs.list_files()
        scannable_files = [
            f for f in all_files
            if self._should_scan(f)
        ]

        logger.info("Scanning %d files for vulnerabilities", len(scannable_files))

        all_vulns: list[Vulnerability] = []
        for file_path in scannable_files:
            try:
                content = self.fs.read_file(file_path)
                vulns = self._scan_file(file_path, content)
                all_vulns.extend(vulns)
            except Exception as e:
                logger.warning("Error scanning %s: %s", file_path, str(e))

        duration = time.time() - start
        report = SecurityReport(
            vulnerabilities=all_vulns,
            files_scanned=len(scannable_files),
            scan_duration_seconds=duration,
        )

        logger.info(report.summary())
        return report

    async def scan_file(
        self,
        file_path: str,
        deep_scan: bool = False,
        tech_stack: dict[str, Any] | None = None,
    ) -> list[Vulnerability]:
        """
        Scan a single file for vulnerabilities.

        Args:
            file_path: Path to the file to scan.
            deep_scan: If True, also use LLM for deeper analysis.
            tech_stack: Technology stack for context.

        Returns:
            List of vulnerabilities found.
        """
        try:
            content = self.fs.read_file(file_path)
        except FileNotFoundError:
            return []

        vulns = self._scan_file(file_path, content)

        if deep_scan and tech_stack:
            llm_vulns = await self._deep_scan_with_llm(file_path, content, tech_stack)
            vulns.extend(llm_vulns)

        return vulns

    def _scan_file(self, file_path: str, content: str) -> list[Vulnerability]:
        """Perform static pattern-based scanning on a file."""
        vulns: list[Vulnerability] = []
        lines = content.split("\n")

        for compiled_pattern, title, severity, category, recommendation in self._compiled_patterns:
            for i, line in enumerate(lines, 1):
                if compiled_pattern.search(line):
                    # Skip if in a comment
                    stripped = line.strip()
                    if stripped.startswith("//") or stripped.startswith("#") or stripped.startswith("*"):
                        continue

                    vulns.append(Vulnerability(
                        title=title,
                        description=f"Found in: {line.strip()[:100]}",
                        severity=severity,
                        file_path=file_path,
                        line_number=i,
                        category=category,
                        recommendation=recommendation,
                    ))

        return vulns

    async def _deep_scan_with_llm(
        self,
        file_path: str,
        content: str,
        tech_stack: dict[str, Any],
    ) -> list[Vulnerability]:
        """Use LLM for deeper security analysis."""
        prompt = f"""Analyze this code for security vulnerabilities.

File: {file_path}
Tech Stack: {tech_stack}

Code:
```
{content[:4000]}
```

Return a JSON array of vulnerabilities found:
[
    {{
        "title": "string",
        "description": "string",
        "severity": "low|medium|high|critical",
        "line_number": 0,
        "category": "string",
        "recommendation": "string"
    }}
]

If no vulnerabilities are found, return an empty array: []
Return ONLY valid JSON."""

        response = await self.llm.generate_structured(prompt=prompt)
        data = response.as_json()

        if data is None or not isinstance(data, list):
            return []

        vulns = []
        for item in data:
            severity_str = item.get("severity", "medium").lower()
            severity_map = {
                "low": VulnerabilitySeverity.LOW,
                "medium": VulnerabilitySeverity.MEDIUM,
                "high": VulnerabilitySeverity.HIGH,
                "critical": VulnerabilitySeverity.CRITICAL,
            }
            vulns.append(Vulnerability(
                title=item.get("title", ""),
                description=item.get("description", ""),
                severity=severity_map.get(severity_str, VulnerabilitySeverity.MEDIUM),
                file_path=file_path,
                line_number=item.get("line_number", 0),
                category=item.get("category", ""),
                recommendation=item.get("recommendation", ""),
            ))

        return vulns

    def _should_scan(self, file_path: str) -> bool:
        """Check if a file should be scanned."""
        # Check extension
        ext = ""
        if "." in file_path:
            ext = "." + file_path.rsplit(".", 1)[-1]
        if ext not in SCANNABLE_EXTENSIONS:
            return False

        # Check skip patterns
        for skip in SKIP_PATTERNS:
            if skip in file_path:
                return False

        return True
