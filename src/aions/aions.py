import os
import re
from typing import Any, Dict, List, Optional
try:
    from pydantic import create_model, Field, BaseModel
except ImportError:
    BaseModel = None

class AIONParseError(Exception):
    """Raised when the syntax of the .aion file is invalid."""
    pass

class AIONPropertyError(Exception):
    """Raised when an unidentified property is found in the .aion file."""
    pass

class AIONS:
    @staticmethod
    def _read_source(source_path: str) -> str:
        if os.path.isdir(source_path):
            combined_text = []
            for root, _, files in os.walk(source_path):
                for file in sorted(files):
                    if file.endswith(".aion"):
                        with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                            combined_text.append(f.read())
            return "\n".join(combined_text)
        elif os.path.isfile(source_path):
            with open(source_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    @staticmethod
    def _extract_global_property(raw_text: str, key: str) -> Optional[str]:
        triple_pattern = rf"\b{key}\s*-->\s*\"\"\"(.*?)\"\"\""
        triple_match = re.search(triple_pattern, raw_text, re.DOTALL)
        if triple_match:
            return triple_match.group(1).strip()

        single_pattern = rf"\b{key}\s*-->\s*\"([^\"]*)\""
        single_match = re.search(single_pattern, raw_text, re.DOTALL)
        if single_match:
            return single_match.group(1).strip()

        return None

    @staticmethod
    def get_system_prompt(source_path: str) -> Optional[str]:
        raw_text = AIONS._read_source(source_path)
        return AIONS._extract_global_property(raw_text, "system_prompt")

    @staticmethod
    def get_wrapped_query(source_path: str, user_query: str, payload: Optional[Any] = None) -> str:
        raw_text = AIONS._read_source(source_path)
        base_template = AIONS._extract_global_property(raw_text, "wrapped_query")

        if not base_template:
            base_template = (
                "User request: {query}\n\n"
                "Analyze the request thoroughly using your available tools."
            )

        processed_query = base_template
        if "{query}" in processed_query:
            processed_query = processed_query.replace("{query}", user_query)
        elif "{user_query}" in processed_query:
            processed_query = processed_query.replace("{user_query}", user_query)
        else:
            processed_query += f"\n\nUser request: {user_query}"

        if payload is not None:
            serialized_payload = json.dumps(payload, indent=2) if isinstance(payload, (dict, list)) else str(payload)
            if "{payload}" in processed_query:
                processed_query = processed_query.replace("{payload}", serialized_payload)
            else:
                processed_query += f"\n\nAdditional Context/Payload:\n{serialized_payload}"

        return processed_query.strip()

    @staticmethod
    def _parse_primitive_value(val_str: str) -> Any:
        val_str = val_str.strip()
        if val_str.startswith('"') and val_str.endswith('"'):
            return val_str[1:-1]
        return val_str

    @staticmethod
    def _parse_embedded_block(block_str: str) -> Dict[str, str]:
        results = {}
        content = block_str.strip().lstrip("{").rstrip("}").strip()
        if not content:
            return results

        pairs = re.split(r",(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", content)
        for pair in pairs:
            if "-->" in pair:
                k, v = pair.split("-->", 1)
                k = k.strip().strip('"')
                v = v.strip().strip('"')
                results[k] = v
        return results

    @staticmethod
    def _build_pydantic_model(model_name: str, schema_dict: Dict[str, str]) -> Any:
        if BaseModel is None:
            return None

        fields = {}
        type_mapping = {
            "str": str,
            "string": str,
            "int": int,
            "integer": int,
            "float": float,
            "bool": bool,
            "boolean": bool,
            "dict": dict,
            "list": list
        }

        for field_name, rules in schema_dict.items():
            parts = [p.strip() for p in rules.split("|")]
            type_str = parts[0].lower()
            field_type = type_mapping.get(type_str, str)

            default_value = ...
            description_text = ""

            for part in parts[1:]:
                if part.startswith("default="):
                    raw_default = part.split("=", 1)[1].strip()
                    if (raw_default.startswith("'") and raw_default.endswith("'")) or \
                            (raw_default.startswith('"') and raw_default.endswith('"')):
                        default_value = raw_default[1:-1]
                    elif raw_default.lower() == "none":
                        default_value = None
                    elif raw_default.lower() == "true":
                        default_value = True
                    elif raw_default.lower() == "false":
                        default_value = False
                    else:
                        try:
                            default_value = int(raw_default)
                        except ValueError:
                            try:
                                default_value = float(raw_default)
                            except ValueError:
                                default_value = raw_default
                else:
                    description_text = part

            fields[field_name] = (field_type, Field(default=default_value, description=description_text))

        return create_model(f"{model_name}Input", **fields)

    @classmethod
    def loads(cls, aion_text: str, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        aion_text = aion_text.strip()

        if not (aion_text.startswith("[") and aion_text.endswith("]")):
            raise AIONParseError("AION definition must be an array enclosed in [ ]")

        start_idx = aion_text.find('[')
        end_idx = aion_text.rfind(']')
        inner_text = aion_text[start_idx + 1:end_idx].strip()

        blocks = []
        current_block = ""
        brace_level = 0
        in_block = False

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

            name_match = re.search(r'name\s*-->\s*"([^"]+)"', block)
            if not name_match:
                raise AIONParseError(f"Found a malformed AION block missing the 'name' property:\n{block[:50]}...")
            tool_data['name'] = name_match.group(1)

            desc_match = re.search(r'description\s*-->\s*"([^"]+)"', block)
            if desc_match:
                tool_data['description'] = desc_match.group(1)

            link_match = re.search(r'link\s*-->\s*"([^"]+)"', block)
            if link_match:
                tool_data['link'] = link_match.group(1)

            schema_block_match = re.search(r'args_schema\s*-->\s*\{([^}]+)\}', block)
            if schema_block_match:
                inner_schema = schema_block_match.group(1)
                schema_items = re.findall(r'([a-zA-Z0-9_-]+)\s*-->\s*"([^"]*)"', inner_schema)
                tool_data['args_schema_raw'] = schema_items

                if BaseModel is not None:
                    fields = {}
                    for field_name, field_def in schema_items:
                        parts = [p.strip() for p in field_def.split('|')]

                        type_str = parts[0].lower() if parts else "str"
                        type_map = {'str': str, 'int': int, 'float': float, 'bool': bool, 'list': list, 'dict': dict}
                        field_type = type_map.get(type_str, str)

                        default_val = ...
                        description = ""

                        if len(parts) == 2:
                            description = parts[1]
                        elif len(parts) >= 3:
                            if parts[1].startswith("default="):
                                raw_val = parts[1].split("=", 1)[1].strip("'\" ")
                                if raw_val.lower() == "none":
                                    default_val = None
                                else:
                                    default_val = raw_val
                            description = parts[2]

                        fields[field_name] = (field_type, Field(default=default_val, description=description))

                    model_name = f"{tool_data.get('name', 'Dynamic')}Input"
                    tool_data['args_schema'] = create_model(model_name, **fields)

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
    def dumps(cls, tools: List[Dict[str, Any]], system_prompt: Optional[str] = None,
              wrapped_query: Optional[str] = None) -> str:
        aion_strings = []

        if system_prompt:
            sp_str = f'  system_prompt --> """\n{system_prompt}\n  """'
            aion_strings.append(sp_str)

        if wrapped_query:
            wq_str = f'  wrapped_query --> """\n{wrapped_query}\n  """'
            aion_strings.append(wq_str)

        for tool in tools:
            aion_str = "  {\n"
            aion_str += f'   name --> "{tool.get("name", "")}",\n'

            if 'function' in tool:
                func = tool.get("function", {})
                if isinstance(func, dict):
                    aion_str += f'   function --> "{func.get("raw_string", "")}" --> {{\n'
                    for arg_k, arg_v in func.get("args", {}).items():
                        aion_str += f'        {arg_k} --> "{arg_v}",\n'
                    for ret_k, ret_v in func.get("returns", {}).items():
                        aion_str += f'        {ret_k} --> "{ret_v}",\n'
                    aion_str = aion_str.rstrip(",\n") + "\n   },\n"
                elif isinstance(func, str):
                    aion_str += f'   function --> "{func}" --> {{\n   }},\n'

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

        return "[\n" + ",\n".join(aion_strings) + "\n]"

    @classmethod
    def dump(cls, tools: List[Dict[str, Any]], filepath: str, system_prompt: Optional[str] = None,
             wrapped_query: Optional[str] = None):
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(cls.dumps(tools, system_prompt=system_prompt, wrapped_query=wrapped_query))

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

            if "function" in tool_config:
                func_data = tool_config["function"]
                if isinstance(func_data, dict) and "executable" in func_data:
                    executable_func = func_data["executable"]
                else:
                    try:
                        executable_func = eval(str(func_data), context)
                    except Exception as e:
                        executable_func = lambda *args, **kwargs: f"Action unavailable."
            else:
                link_url = tool_config.get("link", "")
                executable_func = lambda *args, url=link_url, **kwargs: f"Action unavailable. Please refer to documentation: {url}"

            description = tool_config.get("description", "")
            if "link" in tool_config:
                description += f"\nDocumentation Link: {tool_config['link']}"

            args_schema = tool_config.get("args_schema")

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