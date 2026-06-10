# Quanta Language

**Quanta** is a high-level, Python-like language that compiles to OpenQASM 3. It provides a clean, readable syntax for quantum circuit development while maintaining full compatibility with OpenQASM 3 and Qiskit.

## Features

- 🐍 **Python-like syntax** - Familiar and readable
- ⚛️ **Function-style gates** - Gates as function calls: `H(q[0])`, `CNot(q[0], q[1])`
- 🔒 **Static analysis** - Compile-time safety checks
- 🎯 **OpenQASM 3 output** - Direct compilation to standard QASM
- 🚀 **Qiskit integration** - Seamless execution with Qiskit backends
- 🖥️ **Frontend debug** - `get_prints(source)` runs a statevector sim and returns all `Print()` output (simulator only)
- 📊 **Resource estimation** - `analyze(source)` returns qubit count, depth, T-count, 2Q gates, gate breakdown, estimated runtime
- ⚡ **Compiler optimization** - Gate fusion (`H+H→I`, `RZ+RZ→RZ`), commutation, depth reduction, hardware-native lowering
- 🔍 **Pathway tracing** - `f"{q:pathway}"` shows step-by-step gate execution trace with entanglement tracking
- 🎛️ **Hardware lowering** - `compile(optimize_target="ibm_brisbane")` lowers CNOT→ECR for IBM, etc.
- 📈 **Hardware backends** - Built-in database for IBM Brisbane/Sherbrooke/Kyoto, IonQ Aria/Forte
- 🌐 **Noise simulation** - `NoiseModel { depolarizing=0.01 }` declarations + `run(noisy=True)`

## Installation

```bash
pip install quanta-lang
```

Requires Python 3.10+ and Qiskit.

## Quick Start

### As a Library

```python
from quanta import compile, run, get_prints, analyze, list_backends, backend_info

# Compile Quanta source to OpenQASM 3
source = """
qbit[2] q
bit[2] c

gate Bellgate(a, b) {
    H(a)
    CNot(a, b)
}

Bellgate(q[0], q[1])
Measure(q, c)
"""

qasm = compile(source)
print(qasm)

# Run and get measurement results
result = run(source, shots=1024)
print(result)

# Frontend debug: capture Print() output (statevector simulator only)
debug_source = "qbit q\nH(q)\nPrint(q)"
terminal = get_prints(debug_source)
print(terminal)  # e.g. "1/sqrt(2) * |0> + 1/sqrt(2) * |1>"

# Resource estimation (counts depth, T-count, gates, runtime, hardware fit)
report = analyze(source, hardware_backends=["ibm_brisbane", "ionq_aria"])
print(f"Depth: {report.depth}, T-count: {report.t_count}, Runtime: {report.estimated_runtime}")
print(f"Backend fit: {report.hardware_fits}")

# Compile with depth reduction optimization
qasm_opt = compile(source, depth_reduction=True)

# Compile with hardware-native lowering
qasm_hw = compile(source, optimize_target="ibm_brisbane")

# Compile + analyze in one pass
result = compile(source, analyze=True)
print(f"QASM: {result.qasm}, Depth: {result.metrics.depth}")

# Run with noise simulation
result_noisy = run(source, shots=1024, noisy=True, depolarizing=0.01)

# List available hardware backends
print(list_backends())
print(backend_info("ibm_brisbane"))
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
qbit[2] q
bit[2] c

gate Bellgate(a, b) {
    H(a)
    CNot(a, b)
}

Bellgate(q[0], q[1])

Measure(q, c)
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

- **Types**: classical `int`, `float`, `bool`, `str`, `list`, `dict`, `uint(n)`, `dec(i,f)`, `udec(i,f)`; quantum `qbit[n]`, `bit[n]`, `qint(n)`, `quint(n)`, `qdec(i,f)`, `qudec(i,f)`, `qfloat(e,m)`, `qreal(min,max,bits)`, `bint[n]`
- **Gate Macros**: `gate` keyword for compile-time circuit composition
- **Modifiers**: `ctrl` and `inv` (dagger) modifiers for gates, and `reset` for qubits
- **Functions**: Compile-time inlined for quantum operations
- **Control Flow**: `for` loops (unrolled), `while` loops (structured mode), `if/else` (classical only)
- **Indexing**: Multi-dimensional fancy indexing (`q[0,2,5]`, `q[0:4,7]`)
- **Tensor Types**: N-dimensional classical and quantum tensors (`int[n][m]`, `float[3][3]`, `qbit[2][2]`)
- **Tensor Algebra**: `DotProduct`, `CrossProduct`, `ElementwiseProduct`, `TensorProduct`, `Shape`, `Reshape`; operators `a . b` (dot), `A * B` (cross, 3D vectors), `A ⊙ B` (elementwise), `A ⊗ B` (Kronecker) — frontend / classical only
- **Structured Compilation**: `compile(source, keep_structure=True)` preserves `def`/`gate` and control flow
- **Print Formatting**: f-string specifiers for symbolic states, probabilities, entropy, amplitudes, summary, Bloch vectors, circuit trace
- **String escapes**: C-style `\n`, `\r`, `\t`, `\\`, `\"`, hex/Unicode escapes in string and f-string literals
- **User documentation**: `///` doc comments on `func` and `gate` declarations for IDE hover
- **Metrics**: `Fidelity()` builtin (frontend simulation only)
- **Gate Set**: `H`, `X`, `CNot`, `CZ`, `Swap`, `RZ`, `Measure`, and more
- **High-Level Gates**: `Bell`, `GHZ`, `WState`, `SwapGate`, `QFT`, `InverseQFT`
- **Quantum Arithmetic**: `QAdd`, `QMult`, `Compare`, `Grover`; operator overloading (`+`, `-`, `*`, `/`, `%`) on `quint`/`qint`; `quint()` size inference; signed `qint`/`qdec`; interval `qreal`; classical `uint`/`dec`/`udec`
- **Standard Library**: `Print()`, `Len()`, `Measure()`, `Assert()`, `Range()`
- **Constants**: Built-in `pi`, `e`, and user-defined `const` declarations
- **API**: `compile(source, keep_structure=False, depth_reduction=False, optimize_target="", analyze=False)`, `run(source, shots=..., noisy=False, depolarizing=..., ...)`, `get_prints(source)` (frontend debug, simulator only), `analyze(source, hardware_backends=None)`, `list_backends()`, `backend_info(name)`

> OpenQASM 3 output uses the standard keyword `qubit` (Quanta source uses `qbit`).

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
uint(bits)
dec(int_bits, frac_bits)
udec(int_bits, frac_bits)
```

```quanta
uint(8) counter
dec(16, 16) fixed
udec(8, 8) ufixed
```

- `var` is the default inferred type
- Static typing is optional but encouraged

#### Quantum Types (QASM-Mapped)

**Tensor registers** (bracket syntax for arrays):

```text
qbit[n], bit[n], bint[n]
```

**Numeric registers** (parenthesis syntax — not arrays):

```text
qint(bits)              // signed quantum integer (two's complement), range [-2^(n-1), 2^(n-1)-1]
quint(bits)             // unsigned quantum integer (legacy semantics), range [0, 2^n-1]
qdec(int_bits, frac_bits)    // signed fixed-point quantum decimal (two's complement)
qudec(int_bits, frac_bits)   // unsigned fixed-point (legacy semantics)
qfloat(ebits, mbits)         // quantum float (1 + e + m qubits)
qreal(min, max, qbits)       // uniform interval encoding (not IEEE float)
```

📌 **Rules**

- Numeric types use `()` to avoid confusion with tensor indexing (`[]` is for `qbit[2][2]` etc.)
- **Parameterless declarations** infer canonical defaults (stored explicitly in the AST):

| Bare form | Normalized to |
|-----------|---------------|
| `qint`, `quint`, `uint` | `*(32)` |
| `qdec`, `qudec`, `dec`, `udec` | `*(16,16)` |
| `qreal` | `qreal(-1, 1, 32)` |
| `qreal(lo, hi)` | `qreal(lo, hi, 32)` |

- `quint()` / `qint()` with empty `()` still means **dynamic width inference** from operands (not the 32-bit default)
- Bracket syntax on numeric types is rejected (`qint[4]` → error; use `qint(4)` or bare `qint`)
- All quantum numeric types lower to `qubit[n]` in OpenQASM 3
- `H(register)` applies Hadamard to each underlying qubit → uniform superposition over basis states
- Signed types (`qint`, `qdec`) use two's complement internally (single zero, uniform semantic coverage)

### Variables

#### Declaration

```quanta
var count = 10
int rows = 3
float rate = 1.23
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

#### Reserved names (OpenQASM)

User-defined names must **not** collide with OpenQASM 3 keywords or standard gate names, because registers and parameters are emitted verbatim into `.qasm` output. A register named `x` would produce invalid lines like `x x;` (gate and operand share the same identifier).

The compiler rejects conflicting names at semantic analysis with a clear error.

| Blocked | Examples |
|---------|----------|
| Standard gates | `h`, `x`, `y`, `z`, `cx`, `cz`, `swap`, `rx`, `ry`, `rz`, `s`, `t`, `ccx`, `measure`, `reset`, … |
| OpenQASM keywords | `def`, `gate`, `qubit`, `bit`, `input`, `output`, `const`, `include`, … |

Matching is **case-insensitive** (`x`, `X`, and `h`, `H` are all reserved).

Applies to **quantum register names** (`qbit`, `bit`, `qint`, …), **gate macros**, **functions**, and their **parameters** — anything emitted into OpenQASM. Pure classical names (`int`, `float`, `var`, …) are not restricted.

```quanta
qbit x        // error: conflicts with OpenQASM gate 'x'
qbit q        // ok
H(q)
```

### Strings

String literals use double quotes. Common C-style escape sequences are supported:

```quanta
Print("line1\nline2\ttab");   // newline and tab
Print("path: C:\\data");      // backslash
Print("quote: \"hi\"");       // embedded quote
Print("hex: \x41");           // byte escape → "A"
Print("unicode: \u0042");     // 4-digit Unicode → "B"
```

|Escape|Meaning|
|---|---|
|`\n`|Newline|
|`\r`|Carriage return|
|`\t`|Tab|
|`\\`|Backslash|
|`\"`|Double quote|
|`\'`|Single quote|
|`\a`, `\b`, `\f`, `\v`, `\0`|Bell, backspace, form feed, vertical tab, null|
|`\{`, `\}`|Literal `{` / `}` (useful in f-strings)|
|`\xHH`|Byte (2 hex digits)|
|`\uHHHH`|Unicode code point (4 hex digits)|
|`\UHHHHHHHH`|Unicode code point (8 hex digits)|

F-strings (`f"..."`) use the same escapes in literal text. Use `{{` and `}}` for literal braces in f-string output.

```quanta
Print(f"state:\n{q:symbolic}");
```

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

#### Register slicing & fancy indexing (Python-style)

Quantum registers and classical tensors support **slice** and **multi-index** syntax:

```quanta
qbit[6] q
q[1:4]        // slice: qubits 1, 2, 3 (start:end, end exclusive)
q[0:2:6]      // step 2: qubits 0, 2, 4 (start:step:end)
q[0, 2, 5]    // fancy index: qubits 0, 2, and 5
q[0:4, 7]     // mixed slice and scalar index
```

Slices are **compile-time** (start, end, step must be constant expressions). They are used with high-level gates (e.g. `GHZ(q[1:4])`) and expand to the corresponding list of qubits. Classical tensors use the same bracket syntax for row/column selection (see [Tensor Types & Algebra](#tensor-types--algebra-classical)).

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

### Tensor Types & Algebra (Classical)

Declare N-dimensional classical tensors with repeated `[n]` dimensions:

```quanta
float[3] vec = [1.0, 2.0, 3.0]
float[3][3] W = [[0.2, 0.4, 0.6], [0.1, 0.3, 0.5], [0.7, 0.8, 0.9]]
```

Index rows, columns, and slices (including full-dimension `:`):

```quanta
W[0, 0]       // scalar element
W[0, :]       // row vector
W[:, 1]       // column vector
```

#### Product operations

| Operation | Syntax | Requirement | Result |
|-----------|--------|-------------|--------|
| Dot product | `DotProduct(a, b)` or `a . b` | Rank-1 vectors, equal length | Scalar |
| Cross product | `CrossProduct(a, b)`  or `A * B` | Two 3D vectors | 3-vector |
| Elementwise (Hadamard) | `ElementwiseProduct(a, b)` or `A ⊙ B` on tensors | Identical shape | Same shape |
| Tensor (Kronecker) product | `TensorProduct(a, b)` or `A ⊗ B` | Compatible tensors | Block-expanded tensor |

```quanta
float[3] a = [1.0, 2.0, 3.0]
float[3] b = [4.0, 5.0, 6.0]
float dot_ab = a . b                    // 32.0
float[3] cross_ab = a * b               // cross product (3D vectors)

float[3][3] W = [[0.2, 0.4, 0.6], [0.1, 0.3, 0.5], [0.7, 0.8, 0.9]]
float[3] vec = [1, 0, 1]
float y0 = DotProduct(W[0, :], vec)     // row–vector dot product

float[2][2] A = [[1, 2], [3, 4]]
float[2][2] B = [[0, 5], [6, 7]]
float[2][2] hadamard = A ⊙ B             // elementwise
float[4][4] kron = A ⊗ B                // Kronecker
Print(Shape(kron))                      // (4, 4)
```

Helpers:

- `Shape(tensor)` — returns the shape tuple, e.g. `(3, 3)`
- `Reshape(tensor, d1, d2, ...)` — reshape in the frontend simulator

📌 **Rules**

- **Strict shapes** — mismatched shapes raise a semantic error (no implicit broadcasting)
- **Types** — `int`, `float`, and `bool` tensors; bool `*` is logical AND
- **Scope** — classical preprocessing in `get_prints()` / frontend sim; does **not** lower to OpenQASM

### Functions (Classical)

Functions support optional **return types** and **parameter types**. Omit either to leave it unspecified; use `var` for an inferred return type.

#### Void Function (no return)

```quanta
func apply_h(q) {
    H(q)
}
```

Untyped parameters on quantum functions default to `qvar` (any quantum type).

#### Return Types

| Syntax | Meaning |
|--------|---------|
| `func name(...)` | No return value (quantum subroutine) |
| `func var name(...)` | Return type inferred from the body |
| `func <type> name(...)` | Must return `<type>` (`int`, `float`, `bool`, `str`, …) |

**Typed return:**

```quanta
func float add(float a, float b) {
    return a + b
}
```

**Inferred return (`var`):**

```quanta
func var mul(a, b) {
    return a * b
}
```

#### Parameter Types

| Syntax | Meaning |
|--------|---------|
| `a, b` | Unspecified — defaults to `cvar` on classical functions, `qvar` on quantum subroutines |
| `float a, float b` | Explicit classical types |
| `qbit a, qbit b` | Explicit quantum types (for mixed or quantum functions) |
| `var x` | Any type (classical or quantum) |
| `qvar q` | Any quantum type (`qbit`, `qint`, `qdec`, …) |
| `cvar x` | Any classical type (`int`, `float`, `str`, …) |

You can mix specified and unspecified parameters and return types:

```quanta
func int add(a, b) {          // typed return, unspecified params
    return a + b
}

func var scale(float val, factor) {   // inferred return, one typed param
    return val * factor
}
```

📌 **Rules**

- `func name(...)` → no return
- `func var name(...)` → return type inferred; no return-type check at compile time
- `func <type> name(...)` → must contain a `return` statement

#### Function overloading

Multiple functions may share the same name when their **parameter signatures** differ. The compiler picks the best match at each call site from argument types.

Uniqueness is based on:

1. **Parameter count** — `add(a, b)` vs `add(a, b, c)`
2. **Parameter types** — `add(int, int)` vs `add(float, float)`
3. **Parameter order** — `swap(int, float)` vs `swap(float, int)`

Return type is **not** part of the overload key — two functions with the same parameter signature cannot coexist even if their return types differ.

```quanta
/// - add function
/// - adds two integers together
/// int a - first variable
/// int b - second variable
/// return: int - result of add
func int add(int a, int b) {
    return a + b;
}

/// - add function
/// - adds two floats together
/// float a - first variable
/// float b - second variable
/// return: float - result of add
func float add(float a, float b) {
    return a + b;
}

int i = add(1, 2)        // resolves to int add(int, int)
float f = add(1.5, 2.5)  // resolves to float add(float, float)
```

Wildcard parameter types match by category and lose to more specific overloads when both fit:

| Wildcard | Matches | Default when omitted on |
|----------|---------|-------------------------|
| `var` | any type | — (write explicitly) |
| `qvar` | any quantum type | quantum subroutines (`func name(...)`) |
| `cvar` | any classical type | classical / typed-return functions |

Specificity order: concrete type > `qvar` / `cvar` > `var`.

Structured OpenQASM output (`compile(..., keep_structure=True)`) emits mangled `def` names internally (e.g. `add__int_int`) so each overload lowers to a distinct definition.

#### Documentation comments (`///`)

Place consecutive `///` lines immediately before a `func` or `gate` declaration. Each line is classified by a three-tier rule (top-down priority):

| Priority | Condition | Syntax |
|----------|-----------|--------|
| 1 | Line starts with `return:` | `return: [Type] - [Description]` |
| 2 | Type + identifier before `-` | `[Type] [Identifier] - [Description]` |
| 3 | Everything else | Summary prose (optional `-` bullet) |

Use concrete types in docs when the declaration specifies them; use `cvar`, `qvar`, or `var` when a wildcard is written or implied by omission.

**Specified param and return types:**

```quanta
/// - add function
/// - adds two floats together
/// float a - first variable
/// float b - second variable
/// return: float - result of add
func float add(float a, float b) {
    return a + b;
}
```

**Unspecified param and return types:**

```quanta
/// - add function
/// - adds two variables together
/// cvar a - first variable
/// cvar b - second variable
/// return: var - result of add
func var add(a, b) {
    return a + b;
}
```

Gates use the same format:

```quanta
/// - prepare Bell state on two qubits
/// qbit a - control qubit
/// qbit b - target qubit
gate bell(a, b) {
    H(a);
    CX(a, b);
}
```

Extract documentation from source via the Python API:

```python
from quanta import get_user_function_docs, get_function_docs

doc = get_user_function_docs(source, "add")   # FunctionSummary or None
hover = doc.format_hover()                    # IDE tooltip text

# Built-in lookup with user-doc fallback when source is provided:
doc = get_function_docs("add", source=source)
```

### Quantum Integer Types

#### `qint(n)` — signed quantum integer (two's complement)

```quanta
qint(4) a = -1    // signed range [-8, 7]
H(a)              // uniform over all 16 basis states → uniform signed semantics
```

- **Storage**: n qubits
- **Domain**: `[-2^(n-1), 2^(n-1) - 1]` via two's complement
- **Uniformity**: `H(qint)` is uniform over every representable signed value (one basis state per value)

#### `quint(n)` — unsigned quantum integer (legacy)

Preserves the original unsigned `qint[n]` behavior:

```quanta
quint(3) a = 2    // |010⟩, domain [0, 7]
quint() z = a + b // dynamic width inference from operands
```

- **Storage**: n qubits
- **Domain**: 0 to 2^n - 1
- **Arithmetic**: `QAdd`/`QMult`/operator overloading target `quint` by default

#### `bint[n]` — classical bit integer

A `bint[N]` represents **N classical bits**, equivalent to an unsigned integer:

```quanta
bint[3] c = 2    // Classical integer
```

**Properties:**
- Storage: N classical bits
- Domain: 0 to 2^N - 1
- Nature: Classical
- Copying: ✔ Allowed
- Arithmetic: Classical
- Source: Measurement only

#### Initialization

```quanta
quint(3) a = 2    // Initialize qubits to encode value 2
bint[3] c = 2    // Classical assignment
```

Initialization sets |0…0⟩ then applies X gates from the encoded bit pattern (unsigned magnitude or two's complement for signed types).

### Quantum Fixed-Point, Float, and Real (`qdec`, `qudec`, `qfloat`, `qreal`)

#### `qdec(i, f)` — signed fixed-point (two's complement)

```quanta
qdec(4, 4) fp
H(fp)   // uniform over evenly spaced values in [-8.0, 7.9375] step 1/2^f
```

#### `qudec(i, f)` — unsigned fixed-point (legacy)

```quanta
qudec(16, 8) fp
```

- **Storage**: `int_bits + frac_bits` qubits
- **Legacy unsigned** semantics (former `qdec[...]`)

#### `qfloat(e, m)` — quantum floating-point (IEEE-754–like)

Quantum analogue of IEEE-754:

```quanta
qfloat(8,23) fp   // 32-bit style: 1 sign + 8 exponent + 23 mantissa
```

- **Storage**: `1 + ebits + mbits` qubits (sign, exponent, mantissa; `value = (-1)^sign × (1 + fraction/2^mbits) × 2^(exponent - bias)`).
- **Use when**: Wide dynamic range (scientific computation); semantics (NaN, infinities, subnormals) align with classical floats.
- **Cost**: Reversible floating-point is much more expensive in qubits and gates than fixed-point.

#### When to use which

| Use case | Prefer |
|----------|--------|
| Bounded signed numerics | `qdec(i,f)` |
| Legacy unsigned fixed-point | `qudec(i,f)` |
| Wide dynamic range (IEEE-like) | `qfloat(e,m)` |
| Continuous interval / variational params | `qreal(min,max,bits)` |

#### `qreal(min, max, qbits)` — interval quantum real

Maps `N = 2^qbits` basis states uniformly across `[min, max]`:

```quanta
qreal(-pi, pi, 16) theta
qreal(0, 1, 8) alpha
```

`x_k = min + (k / (N-1)) * (max - min)` — **not** IEEE floating point. Ideal for rotations, QML parameters, and optimization landscapes.

All quantum numeric types lower to `qubit[n]` in OpenQASM 3 with metadata describing semantic decoding.

### Quantum Arithmetic Operations

#### `QAdd` - Quantum Addition

Variadic quantum addition operation:

```quanta
quint(3) a = 1
quint(3) b = 3
quint(3) c
QAdd(a, b, c)           // c = a + b (mod 2^3)
QAdd(a, b, d, result)   // result = a + b + d (mod 2^N)
```

**Semantics:**
- First N-1 arguments are inputs
- Last argument is the destination (output)
- Result = `(q1 + q2 + q3 + ...) mod 2^n`
- All operands must have matching bit widths

**Implementation:**
- Uses a **ripple-carry adder** circuit design
- Computes addition bit-by-bit from LSB to MSB
- Propagates carry bits using Toffoli (CCX) gates
- Reversible: carry bits are computed forward, then uncomputed backward
- Requires `n-1` ancilla qubits for carry storage (where n is bit width)

**Circuit Structure:**
1. **Forward pass**: Compute carry[1..n-1] using Toffoli gates
2. **Sum computation**: Compute sum[i] = a[i] XOR b[i] XOR carry[i] for all bits
3. **Backward pass**: Uncompute carry[n-1..1] to restore ancilla qubits

#### `QMult` - Quantum Multiplication

Variadic quantum multiplication operation:

```quanta
quint(3) a = 2
quint(3) b = 3
quint(5) out              // Output must be wider
QMult(a, b, out)         // out = a * b
QMult(a, b, c, out)      // out = a * b * c
```

**Semantics:**
- First N-1 arguments are inputs
- Last argument is the destination (output)
- Result = `(q1 * q2 * q3 * ...) mod 2^n`
- Output width must be ≥ sum of input widths (ideally 2n for full precision)

**Implementation:**
- Uses **shift-and-add** multiplication algorithm
- For each bit `i` of the multiplier (B):
  - If `B[i] == 1`, add `(A << i)` to result using **controlled ripple-carry adder**
  - The shift is implicit in which qubits of result receive the addition
- Each controlled addition is reversible (uses uncomputation)
- Result accumulates: `result = Σ(B[i] * (A << i))` for all bits `i`

**Circuit Structure:**
1. Initialize result register to |0⟩
2. For each bit `i = 0` to `n-1` of multiplier B:
   - If `B[i] == 1` (controlled operation):
   - Add `(A shifted by i bits)` to result using controlled ripple-carry adder
3. Each controlled addition uses reversible operations with carry uncomputation

**Example:**
For `A = 3` (011) and `B = 5` (101):
- Bit 0 of B = 1 → add `A × 2^0 = 3` to result
- Bit 1 of B = 0 → skip
- Bit 2 of B = 1 → add `A × 2^2 = 12` to result
- Final result = 3 + 12 = 15

**Requires:** Controlled ripple-carry adders, ancilla qubits for carry storage

#### `QFTAdd` - QFT-Based Quantum Addition (Fast Adder)

Variadic quantum addition using Quantum Fourier Transform (QFT):

```quanta
quint(3) a = 1
quint(3) b = 3
quint(3) c
QFTAdd(a, b, c)           // c = a + b (mod 2^3) using QFT
QFTAdd(a, b, d, result)   // result = a + b + d (mod 2^N)
```

**Semantics:**
- First N-1 arguments are inputs
- Last argument is the destination (output)
- Result = `(q1 + q2 + q3 + ...) mod 2^n`
- All operands must have matching bit widths

**Implementation:**
- Uses **QFT-based adder** (Draper adder) circuit design
- Applies QFT to target register to encode value in phase domain
- Uses controlled phase rotations to add operands
- Applies inverse QFT to transform back to computational basis

**Circuit Structure:**
1. **QFT**: Apply Quantum Fourier Transform to target register
2. **Phase rotations**: Controlled phase rotations to add each operand
3. **Inverse QFT**: Transform back to computational basis

**Advantages:**
- Lower circuit depth than ripple-carry adder
- Logarithmic depth in optimized implementations (O(log n))
- Often used within algorithms requiring modular arithmetic (e.g., Shor's algorithm)
- Reduces carry propagation overhead

#### `QTreeAdd` - Tree-Based Quantum Addition (Parallel Adder)

Variadic quantum addition using tree-based carry-save structure:

```quanta
quint(3) a = 1
quint(3) b = 3
quint(3) c
QTreeAdd(a, b, c)           // c = a + b (mod 2^3) using tree adder
QTreeAdd(a, b, d, result)   // result = a + b + d (mod 2^N)
```

**Semantics:**
- First N-1 arguments are inputs
- Last argument is the destination (output)
- Result = `(q1 + q2 + q3 + ...) mod 2^n`
- All operands must have matching bit widths

**Implementation:**
- Uses **tree-based carry-save/parallel adder** circuit design
- Parallelizes carry computation using balanced tree structure
- Reduces multiple partial operands in a tree (Wallace-tree inspired)
- Uses parallel controlled gates to handle carry propagation efficiently

**Circuit Structure:**
1. **Parallel computation**: Compute partial sums and carries in parallel
2. **Tree reduction**: Reduce carries using balanced tree structure
3. **Final combination**: Combine all partial sums with carries

**Advantages:**
- Significantly reduced circuit depth compared to ripple chain
- Better suited for multi-operand addition
- Space-depth tradeoffs via ancilla reuse
- Highly parallel addition operations

#### `QExpEncMult` - Exponent-Encoded Quantum Multiplication

Variadic quantum multiplication using exponent encoding:

```quanta
quint(3) a = 2
quint(3) b = 3
quint(5) out
QExpEncMult(a, b, out)         // out = a * b using exponent encoding
QExpEncMult(a, b, c, out)      // out = a * b * c
```

**Semantics:**
- First N-1 arguments are inputs
- Last argument is the destination (output)
- Result = `(q1 * q2 * q3 * ...) mod 2^n`
- Output width must be ≥ sum of input widths (ideally 2n for full precision)

**Implementation:**
- Uses **exponent-encoded multiplication** algorithm
- Encodes operands as superposition states in compact form (logarithmic qubits)
- Uses fast quantum adder (QFT-based) to sum encodings
- Extracts product from sum via measurement and classical post-processing

**Circuit Structure:**
1. **Encode operands**: Transform n-bit operands to ~log(n) qubits (exponent encoding)
2. **Fast addition**: Use QFT-based adder on encoded operands
3. **Decode result**: Transform encoded sum back to computational basis (requires measurement + classical post-processing)

**Advantages:**
- Uses only **O(log n) qubits** (plus ancilla) to represent n-bit operands
- Circuit depth can be **O(log² n)** with appropriate adders
- Gate complexity scales linearly in n while using sub-linear register widths
- Radically different resource scaling from shift-and-add

**Note:** Requires measurement and classical post-processing for decoding

#### `QTreeMult` - Tree-Based Quantum Multiplication

Variadic quantum multiplication using tree-based partial product reduction:

```quanta
quint(3) a = 2
quint(3) b = 3
quint(5) out
QTreeMult(a, b, out)         // out = a * b using tree multiplier
QTreeMult(a, b, c, out)      // out = a * b * c
```

**Semantics:**
- First N-1 arguments are inputs
- Last argument is the destination (output)
- Result = `(q1 * q2 * q3 * ...) mod 2^n`
- Output width must be ≥ sum of input widths (ideally 2n for full precision)

**Implementation:**
- Uses **tree-based multiplication** (Wallace/Dadda-style) circuit design
- Inspired by classical multipliers like Wallace tree
- Reduces partial products more efficiently using quantum reversible gates
- Uses tree of controlled adders to combine partial products efficiently

**Circuit Structure:**
1. **Generate partial products**: Create all partial products A * B[i] * 2^i in parallel
2. **Tree reduction**: Wallace/Dadda-style tree to reduce partial products
3. **Final addition**: Combine remaining partial products with fast adder (QFT or tree-based)

**Advantages:**
- Significantly less costly in **T gates** and overall depth
- Useful for devices where T-count and depth dominate performance
- Better space-depth tradeoffs than shift-and-add
- Parallelizes reductions to reduce depth vs naive shift/add

**Requires:** Ancilla qubits for partial products and intermediate results

#### `QSub` - Quantum Subtraction

Variadic quantum subtraction using ripple-borrow subtractor:

```quanta
quint(3) a = 5
quint(3) b = 3
quint(3) c
QSub(a, b, c)           // c = a - b (mod 2^3)
QSub(a, b, d, result)   // result = a - b - d (mod 2^N)
```

**Semantics:**
- First N-1 arguments are inputs
- Last argument is the destination (output)
- Result = `(q1 - q2 - q3 - ...) mod 2^n` (modular subtraction)
- All operands must have matching bit widths
- Supports modular two's complement arithmetic

**Implementation:**
- Uses **ripple-borrow subtractor** circuit design
- Similar to `QAdd` but with borrow propagation instead of carry
- Uses CNOT gates for XOR operations
- Uses Toffoli (CCX) gates for borrow computation
- Reversible: borrow bits are computed then uncomputed

**Circuit Structure:**
1. Compute bitwise differences with borrow propagation
2. Uses CNOT for XOR and CCX for borrow computation
3. Similar to `Compare` but preserves difference result
4. Reversible: borrow bits are computed then uncomputed

**Advantages:**
- Standard subtraction algorithm
- Reversible implementation
- Works well for small to medium bit widths

#### `QDiv` - Quantum Division

Quantum integer division with remainder:

```quanta
quint(4) dividend = 7
quint(4) divisor = 3
quint(4) quotient
quint(4) remainder
QDiv(dividend, divisor, quotient, remainder)  // 7 ÷ 3 = 2 R 1
```

**Semantics:**
- `QDiv(dividend, divisor, quotient, remainder)` computes both quotient and remainder
- Integer division: `quotient = floor(dividend / divisor)`
- Modulus: `remainder = dividend mod divisor`
- Both quotient and remainder registers must be same width as dividend
- Division by zero should trigger compile-time error

**Implementation:**
- Uses **repeated subtraction** algorithm
- Subtracts divisor from dividend until dividend < divisor
- Counts iterations to compute quotient
- Final dividend value is the remainder
- Requires controlled subtraction and comparison operations

**Circuit Structure:**
1. Copy dividend to remainder register
2. Initialize quotient to zero
3. Loop: while remainder >= divisor:
   - Subtract divisor from remainder (controlled)
   - Increment quotient (controlled)
   - Check if remainder >= divisor (using Compare)
4. Final remainder is the result

**Advantages:**
- Computes both quotient and remainder in one operation
- Reversible implementation
- Works for any divisor

**Note:** Full implementation requires controlled subtraction and comparison, which adds complexity.

#### `QMod` - Quantum Modulus

Variadic quantum modulus operation:

```quanta
quint(4) a = 7
quint(4) b = 3
quint(4) r
QMod(a, b, r)           // r = a mod b = 1

// With multiple divisors:
quint(4) a, b, c, result
QMod(a, b, c, result)   // result = a mod b mod c
```

**Semantics:**
- First N-1 arguments are inputs
- Last argument is the destination (output)
- Result = `(q1 mod q2 mod q3 mod ...) mod 2^n`
- All operands must have matching bit widths

**Implementation:**
- Uses **repeated subtraction** algorithm (same as division)
- Subtracts divisor from dividend until dividend < divisor
- Final value is the remainder
- For variadic case, applies modulus operations sequentially

**Circuit Structure:**
1. Copy first operand to result register
2. For each subsequent operand:
   - Repeatedly subtract operand from result
   - Continue until result < operand
3. Final result is the modulus

**Advantages:**
- Computes modular reduction efficiently
- Supports chained modulus operations
- Reversible implementation

#### Quantum Arithmetic Functions Summary

| Function | Description | Best For | Depth | Qubits | Notes |
|----------|-------------|----------|-------|--------|-------|
| `QAdd` | Ripple-carry adder | Small to medium bit widths, simple circuits | O(n) | n + ancilla | Standard, well-understood |
| `QFTAdd` | QFT-based adder (Draper) | Large bit widths, modular arithmetic | O(log n) | n + ancilla | Lower depth, used in Shor's algorithm |
| `QTreeAdd` | Tree-based parallel adder | Multi-operand addition, parallel execution | O(log n) | n + ancilla | Highly parallel, reduced depth |
| `QSub` | Ripple-borrow subtractor | Small to medium bit widths, subtraction | O(n) | n + ancilla | Standard subtraction, reversible |
| `QMult` | Shift-and-add multiplier | Small to medium bit widths | O(n²) | 2n + ancilla | Standard, straightforward |
| `QExpEncMult` | Exponent-encoded multiplier | Very large operands, space-constrained | O(log² n) | O(log n) | Logarithmic qubits, requires measurement |
| `QTreeMult` | Tree-based multiplier (Wallace/Dadda) | T-count optimization, depth-critical | O(n log n) | 2n + ancilla | Reduced T-count, better depth |
| `QDiv` | Repeated subtraction division | Small divisors, integer division | O(2ⁿ)* | 2n + ancilla | Computes quotient and remainder |
| `QMod` | Repeated subtraction modulus | Modular reduction operations | O(2ⁿ)* | n + ancilla | Computes remainder efficiently |

*Note: QDiv and QMod depth depends on the divisor value. Worst case is O(2ⁿ) for repeated subtraction.

**Choosing the Right Function:**
- **Small circuits (< 8 bits)**: Use `QAdd`, `QSub`, and `QMult` for simplicity
- **Large circuits (> 16 bits)**: Consider `QFTAdd` or `QTreeAdd` for addition
- **Space-constrained**: Use `QExpEncMult` for logarithmic qubit usage
- **T-count critical**: Use `QTreeMult` for optimized multiplication
- **Modular arithmetic**: Use `QFTAdd` (used in Shor's algorithm)
- **Subtraction**: Use `QSub` for standard subtraction operations
- **Division/Modulus**: Use `QDiv`/`QMod` for integer division and modular reduction

#### Operator Overloading

Quanta supports operator overloading for `+`, `-`, `*`, `/`, and `%` on `qint` types. By default, these operators use `QAdd`, `QSub`, `QMult`, `QDiv`, and `QMod` respectively:

```quanta
quint(3) a = 1
quint(3) b = 3
quint(3) c = a + b        // Sugar for: quint(3) c; QAdd(a, b, c)
quint(3) d = a - b        // Sugar for: quint(3) d; QSub(a, b, d)

quint(4) num1 = 2
quint(4) num2 = 3
quint(4) num3 = 4
quint(4) total = num1 + num2 + num3  // Sugar for: QAdd(num1, num2, num3, total)
quint(4) diff = num1 - num2 - num3   // Sugar for: QSub(num1, num2, num3, diff)

quint(3) r = (a + b) * c   // Compound expression with precedence
quint(4) q = a / b         // Sugar for: QDiv(a, b, q, _remainder)
quint(4) m = a % b         // Sugar for: QMod(a, b, m)

quint(4) val = 3
quint(4) sum = val + 5     // Classical constants in qint expressions
quint() out = val + sum    // Type required (quint()); bit width inferred from operands
quint(4) noop = val + 0    // Simplified: no full adder (identity)
quint(4) zero = val * 0    // Simplified: direct zero initialization
```

**Default Desugaring:**
- `quint() out = a + b` → `qint[N] out; QAdd(a, b, out)` where `N` is inferred from operand widths (`quint()` without an initializer is rejected)
- `qint[n] out = a + b` → `qint[n] out; QAdd(a, b, out)` (uses ripple-carry adder)
- `qint d = a - b` → `qint d; QSub(a, b, d)` (uses ripple-borrow subtractor)
- `qint w = a * b` → `qint w; QMult(a, b, w)` (uses shift-and-add multiplier)
- `qint q = a / b` → `qint q, _remainder; QDiv(a, b, q, _remainder)` (division with remainder)
- `qint m = a % b` → `qint m; QMod(a, b, m)` (modulus operation)
- Operator precedence: `*`, `/`, `%` bind tighter than `+`, `-`
- Automatic destination initialization
- Classical integer constants (`a + 5`, `a * 3`) are materialized as `qint` registers
- Algebraic simplification: `a + 0`, `a * 1`, `a * 0` avoid unnecessary arithmetic circuits
- Compile-time width checks: mismatched `qint[n]` operands are rejected

**Division Operator Notes:**
- The `/` operator computes the quotient and creates a temporary remainder variable
- To get both quotient and remainder, use explicit `QDiv()`:
  ```quanta
  quint(4) dividend = 7
  quint(4) divisor = 3
  quint(4) quotient, remainder
  QDiv(dividend, divisor, quotient, remainder)  // Get both values
  ```

**When to Use Explicit Function Calls:**

For optimal performance, use explicit function calls when you need specific implementations:

```quanta
// For large bit widths or modular arithmetic, use QFTAdd explicitly
quint(64) a, b, c
QFTAdd(a, b, c)          // Better than: c = a + b (which uses QAdd)

// For multi-operand addition with parallelism, use QTreeAdd
quint(16) a, b, c, d, sum
QTreeAdd(a, b, c, d, sum)  // Better than: sum = a + b + c + d

// For T-count optimization, use QTreeMult explicitly
quint(8) m1, m2, product
QTreeMult(m1, m2, product)  // Better than: product = m1 * m2

// For space-constrained scenarios, use QExpEncMult
quint(32) a, b, result
QExpEncMult(a, b, result)   // Uses logarithmic qubits

// For division with remainder, use QDiv explicitly
quint(8) dividend, divisor, quotient, remainder
QDiv(dividend, divisor, quotient, remainder)  // Get both quotient and remainder
```

**Recommendation:**
- **Small circuits (< 8 bits)**: Use operators `+`, `-`, `*`, `/`, `%` (defaults to QAdd/QSub/QMult/QDiv/QMod)
- **Large circuits (> 16 bits)**: Use explicit `QFTAdd` or `QTreeAdd` for addition
- **T-count critical**: Use explicit `QTreeMult` for multiplication
- **Space-constrained**: Use explicit `QExpEncMult`
- **Division with remainder**: Use explicit `QDiv()` to get both quotient and remainder

#### `Compare` - Quantum Comparison

```quanta
quint(3) a
quint(3) b
quint(1) flag              // or qbit flag
Compare(a, b, flag)        // flag = (a >= b)
```

**Semantics:**
- `flag` must be `quint(1)` or `qbit`
- Result usable only as **quantum control**
- `|a⟩|b⟩|0⟩ → |a⟩|b⟩|a ≥ b⟩`

#### `Grover` - Grover Operator

```quanta
quint(3) reg
H(reg)                      // Create uniform superposition
Grover(reg, 5)              // Amplify probability of reg == 5
```

**Semantics:**
- Applies Grover iteration over register `reg`
- Oracle: phase-flip states where `reg == target`
- Diffusion operator
- `target` must be classical (`int` or `bint`)
- `reg` should be in uniform superposition beforehand

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
gate Bellgate(a, b) {
    H(a)
    CNot(a, b)
}
```

Usage:

```quanta
Bellgate(q[0], q[1])
```

📌 `gate`:

- Cannot return
- Expands inline
- Accepts modifiers (`ctrl`, `inv`)

### High-Level Quantum Gates

Quanta provides built-in high-level quantum gates that compile to standard OpenQASM 3 circuits. These gates make the language more expressive and user-friendly.

#### `Bell(q0, q1)` - Bell State Preparation

Prepares a **Bell pair** (maximally entangled 2-qubit state):

```
|00⟩ → (|00⟩ + |11⟩) / √2
```

**Usage:**
```quanta
qbit[2] q
Bell(q[0], q[1])
```

**OpenQASM 3 Equivalent:**
```qasm
h q[0];
cx q[0], q[1];
```

**Explanation:**
- Hadamard on first qubit → puts it into superposition
- CNOT entangles the second qubit with the first

#### `GHZ(q0, q1, ...)` - GHZ State Preparation

Prepares a **GHZ state** on ≥2 qubits:

```
|000…⟩ → (|000…⟩ + |111…⟩) / √2
```

You can pass the **whole register**, a **slice**, or **explicit qubits**:

**Usage:**
```quanta
qbit[6] q

GHZ(q)                   // whole register → GHZ on q[0]..q[5]
GHZ(q[0], q[1], q[2])    // explicit qubits
GHZ(q[1:4])              // slice → GHZ on q[1], q[2], q[3]
```

**OpenQASM 3 Equivalent (e.g. GHZ(q[0], q[1], q[2])):**
```qasm
h q[0];
cx q[0], q[1];
cx q[1], q[2];
// ... continues chain for more qubits
```

**General rule:**  
Prepare superposition on the first qubit, then cascade CNOTs down the list.

#### `WState(q0, q1, q2)` - W State Preparation

Creates a **3-qubit W state**:

```
(|100⟩ + |010⟩ + |001⟩) / √3
```

**Usage:**
```quanta
qbit[3] q
WState(q[0], q[1], q[2])
```

**OpenQASM 3 Equivalent:**
```qasm
ry(2*acos(1/sqrt(3))) q[0];
cx q[0], q[1];
cx q[0], q[2];
```

This produces the equal-superposition of one excitation across three qubits.

#### `SwapGate(a, b)` - Swap Gate

Swaps two qubits using the standard 3-CNOT decomposition.

**Usage:**
```quanta
qbit[4] q
SwapGate(q[0], q[3])
```

**OpenQASM 3 Equivalent:**
```qasm
cx q[0], q[3];
cx q[3], q[0];
cx q[0], q[3];
```

Classic CX ladder swap.

#### `QFT(q0, q1, ...)` - Quantum Fourier Transform

Applies the **Quantum Fourier Transform** on a register of qubits.

**Usage:**
```quanta
qbit[4] q
QFT(q[0], q[1], q[2], q[3])
```

**OpenQASM 3 Equivalent:**
```qasm
h q[0];
crz(pi/2) q[1], q[0];
crz(pi/4) q[2], q[0];
crz(pi/8) q[3], q[0];

h q[1];
crz(pi/2) q[2], q[1];
crz(pi/4) q[3], q[1];

h q[2];
crz(pi/2) q[3], q[2];

h q[3];

// Bit-reversal (swap)
swap q[0], q[3];
swap q[1], q[2];
```

This is the canonical QFT decomposition.

#### `InverseQFT(q0, q1, ...)` - Inverse Quantum Fourier Transform

Applies the **Inverse Quantum Fourier Transform** (reverse of QFT).

**Usage:**
```quanta
qbit[4] q
InverseQFT(q[0], q[1], q[2], q[3])
```

**OpenQASM 3 Equivalent:**

Same gates as QFT in reverse order with `crz(-θ)` instead of `crz(θ)`.

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
int n = 3
if (n > 0) {
    n = n - 1
} else {
    n = n + 1
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

    func init(u, v) {
        a = u
        b = v
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
|`qbit[n]`|Symbolic bra-ket|
|`qint[n]`|Symbolic bra-ket (same as `qbit`)|
|`bint[n]`|Integer value|

📌 Requires the frontend statevector simulator. No amplitudes or diagnostics on hardware backends.

📌 **Case-sensitive:** the builtin must be spelled `Print()` — lowercase `print()` is not valid Quanta syntax.

##### F-string format specifiers

Format specifiers go **inside f-strings**, not as `Print()` arguments:

```quanta
Print(f"{q:summary}")       // ✅ multi-line diagnostic report
Print(q:summary)            // ❌ invalid syntax
```

|Specifier|Aliases|Output|
|---|---|---|
|*(default)*|`symbolic`, `sym`, `s`|Symbolic statevector (bra-ket notation)|
|`probabilities`|`prob`, `p`|Measurement probabilities per basis state|
|`density`|`rho`, `dm`|Density matrix|
|`entropy`|`ent`|Von Neumann entropy (4 decimal places)|
|`amplitudes`|`amp`, `amps`|Nonzero amplitudes with magnitudes|
|`summary`|`sum`|Multi-line diagnostic report (see below)|
|`bloch`||Bloch sphere (single qubit or reduced subsystem)|
|`bloch_vector`|`blochvector`, `bv`|Bloch vector tuple only|
|`circuit`|`circ`|Gate execution trace for the register|
|`pathway`|`path`, `pathway_circuit`|Step-by-step state evolution trace with entanglement tracking|

**`:summary` example** (Bell state):

```quanta
qbit[2] q
H(q[0])
CX(q[0], q[1])
Print(f"{q:summary}")
```

```
QUBIT INFO
- size: 2
- type: entangled
- purity: pure
- entropy: 1.0000

ENTANGLEMENT
- entangled_groups: ...

STATE COMPLEXITY
- basis_states: 2
- dominant_states:
  |00⟩ : 0.7071
  |11⟩ : 0.7071

PREVIEW
1/√2 * |00⟩ + 1/√2 * |11⟩
```

Works on `qbit[n]` and `qint[n]` registers (and indexed elements like `q[0]`). Classical `bint[n]` ignores quantum specifiers and prints its integer value. Combine specifiers in one f-string:

```quanta
Print(f"sym={q:symbolic} | prob={q:prob} | ent={q:entropy}")
```

#### `get_prints(quanta_code)` – Frontend debug execution (Python API)

**Frontend Debug Execution Only. Not compatible with hardware backend.**

Parses Quanta source, runs it in a statevector simulator, and returns the string that would be printed by all `Print()` calls.

- **Classical**: `Print(c)` appends the value of `c` (e.g. `[0, 1]` for a bit register).
- **Quantum**: `Print(q)` appends a symbolic state summary (e.g. `1/sqrt(2) * |0> + 1/sqrt(2) * |1>`). No state collapse.
- **Entangled subsystems**: If you print a register that is entangled with others, the full state is shown with a note: `Subsystem entangled. 1/sqrt(2) * |00> + 1/sqrt(2) * |11>`.

```python
from quanta import get_prints
terminal = get_prints("""
qbit q
H(q)
Print(q)
""")
# terminal == "1/sqrt(2) * |0> + 1/sqrt(2) * |1>"
```

**Limits:** Raises `RuntimeError` if total qubits > 20 (statevector uses 2^n memory).

#### Other Core Helpers

```quanta
Len(q)
Range(0, 3)
Measure(q, c)
reset q 
Assert(len(q) == len(c))
Error("Invalid circuit")
Warn("Simulator-only feature")
```

**Function Descriptions:**

- **`Len(q)`** - Returns the size of a quantum register, classical register, or array. Evaluated at compile-time. Useful for bounds checking and loop generation.
  ```quanta
  qbit[5] q
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

- **`Measure(q, c)`** - Measures qubit(s) to classical bit(s). Use `Measure(q[i], c[i])` for a single qubit, or `Measure(q, c)` with full registers to measure all qubits in `q` to the corresponding bits in `c` (registers must have the same size). Generates individual `measure` statements.
  ```quanta
  Measure(q[0], c[0])     // Single qubit
  Measure(q, c)          // Full registers: measure q[0]->c[0], q[1]->c[1], ...
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

### Resource Estimation & Complexity Analysis

Analyze circuits at the IR level (post macro expansion) for accurate metrics:

```python
from quanta import analyze

report = analyze("""
qbit[4] q
Bell(q[0], q[1])
QFT(q)
""")

print(f"Depth: {report.depth}")          # 8
print(f"T-count: {report.t_count}")      # 2
print(f"2Q gates: {report.two_qubit_gate_count}")  # 8
print(f"Runtime: {report.estimated_runtime}")       # "880 ns"
print(f"Qubits: {report.qubit_count}")   # 4
print(f"Gates: {report.gate_count}")     # 12
print(f"Breakdown: {report.gate_breakdown}")  # {"h": 4, "crz": 6, "swap": 2}
```

**Hardware backend fitting** — check if a circuit fits on real hardware:

```python
report = analyze(source, hardware_backends=["ibm_brisbane", "ionq_aria"])
print(report.hardware_fits)  # {"ibm_brisbane": True, "ionq_aria": True}
```

**In Quanta source**, the `Analyze()` builtin triggers the same machinery:

```quanta
qbit[4] q
Bell(q[0], q[1])
Analyze(true)  // prints resource analysis at compile time
```

**Architecture**: Analysis operates on the IR (intermediate representation) after macro expansion, not on source text — ensuring accurate depth, gate counts, and cost metrics.

### Compiler Optimization Passes

Enable optimization via `compile(..., depth_reduction=True)` or specify a hardware target for native gate lowering.

**Gate fusion** (automatic when `depth_reduction=True`):

| Pattern | Result |
|---------|--------|
| `H H` | removed (identity) |
| `X X` | removed (identity) |
| `RZ(a) RZ(b)` | `RZ(a + b)` |
| `RX(a) RX(b)` | `RX(a + b)` |
| `CNOT CNOT` (same qubits) | removed (identity) |

**Commutation** — commuting gates are reordered to enable more fusion opportunities. Gates on disjoint qubits (`H q[0]` and `H q[1]`), and same-type rotations (`RZ` with `RZ`) always commute.

**Hardware-native lowering**:

```python
# CNOT → ECR + single-qubit rotations (IBM)
qasm_ibm = compile(source, optimize_target="ibm_brisbane")

# Swap → 3 × native 2Q gate
qasm_ionq = compile(source, optimize_target="ionq_aria")
```

**Combined optimization**:

```python
qasm = compile(source, depth_reduction=True, optimize_target="ibm_brisbane")
```

### Pathway Tracing & Quantum Debugging

Visualize how individual qubit states evolve through a circuit using the `pathway` format specifier:

```quanta
qbit[2] q
H(q[0])
CNOT(q[0], q[1])
Print(f"{q:pathway}")
```

Output:
```
PATHWAY TRACE
--------------------------------
Step 1: H(q[0])
Step 2: CNOT(q[0], q[1])

TOTAL STEPS: 2
QUBITS: 2
```

Filter to a single qubit's pathway:
```quanta
Print(f"{q[0]:pathway}")
```

The pathway tracer works both at **compile time** (via `analyze(source).circuit_pathway`) and **runtime** (via `get_prints()` with the `pathway` format specifier). When qubits become entangled, the pathway shows which additional qubits are included:

```
Step 2: CNOT(q[0], q[1])
q_0, q_1: entangled CNOT operation (entangled; includes q_1)
```

### Noise / Error Simulation

Declare noise models directly in Quanta source:

```quanta
NoiseModel {
    depolarizing = 0.01
    readout = 0.03
}

qbit[2] q
Bell(q[0], q[1])
```

Then run with noise:

```python
from quanta import run

# Automatically detects NoiseModel from source
result = run(source, shots=1024, noisy=True)
```

Or specify noise parameters explicitly:

```python
result = run(source, shots=1024, noisy=True,
             depolarizing=0.01, readout_error=0.03,
             t1=150.0, t2=100.0)
```

Noise is applied via Qiskit Aer's noise model infrastructure — including depolarizing, readout, and thermal relaxation errors.

### Complete Examples

#### Example 1: Bell State

```quanta
qbit[2] q
bit[2] c

gate Bellgate(a, b) {
    H(a)
    CNot(a, b)
}

Bellgate(q[0], q[1])

Measure(q, c)
Print(c)
```

#### Example 2: Quantum Arithmetic

```quanta
// Quantum integer arithmetic
quint(3) a = 1
quint(3) b = 3
quint(3) c = a + b        // Operator overloading

// Inferred bit width (type required, size optional)
quint(4) num1 = 2
quint(4) num2 = 3
quint() sum = num1 + num2       // sum inferred as quint(4)

// Classical constant operand
quint(4) offset = num1 + 5

// Multiple operands
quint(4) d = 4
quint(4) total = num1 + num2 + d  // QAdd(num1, num2, d, total)

// Precedence: multiply before add
quint(4) r = num1 + num2 * d      // QMult(num2, d, _temp); QAdd(num1, _temp, r)

// Multiplication
quint(3) m1 = 2
quint(3) m2 = 3
quint(5) product
QMult(m1, m2, product)    // product = m1 * m2

// Comparison
quint(3) val1
quint(3) val2
quint(1) flag
Compare(val1, val2, flag)  // flag = (val1 >= val2)
```

#### Example 2b: Advanced Quantum Arithmetic

```quanta
// QFT-based addition (lower depth)
quint(8) a = 5
quint(8) b = 7
quint(8) c
QFTAdd(a, b, c)            // Fast QFT adder

// Tree-based addition (parallel)
quint(8) p = 2
quint(8) q = 3
quint(8) r = 4
quint(8) sum
QTreeAdd(p, q, r, sum)     // Parallel tree adder

// Exponent-encoded multiplication (logarithmic qubits)
quint(4) m1 = 3
quint(4) m2 = 5
quint(8) exp_product
QExpEncMult(m1, m2, exp_product)  // Uses ~log(n) qubits

// Tree-based multiplication (reduced T-count)
quint(4) n1 = 2
quint(4) n2 = 3
quint(8) tree_product
QTreeMult(n1, n2, tree_product)  // Wallace/Dadda-style
```

#### Example 2c: Subtraction, Division, and Modulus

```quanta
// Quantum subtraction
quint(4) a = 7
quint(4) b = 3
quint(4) diff = a - b        // diff = 4 (using QSub)

// Variadic subtraction
quint(4) num1 = 15
quint(4) num2 = 5
quint(4) num3 = 2
quint(4) result = num1 - num2 - num3  // result = 8 (using QSub)

// Quantum division with remainder
quint(4) dividend = 7
quint(4) divisor = 3
quint(4) quotient, remainder
QDiv(dividend, divisor, quotient, remainder)  // quotient = 2, remainder = 1

// Division using operator
quint(4) q = dividend / divisor  // q = 2 (quotient only, remainder discarded)

// Quantum modulus
quint(4) value = 7
quint(4) mod = 3
quint(4) r = value % mod     // r = 1 (using QMod)

// Chained modulus operations
quint(4) a = 25
quint(4) b = 7
quint(4) c = 3
quint(4) result = a % b % c  // result = (25 mod 7) mod 3 = 4 mod 3 = 1
```

#### Example 3: Grover's Algorithm

```quanta
quint(3) reg
H(reg)                      // Create uniform superposition
Grover(reg, 5)              // Search for value 5
bit c
Measure(reg, c)
```

#### Generated OpenQASM 3 (Bell State Example)

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
var a = 1
var b = 2;
```

Required on same line:

```quanta
var a = 1; var b = 2
```

### Identity Statement

> **Quanta is to OpenQASM 3 what Python/C# is to assembly — a static, readable, honest frontend that never pretends quantum hardware can do what it can't.**

## Documentation

- [Language Specification](docs/language.md)
- [Compiler Pipeline](docs/compiler.md)
- [Roadmap](docs/roadmap.md)

## Development

```bash
# Install in development mode (from project root)
pip install -e .[dev]

# Run the test suite (Windows) — 252 pytest tests
test.bat

# Or run pytest directly (set PYTHONPATH=src if not installed)
python -m pytest tests/ -v --tb=short

# Optional: legacy integration script in ignore/
python ignore/test.py

# Format and lint
black src
ruff check src
```

The `tests/` directory (252 tests) includes:

| Module | Coverage |
|--------|----------|
| `test_parser.py` | Parsing, string escape sequences |
| `test_doc_comments.py` | User `///` documentation comments |
| `test_examples.py` | End-to-end compile |
| `test_lowering.py` | QASM lowering, `Measure`, `qdec`/`qfloat`, high-level gates |
| `test_lowering_structured.py` | `keep_structure=True` |
| `test_indexing.py` | Fancy indexing |
| `test_tensors.py` | Tensor types and declarations |
| `test_tensor_algebra.py` | Dot/cross/elementwise/Kronecker products |
| `test_qint_operators.py` | `qint` `+`/`*`, `quint()` size inference, constants, simplification, width checks |
| `test_fidelity.py` | `Fidelity()` metric |
| `test_print_formatting.py` | f-string print specifiers |
| `test_func_overloading.py` | Function overload resolution |
| `test_grover_simulation.py` | Grover's algorithm |
| `test_numeric_types.py` | Numeric type defaults and signed semantics |
| `test_qint_arithmetic_simulation.py` | Frontend QAdd/QSub/QMult simulation |
| `test_reserved_names.py` | QASM identifier collision checks |
| `test_wildcard_types.py` | `var` / `qvar` / `cvar` matching |

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.
