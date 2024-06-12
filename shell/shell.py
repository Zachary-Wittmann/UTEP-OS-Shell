#! /usr/bin/env python3

import os
import sys
import re

def print_prompt():
    ps1 = os.getenv("PS1", "$ ")
    print(ps1, end="", flush=True)

def execute_command(command):
    try:
        pid = os.fork()

        if pid == 0:  # Child process
            os.execve(command[0], command, os.environ)
        elif pid > 0:  # Parent process
            _, status = os.waitpid(pid, 0)
            if os.WIFEXITED(status):
                if os.WEXITSTATUS(status) != 0:
                    print(f"Program terminated with exit code {os.WEXITSTATUS(status)}")
    except Exception:
        print(f"{command[0]}: command not found")
        sys.exit(1)

def find_command(command):
    # Check if the command is an absolute path
    if os.path.isabs(command[0]):
        return command

    # Check each directory in the PATH environment variable
    paths = os.getenv("PATH", "").split(":")
    for path in paths:
        executable_path = os.path.join(path, command[0])
        if os.path.exists(executable_path):
            return [executable_path] + command[1:]

    return command

def handle_input_redirection(command, input_file):
    try:
        pid = os.fork()

        if pid == 0:  # Child process
            with open(input_file, 'r') as f:
                os.dup2(f.fileno(), sys.stdin.fileno())
                os.execve(command[0], command, os.environ)
        elif pid > 0:  # Parent process
            _, status = os.waitpid(pid, 0)
            if os.WIFEXITED(status):
                return os.WEXITSTATUS(status)
    except Exception as e:
        print(f"Error: {e}")

def handle_output_redirection(command, output_file):
    try:
        pid = os.fork()

        if pid == 0:  # Child process
            with open(output_file, 'w') as f:
                os.dup2(f.fileno(), sys.stdout.fileno())
                os.execve(command[0], command, os.environ)
        elif pid > 0:  # Parent process
            _, status = os.waitpid(pid, 0)
            if os.WIFEXITED(status):
                return os.WEXITSTATUS(status)
    except Exception as e:
        print(f"Error: {e}")

def handle_piping(command1, command2):
    try:
        pipe_read, pipe_write = os.pipe()
        pid1 = os.fork()

        if pid1 == 0:  # Child process 1
            os.dup2(pipe_write, sys.stdout.fileno())
            os.close(pipe_read)
            os.close(pipe_write)
            os.execve(command1[0], command1, os.environ)
        elif pid1 > 0:  # Parent process
            pid2 = os.fork()

            if pid2 == 0:  # Child process 2
                os.dup2(pipe_read, sys.stdin.fileno())
                os.close(pipe_read)
                os.close(pipe_write)
                os.execve(command2[0], command2, os.environ)
            elif pid2 > 0:  # Parent process
                os.close(pipe_read)
                os.close(pipe_write)
                _, status1 = os.waitpid(pid1, 0)
                _, status2 = os.waitpid(pid2, 0)
                if os.WIFEXITED(status1) and os.WIFEXITED(status2):
                    return os.WEXITSTATUS(status2)
    except Exception as e:
        print(f"Error: {e}")

def execute_background_task(command):
    pid = os.fork()
    # taking the child process and giving it process group leader
    if pid == 0:
        os.setsid()
        # allows full perms to child
        os.umask(0)
        # error handling
        try:
            # attempts to execute
            os.execve(command[0], command, os.environ)
        except FileNotFoundError:
            # doesn't work write error message
            sys.stderr.write(f"{command[0]}: command not found\n")
            sys.exit(1)
    else:
        # if the process started properly give process ID
        sys.stdout.write(f"[{pid}]")

def main():
    current_directory = os.getcwd()

    while True:
        print_prompt()
        user_input = input().strip()

        if user_input.lower() == "exit":
            break

        # Split the input into commands using pipes
        pipe_commands = re.split(r'\s*\|\s*', user_input)

        # Initialize command before the loop
        prev_command = None
        command = None  # Initialize command here
           
        # Iterate over each command in the pipeline
        for i, command_str in enumerate(pipe_commands):
            # Split the command into arguments
            args = command_str.split()

            # Check for input/output redirection
            input_file = None
            output_file = None

            if '<' in args:
                input_index = args.index('<')
                input_file = args[input_index + 1]
                del args[input_index:input_index + 2]

            if '>' in args:
                output_index = args.index('>')
                output_file = args[output_index + 1]
                del args[output_index:output_index + 2]

            # Execute the command
            if args[0] == 'cd':
                # Handle 'cd' command separately to change the directory in the parent process
                try:
                    if len(args) > 1 and args[1] == '..':
                        # Handle 'cd ..' to go back to the previous directory
                        current_directory = os.path.dirname(current_directory)
                    else:
                        # Change to the specified directory
                        current_directory = os.path.abspath(args[1])
                    os.chdir(current_directory)
                except FileNotFoundError:
                    print(f"cd: {args[1]}: No such file or directory")
            elif i == 0:
                # Find the absolute path of the command
                command = find_command(args)
                if input_file:
                    handle_input_redirection(command, input_file)
                elif output_file:
                    handle_output_redirection(command, output_file)
                elif command[-1] == "&":
                    execute_background_task(command[:-1])
                else:
                    execute_command(command)
            else:
                # Handle piping for commands after the first one
                command = find_command(args)
                handle_piping(prev_command, command)

            prev_command = command

if __name__ == "__main__":
    main()
