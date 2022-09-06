# PyHeap

A heap dumper and analyzer for CPython based on GDB.

## Usage

Find the PID of a running CPython process you're interested in.

Run:
```bash
$ ./dump-heap.sh <pid> $(realpath .)/heap.json.gz
```

Analyze the heap with the `analyzer` module:
```bash
$ python3 -m pyheap.analyzer retained-heap --file heap.json.gz
```
(in the repo root directory).

## How it works

PyHeap uses GDB to attach to a running CPython process (the debug symbols are not required).

After the debugger is attached, a break point is set at the [`_PyEval_EvalFrameDefault`](https://github.com/python/cpython/blob/3594ebca2cacf5d9b5212d2c487fd017cd00e283/Python/ceval.c#L1577) function inside CPython, which indicated the Python stack frame execution. It's a good spot to intervene into the CPython's normal job.

When the break point is hit by one of the threads, the Python script `injector.py` is loaded and executed (as `$dump_python_heap` function) in the context of the GDB's own Python interpreter. The main purpose of this script is to make the target CPython process to load the `dumper.py` module and execute the `dump_heap` function in it.

`dump_heap` uses the Python standard modules `gc` and `sys` to collect some information about heap objects and their sizes. `dump_heap` does some job to avoid irrelevant garbage created by itself to appear in the heap dump, but some traces of it will be there.

### What objects are dumped

Currently, the dumper sees objects traced by the CPython garbage collector and the objects they reference to (more precisely, the ones they return in their [`tp_traverse`](https://docs.python.org/3/c-api/typeobj.html#c.PyTypeObject.tp_traverse)).

The thread stacks and their locals are not analyzed at the moment.

