import sys
from lightrag import LightRAG
from lightrag.llm import gpt_4o_mini_complete

WORKING_DIR = "./kconfig"

rag = LightRAG(
    working_dir=WORKING_DIR,
    llm_model_func=gpt_4o_mini_complete,
)

with open(sys.argv[1], "r") as f:
    lines = f.readlines()
    for line in lines:
        line = line.strip()
        if line.startswith("#"):
            continue
        print("Insert knowledge " + line)
        rag.insert(line)
