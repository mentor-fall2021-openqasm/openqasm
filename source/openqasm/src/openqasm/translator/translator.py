import inspect
import typing as ty
from copy import deepcopy

from qiskit.circuit import Parameter, QuantumCircuit
from qiskit.circuit.gate import Gate as QiskitGate
from qiskit.circuit.quantumregister import QuantumRegister

from openqasm.ast import (AliasStatement, AssignmentOperator, BinaryExpression,
                          BinaryOperator, BitType, BitTypeName, BooleanLiteral,
                          Box, BranchingStatement, BreakStatement,
                          CalibrationDefinition, CalibrationGrammarDeclaration,
                          ClassicalArgument, ClassicalAssignment,
                          ClassicalDeclaration, ClassicalType, ComplexType,
                          Concatenation, Constant, ConstantDeclaration,
                          ConstantName, ContinueStatement,
                          ControlDirectiveStatement, DelayInstruction,
                          DurationLiteral, DurationOf, EndStatement,
                          Expression, ExpressionStatement, ExternDeclaration,
                          ForInLoop, FunctionCall, GateModifierName,
                          Identifier, IndexExpression, IndexIdentifier,
                          IntegerLiteral, IODeclaration, IOIdentifierName,
                          NoDesignatorType, NoDesignatorTypeName, OpenNode,
                          Program, QuantumArgument, QuantumBarrier,
                          QuantumForInLoop, QuantumGate, QuantumGateDefinition,
                          QuantumGateModifier, QuantumInstruction,
                          QuantumMeasurement, QuantumMeasurementAssignment,
                          QuantumPhase, QuantumReset, QuantumStatement,
                          QuantumWhileLoop, Qubit, QubitDeclaration,
                          QubitDeclTypeName, RangeDefinition, RealLiteral,
                          ReturnStatement, Selection, SingleDesignatorType,
                          SingleDesignatorTypeName, Slice, Span, Statement,
                          StringLiteral, SubroutineDefinition, Subscript,
                          TimeUnit, TimingStatement, UnaryExpression,
                          UnaryOperator, WhileLoop)
from openqasm.translator.context import OpenQASMContext
from openqasm.translator.exceptions import UnsupportedFeature
from openqasm.translator.expressions import compute_expression
from openqasm.translator.identifiers import get_identifier
from openqasm.translator.modifiers import apply_modifier


class OpenQASM3Translator:
    """Translates an OpenQASM 3.0 AST into an instance of QuantumCircuit.

    The translation is still a work in progress. Any encountered unsupported
    feature will throw an exception that will describe what the issue was.

    In this class, a "feature" is one of the possible type for the AST nodes.
    An unsupported feature is then an AST node that cannot be processed because
    the processing code has not been implemented.

    Supported features (node types) can be listed using the
    OpenQASM3Translator.supported_features() static method.
    """

    NODE_PROCESSING_FUNCTIONS_PREFIX: str = "_process_"

    @staticmethod
    def translate(ast: Program) -> QuantumCircuit:
        """Translate the given AST to a QuantumCircuit instance.

        :return: the created QuantumCircuit instance.
        :throw UnsupportedFeature: if the AST contains at least one of the
            unsupported features.
        """
        circuit = QuantumCircuit()
        context = OpenQASMContext()
        for statement in ast.statements:
            OpenQASM3Translator._process_Statement(statement, circuit, context)
        return circuit

    @staticmethod
    def _process_Statement(
        statement: Statement, circuit: QuantumCircuit, context: OpenQASMContext
    ) -> ty.Any:
        statement_type: ty.Type = type(statement)
        statement_type_name: str = statement_type.__name__
        processing_function_name: str = (
            OpenQASM3Translator.NODE_PROCESSING_FUNCTIONS_PREFIX + statement_type_name
        )
        # If the node is not supported yet, raise an exception.
        if not hasattr(OpenQASM3Translator, processing_function_name):
            raise UnsupportedFeature(statement_type_name)
        # Process the node.
        return getattr(OpenQASM3Translator, processing_function_name)(statement, circuit, context)

    @staticmethod
    def supported_features() -> ty.List[str]:
        """Return a list of the supported AST node types names."""
        prefix: str = OpenQASM3Translator.NODE_PROCESSING_FUNCTIONS_PREFIX
        return [
            method_name[len(prefix) :]
            for method_name, method in inspect.getmembers(
                OpenQASM3Translator, predicate=inspect.isfunction
            )
            if method_name.startswith(prefix)
        ]

    @staticmethod
    def _process_QubitDeclaration(
        statement: QubitDeclaration, circuit: QuantumCircuit, context: OpenQASMContext
    ) -> None:
        """Process any QubitDeclaration node in the AST.

        The QubitDeclTypeName is not used because it is only used to make the
        AST retro-compatible with OpenQASM2, providing a way to distinguish
        between "qreg" and "qubit".

        :param statement: the AST node to process
        :param circuit: the QuantumCircuit instance to modify according to the
            AST node.
        :param context: the parsing context used to perform symbol lookup.
        """
        qubit: Qubit = statement.qubit
        designator: ty.Optional[Expression] = statement.designator

        quantum_register_size: int = 1  # Default value if designator is None
        if designator is not None:
            quantum_register_size = compute_expression(designator, context)
        register = QuantumRegister(size=quantum_register_size, name=qubit.name)
        circuit.add_register(register)
        context.add_symbol(qubit.name, register, statement.span)

    @staticmethod
    def _process_ConstantDeclaration(
        statement: ConstantDeclaration, circuit: QuantumCircuit, context: OpenQASMContext
    ) -> None:
        """Process any ConstantDeclaration node in the AST.

        :param statement: the AST node to process
        :param circuit: the QuantumCircuit instance to modify according to the
            AST node.
        :param context: the parsing context used to perform symbol lookup.
        """
        if statement.init_expression is None:
            context.declare_symbol(statement.identifier.name, statement.identifier.span)
        else:
            context.add_symbol(
                statement.identifier.name,
                compute_expression(statement.init_expression, context),
                statement.span,
            )

    @staticmethod
    def _process_ClassicalDeclaration(
        statement: ClassicalDeclaration, circuit: QuantumCircuit, context: OpenQASMContext
    ) -> None:
        """Process any ClassicalDeclaration node in the AST.

        :param statement: the AST node to process
        :param circuit: the QuantumCircuit instance to modify according to the
            AST node.
        :param context: the parsing context used to perform symbol lookup.
        """
        # TODO: is there anything to do with the type?
        type_: ClassicalType = statement.type
        name: str = statement.identifier.name
        init_expression: ty.Optional[Expression] = statement.init_expression
        if init_expression is None:
            context.declare_symbol(name, statement.identifier.span)
        else:
            context.add_symbol(name, compute_expression(init_expression, context), statement.span)

    @staticmethod
    def _process_QuantumReset(
        statement: QuantumReset, circuit: QuantumCircuit, context: OpenQASMContext
    ) -> None:
        """Process any QuantumReset node in the AST.

        :param statement: the AST node to process
        :param circuit: the QuantumCircuit instance to modify according to the
            AST node.
        :param context: the parsing context used to perform symbol lookup.
        """
        for qubit in statement.qubits:
            circuit.reset(get_identifier(qubit, context))

    @staticmethod
    def _process_QuantumGate(
        statement: QuantumGate, circuit: QuantumCircuit, context: OpenQASMContext
    ) -> None:
        """Process any QuantumGate node in the AST.

        :param statement: the AST node to process
        :param circuit: the QuantumCircuit instance to modify according to the
            AST node.
        :param context: the parsing context used to perform symbol lookup.
        """
        arguments: ty.List = [compute_expression(arg, context) for arg in statement.arguments]
        quantum_gate: QiskitGate = context.lookup(statement.name, statement.span)(*arguments)
        qubits: ty.List = [get_identifier(qubit, context) for qubit in statement.qubits]

        for modifier in statement.modifiers:
            quantum_gate = apply_modifier(quantum_gate, modifier, context)

        circuit.append(quantum_gate, qargs=qubits)

    @staticmethod
    def _process_QuantumGateDefinition(
        statement: QuantumGateDefinition, circuit: QuantumCircuit, context: OpenQASMContext
    ) -> None:
        """Process any QuantumGateDefinition node in the AST.

        :param statement: the AST node to process
        :param circuit: the QuantumCircuit instance to modify according to the
            AST node.
        :param context: the parsing context used to perform symbol lookup.
        """
        argument_number: int = len(statement.arguments)
        quantum_gate_name: str = statement.name
        qubit_names: ty.List[str] = [q.name for q in statement.qubits]
        qubit_indices: ty.Dict[str, int] = {qn: qi for qi, qn in enumerate(qubit_names)}

        argument_names: ty.List[str] = [arg.name for arg in statement.arguments]

        # Creating the QuantumCircuit instance that will represent this gate
        # along with the context of the gate.
        gate_definition = QuantumCircuit(len(qubit_names))
        gate_definition_context = deepcopy(context)
        for qubit, (qn, qi) in zip(statement.qubits, qubit_indices.items()):
            gate_definition_context.add_symbol(qn, qi, qubit.span)
        for arg, argname in zip(statement.arguments, argument_names):
            gate_definition_context.add_symbol(argname, Parameter(argname), arg.span)
        for st in statement.body:
            OpenQASM3Translator._process_Statement(st, gate_definition, gate_definition_context)

        def quantum_gate(
            *parameters: ty.Any, circuit=gate_definition, argnames=argument_names
        ) -> QiskitGate:
            return circuit.to_gate({argnames[i]: pvalue for i, pvalue in enumerate(parameters)})

        context.add_symbol(quantum_gate_name, quantum_gate, statement.span)

    @staticmethod
    def _process_QuantumPhase(
        statement: QuantumPhase, circuit: QuantumCircuit, context: OpenQASMContext
    ) -> None:
        """Process any QuantumPhase node in the AST.

        :param statement: the AST node to process
        :param circuit: the QuantumCircuit instance to modify according to the
            AST node.
        :param context: the parsing context used to perform symbol lookup.
        """
        phase: float = compute_expression(statement.argument, context)
        qubits: ty.List = sum(
            (get_identifier(qubit, context) for qubit in statement.qubits), start=[]
        )
        if not qubits:
            # Global phase on all the circuit
            circuit.global_phase += phase
        else:
            # Global phase with potential modifiers
            phased_gate = QuantumCircuit(1, global_phase=phase).to_gate()
            for modifier in statement.quantum_gate_modifiers:
                phased_gate = apply_modifier(phased_gate, modifier, context)
            circuit.append(phased_gate, qargs=qubits)