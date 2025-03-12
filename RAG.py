from lightrag import LightRAG, QueryParam
from lightrag.llm import gpt_4o_mini_complete, gpt_4o_complete
import kconfiglib as klib


class KnowledgeGenerator:
    def __init__(
        self,
        working_dir: str,
        gen_knowledge: bool,
        search_mode: str,
        llm_model_func: str = "gpt-4o-mini",
    ):
        model_func_map = {"gpt-4o-mini": gpt_4o_complete, "gpt-4o": gpt_4o_complete}
        model_func = (
            model_func_map[llm_model_func]
            if llm_model_func in model_func_map.keys()
            else gpt_4o_mini_complete
        )
        self.rag = LightRAG(
            working_dir=working_dir, llm_model_func=model_func, log_level="ERROR"
        )
        self.search_mode = search_mode
        self.gk = gen_knowledge
        if not self.gk:
            print("RAG will not generate knowledge")

    def gen_knowledge(self, prompt: str):
        return self.rag.query(prompt, QueryParam(mode=self.search_mode))

    def gen_configs_knowledge(self, configs: list[klib.MenuNode], target: str):
        if not self.gk:
            return ""
        prompt = f"Of these configs listed below, which ones may affect the target?: {target}\n"
        for config in configs:
            item = config.item
            if item == klib.MENU:
                prompt += config.prompt[0]
                prompt += "\n"
            elif isinstance(item, klib.Choice):
                prompt += config.prompt[0]
                prompt += "\n"
            elif isinstance(item, klib.Symbol):
                prompt += item.name
                prompt += "\n"
        return self.gen_knowledge(prompt)
