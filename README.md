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
qint[n]    // Quantum integer (N qubits)
bint[n]    // Classical bit integer (N classical bits)
```

📌 **Rules**

- These map **1:1** to OpenQASM 3 registers 
- No dynamic allocation
- `qint[n]` represents N qubits interpreted as an integer (0 to 2^n-1)
- `bint[n]` represents N classical bits (0 to 2^n-1)

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

### Quantum Integer Types (`qint` and `bint`)

#### `qint[N]` - Quantum Integer

A `qint[N]` represents **N qubits interpreted as an integer** in the computational basis:

```quanta
qint[3] x = 2    // Initialize to |010⟩
qint[4] y        // Uninitialized (|0000⟩)
```

**Properties:**
- Storage: N qubits
- Domain: 0 to 2^N - 1
- Nature: Quantum (superposition allowed)
- Copying: ❌ Forbidden
- Measurement: Explicit only
- Arithmetic: Reversible, unitary

#### `bint[N]` - Classical Bit Integer

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
qint[3] x = 2    // Initialize qubits to encode value 2
bint[3] c = 2    // Classical assignment
```

For `qint`, initialization:
1. Sets all qubits to |0⟩
2. Applies NOT (X) gates to encode the binary value

**Example:**
```quanta
qint[3] q = 2    // Binary: 010, so |010⟩
```

Generates:
```qasm
qubit[3] q;
x q[1];          // Set bit 1 (second bit) to |1⟩
```

The value `2` in binary is `010` (bits from LSB to MSB: 0, 1, 0), so only `q[1]` is set to |1⟩.

### Quantum Arithmetic Operations

#### `QAdd` - Quantum Addition

Variadic quantum addition operation:

```quanta
qint[3] a = 1
qint[3] b = 3
qint[3] c
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
qint[3] a = 2
qint[3] b = 3
qint[5] out              // Output must be wider
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
qint[3] a = 1
qint[3] b = 3
qint[3] c
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
qint[3] a = 1
qint[3] b = 3
qint[3] c
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
qint[3] a = 2
qint[3] b = 3
qint[5] out
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
qint[3] a = 2
qint[3] b = 3
qint[5] out
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
qint[3] a = 5
qint[3] b = 3
qint[3] c
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
qint[4] dividend = 7
qint[4] divisor = 3
qint[4] quotient
qint[4] remainder
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
qint[4] a = 7
qint[4] b = 3
qint[4] r
QMod(a, b, r)           // r = a mod b = 1

// With multiple divisors:
qint[4] a, b, c, result
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
qint[3] a = 1
qint[3] b = 3
qint[3] c = a + b        // Sugar for: qint[3] c; QAdd(a, b, c)
qint[3] d = a - b        // Sugar for: qint[3] d; QSub(a, b, d)

qint[4] x = 2
qint[4] y = 3
qint[4] z = 4
qint[4] total = x + y + z  // Sugar for: QAdd(x, y, z, total)
qint[4] diff = x - y - z   // Sugar for: QSub(x, y, z, diff)

qint[3] r = (a + b) * c   // Compound expression with precedence
qint[4] q = a / b         // Sugar for: QDiv(a, b, q, _remainder)
qint[4] m = a % b         // Sugar for: QMod(a, b, m)
```

**Default Desugaring:**
- `qint z = x + y` → `qint z; QAdd(x, y, z)` (uses ripple-carry adder)
- `qint d = x - y` → `qint d; QSub(x, y, d)` (uses ripple-borrow subtractor)
- `qint w = x * y` → `qint w; QMult(x, y, w)` (uses shift-and-add multiplier)
- `qint q = x / y` → `qint q, _remainder; QDiv(x, y, q, _remainder)` (division with remainder)
- `qint m = x % y` → `qint m; QMod(x, y, m)` (modulus operation)
- Operator precedence: `*`, `/`, `%` bind tighter than `+`, `-`
- Automatic destination initialization

**Division Operator Notes:**
- The `/` operator computes the quotient and creates a temporary remainder variable
- To get both quotient and remainder, use explicit `QDiv()`:
  ```quanta
  qint[4] dividend = 7
  qint[4] divisor = 3
  qint[4] quotient, remainder
  QDiv(dividend, divisor, quotient, remainder)  // Get both values
  ```

**When to Use Explicit Function Calls:**

For optimal performance, use explicit function calls when you need specific implementations:

```quanta
// For large bit widths or modular arithmetic, use QFTAdd explicitly
qint[64] a, b, c
QFTAdd(a, b, c)          // Better than: c = a + b (which uses QAdd)

// For multi-operand addition with parallelism, use QTreeAdd
qint[16] x, y, z, w, sum
QTreeAdd(x, y, z, w, sum)  // Better than: sum = x + y + z + w

// For T-count optimization, use QTreeMult explicitly
qint[8] m1, m2, product
QTreeMult(m1, m2, product)  // Better than: product = m1 * m2

// For space-constrained scenarios, use QExpEncMult
qint[32] a, b, result
QExpEncMult(a, b, result)   // Uses logarithmic qubits

// For division with remainder, use QDiv explicitly
qint[8] dividend, divisor, quotient, remainder
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
qint[3] a
qint[3] b
qint[1] flag              // or qubit flag
Compare(a, b, flag)        // flag = (a >= b)
```

**Semantics:**
- `flag` must be `qint[1]` or `qubit`
- Result usable only as **quantum control**
- `|a⟩|b⟩|0⟩ → |a⟩|b⟩|a ≥ b⟩`

#### `Grover` - Grover Operator

```quanta
qint[3] x
H(x)                      // Create uniform superposition
Grover(x, 5)              // Amplify probability of x == 5
```

**Semantics:**
- Applies Grover iteration over register `x`
- Oracle: phase-flip states where `x == target`
- Diffusion operator
- `target` must be classical (`int` or `bint`)
- `x` should be in uniform superposition beforehand

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

### Complete Examples

#### Example 1: Bell State

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

#### Example 2: Quantum Arithmetic

```quanta
// Quantum integer arithmetic
qint[3] a = 1
qint[3] b = 3
qint[3] c = a + b        // Operator overloading

// Multiple operands
qint[4] x = 2
qint[4] y = 3
qint[4] d = 4
qint[4] total = x + y + d  // QAdd(x, y, d, total)

// Multiplication
qint[3] m1 = 2
qint[3] m2 = 3
qint[5] product
QMult(m1, m2, product)    // product = m1 * m2

// Comparison
qint[3] val1
qint[3] val2
qint[1] flag
Compare(val1, val2, flag)  // flag = (val1 >= val2)
```

#### Example 2b: Advanced Quantum Arithmetic

```quanta
// QFT-based addition (lower depth)
qint[8] a = 5
qint[8] b = 7
qint[8] c
QFTAdd(a, b, c)            // Fast QFT adder

// Tree-based addition (parallel)
qint[8] x = 2
qint[8] y = 3
qint[8] z = 4
qint[8] sum
QTreeAdd(x, y, z, sum)     // Parallel tree adder

// Exponent-encoded multiplication (logarithmic qubits)
qint[4] m1 = 3
qint[4] m2 = 5
qint[8] exp_product
QExpEncMult(m1, m2, exp_product)  // Uses ~log(n) qubits

// Tree-based multiplication (reduced T-count)
qint[4] n1 = 2
qint[4] n2 = 3
qint[8] tree_product
QTreeMult(n1, n2, tree_product)  // Wallace/Dadda-style
```

#### Example 2c: Subtraction, Division, and Modulus

```quanta
// Quantum subtraction
qint[4] a = 7
qint[4] b = 3
qint[4] diff = a - b        // diff = 4 (using QSub)

// Variadic subtraction
qint[4] x = 15
qint[4] y = 5
qint[4] z = 2
qint[4] result = x - y - z  // result = 8 (using QSub)

// Quantum division with remainder
qint[4] dividend = 7
qint[4] divisor = 3
qint[4] quotient, remainder
QDiv(dividend, divisor, quotient, remainder)  // quotient = 2, remainder = 1

// Division using operator
qint[4] q = dividend / divisor  // q = 2 (quotient only, remainder discarded)

// Quantum modulus
qint[4] value = 7
qint[4] mod = 3
qint[4] r = value % mod     // r = 1 (using QMod)

// Chained modulus operations
qint[4] a = 25
qint[4] b = 7
qint[4] c = 3
qint[4] result = a % b % c  // result = (25 mod 7) mod 3 = 4 mod 3 = 1
```

#### Example 3: Grover's Algorithm

```quanta
qint[3] x
H(x)                      // Create uniform superposition
Grover(x, 5)              // Search for value 5
Measure(x, c)
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
