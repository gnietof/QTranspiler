import io
from fastapi import FastAPI, HTTPException,Response
from pydantic import BaseModel

from qiskit import QuantumCircuit
from qiskit_ibm_runtime import QiskitRuntimeService,IBMBackend
from qiskit.transpiler import generate_preset_pass_manager
from qiskit.qasm3 import dumps
from qiskit.quantum_info import SparsePauliOp

from typing import List, Optional
 
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
#    observables: List[List[Pauli]]
    observables: List[Pauli]
    backend: str
    optimization_level: int = 1


class TranspileResponse(BaseModel):
    qasm: str


class LayoutResponse(BaseModel):
    qasm: str
    observables: List[Pauli]


class CircuitRequest(BaseModel):
    circuit: str    
    backend: Optional[str] = None


def build_from_script(script: str) -> QuantumCircuit:
    """
    Executes a Python script expected to define `qc`.
    """
    local_ns = {}
    global_ns = {
        "QuantumCircuit": QuantumCircuit,
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
        print("2.1")
        pass_manager = generate_preset_pass_manager(
            backend=backend,optimization_level=level
        )
        print("2.2")
        qct = pass_manager.run(qc)
        print("2.3")
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
    print("1")
    backend = resolve_backend(req.backend)
    print("2")
    qct = transpile(backend, qc, req.optimization_level)
    print("3")
    qasm=dumps(qc)

    return TranspileResponse(qasm=qasm)

@app.post("/layout", response_model=LayoutResponse)
def layout_circuit(req: LayoutRequest):

    qc = build(req.circuit)
    backend = resolve_backend(req.backend)
    qct = transpile(backend, qc, req.optimization_level)
    qasm = dumps(qct)

    # 4. Apply layout
    print(f"Before: {req.observables}")
    observables = list_to_sparse(req.observables)
    print(f"After: {observables}")
    observables2 = observables.apply_layout(qct.layout)
    paulis = sparse_to_list(observables2)
    print(f"After: {paulis}")

    return LayoutResponse(qasm=qasm, observables=paulis)

@app.post("/draw")
def draw_circuit(req: CircuitRequest):

    qc = build(req.circuit)
    
    if req.backend is not None:
        backend = resolve_backend(req.backend)
        qc = transpile(backend,qc)

    png_bytes = render(qc)
    
    return Response(
        content=png_bytes,
        media_type="image/png"
    )


