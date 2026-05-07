# AIONS Language Specification (v1.0)

## 1. Syntax Grammar (EBNF)
The syntax of AIONS is defined by the following Extended Backus-Naur Form (EBNF) grammar. This defines exactly how the text must be structured to be recognized by an AIONS-compliant parser across any programming language.
```ebnf
(* Root Document *)
document       ::= "[" ws element_list? ws "]"
element_list   ::= element (ws "," ws element)*

(* Elements and Properties *)
element        ::= "{" ws property_list ws "}"
property_list  ::= property (ws "," ws property)*
property       ::= identifier ws "-->" ws property_val

(* Identifiers and Values *)
identifier     ::= [a-zA-Z0-9_-]+
property_val   ::= string | function_block

(* The Smart Function Block *)
function_block ::= string ws "-->" ws "{" ws interface_list? ws "}"
interface_list ::= interface_item (ws "," ws interface_item)*
interface_item ::= interface_key ws "-->" ws string

(* Interface Keys *)
interface_key  ::= arg_key | return_key
arg_key        ::= "arg-" [1-9] [0-9]*
return_key     ::= "return-" [1-9] [0-9]*

(* Primitives *)
string         ::= '"' [^"]* '"'
ws             ::= [ \t\n\r]*
```

## 2. Semantic Constraints
While the EBNF defines the *shape* of the text, an AIONS-compliant parser must also enforce the following logic rules during the Abstract Syntax Tree (AST) evaluation phase.

### Constraint A: The Closed Ecosystem
The `identifier` in any top-level `property` must strictly belong to the following set:
`{"name", "function", "description", "args_schema", "link"}`. 
Any parsed identifier outside of this set must trigger an `AIONPropertyError`.

### Constraint B: The Required Payload
Every `element` must contain, at a minimum, the `name` and `description` properties.

### Constraint C: The Action/Reference XOR
Every `element` must fulfill the Action/Reference constraint to guarantee utility to the LLM agent. The element must contain:
1. The `function` property, OR
2. The `link` property, OR
3. Both properties.
If the AST evaluates an element containing neither, the parser must trigger an `AIONParseError`.

### Constraint D: Interface Sequencing
Inside the `function_block`, `arg_key` and `return_key` indices must be logical and sequential (e.g., `arg-1`, `arg-2`).