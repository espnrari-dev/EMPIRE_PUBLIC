#!/usr/bin/env python3
import json, os, subprocess, sys, shutil
from datetime import datetime

# Path to your secret architecture spec (JSON)
SPEC_PATH = os.path.expanduser("~/deep_recon/shogun_blueprint.json")
HIDDEN_DIR = os.path.expanduser("~/deep_recon/.shogun_intel")

def load_spec():
    if not os.path.exists(SPEC_PATH):
        print(f"Spec file not found: {SPEC_PATH}")
        sys.exit(1)
    with open(SPEC_PATH) as f:
        return json.load(f)

def forge_tool(name, tool_type, desc, action, hidden=True):
    """Use FORGE.py to create a tool, then move it to hidden dir."""
    forge_cmd = [
        "python", "FORGE.py",
        "--name", name,
        "--type", tool_type,
        "--desc", desc,
        "--action", action
    ]
    subprocess.run(forge_cmd, cwd=os.path.dirname(SPEC_PATH))
    # Move forged file to hidden directory
    src = os.path.join(os.path.dirname(SPEC_PATH), f"{name}.{tool_type}")
    if os.path.exists(src):
        os.makedirs(HIDDEN_DIR, exist_ok=True)
        shutil.move(src, os.path.join(HIDDEN_DIR, f"{name}.{tool_type}"))
        return True
    return False

def main():
    spec = load_spec()
    print(f"🔮 BLUEPRINT FORGE ACTIVE – {len(spec.get('tools', []))} tools in blueprint")
    for tool in spec.get("tools", []):
        name = tool["name"]
        tool_type = tool.get("type", "sh")
        desc = tool.get("desc", "Forged from blueprint")
        action = tool["action"]
        success = forge_tool(name, tool_type, desc, action)
        if success:
            print(f"  ✓ {name} hidden in {HIDDEN_DIR}")
        else:
            print(f"  ✗ Failed to forge {name}")
    # Write a codeword manifest
    manifest = {
        "forged_at": datetime.now().isoformat(),
        "codeword": "SHOW_EMPIRE",
        "tools": [t["name"] for t in spec["tools"]]
    }
    with open(os.path.join(HIDDEN_DIR, ".manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nAll tools hidden. Say the codeword 'SHOW_EMPIRE' to reveal them.")

if __name__ == "__main__":
    main()
