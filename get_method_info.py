

import pickle
import csv
import subprocess
import pdb
import os
import re
import io
import json
import javalang
from datetime import datetime, timedelta

def get_method_start_end(tree, method_node):
    startpos  = None
    endpos    = None
    startline = None
    endline   = None
    for path, node in tree:
        if startpos is not None and method_node not in path:
            endpos = node.position
            endline = node.position.line if node.position is not None else None
            break
        if startpos is None and node == method_node:
            startpos = node.position
            startline = node.position.line if node.position is not None else None
    return startpos, endpos, startline, endline

def get_method_text(codelines, startpos, endpos, startline, endline, last_endline_index):
    if startpos is None:
        return "", None, None, None
    else:
        startline_index = startline - 1 
        endline_index = endline - 1 if endpos is not None else None 

        if last_endline_index is not None:
            for line in codelines[(last_endline_index + 1):(startline_index)]:
                if "@" in line: 
                    startline_index = startline_index - 1
        meth_text = "<ST>".join(codelines[startline_index:endline_index])
        meth_text = meth_text[:meth_text.rfind("}") + 1] 
        brace_diff = abs(meth_text.count("}") - meth_text.count("{"))

        for _ in range(brace_diff):
            meth_text  = meth_text[:meth_text.rfind("}")]    
            meth_text  = meth_text[:meth_text.rfind("}") + 1]     

        meth_lines = meth_text.split("<ST>")  
        meth_text  = "".join(meth_lines)                   
        last_endline_index = startline_index + (len(meth_lines) - 1) 

        return meth_text, (startline_index + 1), (last_endline_index + 1), last_endline_index



def extract_method_info(method_key):
    parts = method_key.split(":")

    # Extract class name and replace '.' with '/'
    class_name = parts[0].replace('.', '/')
    class_parts = parts[0].split(".")

    # Extract method signature
    method_signature = parts[1]

    # Extract method name
    method_name = None
    if "<init>" in method_signature:
        # Check for inner class method
        inner_class_delimiter = "$"
        if inner_class_delimiter in class_parts[-1]:
            class_name = class_name.rsplit(inner_class_delimiter, 1)[0]  # Remove inner class from class_name
        method_name = class_parts[-1]  # Use class name as method name for constructors
    else:
        method_name = method_signature.split('(')[0]
        if '$' in method_name:
            method_name = method_name.split('$', 1)[0]

    # Remove inner class name from class_name for regular methods
    if '$' in class_name:
        class_name = class_name.rsplit('$', 1)[0]

    if '$' in class_name:
        class_name = class_name.rsplit('$', 1)[0]
    # Create file path using the class name (without the inner class)
    file_path = f"{class_name}.java"

    return method_name, file_path

def extract_method_info_special_char(method_key):
    parts = method_key.split(":")

    # Extract class name and replace '.' with '/'
    class_name = parts[0].replace('.', '/')
    class_parts = parts[0].split(".")

    # Extract method signature
    method_signature = parts[1]

    # Extract method name
    method_name = None
    if "<init>" in method_signature:
        # Check for inner class method
        inner_class_delimiter = "$"
        if inner_class_delimiter in class_parts[-1]:
            class_name = class_name.rsplit(inner_class_delimiter, 1)[0]  # Remove inner class from class_name
        method_name = class_parts[-1]  # Use class name as method name for constructors
    else:
        method_name = method_signature.split('(')[0]
    
    file_path = f"{class_name}.java"

    return method_name, file_path


def make_folder_str(proj):
    input_string = proj
    chars = ""
    ints = ""

    for char in input_string:
        if char.isdigit():
            ints += char
        else:
            chars += char

    new_string = f"{chars.lower()}_{ints}_b"
    return new_string


def find_pair_value(pair_set, target):
    for pair in pair_set:
        if pair[0] == target:
            return pair[1]
    return None

def get_key_from_value(my_dict, target_value):
    for key, value in my_dict.items():
        if value == target_value:
            return int(key.split(":")[1])
    return None

def get_element_start_end(element_node, code_text):
    startline = element_node.position.line
    position = element_node.position

    # Find the opening brace of the element
    opening_brace_pos = code_text.find('{', position.column - 1 + sum(len(line) for line in code_text.splitlines(True)[:position.line - 1]))

    # Find the matching closing brace
    brace_count = 1
    closing_brace_pos = opening_brace_pos + 1
    while brace_count > 0 and closing_brace_pos < len(code_text):
        if code_text[closing_brace_pos] == '{':
            brace_count += 1
        elif code_text[closing_brace_pos] == '}':
            brace_count -= 1
        closing_brace_pos += 1

    # Convert character positions to line numbers
    endline = code_text.count('\n', 0, closing_brace_pos) + 1

    return startline, endline




def find_element_by_line(target_file, line_number):
    with open(target_file, 'r', encoding='ISO-8859-1') as r:
        codelines = r.readlines()
        code_text = ''.join(codelines)

    tree = javalang.parse.parse(code_text)
    elements_to_search = [
        javalang.tree.MethodDeclaration,
        javalang.tree.ConstructorDeclaration,
        javalang.tree.FieldDeclaration
    ]

    # List of statement-level AST node types
    statement_node_types = [
        'Statement', 'AssertStatement', 'BlockStatement', 'BreakStatement',
        'CatchClause', 'ContinueStatement', 'DoStatement', 'ForStatement',
        'IfStatement', 'ReturnStatement', 'SwitchStatement', 'SynchronizedStatement',
        'ThrowStatement', 'TryStatement', 'WhileStatement', 'EnhancedForControl'
    ]

    for element_type in elements_to_search:
        for _, element_node in tree.filter(element_type):
            startline, endline = get_element_start_end(element_node, code_text)
            try:
                if startline <= line_number <= endline:
                    element_text = "".join(codelines[startline - 1:endline])
                    element_type_name = str(element_type).split('.')[-1][:-2]
                    
                    # Extract AST node types for each line (only statement-level nodes)
                    line_node_types = {}
                    for path, node in tree:
                        if hasattr(node, 'position') and node.position:
                            if startline <= node.position.line <= endline:
                                if type(node).__name__ in statement_node_types:
                                    line_node_types[node.position.line] = type(node).__name__

                    total_lines = endline - startline + 1
                    return startline, endline, line_node_types, total_lines
            except Exception as e:
                print(e)
                # continue

    return 0, 0, {}, 0


def extract_test_method_body(filename, method_name):
    with open(filename, 'r', encoding='ISO-8859-1') as r:
        codelines = r.readlines()
        code_text = ''.join(codelines)

    tree = javalang.parse.parse(code_text)

    for _, method_node in tree.filter(javalang.tree.MethodDeclaration):
        if method_node.name == method_name:
            startline, endline = get_element_start_end(method_node, code_text)
            method_body_lines = [f"{idx + startline}: {line.lstrip()}" for idx, line in enumerate(codelines[startline - 1:endline])]
            method_body = "".join(method_body_lines)
            return method_body
    return None

def remove_chars_between(s, start, end):
    # Define the pattern to match text between start and end characters
    pattern = re.escape(start) + '.*?' + re.escape(end)
    
    # Substitute the pattern with the end character in the string
    return re.sub(pattern, end, s)

def main():
    root_path = os.getcwd()
    pkl_path_arrays = {
        'Time': ['/home/nakhla/Desktop/defects4j/OriginalPklFiles/Time_original.pkl',
                 '/Users/tahminaakter/Desktop/test/defects4j-1.2.0/Grace/Time_old/Time.pkl']
    }
    all_projects = []

    for project_root_name, pkl_paths in pkl_path_arrays.items():
        pruned_pkl_path = pkl_paths[1]

        with open(pruned_pkl_path, 'rb') as f:
            data = pickle.load(f)

            project_results = {"name": project_root_name, "bugs": []}

            for d in data:
                match = re.match(r'([a-zA-Z]+)(\d+)', d['proj'])
                if not match:
                    print(f"Failed to extract project and bug id for: {d['proj']}")
                    continue
                
                proj_name, bug_id_str = match.groups()
                bug_id = int(bug_id_str)
                print(proj_name, bug_id_str)

                folder_name = make_folder_str(proj_name + bug_id_str)

                os.chdir(f'/Users/tahminaakter/Desktop/test/defects4j-1.2.0/Grace/{project_root_name}/{folder_name}')
                dirs = os.popen('defects4j export -p dir.src.classes').readlines()[-1].strip()
                dirs_test = os.popen('defects4j export -p dir.src.tests').readlines()[-1].strip()

                bug_data = {"bug_id": bug_id, "tests": []}
                lines = d['lines']
                for key, value in d['methods'].items():

                    method_name, file_path = extract_method_info(key)
                    method_covered_line_number = find_pair_value(d['edge2'], value)
                    line_number_cinit = get_key_from_value(d['lines'], method_covered_line_number)
                    full_path = os.path.join(dirs, file_path)

                    if not os.path.exists(full_path):
                        method_name, file_path = extract_method_info_special_char(key)
                        full_path = os.path.join(dirs, file_path)

                    start, end, line_node_types, total_lines = find_element_by_line(full_path, line_number_cinit)

                    if start and end:
                        with open(full_path, 'r', encoding='ISO-8859-1') as r:
                            codelines = r.readlines()
                            method_body = f'{start}: {codelines[start - 1].strip()}'
                            
                            file_path_without_extension = file_path.replace('.java', '')
                            method_key_prefix = file_path_without_extension.replace('/', '.') + ":"
                            
                                # print(method_key_prefix)
                                # print(file_path_without_extension)
                            for i in range(start, end - 1):  # Adjusted the range to exclude the start and end
                                line_num = i + 1
                                line_key = method_key_prefix + str(line_num)
                                
                                pattern = re.escape('$') + '.*?' + re.escape(':')
                                if line_key in lines:
                                    method_body += f'\n{line_num}: {codelines[i].strip()}'
                                else:
                                    # Transform the keys using the remove_chars_between function
                                    transformed_lines = {remove_chars_between(key, '$', ':'): value for key, value in lines.items()}

                                    if line_key in transformed_lines:
                                        if bug_id == 13 and proj_name == 'Lang':
                                            print(line_key)
                                        method_body += f'\n{line_num}: {codelines[i].strip()}'
                                
                            
                            method_body += f'\n{end}: {codelines[end - 1].strip()}'
                            for line, test_id in d['edge']:
                                if line == method_covered_line_number:
                                    test_name = [name for name, tid in d['ftest'].items() if tid == test_id][0]

                                    test_class_path = test_name.rsplit('.', 1)[0].replace('.', '/')
                                    test_method_name = test_name.rsplit('.', 1)[1]
                                    test_file_path = os.path.join(dirs_test, test_class_path + '.java')

                                    if os.path.exists(test_file_path):
                                        test_method_body = extract_test_method_body(test_file_path, test_method_name)
                                        # print(test_method_body)
                                        # pdb.set_trace()
                                        test_data = next((item for item in bug_data["tests"] if item["test_name"] == test_name), None)
                                        if not test_data:
                                            test_data = {
                                                "test_name": test_name,
                                                "test_body": test_method_body,
                                                "covered_methods": []
                                            }
                                            bug_data["tests"].append(test_data)

                                        test_data["covered_methods"].append({
                                            "method_signature": key,
                                            "method_body": method_body
                                        })

                project_results["bugs"].append(bug_data)
                os.chdir(root_path)

            all_projects.append(project_results)

    # with open('chunk_structured_projects_methods.json', 'w') as outfile:
    with open('Time_bugs_linenumber_fixed.json', 'w') as outfile:
        json.dump({"projects": all_projects}, outfile, indent=4)

if __name__ == "__main__":
    main()

