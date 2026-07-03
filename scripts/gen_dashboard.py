#!/usr/bin/env python3
"""
Token Usage Dashboard Generator
Generates static HTML dashboard from Hermes insights data.
Deploys to Vercel via git push.
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

DASHBOARD_DIR = Path(__file__).parent.parent
RUNS_DIR = DASHBOARD_DIR / "runs"
TEMPLATE_FILE = DASHBOARD_DIR / "templates" / "dashboard.html"
OUTPUT_FILE = DASHBOARD_DIR / "index.html"
DATA_FILE = DASHBOARD_DIR / "data" / "history.json"


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
        line = line.strip()
        if not line:
            continue

        # Period
        if "Period:" in line:
            data["period"] = line.replace("Period:", "").strip()

        # Sections
        if "Overview" in line:
            current_section = "overview"
            continue
        elif "Models Used" in line:
            current_section = "models"
            continue
        elif "Platforms" in line:
            current_section = "platforms"
            continue
        elif "Top Tools" in line:
            current_section = "tools"
            continue
        elif "Top Skills" in line:
            current_section = "skills"
            continue
        elif "Activity Patterns" in line:
            current_section = "activity"
            continue
        elif "Notable Sessions" in line:
            current_section = "notable"
            continue

        # Parse overview
        if current_section == "overview" and ":" in line and not line.startswith("─"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                val = parts[1].strip()
                data["overview"][key] = val

        # Parse models
        if current_section == "models" and line and not line.startswith("─") and not line.startswith("Model"):
            parts = line.split()
            if len(parts) >= 3:
                model = " ".join(parts[:-2])
                sessions = parts[-2]
                tokens = parts[-1]
                data["models"].append({"model": model, "sessions": sessions, "tokens": tokens})

        # Parse platforms
        if current_section == "platforms" and line and not line.startswith("─") and not line.startswith("Platform"):
            parts = line.split()
            if len(parts) >= 4:
                platform = parts[0]
                sessions = parts[1]
                messages = parts[2]
                tokens = " ".join(parts[3:])
                data["platforms"].append(
                    {"platform": platform, "sessions": sessions, "messages": messages, "tokens": tokens}
                )

        # Parse tools
        if current_section == "tools" and line and not line.startswith("─") and not line.startswith("Tool"):
            parts = line.split()
            if len(parts) >= 3:
                tool = " ".join(parts[:-2])
                calls = parts[-2]
                pct = parts[-1]
                data["tools"].append({"tool": tool, "calls": calls, "pct": pct})

        # Parse skills
        if current_section == "skills" and line and not line.startswith("─") and not line.startswith("Skill"):
            parts = line.split()
            if len(parts) >= 4:
                skill = " ".join(parts[:-3])
                loads = parts[-3]
                edits = parts[-2]
                last_used = parts[-1]
                data["skills"].append(
                    {"skill": skill, "loads": loads, "edits": edits, "last_used": last_used}
                )

        # Parse activity (days)
        if current_section == "activity" and "█" in line:
            parts = line.split("█")
            if len(parts) >= 2:
                day = parts[0].strip()
                count = parts[1].strip().split()[0] if parts[1].strip() else "0"
                data["activity"][day] = int(count)

        # Parse notable
        if current_section == "notable" and line and not line.startswith("─") and not line.startswith("Longest"):
            if "Longest" in line:
                data["notable"]["longest"] = line.replace("Longest session", "").strip()
            elif "Most messages" in line:
                data["notable"]["most_messages"] = line.replace("Most messages", "").strip()
            elif "Most tokens" in line:
                data["notable"]["most_tokens"] = line.replace("Most tokens", "").strip()
            elif "Most tool calls" in line:
                data["notable"]["most_tool_calls"] = line.replace("Most tool calls", "").strip()

    return data


def load_history() -> list[dict]:
    """Load historical data from JSON file."""
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return []


def save_history(history: list[dict]):
    """Save historical data to JSON file."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(history, f, indent=2)


def update_history(parsed: dict):
    """Add today's data to history."""
    history = load_history()

    # Extract numeric values
    def extract_num(s: str) -> int:
        return int(s.replace(",", "").replace("M", "000000").replace("K", "000"))

    today = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "period": parsed.get("period", ""),
        "sessions": extract_num(parsed.get("overview", {}).get("Sessions", "0")),
        "messages": extract_num(parsed.get("overview", {}).get("Messages", "0")),
        "tool_calls": extract_num(parsed.get("overview", {}).get("Tool calls", "0")),
        "input_tokens": extract_num(parsed.get("overview", {}).get("Input tokens", "0")),
        "output_tokens": extract_num(parsed.get("overview", {}).get("Output tokens", "0")),
        "total_tokens": extract_num(parsed.get("overview", {}).get("Total tokens", "0")),
        "active_time": parsed.get("overview", {}).get("Active time", ""),
        "platforms": parsed.get("platforms", []),
        "top_model": parsed.get("models", [{}])[0].get("model", "") if parsed.get("models") else "",
    }

    # Remove duplicate date if exists
    history = [h for h in history if h["date"] != today["date"]]
    history.append(today)

    # Keep last 90 days
    history = sorted(history, key=lambda x: x["date"])[-90:]

    save_history(history)
    return history


def generate_chart_data(history: list[dict]) -> dict:
    """Prepare data for Chart.js."""
    dates = [h["date"] for h in history]
    input_tokens = [h["input_tokens"] for h in history]
    output_tokens = [h["output_tokens"] for h in history]
    total_tokens = [h["total_tokens"] for h in history]
    sessions = [h["sessions"] for h in history]
    messages = [h["messages"] for h in history]

    # Platform breakdown (last 7 days)
    recent = history[-7:] if len(history) >= 7 else history
    cli_tokens = []
    telegram_tokens = []
    for h in recent:
        cli_t = 0
        tg_t = 0
        for p in h.get("platforms", []):
            if "cli" in p.get("platform", "").lower():
                cli_t = extract_num(p.get("tokens", "0"))
            elif "telegram" in p.get("platform", "").lower():
                tg_t = extract_num(p.get("tokens", "0"))
        cli_tokens.append(cli_t)
        telegram_tokens.append(tg_t)

    return {
        "dates": dates,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "sessions": sessions,
        "messages": messages,
        "platform_dates": [h["date"] for h in recent],
        "cli_tokens": cli_tokens,
        "telegram_tokens": telegram_tokens,
    }


def extract_num(s: str) -> int:
    """Extract number from string like '15.3M' or '72.6K'."""
    s = s.strip().upper()
    if not s or s == "N/A":
        return 0
    try:
        if s.endswith("M"):
            return int(float(s[:-1]) * 1_000_000)
        elif s.endswith("K"):
            return int(float(s[:-1]) * 1_000)
        else:
            return int(s.replace(",", ""))
    except:
        return 0


def format_num(n: int) -> str:
    """Format number with commas."""
    return f"{n:,}"


def render_dashboard(history: list[dict], chart_data: dict, latest: dict) -> str:
    """Render HTML dashboard from template."""
    with open(TEMPLATE_FILE) as f:
        template = f.read()

    # Prepare latest metrics
    latest_metrics = {
        "date": latest.get("date", "—"),
        "sessions": format_num(latest.get("sessions", 0)),
        "messages": format_num(latest.get("messages", 0)),
        "tool_calls": format_num(latest.get("tool_calls", 0)),
        "input_tokens": format_num(latest.get("input_tokens", 0)),
        "output_tokens": format_num(latest.get("output_tokens", 0)),
        "total_tokens": format_num(latest.get("total_tokens", 0)),
        "active_time": latest.get("active_time", "—"),
        "top_model": latest.get("top_model", "—"),
    }

    # Platform breakdown for latest
    cli_t = 0
    tg_t = 0
    for p in latest.get("platforms", []):
        if "cli" in p.get("platform", "").lower():
            cli_t = extract_num(p.get("tokens", "0"))
        elif "telegram" in p.get("platform", "").lower():
            tg_t = extract_num(p.get("tokens", "0"))

    platform_html = f"""
    <div class="platform-bar">
        <div class="platform-segment cli" style="width: {cli_t/(cli_t+tg_t)*100 if cli_t+tg_t else 0:.1f}%"></div>
        <div class="platform-segment telegram" style="width: {tg_t/(cli_t+tg_t)*100 if cli_t+tg_t else 0:.1f}%"></div>
    </div>
    <div class="platform-labels">
        <span class="cli">CLI: {format_num(cli_t)}</span>
        <span class="telegram">Telegram: {format_num(tg_t)}</span>
    </div>
    """

    # History table rows
    history_rows = ""
    for h in reversed(history[-30:]):  # Last 30 days
        history_rows += f"""
        <tr>
            <td>{h['date']}</td>
            <td>{format_num(h['sessions'])}</td>
            <td>{format_num(h['messages'])}</td>
            <td>{format_num(h['input_tokens'])}</td>
            <td>{format_num(h['output_tokens'])}</td>
            <td>{format_num(h['total_tokens'])}</td>
            <td>{h.get('top_model', '—')}</td>
        </tr>
        """

    # Inject data into template
    html = template.replace("{{CHART_DATA}}", json.dumps(chart_data))
    html = html.replace("{{LATEST_METRICS}}", json.dumps(latest_metrics))
    html = html.replace("{{PLATFORM_BREAKDOWN}}", platform_html)
    html = html.replace("{{HISTORY_ROWS}}", history_rows)
    html = html.replace("{{GENERATED_AT}}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    html = html.replace("{{DAYS_TRACKED}}", str(len(history)))

    return html


def main():
    print("🔍 Fetching Hermes insights...")
    output = run_insights(30)

    if output.startswith("ERROR"):
        print(f"❌ Failed: {output}")
        sys.exit(1)

    print("📊 Parsing insights...")
    parsed = parse_insights(output)

    print("📈 Updating history...")
    history = update_history(parsed)

    print("🎨 Generating chart data...")
    chart_data = generate_chart_data(history)

    print("🖥️  Rendering dashboard...")
    latest = history[-1] if history else {}
    html = render_dashboard(history, chart_data, latest)

    print(f"💾 Writing {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w") as f:
        f.write(html)

    # Also save chart data for API
    with open(DASHBOARD_DIR / "data" / "chart.json", "w") as f:
        json.dump(chart_data, f)

    print("✅ Dashboard generated successfully!")
    print(f"📁 Output: {OUTPUT_FILE}")
    print(f"📊 History entries: {len(history)}")


if __name__ == "__main__":
    main()