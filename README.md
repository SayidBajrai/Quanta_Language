# Quanta Language

**Quanta** is a high-level, Python-like language that compiles to OpenQASM 3. It provides a clean, readable syntax for quantum circuit development while maintaining full compatibility with OpenQASM 3 and Qiskit.

## Features

- 🐍 **Python-like syntax** - Familiar and readable
- ⚛️ **Function-style gates** - Gates as function calls: `H(q[0])`, `CNot(q[0], q[1])`
- 🔒 **Static analysis** - Compile-time safety checks
- 🎯 **OpenQASM 3 output** - Direct compilation to standard QASM
- 🚀 **Qiskit integration** - Seamless execution with Qiskit backends

## Installation

```bash
pip install quanta-lang
```

## Quick Start

### As a Library

```python
from quanta import compile, run

# Compile Quanta source to OpenQASM 3
source = """
qubit[2] q
bit[2] c

gate Bell(a, b) {
    H(a)
    CNot(a, b)
}

Bell(q[0], q[1])
measure_all(q, c)
"""

qasm = compile(source)
print(qasm)

# Run and get results
result = run(source, shots=1024)
print(result)
```

### CLI Usage

```bash
# Compile to QASM
quanta compile example.qta -o output.qasm

# Run circuit
quanta run example.qta --shots 1024

# Check syntax
quanta check example.qta
```

## Example

### Quanta Source (`bell.qta`)

```quanta
// Bell state example
qubit[2] q
bit[2] c

gate Bell(a, b) {
    H(a)
    CNot(a, b)
}

Bell(q[0], q[1])

measure_all(q, c)
print(c)
```

### Generated OpenQASM 3

```qasm
OPENQASM 3;
include "stdgates.inc";

qubit[2] q;
bit[2] c;

h q[0];
cx q[0], q[1];

measure q[0] -> c[0];
measure q[1] -> c[1];
```

## Language Features

- **Types**: `int`, `float`, `bool`, `str`, `list`, `dict`, `qubit`, `bit`
- **Gate Macros**: `gate` keyword for compile-time circuit composition
- **Modifiers**: `ctrl` and `inv` (dagger) modifiers for gates
- **Functions**: Compile-time inlined for quantum operations
- **Control Flow**: `for` loops (unrolled), `if/else` (classical only)
- **Gate Set**: `H`, `X`, `CNot`, `CZ`, `Swap`, `RZ`, `Measure`, and more
- **Standard Library**: `print()`, `len()`, `measure_all()`, `reset()`, `assert()`, `range()`

## Language Features

- **Types**: `int`, `float`, `bool`, `str`, `list`, `dict`, `qubit`, `bit`
- **Functions**: Compile-time inlined for quantum operations
- **Control Flow**: `for` loops (unrolled), `if/else` (classical only)
- **Gate Set**: `H`, `X`, `CNot`, `CZ`, `Swap`, `RZ`, `Measure`, and more
- **Standard Library**: `print()`, `len()`, `measure_all()`, `reset()`, `assert()`

## Documentation

- [Language Specification](docs/language.md)
- [Compiler Pipeline](docs/compiler.md)
- [Roadmap](docs/roadmap.md)

## Development

```bash
# Install in development mode
pip install -e .[dev]

# Run tests
pytest

# Format code
black src tests
ruff check src tests
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.
