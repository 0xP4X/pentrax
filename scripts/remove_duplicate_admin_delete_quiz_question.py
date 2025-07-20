import re

ROUTE_PATTERN = re.compile(r"^@app\.route\('/admin/quiz-questions/<int:question_id>/delete', methods=\['POST'\]\)")
ADMIN_DECORATOR_PATTERN = re.compile(r"^@admin_required")
DEF_PATTERN = re.compile(r"^def admin_delete_quiz_question_global\(")


def remove_duplicate_admin_delete_quiz_question_global(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    found_first = False
    i = 0
    n = len(lines)
    while i < n:
        # Look for the route decorator
        if ROUTE_PATTERN.match(lines[i].strip()):
            # Check for @admin_required and def on next lines
            if i+1 < n and ADMIN_DECORATOR_PATTERN.match(lines[i+1].strip()) and i+2 < n and DEF_PATTERN.match(lines[i+2].strip()):
                if not found_first:
                    # Keep the first occurrence
                    found_first = True
                    new_lines.extend(lines[i:i+3])
                    i += 3
                    # Copy the function body
                    while i < n and not lines[i].strip().startswith('@app.route('):
                        new_lines.append(lines[i])
                        i += 1
                else:
                    # Skip this duplicate occurrence
                    i += 3
                    # Skip the function body
                    while i < n and not lines[i].strip().startswith('@app.route('):
                        i += 1
            else:
                new_lines.append(lines[i])
                i += 1
        else:
            new_lines.append(lines[i])
            i += 1

    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

if __name__ == '__main__':
    remove_duplicate_admin_delete_quiz_question_global('routes.py') 