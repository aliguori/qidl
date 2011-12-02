import sys

suppress = False
for line in sys.stdin:
    if line.startswith('#'):
        _, __, rest = line.split(' ', 2)
        filename, _ = rest[1:].split('"', 1)
        if filename == sys.argv[1]:
            suppress = False
        else:
            suppress = True
    elif not suppress:
        sys.stdout.write(line)

sys.stdout.flush()
