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

# class信息查询字典：{class_import_path : [src_file, class_name, package, parent_import_path, imports[], 
#                                       class_annotations[], class_start_line_num, class_end_line_num]}
class_info_dict = {} 
index_src_file = 0 # 源文件路径
index_class_name = 1 # 类名     
index_package = 2 # 包名
index_parent_import_path = 3 # 父类引用路径：父类包名.父类类名
index_imports = 4 # import的所有类数组
index_class_annotations = 5 # 所有定义的annotation
index_class_start_line_num = 6 # 类起始行号
index_class_end_line_num = 7 # 类结束行号
# 文件信息查询字典：{file_path : [package, imports[]]}
file_info_dict = {}
file_index_package = 0 # 包名
file_index_imports = 1 # import的所有类的数组
file_index_classes = 2 # 本文件定义的所有类的字典：{class_name : class_info[parent class，annotations[]，本class开始行号，本class结束行号]}
classes_index_parent_class = 0
classes_index_annotations = 1
classes_index_start_line_num = 2
classes_index_end_line_num = 3
# 类属性和方法字典：{class_import_path : 类属性和方法数组（不包括继承自父类的属性和方法）}
class_props_and_funcs_dict = {} 
class_index_properties = 0
class_index_functions = 1

has_override_getter = "getter"
has_override_setter = "setter"

SAVE_MODIFICATION = False
FILE_LOG = True
time_str = time.strftime('%Y-%m-%d_%H_%M_%S', time.localtime())
LOG_FILE_NAME = 'remove_lomboks_' + time_str + '.log'
MAX_TOTAL_COUNT = 10 # 处理的文件数上限（可能会超过一点），负数表示无上限
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

# 返回一个文件中定义的所有class的基本信息
def parse_classes_in_file(src_file, class_info_dict, file_info_dict):
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
    for line_index in range(0, len(file_content)):
        line_num = line_index + 1
        line = file_content[line_index]
        if DEBUG:
            log("==> #" + str(line_num) + " " + line)

        if line.find("/*") >= 0 and line.find("*/") < 0: # 注释块开始
            line_comment_start = line_index
            if DEBUG:
                print("comment block start")
            continue
        elif line_comment_start >= 0 and line.find("*/") >= 0: # 注释块结束
            line_comment_start = -1
            if DEBUG:
                print("comment block end")
            continue
        elif line_comment_start >= 0 or line.strip().startswith("//"): # 在注释块中 or 行注释
            if DEBUG:
                print("line comment")
            continue

        if line.startswith(key_package): # 解析包名
            package_start = line.index(key_package) + len(key_package)
            package_end = line.rindex(";")
            package = line[package_start : package_end]
        elif line.startswith(key_import): # 解析imports
            import_start = line.index(key_import) + len(key_import)
            import_end = line.rfind(";")
            if import_end < 0: # 换行了
                line_index += 1
                next_line = file_content[line_index].strip()
                line = line.replace("\n", "").rstrip() + next_line # 拼接
                import_end = len(line)
            imports.append(line[import_start : import_end])
        else: 
            # 先去掉引用中的内容
            # 去掉转义双引号之间的内容（e.g. 替换"a = \"abc\";" 为 "a = '';"）
            line = re.sub(r'(\\"[^"\']*\\")+', "''", line) 
            # 去掉双引号之间的内容（e.g. 替换 a = "abc" 为 a = ""）
            line = re.sub(r'("[^"\']*")+', "\"\"", line) 
            # 去掉转义单引号之间的内容（e.g. 替换'a = \'abc\';' 为 'a = "";'）
            line = re.sub(r'(\\\'[^"\']*\\\')+', "\"\"", line)     
            # 去掉单引号之间的内容（e.g. 替换 a = 'abc' 为 a = ''）
            line = re.sub(r'(\'[^"\']*\')+', "''", line)
            if DEBUG:
                log("--> *" + str(line_num) + " " + line)

            # 解析annotation
            if line.startswith("@"):
                annotation = find_declaration_after(line, 1)
                cur_annotations.append(annotation)

            # 解析classes
            if line.startswith("class ") or line.find(" class ") >= 0: # 遇到class定义了
                has_class_def = True
                while line.find("{") < 0 and line_index < len(file_content) - 1: # 换行了
                    line_index += 1
                    next_line = file_content[line_index].strip()
                    line = line.replace("\n", "").rstrip() + next_line # 拼接
                if line.find("{") < 0: # 这不是一个class声明
                    continue
                cur_class = find_declaration_after(line, line.find("class ") + len("class "))
                if DEBUG:
                    print("cur_class = " + cur_class)
                if cur_class == None:
                    continue
                class_names.append(cur_class)
                classes[cur_class] = ['', [], -1, -1]
                classes[cur_class][classes_index_start_line_num] = line_num
                # 之前未确认的annotation，就认为是本class的
                classes[cur_class][classes_index_annotations] = cur_annotations 
                cur_annotations = [] # 重置
                index_extends = line.find(" extends ")
                while index_extends > 0: # extends
                    index_left_angle_bracket = line.find("<")
                    index_right_angle_bracket = line.find(">")
                    # 在<>内部的extends，不是用来修饰class的
                    if index_left_angle_bracket < 0 or index_extends <= index_left_angle_bracket or (index_right_angle_bracket >= 0 and index_extends >= index_right_angle_bracket):
                        parent_class = find_declaration_after(line, index_extends + len(" extends "))
                        if cur_class != '' and parent_class != None and parent_class != '':
                            parent_import_path = parent_class
                            if parent_class.find(".") < 0: # 查找full_path
                                parent_import_path = find_class_import(imports, parent_class)
                                if parent_import_path == None: # 不在imports中，那就是同一package的
                                    parent_import_path = package + "." + parent_class
                            classes[cur_class][classes_index_parent_class] = parent_import_path
                    index_extends = line.find(" extends ", index_extends + len(" extends "))
            
            # 查找匹配的花括号
            pop_line_num, suc = handle_curly_braces(counting_open_left_braces, line, line_num)
            if not suc:
                log("parse_classes_in_file: Error --> handle_curly_braces failed with " + src_file)
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
        # log("import_path = " + package + "." + cur_class)
        # log("parent_class = " + classes[cur_class][classes_index_parent_class])
        if DEBUG:
            log("class_annotations = " + list_str(classes[cur_class][classes_index_annotations]))
        class_info_dict[package + "." + cur_class] = [src_file, cur_class, package, classes[cur_class][classes_index_parent_class], imports, classes[cur_class][classes_index_annotations], classes[cur_class][classes_index_start_line_num], classes[cur_class][classes_index_end_line_num]]

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
                return -1, False
            pop_line_num = counting_open_left_braces.pop()

    # if DEBUG:
    #     print("handle_curly_braces: --> " + list_str(counting_open_left_braces) + ", pop_line_num = " + str(pop_line_num))
    return pop_line_num, True

# 查找import
def find_class_import(imports, the_class):
    for item in imports:
        class_name = find_declaration_after(item, item.rfind(".") + 1)
        if the_class == class_name:
            return item
    return None

# 过滤字典item：返回下标为filter_indices中的值与给定filter_values的值完全相等的items的key列表
def filter_dict_items(data_dict, filter_indices, filter_values):
    if len(filter_indices) != len(filter_values):
        log("filter_dict_items: Error --> Indices and values should have the same length!")
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

# 检查小括号是否匹配
def is_parenthesis_match(str, index_left_parenthesis, index_right_parenthesis):
    left_count = str.count("(", index_left_parenthesis + 1, index_right_parenthesis)
    right_count = str.count(")", index_left_parenthesis + 1, index_right_parenthesis)
    return left_count == right_count

# 替换obj_name.prefixXxx()为obj_name.xxx
# @param prefix: "get" or "is"
def replace_getter(line, line_num, obj_name, prefix):
    log("replace_getter: ==> #" + str(line_num) + " " + line.replace("\n", ""))
    getter_prefix = obj_name + "." + prefix
    index_indent = line.find(getter_prefix)
    # indent_str = line[0 : index_indent] # 替换内容前的其他内容
    index_var_name = index_indent + len(getter_prefix) # 变量名index
    first_char = line[index_var_name].lower() # 变量名首字母小写
    index_parentheses = line.find('()', index_var_name)
    var_name = first_char + line[(index_var_name + 1) : index_parentheses]
    line = line.replace(getter_prefix + line[index_var_name : index_parentheses + 2], obj_name + "." + var_name)
    log("replace_getter: --> *" + str(line_num) + " " + line)
    return line

# 替换setter
# 如果obj_name为None，表示替换本类的成员函数，将setXxx(...);替换为this.xxx = ...;
# 如果obj_name不为None，表示替换引用类的成员函数，将obj_name.setXxx(...);替换为obj_name.xxx = ...;
def replace_setter(line, line_num, obj_name, prefix):
    log("replace_setter: ==> #" + str(line_num) + " " + line.replace("\n", ""))
    setter_prefix = prefix
    if obj_name != None:
        setter_prefix = obj_name + "." + prefix
    index_indent = line.find(setter_prefix) 
    if index_indent != 0 and line[index_indent - 1] != ' ': # 并不是我们要找的set方法
        log("replace_setter: Info --> Not setter begin.")
        return line
    indent_str = line[0 : index_indent] # 替换内容前的其他内容
    index_var_name = index_indent + len(setter_prefix) # 变量名index
    first_char = line[index_var_name].lower() # 变量名首字母小写
    index_first_left_parenthesis = line.find('(', index_var_name)
    index_last_right_parenthesis = line.rfind(')', index_var_name) # 假定这一行就只做了setXxx，不去纠结last_right_parenthesis和first_left_parenthesis是不是match，只做简单校验
    if not is_parenthesis_match(line, index_first_left_parenthesis, index_last_right_parenthesis): # 如果parentheses不匹配，则不修改，并报错
        log("replace_setter: Error --> Parentheses won't match, please check manually!")
        return line
    var_name = first_char + line[(index_var_name + 1) : index_first_left_parenthesis]
    var_value = line[(index_first_left_parenthesis + 1) : index_last_right_parenthesis]
    if line.find(";") == index_last_right_parenthesis + 1: # 这一行就只做了setXxx
        if obj_name != None:
            line = indent_str + obj_name + "." + var_name + " = " + var_value + ";\n"
        else:
            line = indent_str + "this." + var_name + " = " + var_value + ";\n"
    else:
        log("replace_setter: Error --> setXxx is not the only business in this line, please check manually!")
    log("replace_setter: --> *" + str(line_num) + " " + line)
    return line

def has_property_or_function(class_props_and_funcs_dict, class_path, type, value):
    return value in class_props_and_funcs_dict[class_path][type]

# 是否为需要进行替换的getter/setter调用
def should_replace_getter_setter(class_info_dict, class_props_and_funcs_dict, class_path, line, obj_name, prefix):
    obj_prefix = prefix
    if obj_name != None:
        obj_prefix = obj_name + "." + prefix
    obj_prefix_index = line.find(" " + obj_prefix)
    if obj_prefix_index < 0 and line.startswith(obj_prefix):
        obj_prefix_index = 0
    var_start = obj_prefix_index + len(obj_prefix)
    # 先校验是否包含getter/setter调用
    if obj_prefix_index >= 0 and line[var_start].isalpha():
        property_name = find_declaration_after(line, var_start)
        function_name = prefix + property_name
        property_name = property_name[0].lower() + property_name[1 : len(property_name)]
        # 检查该属性是否在该类中有定义、且没有override
        if has_property_or_function(class_props_and_funcs_dict, class_path, class_index_properties, property_name) and not has_property_or_function(class_props_and_funcs_dict, class_path, class_index_functions, function_name):
            return True
        # 检查是否有父类
        elif class_info_dict[class_path][index_parent_import_path] != '':
            if has_property_or_function(class_props_and_funcs_dict, class_info_dict[class_path][index_parent_import_path], class_index_properties, property_name) and not has_property_or_function(class_props_and_funcs_dict, class_info_dict[class_path][index_parent_import_path], class_index_functions, function_name):
                return True
    else: # 不是getter/setter调用
        return False

# 解析类属性名
def getPropertyName(content, line_index):
    line = content[line_index]
    # print("getPropertyName: --> #" + str(line_index + 1) + " " + line)
    property_name = None
    if line.find("{") >= 0 or line.find("}") >= 0: # 包含大括号的都认为不是属性声明
        # print("getPropertyName: --> contains { or }")
        return property_name, line_index + 1
    while line.find(";") < 0 and line_index < len(content) - 1: # 这一行没有结束
        line_index += 1
        line += content[line_index] # 拼接下一行，直到遇到;号
    if line.find(";") < 0: # 认为不是属性声明
        return property_name, line_index
    line.replace("\n", " ")
    index_parenthesis = line.find("(")
    index_assignment = line.find("=")
    if index_parenthesis < 0: # 没有(号
        if index_assignment > 0: # 带赋值的声明
            property_name = find_declaration_before(line, index_assignment)
        else: # 不带赋值的声明
            property_name = find_declaration_before(line, line.find(";"))
    elif index_assignment > 0 and index_assignment < index_parenthesis: # 带初始化赋值的声明
        property_name = find_declaration_before(line, index_assignment)
    # print("getPropertyName: --> " + str(property_name))
    return property_name, line_index + 1

# 解析类方法名
def getFunctionName(content, line_index):
    line = content[line_index]
    # print("getFunctionName: --> #" + str(line_index + 1) + " " + line)
    function_name = None
    if line.find("(") > 0 and line.find("{") > 0 and line.find("class ") < 0 and line.find("=") < 0: # 认为是方法声明
        function_name = find_declaration_before(line, line.find("("))
    # print("getFunctionName: --> " + str(function_name))
    return function_name, line_index + 1

# 解析类的属性和方法
def parse_class_proterties_and_functions(class_props_and_funcs_dict, class_path, class_info):
    # log("parse_class_proterties_and_functions: --> " + class_path)
    properties = []
    functions = []
    f = open(class_info[index_src_file], "r", encoding='utf-8') # r打开：文件内容不变
    content = f.readlines() # 修改前的文件内容
    f.close()
    class_start = class_info[index_class_start_line_num]
    class_end = class_info[index_class_end_line_num]
    line_index = class_start - 1 # 行号
    while line_index + 1 < class_end:
        property_name, line_index = getPropertyName(content, line_index)
        if property_name != None:
            properties.append(property_name)
        else:
            function_name, line_index = getFunctionName(content, line_index)
            if function_name != None and function_name != class_info[index_class_name]: # 非constructor的方法名
                functions.append(function_name)
    # log("properties: " + list_str(properties))
    # log("functions: " + list_str(functions))
    class_props_and_funcs_dict[class_path] = [[], []]
    class_props_and_funcs_dict[class_index_properties] = properties
    class_props_and_funcs_dict[class_index_functions] = functions

def is_inside_lombok_class(file_info_dict, lombok_file, line_num):
    classes = file_info_dict[lombok_file][file_index_classes]
    for class_name, class_info in classes.items():
        if LOMBOK_ANNOTATION_Data in class_info[classes_index_annotations] and line_num in range(class_info[classes_index_start_line_num], class_info[classes_index_end_line_num]):
            return True
    return False

# 修改lombok @Data定义的文件
# @Return lombok类属性字典：属性：属性是否有重定义getter/setter
def process_lombok_file(file_info_dict, class_info_dict, class_props_and_funcs_dict, lombok_file, save_modification):
    log("process_lombok_file: --> " + lombok_file)
    properties = {} # lombok类属性字典：属性：属性是否有重定义getter/setter
    f = open(lombok_file, "r", encoding='utf-8') # r打开：文件内容不变
    content = f.readlines() # 修改前的文件内容
    f.close()
    content_new = '' # 修改后的文件内容
    line_num = 0 # 行号
    setter_prefix = "set"
    getter_prefix = "get"
    for line_index in range(0, len(content)):
        line_num = line_index + 1
        line = content[line_index]
        # 删掉import和@Data的行
        if line.find(LOMBOK_IMPORT_Data) >= 0 or line.find("@" + LOMBOK_ANNOTATION_Data) >= 0: 
            # 跳过这一行，相当于删除
            # print("process_lombok_file: --> remove")
            continue
        # 不在lombok class内部，不处理
        elif not is_inside_lombok_class(file_info_dict, lombok_file, line_num):
            content_new += line
        # 替换属性定义（而非方法定义）的private为public
        elif line.find("private ") >= 0 and line.find("(") < 0: 
            line = line.replace("private ", "public ")
            index_assignment = line.find("=")
            if index_assignment > 0: # 带赋值
                tmp = line[0 : index_assignment].strip()
                prop = tmp[tmp.rfind(" ") + 1 : len(tmp)]
                properties[prop] = "" # 默认没有override getter/setter
            else: # 不带赋值
                tmp = line[0 : line.find(";")].strip()
                prop = tmp[tmp.rfind(" ") + 1 : len(tmp)]
                properties[prop] = "" # 默认没有override getter/setter
            # print("process_lombok_file: --> replace private: " + line)
            content_new += line
        else:
            # 是否为setter调用
            if should_replace_getter_setter(class_info_dict, class_props_and_funcs_dict, lombok_class, line, None, setter_prefix):
                # 将调用本类的setXxx(...)都替换为this.xxx = ... 
                line = replace_setter(line, line_num, None, setter_prefix)
            # 是否为getter调用
            elif should_replace_getter_setter(class_info_dict, class_props_and_funcs_dict, lombok_class, line, None, getter_prefix):
                # todo 暂未发现调用本类getter方法的地方，先不考虑
                log("process_lombok_file: Error --> Found unprocessed getter call!")
                # line = replace_getter(line, line_num, None, getter_prefix)
            content_new += line
    # print("\n\n")
    # print(content_new)

    if save_modification:
        # 把修改后的内容写入文件
        wf=open(lombok_file,'w',encoding='utf-8')  # w打开：覆盖原文件
        wf.write(content_new)
        wf.close()

    return properties

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

# 查找变量声明结束的下标
def find_declaration_end(line, var_start, end):
    var_terminator = " =:,;<>()[]{}\n"
    for var_end in range(var_start, end): # [var_start, end)
        if line[var_end] in var_terminator:
            return var_end
    return end

# 查找line中从下标var_start开始的变量/函数名（可能不是完整的变量or函数名，取决于var_start）
def find_declaration_after(line, var_start):
    temp = line[var_start : len(line)].strip()
    var_end = find_declaration_end(temp, 0, len(temp))
    if var_end > 0:
        return temp[0 : var_end].strip()
    else:
        return None

# 查找变量声明开始的下标
def find_declaration_start(line, start, var_end):
    var_terminator = " =:,;<>()[]{}\n"
    for var_start in range(var_end - 1, start - 1, -1): # [var_end - 1, start - 1)
        if line[var_start] in var_terminator:
            return var_start + 1
    return start

# 查找line中从下标var_end之前的变量/函数名（可能不是完整的变量or函数名，取决于var_end）
def find_declaration_before(line, var_end):
    temp = line[0 : var_end].strip()
    var_start = find_declaration_start(temp, 0, len(temp))
    if var_start >= 0:
        return temp[var_start : len(temp)].strip()
    else:
        return None

# 处理引用lombok的文件
# @param is_same_package 是否为同一个package下的，同一package不需要import
def process_lombok_referred_file(class_info_dict, class_props_and_funcs_dict, lombok_class_name, lombok_import_path, is_same_package, ref_file, save_modification):
    log("process_lombok_referred_file: --> " + ref_file)
    f = open(ref_file)      # 返回一个文件对象  
    content = f.readlines() # 修改前的文件内容
    content_new = ''        # 修改后的文件内容
    f.close()
    line_num = 0            # 行号
    obj_list = []           # 对象名列表
    ref_count = 0
    for line in content:
        line_num += 1 
        if line.find(lombok_class_name) >= 0 and line.find(lombok_import_path) < 0: # 非import的class引用
            ref_count = ref_count + 1
        if line.find(" " + lombok_class_name + " ") >= 0 or line.startswith(lombok_class_name + " "): # 变量声明
            var_start = line.find(lombok_class_name) + len(lombok_class_name) + 1 # 假定class name和var name中间只有一个空格
            obj_name = find_declaration_after(line, var_start)
            if obj_name != None:
                log("process_lombok_referred_file: --> Find object: \"" + obj_name + "\" in line #" + str(line_num) + " \"" + line.replace("\n", "") + "\"")
                if obj_name not in obj_list:
                    obj_list.append(obj_name) 
                    
    log("process_lombok_referred_file: --> obj_list = " + str(obj_list))
    # 如果没有找到引用，直接删除import语句，或结束
    if ref_count == 0:
        if is_same_package: # 同一package，没有引用，则不需要修改
            return
        log("process_lombok_referred_file: Info --> No reference found, remove import.")
        for line in content:
            if line.find(lombok_import_path) < 0:
                content_new += line
        # 把修改后的内容写入文件
        wf=open(ref_file,'w',encoding='utf-8')  # w打开：覆盖原文件
        wf.write(content_new)
        wf.close()
        return
    elif obj_list == []:
        log("process_lombok_referred_file: Info --> No variable found while references are present.")
        return
    else:
        line_num = 0 # 行号
        for line in content:
            line_num += 1
            for obj_name in obj_list:
                # log("process_lombok_referred_file: ==> #" + str(line_num) + " " + line)
                setter_prefix = "set"
                # obj_setter_prefix = obj_name + "." + setter_prefix
                getter_prefix = "get"
                # obj_getter_prefix = obj_name + "." + getter_prefix
                is_prefix = "is"
                # obj_is_prefix = obj_name + "." + is_prefix
                # 将obj_name.setXxx(...)都替换为obj_name.xxx = ... 
                if should_replace_getter_setter(class_info_dict, class_props_and_funcs_dict, lombok_class, line, obj_name, setter_prefix):
                # if line.find(obj_setter_prefix) >= 0 and line[line.find(obj_setter_prefix) + len(obj_setter_prefix)].isalpha(): 
                    line = replace_setter(line, line_num, obj_name, setter_prefix)
                # 将obj_name.getXxx()都替换为obj_name.xxx
                elif should_replace_getter_setter(class_info_dict, class_props_and_funcs_dict, lombok_class, line, obj_name, getter_prefix):
                # elif line.find(obj_getter_prefix) >= 0 and line[line.find(obj_getter_prefix) + len(obj_getter_prefix)].isalpha(): 
                    line = replace_getter(line, line_num, obj_name, getter_prefix)
                # 将obj_name.isXxx()都替换为obj_name.xxx
                # elif line.find(obj_is_prefix) >= 0 and line[line.find(obj_is_prefix) + len(obj_is_prefix)].isalpha(): 
                elif should_replace_getter_setter(class_info_dict, class_props_and_funcs_dict, lombok_class, line, obj_name, is_prefix):
                    line = replace_getter(line, line_num, obj_name, is_prefix)
            content_new += line    

    if save_modification:
        # 把修改后的内容写入文件
        wf=open(ref_file,'w',encoding='utf-8')  # w打开：覆盖原文件
        wf.write(content_new)
        wf.close()

if __name__=='__main__':
    # print(list_str(sys.argv))
    if len(sys.argv) >= 3 and sys.argv[2] == "1":
        DEBUG = True
    if len(sys.argv) >= 4 and sys.argv[3] == "1":
        SINGLE_FILE = True

    print("SINGLE_FILE = " + str(SINGLE_FILE))
    print("DEBUG = " + str(DEBUG))
    if SINGLE_FILE:
        parse_classes_in_file(sys.argv[1], class_info_dict, file_info_dict)
    else:
        # 获取所有的java文件
        all_java_files = all_filtered_files(sys.argv[1], pass_filter, fail_filter) # 从命令行接收一个输入作为路径，获取
        # log("main: --> All java files: \n" + list_str(all_java_files) + "\n")
        log("main: --> Scaned " + str(len(all_java_files)) + " java files.")
        
        # 初始化查询表
        for file in all_java_files:
            parse_classes_in_file(file, class_info_dict, file_info_dict)
        log("main: --> file_info_dict.length = " + str(len(file_info_dict)))
        log("main: --> class_info_dict.length = " + str(len(class_info_dict)))
        
        all_lombok_classes = filter_dict_items(class_info_dict, [index_imports, index_class_annotations], [LOMBOK_IMPORT_Data, LOMBOK_ANNOTATION_Data])
        log("main: --> Scaned " + str(len(all_lombok_classes)) + " lombok classes.")
        # log(list_str(all_lombok_classes))

        # 初始化lombok属性、方法表
        for lombok_class in all_lombok_classes:
            parse_class_proterties_and_functions(class_props_and_funcs_dict, lombok_class, class_info_dict[lombok_class])
        
        all_lombok_files = filter_dict_items(file_info_dict, [file_index_imports], [LOMBOK_IMPORT_Data])
        log("main: --> Scaned " + str(len(all_lombok_files)) + " lombok files.")
        # log(list_str(all_lombok_files))
        
        total_count = 0 # 处理的总文件数

        # 处理lombok文件
        for lombok_file in all_lombok_files:
            process_lombok_file(file_info_dict, class_info_dict, class_props_and_funcs_dict, lombok_file, save_modification=SAVE_MODIFICATION) 
            log("main: --> Finish process lombok file: " + lombok_file)
            total_count += 1

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

                count = 0
                for lombok_referred_file in files_import_lombok:
                    process_lombok_referred_file(class_info_dict, class_props_and_funcs_dict, lombok_class_info[index_class_name], lombok_class, is_same_package=False, ref_file=lombok_referred_file, save_modification=SAVE_MODIFICATION)
                    count = count + 1
                    total_count += 1
                for lombok_referred_file in files_of_same_package:
                    process_lombok_referred_file(class_info_dict, class_props_and_funcs_dict, lombok_class_info[index_class_name], lombok_class, is_same_package=True, ref_file=lombok_referred_file, save_modification=SAVE_MODIFICATION)
                    count = count + 1
                    total_count += 1
                log("main: --> Finish process " + str(count) + " file(s) that refer " + lombok_class + "\n")

            if MAX_TOTAL_COUNT > 0 and total_count >= MAX_TOTAL_COUNT:
                log("main: --> Done processing " + str(total_count) + " files.\n")
                exit(0)
        log("main: --> Done processing " + str(total_count) + " files.\n")
