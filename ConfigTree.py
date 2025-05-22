import kconfiglib as klib
import LLM
import logging
from RAG import KnowledgeGenerator
import Config as C
import os
import json


class Config:
    def __init__(
        self,
        kconfig_path: str,
        chatter: LLM.ChatContext,
        target: str,
        kg_search_mode: str,
        use_knowledge: bool,
        config_path: str = ".config",
    ):
        self.kconfig = klib.Kconfig(kconfig_path)
        self.kconfig.load_config(config_path)
        self.chatter = chatter
        self.current_node: klib.MenuNode = self.kconfig.top_node
        self.unvisit_node_list: list[klib.MenuNode] = [self.kconfig.top_node]
        self.node_dir_dict: dict[klib.MenuNode, list[str]] = {
            self.kconfig.top_node: [self.kconfig.top_node.prompt[0]]
        }
        logging.basicConfig(
            level=logging.INFO,
            filename="Config.log",
            datefmt="%Y/%m/%d %H:%M:%S",
        )

        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(logging.FileHandler("Config.log", mode="w"))
        self.logger.propagate = False
        self.logger.info(target)

        # init question logger to provide training data
        self.qlogger = logging.getLogger("__question_logger__")
        self.qlogger.addHandler(logging.FileHandler("QA.log", mode="w"))
        self.qlogger.propagate = False
        self.qlogger.info(target)

        self.target = target
        self.kg = KnowledgeGenerator(
            working_dir=C.WORKING_DIR,
            search_mode=kg_search_mode,
            gen_knowledge=use_knowledge,
        )

    def run(self):
        while len(self.unvisit_node_list) > 0:
            self.current_node = self.unvisit_node_list.pop()
            print(f"Visiting menu {'/'.join(self.node_dir_dict[self.current_node])}")
            self.process()

    def process(self):
        # get extended node list
        nodes = self.get_menunodes(self.current_node)

        menu_nodes = []
        bool_nodes = []
        binary_nodes = []
        trinary_nodes = []
        multiple_nodes = []
        value_nodes = []

        # iterate all current level nodes
        for node in nodes:
            item = node.item  # determine node type through this property
            if item == klib.MENU:
                menu_nodes.append(node)
            elif item == klib.COMMENT:
                # TODO: ignore comment currently
                pass
            else:
                # symbol or choice node
                if item.type in (klib.STRING, klib.INT, klib.HEX):
                    value_nodes.append(node)
                # select visible choice node
                elif (
                    isinstance(item, klib.Choice)
                    and item.visibility == 2
                    and item.str_value == "y"
                ):
                    multiple_nodes.append(node)
                elif len(item.assignable) == 1 and node.list:
                    # this node is a menu and is set to 'y' always
                    menu_nodes.append(node)
                elif item.type == klib.BOOL:
                    bool_nodes.append(node)
                elif item.type == klib.TRISTATE:
                    if item.assignable == (1, 2):
                        binary_nodes.append(node)
                    else:
                        trinary_nodes.append(node)

        if self.current_node.prompt[0] == "Memory Management options":
            print(self.current_node)
        # process all nodes
        if len(multiple_nodes) != 0:
            self.process_multiple(multiple_nodes)
        if len(value_nodes) != 0:
            self.process_value(value_nodes)
        if len(binary_nodes) != 0:
            self.process_binary(binary_nodes)
        if len(trinary_nodes) != 0:
            self.process_trinary(trinary_nodes)
        # bool nodes may be a menu. add these bool nodes to menu nodes if they are enabled
        new_menu_nodes = []
        if len(bool_nodes) != 0:
            new_menu_nodes.extend(self.process_bool(bool_nodes))

        # add menu nodes to unvisited nodes(which would be explored)
        menu_nodes.extend(new_menu_nodes)
        if len(menu_nodes) != 0:
            self.unvisit_node_list.extend(self.extend_nodes(menu_nodes))

    def get_menunodes(self, node: klib.MenuNode) -> list[klib.MenuNode]:
        """this function is used to get all active child nodes of a menunode

        Returns:
            list[klib.MenuNode]: child node list
        """
        node: klib.MenuNode = node.list
        # get all menu nodes to ask ai which nodes should be extended
        node_list = []
        while node:
            if node.prompt:
                if klib.expr_value(node.prompt[1]):
                    item = node.item
                    if isinstance(item, klib.Symbol) or isinstance(item, klib.Choice):
                        if item.type != klib.UNKNOWN:
                            node_list.append(node)
                    else:
                        node_list.append(node)
            node = node.next
        return node_list

    def extend_nodes(self, nodes: list[klib.MenuNode]) -> list[klib.MenuNode]:
        """
        this function is used to get menunodes to be extended
        for example, if a menu has 10 sub-nodes, ask llm to know which menunodes should be extended
        """
        # get knowledge from RAG
        knowledge_group = []
        for i in range(0, len(nodes), 3):
            knowledge_group.append(nodes[i : i + 3])
        knowledges = [
            self.kg.gen_configs_knowledge(g, self.target) for g in knowledge_group
        ]
        knowledge = "\n".join(knowledges)

        node_name_list = []
        node_name_list_without_idx = []
        node_name_dict = {}
        for i in range(len(nodes)):
            node_name = self.get_node_name(nodes[i])
            node_name_list.append(f"{i} {node_name}")
            node_name_list_without_idx.append(node_name)
            node_name_dict[node_name] = nodes[i]
        # ask LLM
        content = "\n".join(node_name_list)
        answers = self.chatter.ask_menu(content=content, knowledge=knowledge)
        # answers is in form of [0/General setup, 5/Kernel features, 6/Boot options, ...]
        menu_node: list[klib.MenuNode] = []
        # get node path prefix
        path = self.node_dir_dict[self.current_node]
        
        # record answers for qlogger
        qlogger_ans = []
        for answer in answers:
            if type(answer) == int:
                try:
                    node = nodes[answer]
                    menu_node.append(node)
                    self.node_dir_dict[node] = path + [node.prompt[0]]
                    qlogger_ans.append(node.prompt[0])
                except IndexError:
                    print(
                        f"LLM gives non-existent nodes(int). current node is\n{nodes}\nLLM gives\n{answer}"
                    )
            else:
                if answer in node_name_dict.keys():
                    if answer.isspace() or answer == "" or answer == "\n":
                        continue
                    node = node_name_dict[answer]
                    menu_node.append(node)
                    self.node_dir_dict[node] = path + [node.prompt[0]]
                    qlogger_ans.append(node.prompt[0])
                else:
                    print(
                        f"LLM gives non-existent nodes(string). current node is\n{nodes}\nLLM gives\n{answer}"
                    )
        # print("content:\n", content)
        # print("selection:\n", "\n".join([f"{t[0]} {t[1]}" for t in answers]))
        # qlogger logging
        if len(qlogger_ans) > 0:
            self.qlogger.info(
                json.dumps({"question": "Menu\t" + "\n".join(node_name_list_without_idx), "answer": qlogger_ans})
            )
        return menu_node

    def process_bool(self, nodes: list[klib.MenuNode]) -> list[klib.MenuNode]:
        new_menu_nodes_dict: dict[str, klib.MenuNode] = {}
        # ask at most 15 config for once
        nodes_group = []
        for i in range(0, len(nodes), 9):
            nodes_group.append(nodes[i : i + 9])
        for group in nodes_group:
            node_name_dict = {}
            node_name_lower_dict = {}
            for node in group:
                name = self.get_node_name(node)
                node_name_dict[name] = node
                simple_name = self.get_simple_node_name(node)
                node_name_lower_dict[simple_name.lower()] = node
                # add new menu nodes if node is enabled and node has child
                if node.item.tri_value == 2 and node.list:
                    new_menu_nodes_dict[name.lower()] = node
            node_names = "\n".join(node_name_dict.keys())

            # generate knowledge
            knowledge_group = []
            for i in range(0, len(group), 3):
                knowledge_group.append(group[i : i + 3])
            knowledges = [
                self.kg.gen_configs_knowledge(g, self.target) for g in knowledge_group
            ]
            knowledge = "\n".join(knowledges)

            # answer is a dict[str: int]
            answer = self.chatter.ask_on_off_option(node_names, knowledge)
            # record answers for qlogger
            qlogger_ans = []
            for config_name, state in answer.items():
                config_name = config_name.strip().lower()
                if config_name in node_name_lower_dict.keys():
                    node = node_name_lower_dict[config_name]
                    qlogger_ans.append({"config": config_name, "value": state})
                    if node.item.tri_value == state:
                        continue
                    # log
                    self.logger.info(
                        f"CONFIG_{node.item.name}={node.item.str_value}"
                        # f"Config changed: {node.item.name} from state '{node.item.tri_value}' to '{state}'"
                    )
                    # set config value to on or off. state is an int in (0, 2), where off = 0 and on = 2
                    node.item.set_value(state)
                    # if an option is set, check if it is a menu. if so, add it to menu node list
                    if state == 2:
                        new_menu_nodes_dict[config_name] = node
                    elif state == 0 and config_name in new_menu_nodes_dict.keys():
                        new_menu_nodes_dict.pop(config_name)
                else:
                    print(f"Error: config name {config_name} does not exist")
                    print(f"All configs: {node_name_lower_dict.keys()}")
            # qlogger logging
            if len(qlogger_ans) > 0:
                self.qlogger.info(
                    json.dumps({"question": "Bool\t" + node_names, "answer": qlogger_ans})
                )
        return new_menu_nodes_dict.values()

    def process_binary(self, nodes: list[klib.MenuNode]):
        pass

    def process_trinary(self, nodes: list[klib.MenuNode]):
        pass

    def process_multiple(self, nodes: list[klib.MenuNode]):
        for node in nodes:
            choices: list[klib.MenuNode] = []
            node_list = self.get_menunodes(node)
            for choice in node_list:
                choices.append(choice)
            answer = self.chatter.ask_multiple_option(
                "\n".join([self.get_node_name(choice) for choice in choices]),
                self.kg.gen_configs_knowledge(choices, self.target),
            ).strip()
            if answer.startswith("[") and answer.endswith("]"):
                answer = answer[1:-1]
            # find selected answer
            found = False
            # record answer for qlogger
            qlogger_ans = None
            for choice in node_list:
                if answer == self.get_simple_node_name(choice):
                    qlogger_ans = answer
                    # select current option
                    if choice.item.tri_value != 2:
                        # current choice is not selected
                        self.logger.info(
                            f"CONFIG_{choice.item.name}=y"
                            # f"Config changed: {node.item.name} selects {choice.item.name}"
                        )
                        choice.item.set_value(2)
                    found = True
            if not found:
                print(f"Error: answer {answer} does not exist")
                configs = "\n".join(
                    [self.get_simple_node_name(choice) for choice in choices]
                )
                print(f"All configs: {configs}")
            else:
                # qlogger
                self.qlogger.info(
                    json.dumps({"question": "Choice\t" + "\n".join([self.get_node_name(choice) for choice in choices]), "answer": qlogger_ans})
                )

    def process_value(self, nodes: list[klib.MenuNode]):
        # strings passed to LLM is in form of
        # stack depot hash size (12 => 4KB, 20 => 1024KB) (STACK_HASH_ORDER) (20)\n
        # etc.
        help_info_list = []
        node_info_list = []
        prompt_to_node_dict = {}

        # this code is from menuconfig.py
        def get_help_info_from_sym(sym: klib.Symbol):
            tristate_name = ["n", "m", "y"]
            prompt = f"Value for {sym.name}"
            if sym.type in (klib.BOOL, klib.TRISTATE):
                prompt += f" (available: {', '.join(tristate_name[val] for val in sym.assignable)})"
            prompt += ":"
            return f"{str(sym)}\n{prompt}"

        for node in nodes:
            item = node.item
            help_info_list.append(get_help_info_from_sym(item))
            node_info_list.append(f"{node.prompt[0]} ({item.str_value})")
            prompt_to_node_dict[node.prompt[0]] = node

        # call LLM
        answers = self.chatter.ask_value_option(
            "\n".join(help_info_list), "\n".join(node_info_list)
        )
        # record answer for qlogger
        qlogger_ans = []
        # answers is a list of tuple, where tuple[0] is prompt and tuple[1] is value
        # postprocess: set the value
        for answer in answers:
            if answer[0] in prompt_to_node_dict.keys():
                node = prompt_to_node_dict[answer[0]]
                qlogger_ans.append({"config": answer[0], "value": answer[1]})
                if node.item.str_value == answer[1]:
                    continue
                # log
                self.logger.info(
                    f"CONFIG_{node.item.name}={answer[1]}"
                    # f"Config changed: {node.item.name} from state '{node.item.str_value}' to '{answer[1]}'"
                )
                prompt_to_node_dict[answer[0]].item.set_value(answer[1])
        # qlogger
        if len(qlogger_ans) > 0:
            self.qlogger.info(json.dumps({"question": "Value\t" + "\n".join(node_info_list), "answer": qlogger_ans}))

    def save(self, path: str):
        self.kconfig.write_config(path)
        os.rename("Config.log", path + ".log")
        os.rename("QA.log", "QA_" + path + ".log")

    def get_node_name(self, node: klib.MenuNode):
        name = node.prompt[0]
        item = node.item
        if hasattr(item, "name"):
            name = f"{name} ({item.name})"
        return name

    def get_simple_node_name(self, node: klib.MenuNode):
        item = node.item
        if hasattr(item, "name"):
            return item.name
        else:
            return node.prompt[0]
