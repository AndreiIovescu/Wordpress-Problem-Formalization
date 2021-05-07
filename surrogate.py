import os
import csv
from minizinc import Instance, Model, Solver


def solve_surrogate_minizinc(model_path, problem_instances_number):
    # Load the model from the corresponding file
    surrogate = Model(model_path)
    # Find the solver configuration
    chuffed = Solver.lookup("chuffed")
    # Create an instance of the problem using the previous solver
    instance = Instance(chuffed, surrogate)
    # Assign the number of wordpress instances to n
    instance["n"] = problem_instances_number
    result = instance.solve()
    return result


def write_csv(file, result_dict):
    with open(file, mode='w', newline='') as f:
        fieldnames = ['wordpress_instances', 'vm_number']
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        writer.writeheader()
        for key in result_dict:
            writer.writerow({'wordpress_instances': key, 'vm_number': result_dict[key]})


def get_surrogate_results(model, lower_bound, upper_bound):
    solution_dict = {}
    for component_instances in range(lower_bound, upper_bound + 1):
        solution = solve_surrogate_minizinc(model, component_instances)
        solution_dict[component_instances] = solution['objective']
    return solution_dict


if __name__ == '__main__':
    Surrogate = "Wordpress_Surrogate.mzn"

    surrogate_results = get_surrogate_results(Surrogate, 3, 12)

    write_csv("Wordpress_Surrogate.csv", surrogate_results)
