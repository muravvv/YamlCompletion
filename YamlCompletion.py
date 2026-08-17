import base64
import mimetypes
import sys
from typing import Any

import openai
import yaml
import argparse
import os
import time

def main():
    retCode = 1
    parser = argparse.ArgumentParser()
    parser.add_argument("yaml_file", help="yaml file with llm request")
    parser.add_argument("-m", "--model", help="model name or provider/model", default="default")
    parser.add_argument("-p", "--provider", help="provider (default - openai if -a is used)")
    parser.add_argument("-a", "--api-base", help="api base")
    parser.add_argument("-o", "--out-file", help="write llm output to file")
    parser.add_argument("-n", "--no-print-response", help="do not print response to standard output", action="store_true")
    parser.add_argument("--dry-run", help="do not run real request", action="store_true")
    parser.add_argument("--timeout", help="timeout in seconds for completion requests", default=3600, type=int)
    parser.add_argument("--no-usage", help="do not print usage info", action="store_true")
    parser.add_argument("--no-time", help="do not print request time", action="store_true")
    parser.add_argument("--remote-cost-map", help="update model cost map (model_prices_and_context_window.json) from remote server", action="store_true")
    parser.add_argument("--version", action="version", version='YamlCompletion version 1')
    args = parser.parse_args()

    if "/" not in args.model:
        if not args.provider and not args.api_base:
            parser.error("--provider or --api-base must be specified")
        elif not args.provider:
            args.provider = "openai"
        args.model = f"{args.provider}/{args.model}"
    else:
        if args.provider:
            parser.error("Provider name is specified twice: in --model and in --provider")

    if not args.remote_cost_map:
        os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "true"

    import litellm

    completionArgs: dict[str, Any] = {
        "stream": True,
        "timeout": args.timeout,
    }
    if not args.no_usage:
        completionArgs["stream_options"] = {"include_usage": True}

    yaml_file_dir = os.path.dirname(os.path.abspath(args.yaml_file))

    def base64file_constructor(loader: yaml.Loader, node: yaml.nodes.ScalarNode):
        with open(os.path.join(yaml_file_dir,str(loader.construct_scalar(node))), "rb") as binfile:
            return base64.b64encode(binfile.read()).decode("ascii")

    def base64image_constructor(loader: yaml.Loader, node: yaml.nodes.ScalarNode):
        filename = os.path.join(yaml_file_dir, str(loader.construct_scalar(node)))
        try:
            mt = mimetypes.guess_file_type(filename)[0]
        except AttributeError:
            mt = mimetypes.guess_type(filename)[0]
        with open(filename, "rb") as binfile:
            return f"data:{mt};base64,{base64.b64encode(binfile.read()).decode("ascii")}"

    loader = yaml.Loader
    loader.add_constructor("!base64file", base64file_constructor)
    loader.add_constructor("!base64image", base64image_constructor)

    with open(args.yaml_file, "r", encoding="utf8") as yaml_file:
        try:
            yamlArgs = yaml.load(yaml_file, Loader=loader)
        except yaml.YAMLError as exc:
            print("Error in YAML file:", exc)
            return 1
        completionArgs.update(yamlArgs)

    completionArgs["model"] = args.model
    if args.api_base:
        if args.provider == "openai" and  "OPENAI_API_KEY" not in os.environ and "://127.0.0.1" in args.api_base:
            os.environ["OPENAI_API_KEY"] = "none"

        completionArgs["api_base"] = args.api_base

    outFile = None
    if args.out_file:
        outFile = open(args.out_file, "w", encoding="utf8")

    try:
        if args.dry_run:
            argsstr = f"Request: {completionArgs!r}"
            completionArgs["mock_response"] = argsstr

        prevIsThinking = False
        prevIsToolCall = False
        prevToolCallIndex = None
        prevToolCallId = None
        prevToolCallObj = None
        prevToolCallField = None
        usage = None

        toolCallIndexNotChanged = False
        toolCallIdNotChanged = False

        def output(content):
            if not args.no_print_response:
                print(content, end="", flush=True)
            if outFile:
                outFile.write(content)
                outFile.flush()

        def outputLine(content):
            if not args.no_print_response:
                print(content, flush=True)
            if outFile:
                outFile.write(content+"\n")
                outFile.flush()

        def endOfThinking():
            nonlocal prevIsThinking
            outputLine("\n[end of reasoning_content]")
            prevIsThinking = False

        def endOfToolCall():
            nonlocal prevIsToolCall
            nonlocal prevToolCallField
            if prevToolCallField is not None:
                output("'")
                prevToolCallField = None
            outputLine("\n[end of tool_call]")
            prevIsToolCall = False


        start_time = time.monotonic()
        try:
            first_token_time = None
            for chunk in litellm.completion(**completionArgs):
                if first_token_time is None:
                    first_token_time = time.monotonic()
                #print(f"Chunk: {chunk!r}")
                #print(f"Delta: {chunk.choices[0].delta!r}")
                if hasattr(chunk.choices[0].delta, "reasoning_content") and chunk.choices[0].delta.reasoning_content:
                    if prevIsToolCall:
                        endOfToolCall()
                    if not prevIsThinking:
                        outputLine("[reasoning_content]")
                    output(chunk.choices[0].delta.reasoning_content)
                    prevIsThinking = True
                if hasattr(chunk.choices[0].delta, "tool_calls") and chunk.choices[0].delta.tool_calls:
                    if prevIsThinking:
                        endOfThinking()
                    if not prevIsToolCall:
                        output("[tool_call]")
                    def process_tool_call_delta(obj, field, value):
                        if value is None:
                            return
                        nonlocal prevToolCallObj
                        nonlocal prevToolCallField
                        if prevToolCallField is not None and field != prevToolCallField:
                            output("'")
                        if obj != prevToolCallObj:
                            output(f"\n  {obj}:")
                            prevToolCallObj = obj
                        if field != prevToolCallField:
                            output(f"\n    {field}: '")
                            prevToolCallField = field
                        output(value)

                    for tool_call in chunk.choices[0].delta.tool_calls:
                        if tool_call.index != prevToolCallIndex or (tool_call.id is not None and tool_call.id != prevToolCallId):
                            if tool_call.index == prevToolCallIndex:
                                toolCallIndexNotChanged = True
                            if tool_call.id == prevToolCallId:
                                toolCallIdNotChanged = True
                            if prevToolCallField is not None:
                                output("'")
                                prevToolCallField = None
                            output(f"""
-
  id: '{tool_call.id}'
  type: {tool_call.type}""")
                            prevToolCallIndex = tool_call.index
                            prevToolCallId = tool_call.id
                        if tool_call.type == 'function':
                            process_tool_call_delta('function', 'name', tool_call.function.name)
                            process_tool_call_delta('function', 'arguments', tool_call.function.arguments)

                    prevIsToolCall = True

                if chunk.choices[0].delta.content:
                    if prevIsThinking:
                        endOfThinking()
                    if prevIsToolCall:
                        endOfToolCall()
                    output(chunk.choices[0].delta.content)
                if hasattr(chunk, "usage") and chunk.usage:
                    usage = chunk.usage
                if chunk.choices[0].finish_reason:
                    if prevIsThinking:
                        endOfThinking()
                    if prevIsToolCall:
                        endOfToolCall()
                    print(f"\n\nFinished by {chunk.choices[0].finish_reason}")
            if prevIsThinking:
                endOfThinking()
            if prevIsToolCall:
                endOfToolCall()
            retCode = 0
        except openai.OpenAIError as err:
            print(f"\n\nLiteLLM error: {err}")
        except KeyboardInterrupt:
            print(f"\n\nTerminated by user request")

        end_time = time.monotonic()

        if toolCallIndexNotChanged:
            print("Warning! ChatCompletionDeltaToolCall.index not changed")
        if toolCallIdNotChanged:
            print("Warning! ChatCompletionDeltaToolCall.id not changed")

        prompt_tokens_cnt = 0
        completion_tokens_cnt = 0
        if usage:
            prompt_tokens_cnt = usage.prompt_tokens
            completion_tokens_cnt = usage.completion_tokens
            if usage.prompt_tokens_details:
                prompt_details = [f"{name}: {value}" for name, value in dict(usage.prompt_tokens_details).items() if value is not None]
                if hasattr(usage.prompt_tokens_details, "cached_tokens"):
                    prompt_tokens_cnt -= usage.prompt_tokens_details.cached_tokens
            else:
                prompt_details = []
            if usage.completion_tokens_details:
                completion_details = [f"{name}: {value}" for name, value in dict(usage.completion_tokens_details).items() if value is not None]
            else:
                completion_details = []
            if prompt_details:
                prompt_details = f" ({", ".join(prompt_details)})"
            else:
                prompt_details = ""
            if completion_details:
                completion_details = f" ({", ".join(completion_details)})"
            else:
                completion_details = ""
            print(f"\n{usage.prompt_tokens} prompt tokens{prompt_details}\n{usage.completion_tokens} completion tokens{completion_details}\n{usage.total_tokens} total tokens")
        if not args.no_time:
            ttft = first_token_time-start_time if first_token_time is not None else end_time-start_time
            gentm = end_time-first_token_time if first_token_time is not None else 0
            print(f"\nTotal time: {(end_time-start_time):.3f} s")
            print(f"TTFT:       {ttft:.3f} s" + (f" ({prompt_tokens_cnt/ttft:.2f} tok/s)" if (prompt_tokens_cnt>100 and ttft>2.0) else ""))
            print(f"Generation: {gentm:.3f} s" + (f" ({completion_tokens_cnt/gentm:.2f} tok/s)" if (completion_tokens_cnt>0 and gentm>0.5) else ""))
        return retCode
    finally:
        if outFile:
            outFile.close()

if __name__ == "__main__":
    sys.exit(main())
