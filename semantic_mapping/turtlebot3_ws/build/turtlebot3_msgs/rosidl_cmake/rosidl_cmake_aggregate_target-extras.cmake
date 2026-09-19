# generated from rosidl_cmake/cmake/rosidl_cmake_aggregate_target-extras.cmake.in

# Create a convenience aggregate target turtlebot3_msgs::turtlebot3_msgs
# that links all generated interface targets, so downstream packages can use
# a single modern CMake target name instead of ${turtlebot3_msgs_TARGETS}.
if(turtlebot3_msgs_TARGETS AND NOT TARGET turtlebot3_msgs::turtlebot3_msgs)
  add_library(turtlebot3_msgs::turtlebot3_msgs INTERFACE IMPORTED)
  set_target_properties(turtlebot3_msgs::turtlebot3_msgs PROPERTIES
    INTERFACE_LINK_LIBRARIES "${turtlebot3_msgs_TARGETS}")
endif()
