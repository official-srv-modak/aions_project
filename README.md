# AIONS: Actions and Interface Object Notation

**AIONS** (pronounced *IONS*) is an open-standard, text-based data format designed specifically for AI Large Language Models (LLMs). It allows developers to decouple tool definitions from core logic, making AI "Actions" as portable as JSON but as powerful as native Python.

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
*   **Approved Registry:** `name`, `function`, `description`, `args_schema`.

### 4. The Function Block
The `function` property is a "Smart Property." It requires a raw string representing the executable (lambda or function name) followed by an "Interface Block" `{ }` describing the inputs and outputs.
*   Inputs must follow the `arg-N` pattern.
*   Outputs must follow the `return-N` pattern.

---

## 📂 Syntax Example
### 📝 AIONS Syntax Guide

The AIONS (Actions and Interface Object Notation) syntax is designed to be strictly structural yet human-readable. It follows a specific set of rules to ensure LLM compatibility and execution safety.

#### 1. Global Wrapper
All tool definitions must be contained within a root-level array:
`[` ... `]`

#### 2. Tool Objects
Individual tools are defined as objects within curly braces:
`{` ... `}`

#### 3. The Action-Link Operator (-->)
AIONS uses the `-->` operator to map keys to values. Standard colon `:` or equals `=` assignments are invalid and will trigger a parse error.

#### 4. Top-Level Properties
Every tool object must contain the following identified properties:
*   **name**: The unique identifier for the tool.
*   **function**: The executable logic and interface mapping.
*   **args_schema** (Optional): The Pydantic class name for input validation.
*   **description**: The natural language instruction for the LLM.

#### 5. The Smart Function Block
The `function` property is split into two parts:
1.  **Executable String**: The lambda or function name (e.g., `"lambda x: func(x)"`).
2.  **Interface Block**: A nested `{}` mapping that defines parameters and returns.

#### 💡 Syntax Template:
```text
{
 name --> "Unique_Tool_Name",
 function --> "executable_python_logic" --> {
      arg-1 --> "Input description",
      return-1 --> "Output description"
 },
 args_schema --> "PydanticClassName",
 description --> "Detailed prompt for the AI agent"
}
```

## 🚀 Getting Started
1. Project Structure
Keep your tools organized. We recommend an aion_tools/ directory for modularity.

```text
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

## 2. Integration with LangChain
AIONS is built to be a first-class citizen in the LangChain ecosystem.

```text
from aions import AIONS
import api_functions
from schemas import SendLikeInput

# 1. Load your tools with context
# 'globals()' allows AIONS to find your imported functions and schemas
tools = AIONS.get_langchain_tools(
    source_path="aion_tools/", 
    context=globals()
)

# 2. Pass them directly to your Agent
# agent = initialize_agent(tools, llm, ...)
```

## ⚖️ Error Handling

AIONS is designed to fail fast. This prevents your AI Agent from attempting to use a tool that was configured incorrectly.

| Error | Cause |
| :--- | :--- |
| `AIONPropertyError` | Using an unauthorized key (e.g., using `desc` instead of `description`). |
| `AIONParseError` | Syntax errors, missing brackets, or function strings that don't exist in your Python code. |

# AIONS: Actions and Interface Object Notation

**AIONS** (pronounced *IONS*) is an open-standard, text-based data format designed specifically for AI Large Language Models (LLMs). It allows developers to decouple tool definitions from core logic, making AI "Actions" as portable as JSON but as powerful as native Python.

## 🛠 Extending the Framework
The AIONS class provides several utility methods for different workflows:

```text
load_dir(path, context): Automatically stitches together all .aion files in a folder.

dumps(list_of_tools): Converts existing Python tool dictionaries into the AIONS standard text format.

get_langchain_tools(...): The high-level factory for instant LangChain mounting.
``` 
## 🤝 Contributing
AIONS is an open standard. Feel free to fork the framework and add support for other LLM frameworks.

## 📦 Installation
```bash
pip install aions-llm
```

Developed by Sourav Modak