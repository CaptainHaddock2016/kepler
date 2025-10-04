import fsio  # use your existing file API

def main(argv, cwd, input_data=""):
    """
    Linux-like echo command with -n, -e, and redirection.
    Supports:
      echo hello
      echo hello > file.txt
      echo world >> file.txt
      echo -e "line1\\nline2"
      echo hi | next_command
    """
    args = argv[1:]
    interpret_escapes = False
    trailing_newline = True

    # --- Parse redirection ---
    outfile = None
    append_mode = False
    if '>' in args:
        idx = args.index('>')
        if idx + 1 < len(args):
            outfile = args[idx + 1]
            args = args[:idx]
            append_mode = False
        else:
            print("echo: syntax error near unexpected token `newline`")
            return ""
    elif '>>' in args:
        idx = args.index('>>')
        if idx + 1 < len(args):
            outfile = args[idx + 1]
            args = args[:idx]
            append_mode = True
        else:
            print("echo: syntax error near unexpected token `newline`")
            return ""

    # --- Parse flags ---
    while args and args[0].startswith('-'):
        flag = args.pop(0)
        if flag == '-n':
            trailing_newline = False
        elif flag == '-e':
            interpret_escapes = True
        elif flag == '-E':
            interpret_escapes = False
        else:
            args.insert(0, flag)
            break

    # --- Build output string ---
    output = " ".join(args)
    if input_data:
        output = input_data + output

    if interpret_escapes:
        output = output.encode('utf-8').decode('unicode_escape')
        output = output.replace("\\n", "\n")

    if trailing_newline:
        output += '\n'

    # --- Handle redirection ---
    if outfile:
        mode = "a" if append_mode else "w"
        path = fsio.Path(cwd).resolve(outfile)
        path.write(output, mode=mode)
        return None  # nothing to pipe forward

    return output
