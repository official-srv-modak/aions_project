import os
import re
from typing import Any, Dict, List

try:
    from pydantic import create_model, Field, BaseModel
except ImportError:
    BaseModel = None


class AIONPropertyError(Exception):
    """Raised when an unidentified property is found in the .aion file."""
    pass


class AIONParseError(Exception):
    """Raised when the syntax of the .aion file is invalid."""
    pass


class AIONS:
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
                        "return-") and not prop in block:
                    pass  # Relaxed to allow schema field names

            # Extract Basic Properties
            name_match = re.search(r'name\s*-->\s*"([^"]+)"', block)
            if name_match: tool_data['name'] = name_match.group(1)

            desc_match = re.search(r'description\s*-->\s*"([^"]+)"', block)
            if desc_match: tool_data['description'] = desc_match.group(1)

            link_match = re.search(r'link\s*-->\s*"([^"]+)"', block)
            if link_match: tool_data['link'] = link_match.group(1)

            # --- NEW: Extract Native Args Schema Block ---
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

                if context:
                    try:
                        func_data["executable"] = eval(func_str, context)
                    except Exception as e:
                        raise AIONParseError(f"Could not parse function '{func_str}'. Error: {e}")

                inner_items = re.findall(r'(arg-\d+|return-\d+)\s*-->\s*"([^"]*)"', inner_block)
                for key, val in inner_items:
                    if key.startswith("arg-"):
                        func_data["args"][key] = val
                    elif key.startswith("return-"):
                        func_data["returns"][key] = val

                tool_data['function'] = func_data

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
                all_tools.extend(cls.load(os.path.join(dirpath, filename), context))
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
                for k, v in func.get("args", {}).items(): aion_str += f'        {k} --> "{v}",\n'
                for k, v in func.get("returns", {}).items(): aion_str += f'        {k} --> "{v}",\n'
                aion_str = aion_str.rstrip(",\n") + "\n   },\n"

            if 'args_schema_raw' in tool:
                aion_str += '   args_schema --> {\n'
                for k, v in tool['args_schema_raw']: aion_str += f'        {k} --> "{v}",\n'
                aion_str = aion_str.rstrip(",\n") + "\n   },\n"

            if 'link' in tool: aion_str += f'   link --> "{tool["link"]}",\n'
            aion_str += f'   description --> "{tool.get("description", "")}"\n  }}'
            aion_strings.append(aion_str)

        return "[\n" + ",\n".join(aion_strings) + "\n]"

    @classmethod
    def get_langchain_tools(cls, source_path: str, context: Dict[str, Any]) -> list:
        try:
            from langchain.tools import Tool, StructuredTool
        except ImportError:
            raise ImportError("LangChain is not installed.")

        parsed_data = cls.load_dir(source_path, context) if os.path.isdir(source_path) else cls.load(source_path,
                                                                                                     context)
        langchain_tools = []

        for tool_config in parsed_data:
            tool_name = tool_config["name"]
            executable_func = tool_config.get("function", {}).get("executable",
                                                                  lambda *args, **kwargs: "No function provided.")

            description = tool_config.get("description", "")
            if "link" in tool_config:
                description += f"\nDocumentation: {tool_config['link']}"

            args_schema = tool_config.get("args_schema")

            # NEW: Use StructuredTool if schema exists to properly map kwargs to the function
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