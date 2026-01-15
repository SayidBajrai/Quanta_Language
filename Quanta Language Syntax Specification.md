# 🧠 **Quanta Language – v1 Refined Specification**

> **Quanta is a Python-like, static quantum programming language that compiles deterministically to OpenQASM 3.**

---

## 1️⃣ Design Principles

- **Readable & familiar** (Python / C# inspired)
    
- **No abstraction leaks**: everything maps cleanly to OpenQASM 3
    
- **Explicit quantum semantics**
    
- **Static-circuit first** (no runtime quantum control in v1)
    
- **Frontend power, backend honesty**
    
- **Semicolons optional**, never required except for same-line statements
    

---

## 2️⃣ Comments

```quanta
// single-line comment
```

> No multiline comments in v1 (simplifies parsing & tooling).

---

## 3️⃣ Type System

### Primitive Types (Classical)

```text
int, float, bool, str, list, dict
```

- `var` is the default inferred type
    
- Static typing is optional but encouraged
    

---

### Quantum Types (QASM-Mapped)

```text
qubit
bit
qubit[n]
bit[n]
```

📌 **Rules**

- These map **1:1** to OpenQASM 3 registers
    
- No user-defined quantum types in v1
    
- No dynamic allocation
    

---

## 4️⃣ Variables

### Declaration

```quanta
var x = 10
int y = 3
float z = 1.23
```

- `var` → inferred, immutable type after assignment
    
- Quantum variables must be explicitly declared
    

---

### Constants & Immutability

```quanta
const N = 4
let theta = pi / 4
```

|Keyword|Meaning|
|---|---|
|`const`|Compile-time literal|
|`let`|Immutable value, resolved once|

---

## 5️⃣ Arrays (Lists)

### Literals

```quanta
list a = [1, 2, 3]
list b = [1:6]       // [1,2,3,4,5]
list c = [1:2:6]     // [1,3,5]
```

### Indexing

```quanta
a[0]
q[qidx[1]]
```

📌 **Quantum rule**

> Any array used in quantum operations **must be compile-time resolvable**.

---

## 6️⃣ Dictionaries (Maps)

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
    

---

## 7️⃣ Functions (Classical)

### Void Function

```quanta
func apply_h(q) {
    H(q)
}
```

### Typed Return

```quanta
func int add(a, b) {
    return a + b
}
```

### Inferred Return

```quanta
func var mul(a, b) {
    return a * b
}
```

📌 **Rule**

- `func name(...)` → no return
    
- `func <type> name(...)` → must return
    

---

## 8️⃣ Gate Calls (Core Feature)

### Function-Like Gate Syntax

```quanta
H(q[0])
X(q[1])
CNot(q[0], q[1])
RZ(pi/2, q[0])
```

### Built-in Gate Mapping

|Quanta|OpenQASM 3|
|---|---|
|`H(q)`|`h q;`|
|`X(q)`|`x q;`|
|`CNot(a,b)`|`cx a, b;`|
|`CZ(a,b)`|`cz a, b;`|
|`Swap(a,b)`|`swap a, b;`|
|`Measure(q,c)`|`measure q -> c;`|

📌 Gates **look like functions** but are **not functions** semantically.

---

## 9️⃣ Gate Macros (`gate`)

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
    

---

## 🔟 Controlled (ctrl) & Dagger (inv) Modifiers

### Controlled (ctrl)

```quanta
ctrl X(q[0], q[1])
ctrl[2] Z(q[0], q[1], q[2])
```

### Dagger (inv)

```quanta
inv RZ(theta, q[0])
RZ(theta, q[0])†
```

### Combined

```quanta
ctrl inv U(q[0], q[1])
```

📌 Maps directly to:

```qasm
ctrl @ inv @ U q[0], q[1];
```

🚫 Not allowed on `Measure`

---

## 🔁 Control Flow (Compile-Time)

### For Loop

```quanta
for (i in [0:3]) {
    H(q[i])
}
```

Unrolled at compile time.

---

### If / Else (Classical Only)

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
    

---

## 🧱 Classes (Frontend Only)

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
    

---

## 🖨 Standard Library (v1)

### `print()` – Debug / Frontend Runtime

```quanta
print(c)      // [1,0,0]
print(c[0])   // 1
print(q)      // |ψ⟩ (symbolic)
```

|Type|Output|
|---|---|
|Primitive|Normal|
|`bit[n]`|Measurement results|
|`qubit[n]`|Symbolic bra-ket|

📌 No amplitudes unless simulator supports it.

---

### Other Core Helpers

```quanta
len(q)
range(0, 3)
measure_all(q, c)
reset(q)
assert len(q) == len(c)
error("Invalid circuit")
warn("Simulator-only feature")
```

---

## 🧪 Complete Example

### Quanta

```quanta
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

---

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

---

## 🧩 Semicolons

Optional by default:

```quanta
var x = 1
var y = 2;
```

Required on same line:

```quanta
var x = 1; var y = 2
```

---

## 🧠 Identity Statement

> **Quanta is to OpenQASM 3 what Python/C# is to assembly — a static, readable, honest frontend that never pretends quantum hardware can do what it can’t.**
