import re

ROUTES_FILE = "routes.py"

with open(ROUTES_FILE, "r", encoding="utf-8") as f:
    content = f.read()

# Pattern to find the advanced admin edit route/function
pattern = re.compile(
    r"(@app\.route\(['\"]\/admin\/labs\/<int:lab_id>\/edit['\"].*?\)\s*@admin_required\s*def )admin_edit_lab(\s*\()",
    re.DOTALL
)

def replacer(match):
    return (
        "@app.route('/admin/advanced-labs/<int:lab_id>/edit', methods=['GET', 'POST'])\n"
        "@admin_required\n"
        "def admin_edit_advanced_lab("
    )

new_content, count = pattern.subn(replacer, content)

if count > 0:
    with open(ROUTES_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"✅ Fixed {count} advanced admin lab edit route(s) in {ROUTES_FILE}.")
else:
    print("⚠️ No advanced admin lab edit route found to fix.")

# Optionally, update template references if needed.