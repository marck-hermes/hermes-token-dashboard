#!/usr/bin/env python3
"""
Token Usage Dashboard Generator
Generates static HTML dashboard from Hermes insights data.
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

DASHBOARD_DIR = Path(__file__).parent.parent
DATA_FILE = DASHBOARD_DIR / "data" / "history.json"
TEMPLATE_FILE = DASHBOARD_DIR / "templates" / "dashboard.html"
OUTPUT_FILE = DASHBOARD_DIR / "index.html"

# Regex patterns for parsing insights output
OVERVIEW_PAIR_PATTERN = re.compile(r'([A-Za-z\s/]+):\s+([\d,]+)')
MODEL_PATTERN = re.compile(r"^\s+(.+?)\s+(\d+)\s+([\d,]+)$")
PLATFORM_PATTERN = re.compile(r"^\s+(\S+)\s+(\d+)\s+(\d+)\s+([\d,]+)$")
ACTIVITY_PATTERN = re.compile(r"^\s*(\w+)\s+█+.*?(\d+)$")
PERIOD_PATTERN = re.compile(r"Period:\s*(.+)")


def ensure_dirs():
    """Create required directories."""
    (DASHBOARD_DIR / "data").mkdir(parents=True, exist_ok=True)
    (DASHBOARD_DIR / "runs").mkdir(parents=True, exist_ok=True)


def run_insights(days: int = 30) -> str:
    """Run hermes insights and return output."""
    try:
        result = subprocess.run(
            ["hermes", "insights", "--days", str(days)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        return "ERROR: Timeout"
    except Exception as e:
        return f"ERROR: {e}"


def extract_overview_pairs(text: str) -> dict:
    """Extract all key:value pairs from overview section lines."""
    results = {}
    for match in OVERVIEW_PAIR_PATTERN.finditer(text):
        key = match.group(1).strip()
        val = match.group(2).strip()
        results[key] = val
    return results


def parse_insights(output: str) -> dict[str, Any]:
    """Parse hermes insights output into structured data."""
    data = {
        "period": "",
        "overview": {},
        "models": [],
        "platforms": [],
        "tools": [],
        "skills": [],
        "activity": {},
        "notable": {},
    }

    lines = output.split("\n")
    current_section = ""

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Skip box drawing lines
        if any(c in stripped for c in "╔════════════════════════════════════════════════════════════════════════════════════╗"):
            continue
        if stripped.startswith("║") or stripped.startswith("╚"):
            continue

        # Period
        if match := PERIOD_PATTERN.match(stripped):
            data["period"] = match.group(1).strip()
            continue

        # Section headers
        if "Overview" in stripped:
            current_section = "overview"
            continue
        elif "Models Used" in stripped:
            current_section = "models"
            continue
        elif "Platforms" in stripped:
            current_section = "platforms"
            continue
        elif "Top Tools" in stripped:
            current_section = "tools"
            continue
        elif "Top Skills" in stripped:
            current_section = "skills"
            continue
        elif "Activity Patterns" in stripped:
            current_section = "activity"
            continue
        elif "Notable Sessions" in stripped:
            current_section = "notable"
            continue

        # Skip divider/icon lines
        if stripped.startswith("───") or \
           any(stripped.startswith(icon) for icon in ["📋", "🤖", "📱", "🔧", "🧠", "📅", "🏆"]):
            if current_section == "notable":
                pass
            else:
                continue

        if current_section == "overview":
            pairs = extract_overview_pairs(line)
            data["overview"].update(pairs)
            continue

        elif current_section == "models":
            if match := MODEL_PATTERN.match(line):
                model = match.group(1).strip()
                sessions = match.group(2)
                tokens = match.group(3)
                if model.lower() != "model":
                    data["models"].append({"model": model, "sessions": sessions, "tokens": tokens})

        elif current_section == "platforms":
            if match := PLATFORM_PATTERN.match(line):
                platform = match.group(1)
                sessions = match.group(2)
                messages = match.group(3)
                tokens = match.group(4)
                if platform.lower() != "platform":
                    data["platforms"].append(
                        {"platform": platform, "sessions": sessions, "messages": messages, "tokens": tokens}
                    )

        elif current_section == "activity":
            if match := ACTIVITY_PATTERN.match(line):
                day = match.group(1)
                count = int(match.group(2))
                data["activity"][day] = count

        elif current_section == "notable" and stripped:
            data["notable"]["raw"] = data["notable"].get("raw", "") + stripped + "\n"

    return data


def load_history() -> list[dict]:
    """Load historical data from JSON file."""
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE) as f:
                return json.load(f)
        except:
            pass
    return []


def save_history(history: list[dict]):
    """Save historical data to JSON file."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(history, f, indent=2)


def parse_num(s: str) -> int:
    """Parse number from string like '18,773,030'."""
    try:
        return int(s.replace(",", ""))
    except:
        return 0


def extract_metrics(parsed: dict) -> dict:
    """Extract key metrics from parsed insights."""
    ov = parsed.get("overview", {})

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "period": parsed.get("period", ""),
        "sessions": parse_num(ov.get("Sessions", "0")),
        "messages": parse_num(ov.get("Messages", "0")),
        "tool_calls": parse_num(ov.get("Tool calls", "0")),
        "user_messages": parse_num(ov.get("User messages", "0")),
        "input_tokens": parse_num(ov.get("Input tokens", "0")),
        "output_tokens": parse_num(ov.get("Output tokens", "0")),
        "total_tokens": parse_num(ov.get("Total tokens", "0")),
        "active_time": ov.get("Active time", ""),
        "avg_session": ov.get("Avg session", ""),
        "avg_msgs_session": parse_num(ov.get("Avg msgs/session", "0")),
        "top_model": parsed.get("models", [{}])[0].get("model", "unknown"),
        "platforms": parsed.get("platforms", []),
        "notable": parsed.get("notable", {}),
    }


def update_history(new_metrics: dict):
    """Update history with today's metrics."""
    history = load_history()
    today = datetime.now().strftime("%Y-%m-%d")

    history = [h for h in history if h.get("date") != today]
    history.append(new_metrics)
    history.sort(key=lambda x: x["date"])

    cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    history = [h for h in history if h["date"] >= cutoff]

    save_history(history)


def prepare_chart_data(history: list[dict]) -> dict:
    """Prepare data for Chart.js."""
    if not history:
        return {
            "dates": [],
            "input_tokens": [],
            "output_tokens": [],
            "total_tokens": [],
            "sessions": [],
            "messages": [],
            "platform_dates": [],
            "cli_tokens": [],
            "telegram_tokens": [],
        }

    dates = [h["date"] for h in history]
    input_tokens = [h["input_tokens"] for h in history]
    output_tokens = [h["output_tokens"] for h in history]
    total_tokens = [h["total_tokens"] for h in history]
    sessions = [h["sessions"] for h in history]
    messages = [h["messages"] for h in history]

    platform_dates = dates[-7:]
    cli_tokens = []
    telegram_tokens = []

    for h in history[-7:]:
        cli_t = 0
        tg_t = 0
        for p in h.get("platforms", []):
            if "cli" in p.get("platform", "").lower():
                cli_t = parse_num(p.get("tokens", "0"))
            elif "telegram" in p.get("platform", "").lower():
                tg_t = parse_num(p.get("tokens", "0"))
        cli_tokens.append(cli_t)
        telegram_tokens.append(tg_t)

    return {
        "dates": dates,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "sessions": sessions,
        "messages": messages,
        "platform_dates": platform_dates,
        "cli_tokens": cli_tokens,
        "telegram_tokens": telegram_tokens,
    }


def render_template(history: list[dict], chart_data: dict, latest: dict) -> str:
    """Render HTML template with data."""
    with open(TEMPLATE_FILE) as f:
        template = f.read()

    # Generate history rows (last 30 days)
    rows = []
    for h in reversed(history[-30:]):
        rows.append(f"""
            <div class="table-row">
                <div class="date">{h['date']}</div>
                <div class="muted">{h['sessions']:,}</div>
                <div class="muted">{h['messages']:,}</div>
                <div class="muted">{h['input_tokens']:,}</div>
                <div class="muted">{h['output_tokens']:,}</div>
                <div class="muted">{h['total_tokens']:,}</div>
                <div class="muted"><code>{h['top_model']}</code></div>
            </div>
        """)

    # Platform breakdown
    platform_html = ""
    for p in latest.get("platforms", []):
        platform_html += f'<div class="platform-item"><span class="platform-name">{p["platform"]}</span><span class="platform-tokens">{p["tokens"]}</span></div>'
    if not platform_html:
        platform_html = '<div class="platform-item"><span class="platform-name">CLI</span><span class="platform-tokens">—</span></div><div class="platform-item"><span class="platform-name">Telegram</span><span class="platform-tokens">—</span></div>'

    # Replace placeholders
    template = template.replace("{{GENERATED_AT}}", datetime.now().strftime("%Y-%m-%d %H:%M"))
    template = template.replace("{{DAYS_TRACKED}}", str(len(history)))
    template = template.replace("{{PLATFORM_BREAKDOWN}}", platform_html)
    template = template.replace("{{HISTORY_ROWS}}", "\n".join(rows))
    template = template.replace("{{CHART_DATA}}", json.dumps(chart_data))
    template = template.replace("{{LATEST_METRICS}}", json.dumps(latest))

    return template


def main():
    print("🔄 Generating token usage dashboard...")

    ensure_dirs()

    # Run insights for 1 day (most recent)
    output = run_insights(1)
    if output.startswith("ERROR"):
        print(f"❌ Failed: {output}")
        sys.exit(1)

    # Parse
    print("📊 Parsing insights...")
    parsed = parse_insights(output)

    # Extract metrics
    latest = extract_metrics(parsed)

    # Update history
    print("📈 Updating history...")
    update_history(latest)

    # Load full history
    history = load_history()

    # Prepare chart data
    chart_data = prepare_chart_data(history)

    # Render HTML
    print("🖥️  Rendering dashboard...")
    html = render_template(history, chart_data, latest)

    # Write output
    with open(OUTPUT_FILE, "w") as f:
        f.write(html)

    # Also save chart data as JSON for API
    with open(DASHBOARD_DIR / "data" / "chart.json", "w") as f:
        json.dump(chart_data, f)

    print(f"✅ Dashboard generated: {OUTPUT_FILE}")
    print(f"📊 History entries: {len(history)}")
    print(f"📅 Period: {parsed.get('period', 'unknown')}")
    print(f"🤖 Top model: {latest['top_model']}")
    print(f"📈 Today: {latest['sessions']} sessions, {latest['total_tokens']:,} tokens")


if __name__ == "__main__":
    main()