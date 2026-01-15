"""
CLI entry point for quanta command
"""

import sys
import argparse
from pathlib import Path
from ..api import compile, run
from ..errors import QuantaError, QuantaSyntaxError, QuantaSemanticError


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        prog="quanta",
        description="Quanta Language Compiler - Compiles Quanta to OpenQASM 3"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Compile command
    compile_parser = subparsers.add_parser("compile", help="Compile Quanta source to OpenQASM 3")
    compile_parser.add_argument("input", type=str, help="Input .qta file")
    compile_parser.add_argument("-o", "--output", type=str, help="Output .qasm file (default: stdout)")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Compile and run Quanta source")
    run_parser.add_argument("input", type=str, help="Input .qta file")
    run_parser.add_argument("--shots", type=int, default=1024, help="Number of measurement shots")
    run_parser.add_argument("--backend", type=str, help="Qiskit backend name")
    
    # Check command
    check_parser = subparsers.add_parser("check", help="Check Quanta source for errors")
    check_parser.add_argument("input", type=str, help="Input .qta file")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Read input file
    try:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: File not found: {args.input}", file=sys.stderr)
            sys.exit(1)
        
        source = input_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Execute command
    try:
        if args.command == "compile":
            qasm = compile(source)
            
            if args.output:
                output_path = Path(args.output)
                output_path.write_text(qasm, encoding="utf-8")
                print(f"Compiled to: {args.output}")
            else:
                print(qasm)
            
            sys.exit(0)
        
        elif args.command == "run":
            result = run(source, shots=args.shots, backend=args.backend)
            
            if "error" in result:
                print(f"Error: {result['error']}", file=sys.stderr)
                sys.exit(1)
            
            print(f"Results ({result['shots']} shots):")
            for state, count in sorted(result["counts"].items(), key=lambda x: -x[1]):
                print(f"  {state}: {count}")
            
            sys.exit(0)
        
        elif args.command == "check":
            # Just compile to check for errors
            compile(source)
            print("✓ No errors found")
            sys.exit(0)
    
    except QuantaSyntaxError as e:
        print(f"Syntax Error: {e}", file=sys.stderr)
        sys.exit(1)
    except QuantaSemanticError as e:
        print(f"Semantic Error: {e}", file=sys.stderr)
        sys.exit(2)
    except QuantaError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
