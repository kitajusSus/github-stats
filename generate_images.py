#!/usr/bin/python3

import asyncio
import os
import re
import html
from pathlib import Path
from typing import Optional, Set

import aiohttp
from github_stats import Stats

# Constants
OUT_DIR = Path("generated")
TEMPLATE_DIR = Path("templates")

################################################################################
# Helper Functions
################################################################################

def str_to_bool(value: Optional[str]) -> bool:
    """Helper to cleanly parse boolean env vars."""
    if not value:
        return False
    return value.strip().lower() in ("true", "1", "yes", "on")

def safe_sub(pattern: str, replacement: str, string: str) -> str:
    """
    Safely substitutes a regex pattern with an escaped replacement 
    to prevent SVG breakage or injection.
    """
    # Escape XML/HTML special characters in the replacement string
    safe_replacement = html.escape(str(replacement))
    return re.sub(pattern, safe_replacement, string)

################################################################################
# Individual Image Generation Functions
################################################################################

async def generate_overview(s: Stats) -> None:
    """
    Generate an SVG badge with summary statistics
    """
    template_path = TEMPLATE_DIR / "overview.svg"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    with open(template_path, "r", encoding="utf-8") as f:
        output = f.read()

    # Calculate stats concurrently where possible or await sequentially
    lines_changed_data = await s.lines_changed
    total_lines = lines_changed_data[0] + lines_changed_data[1]
    
    # Use safe substitution
    output = safe_sub("{{ name }}", await s.name, output)
    output = safe_sub("{{ stars }}", f"{await s.stargazers:,}", output)
    output = safe_sub("{{ forks }}", f"{await s.forks:,}", output)
    output = safe_sub("{{ contributions }}", f"{await s.total_contributions:,}", output)
    output = safe_sub("{{ lines_changed }}", f"{total_lines:,}", output)
    output = safe_sub("{{ views }}", f"{await s.views:,}", output)
    output = safe_sub("{{ repos }}", f"{len(await s.repos):,}", output)

    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "overview.svg", "w", encoding="utf-8") as f:
        f.write(output)


async def generate_languages(s: Stats) -> None:
    """
    Generate an SVG badge with summary languages used
    """
    template_path = TEMPLATE_DIR / "languages.svg"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    with open(template_path, "r", encoding="utf-8") as f:
        output = f.read()

    progress = ""
    lang_list = ""
    
    # Fetch languages once
    langs_data = await s.languages
    sorted_languages = sorted(
        langs_data.items(), reverse=True, key=lambda t: t[1].get("size", 0)
    )
    
    delay_between = 150
    for i, (lang, data) in enumerate(sorted_languages):
        color = data.get("color", "#000000")
        prop = data.get("prop", 0)
        
        progress += (
            f'<span style="background-color: {color};'
            f'width: {prop:0.3f}%;" '
            f'class="progress-item"></span>'
        )
        
        # HTML structure for the list
        lang_list += f"""
        <li style="animation-delay: {i * delay_between}ms;">
        <svg xmlns="http://www.w3.org/2000/svg" class="octicon" style="fill:{color};"
        viewBox="0 0 16 16" version="1.1" width="16" height="16"><path
        fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8z"></path></svg>
        <span class="lang">{html.escape(lang)}</span>
        <span class="percent">{prop:0.2f}%</span>
        </li>
        """

    output = re.sub(r"{{ progress }}", progress, output) # Internal HTML, already escaped/safe
    output = re.sub(r"{{ lang_list }}", lang_list, output) # Internal HTML, already escaped/safe

    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "languages.svg", "w", encoding="utf-8") as f:
        f.write(output)

################################################################################
# Main Function
################################################################################

async def main() -> None:
    access_token = os.getenv("ACCESS_TOKEN")
    if not access_token:
        raise ValueError("Environment variable ACCESS_TOKEN is required.")
        
    user = os.getenv("GITHUB_ACTOR")
    if not user:
        raise ValueError("Environment variable GITHUB_ACTOR is required.")

    # Parsing lists
    exclude_repos_env = os.getenv("EXCLUDED")
    excluded_repos: Optional[Set[str]] = (
        {x.strip() for x in exclude_repos_env.split(",")} if exclude_repos_env else None
    )

    exclude_langs_env = os.getenv("EXCLUDED_LANGS")
    excluded_langs: Optional[Set[str]] = (
        {x.strip() for x in exclude_langs_env.split(",")} if exclude_langs_env else None
    )

    # Clean boolean parsing
    ignore_forked_repos = str_to_bool(os.getenv("EXCLUDE_FORKED_REPOS"))

    async with aiohttp.ClientSession() as session:
        s = Stats(
            user,
            access_token,
            session,
            exclude_repos=excluded_repos,
            exclude_langs=excluded_langs,
            ignore_forked_repos=ignore_forked_repos,
        )
        
        print(f"Generating stats for {user}...")
        try:
            await asyncio.gather(generate_languages(s), generate_overview(s))
            print("Generation complete.")
        except Exception as e:
            print(f"Error during generation: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(main())
