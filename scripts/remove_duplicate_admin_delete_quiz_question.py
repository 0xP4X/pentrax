import re

ROUTES_FILE = 'routes.py'  # Corrected path

with open(ROUTES_FILE, 'r', encoding='utf-8') as f:
    lines = f.readlines()

pattern = re.compile(r'^@app\.route\(["\"]/admin/quiz-questions/<int:question_id>/delete["\"][^)]*\)')
def_pattern = re.compile(r'^def admin_delete_quiz_question_global\(')

found_first = False
new_lines = []
i = 0
while i < len(lines):
    if pattern.match(lines[i].strip()):
        # Check if this is the first occurrence
        if not found_first:
            found_first = True
            new_lines.append(lines[i])
            i += 1
            # Copy decorators and function definition
            while i < len(lines) and (lines[i].strip().startswith('@') or def_pattern.match(lines[i].strip()) or lines[i].strip() == ''):
                new_lines.append(lines[i])
                i += 1
            # Copy function body
            indent = None
            while i < len(lines):
                if lines[i].strip() == '':
                    new_lines.append(lines[i])
                    i += 1
                    continue
                if indent is None:
                    match = re.match(r'^(\s+)', lines[i])
                    if match:
                        indent = match.group(1)
                    else:
                        break
                if lines[i].startswith(indent):
                    new_lines.append(lines[i])
                    i += 1
                else:
                    break
        else:
            # Skip this duplicate route and function
            i += 1
            # Skip decorators and function definition
            while i < len(lines) and (lines[i].strip().startswith('@') or def_pattern.match(lines[i].strip()) or lines[i].strip() == ''):
                i += 1
            # Skip function body
            indent = None
            while i < len(lines):
                if lines[i].strip() == '':
                    i += 1
                    continue
                if indent is None:
                    match = re.match(r'^(\s+)', lines[i])
                    if match:
                        indent = match.group(1)
                    else:
                        break
                if lines[i].startswith(indent):
                    i += 1
                else:
                    break
    else:
        new_lines.append(lines[i])
        i += 1

with open(ROUTES_FILE, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Duplicate admin_delete_quiz_question_global definitions removed.') 