# AIONS: Actions and Interface Object Notation

**AIONS** (pronounced *IONS*) is an open-standard, text-based data format engineered specifically for Large Language Model (LLM) agent architectures. By decoupling tool definitions from application logic, AIONS provides a portable, JSON-like notation while retaining the full execution capabilities of native Python.

## Installation
```bash
pip install aions-llm
```

## Architecture and Rationale

Traditional AI tool registration often pollutes backend Python code with extensive prompt strings, interface definitions, and repetitive boilerplate. AIONS modernizes this workflow through the following architectural principles:

*   **Logic Decoupling:** Isolates LLM prompts (descriptions) and tool mappings into external `.aion` configuration files.
*   **Dynamic Evaluation:** Safely parses and binds native Python lambdas and complex conditional logic directly from the notation into memory.
*   **Strict Validation:** Enforces a rigid property schema during the parsing phase to prevent runtime failures, "ghost tools," or broken agent execution.
*   **Zero-Map Architecture:** Eliminates the need to maintain manual dictionaries in the application layer. If a tool is defined in the `.aion` file, the framework autonomously mounts it to your Agent.

---

## Specification and Constraints

To maintain standard integrity, every `.aion` file must adhere strictly to the following validation rules:

### 1. The Array Constraint
An AIONS definition must always manifest as a root-level array, enclosed in square brackets `[ ]`. Single-tool definitions must still reside within this array.

### 2. The Assignment Operator
Properties are assigned exclusively using the "Action-Link" operator: `-->`. 
*   **Valid:** `name --> "AuthModule"`
*   **Invalid:** `name: "AuthModule"` or `name = "AuthModule"`

### 3. Strict Property Isolation
AIONS enforces a strict, closed-property ecosystem. If the parser encounters a top-level key not present in the **Approved Registry**, it will raise an `AIONPropertyError`.
*   **Approved Registry:** `name`, `function`, `description`, `args_schema`, `link`.

### 4. The Function/Link Dependency Rule
Every valid AION element must possess at least one executable or referential parameter. An element must declare a `function`, a `link` (to feed public documentation to the AI), or both. If neither property is present, the parser will fail. 

### 5. The Interface Block
When utilizing the `function` property, the value must be a raw string representing the executable (e.g., a lambda or function name), immediately followed by an Interface Block `{ }` that maps the inputs and outputs.
*   Inputs must follow the sequential `arg-N` pattern.
*   Outputs must follow the sequential `return-N` pattern.

---

## Syntax Variations

The following examples demonstrate the flexibility of the Function/Link Dependency Rule. An element can act as a direct execution tool, a documentation reference, or a hybrid of both.

### Variation A: Function-Only Execution
Used when the agent needs to directly execute backend logic without requiring external documentation.
```text
[
  {
    name --> "SendOutput",
    function --> "lambda user: send_output(user)" --> {
        arg-1 --> "string (user identifier)",
        return-1 --> "dict (execution status)"
    },
    args_schema --> "SendOutputSchema",
    description --> "Executes the output transmission to the specified user."
  }
]
```

### Variation B: Link-Only Reference
Used when the agent needs access to external API documentation or a web resource, but no direct backend Python execution is required. *Note: The framework automatically binds a fallback function that returns this URL to the LLM.*
```text
[
  {
    name --> "FetchAbcDocs",
    link --> "[https://api.Abc.com/docs](https://api.Abc.com/docs)",
    description --> "Retrieves the public documentation for the Abc API to understand endpoint structures."
  }
]
```

### Variation C: Hybrid Execution & Reference
Used for complex tools where the agent can execute the function, but is also provided a link to the relevant documentation to understand the broader context of the action.
```text
[
  {
    name --> "AdminSignup",
    function --> "lambda params: admin_signup(*params.split('|'))" --> {
        arg-1 --> "string (pipe-separated user data)",
        return-1 --> "dict (new user profile)"
    },
    link --> "[https://api.Abc.com/docs/admin_signup](https://api.Abc.com/docs/admin_signup)",
    description --> "Creates a new admin account. Refer to the provided documentation link for strict password policies."
  }
]
```

---

## Implementation Guide

### 1. Recommended Directory Structure
To ensure clean modularity, isolate your notation files in a dedicated directory.
```text
project_root/
├── aion_tools/         # Directory for AIONS notation files
│   ├── auth.aion
│   └── users.aion
├── schemas.py          # Pydantic validation models
├── api_functions.py    # Core application logic
└── agent_factory.py    # LangChain entry point
```

### 2. LangChain Integration
AIONS is engineered to natively compile into LangChain Tool objects. By passing `globals()` into the execution context, the parser autonomously binds the strings in your `.aion` files to the functions and schemas residing in your application's memory.
```python
from aions import AIONS
import api_functions
from schemas import SendOutputSchema

# Initialize the AIONS parser with the local execution context
tool_registry = AIONS.get_langchain_tools(
    source_path="aion_tools/", 
    context=globals()
)

# The resulting list can be injected directly into a LangChain Agent
# agent = initialize_agent(tools=tool_registry, llm=model, ...)
```

---

## Exception Reference

The AIONS parser is designed to fail fast. Strict validation ensures the LLM is never provided with malformed tool schemas.

| Exception Class | Trigger Condition |
| :--- | :--- |
| `AIONPropertyError` | Raised when an unauthorized key is declared (e.g., using `desc` instead of the approved `description` property). |
| `AIONParseError` | Raised upon detecting syntax violations, missing array brackets, failure to meet the Function/Link Dependency Rule, or if a declared function/schema does not exist in the provided execution context. |

---

## API Reference

The `AIONS` class exposes several static methods to accommodate various system architectures:

*   `AIONS.get_langchain_tools(source_path, context)`: High-level factory method that parses files and compiles them directly into LangChain `Tool` instances.
*   `AIONS.load_dir(dirpath, context)`: Scans a target directory and compiles all contained `.aion` files into a unified Python dictionary list.
*   `AIONS.loads(aion_text, context)`: Parses a raw AIONS string directly from memory, bypassing the file system.
*   `AIONS.dumps(tools_list)`: Serializes an existing list of Python tool dictionaries back into the standard AIONS text format.

---

**Developed by Sourav Modak**