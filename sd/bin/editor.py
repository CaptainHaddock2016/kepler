import fsio

PROMPT = "editor> "
SENTINEL = "."


def _safe_input(prompt=""):
    try:
        return input(prompt)
    except EOFError:
        return None


def _display_help():
    print("Simple line editor commands:")
    print(":show          - display the current buffer")
    print(":append        - add lines to the end of the buffer")
    print(":insert N      - insert lines before line N (1-based)")
    print(":set N text    - replace line N with the provided text")
    print(":delete N      - delete line N")
    print(":clear         - clear the buffer")
    print(":w             - write the buffer to disk")
    print(":wq            - write the buffer and quit")
    print(":q             - quit without saving (prompts if unsaved changes)")
    print(":help          - show this message again")
    print()
    print(f"When inserting or appending lines, finish by entering '{SENTINEL}' on a line by itself.")


def _display_buffer(buffer):
    if not buffer:
        print("(buffer is empty)")
        return
    width = len(str(len(buffer)))
    for idx, line in enumerate(buffer, start=1):
        print(f"{idx:>{width}}| {line}")


def _collect_lines():
    print(f"Enter text. Finish with '{SENTINEL}' on its own line.")
    lines = []
    while True:
        line = _safe_input()
        if line is None:
            print("End of input detected. Leaving line entry mode.")
            break
        if line == SENTINEL:
            break
        lines.append(line)
    return lines


def _write_buffer(path, buffer):
    content = "\n".join(buffer)
    if buffer:
        content += "\n"
    path.write(content)
    print(f"Wrote {len(buffer)} line(s) to {path.pstr()}")


def main(argv, cwd):
    args = argv[1:]
    if not args:
        return "Usage: editor <filename>"

    path = fsio.Path(cwd).resolve(args[0])

    if path.exists() and path.is_dir:
        return f"editor: '{path.pstr()}' is a directory"

    parent = path.parent
    if str(parent) and not parent.exists():
        return f"editor: directory '{parent.pstr()}' does not exist"

    buffer = []
    if path.exists():
        data = path.read("r")
        buffer = data.splitlines()
        print(f"Opened {path.pstr()} ({len(buffer)} line(s))")
    else:
        print(f"Editing new file {path.pstr()}")

    _display_help()
    if buffer:
        _display_buffer(buffer)

    dirty = False

    while True:
        command = _safe_input(PROMPT)
        if command is None:
            print("Input closed. Exiting editor.")
            break

        command = command.strip()
        if not command:
            continue

        if command == ":help":
            _display_help()
        elif command == ":show":
            _display_buffer(buffer)
        elif command == ":append":
            new_lines = _collect_lines()
            if new_lines:
                buffer.extend(new_lines)
                dirty = True
        elif command.startswith(":insert"):
            parts = command.split()
            if len(parts) != 2 or not parts[1].isdigit():
                print("Usage: :insert N")
                continue
            line_no = int(parts[1])
            if line_no < 1 or line_no > len(buffer) + 1:
                print("Line number out of range")
                continue
            new_lines = _collect_lines()
            if new_lines:
                index = line_no - 1
                buffer[index:index] = new_lines
                dirty = True
        elif command.startswith(":set"):
            parts = command.split(maxsplit=2)
            if len(parts) < 3 or not parts[1].isdigit():
                print("Usage: :set N text")
                continue
            line_no = int(parts[1])
            if line_no < 1 or line_no > len(buffer):
                print("Line number out of range")
                continue
            buffer[line_no - 1] = parts[2]
            dirty = True
        elif command.startswith(":delete"):
            parts = command.split()
            if len(parts) != 2 or not parts[1].isdigit():
                print("Usage: :delete N")
                continue
            line_no = int(parts[1])
            if line_no < 1 or line_no > len(buffer):
                print("Line number out of range")
                continue
            removed = buffer.pop(line_no - 1)
            print(f"Deleted line {line_no}: {removed}")
            dirty = True
        elif command == ":clear":
            buffer.clear()
            dirty = True
        elif command in (":w", ":write"):
            _write_buffer(path, buffer)
            dirty = False
        elif command in (":wq", ":writequit"):
            _write_buffer(path, buffer)
            dirty = False
            break
        elif command == ":q":
            if dirty:
                confirm = _safe_input("Unsaved changes, quit anyway? (y/N): ")
                if confirm and confirm.lower().startswith("y"):
                    break
            else:
                break
        else:
            print("Unknown command. Type :help for instructions.")

    return ""
