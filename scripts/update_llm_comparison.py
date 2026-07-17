#!/usr/bin/env python3
"""
Fetch OpenRouter models and update llm-comparison.html table
Run weekly (Thursday 00:00) via cron
"""

import json
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

DASHBOARD_DIR = Path(__file__).parent.parent
HTML_FILE = DASHBOARD_DIR / "llm-comparison.html"

# Models we care about tracking for Hermes Agent
# Updated with ACTUAL OpenRouter model IDs as of 2026-07-15
TRACKED_MODELS = {
    # Paid - Production tier (current OpenRouter IDs)
    "openai/gpt-5.6-sol": {"tier": "paid", "role": "master, coding, reasoning"},
    "openai/gpt-5.6-sol-pro": {"tier": "paid", "role": "master, coding, reasoning"},
    "openai/gpt-5.6-terra": {"tier": "paid", "role": "coding, reasoning"},
    "openai/gpt-5.6-terra-pro": {"tier": "paid", "role": "coding, reasoning"},
    "openai/gpt-5.6-luna": {"tier": "paid", "role": "worker, fast"},
    "openai/gpt-5.6-luna-pro": {"tier": "paid", "role": "worker, fast"},
    "openai/gpt-4o": {"tier": "paid", "role": "master, coding, vision"},
    "openai/gpt-4o-mini": {"tier": "paid", "role": "worker, fast"},
    "deepseek/deepseek-v3.1-terminus": {"tier": "paid", "role": "coding, reasoning"},
    "deepseek/deepseek-v3.2": {"tier": "paid", "role": "coding, reasoning"},
    "deepseek/deepseek-v4-pro": {"tier": "paid", "role": "coding, reasoning"},
    "deepseek/deepseek-v4-flash": {"tier": "paid", "role": "worker, fast"},
    "x-ai/grok-4.5": {"tier": "paid", "role": "coding, reasoning"},
    "~x-ai/grok-latest": {"tier": "paid", "role": "coding, reasoning"},
    "nvidia/nemotron-3-ultra-550b-a55b": {"tier": "paid", "role": "reasoning"},
    "nvidia/nemotron-3-super-120b-a12b": {"tier": "paid", "role": "reasoning"},
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning": {"tier": "paid", "role": "reasoning, vision"},
    "nvidia/nemotron-3.5-content-safety": {"tier": "paid", "role": "safety"},
    "meta-llama/llama-3.1-70b-instruct": {"tier": "paid", "role": "worker, coding"},
    "mistralai/mistral-nemo": {"tier": "paid", "role": "fast, worker"},
    "google/gemma-3-27b-it": {"tier": "paid", "role": "vision, fast"},
    "google/gemma-4-26b-a4b-it": {"tier": "paid", "role": "vision, fast"},
    "google/gemma-4-31b-it": {"tier": "paid", "role": "vision, fast"},
    "nousresearch/hermes-3-llama-3.1-405b": {"tier": "paid", "role": "coding, reasoning"},
    "nousresearch/hermes-3-llama-3.1-70b": {"tier": "paid", "role": "coding, reasoning"},
    
    # Free tier - Fallback / Dev (ACTUAL OpenRouter IDs from API 2026-07-15)
    "tencent/hy3:free": {"tier": "free", "role": "reasoning"},
    "poolside/laguna-xs-2.1:free": {"tier": "free", "role": "coding"},
    "cohere/north-mini-code:free": {"tier": "free", "role": "coding"},
    "nvidia/nemotron-3.5-content-safety:free": {"tier": "free", "role": "safety"},
    "nvidia/nemotron-3-ultra-550b-a55b:free": {"tier": "free", "role": "reasoning"},
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free": {"tier": "free", "role": "reasoning, vision"},
    "poolside/laguna-m.1:free": {"tier": "free", "role": "coding"},
    "google/gemma-4-26b-a4b-it:free": {"tier": "free", "role": "vision, fast"},
    "google/gemma-4-31b-it:free": {"tier": "free", "role": "vision, fast"},
    "google/lyria-3-pro-preview": {"tier": "free", "role": "audio"},
    "google/lyria-3-clip-preview": {"tier": "free", "role": "audio"},
    "nvidia/nemotron-3-super-120b-a12b:free": {"tier": "free", "role": "reasoning"},
    "openrouter/free": {"tier": "free", "role": "auto-router"},
    "nvidia/nemotron-nano-12b-v2-vl:free": {"tier": "free", "role": "vision, fast"},
    "qwen/qwen3-next-80b-a3b-instruct:free": {"tier": "free", "role": "coding, reasoning"},
    "nvidia/nemotron-nano-9b-v2:free": {"tier": "free", "role": "fast"},
    "openai/gpt-oss-20b:free": {"tier": "free", "role": "fast, worker"},
    "qwen/qwen3-coder:free": {"tier": "free", "role": "coding"},
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free": {"tier": "free", "role": "creative"},
    "meta-llama/llama-3.3-70b-instruct:free": {"tier": "free", "role": "worker, coding"},
    "meta-llama/llama-3.2-3b-instruct:free": {"tier": "free", "role": "fast, worker"},
    "nousresearch/hermes-3-llama-3.1-405b:free": {"tier": "free", "role": "coding, reasoning"},
}


def fetch_openrouter_models():
    """Fetch all models from OpenRouter API"""
    url = "https://openrouter.ai/api/v1/models"
    req = urllib.request.Request(url, headers={'User-Agent': 'Hermes-Agent/1.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)['data']


def parse_model_data(models):
    """Parse raw API data into our tracked format"""
    result = {}
    model_by_id = {m['id']: m for m in models}
    
    for model_id, info in TRACKED_MODELS.items():
        if model_id not in model_by_id:
            print(f"⚠️  Model not found in API: {model_id}")
            continue
            
        m = model_by_id[model_id]
        pricing = m.get('pricing', {})
        arch = m.get('architecture', {})
        input_modalities = arch.get('input_modalities', [])
        reasoning = m.get('reasoning', {})
        
        result[model_id] = {
            'name': m.get('name', model_id),
            'context': m.get('context_length', 0),
            'prompt_price': float(pricing.get('prompt', 0)),
            'completion_price': float(pricing.get('completion', 0)),
            'is_free': float(pricing.get('prompt', 1)) == 0 and float(pricing.get('completion', 1)) == 0,
            'is_multimodal': 'image' in input_modalities or 'file' in input_modalities,
            'has_reasoning': reasoning.get('mandatory', False) or 'reasoning' in m.get('supported_parameters', []),
            'tool_use': 'tools' in m.get('supported_parameters', []),
            'tier': info['tier'],
            'role': info['role'],
        }
    
    return result


def format_context(ctx):
    """Format context length for display"""
    if ctx >= 1_000_000:
        return f"{ctx // 1_000_000}M"
    return f"{ctx // 1000}k"


def format_price(p):
    """Format price per 1M tokens"""
    if p == 0:
        return "Free"
    return f"${p * 1_000_000:.2f}"


def get_badge_class(tier, value, column):
    """Determine badge CSS class based on value"""
    v = value.lower()
    
    if column == 'tool_use':
        if 'forte' in v or 'strong' in v:
            return 'badge-strong'
        elif 'sim' in v or 'yes' in v:
            return 'badge-yes'
        return 'badge-no'
    elif column == 'multimodal':
        if 'sim' in v or 'yes' in v:
            return 'badge-yes'
        return 'badge-no'
    elif column == 'reasoning':
        if 'sim' in v or 'yes' in v:
            return 'badge-yes'
        elif 'parcial' in v or 'partial' in v:
            return 'badge-partial'
        return 'badge-no'
    elif column == 'coding':
        if 'forte' in v or 'strong' in v:
            return 'badge-strong'
        elif 'bom' in v or 'good' in v:
            return 'badge-yes'
        elif 'básico' in v or 'basic' in v:
            return 'badge-no'
        return 'badge-no'
    elif column == 'speed':
        if 'ultra' in v:
            return 'badge-fast'
        elif 'muito rápida' in v or 'very fast' in v:
            return 'badge-fast'
        elif 'rápida' in v or 'fast' in v:
            return 'badge-fast'
        elif 'média' in v or 'medium' in v:
            return 'badge-medium'
        elif 'lenta' in v or 'slow' in v:
            return 'badge-slow'
        elif 'muito lenta' in v or 'very slow' in v:
            return 'badge-veryslow'
        return 'badge-medium'
    elif column == 'cost':
        if 'free' in v:
            return 'cost-free'
        return ''
    return ''


def generate_table_rows(models_data):
    """Generate HTML table rows for all tracked models"""
    rows = []
    
    # Sort: paid first, then free; within each, by context desc
    paid_models = [(k, v) for k, v in models_data.items() if v['tier'] == 'paid']
    free_models = [(k, v) for k, v in models_data.items() if v['tier'] == 'free']
    
    paid_models.sort(key=lambda x: -x[1]['context'])
    free_models.sort(key=lambda x: -x[1]['context'])
    
    # Paid models
    for model_id, m in paid_models:
        ctx = format_context(m['context'])
        cost = f"${m['prompt_price']*1_000_000:.2f} / ${m['completion_price']*1_000_000:.2f}"
        
        # Determine capabilities based on model knowledge
        tool_use = "Sim / Forte" if m['tool_use'] else "Não"
        multimodal = "Sim" if m['is_multimodal'] else "Não"
        reasoning = "Sim" if m['has_reasoning'] else "Não"
        coding = "Forte" if any(x in model_id for x in ['claude-3.5-sonnet', 'gpt-4o', 'deepseek', 'grok', 'gpt-5.6-sol', 'gpt-5.6-terra']) else ("Bom" if any(x in model_id for x in ['gpt-4o-mini', 'gemini', 'minimax']) else "Básico")
        speed = "Média"
        if 'haiku' in model_id or 'mini' in model_id or 'flash' in model_id or 'luna' in model_id:
            speed = "Rápida"
        elif 'sol' in model_id or 'opus' in model_id or 'nemotron-3-ultra' in model_id or 'grok' in model_id:
            speed = "Lenta" if 'sol' in model_id or 'opus' in model_id else "Média"
        
        row = f'''                        <tr class="tier-paid" data-tier="paid">
                            <td class="model-name">{model_id}</td>
                            <td class="context">{ctx}</td>
                            <td><span class="badge {get_badge_class('paid', tool_use, 'tool_use')}">{tool_use}</span></td>
                            <td><span class="badge {get_badge_class('paid', multimodal, 'multimodal')}">{multimodal}</span></td>
                            <td><span class="badge {get_badge_class('paid', reasoning, 'reasoning')}">{reasoning}</span></td>
                            <td><span class="badge {get_badge_class('paid', coding, 'coding')}">{coding}</span></td>
                            <td class="cost">{cost}</td>
                            <td><span class="badge {get_badge_class('paid', speed, 'speed')}">{speed}</span></td>
                        </tr>'''
        rows.append(row)
    
    # Free models
    for model_id, m in free_models:
        ctx = format_context(m['context'])
        
        tool_use = "Sim" if m['tool_use'] else "Não"
        multimodal = "Sim" if m['is_multimodal'] else "Texto"
        reasoning = "Sim" if m['has_reasoning'] else ("Parcial" if any(x in model_id for x in ['nemotron', 'qwen3-235b', 'deepseek']) else "Não")
        coding = "Bom" if any(x in model_id for x in ['qwen3-235b', 'qwen3-32b', 'qwen2.5-72b', 'llama-3.1-70b', 'llama-3.3-70b', 'hermes-3-llama-3.1-405b']) else ("Básico" if any(x in model_id for x in ['llama-3.2-3b', 'gpt-oss-20b', 'gemma-4']) else "Bom")
        speed = "Lenta" if any(x in model_id for x in ['nemotron-3-ultra', 'qwen3-235b', 'hermes-3-llama-3.1-405b', 'llama-3.3-70b', 'openai/gpt-oss-120b', 'llama-3.1-70b']) else ("Rápida" if any(x in model_id for x in ['llama-3.1-8b', 'llama-3.2-3b', 'gpt-oss-20b', 'gemma-4-31b', 'mistral-nemo']) else ("Muito Rápida" if 'mistral-nemo' in model_id or 'llama-3.2-3b' in model_id else "Média"))
        
        row = f'''                        <tr class="tier-free" data-tier="free">
                            <td class="model-name">{model_id}</td>
                            <td class="context">{ctx}</td>
                            <td><span class="badge {get_badge_class('free', tool_use, 'tool_use')}">{tool_use}</span></td>
                            <td><span class="badge {get_badge_class('free', multimodal, 'multimodal')}">{multimodal}</span></td>
                            <td><span class="badge {get_badge_class('free', reasoning, 'reasoning')}">{reasoning}</span></td>
                            <td><span class="badge {get_badge_class('free', coding, 'coding')}">{coding}</span></td>
                            <td class="cost cost-free">Free</td>
                            <td><span class="badge {get_badge_class('free', speed, 'speed')}">{speed}</span></td>
                        </tr>'''
        rows.append(row)
    
    return '\n'.join(rows)


def update_html(models_data):
    """Update the llm-comparison.html file with fresh data"""
    with open(HTML_FILE, 'r') as f:
        html = f.read()
    
    # Generate new table rows
    new_rows = generate_table_rows(models_data)
    
    # Replace tbody content
    tbody_start = html.find('<tbody>')
    tbody_end = html.find('</tbody>')
    
    if tbody_start == -1 or tbody_end == -1:
        print("❌ Could not find tbody tags")
        return False
    
    new_html = html[:tbody_start + 7] + '\n' + new_rows + '\n' + html[tbody_end:]
    
    # Update the "Atualizado" date in meta
    today = datetime.now().strftime("%B %Y")
    new_html = re.sub(r'📅 Atualizado: [^<]+', f'📅 Atualizado: {today}', new_html)
    
    # Update filter tab counts
    paid_count = sum(1 for m in models_data.values() if m['tier'] == 'paid')
    free_count = sum(1 for m in models_data.values() if m['tier'] == 'free')
    total_count = paid_count + free_count
    
    new_html = re.sub(r'Todos \(\d+\)', f'Todos ({total_count})', new_html)
    new_html = re.sub(r'Pagos \(\d+\)', f'Pagos ({paid_count})', new_html)
    new_html = re.sub(r'Free Tier \(\d+\)', f'Free Tier ({free_count})', new_html)
    
    with open(HTML_FILE, 'w') as f:
        f.write(new_html)
    
    print(f"✅ Updated {HTML_FILE}")
    print(f"   Total: {total_count} (Paid: {paid_count}, Free: {free_count})")
    print(f"   Date updated to: {today}")
    return True


def deploy():
    """Deploy to Vercel via git push"""
    import subprocess
    result = subprocess.run(['git', 'add', 'llm-comparison.html'], cwd=DASHBOARD_DIR, capture_output=True, text=True)
    result = subprocess.run(['git', 'commit', '-m', f'chore: update LLM comparison table ({datetime.now().strftime("%Y-%m-%d")})'], cwd=DASHBOARD_DIR, capture_output=True, text=True)
    result = subprocess.run(['git', 'push'], cwd=DASHBOARD_DIR, capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ Deployed to Vercel via git push")
    else:
        print(f"⚠️  Git push failed: {result.stderr}")


def main():
    print("🔄 Fetching OpenRouter models...")
    try:
        models = fetch_openrouter_models()
        print(f"   Fetched {len(models)} models from API")
    except Exception as e:
        print(f"❌ Failed to fetch models: {e}")
        sys.exit(1)
    
    print("📊 Parsing tracked models...")
    models_data = parse_model_data(models)
    print(f"   Tracked: {len(models_data)} models")
    
    print("📝 Updating HTML table...")
    update_html(models_data)
    
    print("🚀 Deploying...")
    deploy()
    
    print("✅ Done!")


if __name__ == "__main__":
    main()