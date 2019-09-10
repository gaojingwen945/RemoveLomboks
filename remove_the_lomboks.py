#!/usr/bin/python
# -*- coding: UTF-8 -*-

import os
import sys
import time
import re

pass_filter = [".java"] # 设置过滤后的文件类型 当然可以设置多个类型
fail_filter = ["/build/"] # 过滤掉路径中包含指定关键字的文件
LOMBOK_ANNOTATION_Data = "Data"
LOMBOK_IMPORT_Data = "lombok.Data"

# class信息查询字典：
# {class_import_path : [src_file, class_name, package, parent_import_path, imports[], class_annotations[], class_start_line_num, class_end_line_num]}
class_info_dict = {} 
index_src_file = 0 # 源文件路径
index_class_name = 1 # 类名     
index_package = 2 # 包名
index_parent_import_path = 3 # 父类引用路径：父类包名.父类类名
index_imports = 4 # import的所有类数组
index_class_annotations = 5 # 所有定义的annotation
index_class_start_line_num = 6 # 类起始行号
index_class_end_line_num = 7 # 类结束行号

# 文件信息查询字典：
# {file_path : [package, imports[]]}
file_info_dict = {}
file_index_package = 0 # 包名
file_index_imports = 1 # import的所有类的数组
file_index_classes = 2 # 本文件定义的所有类的字典：{class_name : class_info[parent class，annotations[]，本class开始行号，本class结束行号]}
classes_index_parent_class = 0
classes_index_annotations = 1
classes_index_start_line_num = 2
classes_index_end_line_num = 3

# 类属性和方法字典：
# {class_import_path : 类属性和方法数组（不包括继承自父类的属性和方法）}
class_props_and_funcs_dict = {} 
class_index_properties = 0
class_index_functions = 1

EXIT_ON_ERROR = True
FILE_LOG = True
time_str = time.strftime('%Y-%m-%d_%H_%M_%S', time.localtime())
LOG_FILE_NAME = 'remove_lomboks_' + time_str + '.log'
MAX_TOTAL_COUNT = 1000 # 处理的文件数上限（可能会超过一点），负数表示无上限

#### 命令行可控制的选项们 ####
SAVE_MODIFICATION = False # 保存文件修改
DEBUG = False # debug模式，打印日志
SINGLE_FILE = False # 单文件模式

def log(log_str):
    time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + ": "
    # time_str = ''
    print(time_str + str(log_str))
    if FILE_LOG:
        with open(LOG_FILE_NAME, 'a') as file_object:
            file_object.write(time_str + log_str + "\n")

# 获取指定路径下所有filter过滤后的文件
def all_filtered_files(dirname, pass_filter, fail_filter):
    result = []
    for maindir, subdir, file_name_list in os.walk(dirname): # 遍历dirname
        # print("\n")
        # print("1:",maindir) # 当前目录
        # print("2:",subdir)  # 当前目录下的所有子目录
        # print("3:",file_name_list)  # 当前目录下的所有文件

        for filename in file_name_list:
            apath = os.path.join(maindir, filename)# 合并成一个完整路径
            ext = os.path.splitext(apath)[1]  # 获取文件后缀[0]获取的是除了文件名以外的内容

            if ext in pass_filter:
                fail = False
                for ff in fail_filter:
                    if apath.find(ff) >= 0:
                        fail = True
                        break
                if not fail:
                    result.append(apath)

    return result

# 返回一行中的有效内容
def get_effective_line(line):
    line = line.replace('\n', '') # 换行会影响正则替换
    # if DEBUG:
    #     log("get_effective_line ==> " + line)
    # 先去掉注释和引用中的内容
    # 去掉注释块/* */之间的内容（e.g. 替换"/*...*/" 为 ""）
    line = re.sub(r'(/\*.*\*/)+', "", line) 
    # 去掉单引号中的转义单引号（e.g. 替换"a = '\'';" 为 "a = '';"）
    line = re.sub(r'(\'\\\'*\')+', "''", line) 
    # 去掉双引号中的转义双引号（e.g. 替换"a = "\"";" 为 "a = "";"）
    line = re.sub(r'("\\"*")+', "\"\"", line) 
    # 去掉双引号之间的内容（e.g. 替换 a = "abc" 为 a = ""）
    line = re.sub(r'("[^"]*")+', "\"\"", line)  
    # 去掉单引号之间的内容（e.g. 替换 a = 'abc' 为 a = ''）
    line = re.sub(r'(\'[^\']*\')+', "''", line)
    # if DEBUG:
    #     log("get_effective_line --> " + line)
    return line

# 处理花括号
# 返回参数1：结束的左花括号行号，如果没有或者出错，返回-1
# 返回参数2：调用是否成功
def handle_curly_braces(counting_open_left_braces, line, line_num):
    pop_line_num = -1
    # inside_quote = False # 是否在引用作用域内，如 ""、'' # 在传入前已经做了处理
    for i in range(0, len(line)):
        c = line[i]
        # if c == '\'' or c == "\"":
        #     inside_quote = not inside_quote
        #     if DEBUG:
        #         print("handle_curly_braces: --> inside_quote = " + str(inside_quote))
        #     continue
        # if inside_quote:
        #     if DEBUG:
        #         print("handle_curly_braces: --> inside_quote = " + str(inside_quote))
        #     continue
        if c == '{':
            counting_open_left_braces.append(line_num)
        elif c == '}':
            if len(counting_open_left_braces) == 0:
                log("handle_curly_braces: Error --> pop from empty list!")
                log("#" + str(line_num) + " " + line)
                return -1, False
            pop_line_num = counting_open_left_braces.pop()

    # if DEBUG:
    #     print("handle_curly_braces: --> " + list_str(counting_open_left_braces) + ", pop_line_num = " + str(pop_line_num))
    return pop_line_num, True

# 查找import
def find_class_import(imports, the_class):
    for item in imports:
        class_name = get_declaration_starting_from(item, item.rfind(".") + 1)
        if the_class == class_name:
            return item
    return None

# 过滤字典item：返回下标为filter_indices中的值与给定filter_values的值完全相等的items的key列表
def filter_dict_items(data_dict, filter_indices, filter_values):
    if len(filter_indices) != len(filter_values):
        log("filter_dict_items: Error --> Indices and values should have the same length!")
        if EXIT_ON_ERROR:
            exit(0)
        else:
            return None
    result = []
    for key, value in data_dict.items():
        index = 0
        values_match = True
        for filter_index in filter_indices:
            filter_value = filter_values[index] # 目标值
            index += 1
            cur_value = value[filter_index] # 当前值
            # print(key + " : " + list_str(cur_value))
            if isinstance(cur_value, str):
                if cur_value != filter_value:
                    values_match = False
                    break
            elif isinstance(cur_value, list):
                try:
                    if cur_value.index(filter_value) < 0:
                        values_match = False
                        break
                except:
                    values_match = False
                    break
        if values_match:
            result.append(key)
    return result

def is_valid_var_char(c, exceptions = '_'):
    return c.isalnum() or (exceptions != None and c in exceptions)

def get_corresponding_property_name(function_call, prefix):
    property_name = get_declaration_starting_from(function_call, len(prefix))
    if property_name == None:
        return None
    property_name = property_name[0].lower() + property_name[1 : len(property_name)]
    return property_name

# 替换line中从start_index开始第一个出现的getter调用
# 如果obj_name为None，表示替换本类的成员函数，obj_name.function_call() --> this.property_name
# 如果obj_name不为None，表示替换引用类的函数，obj_name.function_call() --> obj_name.property_name
def replace_next_getter_call(line, start_index, obj_name, property_name, function_call):
    part_1 = line[0 : start_index]
    part_2 = line[start_index : len(line)]
    if obj_name != None:
        line = part_1 + part_2.replace(obj_name + "." + function_call + "()", obj_name + "." + property_name, 1)
    else:
        line = part_1 + part_2.replace(obj_name + "." + function_call + "()", "this." + property_name, 1)
    return line

# 替换line中从start_index开始第一个出现的setter调用
# 如果obj_name为None，表示替换本类的成员函数，function_call(...); --> this.property_name = ...;
# 如果obj_name不为None，表示替换引用类的函数，obj_name.function_call(...); --> obj_name.property_name = ...;
def replace_next_setter_call(line, start_index, obj_name, property_name, function_call):
    part_1 = line[0 : start_index]
    part_2 = line[start_index : len(line)]

    index_open_parenthesis = part_2.find("(")
    index_close_parenthesis = find_matching_close_parenthesis(part_2, index_open_parenthesis)
    if index_close_parenthesis < 0: # 找不到匹配的一对括号
        log("replace_next_setter_call: Error --> Can't find matching parenthesis " + str(index_open_parenthesis))
        print_line(line)
        if EXIT_ON_ERROR:
            exit(0)
        else:
            return line
    else:
        # 先去掉结尾的)号
        part_2 = part_2[0 : index_close_parenthesis] + part_2[index_close_parenthesis + 1 : len(part_2)]
        # 然后替换
        if obj_name != None:
            line = part_1 + part_2.replace(obj_name + "." + function_call + "(", obj_name + "." + property_name + " = ", 1)
        else:
            line = part_1 + part_2.replace(function_call + "(", "this." + property_name + " = ", 1)
    
    return line

# 查找匹配的右括号
def find_matching_close_parenthesis(line, index_open_parenthesis):
    print("find_matching_close_parenthesis: --> line = " + line + ", index_open_parenthesis = " + str(index_open_parenthesis))
    close_index = line.find(")", index_open_parenthesis)
    if index_open_parenthesis < 0 or close_index < 0:
        return -1
    while close_index >= 0 and close_index < len(line):
        left_count = line.count("(", index_open_parenthesis + 1, close_index)
        right_count = line.count(")", index_open_parenthesis + 1, close_index)
        if left_count != right_count:
            if close_index + 1 >= len(line):
                return -1
            close_index = line.find(")", close_index + 1)
        else:
            return close_index
    return -1

def has_property_or_function(class_path, type_index, value):
    if class_path not in class_props_and_funcs_dict:
        log("has_property_or_function: Error --> Class info doesn't exist in dict: " + class_path)
        if EXIT_ON_ERROR:
            exit(0)
        else:
            return False
    return value in class_props_and_funcs_dict[class_path][type_index]

def has_property_or_function_including_parents(class_path, type_index, value):
    has_property = False
    
    if has_property_or_function(class_path, type_index, value): # 当前类
        has_property = True
    else: # 逐级查找父类
        if class_path not in class_info_dict:
            log("has_property_or_function_including_parents: Error --> Class info doesn't exist in dict: " + class_path)
            if EXIT_ON_ERROR:
                exit(0)
            else:
                return has_property
        current = class_info_dict[class_path][index_parent_import_path]
        if DEBUG:
            print("has_property_or_function_including_parents: --> next parent: " + str(current))
        while current != '':
            if has_property_or_function(current, type_index, value):
                has_property = True
                break
            if current not in class_info_dict:
                log("has_property_or_function_including_parents: Error --> Class info doesn't exist in dict: " + class_path)
                if EXIT_ON_ERROR:
                    exit(0)
                else:
                    return has_property
            current = class_info_dict[current][index_parent_import_path]
    return has_property

def is_property_defined_and_not_overwritten(class_path, property_name, function_call):
    if property_name == None:
        if DEBUG:
            print("is_property_defined_and_not_overwritten: --> property_name = None")
        return False
    # 检查该属性是否有定义
    if not has_property_or_function_including_parents(class_path, class_index_properties, property_name):
        if DEBUG:
            print("is_property_defined_and_not_overwritten: --> no property called: " + property_name)
        return False
    # 检查是否有overwritten方法
    elif has_property_or_function_including_parents(class_path, class_index_functions, function_call):
        if DEBUG:
            print("is_property_defined_and_not_overwritten: --> function defined: " + function_call)
        return False
    else:
        if DEBUG:
            print("is_property_defined_and_not_overwritten: --> has property '" + property_name + "' and no function '" + function_call + "'")
        return True

# 解析类属性名
def getPropertyName(line):
    property_name = None
    if line.find("{") >= 0 or line.find("}") >= 0: # 包含大括号的都认为不是属性声明
        # print("getPropertyName: --> contains { or }")
        return property_name
    if line.find(";") < 0: # 认为不是属性声明
        return property_name
    line.replace("\n", " ")
    index_parenthesis = line.find("(")
    index_assignment = line.find("=")
    if index_parenthesis < 0: # 没有(号
        if index_assignment > 0: # 带赋值的声明
            property_name = get_declaration_before(line, index_assignment)
        else: # 不带赋值的声明
            property_name = get_declaration_before(line, line.find(";"))
    elif index_assignment > 0 and index_assignment < index_parenthesis: # 带初始化赋值的声明
        property_name = get_declaration_before(line, index_assignment)
    if DEBUG:
        print("getPropertyName: --> " + str(property_name))
    return property_name

# 解析类方法名
def getFunctionName(line):
    function_name = None
    if line.find("(") > 0 and line.find("{") > 0 and line.find("class ") < 0 and line.find("=") < 0: # 认为是方法声明
        function_name = get_declaration_before(line, line.find("("))
    if DEBUG:
        print("getFunctionName: --> " + str(function_name))
    return function_name

# 解析类的属性和方法
def parse_class_proterties_and_functions(class_path, class_info):
    if DEBUG:
        log("parse_class_proterties_and_functions: --> " + class_path)
    properties = []
    functions = []
    f = open(class_info[index_src_file], "r", encoding='utf-8') # r打开：文件内容不变
    content = f.readlines() # 修改前的文件内容
    f.close()
    class_start = class_info[index_class_start_line_num]
    class_end = class_info[index_class_end_line_num]
    line_index = class_start - 1 # 行号
    open_brace_count = 0 # '{'个数
    close_brace_count = 0 # '}'个数
    while line_index + 1 < class_end:
        # 获取下一有效行
        line, line_index = get_next_line(content, line_index)
        # 去掉注释块和引用中的内容
        line = get_effective_line(line)
        if DEBUG:
            print("parse_class_proterties_and_functions: --> ")
            print_line(line, line_index)

        open_brace_count += len(re.findall(r'{', line))
        close_brace_count += len(re.findall(r'}', line))
        if open_brace_count == close_brace_count: # 可能是class成员属性
            property_name = getPropertyName(line)
            if property_name != None:
                properties.append(property_name)
        elif open_brace_count == close_brace_count + 1: # 可能是class成员方法
            function_name = getFunctionName(line)
            if function_name != None and function_name != class_info[index_class_name]: # 非constructor的方法名
                functions.append(function_name)
        else:
            if DEBUG:
                print("parse_class_proterties_and_functions: --> inside braces")
                print("open_brace_count = " + str(open_brace_count) + ", close_brace_count = " + str(close_brace_count))

    if DEBUG:
        log("properties: " + list_str(properties))
        log("functions: " + list_str(functions))
    class_props_and_funcs_dict[class_path] = [[], []]
    class_props_and_funcs_dict[class_path][class_index_properties] = properties
    class_props_and_funcs_dict[class_path][class_index_functions] = functions

# 是否在lombok @Data类内部
# 如果是，返回lombok类名，否则返回None
def is_inside_lombok_class(lombok_file, line_num):
    classes = file_info_dict[lombok_file][file_index_classes]
    for class_name, class_info in classes.items():
        if LOMBOK_ANNOTATION_Data in class_info[classes_index_annotations] and line_num in range(class_info[classes_index_start_line_num], class_info[classes_index_end_line_num]):
            return class_name
    return None

# 适用List的str()函数
def list_str(obj):
    result = ''
    if isinstance(obj, list):
        result += "["
        index = 0
        for item in obj:
            result += str(index) + " " + list_str(item)
            index += 1
        result += "]"
    else:
        result += str(obj) + "\n"
    return result

def print_line(line, line_num = None, file_log = False):
    if not file_log:
        print("#" + str(line_num) + " " + line.replace("\n", ""))
    else:
        log("#" + str(line_num) + " " + line.replace("\n", ""))

# 查找变量声明结束的下标
def find_declaration_end(line, var_start, end, exceptions = '_'):
    for var_end in range(var_start, end): # [var_start, end)
        if not is_valid_var_char(line[var_end], exceptions):
            return var_end
    return end

# 查找line中从下标var_start开始的变量/函数名（可能不是完整的变量or函数名，取决于var_start）
def get_declaration_starting_from(line, var_start, exceptions = '_'):
    temp = line[var_start : len(line)].strip()
    var_end = find_declaration_end(temp, 0, len(temp), exceptions)
    if var_end > 0:
        return temp[0 : var_end].strip()
    else:
        return None

# 查找变量声明开始的下标
def find_declaration_start(line, start, var_end, exceptions = '_'):
    for var_start in range(var_end - 1, start - 1, -1): # [var_end - 1, start - 1)
        if not is_valid_var_char(line[var_start], exceptions):
            return var_start + 1
    return start

# 查找line中从下标var_end之前的变量/函数名（可能不是完整的变量or函数名，取决于var_end）
def get_declaration_before(line, var_end, exceptions = '_'):
    temp = line[0 : var_end].strip()
    var_start = find_declaration_start(temp, 0, len(temp), exceptions)
    if var_start >= 0:
        return temp[var_start : len(temp)].strip()
    else:
        return None

# 获取下一行，以;{}为结束
# 返回下一个index
# @param strip 为true时，拼接行时去掉中间的空格
def get_next_line(content, line_index, strip = False):
    line = content[line_index]
    line_index += 1
    if line.isspace(): # 空行
        return line, line_index

    if line.strip().startswith("@"): # 注解
        if line.find("(") > 0: # 带参数
            while line.find(")") < 0: 
                if line_index >= len(content): # 文件结束了还没遇到结束符
                    log("get_next_line: Error --> file_length = " + str(len(content)))
                    print_line(line, line_index, True)
                    if EXIT_ON_ERROR:
                        exit(0)
                    else:
                        break
                if strip:
                    line = line.strip() + content[line_index].strip()
                else:
                    line = line + content[line_index]
                line_index += 1
        if DEBUG:
            print("get_next_line: --> ")
            print_line(line, line_index)
        return line, line_index
            
    # 去掉注释块和引用中的内容
    tmp = get_effective_line(line)
    while tmp.find(";") < 0 and tmp.find("{") < 0 and tmp.find("}") < 0: # 本行并未结束，拼接下一行
        if line_index >= len(content): # 文件结束了还没遇到结束符
            log("get_next_line: Error --> file_length = " + str(len(content)))
            print_line(line, line_index, True)
            if EXIT_ON_ERROR:
                exit(0)
            else:
                break
        if strip:
            line = line.strip() + content[line_index].strip()
        else:
            line = line + content[line_index]
        # 去掉注释块和引用中的内容
        tmp = get_effective_line(line)
        line_index += 1
    if DEBUG:
        print("get_next_line: --> ")
        print_line(line, line_index)
    return line, line_index

# 返回一个文件中定义的所有class的基本信息
def parse_classes_in_file(src_file):
    if DEBUG:
        log("parse_classes_in_file: --> " + src_file)
    f = open(src_file)         # 返回一个文件对象  
    file_content = f.readlines()   
    f.close()

    classes = {} # class_name : class_info[parent class，annotations[]，本class开始行号，本class结束行号]
    line_num = 0
    package = ''
    imports = []
    key_package = "package "
    key_import = "import "
    counting_open_left_braces = [] # 当前文件中未结束的左大括号行号
    class_names = [] # 所有未结束的class_name
    cur_class = '' # 当前未结束的class_name
    cur_annotations = [] # 当前未确认所属class的annotations
    line_comment_start = -1
    has_class_def = False
    line_index = 0
    while line_index >= 0 and line_index < len(file_content):
        line_num = line_index + 1
        line = file_content[line_index]
        
        if DEBUG:
            print("parse_classes_in_file: -->")
            print_line(line, line_num)

        if line.isspace(): # 空行
            line_index += 1
            continue
        elif line.find("/*") >= 0 and line.find("*/") < 0: # 注释块开始
            line_comment_start = line_index
            if DEBUG:
                print("comment block start")
            line_index += 1
            continue
        elif line_comment_start >= 0 and line.find("*/") >= 0 and line.find("/*") < 0: # 注释块结束
            line_comment_start = -1
            if DEBUG:
                print("comment block end")
            line_index += 1
            continue
        elif line_comment_start >= 0 or line.strip().startswith("//"): # 在注释块中 or 行注释
            if DEBUG:
                print("line comment")
            line_index += 1
            continue

        # 获取下一有效行
        line, line_index = get_next_line(file_content, line_index, True)
        line_num = line_index + 1
        # 去掉注释块和引用中的内容
        line = get_effective_line(line)
        # 去掉尖括号之间的内容（e.g. 替换 <aaa> 为 <>）
        line = re.sub(r'(<[^"\']*>)+', "<>", line)
        if DEBUG:
            print("parse_classes_in_file: --> effective_line: ")
            print_line(line, line_num)

        if line.startswith(key_package): # 解析包名
            package_start = line.index(key_package) + len(key_package)
            package_end = line.rindex(";")
            package = line[package_start : package_end]
        elif line.startswith(key_import): # 解析imports
            import_start = line.index(key_import) + len(key_import)
            import_end = line.rfind(";")
            imports.append(line[import_start : import_end])
        else: 
            # 解析annotation
            if line.startswith("@"):
                annotation = get_declaration_starting_from(line, 1)
                cur_annotations.append(annotation)

            # 解析classes
            if line.startswith("class ") or line.find(" class ") >= 0: # 遇到class定义了
                if line.find("{") < 0: # 这不是一个class声明
                    continue
                has_class_def = True
                cur_class = get_declaration_starting_from(line, line.find("class ") + len("class "))
                # if DEBUG:
                #     print("cur_class = " + str(cur_class))
                if cur_class == None:
                    continue
                class_names.append(cur_class)
                classes[cur_class] = ['', [], -1, -1]
                classes[cur_class][classes_index_start_line_num] = line_num
                # 之前未确认的annotation，就认为是本class的
                classes[cur_class][classes_index_annotations] = cur_annotations 
                cur_annotations = [] # 重置
                index_extends = line.find(cur_class + " extends ")
                if index_extends > 0: # extends
                    parent_class = get_declaration_starting_from(line, index_extends + len(cur_class + " extends "), exceptions='_.')
                    if cur_class != '' and parent_class != None and parent_class != '':
                        parent_import_path = parent_class
                        if parent_class.find(".") < 0: # 查找full_path
                            parent_import_path = find_class_import(imports, parent_class)
                            if parent_import_path == None: # 不在imports中，那就是同一package的
                                parent_import_path = package + "." + parent_class
                        if DEBUG:
                            print("parse_classes_in_file: --> find parent: " + str(parent_import_path))
                        classes[cur_class][classes_index_parent_class] = parent_import_path
            
            # 查找匹配的花括号
            pop_line_num, suc = handle_curly_braces(counting_open_left_braces, line, line_num)
            if not suc:
                log("parse_classes_in_file: Error --> handle_curly_braces failed with " + src_file)
                if EXIT_ON_ERROR:
                    exit(0)
            if pop_line_num >= 0: # 找到匹配的}号
                # 如果这个}匹配了当前class的结束
                if cur_class != '' and pop_line_num == classes[cur_class][classes_index_start_line_num]:
                    # 则把cur_class设为上一级class
                    classes[cur_class][classes_index_end_line_num] = line_num 
                    if cur_class in class_names:
                        class_names.remove(cur_class)
                    if len(class_names) > 0:
                        cur_class = class_names.pop()
                    else:
                        cur_class = ''
    
    if has_class_def and len(classes) <= 0:
        log("parse_classes_in_file: Warning --> No classes found in file: " + src_file)
    if (package + "." + cur_class) in class_info_dict:
        log("parse_classes_in_file: Warning --> This class already exists in dict: " + (package + "." + cur_class))
        log(", current file: " + src_file)
        log(", previously defined in file: " + class_info_dict[package + "." + cur_class][index_src_file])

    # log("imports = " + list_str(imports))
    file_info_dict[src_file] = [package, imports, classes]
    for cur_class in classes:
        if DEBUG:
            log("import_path = " + package + "." + cur_class)
            log("parent_class = " + classes[cur_class][classes_index_parent_class])
            log("class_annotations = " + list_str(classes[cur_class][classes_index_annotations]))
        class_info_dict[package + "." + cur_class] = [src_file, cur_class, package, classes[cur_class][classes_index_parent_class], imports, classes[cur_class][classes_index_annotations], classes[cur_class][classes_index_start_line_num], classes[cur_class][classes_index_end_line_num]]

# 返回处理后的内容和下一个待处理的line_index
# @param class_path 对象obj_name对应的类引用路径
def process_line(class_path, line, obj_name):
    if DEBUG:
        print("process_line: --> line = " + str(line))
        print("process_line: --> obj_name = " + str(obj_name))

    if obj_name != None: # 对象引用
        obj_len = len(obj_name)
        start = 0
        occurance = 0
        while start < len(line): # 逐个查找匹配
            occurance = line.find(obj_name, start)
            if occurance < 0: # 没有引用
                if DEBUG and start == 0:
                    print("process_line: --> no reference in current line")
                    print_line(line)
                return line
            if (occurance > 0 and is_valid_var_char(line[occurance - 1])) or (occurance + obj_len < len(line) and is_valid_var_char(line[occurance + obj_len])): # 非obj引用
                start = occurance + obj_len # 查找下一个
                continue
            elif occurance + obj_len < len(line) - 1 and line[occurance + obj_len] == '.': # 确实是obj方法调用
                function_call = get_declaration_starting_from(line, occurance + obj_len + 1)
                line = process_function_call(class_path, line, obj_name, function_call, occurance)
                start = occurance + obj_len # 查找下一个
                continue
            else: # 其他obj引用
                start = occurance + obj_len # 查找下一个
                continue
    else: # 本类引用，由于没有找到调用本类getter方法的地方，所以目前只处理setter方法
        tmp = line.strip()
        if tmp.startswith("set"):
            start_index = line.find("set")
            function_call = get_declaration_starting_from(line, start_index)
            line = process_function_call(class_path, line, obj_name, function_call, start_index)
    if DEBUG:
        print("process_line: --> result: ")
        print_line(line)
    return line

def process_function_call(class_path, line, obj_name, function_call, start_index):
    if DEBUG:
        print("process_function_call: --> function_call = " + str(function_call) + ", start_index = " + str(start_index))
    if function_call.startswith("get"): # getter调用
        property_name = get_corresponding_property_name(function_call, "get")
        if is_property_defined_and_not_overwritten(class_path, property_name, function_call):
            # 替换当前的这次getter调用
            line = replace_next_getter_call(line, start_index, obj_name, property_name, function_call)
    elif function_call.startswith("is"): # getter调用
        property_name = get_corresponding_property_name(function_call, "is")
        if is_property_defined_and_not_overwritten(class_path, property_name, function_call):
            # 替换当前的这次getter调用
            line = replace_next_getter_call(line, start_index, obj_name, property_name, function_call)
    elif function_call.startswith("set"): # setter调用
        property_name = get_corresponding_property_name(function_call, "set")
        if is_property_defined_and_not_overwritten(class_path, property_name, function_call):
            # 替换当前的这次setter调用
            line = replace_next_setter_call(line, start_index, obj_name, property_name, function_call)
    else:
        if DEBUG:
            print("process_function_call: --> no getter or setter call")
    if DEBUG:
        print("process_function_call: --> line = " + line)
    return line

# 修改lombok @Data定义的文件
# @Return lombok类属性字典：属性：属性是否有重定义getter/setter
def process_lombok_file(lombok_file, save_modification):
    log("process_lombok_file: --> " + lombok_file)
    f = open(lombok_file, "r", encoding='utf-8') # r打开：文件内容不变
    content = f.readlines() # 修改前的文件内容
    f.close()
    content_new = '' # 修改后的文件内容
    line_index = 0
    line_num = 0 # 显示行号
    line_comment_start = -1
    while line_index >= 0 and line_index < len(content):
        line_num = line_index + 1
        line = content[line_index]

        if line.isspace(): # 空行
            content_new += line
            line_index += 1
            continue
        elif line.find("/*") >= 0 and line.find("*/") < 0: # 注释块开始
            line_comment_start = line_index
            # if DEBUG:
            #     print("comment block start")
            content_new += line
            line_index += 1
            continue
        elif line_comment_start >= 0 and line.find("*/") >= 0: # 注释块结束
            line_comment_start = -1
            # if DEBUG:
            #     print("comment block end")
            content_new += line
            line_index += 1
            continue
        elif line_comment_start >= 0 or line.strip().startswith("//") or (line.find("/*") >= 0 and line.find("*/") > line.find("/*")): # 在注释块中 or 行注释
            # if DEBUG:
            #     print("line comment")
            content_new += line
            line_index += 1
            continue  
        # 删掉import和@Data的行
        elif line.find(LOMBOK_IMPORT_Data) >= 0 or line.find("@" + LOMBOK_ANNOTATION_Data) >= 0: 
            # 跳过这一行，相当于删除
            # print("process_lombok_file: --> remove")
            line_index += 1
            continue
        else:
            lombok_class_name = is_inside_lombok_class(lombok_file, line_num)
            # 不在lombok class内部，不处理
            if lombok_class_name == None: 
                content_new += line
                line_index += 1
                if DEBUG:
                    print("process_lombok_file: --> outside lombok class, ignore")
                    print_line(line, line_num)
            # 替换属性定义（而非方法定义）的private为public
            elif line.find("private ") >= 0 and line.find("(") < 0: 
                line = line.replace("private ", "public ")
                if DEBUG:
                    print("process_lombok_file: --> replace private")
                    print_line(line, line_num)
                content_new += line
                line_index += 1
            # 替换属性定义（而非方法定义）的protected为public
            elif line.find("protected ") >= 0 and line.find("(") < 0: 
                line = line.replace("protected ", "public ")
                if DEBUG:
                    print("process_lombok_file: --> replace protected")
                    print_line(line, line_num)
                content_new += line
                line_index += 1
            # 处理可能的setter/getter替换
            else:
                class_path = file_info_dict[lombok_file][file_index_package] + "." + lombok_class_name
                line, line_index = get_next_line(content, line_index)
                line = process_line(class_path, line, None)
                content_new += line
    # if DEBUG:
    #     print("\n\n")
    #     print(content_new)

    if save_modification:
        # 把修改后的内容写入文件
        wf=open(lombok_file,'w',encoding='utf-8')  # w打开：覆盖原文件
        wf.write(content_new)
        wf.close()

# 处理引用lombok的文件
# @param is_same_package 是否为同一个package下的，同一package不需要import
def process_lombok_referred_file(lombok_class_name, lombok_import_path, is_same_package, ref_file, save_modification):
    log("process_lombok_referred_file: --> " + ref_file)
    f = open(ref_file)      # 返回一个文件对象  
    content = f.readlines() # 修改前的文件内容
    content_new = ''        # 修改后的文件内容
    f.close()
    line_num = 0            # 行号
    obj_list = []           # 对象名列表
    ref_count = 0
    # 先查找lombok类对象引用，暂不考虑代码中使用全路径方式引用的场景
    for line in content:
        line_num += 1 
        # 去掉注释块和引用中的内容
        line = get_effective_line(line)
        if line.startswith("class ") or line.find(" class ") >= 0: # 遇到class定义了
            continue

        if line.find(lombok_class_name) >= 0 and line.find("import " + lombok_import_path) < 0: # 非import的class引用
            ref_count = ref_count + 1

        class_ref_index = line.find(lombok_class_name + " ")
        while class_ref_index == 0 or (class_ref_index > 0 and is_valid_var_char(line[class_ref_index - 1]) == False): # 变量声明
            var_start = line.find(lombok_class_name) + len(lombok_class_name) + 1 # 假定class name和var name中间只有一个空格
            obj_name = get_declaration_starting_from(line, var_start)
            if obj_name != None:
                log("process_lombok_referred_file: --> Find object \"" + obj_name + "\" in line:")
                print_line(line, line_num, True)
                if obj_name not in obj_list:
                    obj_list.append(obj_name) 
            class_ref_index = line.find(lombok_class_name + " ", var_start + len(obj_name))
                    
    log("process_lombok_referred_file: --> obj_list = " + str(obj_list))
    # 如果没有找到引用，直接删除import语句，或结束
    if ref_count == 0:
        if is_same_package: # 同一package，没有引用，则不需要修改
            return
        log("process_lombok_referred_file: Info --> No reference found, remove import.")
        for line in content:
            if line.find(lombok_import_path) < 0:
                content_new += line
        if save_modification:
            # 把修改后的内容写入文件
            wf=open(ref_file,'w',encoding='utf-8')  # w打开：覆盖原文件
            wf.write(content_new)
            wf.close()
        return
    elif obj_list == []:
        log("process_lombok_referred_file: Info --> No variable found while references are present.")
        return
    else:
        line_index = 0
        line_num = 0 # 显示行号
        line_comment_start = -1
        while line_index >= 0 and line_index < len(content):
            line_num = line_index + 1
            line = content[line_index]
            # if DEBUG:
            #     print_line(line, line_num)

            if line.isspace(): # 空行
                content_new += line
                line_index += 1
                continue
            elif line.find("/*") >= 0 and line.find("*/") < 0: # 注释块开始
                line_comment_start = line_index
                # if DEBUG:
                #     print("comment block start")
                content_new += line
                line_index += 1
                continue
            elif line_comment_start >= 0 and line.find("*/") >= 0: # 注释块结束
                line_comment_start = -1
                # if DEBUG:
                #     print("comment block end")
                content_new += line
                line_index += 1
                continue
            elif line_comment_start >= 0 or line.strip().startswith("//"): # 在注释块中 or 行注释
                # if DEBUG:
                #     print("line comment")
                content_new += line
                line_index += 1
                continue      

            line, line_index = get_next_line(content, line_index)
            for obj_name in obj_list:
                line = process_line(lombok_import_path, line, obj_name)
            # if DEBUG:
            #     print_line(line, line_num)

            content_new += line  

    if save_modification:
        # 把修改后的内容写入文件
        wf=open(ref_file,'w',encoding='utf-8')  # w打开：覆盖原文件
        wf.write(content_new)
        wf.close()

if __name__=='__main__':
    # print(list_str(sys.argv))
    if len(sys.argv) >= 3 and sys.argv[2] == "1":
        SAVE_MODIFICATION = True
    if len(sys.argv) >= 4 and sys.argv[3] == "1":
        DEBUG = True
    if len(sys.argv) >= 5 and sys.argv[4] == "1":
        SINGLE_FILE = True
    print("SAVE_MODIFICATION = " + str(SAVE_MODIFICATION))
    print("DEBUG = " + str(DEBUG))
    print("SINGLE_FILE = " + str(SINGLE_FILE))

    directory = "./lombok_test_dir"
    if len(sys.argv) >= 2:
        directory = sys.argv[1]
    print("directory = " + directory)

    if SINGLE_FILE:
        parse_classes_in_file(directory)

        all_lombok_classes = filter_dict_items(class_info_dict, [index_imports, index_class_annotations], [LOMBOK_IMPORT_Data, LOMBOK_ANNOTATION_Data])
        log("main: --> Scaned " + str(len(all_lombok_classes)) + " lombok classes.")
        # log(list_str(all_lombok_classes))

        # 初始化lombok属性、方法表
        for lombok_class in all_lombok_classes:
            parse_class_proterties_and_functions(lombok_class, class_info_dict[lombok_class])
    else:
        # 获取所有的java文件
        all_java_files = all_filtered_files(directory, pass_filter, fail_filter) # 从命令行接收一个输入作为路径，获取
        # log("main: --> All java files: \n" + list_str(all_java_files) + "\n")
        log("main: --> Scaned " + str(len(all_java_files)) + " java files.")
        
        # 初始化查询表
        for file in all_java_files:
            parse_classes_in_file(file)
        log("main: --> file_info_dict.length = " + str(len(file_info_dict)))
        log("main: --> class_info_dict.length = " + str(len(class_info_dict)))
        
        all_lombok_classes = filter_dict_items(class_info_dict, [index_imports, index_class_annotations], [LOMBOK_IMPORT_Data, LOMBOK_ANNOTATION_Data])
        log("main: --> Scaned " + str(len(all_lombok_classes)) + " lombok classes.")
        # log(list_str(all_lombok_classes))

        # 初始化lombok属性、方法表
        for lombok_class in all_lombok_classes:
            parse_class_proterties_and_functions(lombok_class, class_info_dict[lombok_class])
        
        all_lombok_files = filter_dict_items(file_info_dict, [file_index_imports], [LOMBOK_IMPORT_Data])
        log("main: --> Scaned " + str(len(all_lombok_files)) + " lombok files.")
        # log(list_str(all_lombok_files))
        
        total_count = 0 # 处理的总文件数

        # 处理lombok文件
        lombok_files_processed = []
        for lombok_file in all_lombok_files:
            process_lombok_file(lombok_file, save_modification=SAVE_MODIFICATION) 
            log("main: --> Finish process lombok file: " + lombok_file)
            total_count += 1
            lombok_files_processed.append(lombok_file)

            classes_defined = file_info_dict[lombok_file][file_index_classes]
            # 处理引用lombok类的文件
            for class_name, class_info in classes_defined.items():
                lombok_class = file_info_dict[lombok_file][file_index_package] + "." + class_name
                lombok_class_info = class_info_dict[lombok_class]

                # 文件中有import lombok类的文件
                files_import_lombok = filter_dict_items(file_info_dict, [file_index_imports], [lombok_class])
                log("main: --> All files that import \"" + lombok_class + "\":\n" + list_str(files_import_lombok))

                # 和lombok文件处于同一package的文件
                files_of_same_package = filter_dict_items(file_info_dict, [file_index_package], [lombok_class_info[index_package]])
                # files_of_same_package.remove(lombok_class) # 不要去掉当前文件，因为有可能引用的地方就在当前文件中定义
                log("main: --> All files that in the same package as \"" + lombok_class + "\":\n" + list_str(files_of_same_package))

                # 暂不考虑代码中没有import、直接使用全路径引用的场景

                count = 0
                for lombok_referred_file in files_import_lombok:
                    process_lombok_referred_file(lombok_class_info[index_class_name], lombok_class, is_same_package=False, ref_file=lombok_referred_file, save_modification=SAVE_MODIFICATION)
                    count = count + 1
                    total_count += 1
                for lombok_referred_file in files_of_same_package:
                    process_lombok_referred_file(lombok_class_info[index_class_name], lombok_class, is_same_package=True, ref_file=lombok_referred_file, save_modification=SAVE_MODIFICATION)
                    count = count + 1
                    total_count += 1
                log("main: --> Finish process " + str(count) + " file(s) that refer " + lombok_class + "\n")

            if MAX_TOTAL_COUNT > 0 and total_count >= MAX_TOTAL_COUNT:
                log("main: --> lombok_files_processed: " + list_str(lombok_files_processed))
                log("main: --> Done processing " + str(total_count) + " files.\n")
                exit(0)
        log("main: --> lombok_files_processed: " + list_str(lombok_files_processed))
        log("main: --> Done processing " + str(total_count) + " files.\n")
