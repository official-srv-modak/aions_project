import os
import re
from typing import Any, Dict, List


class AIONPropertyError(Exception):
    """Raised when an unidentified property is found in the .aion file."""
    pass


class AIONParseError(Exception):
    """Raised when the syntax of the .aion file is invalid."""
    pass


class AIONS:
    # Expanded properties to include LangChain's args_schema and the new link property
    ALLOWED_PROPERTIES = {"name", "function", "description", "args_schema", "link"}

    @classmethod
    def loads(cls, aion_text: str, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        aion_text = aion_text.strip()

        if not (aion_text.startswith("[") and aion_text.endswith("]")):
            raise AIONParseError("AION definition must be an array enclosed in [ ]")

        tools = []
        block_pattern = re.compile(r'\{([^{}]*\{[^{}]*\}[^{}]*|[^{}]*)\}')
        blocks = block_pattern.findall(aion_text)

        for block in blocks:
            tool_data = {}
            found_properties = re.findall(r'([a-zA-Z0-9_-]+)\s*-->', block)

            for prop in set(found_properties):
                if prop not in cls.ALLOWED_PROPERTIES and not prop.startswith("arg-") and not prop.startswith(
                        "return-"):
                    raise AIONPropertyError(f"Error: Property [{prop}] cannot be identified.")

            # Extract Name
            name_match = re.search(r'name\s*-->\s*"([^"]+)"', block)
            if name_match:
                tool_data['name'] = name_match.group(1)

            # Extract Description
            desc_match = re.search(r'description\s*-->\s*"([^"]+)"', block)
            if desc_match:
                tool_data['description'] = desc_match.group(1)

            # Extract Link (New Property)
            link_match = re.search(r'link\s*-->\s*"([^"]+)"', block)
            if link_match:
                tool_data['link'] = link_match.group(1)

            # Extract Args Schema
            schema_match = re.search(r'args_schema\s*-->\s*"([^"]+)"', block)
            if schema_match:
                schema_str = schema_match.group(1)
                tool_data['args_schema_str'] = schema_str
                if context:
                    try:
                        tool_data['args_schema'] = eval(schema_str, context)
                    except Exception as e:
                        raise AIONParseError(
                            f"Could not parse schema '{schema_str}'. Ensure it is in context. Error: {e}")

            # Extract Function Block
            func_match = re.search(r'function\s*-->\s*"([^"]+)"\s*-->\s*\{([^}]+)\}', block)
            if func_match:
                func_str = func_match.group(1)
                inner_block = func_match.group(2)
                func_data = {"raw_string": func_str, "args": {}, "returns": {}}

                if context:
                    try:
                        func_data["executable"] = eval(func_str, context)
                    except Exception as e:
                        raise AIONParseError(
                            f"Could not parse function '{func_str}'. Ensure all dependencies are in context. Error: {e}")

                inner_items = re.findall(r'(arg-\d+|return-\d+)\s*-->\s*"([^"]*)"', inner_block)
                for key, val in inner_items:
                    if key.startswith("arg-"):
                        func_data["args"][key] = val
                    elif key.startswith("return-"):
                        func_data["returns"][key] = val

                tool_data['function'] = func_data

            # Validation: Must have at least a function OR a link
            if 'function' not in tool_data and 'link' not in tool_data:
                raise AIONParseError(
                    f"AION element '{tool_data.get('name', 'Unknown')}' must contain at least 'function' or 'link'.")

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
    def dumps(cls, tools: List[Dict[str, Any]]) -> str:
        aion_strings = []
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

            if 'link' in tool:
                aion_str += f'   link --> "{tool["link"]}",\n'

            if 'args_schema_str' in tool:
                aion_str += f'   args_schema --> "{tool["args_schema_str"]}",\n'

            aion_str += f'   description --> "{tool.get("description", "")}"\n'
            aion_str += "  }"
            aion_strings.append(aion_str)

        return "[\n" + ",\n".join(aion_strings) + "\n]"

    @classmethod
    def dump(cls, tools: List[Dict[str, Any]], filepath: str):
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(cls.dumps(tools))

    @classmethod
    def get_langchain_tools(cls, source_path: str, context: Dict[str, Any]) -> list:
        try:
            from langchain.agents import Tool
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

            # Dynamically determine the execution strategy based on the presence of func/link
            if "function" in tool_config:
                executable_func = tool_config["function"]["executable"]
            else:
                # If only a link is provided, create a dummy function that returns the URL for the LLM
                link_url = tool_config.get("link", "")
                executable_func = lambda *args, url=link_url,
                                         **kwargs: f"Action unavailable. Please refer to documentation: {url}"

            # Append the link to the description if it exists so the AI knows about it
            description = tool_config["description"]
            if "link" in tool_config:
                description += f"\nDocumentation Link: {tool_config['link']}"

            args_schema = tool_config.get("args_schema")

            tool = Tool(
                name=tool_name,
                func=executable_func,
                description=description,
                args_schema=args_schema
            )
            langchain_tools.append(tool)

        return langchain_tools