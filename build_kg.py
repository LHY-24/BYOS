import os
import sys
from lightrag import LightRAG
from lightrag.llm import gpt_4o_mini_complete

import kconfiglib as klib

def gen_kg(linux_path: str) -> dict:
    config = klib.Kconfig(linux_path + "/Kconfig")
    config.load_config(linux_path + "/.config")
    def init_config(node: klib.MenuNode) -> tuple[list[dict], list[dict], str]:
        entities = []
        relationships = []
        name = ""
        description = ""
        help = None

        item = node.item
        if item == klib.MENU:
            name = node.prompt[0]
            if hasattr(node, "help"):
                help = node.help
        elif item == klib.COMMENT:
            return [], [], None
        elif isinstance(item, klib.Symbol) or isinstance(item, klib.Choice):
            if item.name:
                name = item.name
                description = node.prompt[0]
                if hasattr(node, "help") and node.help:
                    help = node.help
            else:
                name = node.prompt[0]
                if hasattr(node, "help") and node.help:
                    help = node.help

        entities.append({
            "entity_name": name,
            "entity_type": "config",
            "description": description,
            "source_id": "Kconfig"
        })
        if help:
            entities.append({
                "entity_name": "HELPER TEXT(" + name + ")",
                "entity_type": "help_text",
                "description": help,
                "source_id": "Kconfig"
            })
            relationships.append({
                "src_id": name,
                "tgt_id": "HELPER TEXT(" + name + ")",
                "description": "helper text describes this config",
                "keywords": "",
                "weight": 1.0,
                "source_id": "Kconfig"
            })
        
        child = node.list
        while child:
            if not child.prompt:
                child = child.next
                continue
            e, r, n = init_config(child)
            if not n:
                child = child.next
                continue
            entities.extend(e)
            relationships.extend(r)
            relationships.append({
                "src_id": name,
                "tgt_id": n,
                "description": "source is parent of target",
                "keywords": "",
                "weight": 1.0,
                "source_id": "Kconfig"
            })

            child = child.next
        return entities, relationships, name
    e, r, n = init_config(config.top_node)
    return {
        "chunks": [],
        "entities": e,
        "relationships": r
    }


def build_kg(linux_path):
    os.environ['srctree'] = linux_path
    os.environ['CC'] = "gcc"
    os.environ['LD'] = "ld"
    os.environ['ARCH'] = "x86"
    os.environ['SRCARCH'] = "x86"

    WORKING_DIR = "./kconfig"


    if not os.path.exists(WORKING_DIR):
        os.mkdir(WORKING_DIR)

    rag = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=gpt_4o_mini_complete,  # Use gpt_4o_mini_complete LLM model
        # llm_model_func=gpt_4o_complete  # Optionally, use a stronger model
    )

    rag.insert_custom_kg(gen_kg(linux_path))

if __name__ == "__main__":
    build_kg(sys.argv[1])
