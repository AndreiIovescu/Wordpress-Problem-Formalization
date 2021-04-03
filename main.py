import json
import string
from copy import deepcopy

# input from MiniZinc results
assignment_matrix = []
vm_types = []
prices = []

# problem input
components = []
offers = []
added_component = []
constraints = {}

# variables to hold the output of the algorithm
new_assignment_matrix = []
new_price_array = []
new_vm_types = []


def get_components():
    with open('data.txt') as f:
        components_list = json.load(f)
        return components_list["Components"]


def get_offers():
    with open('data.txt') as f:
        components_list = json.load(f)
        return components_list["Offers"]


def get_assignment_matrix():
    with open('data.txt') as f:
        components_list = json.load(f)
        return components_list["Assignment Matrix"]


def get_vm_types():
    with open('data.txt') as f:
        components_list = json.load(f)
        return components_list["Type Array"]


def get_constraints():
    with open('data.txt') as f:
        components_list = json.load(f)
        constraints_dict = components_list["Constraints"]
        return constraints_dict


def get_added_component():
    with open('data.txt') as f:
        components_list = json.load(f)
        added_component_id = components_list["Added Component"]
        return components[added_component_id]


def get_prices(offers_array):
    price_array = [offer['Price'] for offer in offers_array]
    return price_array


# this function computes the number of deployed instances for the component with the provided id
# that means it goes trough the assignment matrix at row 'component_id' and adds all the elements
# since a value of 1 in the assignment matrix means 'deployed' we can find the occurrence of a certain component
def compute_frequency(component_id, matrix):
    component_frequency = sum(matrix[component_id])
    return component_frequency


# checks on each machine if the component with parameter id and his conflict are both deployed
def check_conflict(constraint, matrix, component_id):
    conflict_component_id = constraint['compId']
    for column in range(len(matrix[0])):
        conflict_component_deployed = False
        component_id_deployed = False
        for row in range(len(matrix)):
            if matrix[row][column] == 1 and row == conflict_component_id:
                conflict_component_deployed = True
            elif matrix[row][column] == 1 and row == component_id:
                component_id_deployed = True
        if component_id_deployed is True and conflict_component_deployed is True:
            return False
    return True


# checks whether the component with provided id is deployed at least 'bound' times
def check_lower_bound(component_id, bound):
    if compute_frequency(component_id) >= bound:
        return True
    return False


# checks whether the component with provided id is deployed at most 'bound' times
def check_upper_bound(component_id, bound):
    if compute_frequency(component_id) <= bound:
        return True
    return False


# this function checks whether the components with the provided id are both deployed in the system
# it returns false if both are deployed, since there is no 'exclusive deployment' which needs just one to be deployed
def check_exclusive_deployment(component_id, component2_id):
    if compute_frequency(component_id) > 0 and compute_frequency(component2_id) > 0:
        return False
    return True


# this function verifies that the numerical constraint between two components is respected
# Ex: Wordpress requires at least three instances of mysql and mysql can serve at most 2 Wordpress
# this is a require provide constraint since we have limitations for both 'require' and 'provider'
def check_require_provide(component_id, component2_id, comp_instances, comp2_instances, matrix):
    if compute_frequency(component_id, matrix) * comp_instances <= compute_frequency(component2_id,
                                                                                     matrix) * comp2_instances:
        return True
    return False


# this function is similar to require provide, but this time we have no knowledge about one component in the relation
# Ex:HTTP Balancer requires at least one wordpress instance and http balancer can serve at most 3 Wordpress instances.
# we know that http requires at least 1 wordpress can serve at most 3, but we know nothing about what wordpress offers.
def check_provide(component_id, component2_id, comp_instances, matrix):
    if compute_frequency(component_id, matrix) <= comp_instances * compute_frequency(component2_id, matrix):
        return True
    return False


# function that returns for a given component all the conflicts
# it checks the conflicts dictionary for both keys and values, adding them to the conflict array for that component
def get_component_conflicts(component_id):
    conflicts = [constraint for constraint in constraints if constraint['type'] == 'Conflict']
    component_conflicts = []
    for conflict in conflicts:
        if conflict['compId'] == component_id:
            for component in conflict['compIdList']:
                if component not in component_conflicts:
                    component_conflicts.append(component)
        if component_id in conflict['compIdList'] and conflict['compId'] not in component_conflicts:
            component_conflicts.append(conflict['compId'])
    return component_conflicts


# this function checks whether on a column from the assignment matrix(machine) we could add the new component
# to do this, we first find all the components that are in conflict with the added component
# then we look on the column with the provided id if there are any components deployed that are in conflict with the
# component that we want to add
# if there is at least one we cannot possibly deploy the new component on that machine
def check_column_placement(column_id, component_id):
    if assignment_matrix[component_id][column_id] == 1:
        return False
    component_conflicts = get_component_conflicts(component_id)
    for row in range(len(assignment_matrix)):
        if assignment_matrix[row][column_id] == 1 and row in component_conflicts:
            return False
    return True


# function that returns the id of the deployed component on the column(machine) with provided id
# if no component is deployed the function returns -1
def get_deployed_component(column_id):
    for row in range(len(assignment_matrix)):
        if assignment_matrix[row][column_id] == 1:
            return row
    return -1


# function that returns the free amount of space on a given machine
# if a component is already deployed on that machine it will compute the remaining space
# otherwise it returns the entire capacity of the machine
def get_free_space(machine_id, column):
    deployed_component = get_deployed_component(column)
    if deployed_component == -1:
        free_space = [offers[machine_id][resource] for resource in offers[machine_id] if resource != 'Price']
        return free_space
    else:
        resources = [resource for resource in offers[machine_id] if resource != 'Price']
        free_space = [offers[machine_id][resource] - components[deployed_component][resource] for resource in resources]
        return free_space


# checks if the free space on a machine is enough to deploy the component with provided id
# we create a new list made of the difference between the free space on the machine and the component requirements
# therefore, if any value is smaller than 0 that means we can not deploy a component of that type on the machine
def check_enough_space(free_space, component_id):
    resources = [resource for resource in components[component_id] if resource != 'Name']
    remaining_space = [free_space[index] - components[component_id][resources[index]] for index in
                       range(len(free_space))]
    for space in remaining_space:
        if space < 0:
            return False
    return True


# build a list of all the constraints that involve the component with the parameter id
def get_component_constraints(component_id):
    component_constraints = []
    # the only keys that can contain a component id
    id_keys = ['compId', 'alphaCompId', 'betaCompId', 'compIdList']
    for constraint in constraints:
        # gets the corresponding keys for that specific constraint
        constraint_keys = [value for value in constraint if value in id_keys]
        for id_key in constraint_keys:
            # some of the keys can have lists as value so we have to check if they contain our component id
            if type(constraint[id_key]) is list:
                if component_id in constraint[id_key]:
                    component_constraints.append(constraint)
            else:
                if component_id == constraint[id_key]:
                    component_constraints.append(constraint)
    return component_constraints


def check_constraints(constraints_list, matrix, component_id):
    for constraint in constraints_list:
        constraint_name = constraint['type']
        corresponding_function = eval(f'check_{constraint_name}'.lower() + "(constraint, matrix, component_id)")
        print(corresponding_function)


# builds a new matrix by adding a column to the parameter one
# the new column has 0 on every row but the one corresponding to the component with the parameter id
def add_column(matrix, component_id):
    return_matrix = deepcopy(matrix)
    row_counter = 0
    for row in return_matrix:
        if row_counter == component_id:
            row.append(1)
        else:
            row.append(0)
        row_counter += 1
    return return_matrix


# goes on each column (which represents a machine) in our assignment matrix and checks:
# if we can put the new component on that machine regarding the conflict constraints that means,
# we can deploy it on that machine if there exists no other component, or one that is not in conflict
# then, in case we could make a case for deploying on a machine, we also have to check the capacity
# that means, we have to go and check if on that machine, there is enough space to also add the new component
# if we find a machine that satisfies both previous checks, we have to look for one last thing
# we need to take the possible new assignment matrix and verify that all the numerical constraints regarding
# the new component are satisfied
def greedy(component_id):
    for column in range(len(assignment_matrix[component_id])):
        if check_column_placement(column, component_id):
            free_space = get_free_space(vm_types[column], column)
            if check_enough_space(free_space, component_id):
                new_matrix = list.copy(assignment_matrix)
                new_matrix[component_id][column] = 1
            else:
                new_matrix = add_column(assignment_matrix, component_id)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    # initialize global variables
    components = get_components()

    offers = get_offers()
    prices = get_prices(offers)

    assignment_matrix = get_assignment_matrix()

    vm_types = get_vm_types()

    added_component = get_added_component()

    constraints = get_constraints()

    # greedy(0)

    print(check_constraints(get_component_constraints(0), assignment_matrix, 0))
