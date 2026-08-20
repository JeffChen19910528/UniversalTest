cmake_minimum_required(VERSION 3.20)
project(cpp_cmake_fixture CXX)

set(CMAKE_CXX_STANDARD 17)

add_executable(app src/main.cpp src/widget.cpp)

enable_testing()
find_package(GTest REQUIRED)
add_executable(app_tests tests/widget_test.cpp)
target_link_libraries(app_tests GTest::gtest_main)
add_test(NAME widget_tests COMMAND app_tests)
