import io
from fastapi import FastAPI, HTTPException,Response
from pydantic import BaseModel

from qiskit import QuantumRegister, ClassicalRegister, AncillaRegister,QuantumCircuit
from qiskit_ibm_runtime import QiskitRuntimeService,IBMBackend
from qiskit.transpiler import generate_preset_pass_manager
#from qiskit.qasm3 import dumps
from qiskit.qasm2 import dumps
from qiskit.quantum_info import SparsePauliOp

from typing import List, Optional

import numpy as np
 
service = QiskitRuntimeService()
app = FastAPI(title="Qiskit Transpilation Service")

class Pauli(BaseModel):
    label:str
    coeff: float
    

class TranspileRequest(BaseModel):
    circuit: str     
    backend: str
    optimization_level: int = 1


class LayoutRequest(BaseModel):
    circuit: str     
    observables: List[List[Pauli]]
    backend: str
    optimization_level: int = 1


class TranspileResponse(BaseModel):
    qasm: str


class LayoutResponse(BaseModel):
    qasm: str
    observables: List[List[Pauli]]


class CircuitRequest(BaseModel):
    circuit: str    
    backend: Optional[str] = None
    level: Optional [int] = 0


def build_from_script(script: str) -> QuantumCircuit:
    """
    Executes a Python script expected to define `qc`.
    """
    local_ns = {}
    global_ns = {
#	"__builtins__": {},  # IMPORTANT
        "QuantumCircuit": QuantumCircuit,
        "QuantumRegister": QuantumRegister,
        "ClassicalRegister": ClassicalRegister,
        "AncillaRegister": AncillaRegister,
        "np": np
    }

    try:
        exec(script, global_ns, local_ns)
    except Exception as e:
        raise ValueError(f"Error executing circuit script: {e}")

    qc = local_ns.get("qc")
    if not isinstance(qc, QuantumCircuit):
        raise ValueError("Script must define a QuantumCircuit named 'qc'")

    return qc


def circuit_to_png(qc: QuantumCircuit) -> bytes:
    fig = qc.draw(output="mpl")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)

    return buf.read()
    
    
def list_to_sparse(paulis: list) -> SparsePauliOp:
    labels = [p.label for p in paulis]
    coeffs = [p.coeff for p in paulis]
    return SparsePauliOp(labels, coeffs)


def sparse_to_list(op: SparsePauliOp):
    return [
        {
            "label": pauli.to_label(),
            "coeff": float(coeff)
        }
        for pauli, coeff in zip(op.paulis, op.coeffs)
    ]
    
    
def resolve_backend(name: str) -> IBMBackend:
    backend = service.backend(name)
    if backend is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown backend '{req.backend}'."
        )
    else: 
    	print(f"Backend: {backend}")
    	
    return backend    
    
def build(circuit: str) -> QuantumCircuit:
    try:
        qc = build_from_script(circuit)
        return qc
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def transpile(backend: IBMBackend, qc: QuantumCircuit, level: int) -> QuantumCircuit:
    try:
        pass_manager = generate_preset_pass_manager(
            backend=backend,optimization_level=level
        )
        qct = pass_manager.run(qc)
        return qct
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transpilation failed: {e}")


def render(qc: QuantumCircuit) -> bytes:
    try:
        png_bytes = circuit_to_png(qc)
        return png_bytes
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Draw failed: {e}")


@app.post("/transpile", response_model=TranspileResponse)
def transpile_circuit(req: TranspileRequest):

    qc = build(req.circuit)
    backend = resolve_backend(req.backend)
    qct = transpile(backend, qc, req.optimization_level)
    qasm=dumps(qct)

    return TranspileResponse(qasm=qasm)

@app.post("/layout", response_model=LayoutResponse)
def layout_circuit(req: LayoutRequest):

    qc = build(req.circuit)
    backend = resolve_backend(req.backend)
    qct = transpile(backend, qc, req.optimization_level)
    qasm = dumps(qct)

    observables : List[List[Pauli]]=[]
    for oo in req.observables: 
        sparse = list_to_sparse(oo)
        mapped = sparse.apply_layout(qct.layout)
        mapped_list = sparse_to_list(mapped)
        observables.append(mapped_list)

    return LayoutResponse(qasm=qasm, observables=observables)

@app.post("/draw")
def draw_circuit(req: CircuitRequest):

    qc = build(req.circuit)
    
    if req.backend is not None:
        backend = resolve_backend(req.backend)
        qc = transpile(backend,qc,req.level)

    png_bytes = render(qc)
    
    return Response(
        content=png_bytes,
        media_type="image/png"
    )


