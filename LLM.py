from openai import OpenAI
import logging
import re

import Config as C


class ChatContext:
    def __init__(
        self,
        opt_target: str,
        api_key: str,
        api_url: str = "https://api.ai.cs.ac.cn/v1",
        model: str = "gpt-3.5-turbo-1106",
    ):
        """
        You should choose an optimization target to start using LLM.
        Target is a string, for example, it could be "the Dhrystone and Whetstone scores in UnixBench", so that LLM
        can optimize config towards this goal.
        Then you should pass an optimization description to describe what the target does and how to improve it.
        """
        # init logging
        self.logger = logging.getLogger(__name__)

        # init LLM context
        self.client = OpenAI(base_url=api_url, api_key=api_key)
        self.model = model

        self.menu_prompt = """
        KNOWLEDGE = {}

        TARGET = {}

        DIRECTORIES = {}

        Q: "I want to explore the config options related to TARGET in the Linux kernel configurations. Please choose the directories concerned with TARGET in the DIRECTORIES as much as possible. You can reference the knowledge in KNOWLEDGE. I also have to gurantee the success boot of the OS after selecting. Answer the in the following form, with out any explanation, just answer in pure text form, give me directory names with index in my given DIRECTORIES, each line represents a single directory like this:
        [directory_name_1]
        [directory_name_2]
        ....
        [directory_name_n]
        """
        self.on_off_prompt = """
        KNOWLEDGE = {}

        TARGET = {}

        CONFIGS = {}

        Q: "I want to explore the config options related to TARGET in the Linux kernel configurations. Please choose the configs concerned with TARGET in the CONFIGS as much as possible. For each concerned config related to TARGET, you should determine whether it will increase or decrease TARGET. If it increases TARGET, output [CONFIG increase]. If it decreases TARGET, output [CONFIG decrease]. If a config is not related to TARGET, output [CONFIG - cannot determine impact without specific context] You can reference the knowledge in KNOWLEDGE. I also have to gurantee the success boot of the OS after selecting. Answer the in the following form, with out any explanation, just answer in pure text form, give me the config names in my given CONFIGS, each line represents a single config like this:
        [config_name_1 increase]
        [config_name_2 decrease]
        ....
        [config_name_n increase]
        """
        self.multiple_option_prompt = """
        KNOWLEDGE = {}

        TARGET = {}

        CONFIGS = {}

        Q: "I want to explore the config options related to TARGET in the Linux kernel configurations. The CONFIGS I gave you are choices of a config, and you need to choose which config is most likely related to TARGET. Give me only one config in my given CONFIGS. You can reference the knowledge in KNOWLEDGE. I also have to gurantee the success boot of the OS after selecting. Answer the in the following form, with out any explanation, just answer in pure text form, each line represents a single config like this:
        [config_name]
        """
        
        self.value_option_prompt = (
            f"TARGET = {opt_target}\n\n"
            f"I'm looking for the Linux kernel's menuconfig options that could potentially affect TARGET."
            f"I have listed some numeric config options listed in menuconfig, along with their corresponding value ranges.\n"
            f"For each option, please select a value that may help improve TARGET." 
            f"If the option is not related to TARGET, reset it to the defalut value. \n"
            f"Config input format:\n "
            f"[option name] (default value)  \n"
            f"Value output format: \n" 
            f"[option name] (recommended  value)   \n"
            f"For instance, if you are given:\n"
            f"'maximum CPU number(1=>2 2=>4)  (cpunum) (1)\n" 
            f"Your response would be:\n"
            f"'maximum CPU number(1=>2 2=>4)  (cpunum) (2)\n"
            f"Because when the CPU number is more, the speed is usually better.\n"
            f"Attention! Please provide your recommended values without extra explanations or additional details.\n"
            f"Only suggest options that could possibly help TARGET, and do not add units next to the numbers.\n"
            f"Below are the numeric config options for your recommendations: "
        )
        self.new_value_option_prompt = """
        """

        # init regex pattern used to extract answers from the answers
        self.menu_ans_pattern = re.compile(
            r"^(\d+)\s+(\[\s+\]|\[\*\]|\(.*?\)|\<.*?\>|\({.*?}\)|\-\*\-|\-\-\>)?\s*([A-Za-z].*?)\s*($|\n)"
        )
        self.value_ans_pattern = re.compile(
            r"(.*?)\s+([\[\(\<\{]?(?:on|off|M|\d+|\-\-\>)[\]\)\}\>]?)\s*($|\n)"
        )

        # init price accumulator
        self.price = 0.0

        # init logger
        logging.basicConfig(
            level=logging.INFO,
            datefmt="%Y/%m/%d %H:%M:%S",
        )
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(logging.FileHandler("LLM.log", mode="w"))
        self.logger.propagate = False

        self.target = opt_target

    def chat(self, content: list[dict]) -> str:
        # log
        self.logger.info(f"LLM REQUEST:\n{content}")
        response = self.client.chat.completions.create(
            messages=content, model=self.model
        )
        # add prices
        self.price += (
            int(response.usage.prompt_tokens) * self.get_prompt_price()
            + int(response.usage.completion_tokens) * self.get_completion_price()
        )
        # log
        self.logger.info(f"LLM RESPONSE:\n{response.choices[0].message.content}")
        return response.choices[0].message.content

    def ask_menu(self, content: str, knowledge: str) -> list[int]:
        conversation = [
            {
                "role": "user",
                "content": self.menu_prompt.format(knowledge, self.target, content),
            }
        ]
        answer = self.chat(conversation)
        if answer.startswith("```") or answer.endswith("```"):
            answer = answer.strip("```")
        if answer.startswith("["):
            answer = answer.strip("[")
        if answer.endswith("]"):
            answer = answer.strip("]")
        answers = answer.split("\n")
        matches = []
        for ans in answers:
            index = ans.split(" ")[0]
            if index.isspace():
                continue
            try:
                index = int(index)
            except ValueError:
                matches.append(index)
                print("Error casting menu index: " + index)
                continue
            matches.append(index)
        return matches

    def ask_on_off_option(self, content: str, knowledge: str) -> dict[str:int]:
        conversation = [
            {
                "role": "user",
                "content": self.on_off_prompt.format(knowledge, self.target, content),
            }
        ]
        """
        conversation = [
            {"role": "user", "content": f"{self.on_off_prompt[0]} {content}"}
        ]
        conversation.append({"role": "assistant", "content": self.chat(conversation)})
        conversation.append({"role": "user", "content": self.on_off_prompt[1]})
        conversation.append({"role": "assistant", "content": self.chat(conversation)})
        conversation.append({"role": "user", "content": self.on_off_prompt[2]})
        """
        # answer is a concatenation of the following three forms
        # xxx-config increase
        # xxx-config decrease
        # xxx-config - cannot determine impact without specific context
        answer = self.chat(conversation)
        # extract options to be open and close
        result_dict = {}
        # 'lines' is a list, for example, lines = ['increase', 'xxx-config', 'decrease', 'xxx-config']
        lines = answer.split("\n")
        for line in lines:
            line = line[1:-1]
            blocks = line.split(" ")
            if len(blocks) != 2:
                # line is in form xxx-config - cannot determine impact without specific context
                # skip
                continue
            if blocks[1] == "increase":
                result_dict[blocks[0]] = 2
            elif blocks[1] == "decrease":
                result_dict[blocks[0]] = 0
            else:
                print("LLM gives wrong answer: " + line)
        return result_dict

    def ask_multiple_option(self, content: str, knowledge: str) -> str:
        answer = self.chat(
            [
                {
                    "role": "user",
                    "content": self.multiple_option_prompt.format(
                        knowledge, self.target, content
                    ),
                }
            ]
        ).strip("\n")
        if answer.startswith("[") and answer.endswith("]"):
            return answer[1:-1]
        elif answer.startswith("```") and answer.endswith("```"):
            return answer[3:-3]
        else:
            return answer

    def ask_binary_option(self, content: str) -> str:
        return self.chat(
            [{"role": "user", "content": f"{self.binary_option_prompt} {content}"}]
        )

    def ask_trinary_option(self, content: str) -> str:
        return self.chat(
            [{"role": "user", "content": f"{self.trinary_option_prompt} {content}"}]
        )

    def ask_value_option(self, help_info: str, content: str) -> list[tuple[str, str]]:
        answer = self.chat(
            [
                {
                    "role": "user",
                    "content": f"Here is value options information: "
                    f"{help_info}\n{self.value_option_prompt} {content}",
                }
            ]
        )
        # get useful message from answer
        matches = self.value_ans_pattern.findall(answer)
        result = []
        for m in matches:
            # m is in form of ('Warn for stack frames larger than (FRAME_WARN)', '(512)', '')
            result.append((m[0], m[1][1:-1]))
        return result

    def gen_target(self, origin_target: str) -> str:
        """
        Args:
            origin_target (str): target given by user

        Returns:
            processed_target (str): detailed target
        """
        pass

    def get_prompt_price(self):
        return 0.008 / 1000

    def get_completion_price(self):
        return 0.016 / 1000
