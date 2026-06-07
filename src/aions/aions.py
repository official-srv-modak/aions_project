import os
import re
from typing import Any, Dict, List, Optional
from aion_parse_error import AIONParseError

try:
    from pydantic import create_model, Field, BaseModel
except ImportError:
    BaseModel = None

class AIONS:
    @classmethod
    def loads(cls, aion_text: str, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        aion_text = aion_text.strip()

        if not (aion_text.startswith("[") and aion_text.endswith("]")):
            raise AIONParseError("AION definition must be an array enclosed in [ ]")

        blocks = []
        current_block = ""
        brace_level = 0
        in_block = False

        # Strip the outer array brackets to just iterate over the objects
        inner_text = aion_text[1:-1].strip()

        for char in inner_text:
            if char == '{':
                if brace_level == 0:
                    in_block = True
                brace_level += 1

            if in_block:
                current_block += char

            if char == '}':
                brace_level -= 1
                if brace_level == 0 and in_block:
                    blocks.append(current_block)
                    current_block = ""
                    in_block = False

        tools = []
        for block in blocks:
            tool_data = {}

            # Extract Name (Fails fast with a clear error if missing, rather than a KeyError later)
            name_match = re.search(r'name\s*-->\s*"([^"]+)"', block)
            if not name_match:
                raise AIONParseError(f"Found a malformed AION block missing the 'name' property:\n{block[:50]}...")
            tool_data['name'] = name_match.group(1)

            # Extract Description
            desc_match = re.search(r'description\s*-->\s*"([^"]+)"', block)
            if desc_match:
                tool_data['description'] = desc_match.group(1)

            # Extract Link
            link_match = re.search(r'link\s*-->\s*"([^"]+)"', block)
            if link_match:
                tool_data['link'] = link_match.group(1)

            # Extract Native Args Schema Block
            schema_block_match = re.search(r'args_schema\s*-->\s*\{([^}]+)\}', block)
            if schema_block_match:
                inner_schema = schema_block_match.group(1)
                schema_items = re.findall(r'([a-zA-Z0-9_-]+)\s*-->\s*"([^"]*)"', inner_schema)
                tool_data['args_schema_raw'] = schema_items

                if BaseModel:
                    fields = {}
                    for field_name, field_def in schema_items:
                        parts = [p.strip() for p in field_def.split('|')]

                        # Map type
                        type_str = parts[0].lower() if parts else "str"
                        type_map = {'str': str, 'int': int, 'float': float, 'bool': bool, 'list': list, 'dict': dict}
                        field_type = type_map.get(type_str, str)

                        # Parse defaults and description
                        default_val = ...  # Ellipsis means 'required' in Pydantic
                        description = ""

                        if len(parts) == 2:
                            description = parts[1]
                        elif len(parts) >= 3:
                            if parts[1].startswith("default="):
                                raw_val = parts[1].split("=", 1)[1].strip("'\" ")
                                default_val = None if raw_val.lower() == "none" else raw_val
                            description = parts[2]

                        fields[field_name] = (field_type, Field(default=default_val, description=description))

                    # Dynamically generate the Pydantic Model
                    model_name = f"{tool_data.get('name', 'Dynamic')}Input"
                    tool_data['args_schema'] = create_model(model_name, **fields)

            # Extract Function Block
            func_match = re.search(r'function\s*-->\s*"([^"]+)"\s*-->\s*\{([^}]+)\}', block)
            if func_match:
                func_str = func_match.group(1)
                inner_block = func_match.group(2)
                func_data = {"raw_string": func_str, "args": {}, "returns": {}}

                if context is not None:
                    try:
                        func_data["executable"] = eval(func_str, context)
                    except Exception as e:
                        raise AIONParseError(
                            f"Could not parse function '{func_str}'. Ensure dependencies are passed in context. Error: {e}")

                inner_items = re.findall(r'(arg-\d+|return-\d+)\s*-->\s*"([^"]*)"', inner_block)
                for key, val in inner_items:
                    if key.startswith("arg-"):
                        func_data["args"][key] = val
                    elif key.startswith("return-"):
                        func_data["returns"][key] = val

                tool_data['function'] = func_data

            # Validation: Must have at least a function OR a link
            if 'function' not in tool_data and 'link' not in tool_data:
                raise AIONParseError(f"AION element '{tool_data['name']}' must contain at least 'function' or 'link'.")

            tools.append(tool_data)

        return tools

    @classmethod
    def load(cls, filepath: str, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        with open(filepath, 'r', encoding='utf-8') as f:
            return cls.loads(f.read(), context)

    @classmethod
    def load_dir(cls, dirpath: str, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        all_tools = []
        for filename in os.listdir(dirpath):
            if filename.endswith(".aion"):
                filepath = os.path.join(dirpath, filename)
                all_tools.extend(cls.load(filepath, context))
        return all_tools

    @classmethod
    def dumps(cls, tools: List[Dict[str, Any]], system_prompt: Optional[str] = None) -> str:
        """Serializes tools (and an optional system prompt) into an AION formatted string."""
        aion_strings = []

        # 1. Add the System Prompt as the very first array element
        if system_prompt:
            sp_str = f'  system_prompt --> """\n{system_prompt}\n  """'
            aion_strings.append(sp_str)

        # 2. Add all the tool objects
        for tool in tools:
            aion_str = "  {\n"
            aion_str += f'   name --> "{tool.get("name", "")}",\n'

            if 'function' in tool:
                func = tool.get("function", {})
                aion_str += f'   function --> "{func.get("raw_string", "")}" --> {{\n'
                for arg_k, arg_v in func.get("args", {}).items():
                    aion_str += f'        {arg_k} --> "{arg_v}",\n'
                for ret_k, ret_v in func.get("returns", {}).items():
                    aion_str += f'        {ret_k} --> "{ret_v}",\n'
                aion_str = aion_str.rstrip(",\n") + "\n   },\n"

            if 'args_schema_raw' in tool:
                aion_str += '   args_schema --> {\n'
                for k, v in tool['args_schema_raw']:
                    aion_str += f'        {k} --> "{v}",\n'
                aion_str = aion_str.rstrip(",\n") + "\n   },\n"

            if 'link' in tool:
                aion_str += f'   link --> "{tool["link"]}",\n'

            aion_str += f'   description --> "{tool.get("description", "")}"\n'
            aion_str += "  }"
            aion_strings.append(aion_str)

        # 3. Join with commas. This naturally puts the comma after the system_prompt
        # and between every subsequent tool block.
        return "[\n" + ",\n".join(aion_strings) + "\n]"

    @classmethod
    def dump(cls, tools: List[Dict[str, Any]], filepath: str, system_prompt: Optional[str] = None):
        """Writes tools and an optional system prompt to an AION file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(cls.dumps(tools, system_prompt=system_prompt))

    @classmethod
    def get_langchain_tools(cls, source_path: str, context: Dict[str, Any]) -> list:
        try:
            from langchain.tools import Tool, StructuredTool
        except ImportError:
            raise ImportError("LangChain is not installed. Run 'pip install langchain'")

        if os.path.isdir(source_path):
            parsed_data = cls.load_dir(source_path, context)
        elif os.path.isfile(source_path):
            parsed_data = cls.load(source_path, context)
        else:
            raise FileNotFoundError(f"Source '{source_path}' is neither a valid file nor directory.")

        langchain_tools = []
        for tool_config in parsed_data:
            tool_name = tool_config["name"]

            # Dynamically determine the execution strategy
            if "function" in tool_config:
                executable_func = tool_config["function"]["executable"]
            else:
                link_url = tool_config.get("link", "")
                executable_func = lambda *args, url=link_url, **kwargs: f"Action unavailable. Please refer to documentation: {url}"

            # Append the link to the description if it exists
            description = tool_config["description"]
            if "link" in tool_config:
                description += f"\nDocumentation Link: {tool_config['link']}"

            args_schema = tool_config.get("args_schema")

            # Use StructuredTool to handle the dynamic Pydantic models cleanly
            if args_schema:
                tool = StructuredTool.from_function(
                    func=executable_func,
                    name=tool_name,
                    description=description,
                    args_schema=args_schema
                )
            else:
                tool = Tool(
                    name=tool_name,
                    func=executable_func,
                    description=description
                )

            langchain_tools.append(tool)

        return langchain_tools

    # ====== ENFORCING THE 1-PROMPT RULE ======
    @classmethod
    def get_system_prompt(cls, source_path: str) -> Optional[str]:
        """Extracts the singular global system_prompt from an .aion file or directory.
           Strictly enforces a maximum of ONE system prompt."""

        def extract_prompt(content: str) -> Optional[str]:
            # Find all instances
            matches_triple = re.findall(r'system_prompt\s*-->\s*"""(.*?)"""', content, re.DOTALL)
            matches_single = re.findall(r'system_prompt\s*-->\s*"([^"]+)"', content)

            total_prompts = len(matches_triple) + len(matches_single)

            # The Enforcement Rule
            if total_prompts > 1:
                raise AIONParseError(
                    "Multiple system prompts found. An AION file can contain at most ONE system_prompt.")

            if matches_triple:
                return matches_triple[0].strip()
            if matches_single:
                return matches_single[0].strip()

            return None

        # Directory logic
        if os.path.isdir(source_path):
            all_prompts = []
            for filename in os.listdir(source_path):
                if filename.endswith(".aion"):
                    with open(os.path.join(source_path, filename), 'r', encoding='utf-8') as f:
                        prompt = extract_prompt(f.read())
                        if prompt:
                            all_prompts.append(prompt)

            if len(all_prompts) > 1:
                raise AIONParseError(
                    "Multiple system prompts found across directory. Only one global system_prompt is allowed.")
            return all_prompts[0] if all_prompts else None

        # Single file logic
        elif os.path.isfile(source_path):
            with open(source_path, 'r', encoding='utf-8') as f:
                return extract_prompt(f.read())

        else:
            raise FileNotFoundError(f"Source '{source_path}' is neither a valid file nor directory.")