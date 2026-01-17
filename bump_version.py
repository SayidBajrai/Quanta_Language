#!/usr/bin/env python3
"""Bump version in pyproject.toml"""
import re
import sys

bump_type = sys.argv[1] if len(sys.argv) > 1 else "patch"

with open("pyproject.toml", "r") as f:
    content = f.read()

# Find version line
match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
if not match:
    print("Error: Could not find version in pyproject.toml")
    sys.exit(1)

old_version = match.group(1)
parts = [int(x) for x in old_version.split(".")]

# Ensure we have at least 3 parts (major.minor.patch)
while len(parts) < 3:
    parts.append(0)

# Bump version
if bump_type == "patch":
    parts[2] += 1
elif bump_type == "minor":
    parts[1] += 1
    parts[2] = 0
elif bump_type == "major":
    parts[0] += 1
    parts[1] = 0
    parts[2] = 0
else:
    print(f"Error: Invalid bump type: {bump_type}")
    sys.exit(1)

new_version = ".".join(map(str, parts))

# Replace version in content
new_content = re.sub(
    r'version\s*=\s*["\'][^"\']+["\']',
    f'version = "{new_version}"',
    content
)

# Write back
with open("pyproject.toml", "w") as f:
    f.write(new_content)

print(f"{old_version} -> {new_version}")

