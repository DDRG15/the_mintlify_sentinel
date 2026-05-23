import os
import json
from jinja2 import Environment, FileSystemLoader

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(SCRIPT_DIR, "..", "templates")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "output")
BASELINE_PATH = os.path.join(SCRIPT_DIR, "..", "input", "admin-openapi.json")
TARGET_PATH = os.path.join(SCRIPT_DIR, "..", "input", "analytics.openapi.json")

def render_changelog(broken_contracts):
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("changelog.mdx.jinja")
    rendered_mdx = template.render(changes=broken_contracts)
    output_file = os.path.join(OUTPUT_DIR, "changelog.mdx")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(rendered_mdx)

    if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
        raise RuntimeError(
            f"[architect] Changelog write failed — output file is missing or empty: {output_file}"
        )

    print(f"[architect] SUCCESS: Rendered changelog saved to {output_file}")

if __name__ == "__main__":
    from judge_diff import run_diff
    print("[architect] Retrieving payload from Judge...")
    payload = run_diff(BASELINE_PATH, TARGET_PATH)
    print("[architect] Rendering MDX artifact...")
    render_changelog(payload)