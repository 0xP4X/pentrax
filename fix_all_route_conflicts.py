import re

ROUTES_FILE = "routes.py"

with open(ROUTES_FILE, "r", encoding="utf-8") as f:
    content = f.read()

# Track changes
changes_made = []

# Fix 1: Second admin_delete_lab (around line 4065) - rename to admin_delete_advanced_lab
pattern1 = re.compile(
    r"(@app\.route\(['\"]\/admin\/labs\/<int:lab_id>\/delete['\"].*?\)\s*@admin_required\s*def )admin_delete_lab(\s*\(lab_id\):)",
    re.DOTALL
)

def replacer1(match):
    changes_made.append("admin_delete_lab -> admin_delete_advanced_lab")
    return (
        "@app.route('/admin/advanced-labs/<int:lab_id>/delete', methods=['POST'])\n"
        "@admin_required\n"
        "def admin_delete_advanced_lab(lab_id):"
    )

content, count1 = pattern1.subn(replacer1, content)

# Fix 2: Second admin_create_advanced_lab (around line 4815) - rename to admin_create_advanced_lab_v2
pattern2 = re.compile(
    r"(@app\.route\(['\"]\/admin\/advanced-labs\/create['\"].*?\)\s*@admin_required\s*def )admin_create_advanced_lab(\s*\(\):)",
    re.DOTALL
)

def replacer2(match):
    changes_made.append("admin_create_advanced_lab -> admin_create_advanced_lab_v2")
    return (
        "@app.route('/admin/advanced-labs/create-v2', methods=['GET', 'POST'])\n"
        "@admin_required\n"
        "def admin_create_advanced_lab_v2():"
    )

content, count2 = pattern2.subn(replacer2, content)

# Write changes back to file
if changes_made:
    with open(ROUTES_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Fixed {len(changes_made)} route conflicts in {ROUTES_FILE}:")
    for change in changes_made:
        print(f"   - {change}")
else:
    print("✅ No route conflicts found to fix.")

# Verify no more duplicates
print("\n🔍 Checking for remaining conflicts...")
with open(ROUTES_FILE, "r", encoding="utf-8") as f:
    content = f.read()

# Check for any remaining duplicate function names
function_pattern = re.compile(r'def (admin_\w+)\(', re.MULTILINE)
functions = function_pattern.findall(content)
duplicates = {}
for func in functions:
    if func in duplicates:
        duplicates[func] += 1
    else:
        duplicates[func] = 1

conflicts = [func for func, count in duplicates.items() if count > 1]
if conflicts:
    print(f"⚠️ Remaining conflicts found: {conflicts}")
else:
    print("✅ No remaining function name conflicts!") 