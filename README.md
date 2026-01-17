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
MeasureAll(q, c)
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

MeasureAll(q, c)
Print(c)
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
- **Modifiers**: `ctrl` and `inv` (dagger) modifiers for gates, and `reset` modifiers for qubits
- **Functions**: Compile-time inlined for quantum operations
- **Control Flow**: `for` loops (unrolled), `if/else` (classical only)
- **Gate Set**: `H`, `X`, `CNot`, `CZ`, `Swap`, `RZ`, `Measure`, and more
- **Standard Library**: `Print()`, `Len()`, `MeasureAll()`, `Assert()`, `Range()`
- **Constants**: Built-in constants like `pi`, `e`, and user-defined `const` declarations

## Quanta Language Specification

> **Quanta is a Python-like, static quantum programming language that compiles deterministically to OpenQASM 3.**

### Design Principles

- **Readable & familiar** (Python / C# inspired)
- **No abstraction leaks**: everything maps cleanly to OpenQASM 3
- **Explicit quantum semantics**
- **Static-circuit first** (no runtime quantum control in v1)
- **Frontend power, backend honesty**
- **Semicolons optional**, never required except for same-line statements

### Comments

```quanta
// single-line comment
```

> No multiline comments in v1 (simplifies parsing & tooling).

### Type System

#### Primitive Types (Classical)

```text
int, float, bool, str, list, dict
```

- `var` is the default inferred type
- Static typing is optional but encouraged

#### Quantum Types (QASM-Mapped)

```text
qubit
bit
qubit[n]
bit[n]
```

📌 **Rules**

- These map **1:1** to OpenQASM 3 registers 
- No dynamic allocation

### Variables

#### Declaration

```quanta
var x = 10
int y = 3
float z = 1.23
```

- `var` → inferred, immutable type after assignment
- Quantum variables must be explicitly declared

#### Constants & Immutability

```quanta
const N = 4
let theta = pi / 4
```

|Keyword|Meaning|
|---|---|
|`const`|Compile-time literal|
|`let`|Immutable value, resolved once|

### Arrays (Lists)

#### Literals

```quanta
list a = [1, 2, 3]
list b = [1:6]       // [1,2,3,4,5]
list c = [1:2:6]     // [1,3,5]
```

#### Indexing

```quanta
a[0]
q[qidx[1]]
```

📌 **Quantum rule**

> Any array used in quantum operations **must be compile-time resolvable**.

### Dictionaries (Maps)

```quanta
dict gates = {
    "control": 0,
    "target": 1
}
```

```quanta
gates["control"]
```

📌 **Restriction**

- Dictionaries are **frontend-only**
- Must fully resolve before quantum lowering

### Functions (Classical)

#### Void Function

```quanta
func apply_h(q) {
    H(q)
}
```

#### Typed Return

```quanta
func int add(a, b) {
    return a + b
}
```

#### Inferred Return

```quanta
func var mul(a, b) {
    return a * b
}
```

📌 **Rule**

- `func name(...)` → no return
- `func <type> name(...)` → must return

### Gate Calls (Core Feature)

#### Function-Like Gate Syntax

```quanta
H(q[0])
X(q[1])
CNot(q[0], q[1])
RZ(pi/2, q[0])
```

#### Built-in Gate Mapping

|Quanta|OpenQASM 3|
|---|---|
|`H(q)`|`h q;`|
|`X(q)`|`x q;`|
|`CNot(a,b)`|`cx a, b;`|
|`CZ(a,b)`|`cz a, b;`|
|`Swap(a,b)`|`swap a, b;`|
|`Measure(q,c)`|`measure q -> c;`|

📌 Gates **look like functions** but are **not functions** semantically.

### Gate Macros (`gate`)

Compile-time circuit composition.

```quanta
gate Bell(a, b) {
    H(a)
    CNot(a, b)
}
```

Usage:

```quanta
Bell(q[0], q[1])
```

📌 `gate`:

- Cannot return
- Expands inline
- Accepts modifiers (`ctrl`, `inv`)

### Controlled (ctrl) & Dagger (inv) Modifiers

#### Controlled (ctrl)

```quanta
ctrl X(q[0], q[1])
ctrl[2] Z(q[0], q[1], q[2])
```

#### Dagger (inv)

```quanta
inv RZ(theta, q[0])
RZ(theta, q[0])†
```

#### Combined

```quanta
ctrl inv U(q[0], q[1])
```

📌 Maps directly to:

```qasm
ctrl @ inv @ U q[0], q[1];
```

🚫 Not allowed on `Measure`

### Control Flow (Compile-Time)

#### For Loop

```quanta
for (i in [0:3]) {
    H(q[i])
}
```

Unrolled at compile time.

#### If / Else (Classical Only)

```quanta
if (x > 0) {
    x = x - 1
} else {
    x = x + 1
}
```

📌 **Restriction**

- No runtime classical-quantum branching in v1
- Conditions must be statically resolvable

### Classes (Frontend Only)

```quanta
class Pair {
    var a
    var b

    func init(x, y) {
        a = x
        b = y
    }
}
```

📌 Classes:

- Do **not** exist in QASM
- Fully expanded before lowering

### Standard Library (v1)

#### `Print()` – Debug / Frontend Runtime

```quanta
Print(c)      // [1,0,0]
Print(c[0])   // 1
Print(q)      // |ψ⟩ (symbolic)
```

|Type|Output|
|---|---|
|Primitive|Normal|
|`bit[n]`|Measurement results|
|`qubit[n]`|Symbolic bra-ket|

📌 No amplitudes unless simulator supports it.

#### Other Core Helpers

```quanta
Len(q)
Range(0, 3)
MeasureAll(q, c)
reset q 
Assert(len(q) == len(c))
Error("Invalid circuit")
Warn("Simulator-only feature")
```

**Function Descriptions:**

- **`Len(q)`** - Returns the size of a quantum register, classical register, or array. Evaluated at compile-time. Useful for bounds checking and loop generation.
  ```quanta
  qubit[5] q
  var size = Len(q)  // size = 5
  ```

- **`Range(start, steps, end)`** - Generates a compile-time range for use in `for` loops. Creates a list of integers from `start` (inclusive) (default = 0) to `end` (exclusive) in `steps` (default = 1).
  ```quanta
  for (i in range(3)) {
      H(q[i])  // Applies H to q[0], q[1], q[2]
  }
  for (i in range(0, 3)) {
      H(q[i])  // Applies H to q[0], q[1], q[2]
  }
  for (i in range(0, 1, 3)) {
      H(q[i])  // Applies H to q[0], q[1], q[2]
  }
  ```

- **`MeasureAll(q, c)`** - Convenience function that measures all qubits in register `q` to corresponding classical bits in register `c`. Generates individual `measure` statements for each qubit. Both registers must have the same size.
  ```quanta
  qubit[3] q
  bit[3] c
  MeasureAll(q, c)  // Equivalent to: measure(q[0], c[0]); measure(q[1], c[1]); measure(q[2], c[2]);
  ```

- **`reset q`** - Resets one or more qubits to the |0⟩ state. Maps to OpenQASM 3 `reset` statement. Useful for reinitializing qubits during circuit execution.
  ```quanta
  reset q[0]         // Reset single qubit
  reset q            // Reset entire register
  ```

- **`Assert(condition)`** - Compile-time assertion that validates a condition during compilation. If the condition evaluates to false, compilation fails with an error. Useful for validating circuit constraints.
  ```quanta
  Assert(len(q) == len(c))  // Ensures registers have matching sizes
  Assert(len(q) > 0)        // Ensures non-empty register
  ```

- **`Error("message")`** - Emits a compile-time error with the specified message and stops compilation. Useful for validating circuit parameters or detecting unsupported configurations.
  ```quanta
  if (len(q) > 10) {
      Error("Register size exceeds maximum of 10 qubits")
  }
  ```

- **`Warn("message")`** - Emits a compile-time warning with the specified message but allows compilation to continue. Useful for alerting about potential issues or simulator-only features.
  ```quanta
  Warn("This circuit uses features only available in simulators")
  ```

### Complete Example

#### Quanta

```quanta
qubit[2] q
bit[2] c

gate Bell(a, b) {
    H(a)
    CNot(a, b)
}

Bell(q[0], q[1])

MeasureAll(q, c)
Print(c)
```

#### Generated OpenQASM 3

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

### Semicolons

Optional by default:

```quanta
var x = 1
var y = 2;
```

Required on same line:

```quanta
var x = 1; var y = 2
```

### Identity Statement

> **Quanta is to OpenQASM 3 what Python/C# is to assembly — a static, readable, honest frontend that never pretends quantum hardware can do what it can't.**

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
