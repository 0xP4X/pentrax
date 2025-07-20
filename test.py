import re

ROUTES_FILE = "routes.py"

with open(ROUTES_FILE, "r", encoding="utf-8") as f:
    content = f.read()

changes_made = []

# List of known advanced admin function name conflicts and their new names/routes
conflict_patterns = [
    ("admin_add_quiz_question", "admin_add_advanced_quiz_question", "/admin/advanced-labs/<int:lab_id>/quiz/add", r"/admin/labs/<int:lab_id>/quiz/add"),
    ("admin_delete_quuiz_question", "admin_delete_advanced_quuiz_question", "/admin/advanced-labs/<int:lab_id>/quiz/delete", r"/admin/labs/<int:lab_id>/quiz/delete"),
    ("admin_add_terminal_command", "admin_add_advanced_terminal_command", "/admin/advanced-labs/<int:lab_id>/terminal-commands/add", r"/admin/labs/terminal-commands/add"),
    ("admin_delete_terminal_command", "admin_delete_advanced_terminal_command", "/admin/advanced-labs/<int:lab_id>/terminal-commands/delete", r"/admin/labs/terminal-commands/delete"),
    ("admin_learning_paths", "admin_advanced_learning_paths", "/admin/advanced-labs/learning-paths", r"/admin/labs/learning-paths"),
    ("admin_ctf_challenges", "admin_advanced_ctf_challenges", "/admin/advanced-labs/ctf-challenges", r"/admin/labs/ctf-challenges"),
    ("admin_sandbox_environments", "admin_advanced_sandbox_environments", "/admin/advanced-labs/sandbox-environments", r"/admin/labs/sandbox-environments"),
    ("admin_create_advanced_lab_v3", "admin_create_advanced_lab_v4", "/admin/advanced-labs/create-v4", r"/admin/advanced-labs/create-v3"),
]

for func, new_func, new_route, old_route_pattern in conflict_patterns:
    pattern = re.compile(
        rf"(@app\.route\(['\"]{old_route_pattern}['"].*?\)\s*@admin_required\s*def ){func}(\s*\(.*?\):)",
        re.DOTALL
    )
    def make_replacer(new_func=new_func, new_route=new_route):
        def replacer(match):
            changes_made.append(f"{func} -> {new_func}")
            return (
                f"@app.route('{new_route}', methods=['GET', 'POST'])\n"
                "@admin_required\n"
                f"def {new_func}{match.group(2)}"
            )
        return replacer
    content, count = pattern.subn(make_replacer(), content)

# Special case: admin_delete_terminal_command with command_id (not lab_id)
pattern_special = re.compile(
    r"(@app\.route\(['\"]\/admin\/terminal-commands\/\<int:command_id\>\/delete['"].*?\)\s*@admin_required\s*def )admin_delete_terminal_command(\s*\(command_id\):)",
    re.DOTALL
)
def replacer_special(match):
    changes_made.append("admin_delete_terminal_command (command_id) -> admin_delete_advanced_terminal_command")
    return (
        "@app.route('/admin/advanced-labs/terminal-commands/<int:command_id>/delete', methods=['POST'])\n"
        "@admin_required\n"
        "def admin_delete_advanced_terminal_command(command_id):"
    )
content, count_special = pattern_special.subn(replacer_special, content)

# Write changes back to file
if changes_made or count_special > 0:
    with open(ROUTES_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Fixed {len(changes_made) + count_special} route conflicts in {ROUTES_FILE}:")
    for change in changes_made:
        print(f"   - {change}")
    if count_special > 0:
        print("   - admin_delete_terminal_command (command_id) -> admin_delete_advanced_terminal_command")
else:
    print("✅ No route conflicts found to fix.")

# Verify no more duplicates
print("\n🔍 Checking for remaining conflicts...")
with open(ROUTES_FILE, "r", encoding="utf-8") as f:
    content = f.read()

function_pattern = re.compile(r'def (admin_\w+)[\(:]', re.MULTILINE)
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
