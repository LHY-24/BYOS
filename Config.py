KEY = "sk-xxx"  # replace key here
CC = "gcc"
LD = "ld"
SRCTREE = "."
ARCH = "riscv"
SRCARCH = "riscv"
WORKING_DIR = "./kconfig"

# debug output
DEBUG = False

# opt target
opt_target = [
    "the  Dhrystone and Whetstone  scores in UnixBench",
    " the File Copy score in Unixbench, and  the file copy throughput ",
    " the Execl Throughput score in Unixbench,The execl is a system call in Unix and Linux systems, used to execute a new program. ",
    " the Pipe-based Context Switching score in Unixbench",
    " the unixbench total score",
    " the Process Creation score in Unixbench and the process creation throughput",
    " the System Callscore in Unixbench and the system call throughput",
    " the Shell Scripts score in Unixbench and the Shell Script  throughput",
]

# opt description
opt_description = [
    "To enhance the Dhrystone and Whetstone  scores in UnixBench. The former represents integer processing capability, while the latter represents floating-point processing capability.",
    "to enhance the File Copy  score in Unixbench",
    "to enhance the Execl Throughput  score in Unixbench .",
    "to enhance the Pipe-based Context Switching score in Unixbench",
    "to enhance the unixbench  total score",
    "to enhance the Process Creation  score in Unixbench, improve the process creation ability for os",
    "to enhance the System Call  score in Unixbench, improve the system call ability for os",
    "to enhance the Shell Scripts  score in Unixbench",
]
