# Quanta Language Specification

See the main [Quanta Language Syntax Specification](../Quanta%20Language%20Syntax%20Specification.md) for the complete language reference.

## Quick Reference

### Types
- Primitive: `int`, `float`, `bool`, `str`, `list`, `dict`
- Quantum: `qbit`, `bit`, `qbit[n]`, `bit[n]`, `qdec[int_bits, frac_bits]`, `qfloat[ebits, mbits]`
- Tensors: `int[n][m]`, `float[n][m]`, `qbit[2][2]`
- Structured compile: `compile(source, keep_structure=True)`

### Gate Calls
```quanta
H(q[0])
CNot(q[0], q[1])
Measure(q[0], c[0])
```

### Functions
```quanta
func bell(a, b) {
    H(a);
    CNot(a, b);
}
```

### Control Flow
```quanta
for (i in [0:3]) {
    H(q[i]);
}

if (x > 0) {
    x = x - 1;
}
```
