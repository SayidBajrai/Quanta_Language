# Quanta Compiler Pipeline

## Overview

The Quanta compiler follows a standard multi-stage pipeline:

```
Quanta Source Code
        ↓
 Lexer (Tokenization)
        ↓
 Parser (AST Construction)
        ↓
 Semantic Analysis
        ↓
 Code Generation (OpenQASM 3)
```

## Stages

### 1. Lexical Analysis
- Tokenizes source code
- Removes comments
- Handles whitespace and newlines

### 2. Parsing
- Builds Abstract Syntax Tree (AST)
- Validates syntax structure
- No semantic checks at this stage

### 3. Semantic Analysis
- Symbol table construction
- Type checking
- Quantum operation validation
- Function inlining preparation

### 4. Code Generation
- AST to OpenQASM 3 translation
- Gate name mapping
- Register declaration generation

## AST Structure

The AST consists of:
- **Statements**: declarations, control flow, expressions
- **Expressions**: calls, indexes, literals, operators
- **Types**: quantum registers, variables, functions

See `src/quanta/ast/nodes.py` for complete node definitions.
