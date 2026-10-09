import re

p = 'C:/Users/JerryJoel/OneDrive - Cloud Destinations Infotech Pvt Ltd/Documents/Projects/License Management Tool - Updated UI/Frontend/src/pages/RequestsPage.jsx'
src = open(p, encoding='utf-8').read()
lines = src.split('\n')

# strip strings and comments crudely (line-based), then count brackets
depth_stack = []  # (char, line)
pairs = {')': '(', '}': '{', ']': '['}

state = 'code'  # code | squote | dquote | template | line_comment | block_comment
for ln, line in enumerate(lines, 1):
    i = 0
    while i < len(line):
        ch = line[i]
        nxt = line[i + 1] if i + 1 < len(line) else ''
        if state == 'code':
            if ch == '/' and nxt == '/':
                state = 'line_comment'
                break
            elif ch == '/' and nxt == '*':
                state = 'block_comment'
                i += 2
                continue
            elif ch == "'":
                state = 'squote'
            elif ch == '"':
                state = 'dquote'
            elif ch == '`':
                state = 'template'
            elif ch in '({[':
                depth_stack.append((ch, ln))
            elif ch in ')}]':
                if depth_stack and depth_stack[-1][0] == pairs[ch]:
                    depth_stack.pop()
                else:
                    print(f'MISMATCH line {ln}: got {ch!r}, stack top {depth_stack[-1] if depth_stack else None}')
        elif state == 'squote':
            if ch == '\\':
                i += 2
                continue
            if ch == "'":
                state = 'code'
        elif state == 'dquote':
            if ch == '\\':
                i += 2
                continue
            if ch == '"':
                state = 'code'
        elif state == 'template':
            if ch == '\\':
                i += 2
                continue
            if ch == '`':
                state = 'code'
        elif state == 'line_comment':
            break
        elif state == 'block_comment':
            if ch == '*' and nxt == '/':
                state = 'code'
                i += 2
                continue
        i += 1
    if state == 'line_comment':
        state = 'code'

print('final state:', state)
print('unclosed (from last):')
for item in depth_stack[-10:]:
    print('   ', item)

# crude JSX tag balance for div/form/table/select/td/tr
for tag in ['div', 'form', 'table', 'thead', 'tbody', 'select', 'button', 'span', 'p', 'label', 'td', 'th', 'tr', 'h1', 'h2']:
    opens = len(re.findall(r'<' + tag + r'[\s>]', src))
    closes = len(re.findall(r'</' + tag + r'>', src))
    if opens != closes:
        print(f'tag imbalance <{tag}>: open={opens} close={closes}')
