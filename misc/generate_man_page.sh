#!/bin/bash -x

SCRIPT_DIR=`dirname "$0"`

cd "$SCRIPT_DIR"

# ALWAYS CHECK THE RESULT - too much magic!!!
# certain hacks are needed:
# - usage to SYNOPSIS (too much magic)
# - add OPTIONS section in place of "positional arguments:"
# - remove .SS (currently they are used only for option sections
# - for some reason \fB and \fR are put in [--option ...] lines
# - newlines
# the result is far from perfect and might be problematic when parsed
# with some automated tools but is properly displayed in man
help2man ../git_trustcheck.py \
    --no-discard-stderr --no-info \
    --include additional_man_info.txt \
    --name=git-trustcheck --section=1 \
    | sed 's/^\.SH DESCRIPTION//' \
    | sed --null-data --regexp-extended \
        's/usage: (.*?)\.TP\n(\[.*?]\n)\.PP/.SH SYNOPSIS\n\1\2.SH DESCRIPTION\n/' \
    | sed 's/^\.SS "positional arguments:"/.SH OPTIONS/' \
    | sed 's/^\.SS.*//' \
    | sed '/^ *\[/s/\\f[BR]//g' \
    | awk '{print $0 "\n.br"}' \
    > ../man/git-trustcheck.man.1
    
