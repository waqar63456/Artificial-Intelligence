"""Quality modules: debugging, testing, security, browser automation, and optimization."""

from autodev.quality.auto_debugger import AutoDebugger, DebugResult
from autodev.quality.browser_agent import BrowserAgent, BrowserTestResult
from autodev.quality.error_analyzer import ErrorAnalysis, ErrorAnalyzer
from autodev.quality.optimizer import ContinuousImprover, OptimizationReport
from autodev.quality.security_checker import SecurityChecker, SecurityReport
from autodev.quality.testing_agent import TestingAgent, TestResult

__all__ = [
    "AutoDebugger",
    "DebugResult",
    "BrowserAgent",
    "BrowserTestResult",
    "ErrorAnalyzer",
    "ErrorAnalysis",
    "ContinuousImprover",
    "OptimizationReport",
    "SecurityChecker",
    "SecurityReport",
    "TestingAgent",
    "TestResult",
]
