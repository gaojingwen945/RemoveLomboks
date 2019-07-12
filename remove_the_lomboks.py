#!/usr/bin/python
# -*- coding: UTF-8 -*-

import os
import sys
import time

filter = [".java"] # 设置过滤后的文件类型 当然可以设置多个类型
index_class_name = 0
index_package = 1
index_imports = 2
index_class_annotations = 3
file_info_dict = {} # 查询字典：file_path：[class_name, package, imports[], class_annotations[]]
save_modification = False
MAX_TOTAL_COUNT = -1 # 处理的文件数上限（可能会超过一点），负数表示无上限
FILE_LOG = True
time_str = time.strftime('%Y-%m-%d_%H_%M_%S', time.localtime())
LOG_FILE_NAME = 'remove_lomboks_' + time_str + '.log'

def log(log_str):
    time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + ": "
    # time_str = ''
    print(time_str + str(log_str))
    if FILE_LOG:
        with open(LOG_FILE_NAME, 'a') as file_object:
            file_object.write(time_str + log_str + "\n")

# 获取指定路径下所有filter过滤后的文件
def all_filtered_files(dirname, filter):
    result = []
    for maindir, subdir, file_name_list in os.walk(dirname): # 遍历dirname
        # print("\n")
        # print("1:",maindir) # 当前目录
        # print("2:",subdir)  # 当前目录下的所有子目录
        # print("3:",file_name_list)  # 当前目录下的所有文件

        for filename in file_name_list:
            apath = os.path.join(maindir, filename)# 合并成一个完整路径
            ext = os.path.splitext(apath)[1]  # 获取文件后缀[0]获取的是除了文件名以外的内容

            if ext in filter:
                result.append(apath)

    return result

# # 从传入的列表中，获取所有 从文件开始到stop_sign为止 的范围内包含指定关键字key的文件
# def all_files_contains_key(path_list, key, stop_sign=None):
#     result = []
    
#     for path in path_list:
#         # print("\n parsing file: " + path)
#         f = open(path)             # 返回一个文件对象  
#         line = f.readline()        # 调用文件的 readline()方法  
#         while line:  
#             # # print line,          # 后面跟 ',' 将忽略换行符  
#             # print(line, end='')    # 在 Python 3中使用  

#             if line.find(key) >= 0:
#                 result.append(path)
#                 # print(line, end='')
#                 # print("all_path_contains_key: --> break on keyword found: " + key)
#                 break
#             else:
#                 if stop_sign != None and line.find(stop_sign) >= 0:
#                     # print("all_path_contains_key: --> break when stop_sign meets: " + stop_sign)
#                     break
#                 line = f.readline()  

#         f.close()  

#     return result

# 返回class_name, package, imports[], class_annotations[]
def get_class_info(src_file):
    log("get_class_info: --> " + src_file)
    f = open(src_file)         # 返回一个文件对象  
    line = f.readline()        # 调用文件的 readline()方法  
    line_num = 0
    class_name_start = src_file.rindex("/") + 1
    class_name_end = src_file.rindex(".")
    class_name = src_file[class_name_start : class_name_end]
    package = ''
    imports = []
    class_annotations = []
    key_package = "package "
    key_import = "import "
    key_annotation = "@"
    while line:  
        # print("#" + str(line_num) + " " + line)
        line_num += 1
        if line.startswith(key_package):
            package_start = line.index(key_package) + len(key_package)
            package_end = line.rindex(";")
            package = line[package_start : package_end]
        elif line.startswith(key_import):
            import_start = line.index(key_import) + len(key_import)
            import_end = line.rfind(";")
            if import_end < 0: # 换行了
                next_line = f.readline().strip()
                line = line.replace("\n", "").rstrip() + next_line # 拼接
                import_end = len(line)
            imports.append(line[import_start : import_end])
        elif line.startswith(key_annotation):
            annotation_start = line.index(key_annotation) + len(key_annotation)
            annotation_end = line.find(" ")
            if annotation_end == -1:
                annotation_end = line.find("(")
            if annotation_end == -1:
                annotation_end = line.find("\n")
            if annotation_end == -1:
                annotation_end = len(line)
            class_annotations.append(line[annotation_start : annotation_end])
        elif line.find("class ") >= 0: # 遇到class定义了，停止遍历
            break
        line = f.readline()  
    # print("class_name = " + class_name + ", package = " + package)
    # print("imports = " + list_str(imports))
    # print("class_annotations = " + list_str(class_annotations))
    return class_name, package, imports, class_annotations

# 所有类型为type_index的信息中包含指定value的文件，只处理str / list
def all_files_have_value_in_type(file_info_dict, type_index, value):
    result = []
    for path, info in file_info_dict.items():
        type_info = info[type_index]
        # print(path + list_str(type_info))
        if isinstance(type_info, str) and type_info.find(value) >= 0:
            result.append(path)
        elif isinstance(type_info, list):
            try:
                if type_info.index(value) >= 0:
                    result.append(path)
            except:
                continue
    return result

# 检查括号是否匹配
def is_bracket_match(str, index_left_bracket, index_right_bracket):
    left_count = str.count("(", index_left_bracket + 1, index_right_bracket)
    right_count = str.count(")", index_left_bracket + 1, index_right_bracket)
    return left_count == right_count

# 替换setter，
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
    index_first_left_bracket = line.find('(', index_var_name)
    index_last_right_bracket = line.rfind(')', index_var_name) # 假定这一行就只做了setXxx，不去纠结last_right_bracket和first_left_bracket是不是match，只做简单校验
    if not is_bracket_match(line, index_first_left_bracket, index_last_right_bracket): # 如果brackets不匹配，则不修改，并报错
        log("replace_setter: Error --> Brackets won't match, please check manually!")
        return line
    var_name = first_char + line[(index_var_name + 1) : index_first_left_bracket]
    var_value = line[(index_first_left_bracket + 1) : index_last_right_bracket]
    if line.find(";") == index_last_right_bracket + 1: # 这一行就只做了setXxx
        if obj_name != None:
            line = indent_str + obj_name + "." + var_name + " = " + var_value + ";\n"
        else:
            line = indent_str + "this." + var_name + " = " + var_value + ";\n"
    else:
        log("replace_setter: Error --> setXxx is not the only business in this line, please check manually!")
    log("replace_setter: --> #" + str(line_num) + " " + line)
    return line

# 修改lombok @Data定义的文件
def process_lombok_file(lombok_file, save_modification):
    log("process_lombok_file: --> " + lombok_file)
    f = open(lombok_file, "r", encoding='utf-8') # r打开：文件内容不变
    content = f.readlines() # 修改前的文件内容
    f.close()
    content_new = '' # 修改后的文件内容
    line_num = 0 # 行号
    setter_prefix = "set"
    for line in content:
        line_num += 1
        # 删掉import和@Data的行
        if line.find("lombok.Data") >= 0 or line.find("@Data") >= 0: 
            # 跳过这一行，相当于删除
            # print("process_lombok_file: --> remove")
            continue
        # 替换private为public
        elif line.find("private ") >= 0: 
            line = line.replace("private ", "public ")
            # print("process_lombok_file: --> replace private: " + line)
            content_new += line
        # 将调用本类的setXxx(...)都替换为this.xxx = ... 
        elif (line.startswith(setter_prefix) or line.find(" " + setter_prefix) >= 0) and line[line.find(setter_prefix) + len(setter_prefix)].isalpha(): 
            line = replace_setter(line, line_num, None, setter_prefix)
            content_new += line
        else:
            # print("process_lombok_file: --> do nothing")
            content_new += line
    # print("\n\n")
    # print(content_new)

    if save_modification:
        # 把修改后的内容写入文件
        wf=open(lombok_file,'w',encoding='utf-8')  # w打开：覆盖原文件
        wf.write(content_new)
        wf.close()

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

# 替换obj_name.prefixXxx()为obj_name.xxx
# @param prefix: "get" or "is"
def replace_getter(line, line_num, obj_name, prefix):
    log("replace_getter: ==> #" + str(line_num) + " " + line.replace("\n", ""))
    getter_prefix = obj_name + "." + prefix
    index_indent = line.find(getter_prefix)
    # indent_str = line[0 : index_indent] # 替换内容前的其他内容
    index_var_name = index_indent + len(getter_prefix) # 变量名index
    first_char = line[index_var_name].lower() # 变量名首字母小写
    index_brackets = line.find('()', index_var_name)
    var_name = first_char + line[(index_var_name + 1) : index_brackets]
    line = line.replace(getter_prefix + line[index_var_name : index_brackets + 2], obj_name + "." + var_name)
    log("replace_getter: --> #" + str(line_num) + " " + line)
    return line

# 查找变量声明结束的下标
def find_declaration_end(line, var_start, end):
    var_end = line.find(" ", var_start, end) # 用空格分隔
    if var_end < 0:
        var_end = line.find("=", var_start, end) # 变量赋值
    if var_end < 0:
        var_end = line.find(";", var_start, end) # 变量声明
    if var_end < 0:
        var_end = line.find(")", var_start, end) # 参数声明
    if var_end < 0:
        var_end = line.find(":", var_start, end) # 迭代器
    if var_end < 0:
        var_end = line.find("\n", var_start, end) # 换行
    if var_end > var_start:
        var = line[var_start : var_end]
        if var.find("=") >= 0 or var.find(";") >= 0 or var.find(")") >= 0 or var.find(":") >= 0 or var.find("\n") >= 0:
            return find_declaration_end(line, var_start, var_end)
        else:
            return var_end
    else:
        return -1

# 处理引用lombok的文件
# @param is_same_package 是否为同一个package下的，同一package不需要import
def process_lombok_referred_file(class_name, import_path, is_same_package, ref_file, save_modification):
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
        if line.find(class_name) >= 0 and line.find(import_path) < 0: # 非import的class引用
            ref_count = ref_count + 1
        if line.find(" " + class_name + " ") >= 0 or line.startswith(class_name + " "): # 变量声明
            var_start = line.find(class_name) + len(class_name) + 1 # 假定class name和var name中间只有一个空格
            var_end = find_declaration_end(line, var_start, len(line))

            if var_end > var_start:
                obj_name = line[var_start : var_end]
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
            if line.find(import_path) < 0:
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
                obj_setter_prefix = obj_name + "." + setter_prefix
                getter_prefix = "get"
                obj_getter_prefix = obj_name + "." + getter_prefix
                is_prefix = "is"
                obj_is_prefix = obj_name + "." + is_prefix
                # 将obj_name.setXxx(...)都替换为obj_name.xxx = ... 
                if line.find(obj_setter_prefix) >= 0 and line[line.find(obj_setter_prefix) + len(obj_setter_prefix)].isalpha(): 
                    line = replace_setter(line, line_num, obj_name, setter_prefix)
                # 将obj_name.getXxx()都替换为obj_name.xxx
                elif line.find(obj_getter_prefix) >= 0 and line[line.find(obj_getter_prefix) + len(obj_getter_prefix)].isalpha(): 
                    line = replace_getter(line, line_num, obj_name, getter_prefix)
                # 将obj_name.isXxx()都替换为obj_name.xxx
                elif line.find(obj_is_prefix) >= 0 and line[line.find(obj_is_prefix) + len(obj_is_prefix)].isalpha(): 
                    line = replace_getter(line, line_num, obj_name, is_prefix)
            content_new += line    

    if save_modification:
        # 把修改后的内容写入文件
        wf=open(ref_file,'w',encoding='utf-8')  # w打开：覆盖原文件
        wf.write(content_new)
        wf.close()

if __name__=='__main__':
    # 获取所有的java文件
    all_java_files = all_filtered_files(sys.argv[1], filter) # 从命令行接收一个输入作为路径，获取
    # log("main: --> All java files: \n" + list_str(all_java_files) + "\n")
    log("main: --> Scaned " + str(len(all_java_files)) + " java files.\n")
    
    # 初始化查询表
    for file in all_java_files:
        class_name, package, imports, class_annotations = get_class_info(file)
        file_info_dict[file] = [class_name, package, imports, class_annotations]
        # print(file_info_dict[file])
    
    # all_lombok_files = all_files_contains_key(all_java_files, "lombok.Data", "class ")
    all_lombok_files = all_files_have_value_in_type(file_info_dict, index_imports, "lombok.Data")
    # log("main: --> All lombok files: \n" + list_str(all_lombok_files) + "\n")
    log("main: --> Scaned " + str(len(all_lombok_files)) + " lombok files.\n")
    
    total_count = 0 # 处理的总文件数
    for lombok_file in all_lombok_files:
        # 处理有引用lombok文件的文件
        # class_name, import_path = find_full_path(lombok_file)
        class_name, package, imports, class_annotations = file_info_dict[lombok_file]

        # 文件中有import lombok文件的文件
        # files_import_lombok_file = all_files_contains_key(all_java_files, import_path) 
        import_path = package + "." + class_name
        files_import_lombok_file = all_files_have_value_in_type(file_info_dict, index_imports, import_path)
        log("main: --> All files that import \"" + import_path + "\":\n" + list_str(files_import_lombok_file))

        # 和lombok文件处于同一package的文件
        files_of_same_package = all_files_have_value_in_type(file_info_dict, index_package, package)
        files_of_same_package.remove(lombok_file)
        log("main: --> All files that in the same package as \"" + import_path + "\":\n" + list_str(files_of_same_package))

        count = 0
        for lombok_referred_file in files_import_lombok_file:
            process_lombok_referred_file(class_name, import_path, is_same_package=False, ref_file=lombok_referred_file, save_modification=save_modification)
            count = count + 1
            total_count += 1
        for lombok_referred_file in files_of_same_package:
            process_lombok_referred_file(class_name, import_path, is_same_package=True, ref_file=lombok_referred_file, save_modification=save_modification)
            count = count + 1
            total_count += 1
        log("main: --> Finish process " + str(count) + " file(s) that refer " + lombok_file + "\n")

        # 最后处理lombok文件
        process_lombok_file(lombok_file, save_modification=save_modification) 
        log("main: --> Finish process lombok file: " + lombok_file + "\n")
        total_count += 1
        if MAX_TOTAL_COUNT > 0 and total_count >= MAX_TOTAL_COUNT:
            log("main: --> Done processing " + str(total_count) + " files.\n")
            exit(0)
    log("main: --> Done processing " + str(total_count) + " files.\n")
