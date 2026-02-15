#!/usr/bin/env python3
"""
Skill Bootstrap Template
Use this to create new skills following the SOP.

USAGE:
    python3 skills/system/skill-bootstrap/create.py --name "my-skill" --category "crypto"

OUTPUT:
    skills/{category}/my-skill/
    ├── README.md      # Skill documentation (REQUIRED)
    ├── main.py        # Entry point script
    ├── config.yaml    # Default configuration
    └── test.py        # Unit tests
"""

import os
import sys
import argparse
from datetime import datetime

def create_skill(name: str, category: str):
    """Create a new skill with proper structure."""
    
    base_path = f"/Users/pterion2910/.openclaw/workspace/skills/{category}/{name}"
    
    if os.path.exists(base_path):
        print(f"❌ Skill already exists: {base_path}")
        return False
    
    os.makedirs(base_path, exist_ok=True)
    
    # README.md
    readme = f"""# Skill: {name}

## Description
[Brief description of what this skill does]

## When to Use
- [Specific use case 1]
- [Specific use case 2]

## When NOT to Use
- [Anti-pattern 1]
- [Anti-pattern 2]

## Negative Examples (Failures)
1. **[Failure description]**: [What went wrong]
   - Fix: [How it was fixed]

## Dependencies
```bash
# System
python3 >= 3.10

# APIs
[API_KEY_NAME]  # [Description]
```

## Usage
```bash
python3 skills/{category}/{name}/main.py [args]
```

## Configuration
Edit `config.yaml`:
```yaml
[key]: [value]
```

## Output
- [Output location/description]

## Artifacts
[Saved to /mnt/data/... or None]

## Handoff Protocol
When context compacts:
1. [Step 1]
2. [Step 2]
"""
    
    with open(f"{base_path}/README.md", "w") as f:
        f.write(readme)
    
    # main.py template
    main_py = f'''#!/usr/bin/env python3
"""
Skill: {name}
Created: {datetime.now().strftime("%Y-%m-%d %H:%M")}
"""

import os
import sys

def main():
    """Main entry point."""
    print(f"Skill '{name}' executed")
    # TODO: Implement

if __name__ == "__main__":
    main()
'''
    
    with open(f"{base_path}/main.py", "w") as f:
        f.write(main_py)
    os.chmod(f"{base_path}/main.py", 0o755)
    
    # config.yaml
    config_yaml = f"""# {name} configuration
# Edit as needed

setting: value
"""
    
    with open(f"{base_path}/config.yaml", "w") as f:
        f.write(config_yaml)
    
    print(f"✅ Created skill: {base_path}")
    print(f"   Next steps:")
    print(f"   1. Edit {base_path}/README.md")
    print(f"   2. Implement {base_path}/main.py")
    print(f"   3. Test: python3 {base_path}/main.py")
    print(f"   4. Update SKILL_MANIFEST.md")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a new skill")
    parser.add_argument("--name", required=True, help="Skill name (kebab-case)")
    parser.add_argument("--category", required=True, help="Skill category (crypto|automation|data|system)")
    
    args = parser.parse_args()
    create_skill(args.name, args.category)
