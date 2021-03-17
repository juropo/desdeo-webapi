import json

import numpy as np
from app import db
from desdeo_problem import MOProblem, Variable, _ScalarObjective
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_restful import Resource, reqparse
from models.problem_models import Problem
from models.user_models import UserModel
from utilities.expression_parser import numpify_expressions

# The vailable problem types
available_problem_types = ["Analytical"]
supported_analytical_problem_operators = ["+", "-", "*", "/"]

# Problem creation parser
problem_create_parser = reqparse.RequestParser()
problem_create_parser.add_argument(
    "problem_type",
    type=str,
    help=f"The problem type is required and must be one of {available_problem_types}",
    required=True,
)
problem_create_parser.add_argument(
    "name",
    type=str,
    help="The problem name is required",
    required=True,
)
problem_create_parser.add_argument(
    "objective_functions",
    type=str,
    help=(
        f"If specifying an analytical problem, please provide expressions for each objective function as a string in"
        f"a list of strings."
        f"Supported operators: {supported_analytical_problem_operators}"
    ),
    required=False,
    action="append",
)
problem_create_parser.add_argument(
    "objective_names",
    type=str,
    help=(
        "If specifying an analytical problem, please provide names for each objective function as a string in"
        "a list of strings."
    ),
    required=False,
    action="append",
)
problem_create_parser.add_argument(
    "variables",
    type=str,
    help=("If specifying an analytical problem, please define the variable symbols as a list of strings."),
    required=False,
    action="append",
)
problem_create_parser.add_argument(
    "variable_names",
    type=str,
    help=("If specifying an analytical problem, please define the variable variable as a list of strings."),
    required=False,
    action="append",
)
problem_create_parser.add_argument(
    "variable_initial_values",
    type=str,
    help=("If specifying an analytical problem, please define the variable initial values as a list of floats."),
    required=True,
    action="append",
)
problem_create_parser.add_argument(
    "variable_bounds",
    type=str,
    help=(
        "If specifying an analytical problem, please define the variable bounds as a list of tuples of the form"
        "['lower_bound', 'upper_bound']."
    ),
    required=True,
    action="append",
)


class ProblemCreation(Resource):
    def get(self):
        return "Available problem types", 200

    @jwt_required()
    def post(self):
        data = problem_create_parser.parse_args()

        if data["problem_type"] not in available_problem_types:
            # check that problem type is valid, if not, return 406
            return {"message": f"The problem type must be one of {available_problem_types}"}, 406

        if data["problem_type"] == "Analytical":
            # handle analytical problem case
            if data["objective_functions"] is None:
                # no objective functions given
                return {
                    "message": "When specifying an analytical problem, objective function expressions are required"
                }, 406
            if data["objective_names"] is None:
                # if no names given, go with default names
                objective_names = [f"f_{i+1}" for i in range(len(data["objective_functions"]))]

            elif len(data["objective_names"]) != len(data["objective_functions"]):
                msg = "Bad number of objective function names given."
                return {"message": msg}, 406

            else:
                objective_names = data["objective_names"]

            if data["variables"] is None:
                return {"message": "When specifying an analytical problem, variable names must be specified"}, 406

            if data["variable_names"] is None:
                variable_names = [f"var_{i+1}" for i in range(len(data["variables"]))]

            elif len(data["variable_names"]) != len(data["variables"]):
                msg = "Bad number of variable names given."
                return {"message": msg}, 406

            else:
                variable_names = data["variable_names"]

            if len(data["variable_initial_values"]) != len(data["variables"]):
                msg = "Bad number of initial variable values given"
                return {"message": msg}, 406

            # TODO: validate objective functions
            objective_functions_str = data["objective_functions"]
            variables_str = data["variables"]
            variable_bounds_str = data["variable_bounds"]

            if len(variable_bounds_str) != len(variables_str):
                return {"message": "Bad number of variable bounds tuples given"}, 406

            # convert the bounds and initial values to a numpy array
            variable_bounds = np.array(list(map(json.loads, variable_bounds_str)))
            variable_initial_values = np.array(data["variable_initial_values"]).astype(float)

            objective_evaluators = numpify_expressions(objective_functions_str, variables_str)

            objectives = [
                _ScalarObjective(objective_names[i], evaluator) for (i, evaluator) in enumerate(objective_evaluators)
            ]

            variables = [
                Variable(variable_names[i], variable_initial_values[i], variable_bounds[i][0], variable_bounds[i][1])
                for i, x in enumerate(variables_str)
            ]

            problem = MOProblem(objectives, variables)

            current_user = get_jwt_identity()
            current_user_id = UserModel.query.filter_by(username=current_user).first().id

            db.session.add(
                Problem(
                    name=data["name"],
                    problem_type=data["problem_type"],
                    problem_pickle=problem,
                    user_id=current_user_id,
                )
            )
            db.session.commit()

            response = {"problem_type": data["problem_type"], "name": data["name"], "owner": current_user}
            return response, 201
