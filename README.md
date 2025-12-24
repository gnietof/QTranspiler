# QTranspiler
This is a small project which provides a REST service to: 
- Transpile circuits
- Apply the layout of the transpiled circuit to the observables

Additionally, other functions will be included such as:
- Rendering a circuit (original or transpiled) into an image.

The idea for this service is being able to run Quantum circuits in Java code without the limitations of not having the capability to transpile the circuit inside Java code.

## Development
The code has been developed in Python to get access to the Qiskit libraries. The server has been implemented using FastAPI which, among other benefits, automatically builds a _swagger_ page which allows the testing of the services without any extra code.
