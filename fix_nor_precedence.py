import re, sys

path = sys.argv[1]
out_path = sys.argv[2] if len(sys.argv) > 2 else path.replace('.py', '_norfix.py')

with open(path) as f:
    content = f.read()

# Write_Circuit produced:  g[i] = r[a] | r[b] ^ 1     (evaluates WRONG as r[a] | (r[b]^1))
# Correct NOR is:          g[i] = (r[a] | r[b]) ^ 1
pattern = re.compile(r'(g\[\d+\] = )r\[(\d+)\] \| r\[(\d+)\] \^ 1')
fixed, count = pattern.subn(r'\1(r[\2] | r[\3]) ^ 1', content)

with open(out_path, 'w') as f:
    f.write(fixed)
print(f'Patched {count} NOR gate line(s) -> {out_path}')