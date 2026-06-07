# AIONS Language Specification (v1.1)

## 1. Syntax Grammar (EBNF)
The syntax of AIONS is defined by the following Extended Backus-Naur Form (EBNF) grammar. This defines exactly how the text must be structured to be recognized by an AIONS-compliant parser across any programming language.

```ebnf
(* Root Document *)
document           ::= "[" ws (system_prompt_def ws "," ws)? element_list? ws "]"
system_prompt_def  ::= "system_prompt" ws "-->" ws (multi_string | string)

(* Elements and Properties *)
element_list       ::= element (ws "," ws element)*
element            ::= "{" ws property_list ws "}"
property_list      ::= property (ws "," ws property)*
property           ::= identifier ws "-->" ws property_val

(* Identifiers and Values *)
identifier         ::= [a-zA-Z0-9_-]+
property_val       ::= string | function_block | schema_block

(* The Smart Function Block *)
function_block     ::= string ws "-->" ws "{" ws interface_list? ws "}"
interface_list     ::= interface_item (ws "," ws interface_item)*
interface_item     ::= interface_key ws "-->" ws string

(* Interface Keys *)
interface_key      ::= arg_key | return_key
arg_key            ::= "arg-" [1-9] [0-9]*
return_key         ::= "return-" [1-9] [0-9]*

(* The Schema Block (Native Pydantic Support) *)
schema_block       ::= "{" ws schema_list? ws "}"
schema_list        ::= schema_item (ws "," ws schema_item)*
schema_item        ::= identifier ws "-->" ws string

(* Primitives *)
string             ::= '"' [^"]* '"'
multi_string       ::= '"""' ANY* '"""'
ws                 ::= [ \t\n\r]*