# AIONS: Actions and Interface Object Notation

**AIONS** (pronounced *IONS*) is an open-standard, text-based data format designed specifically for AI Large Language Models (LLMs). It allows developers to decouple tool definitions from core logic, making AI "Actions" as portable as JSON but as powerful as native Python.

## 📦 Installation
```bash
pip install aions-llm
```

## 🛠 Why AIONS?
Traditional AI tool registration often involves bloating your Python files with massive strings for descriptions and repetitive boilerplate. AIONS solves this by:
*   **Decoupling:** Move your LLM prompts (descriptions) and tool mappings into external `.aion` files.
*   **Dynamic Evaluation:** Supports native Python lambdas and complex logic directly within the notation.
*   **Strict Validation:** Enforces a rigid property schema to prevent "ghost tools" or broken agent execution.
*   **Zero-Map Architecture:** No need to maintain manual dictionaries; if it’s in the `.aion` file, it’s in your Agent.

---

## 📜 The Laws of AIONS
To maintain the "Open Standard" integrity, every `.aion` file must adhere to the following rules:

### 1. The Array Constraint
An AIONS definition must always be an array, enclosed in square brackets `[ ]`. Even if you are defining a single tool, it must reside within an array.

### 2. The Arrow Operator
Properties are assigned using the "Action-Link" operator: `-->`. 
*   **Valid:** `name --> "MyTool"`
*   **Invalid:** `name: "MyTool"` or `name = "MyTool"`

### 3. Property Isolation
AIONS strictly enforces identified properties. If the parser encounters a top-level key that is not in the **Approved Registry**, it will throw an `AIONPropertyError`.
*   **Approved Registry:** `name`, `function`, `description`, `args_schema`, `link`.

### 4. The `function` XOR `link` Rule
An AION element must possess at least **one** executable/referential parameter. A valid element can have a `function`, a `link` (for public documentation to feed the AI), or both. If neither is present, the parser will fail.

### 5. The Smart Function Block
The `function` property requires a raw string representing the executable (lambda or function name) followed by an "Interface Block" `{ }` describing the inputs and outputs.
*   Inputs must follow the `arg-N` pattern.
*   Outputs must follow the `return-N` pattern.

---

## 📂 Syntax & Example

### 💡 Syntax Template:
```text
[
  {
    name --> "Unique_Tool_Name",
    function --> "executable_python_logic" --> {
                                                    arg-1 --> "Input description",
                                                    return-1 --> "Output description"
                                               },
    link --> "[https://docs.yoursite.com/tool](https://docs.yoursite.com/tool)",
    args_schema --> "PydanticClassName",
    description --> "Detailed prompt for the AI agent"
  }
]
```

### 💡 Real-World Example
```text
[
  {
   name --> "send_output",
   function --> "lambda user: send_output(user)" --> {
                                                        arg-1 --> "string",
                                                        return-1 --> "dict"
                                                     },
   link --> "[https://api.balkandate.com/docs/send_output](https://api.balkandate.com/docs/send_output)",
   args_schema --> "SendOutputSchema",
   description --> "This is the prompt that describes the function."
  }
]
```

---

## 🚀 Getting Started

### 1. Project Structure
Keep your tools organized. We recommend an `aion_tools/` directory for modularity.
```text
my_project/
├── aion_tools/       # .aion files
│   ├── auth.aion
│   └── user.aion
├── schemas.py        # Pydantic Models
├── api_functions.py  # Backend Logic
└── main.py           # Entry point
```

### 2. Integration with LangChain
AIONS is built to be a first-class citizen in the LangChain ecosystem.

```python
from aions import AIONS
import api_functions
from schemas import SendLikeInput

# 1. Load your tools with context
# 'globals()' allows AIONS to find your imported functions and schemas in memory
tools = AIONS.get_langchain_tools(
    source_path="aion_tools/", 
    context=globals()
)

# 2. Pass them directly to your Agent
# agent = initialize_agent(tools, llm, ...)
```

---

## ⚖️ Error Handling

AIONS is designed to fail fast. This prevents your AI Agent from attempting to use a tool that was configured incorrectly.

| Error | Cause |
| :--- | :--- |
| `AIONPropertyError` | Using an unauthorized key (e.g., using `desc` instead of `description`). |
| `AIONParseError` | Syntax errors, missing brackets, missing a function/link, or function strings that don't exist in your Python code. |

---

## 🛠 Extending the Framework

The `AIONS` class provides several utility methods for different workflows:
*   `load_dir(path, context)`: Automatically stitches together all `.aion` files in a folder.
*   `loads(text, context)`: Parses a raw string representing AION notation directly from memory.
*   `dumps(list_of_tools)`: Converts existing Python tool dictionaries into the AIONS standard text format.
*   `get_langchain_tools(...)`: The high-level factory for instant LangChain mounting.

---

## 🤝 Contributing
AIONS is an open standard. Feel free to fork the framework and add support for other LLM frameworks!

**Developed by Sourav Modak**