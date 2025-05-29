import Config as C
from ConfigTree import Config
from LLM import ChatContext
import os
import logging

import argparse


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", default=C.SRCTREE, type=str)
    parser.add_argument("-t", "--target", type=str)
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument("-o", "--output", default="config_output", type=str)
    parser.add_argument("-m", "--mode", default="hybrid", type=str)
    parser.add_argument("--use-knowledge", default=1, type=int)
    parser.add_argument("--arch", default="x86", type=str)
    parser.add_argument("--srcarch", default="x86", type=str)
    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    C.DEBUG = args.debug

    if not bool(args.use_knowledge):
        print("Generating config without knowledge")

    # disable openai output
    logging.getLogger("openai").setLevel(logging.ERROR)
    logging.getLogger("httpx").setLevel(logging.ERROR)

    # set OS environment
    os.environ["srctree"] = args.path
    os.environ["CC"] = C.CC
    os.environ["LD"] = C.LD
    os.environ["ARCH"] = args.arch
    os.environ["SRCARCH"] = args.srcarch

    # init llm chatter
    chatter = ChatContext(
        args.target, C.KEY, model="gpt-4o-mini"
    )

    # read config and process
    config = Config(
        f"{args.path}/Kconfig",
        chatter,
        args.target,
        kg_search_mode=args.mode,
        use_knowledge=bool(args.use_knowledge),
        config_path=f"{args.path}/.config",
    )
    config.run()
    config.save(args.output)
    print("Money spent on LLM: ", chatter.price)


if __name__ == "__main__":
    main()