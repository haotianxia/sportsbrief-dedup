"""The deterministic verifier: each tool's checks live in its own module, on contract instances."""

from contract import Task, Tool

from . import compare, pin, reports, task

TOOLS = {
    Tool.PIN_DUPLICATES: pin,
    Tool.LIST_REPORTS: reports,
    Tool.COMPARE_REPORTS: compare,
}
# task -> its output's check, verify_task(arguments, output, reference, workspace)
TASKS = {Task.FILTER_DUPLICATES: task.verify_task, Task.LIST_REPORTS: reports.verify_task}


def verify_input(tool, value):
    return TOOLS[Tool(tool)].verify_input(value)


def verify_output(tool, input_value, output_value, workspace):
    return TOOLS[Tool(tool)].verify_output(input_value, output_value, workspace)


def verify_task(task, arguments, output, reference, workspace):
    return TASKS[Task(task)](arguments, output, reference, workspace)
