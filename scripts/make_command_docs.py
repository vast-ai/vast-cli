#!/usr/bin/env python3

####################################################################################################
# Title: make_command_docs.py; Author Greg Propf; Date 2022-02-01
####################################################################################################
# Usage: 'python scripts/make_command_docs.py' This script runs the 'vastai'
# command with the --help option to generate the list of commands and then
# again for each command shown by help. It does some minimal formatting on
# the results and produces a Markdown version of the commands and their
# options.
####################################################################################################

import re
import subprocess
import sys
import os
import pty
import subprocess
import shutil
import json


def snip_lines_from_text(text: str, start_line: int, end_line: int = None, invert: bool = False):
    text_lines = text.split("\n")
    # for x in text_lines:
    #     print(x)
    if invert:
        return text_lines[:start_line] + text_lines[end_line:]
    if end_line is not None:
        return text_lines[start_line:end_line]
    else:
        return text_lines[start_line:]


def make_lines_into_links(text_lines: list):
    return "\n".join([re.sub(r"\s*(.+)\s*", r"[\1](#\1)  ", line) for line in text_lines])


def run_cmd_and_capture_output(verb: str, obj: str = None, direct_obj: str = None) -> str:



    # Get terminal size
    columns, rows = shutil.get_terminal_size()

    # Create a pseudo-terminal with the same size
    master, slave = pty.openpty()

    # Set the terminal size of the slave
    os.system(f'stty cols {columns} rows {rows} < /dev/pts/{os.minor(os.fstat(slave).st_rdev)}')

    # Execute the command
    #proc = subprocess.Popen(["vastai", "--help"], stdout=slave, stderr=slave)


    if verb:
        if direct_obj:
            cmd_output = subprocess.run(["vastai", verb, obj, direct_obj, "--help"], stdout=subprocess.PIPE)
            #proc = subprocess.Popen(["vastai", verb, obj, direct_obj, "--help"], stdout=slave, stderr=slave)
        elif obj:
            cmd_output = subprocess.run(["vastai", verb, obj, "--help"], stdout=subprocess.PIPE)
            #proc = subprocess.Popen(["vastai", verb, obj, "--help"], stdout=slave, stderr=slave)
        else:
            cmd_output = subprocess.run(["vastai", verb, "--help"], stdout=subprocess.PIPE)
            #proc = subprocess.Popen(["vastai", verb, "--help"], stdout=slave, stderr=slave)
    else:
        cmd_output = subprocess.run(["vastai", "--help"], stdout=subprocess.PIPE)
        #cmd_output = subprocess.Popen(["vastai", "--help"], stdout=subprocess.PIPE)

        command = "vastai --help"
        os.system("resize -s 128 128")
        res = os.popen(command).read() # get all content as text
        #res = list(os.popen(command)) # get lines as array elements
        return res


    # Read the output
    #cmd_output = os.fdopen(master).read()

    #return cmd_output.stdout
    cmd_output_text = cmd_output.stdout.decode('utf-8')

    # Close the pseudo-terminal
    os.close(slave)
    os.close(master)

    return cmd_output_text


def run_help_for_commands(lines):
    help_text = ""
    i = 1
    for line in lines:
        cmd_output = ""
        line_parts = re.split(r"\s{2,}", line.strip())
        command_parts = re.split(r"\s+", line_parts[0])
        if len(line_parts) < 2:
            line_parts.append("")
        print(f"{i}: {command_parts}")
        i += 1
        num_command_parts = len(command_parts)
        if num_command_parts == 0:
            continue
        if num_command_parts == 3:
            cmd_output = run_cmd_and_capture_output(command_parts[0], command_parts[1], command_parts[2])
        if num_command_parts == 2:
            cmd_output = run_cmd_and_capture_output(command_parts[0], command_parts[1])
        elif num_command_parts == 1:
            cmd_output = run_cmd_and_capture_output(command_parts[0])

        help_text += f"## {line_parts[0]} \n {line_parts[1]}\n\n"
        #help_text += f"\n{cmd_output}\n\n---\n"
        help_text += f"```\n{cmd_output}\n```\n---\n"

    return help_text


def parse_commands(lines):
    commands = []
    help_text = ""
    i = 1
    for line in lines:
        cmd_output = ""
        line_parts = re.split(r"\s{2,}", line.strip())
        command_parts = re.split(r"\s+", line_parts[0])
        if len(line_parts) < 2:
            line_parts.append("")
        print(f"{i}: {command_parts}")
        i += 1
        num_command_parts = len(command_parts)
        if num_command_parts == 0:
            continue
        if num_command_parts == 3:
            cmd_output = run_cmd_and_capture_output(command_parts[0], command_parts[1], command_parts[2])
        if num_command_parts == 2:
            cmd_output = run_cmd_and_capture_output(command_parts[0], command_parts[1])
        elif num_command_parts == 1:
            cmd_output = run_cmd_and_capture_output(command_parts[0])

        help_text += f"## {line_parts[0]} \n {line_parts[1]}\n\n"
        #help_text += f"\n{cmd_output}\n\n---\n"
        help_text += f"```\n{cmd_output}\n```\n---\n"

        command = {"name": line_parts[0], "summary": line_parts[1], "details": cmd_output}
        commands.append(command)

    return commands

main_help_text = run_cmd_and_capture_output("", "")

snipped_help_text = snip_lines_from_text(main_help_text, start_line=7, end_line=None)
snipped_help_text = sorted(list(map(str.strip, snipped_help_text)))

commands = parse_commands(snipped_help_text)
# with open("commands.json", "w") as f:
#     json.dump(commands, f)

command_help_text = ""
command_help_text += f"\n# Client Commands \n\n"

for c in commands:
    if "[Host]" not in c["summary"]:
        name = c['name']
        summary = c['summary']
        details = c['details']
        if name == "" or name[:1] == "-" or details == "":
            continue
        command_help_text += f"\n## {name} \n\n {summary}\n\n"
        command_help_text += f"```\n{details}\n```\n\n"

command_help_text += f"\n# Host Commands \n\n"

for c in commands:
    if "[Host]" in c["summary"]:
        name = c['name']
        summary = c['summary']
        details = c['details']
        command_help_text += f"\n## {name} \n\n {summary}\n\n"
        command_help_text += f"```\n{details}\n```\n\n"

out_text  = "# CLI Commands \n\n"
out_text += f"```\n{main_help_text}\n```\n"


with open("commands.md", "w") as fh:
    fh.write(out_text)
    fh.write(command_help_text)
