---
title: CMake语法简介
description: 偶然了解到一个用cmake构建的mlsys工程，于是简单了解了一下cmake的语法
---

## 一、基本语法结构

### 1. 注释
```cmake
# 这是单行注释

#[[
这是
多行注释
]]
```

### 2. 基本命令格式
```cmake
command_name(arg1 arg2 ...)  # 命令名(参数1 参数2 ...)
```

**注意**：CMake 不区分大小写，但**推荐统一使用小写**（现代 CMake 风格）。

---

## 二、变量操作

### 定义与引用变量
```cmake
# 设置变量
set(MY_VAR "Hello")
set(NUMBERS 1 2 3 4)          # 列表（用分号分隔的字符串）
set(FLAG ON)                  # 布尔值：ON/OFF, TRUE/FALSE, 1/0

# 引用变量（使用 ${}）
message("Value: ${MY_VAR}")

# 列表操作
list(APPEND NUMBERS 5)        # 追加元素
list(LENGTH NUMBERS len)      # 获取长度
list(GET NUMBERS 0 first)     # 获取索引0的元素
```

### 变量作用域
```cmake
# 普通变量：仅当前作用域有效
set(LOCAL_VAR "local")

# CACHE 变量：持久化到缓存，命令行可覆盖
set(CACHE_VAR "default" CACHE STRING "描述信息")

# 环境变量
set(ENV{PATH} "$ENV{PATH}:/new/path")
```

---

## 三、核心构建命令

### 项目与版本
```cmake
cmake_minimum_required(VERSION 3.15)    # 最低版本要求
project(MyProject                       # 项目名称
    VERSION 1.0.0                       # 版本号
    DESCRIPTION "项目描述"
    LANGUAGES CXX)                      # 使用语言：C, CXX, CUDA等
```

### 生成可执行文件
```cmake
add_executable(app_name 
    main.cpp 
    utils.cpp
)
```

### 生成库
```cmake
# 静态库
add_library(my_static STATIC src.cpp)

# 动态库/共享库
add_library(my_shared SHARED src.cpp)

# 对象库（不直接链接，用于组合）
add_library(my_objects OBJECT src1.cpp src2.cpp)

# 接口库（仅头文件，无源文件）
add_library(my_header INTERFACE)
```

### 链接库
```cmake
# 链接到目标
target_link_libraries(app_name 
    PRIVATE my_lib      # 仅当前目标使用
    PUBLIC dep_lib      # 当前及依赖此目标的目标都使用
    INTERFACE header_lib # 仅依赖此目标的目标使用
)

# 现代CMake推荐：配合 target_ 命令使用
target_include_directories(app_name PRIVATE include/)
target_compile_definitions(app_name PRIVATE DEBUG=1)
target_compile_options(app_name PRIVATE -Wall -Wextra)
```

---

## 四、条件与循环

### 条件判断
```cmake
if(CONDITION)
    # ...
elseif(OTHER_CONDITION)
    # ...
else()
    # ...
endif()

# 常见条件
if(EXISTS "${CMAKE_SOURCE_DIR}/file.txt")  # 文件存在
if(IS_DIRECTORY "${CMAKE_SOURCE_DIR}/dir") # 是目录
if(VARIABLE)                               # 变量为真（非空、非0、非OFF等）
if(NOT VARIABLE)
if(VAR1 AND VAR2)
if(VAR1 OR VAR2)
if(VAR STREQUAL "string")                  # 字符串比较
if(VERSION_GREATER ${VER1} ${VER2})        # 版本比较
```

### 循环
```cmake
# foreach 循环
set(items a b c)
foreach(item IN LISTS items)
    message("Item: ${item}")
endforeach()

# 范围循环
foreach(i RANGE 1 10)
    message("i = ${i}")
endforeach()

# while 循环
set(i 0)
while(i LESS 10)
    math(EXPR i "${i} + 1")
    message("i = ${i}")
endwhile()
```

---

## 五、函数与宏

### 定义函数
```cmake
function(my_function arg1 arg2)
    # ARGC: 参数总数
    # ARGV: 所有参数列表
    # ARGN: 超出命名参数的参数
    
    message("First arg: ${arg1}")
    message("All args: ${ARGV}")
    
    # 设置返回值（通过父作用域变量）
    set(result "computed" PARENT_SCOPE)
endfunction()

my_function(1 2 3)
message("Result: ${result}")  # 输出: computed
```

### 定义宏
```cmake
macro(my_macro arg)
    # 宏直接展开，不创建新作用域
    message("Arg: ${arg}")
endmacro()
```

**区别**：`function` 创建新作用域，`macro` 直接文本替换（类似 C 预处理器）。

---

## 六、模块与包含

### 包含其他 CMake 文件
```cmake
# 包含模块（从 CMAKE_MODULE_PATH 查找）
include(FindPackageHandleStandardArgs)
include(ExternalProject)

# 包含自定义 .cmake 文件
include(${CMAKE_SOURCE_DIR}/cmake/utils.cmake)

# 添加子目录（执行该目录下的 CMakeLists.txt）
add_subdirectory(src)
add_subdirectory(extern/lib EXCLUDE_FROM_ALL)  # 不构建默认目标
```

### 查找包
```cmake
# 查找系统包
find_package(Boost 1.70 REQUIRED COMPONENTS system thread)
find_package(OpenCV REQUIRED)

# 使用查找结果
if(Boost_FOUND)
    target_link_libraries(my_target PRIVATE Boost::system)
endif()

# 查找库文件
find_library(MATH_LIB m)
find_path(OPENSSL_INCLUDE_DIR openssl/ssl.h)

# 查找程序
find_program(PYTHON_EXECUTABLE python3)
```

---

## 七、现代 CMake 最佳实践（重要！）

### 目标导向设计（Target-based）
```cmake
# ❌ 旧方式（全局设置，不推荐）
include_directories(include)
add_definitions(-DDEBUG)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++17")

# ✅ 新方式（目标属性，推荐）
add_library(my_lib src.cpp)
target_include_directories(my_lib 
    PUBLIC 
        $<BUILD_INTERFACE:${CMAKE_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)
target_compile_features(my_lib PUBLIC cxx_std_17)
target_compile_definitions(my_lib PRIVATE DEBUG=1)
```

### 生成器表达式（Generator Expressions）
```cmake
target_compile_definitions(app PRIVATE
    $<$<CONFIG:Debug>:DEBUG_MODE>           # Debug配置时定义
    $<$<PLATFORM_ID:Windows>:WIN32_LEAN>    # Windows平台时定义
    $<$<CXX_COMPILER_ID:GNU,Clang>:GNU_COMPAT> # GCC或Clang时
)

# 条件链接
target_link_libraries(app PRIVATE
    $<$<BOOL:${USE_OPENSSL}>:OpenSSL::SSL>
)
```

### 安装与导出
```cmake
# 安装目标
install(TARGETS my_lib
    EXPORT my_lib-targets
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
    INCLUDES DESTINATION include
)

# 安装头文件
install(DIRECTORY include/ DESTINATION include)

# 导出配置
install(EXPORT my_lib-targets
    FILE my_lib-targets.cmake
    NAMESPACE my_lib::
    DESTINATION lib/cmake/my_lib
)
```

---

## 八、实用示例：完整 CMakeLists.txt

```cmake
cmake_minimum_required(VERSION 3.15)
project(Calculator VERSION 1.0.0 LANGUAGES CXX)

# 选项
option(BUILD_TESTS "Build unit tests" ON)
option(BUILD_SHARED_LIBS "Build shared libraries" OFF)

# C++标准
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# 库
add_library(math_lib
    src/add.cpp
    src/subtract.cpp
)
target_include_directories(math_lib
    PUBLIC 
        $<BUILD_INTERFACE:${CMAKE_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

# 可执行文件
add_executable(calc app/main.cpp)
target_link_libraries(calc PRIVATE math_lib)

# 测试
if(BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()

# 安装
install(TARGETS calc math_lib
    RUNTIME DESTINATION bin
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
)
install(DIRECTORY include/ DESTINATION include)
```

---

## 九、常用变量速查

| 变量                       | 含义                                                |
| -------------------------- | --------------------------------------------------- |
| `CMAKE_SOURCE_DIR`         | 源码根目录                                          |
| `CMAKE_BINARY_DIR`         | 构建根目录                                          |
| `CMAKE_CURRENT_SOURCE_DIR` | 当前 CMakeLists.txt 所在目录                        |
| `CMAKE_CURRENT_BINARY_DIR` | 当前构建目录                                        |
| `PROJECT_NAME`             | 项目名称                                            |
| `PROJECT_VERSION`          | 项目版本                                            |
| `CMAKE_BUILD_TYPE`         | 构建类型 (Debug/Release/RelWithDebInfo/MinSizeRel)  |
| `CMAKE_CXX_COMPILER`       | C++ 编译器                                          |
| `CMAKE_INSTALL_PREFIX`     | 安装前缀（默认 `/usr/local` 或 `C:\Program Files`） |

---

CMake 3.0+ 引入了**现代 CMake** 理念，核心思想是**以目标（Target）为中心**，通过 `target_` 系列命令精确控制构建属性，避免全局设置带来的副作用。这是目前最推荐的写法。

---

## 十、 其他

### CMake 是**声明式**的，不是**命令式**的

````
CMake 配置阶段（运行 cmake 命令时）
    │
    ├── 读取所有 CMakeLists.txt
    ├── 收集所有目标（add_executable/add_library）
    ├── 收集所有关系（target_link_libraries 等）
    └── 生成构建系统（Makefile/Ninja/VS项目）
              │
              ▼
        真正的编译阶段（运行 make 命令时）
              │
              ├── 编译 ggml 的源文件 → libggml.a
              ├── 编译 llama 的源文件 → llama.o
              └── 链接：llama.o + libggml.a → llama（可执行文件）
````

