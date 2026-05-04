"""
FizzBuzz variants for the Logic Skeleton spike.

All three compute the same output for n in [1, 15], but differ in
control-flow shape. Used to test whether structural extraction
distinguishes implementations that embeddings would cluster together.
"""
from __future__ import annotations

# --- Variant A: imperative (loop + if/elif chain) ---
IMPERATIVE = '''
def fizzbuzz(n):
    results = []
    for i in range(1, n + 1):
        if i % 15 == 0:
            results.append("FizzBuzz")
        elif i % 3 == 0:
            results.append("Fizz")
        elif i % 5 == 0:
            results.append("Buzz")
        else:
            results.append(str(i))
    return results
'''

# --- Variant B: recursive (no loops, conditional recursion) ---
RECURSIVE = '''
def fizzbuzz(n, i=1, acc=None):
    if acc is None:
        acc = []
    if i > n:
        return acc
    if i % 15 == 0:
        acc.append("FizzBuzz")
    elif i % 3 == 0:
        acc.append("Fizz")
    elif i % 5 == 0:
        acc.append("Buzz")
    else:
        acc.append(str(i))
    return fizzbuzz(n, i + 1, acc)
'''

# --- Variant C: functional (comprehension + ternary chain) ---
FUNCTIONAL = '''
def fizzbuzz(n):
    return [
        "FizzBuzz" if i % 15 == 0
        else "Fizz" if i % 3 == 0
        else "Buzz" if i % 5 == 0
        else str(i)
        for i in range(1, n + 1)
    ]
'''

VARIANTS = {
    "imperative": IMPERATIVE,
    "recursive":  RECURSIVE,
    "functional": FUNCTIONAL,
}
