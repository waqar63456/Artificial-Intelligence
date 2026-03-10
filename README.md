# AutoDev - Autonomous Software Development Platform

Build complete, working software projects from a single natural language prompt. AutoDev acts as an AI software engineer that performs the entire development lifecycle autonomously — from requirements analysis through code generation, debugging, testing, and delivery.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI / Entry Point                       │
├─────────────────────────────────────────────────────────────┤
│                     Orchestrator (Workflow Engine)            │
│  Executes the 15-step pipeline from prompt to delivery       │
├──────────────┬──────────────────┬───────────────────────────┤
│   Agents     │  Infrastructure  │  Quality                   │
│              │                  │                             │
│ • Prompt     │ • File System    │ • Error Analyzer            │
│   Interpreter│   Manager        │ • Auto Debugger             │
│ • Project    │ • Dependency     │ • Testing Agent             │
│   Planner    │   Manager        │ • Security Checker          │
│ • Technology │ • Command        │ • Browser Automation        │
│   Selector   │   Executor       │ • Continuous Improvement    │
│ • Code       │ • Runtime        │                             │
│   Generator  │   Monitor        │                             │
├──────────────┴──────────────────┴───────────────────────────┤
│                     Core Layer                               │
│  • LLM Integration (OpenAI, DeepSeek, Claude)                │
│  • Configuration Management                                  │
│  • Logging & Action Tracking                                 │
└─────────────────────────────────────────────────────────────┘
```

## Workflow (15 Steps)

| Step | Name | Description |
|------|------|-------------|
| 1 | Receive Prompt | Accept the user's project description |
| 2 | Analyze Request | Extract features, requirements, constraints via LLM |
| 3 | Design Architecture | Select tech stack and design system architecture |
| 4 | Generate Structure | Plan project folder layout and file organization |
| 5 | Create Files | Create all directories and empty file placeholders |
| 6 | Generate Code | LLM-powered code generation for every project file |
| 7 | Install Dependencies | Auto-detect package manager and install all deps |
| 8 | Run Application | Start the application in the background |
| 9 | Monitor Errors | Detect runtime errors from terminal/server output |
| 10 | Auto Debug | Analyze errors and auto-fix source code |
| 11 | Browser Test | Open in headless browser, detect console/network errors |
| 12 | Debug Loop | Repeat steps 9-11 until the application runs cleanly |
| 13 | Run Tests | Generate and execute unit, API, and UI tests |
| 14 | Optimize | Security scan + code quality optimization |
| 15 | Deliver | Produce final application with run/deploy instructions |

## Installation

```bash
# Clone the repository
git clone https://github.com/autodev/auto-dev-platform.git
cd auto-dev-platform

# Install with pip
pip install -e .

# Or install dependencies directly
pip install -r requirements.txt

# Install Playwright browsers (for browser testing)
playwright install chromium
```

## Quick Start

```bash
# Set your LLM API key
export OPENAI_API_KEY="your-key-here"
# Or for other providers:
# export ANTHROPIC_API_KEY="your-key-here"
# export DEEPSEEK_API_KEY="your-key-here"

# Build a project from a prompt
autodev "Build a todo app with user authentication using React and Express"

# Use Claude instead of OpenAI
autodev --provider claude "Create a REST API for a blog with Node.js"

# Specify output directory
autodev --output ./my-projects "Build a real-time chat application"

# Interactive mode
autodev --interactive
```

## CLI Options

```
Usage: autodev [OPTIONS] PROMPT

Positional Arguments:
  prompt                    Project description prompt

LLM Configuration:
  --provider {openai,deepseek,claude}  LLM provider (default: openai)
  --model MODEL             Specific model name
  --api-key KEY             API key (default: from env var)
  --temperature FLOAT       Generation temperature (default: 0.2)

Project Configuration:
  --output, -o DIR          Output directory (default: ./output)
  --name NAME               Project name (default: auto-generated)

Workflow Configuration:
  --max-debug-iterations N  Max debug loop iterations (default: 10)
  --no-browser-test         Disable browser testing
  --no-security-scan        Disable security scanning
  --no-optimize             Disable code optimization

General:
  --config, -c FILE         JSON configuration file
  --verbose, -v             Verbose logging
  --log-dir DIR             Log directory (default: ./logs)
  --interactive, -i         Interactive prompt mode
  --version                 Show version
```

## Configuration File

Create a `config.json` for advanced configuration:

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o",
    "temperature": 0.2,
    "max_tokens": 4096
  },
  "fallback_llms": [
    {
      "provider": "claude",
      "model": "claude-sonnet-4-20250514"
    }
  ],
  "project": {
    "output_dir": "./projects"
  },
  "max_debug_iterations": 10,
  "enable_browser_testing": true,
  "enable_security_scan": true,
  "enable_optimization": true,
  "verbose": false,
  "log_dir": "./logs"
}
```

## Module Reference

### Core

| Module | Purpose |
|--------|---------|
| `core.config` | Configuration management (LLM keys, models, defaults) |
| `core.llm` | Unified LLM interface with OpenAI/DeepSeek/Claude support and automatic fallback |
| `core.logger` | Action tracking, session logging, and timed operations |

### Agents

| Module | Purpose |
|--------|---------|
| `agents.prompt_interpreter` | Analyzes user prompts to extract structured requirements |
| `agents.project_planner` | Creates development plans with architecture, files, and tasks |
| `agents.tech_selector` | Auto-selects optimal technology stacks |
| `agents.code_generator` | LLM-powered code generation with context awareness |

### Infrastructure

| Module | Purpose |
|--------|---------|
| `infrastructure.filesystem` | File/directory CRUD operations and project tree management |
| `infrastructure.dependency_manager` | Package installation via npm/pip/composer/yarn/pnpm/cargo |
| `infrastructure.command_executor` | Terminal command execution with timeout and background process support |
| `infrastructure.runtime_monitor` | Real-time error detection from terminal/build/server output |

### Quality

| Module | Purpose |
|--------|---------|
| `quality.error_analyzer` | LLM-powered root cause analysis for runtime errors |
| `quality.auto_debugger` | Automatic code fixing based on error analysis |
| `quality.testing_agent` | Test generation and execution (unit, API, UI) |
| `quality.security_checker` | Static + LLM-powered security vulnerability scanning |
| `quality.browser_agent` | Playwright-based browser testing with console/network error capture |
| `quality.optimizer` | Code quality analysis, scoring, and automatic optimization |

## Supported Project Types

- **Web Applications** — React, Vue, Angular, Svelte frontends with any backend
- **APIs** — REST and GraphQL APIs with Express, Django, FastAPI, Laravel
- **Full-Stack Platforms** — Complete frontend + backend + database applications
- **Mobile Applications** — Flutter/Dart cross-platform apps
- **Desktop Applications** — Electron-based desktop apps
- **Microservices** — Docker-containerized service architectures

## Supported Technology Stacks

| Stack | Frontend | Backend | Database |
|-------|----------|---------|----------|
| Node + React | React/TypeScript | Express/Node.js | PostgreSQL |
| Next.js | Next.js/React | Next.js API Routes | PostgreSQL |
| Django + React | React/TypeScript | Django/Python | PostgreSQL |
| Laravel + Vue | Vue.js | Laravel/PHP | MySQL |
| Flutter | Flutter/Dart | Express/Node.js | PostgreSQL |
| Electron | React + Electron | N/A | SQLite |

## Self-Improvement

AutoDev logs all agent actions, decisions, and outcomes in JSONL format under the `logs/` directory. Each session produces:

- `session_<timestamp>.jsonl` — Detailed action log with timing, inputs, outputs, and error tracking
- `autodev.log` — Human-readable execution log

This data enables analysis of:
- Common error patterns and fix strategies
- Code generation quality over time
- Technology-specific success rates
- Debug loop efficiency

## Project Structure

```
auto-dev-platform/
├── autodev/
│   ├── __init__.py              # Package init, version
│   ├── cli.py                   # CLI entry point
│   ├── orchestrator.py          # Main 15-step workflow engine
│   ├── agents/
│   │   ├── prompt_interpreter.py  # Requirement extraction
│   │   ├── project_planner.py     # Architecture & task planning
│   │   ├── tech_selector.py       # Technology stack selection
│   │   └── code_generator.py      # LLM code generation
│   ├── core/
│   │   ├── config.py              # Configuration management
│   │   ├── llm.py                 # LLM provider abstraction
│   │   └── logger.py              # Action tracking & logging
│   ├── infrastructure/
│   │   ├── filesystem.py          # File system operations
│   │   ├── dependency_manager.py  # Package management
│   │   ├── command_executor.py    # Terminal automation
│   │   └── runtime_monitor.py     # Error detection
│   ├── quality/
│   │   ├── error_analyzer.py      # Root cause analysis
│   │   ├── auto_debugger.py       # Automatic fixing
│   │   ├── testing_agent.py       # Test generation & execution
│   │   ├── security_checker.py    # Vulnerability scanning
│   │   ├── browser_agent.py       # Browser automation
│   │   └── optimizer.py           # Code optimization
│   ├── templates/                 # Project templates
│   └── utils/                     # Shared utilities
├── pyproject.toml
├── requirements.txt
└── README.md
```

## License

MIT
